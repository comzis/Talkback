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
from state import get

logger = logging.getLogger(__name__)


def reindex_required() -> bool:
    """True when stored vectors were embedded with a different model."""
    return get().needs_reindex


def _remember_collection(collection) -> None:
    """Keep the open collection and record whether its vectors match EMBED_MODEL."""
    count = collection.count()
    current = config.embed_model_name()
    get().needs_reindex = embeddings.full_reindex_required(
        collection.metadata, count, current
    )
    if count == 0:
        meta = dict(collection.metadata or {})
        if meta.get(embeddings.EMBED_META_KEY) != current:
            meta[embeddings.EMBED_META_KEY] = current
            collection.modify(metadata=meta)
        get().needs_reindex = False
    get().chroma_collection = collection
    get().vector_store = ChromaVectorStore(chroma_collection=collection)
    get().storage_context = StorageContext.from_defaults(
        vector_store=get().vector_store
    )
    logger.info(
        "Embedding model %s. Full re-index required: %s", current, get().needs_reindex
    )


def connect_chroma() -> None:
    """Retry until Chroma accepts a heartbeat, then open the library collection."""
    host = os.getenv("CHROMA_HOST")
    port = int(os.getenv("CHROMA_PORT", "8000"))
    last_error: Exception | None = None
    for attempt in range(1, 31):
        try:
            client = chromadb.HttpClient(host=host, port=port)
            client.heartbeat()
            collection = client.get_or_create_collection("rag_collection")
            get().db = client
            _remember_collection(collection)
            logger.info("Connected to ChromaDB on attempt %s", attempt)
            return
        except Exception as exc:
            # Chroma/httpx/server errors all mean "not ready"; retry, then raise below.
            last_error = exc
            logger.warning("ChromaDB not ready (attempt %s/30): %s", attempt, exc)
            time.sleep(2)
    raise RuntimeError(
        f"Failed to connect to ChromaDB at {host}:{port}. "
        f"Ensure the ChromaDB service is running. Error: {last_error}"
    )


def collection_count() -> int:
    if get().chroma_collection is None:
        return 0
    return get().chroma_collection.count()


def chunk_metadatas() -> list:
    """Every stored chunk's metadata, or [] when Chroma is empty or offline."""
    if get().chroma_collection is None or collection_count() == 0:
        return []
    stored = get().chroma_collection.get(include=["metadatas"])
    return stored.get("metadatas") or []


def get_or_create_cached_index() -> VectorStoreIndex:
    if get().cached_index is not None:
        return get().cached_index
    logger.info("Creating VectorStoreIndex from existing vector store for query")
    get().cached_index = VectorStoreIndex.from_vector_store(
        get().vector_store,
        storage_context=get().storage_context,
    )
    return get().cached_index


def replace_vector_collection() -> None:
    """Empty the library collection and keep its id when the model is unchanged.

    delete_collection makes Chroma assign a new id. The API keeps the old
    one, so every query 404s until that process restarts. Clearing the rows
    leaves the id in place for both processes. A different embedding model
    cannot reuse those rows: the vector width may differ, so the collection
    is recreated and the API has to be restarted after that rebuild.
    """
    current = config.embed_model_name()
    collection = get().chroma_collection
    if collection is None:
        collection = get().db.get_or_create_collection(
            "rag_collection",
            metadata={embeddings.EMBED_META_KEY: current},
        )
    elif embeddings.full_reindex_required(
        collection.metadata, collection.count(), current
    ):
        get().db.delete_collection(collection.name)
        collection = get().db.get_or_create_collection(
            "rag_collection",
            metadata={embeddings.EMBED_META_KEY: current},
        )
        logger.info(
            "Recreated rag_collection for %s. Restart the API after the rebuild.",
            current,
        )
    else:
        ids = list(collection.get(include=[]).get("ids") or [])
        for offset in range(0, len(ids), 500):
            collection.delete(ids=ids[offset : offset + 500])
        logger.info("Cleared %s vectors from rag_collection", len(ids))
    get().cached_index = None
    _remember_collection(collection)


def indexed_documents() -> tuple[dict[str, tuple], set[str], set[str]]:
    """Return complete signatures, legacy paths, and files still missing a finished marker."""
    if get().chroma_collection is None or collection_count() == 0:
        return {}, set(), set()
    stored = get().chroma_collection.get(include=["metadatas"])
    return classify_stored_chunks(stored.get("metadatas") or [])


def delete_chunks_for_file(relative_path: str) -> int:
    """Remove indexed chunks for one library path and drop the in-memory index."""
    if get().chroma_collection is None:
        return 0
    ids: set[str] = set()
    direct = get().chroma_collection.get(where={"relative_path": relative_path})
    ids.update(direct.get("ids") or [])
    named = get().chroma_collection.get(
        where={"file_name": Path(relative_path).name}, include=["metadatas"]
    )
    for chunk_id, metadata in zip(named.get("ids") or [], named.get("metadatas") or []):
        if chunk_belongs_to(metadata, relative_path):
            ids.add(chunk_id)
    if ids:
        get().chroma_collection.delete(ids=list(ids))
    get().cached_index = None
    return len(ids)


def mark_file_complete(relative_path: str) -> None:
    """Stamp every stored chunk only after that file's batches have all been inserted."""
    if get().chroma_collection is None:
        raise RuntimeError("Chroma is not connected")
    stored = get().chroma_collection.get(
        where={"relative_path": relative_path}, include=["metadatas"]
    )
    ids = list(stored.get("ids") or [])
    metas = [dict(meta or {}) for meta in (stored.get("metadatas") or [])]
    if not ids or len(ids) != len(metas):
        raise RuntimeError(f"Could not mark {relative_path} complete")
    for meta in metas:
        meta["index_complete"] = True
    for offset in range(0, len(ids), 100):
        get().chroma_collection.update(
            ids=ids[offset : offset + 100],
            metadatas=metas[offset : offset + 100],
        )
