"""Ingestion endpoints. The indexer process does the embedding."""

from fastapi import APIRouter

import engine
from api.deps import _reject_if_reindex_required
from state import get
from store.status_db import StatusStore

router = APIRouter()


@router.post("/ingest")
async def ingest_documents():
    """Ask the indexer to add new or changed files. This process does not embed them."""
    _reject_if_reindex_required()
    if not engine.enqueue_ingestion("incremental"):
        return {"message": "Ingestion already in progress", "status": "processing"}

    return {
        "message": "Adding new documents. Files already indexed are kept.",
        "status": "processing",
    }


@router.post("/ingest/rebuild")
async def rebuild_index():
    """Ask the indexer to drop the collection and embed every file again."""
    if not engine.enqueue_ingestion("rebuild"):
        return {"message": "Ingestion already in progress", "status": "processing"}
    return {
        "message": "Full re-index started. The old vectors are being replaced.",
        "status": "processing",
    }


@router.get("/ingest/status")
async def get_ingestion_status():
    """Progress written by the indexer. This process only reads it."""
    shared = StatusStore(get().status_dir / "library.sqlite").read_job()
    if shared:
        return shared
    return get().ingestion_status
