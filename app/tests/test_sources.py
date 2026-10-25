"""FilesystemSource keeps today's path, hidden-file, and read-only rules."""

from pathlib import Path

import pytest

from sources.base import ReadOnlyLibrary
from sources.filesystem import FilesystemSource


def test_item_id_is_the_relative_path(tmp_path: Path):
    folder = tmp_path / "notes"
    folder.mkdir()
    target = folder / "gate.txt"
    target.write_text("north", encoding="utf-8")
    (tmp_path / ".hidden.txt").write_text("no", encoding="utf-8")

    items = FilesystemSource(tmp_path).list_items()

    assert [item.id for item in items] == ["notes/gate.txt"]
    assert items[0].title == "gate.txt"
    assert items[0].size == target.stat().st_size
    assert items[0].location == str(target)


def test_deleted_ids_are_known_ids_that_left(tmp_path: Path):
    (tmp_path / "keep.txt").write_text("a", encoding="utf-8")
    source = FilesystemSource(tmp_path)

    assert source.deleted_ids({"keep.txt", "gone.txt"}) == ["gone.txt"]


def test_read_only_refuses_upload_and_delete(tmp_path: Path):
    source = FilesystemSource(tmp_path, read_only=True)
    with pytest.raises(ReadOnlyLibrary) as upload:
        source.ensure_writable("upload")
    with pytest.raises(ReadOnlyLibrary) as delete:
        source.ensure_writable("delete")
    assert upload.value.action == "upload"
    assert delete.value.action == "delete"


def test_writable_source_accepts_a_change(tmp_path: Path):
    FilesystemSource(tmp_path, read_only=False).ensure_writable("upload")
