"""Index the library in its own process.

The API asks for a run by writing a row. This process holds the lock row
while it embeds, so a second process does not start another run.
"""

from __future__ import annotations

import logging
import os
import signal
import sqlite3
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)
HEARTBEAT_PATH = Path("/tmp/talkback-indexer-heartbeat")
SQLITE_BACKOFF_SECONDS = 3
SQLITE_FAIL_LIMIT = 5


def write_heartbeat(path: Path = HEARTBEAT_PATH) -> None:
    """Touch the liveness file the container healthcheck reads."""
    path.write_text(str(time.time()), encoding="utf-8")


def _heartbeat_loop(path: Path = HEARTBEAT_PATH, interval: float = 10) -> None:
    while True:
        write_heartbeat(path)
        time.sleep(interval)


def next_kind(store) -> str | None:
    """The waiting request, unless a run already holds the lock."""
    if store.lock_held():
        return None
    return store.peek_request()


def record_run_failed(store_factory, message: str) -> None:
    """Write an error job row. A second I/O failure is only logged."""
    try:
        with store_factory() as store:
            store.write_job(
                {
                    "status": "error",
                    "progress": 0,
                    "current": 0,
                    "total": 0,
                    "message": message,
                    "error": message,
                    "current_file": None,
                    "total_files": 0,
                    "processed_files": 0,
                    "start_time": None,
                    "finished_at": time.time(),
                    "chunks_per_second": 0.0,
                    "cpu_percent": 0.0,
                    "memory_percent": 0.0,
                    "estimated_time_remaining": 0,
                }
            )
    except sqlite3.OperationalError:
        logger.warning("Could not record the failed status after a disk I/O error")


def handle_sqlite_error(
    failures: int,
    store_factory,
    *,
    message: str = "Status database disk I/O failed repeatedly.",
    backoff: float = SQLITE_BACKOFF_SECONDS,
    limit: int = SQLITE_FAIL_LIMIT,
    sleep=time.sleep,
) -> int:
    """Log, back off, and after `limit` failures mark the run failed. Returns the new count."""
    failures += 1
    logger.warning(
        "Status database error (%s/%s); backing off %.0fs",
        failures,
        limit,
        backoff,
    )
    if failures >= limit:
        record_run_failed(store_factory, message)
        failures = 0
    sleep(backoff)
    return failures


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    write_heartbeat()
    threading.Thread(
        target=_heartbeat_loop, name="talkback-indexer-heartbeat", daemon=True
    ).start()
    import engine
    from ingestion.pipeline import (
        begin_ingestion,
        finish_ingestion,
        open_status,
        process_ingestion,
        rebuild_library,
        start_initial_index,
        start_reindex_schedule,
    )

    engine.init()
    start_reindex_schedule()
    start_initial_index()

    def stop(_signum, _frame) -> None:
        try:
            finish_ingestion()
        except sqlite3.OperationalError:
            logger.warning("Could not release the ingest lock during shutdown")
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    sqlite_failures = 0
    while True:
        time.sleep(2)
        started = False
        try:
            with open_status() as store:
                kind = next_kind(store)
                if kind is not None and begin_ingestion():
                    started = True
                    kind = store.take_request()
                else:
                    kind = None
            sqlite_failures = 0
            if not started:
                continue
            try:
                if kind == "rebuild":
                    logger.info("Full re-index requested.")
                    rebuild_library()
                elif kind:
                    logger.info("Incremental index requested.")
                    process_ingestion()
            except sqlite3.OperationalError:
                sqlite_failures = handle_sqlite_error(sqlite_failures, open_status)
            finally:
                if started:
                    try:
                        finish_ingestion()
                    except sqlite3.OperationalError:
                        logger.warning("Could not release the ingest lock after a run")
                        sqlite_failures = handle_sqlite_error(
                            sqlite_failures, open_status
                        )
        except sqlite3.OperationalError:
            sqlite_failures = handle_sqlite_error(sqlite_failures, open_status)


if __name__ == "__main__":
    main()
