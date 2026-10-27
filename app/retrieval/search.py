"""Search the library and balance matches across files."""

from __future__ import annotations

import logging
import re

from llama_index.core import VectorStoreIndex

import config
from ingestion.plan import balance_matches
from llm.prompts import (
    asks_for_example,
    asks_for_steps,
    named_library_files,
    prompt_passage,
    source_label,
)
from retrieval.rerank import best_rerank_score, rerank_nodes

logger = logging.getLogger(__name__)


def _source_record(node, number: int, query: str = "") -> dict:
    """Keep the citation number, file, page, and the full chunk for one retrieved passage."""
    metadata = node.metadata or {}
    file_name = metadata.get("relative_path") or metadata.get("file_name") or "Document"
    page = metadata.get("page_label") or metadata.get("page_number")
    record = {
        "number": number,
        "source": file_name,
        "path": metadata.get("relative_path") or file_name,
        "text": prompt_passage(node.get_text() or ""),
    }
    if page not in (None, ""):
        record["page"] = str(page)
    record["label"] = source_label(record)
    return record


def _prefer_prose(nodes):
    """Keep a list of links from taking the slots a worked example needs."""
    prose = []
    links = []
    for node in nodes:
        text = (node.get_text() or "").lower()
        if text.count("http") >= 3:
            links.append(node)
        else:
            prose.append(node)
    return prose + links


def _prefer_focused(nodes, query: str):
    """For an example or a procedure, prefer chunks that use those words."""
    if not (asks_for_example(query) or asks_for_steps(query)):
        return _prefer_prose(nodes)
    skip = {
        "give",
        "detailed",
        "explanation",
        "each",
        "practical",
        "that",
        "this",
        "with",
        "from",
        "your",
        "what",
        "about",
        "have",
        "would",
        "could",
        "should",
        "into",
        "using",
    }
    needles = [
        word for word in re.findall(r"[a-z0-9]{4,}", query.lower()) if word not in skip
    ]

    def key(node):
        text = (node.get_text() or "").lower()
        hits = sum(word in text for word in needles)
        return (-hits, text.count("http") >= 3, -(getattr(node, "score", 0) or 0))

    return sorted(nodes, key=key)


def resolve_scope(scope: str | None, library_files: list[str]) -> list[str] | None:
    """Map a UI scope to exact relative_path values, or None for the whole library."""
    if scope is None:
        return None
    text = str(scope).strip().rstrip("/")
    if not text or text.lower() in {"all", "*", "library"}:
        return None
    if text in library_files:
        return [text]
    prefix = text + "/"
    matched = [path for path in library_files if path == text or path.startswith(prefix)]
    return matched


def _retrieve_nodes(
    index: VectorStoreIndex,
    query: str,
    library_files: list[str],
    scope: str | None = None,
):
    """Search the library. Named files boost the global pool; they never replace it.

    When ``scope`` is set (file or folder relative_path), retrieval is hard-filtered
    to that set. Returns the kept nodes and whether a named-file boost was applied.
    """
    per_file = config.retrieve_per_file()
    limit = config.retrieve_limit()
    candidates = config.retrieve_candidates()
    if asks_for_steps(query):
        per_file = max(per_file, 4)
        limit = max(limit, 4)
        candidates = max(candidates, 16)
    elif asks_for_example(query):
        candidates = max(candidates, 16)
    if config.rerank_enabled():
        candidates = max(candidates, config.rerank_candidates())
    allowed = resolve_scope(scope, library_files)
    if allowed is not None and not allowed:
        return [], False
    if allowed is not None:
        global_nodes = _retrieve_named(index, query, allowed, candidates)
    else:
        global_nodes = index.as_retriever(similarity_top_k=candidates).retrieve(query)
    nodes = global_nodes
    boosted = False
    if config.hybrid_bm25():
        from retrieval import bm25 as bm25_index

        lexical = bm25_index.retrieve_nodes(
            query, config.bm25_candidates(), allowed_paths=allowed
        )
        if lexical:
            # Keep most vector slots; reserve a slice for keyword-only hits.
            reserved = max(10, candidates // 5)
            nodes = _hybrid_merge(nodes, lexical, candidates, reserved)
            boosted = True
    named = named_library_files(query, library_files)
    if allowed is not None:
        named = [name for name in named if name in allowed]
    if named:
        pinned = _retrieve_named(index, query, named, candidates)
        if pinned:
            nodes = _merge_candidates(nodes, pinned, candidates)
            boosted = True
    ordered = _order_nodes(nodes, query)
    _log_rerank(ordered)
    return _keep(ordered, per_file, limit), boosted


def _node_key(node) -> str:
    node_id = getattr(node, "node_id", None) or getattr(node, "id_", None)
    if node_id:
        return str(node_id)
    metadata = getattr(node, "metadata", None) or {}
    text = ""
    if hasattr(node, "get_text"):
        text = node.get_text() or ""
    return f"{metadata.get('relative_path')}:{metadata.get('page_label')}:{text[:80]}"


def _merge_candidates(global_nodes, named_nodes, limit: int):
    """Put named-file hits first, then fill from the global search. Dedupe by id."""
    merged = []
    seen: set[str] = set()
    for node in list(named_nodes) + list(global_nodes):
        key = _node_key(node)
        if key in seen:
            continue
        seen.add(key)
        merged.append(node)
        if len(merged) >= limit:
            break
    return merged


def _hybrid_merge(vector_nodes, lexical_nodes, limit: int, reserved: int):
    """Vector-first pool with reserved slots filled from BM25."""
    reserved = min(reserved, limit)
    vector_budget = limit - reserved
    merged = []
    seen: set[str] = set()
    for node in vector_nodes:
        if len(merged) >= vector_budget:
            break
        key = _node_key(node)
        if key in seen:
            continue
        seen.add(key)
        merged.append(node)
    for node in lexical_nodes:
        if len(merged) >= limit:
            break
        key = _node_key(node)
        if key in seen:
            continue
        seen.add(key)
        merged.append(node)
    return merged


def _keep(nodes, per_file: int, limit: int):
    return balance_matches(
        nodes,
        per_file=per_file,
        limit=limit,
        balance_after=config.retrieve_balance_files(),
    )


def _log_rerank(nodes) -> None:
    """The logit is recorded. It does not choose the answer path."""
    score = best_rerank_score(nodes)
    if score is None:
        return
    logger.info("Reranker score %.3f", score)


def _order_nodes(nodes, query: str):
    """Rerank when it is on. Otherwise prefer a prose chunk over a list of links."""
    if config.rerank_enabled():
        return rerank_nodes(query, nodes)
    return _prefer_focused(nodes, query)


def _retrieve_named(index: VectorStoreIndex, query: str, names: list[str], top_k: int):
    """Return chunks from the files the question names."""
    from llama_index.core.vector_stores import (
        FilterCondition,
        MetadataFilter,
        MetadataFilters,
    )

    filters = MetadataFilters(
        filters=[MetadataFilter(key="relative_path", value=name) for name in names],
        condition=FilterCondition.OR,
    )
    return index.as_retriever(
        similarity_top_k=top_k,
        filters=filters,
    ).retrieve(query)
