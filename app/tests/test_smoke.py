"""Import the running app without Chroma, Ollama, or an embedding download."""

import time

import pytest


class FakeChat:
    """Stand-in for the host chat client. Startup must not call Ollama."""

    def complete(self, prompt: str) -> str:
        return "ok"

    def stream_complete(self, prompt: str):
        yield type("Chunk", (), {"delta": "ok"})()


def test_app_starts_with_a_fake_chat_client_and_memory_store(monkeypatch, tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("llama_index")
    pytest.importorskip("chromadb")
    pytest.importorskip("fastapi")

    monkeypatch.setenv("OLLAMA_MODEL", "fake-model")
    monkeypatch.setenv("CHROMA_HOST", "memory")
    monkeypatch.setenv("CHROMA_PORT", "8000")
    monkeypatch.setenv("RAG_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("OFFLINE_MODE", "true")
    monkeypatch.setenv("LIBRARY_READ_ONLY", "true")
    monkeypatch.delenv("REINDEX_INTERVAL_MINUTES", raising=False)

    import chromadb
    from llama_index.core import Settings

    import engine
    from state import get, reset_for_tests

    reset_for_tests()
    memory = chromadb.EphemeralClient()

    def connect_memory() -> None:
        from store.chroma import _remember_collection

        collection = memory.get_or_create_collection("rag_collection")
        get().db = memory
        _remember_collection(collection)

    def warm_with_fakes() -> None:
        Settings.llm = FakeChat()
        Settings.embed_model = object()
        get().models_ready.set()

    monkeypatch.setattr(engine, "connect_chroma", connect_memory)
    monkeypatch.setattr(engine, "_warm_up", warm_with_fakes)

    import api.app as api_app
    from fastapi.testclient import TestClient

    with TestClient(api_app.app) as client:
        health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    deadline = time.time() + 20
    status = None
    while time.time() < deadline:
        status = get().ingestion_status.get("status")
        if status in {"completed", "error"}:
            break
        time.sleep(0.05)

    assert isinstance(Settings.llm, FakeChat)
    assert get().chroma_collection is memory.get_collection("rag_collection")
    assert get().chroma_collection.count() == 0
    assert status == "completed"
