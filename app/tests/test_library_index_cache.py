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


def _metadata(name, size=1):
    return {
        "relative_path": name,
        "file_size": size,
        "last_modified_date": "2026-01-01",
        "index_complete": True,
    }


class SharedCollection:
    """Stands in for the Chroma server: one shared store, no invalidation calls.

    The indexer writes here directly, the way it would through the real
    Chroma service from its own container. Nothing on this object ever
    calls ``invalidate_library_index()`` -- that only happens inside the
    process that changed the data. The API process's cache has to notice
    the change on its own, by comparing against this object's live count.
    """

    def __init__(self, metadatas):
        self._metadatas = list(metadatas)

    def count(self):
        return len(self._metadatas)

    def get(self, include=None):
        return {"metadatas": list(self._metadatas)}


def test_indexed_documents_sees_indexer_add_without_local_invalidate():
    """The API process never calls invalidate here -- only the live count does."""
    import store.chroma as chroma
    from state import get

    shared = SharedCollection([_metadata("a.pdf"), _metadata("b.pdf")])
    get().chroma_collection = shared
    first = chroma.indexed_documents()
    assert first[0].keys() == {"a.pdf", "b.pdf"}

    # A separate process (the indexer) adds a file straight to the shared
    # store. It cannot reach into this process's library_index cache.
    shared._metadatas.append(_metadata("c.pdf"))

    second = chroma.indexed_documents()
    assert second[0].keys() == {"a.pdf", "b.pdf", "c.pdf"}


def test_indexed_documents_sees_indexer_remove_without_local_invalidate():
    import store.chroma as chroma
    from state import get

    shared = SharedCollection([_metadata("a.pdf"), _metadata("b.pdf")])
    get().chroma_collection = shared
    chroma.indexed_documents()

    # The indexer deletes b.pdf's chunk directly in the shared store.
    shared._metadatas = [m for m in shared._metadatas if m["relative_path"] != "b.pdf"]

    refreshed = chroma.indexed_documents()
    assert refreshed[0].keys() == {"a.pdf"}


def test_bm25_sees_indexer_change_without_local_invalidate():
    pytest = __import__("pytest")
    pytest.importorskip("rank_bm25")
    import retrieval.bm25 as bm25
    from state import get

    class Bm25Collection(SharedCollection):
        def get(self, include=None):
            return {
                "ids": [m["relative_path"] for m in self._metadatas],
                "documents": [
                    f"content for {m['relative_path']}" for m in self._metadatas
                ],
                "metadatas": list(self._metadatas),
            }

    shared = Bm25Collection([_metadata("a.pdf"), _metadata("b.pdf")])
    get().chroma_collection = shared
    bm25.retrieve_nodes("content", top_k=5)
    assert get().bm25.count == 2

    shared._metadatas.append(_metadata("c.pdf"))
    bm25.retrieve_nodes("content", top_k=5)
    assert get().bm25.count == 3
    assert "c.pdf" in get().bm25.ids
