"""Library path classification is cached until the collection changes."""

from state import LibraryIndexCache, activate, reset_for_tests


def setup_function(_function):
    reset_for_tests()
    activate()


def teardown_function(_function):
    reset_for_tests()


def test_indexed_documents_reuses_cache(monkeypatch):
    import store.chroma as chroma
    from state import get

    calls = {"n": 0}

    class FakeCollection:
        def count(self):
            return 2

        def get(self, include=None):
            calls["n"] += 1
            return {
                "metadatas": [
                    {
                        "relative_path": "a.pdf",
                        "file_size": 1,
                        "last_modified_date": "2026-01-01",
                        "index_complete": True,
                    },
                    {
                        "relative_path": "b.pdf",
                        "file_size": 2,
                        "last_modified_date": "2026-01-01",
                        "index_complete": True,
                    },
                ]
            }

    get().chroma_collection = FakeCollection()
    first = chroma.indexed_documents()
    second = chroma.indexed_documents()
    assert first[0].keys() == {"a.pdf", "b.pdf"}
    assert second is not first  # tuple rebuilt from cached maps is fine
    assert first[0] == second[0]
    assert calls["n"] == 1
    assert get().library_index.count == 2


def test_invalidate_library_index_clears_cache():
    from state import get
    import store.chroma as chroma

    get().library_index.complete = {"x.pdf": (1, "2026-01-01", None)}
    get().library_index.count = 1
    chroma.invalidate_library_index()
    assert isinstance(get().library_index, LibraryIndexCache)
    assert get().library_index.complete is None
    assert get().library_index.count == -1
