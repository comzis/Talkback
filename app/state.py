"""The one object created when the process starts.

Routes and background jobs share it. Nothing here opens Chroma or a model.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

_current: Talkback | None = None


class Bm25Cache:
    """The in-memory BM25 index and the chunks it was built from."""

    def __init__(self) -> None:
        self.index = None
        self.ids: list[str] = []
        self.documents: list[str] = []
        self.metadatas: list[dict] = []
        self.count = -1


class LibraryIndexCache:
    """Classified library paths from Chroma metadata.

    A full metadata pull is tens of MiB. Rebuilding it on every query made RSS
    climb for the life of the worker; refresh when the collection changes.
    """

    def __init__(self) -> None:
        self.count = -1
        self.complete: dict[str, tuple] | None = None
        self.legacy: set[str] | None = None
        self.incomplete: set[str] | None = None


class Talkback:
    """Process state that used to live in module globals."""

    def __init__(self) -> None:
        self.db = None
        self.chroma_collection = None
        self.vector_store = None
        self.storage_context = None
        self.cached_index = None
        self.needs_reindex = False
        self.upload_dir = Path(os.getenv("RAG_DATA_DIR", "/app/data"))
        self.status_dir = Path(os.getenv("STATUS_DIR", "/app/status"))
        self.last_indexed_at: float | None = None
        self.ingest_lock = threading.Lock()
        self.ingest_again = False
        self.models_ready = threading.Event()
        self.chat = None
        self.heartbeat_stop: threading.Event | None = None
        self.bm25 = Bm25Cache()
        self.library_index = LibraryIndexCache()
        self.rerank_model = None
        self.rerank_tokenizer = None
        self.rerank_host_warning_logged = False
        self.embed_host_warning_logged = False
        self.ingestion_status = {
            "status": "idle",
            "progress": 0,
            "current": 0,
            "total": 0,
            "message": "",
            "error": None,
            "current_file": None,
            "total_files": 0,
            "processed_files": 0,
            "start_time": None,
            "finished_at": None,
            "chunks_per_second": 0.0,
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "estimated_time_remaining": 0,
        }


def activate() -> Talkback:
    """Create the process object on the first call and return it after that."""
    global _current
    if _current is None:
        _current = Talkback()
    return _current


def get() -> Talkback:
    if _current is None:
        raise RuntimeError("Talkback has not been started.")
    return _current


def reset_for_tests() -> None:
    """Drop the process object. Unit tests only."""
    global _current
    _current = None
