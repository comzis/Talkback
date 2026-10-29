"""Health, system status, resources, and the chat page."""

import logging

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

import config
import engine
import retrieval.rerank as rerank
import store.host_embed as host_embed
from api.deps import STATIC_DIR
from api.routers.llm import get_llm_status
from state import get

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
def health_check():
    """Simple health check to confirm the API is running."""
    return {"status": "ok"}


@router.get("/system/resources")
async def get_system_resources():
    """
    Get real-time CPU and memory usage from the system.
    """
    import psutil
    import time

    return {
        "cpu_percent": round(psutil.cpu_percent(interval=0.1), 1),
        "memory_percent": round(psutil.virtual_memory().percent, 1),
        "timestamp": time.time(),
    }


@router.get("/system/memory")
def get_system_memory():
    """Process RSS and the fixed caches that used to grow per query."""
    import os
    from pathlib import Path

    from llama_index.core import Settings

    talkback = get()
    rss_bytes = 0
    status_path = Path("/proc/self/status")
    if status_path.is_file():
        for line in status_path.read_text().splitlines():
            if line.startswith("VmRSS:"):
                rss_bytes = int(line.split()[1]) * 1024
                break
    bm25 = talkback.bm25
    library = talkback.library_index
    index = talkback.cached_index
    docstore_len = None
    if index is not None:
        docstore = getattr(index, "docstore", None)
        docs = getattr(docstore, "docs", None) if docstore is not None else None
        if docs is not None:
            docstore_len = len(docs)
    local_loaded = False
    try:
        embed = Settings.embed_model
        local_loaded = getattr(embed, "_local", None) is not None
    except Exception:
        # Warm-up may not have finished; the snapshot still reports RSS.
        local_loaded = False
    return {
        "pid": os.getpid(),
        "rss_bytes": rss_bytes,
        "rss_miB": round(rss_bytes / (1024 * 1024), 1),
        "bm25_docs": len(bm25.documents),
        "bm25_count": bm25.count,
        "library_index_count": library.count,
        "library_files": len(library.complete or {}),
        "docstore_len": docstore_len,
        "rerank_loaded": talkback.rerank_model is not None,
        "embed_local_loaded": local_loaded,
    }


@router.get("/system/status")
async def get_system_status():
    """
    Comprehensive system status including API, LLM, Database, and alarms.
    """
    import time

    status = {
        "timestamp": time.time(),
        "api": {"status": "online", "uptime": "running"},
        "llm": {
            "status": "unknown",
            "available": False,
            "model_configured": None,
            "response_time_ms": None,
            "error": None,
        },
        "offline_mode": engine.offline_mode(),
        "library_read_only": engine.library_read_only(),
        "reindex_required": engine.reindex_required(),
        "files_waiting": engine.files_waiting(),
        "embed_model": config.embed_model_name(),
        "embed": host_embed.active_embed(),
        "rerank": rerank.active_rerank(),
        "retrieval": {
            "hybrid_bm25": config.hybrid_bm25(),
            "rerank_candidates": config.rerank_candidates(),
            "retrieve_limit": config.retrieve_limit(),
            "retrieve_balance_files": config.retrieve_balance_files(),
            "retrieve_per_file": config.retrieve_per_file(),
        },
        "database": {
            "status": "unknown",
            "connected": False,
            "collection_count": 0,
            "error": None,
        },
        "alarms": [],
    }

    # Check LLM status
    try:
        llm_status = await get_llm_status()
        status["llm"] = llm_status
        if not llm_status.get("available", False):
            status["alarms"].append(
                {
                    "type": "warning",
                    "component": "llm",
                    "message": f"LLM is {llm_status.get('status', 'unknown')}: {llm_status.get('error', 'Unknown error')}",
                }
            )
    except Exception:
        # Status page must still render; record the failure as an alarm instead.
        status["llm"]["status"] = "error"
        logger.exception("Failed to check LLM status")
        status["llm"]["error"] = "The language model could not be reached."
        status["alarms"].append(
            {
                "type": "error",
                "component": "llm",
                "message": "The language model could not be reached.",
            }
        )

    # Check Database status
    try:
        collection_count = engine.collection_count()
        status["database"]["status"] = "online"
        status["database"]["connected"] = True
        status["database"]["collection_count"] = collection_count
    except Exception:
        # Status page must still render; record the failure as an alarm instead.
        status["database"]["status"] = "offline"
        status["database"]["connected"] = False
        logger.exception("Database connection error")
        status["database"]["error"] = "Database connection error"
        status["alarms"].append(
            {
                "type": "error",
                "component": "database",
                "message": "Database connection error",
            }
        )

    if status["rerank"].get("host") == "unreachable":
        status["alarms"].append(
            {
                "type": "warning",
                "component": "rerank",
                "message": "Host reranker is unreachable. Library search is unavailable.",
            }
        )
    if status["embed"].get("host") == "unreachable":
        status["alarms"].append(
            {
                "type": "warning",
                "component": "embed",
                "message": "Host embedder is unreachable. Library search is unavailable.",
            }
        )

    # Check ingestion status for warnings
    if get().ingestion_status.get("status") == "error":
        status["alarms"].append(
            {"type": "warning", "component": "ingestion", "message": "Ingestion failed"}
        )

    return status


@router.get("/", response_class=HTMLResponse)
async def root():
    """Serve the chatbot interface."""
    try:
        with open(STATIC_DIR / "index.html", "r") as f:
            return HTMLResponse(content=f.read(), headers={"Cache-Control": "no-cache"})
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Chatbot interface not found</h1>", status_code=404
        )
