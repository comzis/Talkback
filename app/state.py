"""The one object created when the process starts.

Routes and background jobs share it. Nothing here opens Chroma or a model.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

_current: Talkback | None = None


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
