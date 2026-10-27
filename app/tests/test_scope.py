"""Search-scope helpers."""

from retrieval.search import resolve_scope


def test_resolve_scope_all_and_file():
    files = [
        "TechnicalDeliveryStandardsBBCLive.pdf",
        "notes/gate.txt",
        "notes/deep/a.txt",
    ]
    assert resolve_scope(None, files) is None
    assert resolve_scope("", files) is None
    assert resolve_scope("all", files) is None
    assert resolve_scope("TechnicalDeliveryStandardsBBCLive.pdf", files) == [
        "TechnicalDeliveryStandardsBBCLive.pdf"
    ]


def test_resolve_scope_folder_prefix():
    files = [
        "notes/gate.txt",
        "notes/deep/a.txt",
        "other/x.txt",
    ]
    assert resolve_scope("notes", files) == ["notes/gate.txt", "notes/deep/a.txt"]
    assert resolve_scope("notes/", files) == ["notes/gate.txt", "notes/deep/a.txt"]
    assert resolve_scope("missing", files) == []
