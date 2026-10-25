"""The indexer starts a requested run only when the lock row is free."""

import time
from pathlib import Path

from ingestion.worker import next_kind, write_heartbeat
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
