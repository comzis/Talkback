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


def _retrieve_nodes(index: VectorStoreIndex, query: str, library_files: list[str]):
    """Search the library. A named file is searched on its own.

    Returns the nodes and whether they were limited to files the question names.
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
    named = named_library_files(query, library_files)
    if named:
        pinned = _retrieve_named(index, query, named, candidates)
        if pinned:
            ordered = _order_nodes(pinned, query)
            _log_rerank(ordered)
            return _keep(ordered, per_file, limit), True
    nodes = index.as_retriever(similarity_top_k=candidates).retrieve(query)
    ordered = _order_nodes(nodes, query)
    _log_rerank(ordered)
    return _keep(ordered, per_file, limit), False


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
