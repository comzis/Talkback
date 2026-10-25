"""Chroma collection, cached index, and chunk deletes."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import chromadb
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.vector_stores.chroma import ChromaVectorStore

import config
import store.embeddings as embeddings
from ingestion.plan import chunk_belongs_to, classify_stored_chunks

logger = logging.getLogger(__name__)

db = None
chroma_collection = None
vector_store = None
storage_context = None
cached_index: VectorStoreIndex | None = None
_reindex_required = False


def reindex_required() -> bool:
    """True when stored vectors were embedded with a different model."""
    return _reindex_required


def _remember_collection(collection) -> None:
    """Keep the open collection and record whether its vectors match EMBED_MODEL."""
    global db, chroma_collection, vector_store, storage_context, _reindex_required

    count = collection.count()
    current = config.embed_model_name()
    _reindex_required = embeddings.full_reindex_required(
        collection.metadata, count, current
    )
    if count == 0:
        meta = dict(collection.metadata or {})
        if meta.get(embeddings.EMBED_META_KEY) != current:
            meta[embeddings.EMBED_META_KEY] = current
            collection.modify(metadata=meta)
        _reindex_required = False
    chroma_collection = collection
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    logger.info(
        "Embedding model %s. Full re-index required: %s", current, _reindex_required
    )


def connect_chroma() -> None:
    """Retry until Chroma accepts a heartbeat, then open the library collection."""
    global db

    host = os.getenv("CHROMA_HOST")
    port = int(os.getenv("CHROMA_PORT", "8000"))
    last_error: Exception | None = None
    for attempt in range(1, 31):
        try:
            client = chromadb.HttpClient(host=host, port=port)
            client.heartbeat()
            collection = client.get_or_create_collection("rag_collection")
            db = client
            _remember_collection(collection)
            logger.info("Connected to ChromaDB on attempt %s", attempt)
            return
        except Exception as exc:
            last_error = exc
            logger.warning("ChromaDB not ready (attempt %s/30): %s", attempt, exc)
            time.sleep(2)
    raise RuntimeError(
        f"Failed to connect to ChromaDB at {host}:{port}. "
        f"Ensure the ChromaDB service is running. Error: {last_error}"
    )


def collection_count() -> int:
    if chroma_collection is None:
        return 0
    return chroma_collection.count()


def get_or_create_cached_index() -> VectorStoreIndex:
    global cached_index
    if cached_index is not None:
        return cached_index
    logger.info("Creating VectorStoreIndex from existing vector store for query")
    cached_index = VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage_context,
    )
    return cached_index


def replace_vector_collection() -> None:
    """Drop stored vectors so the next ingest replaces the library."""
    global cached_index

    try:
        db.delete_collection("rag_collection")
        logger.info("Removed existing rag_collection before re-ingest")
    except Exception as exc:
        logger.info("No existing rag_collection to remove: %s", exc)

    collection = db.get_or_create_collection(
        "rag_collection",
        metadata={embeddings.EMBED_META_KEY: config.embed_model_name()},
    )
    cached_index = None
    _remember_collection(collection)


def indexed_documents() -> tuple[dict[str, tuple], set[str], set[str]]:
    """Return complete signatures, legacy paths, and files still missing a finished marker."""
    if chroma_collection is None or collection_count() == 0:
        return {}, set(), set()
    stored = chroma_collection.get(include=["metadatas"])
    return classify_stored_chunks(stored.get("metadatas") or [])


def delete_chunks_for_file(relative_path: str) -> int:
    """Remove indexed chunks for one library path and drop the in-memory index."""
    global cached_index
    if chroma_collection is None:
        return 0
    ids: set[str] = set()
    direct = chroma_collection.get(where={"relative_path": relative_path})
    ids.update(direct.get("ids") or [])
    named = chroma_collection.get(
        where={"file_name": Path(relative_path).name}, include=["metadatas"]
    )
    for chunk_id, metadata in zip(named.get("ids") or [], named.get("metadatas") or []):
        if chunk_belongs_to(metadata, relative_path):
            ids.add(chunk_id)
    if ids:
        chroma_collection.delete(ids=list(ids))
    cached_index = None
    return len(ids)


def mark_file_complete(relative_path: str) -> None:
    """Stamp every stored chunk only after that file's batches have all been inserted."""
    if chroma_collection is None:
        raise RuntimeError("Chroma is not connected")
    stored = chroma_collection.get(
        where={"relative_path": relative_path}, include=["metadatas"]
    )
    ids = list(stored.get("ids") or [])
    metas = [dict(meta or {}) for meta in (stored.get("metadatas") or [])]
    if not ids or len(ids) != len(metas):
        raise RuntimeError(f"Could not mark {relative_path} complete")
    for meta in metas:
        meta["index_complete"] = True
    for offset in range(0, len(ids), 100):
        chroma_collection.update(
            ids=ids[offset : offset + 100],
            metadatas=metas[offset : offset + 100],
        )
