"""The indexer starts a requested run only when the lock row is free."""

from pathlib import Path

from ingestion.worker import next_kind
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
