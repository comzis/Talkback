"""FilesystemSource keeps today's path, hidden-file, and read-only rules."""

from pathlib import Path

import pytest

from sources.base import ReadOnlyLibrary
from sources.filesystem import FilesystemSource
import store.embeddings as embeddings


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


def test_listing_skips_macos_metadata(tmp_path: Path):
    (tmp_path / "guide.pdf").write_bytes(b"%PDF")
    (tmp_path / "._guide.pdf").write_bytes(b"sidecar")
    (tmp_path / ".DS_Store").write_bytes(b"store")

    assert [item.id for item in FilesystemSource(tmp_path).list_items()] == [
        "guide.pdf"
    ]


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


def test_source_fields_keep_the_same_chunk_boundaries():
    pytest.importorskip("llama_index")
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.core.schema import Document

    import config
    from ingestion.pipeline import nodes_for_index

    text = "The live tolerance is plus or minus 1.0 LU. " * 80
    splitter = SentenceSplitter(
        chunk_size=config.chunk_size(), chunk_overlap=config.chunk_overlap()
    )
    metadata = {
        "file_name": "TechnicalDeliveryStandardsBBCLive.pdf",
        "file_path": "/app/data/TechnicalDeliveryStandardsBBCLive.pdf",
        "file_size": 12000,
        "file_type": "application/pdf",
        "page_label": "16",
        "creation_date": "2024-01-01",
        "last_modified_date": "2024-01-02",
        "relative_path": "TechnicalDeliveryStandardsBBCLive.pdf",
        "source_mtime": 1700000000,
    }
    baseline = splitter.get_nodes_from_documents(
        [Document(text=text, metadata=dict(metadata))]
    )
    early = dict(metadata)
    early["source_type"] = "filesystem"
    early["source_id"] = metadata["relative_path"]
    shifted = splitter.get_nodes_from_documents([Document(text=text, metadata=early)])
    stamped = nodes_for_index(
        [Document(text=text, metadata=dict(metadata))],
        FilesystemSource(Path(".")),
    )

    assert [node.text for node in shifted] != [node.text for node in baseline]
    assert [node.text for node in stamped] == [node.text for node in baseline]
    assert stamped[0].metadata["source_type"] == "filesystem"
    assert stamped[0].metadata["source_id"] == metadata["relative_path"]
    assert stamped[0].metadata["relative_path"] == metadata["relative_path"]


def test_source_ids_stay_out_of_the_embedded_text_and_the_prompt():
    pytest.importorskip("llama_index")
    from llama_index.core.schema import Document, MetadataMode

    from ingestion.pipeline import nodes_for_index

    text = "Target loudness is -23.0 LUFS."
    document = Document(
        text=text,
        metadata={
            "file_name": "TechnicalDeliveryStandardsBBCLive.pdf",
            "file_path": "/app/data/TechnicalDeliveryStandardsBBCLive.pdf",
            "file_size": 12000,
            "file_type": "application/pdf",
            "page_label": "16",
            "creation_date": "2024-01-01",
            "last_modified_date": "2024-01-02",
            "relative_path": "TechnicalDeliveryStandardsBBCLive.pdf",
            "source_mtime": 1700000000,
        },
        excluded_embed_metadata_keys=[
            "file_name",
            "file_type",
            "file_size",
            "creation_date",
            "last_modified_date",
            "last_accessed_date",
        ],
        excluded_llm_metadata_keys=[
            "file_name",
            "file_type",
            "file_size",
            "creation_date",
            "last_modified_date",
            "last_accessed_date",
        ],
    )
    node = nodes_for_index([document], FilesystemSource(Path(".")))[0]
    embedded = node.get_content(metadata_mode=MetadataMode.EMBED)
    prompted = node.get_content(metadata_mode=MetadataMode.LLM)

    assert node.get_text() == text
    for hidden in ("source_type", "source_id", "file_name", "file_size"):
        assert hidden not in embedded
        assert hidden not in prompted
    for kept in ("file_path", "page_label", "relative_path", "source_mtime"):
        assert kept in embedded
        assert kept in prompted


def test_new_chunks_record_the_source_without_forcing_a_reindex():
    metadata = {}
    FilesystemSource(Path(".")).describe_chunk("notes/gate.txt", metadata)
    assert metadata == {
        "relative_path": "notes/gate.txt",
        "source_type": "filesystem",
        "source_id": "notes/gate.txt",
    }
    collection = {
        "embed_model": "intfloat/multilingual-e5-small",
        "source_type": "filesystem",
    }
    assert (
        embeddings.full_reindex_required(
            collection, 3, "intfloat/multilingual-e5-small"
        )
        is False
    )
