"""The steps behind _ingest_once, tested one at a time with mocks."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ingestion import pipeline
from ingestion.pipeline import IngestPlan
from state import Talkback


@pytest.fixture
def app_state(tmp_path: Path, monkeypatch):
    state = Talkback()
    state.upload_dir = tmp_path
    state.status_dir = tmp_path / "status"
    monkeypatch.setattr(pipeline, "get", lambda: state)
    monkeypatch.setattr(pipeline, "_publish", MagicMock())
    return state


def _node(**metadata):
    return SimpleNamespace(metadata=metadata)


def _plan(**overrides) -> IngestPlan:
    values = {
        "embed_names": [],
        "drop_names": [],
        "on_disk": {},
        "by_key": {},
        "keep_names": [],
    }
    values.update(overrides)
    return IngestPlan(**values)


def test_nodes_group_by_relative_path_then_file_name():
    a1, a2 = _node(relative_path="a.txt"), _node(relative_path="a.txt")
    b = _node(file_name="b.txt")
    orphan = SimpleNamespace(metadata=None)
    grouped = pipeline._group_nodes_by_file([a1, b, a2, orphan])
    assert grouped == {"a.txt": [a1, a2], "b.txt": [b], None: [orphan]}


def test_plan_migrates_an_empty_status_and_adds_deleted_ids(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(pipeline, "chunk_metadatas", lambda: [{"a": 1}])
    (tmp_path / "new.txt").write_text("hello", encoding="utf-8")
    item = SimpleNamespace(id="new.txt", location=str(tmp_path / "new.txt"))
    source = MagicMock()
    source.list_items.return_value = [item]
    source.deleted_ids.return_value = ["gone.txt", "stale.txt"]
    status = MagicMock()
    status.empty.return_value = True
    status.planning_sets.return_value = (
        {"kept.txt": 1, "stale.txt": 1},
        set(),
        set(),
    )
    plan = pipeline._plan_ingest_pass(source, status)
    status.migrate.assert_called_once_with([{"a": 1}])
    assert plan.by_key == {"new.txt": item}
    assert set(plan.on_disk) == {"new.txt"}
    assert "new.txt" in plan.embed_names
    assert "gone.txt" in plan.drop_names
    assert plan.drop_names.count("stale.txt") == 1
    assert "stale.txt" not in plan.keep_names


def test_plan_skips_migration_when_the_status_has_rows():
    source = MagicMock()
    source.list_items.return_value = []
    source.deleted_ids.return_value = []
    status = MagicMock()
    status.empty.return_value = False
    status.planning_sets.return_value = ({}, set(), set())
    plan = pipeline._plan_ingest_pass(source, status)
    status.migrate.assert_not_called()
    assert plan.embed_names == [] and plan.drop_names == []


def test_planned_drops_remove_chunks_and_status_rows(monkeypatch):
    delete = MagicMock()
    monkeypatch.setattr(pipeline, "delete_chunks_for_file", delete)
    status = MagicMock()
    source = SimpleNamespace(source_type="filesystem")
    pipeline._apply_planned_drops(status, source, ["a.txt", "b.txt"])
    assert [c.args for c in delete.call_args_list] == [("a.txt",), ("b.txt",)]
    assert [c.args for c in status.forget.call_args_list] == [
        ("filesystem", "a.txt"),
        ("filesystem", "b.txt"),
    ]


def test_read_documents_tags_key_and_mtime(app_state):
    path = app_state.upload_dir / "docs" / "a.txt"
    path.parent.mkdir()
    path.write_text("hello", encoding="utf-8")
    document = SimpleNamespace(metadata={"file_path": str(path)})
    source = MagicMock()
    source.read.return_value = [document]
    by_key = {"docs/a.txt": SimpleNamespace(location=str(path))}
    documents = pipeline._read_documents_for_embed(source, ["docs/a.txt"], by_key)
    source.read.assert_called_once_with([str(path)])
    assert documents == [document]
    assert document.metadata["relative_path"] == "docs/a.txt"
    assert document.metadata["source_mtime"] == int(path.stat().st_mtime)


def test_read_documents_falls_back_to_the_library_key(app_state):
    path = app_state.upload_dir / "other.txt"
    path.write_text("hello", encoding="utf-8")
    document = SimpleNamespace(metadata={"file_path": str(path)})
    source = MagicMock()
    source.read.return_value = [document]
    by_key = {"a.txt": SimpleNamespace(location=str(app_state.upload_dir / "a.txt"))}
    pipeline._read_documents_for_embed(source, ["a.txt"], by_key)
    assert document.metadata["relative_path"] == "other.txt"


def test_read_documents_uses_the_name_outside_the_library(app_state, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "x.txt"
    outside.write_text("hello", encoding="utf-8")
    document = SimpleNamespace(metadata={"file_path": str(outside)})
    source = MagicMock()
    source.read.return_value = [document]
    by_key = {"a.txt": SimpleNamespace(location=str(app_state.upload_dir / "a.txt"))}
    pipeline._read_documents_for_embed(source, ["a.txt"], by_key)
    assert document.metadata["relative_path"] == "x.txt"


def test_read_documents_leaves_a_missing_file_untagged(app_state):
    document = SimpleNamespace(metadata={"file_path": str(app_state.upload_dir / "no")})
    source = MagicMock()
    source.read.return_value = [document]
    by_key = {"a.txt": SimpleNamespace(location=str(app_state.upload_dir / "a.txt"))}
    pipeline._read_documents_for_embed(source, ["a.txt"], by_key)
    assert "relative_path" not in document.metadata
    assert "source_mtime" not in document.metadata


def test_embed_inserts_in_batches_and_marks_files(app_state, monkeypatch):
    monkeypatch.setattr(pipeline, "mark_file_complete", MagicMock())
    monkeypatch.setattr(pipeline.config, "embed_batch", lambda: 2)
    monkeypatch.setattr(pipeline, "_touch_resources", MagicMock())
    index, status = MagicMock(), MagicMock()
    source = SimpleNamespace(source_type="filesystem")
    nodes = [_node(relative_path="a.txt") for _ in range(3)]
    plan = _plan(
        embed_names=["a.txt", "empty.txt"],
        on_disk={"a.txt": (1, "day", 2), "empty.txt": (0, "day", 3)},
    )
    pipeline._embed_planned_files(index, status, source, plan, {"a.txt": nodes}, 3, 0.0)
    assert [len(c.args[0]) for c in index.insert_nodes.call_args_list] == [2, 1]
    status.mark_pending.assert_called_once_with("filesystem", "a.txt")
    status.mark_complete.assert_called_once_with(
        "filesystem", "a.txt", (1, "day", 2), 3
    )
    status.mark_failed.assert_called_once_with(
        "filesystem", "empty.txt", "No readable text"
    )
    pipeline.mark_file_complete.assert_called_once_with("a.txt")
    assert app_state.ingestion_status["processed_files"] == 1
    assert app_state.ingestion_status["current_file"] == "a.txt"
    assert app_state.ingestion_status["message"] == "Embedded 3 of 3 new chunks"


def test_complete_pass_reports_the_finished_library(app_state, monkeypatch):
    monkeypatch.setattr(pipeline, "collection_count", lambda: 42)
    note = MagicMock()
    monkeypatch.setattr(pipeline, "_note_indexed", note)
    app_state.ingestion_status["cpu_percent"] = 12.5
    index = object()
    plan = _plan(
        embed_names=["a.txt"], on_disk={"a.txt": (1, "d", 2), "b.txt": (1, "d", 2)}
    )
    pipeline._complete_ingest_pass(index, plan, 100.0, pipeline.time.time() - 2, 10)
    status = app_state.ingestion_status
    assert app_state.cached_index is index
    assert status["status"] == "completed"
    assert status["current"] == status["total"] == 42
    assert status["total_files"] == 2
    assert status["processed_files"] == 1
    assert status["start_time"] == 100.0
    assert status["cpu_percent"] == 12.5
    assert status["chunks_per_second"] > 0
    assert status["message"].startswith("Added 10 chunks from 1 file(s)")
    note.assert_called_once()
    pipeline._publish.assert_called_once()


def test_fail_pass_sets_the_error_status(app_state):
    app_state.ingestion_status["current_file"] = "a.txt"
    app_state.ingestion_status["progress"] = 50
    status = MagicMock()
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        pipeline._fail_ingest_pass(status)
    status.fail_pending.assert_called_once_with("Ingestion failed")
    result = app_state.ingestion_status
    assert result["status"] == "error"
    assert result["error"] == "Ingestion failed"
    assert result["progress"] == 0
    assert result["current_file"] is None
    pipeline._publish.assert_called_once()


def test_fail_pass_works_before_the_status_file_opens(app_state):
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        pipeline._fail_ingest_pass(None)
    assert app_state.ingestion_status["status"] == "error"
