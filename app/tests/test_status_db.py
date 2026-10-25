"""File status follows the chunk rules and does not re-embed a finished file."""

import time
from pathlib import Path

from ingestion.plan import index_plan
from store.status_db import StatusStore


def _store(tmp_path: Path) -> StatusStore:
    store = StatusStore(tmp_path / "status" / "library.sqlite")
    store.open()
    return store


def _finished(name: str, signature: tuple) -> dict:
    size, day, mtime = signature
    return {
        "relative_path": name,
        "file_size": size,
        "last_modified_date": day,
        "source_mtime": mtime,
        "index_complete": True,
    }


def test_a_missing_marker_stays_unfinished_and_a_marked_file_does_not(tmp_path: Path):
    signature = (12000, "2024-06-01", 1717200000)
    store = _store(tmp_path)
    store.migrate(
        [
            _finished("done.pdf", signature),
            {
                "relative_path": "partial.pdf",
                "file_size": 40,
                "last_modified_date": "2024-06-01",
                "source_mtime": 1717200000,
            },
        ]
    )
    store.migrate([_finished("ignored.pdf", signature)])

    indexed, legacy, unfinished = store.planning_sets()
    on_disk = {
        "done.pdf": signature,
        "partial.pdf": (40, "2024-06-01", 1717200000),
    }
    embed, drop = index_plan(on_disk, indexed, legacy, unfinished)

    assert "done.pdf" not in embed
    assert "partial.pdf" in embed and "partial.pdf" in drop
    assert store.get("filesystem", "ignored.pdf") is None
    assert store.get("filesystem", "done.pdf")["chunk_count"] == 1


def test_crash_mid_file_is_retried(tmp_path: Path):
    store = _store(tmp_path)
    store.mark_pending("filesystem", "live.pdf")
    indexed, _legacy, unfinished = store.planning_sets()
    embed, drop = index_plan(
        {"live.pdf": (8, "2024-06-01", 10)}, indexed, _legacy, unfinished
    )
    assert store.get("filesystem", "live.pdf")["status"] == "pending"
    assert "live.pdf" in embed and "live.pdf" in drop


def test_deleted_file_is_dropped_and_forgotten(tmp_path: Path):
    store = _store(tmp_path)
    signature = (8, "2024-06-01", 10)
    store.mark_complete("filesystem", "gone.pdf", signature, chunk_count=2)
    indexed, legacy, unfinished = store.planning_sets()
    _embed, drop = index_plan({}, indexed, legacy, unfinished)
    assert "gone.pdf" in drop
    store.forget("filesystem", "gone.pdf")
    assert store.get("filesystem", "gone.pdf") is None


def test_moved_file_drops_the_old_id_and_embeds_the_new_one(tmp_path: Path):
    store = _store(tmp_path)
    signature = (8, "2024-06-01", 10)
    store.mark_complete("filesystem", "old.pdf", signature, chunk_count=2)
    indexed, legacy, unfinished = store.planning_sets()
    embed, drop = index_plan({"notes/old.pdf": signature}, indexed, legacy, unfinished)
    assert "old.pdf" in drop
    assert "notes/old.pdf" in embed


def test_failed_extraction_is_shown_and_retried(tmp_path: Path):
    store = _store(tmp_path)
    store.mark_failed("filesystem", "bad.pdf", "No readable text")
    row = store.get("filesystem", "bad.pdf")
    assert row["status"] == "failed"
    assert row["last_error"] == "No readable text"
    assert store.failed_rows()[0]["item_id"] == "bad.pdf"
    indexed, legacy, unfinished = store.planning_sets()
    embed, drop = index_plan(
        {"bad.pdf": (3, "2024-06-01", 9)}, indexed, legacy, unfinished
    )
    assert "bad.pdf" in embed and "bad.pdf" in drop


def test_clear_lets_the_next_pass_embed_again(tmp_path: Path):
    store = _store(tmp_path)
    store.mark_complete("filesystem", "done.pdf", (4, "2024-06-02", 11), 1)
    store.clear()
    assert store.empty()


def test_rebuild_replaces_the_table(tmp_path: Path):
    store = _store(tmp_path)
    store.mark_failed("filesystem", "old.pdf", "gone")
    store.rebuild([_finished("new.pdf", (4, "2024-06-02", 11))])
    assert store.get("filesystem", "old.pdf") is None
    assert store.get("filesystem", "new.pdf")["status"] == "complete"


def test_the_store_closes_when_the_loop_releases_it(tmp_path: Path):
    store = _store(tmp_path)
    store.request_run("incremental")
    store.close()
    assert store._db is None
    with store:
        assert store.peek_request() == "incremental"
    assert store._db is None


def test_one_lock_row_lets_a_single_run_proceed(tmp_path: Path):
    first = _store(tmp_path)
    second = StatusStore(first.path)
    second.open()
    assert first.try_lock("api")
    assert not second.try_lock("worker")
    assert second.lock_held()
    assert first.refresh_lock("api")
    assert not second.refresh_lock("worker")
    first.unlock("api")
    assert not first.lock_held()
    assert second.try_lock("worker")
    second.unlock("worker")


def test_a_quiet_lock_can_be_taken_over(tmp_path: Path):
    store = _store(tmp_path)
    store.try_lock("crashed")
    store._conn().execute(
        "UPDATE run_lock SET heartbeat = ? WHERE id = 1", (time.time() - 60,)
    )
    assert store.try_lock("worker", stale_after=30)
    assert store.refresh_lock("worker")


def test_a_rebuild_request_replaces_an_incremental_one(tmp_path: Path):
    store = _store(tmp_path)
    store.request_run("incremental")
    store.request_run("rebuild")
    store.request_run("incremental")
    assert store.peek_request() == "rebuild"
    assert store.take_request() == "rebuild"
    assert store.peek_request() is None
    store.write_job({"status": "processing", "message": "Checking the library..."})
    assert store.read_job()["message"] == "Checking the library..."
