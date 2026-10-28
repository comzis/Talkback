"""In-memory BM25 over the Chroma collection for hybrid retrieval."""

from __future__ import annotations

import logging
import re
import threading

from llama_index.core.schema import NodeWithScore, TextNode

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)
_lock = threading.Lock()


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN.findall(text or "")]


def invalidate() -> None:
    """Drop the cached index (after a re-index)."""
    from state import Bm25Cache, get

    with _lock:
        get().bm25 = Bm25Cache()


def _ensure(collection) -> None:
    from state import get

    cache = get().bm25
    current = collection.count()
    if cache.index is not None and current == cache.count:
        return
    from rank_bm25 import BM25Okapi

    logger.info("Building BM25 index over %s chunks", current)
    stored = collection.get(include=["documents", "metadatas"])
    cache.ids = list(stored.get("ids") or [])
    cache.documents = [doc or "" for doc in (stored.get("documents") or [])]
    cache.metadatas = [meta or {} for meta in (stored.get("metadatas") or [])]
    tokenized = [_tokenize(doc) for doc in cache.documents]
    cache.index = BM25Okapi(tokenized)
    cache.count = current
    logger.info("BM25 index ready (%s docs)", cache.count)


def retrieve_nodes(
    query: str, top_k: int, allowed_paths: list[str] | None = None
) -> list:
    """Return top BM25 hits as LlamaIndex text nodes.

    When ``allowed_paths`` is set, only chunks from those relative_path values
    are ranked (hard search scope).
    """
    if top_k <= 0 or not (query or "").strip():
        return []
    from state import get

    collection = get().chroma_collection
    if collection is None or collection.count() == 0:
        return []
    allowed = set(allowed_paths) if allowed_paths is not None else None
    with _lock:
        _ensure(collection)
        cache = get().bm25
        assert cache.index is not None
        scores = cache.index.get_scores(_tokenize(query))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        nodes = []
        for index in order:
            if allowed is not None:
                meta_path = (cache.metadatas[index] or {}).get("relative_path") or (
                    cache.metadatas[index] or {}
                ).get("file_name")
                if meta_path not in allowed:
                    continue
            score = float(scores[index])
            if score <= 0:
                continue
            meta = dict(cache.metadatas[index])
            for key in list(meta):
                if str(key).startswith("_"):
                    meta.pop(key, None)
            node = TextNode(
                text=cache.documents[index],
                metadata=meta,
                id_=cache.ids[index],
            )
            nodes.append(NodeWithScore(node=node, score=score))
            if len(nodes) >= top_k:
                break
        return nodes
