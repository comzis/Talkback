"""The indexer starts a requested run only when the lock row is free."""

import time
from pathlib import Path

from ingestion.worker import (
    handle_sqlite_error,
    next_kind,
    record_run_failed,
    write_heartbeat,
)
from store.status_db import StatusStore


def test_a_held_lock_keeps_the_request_waiting(tmp_path: Path):
    store = StatusStore(tmp_path / "status" / "library.sqlite")
    store.open()
    store.request_run("rebuild")
    assert next_kind(store) == "rebuild"
    assert store.try_lock("indexer")
    assert next_kind(store) is None
    store.unlock("indexer")
    assert next_kind(store) == "rebuild"


def test_heartbeat_file_is_fresh(tmp_path: Path):
    path = tmp_path / "heartbeat"
    write_heartbeat(path)
    age = time.time() - float(path.read_text(encoding="utf-8"))
    assert age < 5


def test_repeated_sqlite_errors_mark_the_run_failed(tmp_path: Path):
    path = tmp_path / "status" / "library.sqlite"
    waits: list[float] = []

    def factory():
        return StatusStore(path)

    count = 0
    for _ in range(4):
        count = handle_sqlite_error(
            count, factory, backoff=0, limit=5, sleep=waits.append
        )
        assert count > 0
        assert factory().read_job() is None
    count = handle_sqlite_error(count, factory, backoff=0, limit=5, sleep=waits.append)
    assert count == 0
    job = factory().read_job()
    assert job["status"] == "error"
    assert "disk I/O" in job["error"]
    assert len(waits) == 5


def test_record_run_failed_writes_an_error_job(tmp_path: Path):
    path = tmp_path / "status" / "library.sqlite"

    def factory():
        return StatusStore(path)

    record_run_failed(factory, "temporary disk I/O error")
    job = factory().read_job()
    assert job["status"] == "error"
    assert job["error"] == "temporary disk I/O error"
