"""Search the library and balance matches across files."""

from __future__ import annotations

import logging
import re

from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import BaseRetriever

import config
import store.embeddings as embeddings
from ingestion.plan import balance_matches
from llm.prompts import (
    asks_for_example,
    asks_for_steps,
    named_library_files,
    prompt_passage,
    source_label,
)

logger = logging.getLogger(__name__)


class BalancedRetriever(BaseRetriever):
    """Retrieve across the library instead of letting one large file fill every slot."""

    def __init__(
        self,
        index: VectorStoreIndex,
        candidate_k: int = 12,
        per_file: int = 2,
        limit: int = 4,
    ):
        self._inner = index.as_retriever(similarity_top_k=candidate_k)
        self._per_file = per_file
        self._limit = limit
        super().__init__()

    def _retrieve(self, query_bundle):
        return balance_matches(
            self._inner.retrieve(query_bundle),
            per_file=self._per_file,
            limit=self._limit,
        )


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
    named = named_library_files(query, library_files)
    if named:
        pinned = _retrieve_named(index, query, named, candidates)
        if pinned:
            return balance_matches(
                _prefer_focused(pinned, query), per_file=per_file, limit=limit
            ), True
    nodes = index.as_retriever(similarity_top_k=candidates).retrieve(query)
    return balance_matches(
        _prefer_focused(nodes, query), per_file=per_file, limit=limit
    ), False


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


def _library_matches(nodes) -> bool:
    scores = [getattr(node, "score", None) for node in nodes]
    return embeddings.relevant_enough(scores, config.relevance_threshold())
