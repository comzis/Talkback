"""Import the running app without Chroma, Ollama, or an embedding download."""

import time

import pytest


def test_app_starts_with_a_fake_chat_client_and_memory_store(monkeypatch, tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("llama_index")
    pytest.importorskip("chromadb")
    pytest.importorskip("fastapi")
    from llama_index.core.embeddings.mock_embed_model import MockEmbedding
    from llama_index.core.llms.mock import MockLLM

    monkeypatch.setenv("OLLAMA_MODEL", "fake-model")
    monkeypatch.setenv("CHROMA_HOST", "memory")
    monkeypatch.setenv("CHROMA_PORT", "8000")
    library = tmp_path / "library"
    library.mkdir()
    monkeypatch.setenv("RAG_DATA_DIR", str(library))
    monkeypatch.setenv("STATUS_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("OFFLINE_MODE", "true")
    monkeypatch.setenv("LIBRARY_READ_ONLY", "true")
    monkeypatch.delenv("REINDEX_INTERVAL_MINUTES", raising=False)

    import chromadb
    from llama_index.core import Settings

    import engine
    from state import get, reset_for_tests

    reset_for_tests()
    memory = chromadb.EphemeralClient()
    chat = MockLLM()

    def connect_memory() -> None:
        from store.chroma import _remember_collection

        collection = memory.get_or_create_collection("rag_collection")
        get().db = memory
        _remember_collection(collection)

    def warm_with_fakes() -> None:
        Settings.llm = chat
        Settings.embed_model = MockEmbedding(embed_dim=8)

        class _FakeChat:
            def complete(self, prompt: str, temperature: float | None = None) -> str:
                return str(chat.complete(prompt)).strip()

            def stream(self, prompt: str, temperature: float | None = None):
                for chunk in chat.stream_complete(prompt):
                    delta = chunk.delta or ""
                    if delta:
                        yield delta

        get().chat = _FakeChat()
        get().models_ready.set()

    monkeypatch.setattr(engine, "connect_chroma", connect_memory)
    monkeypatch.setattr(engine, "_warm_up", warm_with_fakes)

    import api.app as api_app
    from fastapi.testclient import TestClient

    with TestClient(api_app.app) as client:
        health = client.get("/health")
        assert get().ingestion_status.get("status") == "idle"
        queued = client.post("/ingest")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert queued.status_code == 200
    assert get().ingestion_status.get("status") == "idle"
    from store.status_db import StatusStore

    assert (
        StatusStore(tmp_path / "state" / "library.sqlite").peek_request()
        == "incremental"
    )

    engine.start_initial_index()
    deadline = time.time() + 20
    status = None
    while time.time() < deadline:
        status = get().ingestion_status.get("status")
        if status in {"completed", "error"}:
            break
        time.sleep(0.05)

    assert Settings.llm is chat
    assert get().db is memory
    assert get().chroma_collection.count() == 0
    assert status == "completed"

    (library / "bad.txt").write_text("unreadable", encoding="utf-8")
    StatusStore(tmp_path / "state" / "library.sqlite").mark_failed(
        "filesystem", "bad.txt", "No readable text"
    )
    listed = TestClient(api_app.app).get("/files")
    assert listed.status_code == 200
    failed = listed.json()["files"]
    assert failed[0]["name"] == "bad.txt"
    assert failed[0]["index_status"] == "failed"
    assert failed[0]["index_error"] == "No readable text"

    held = get().chroma_collection
    (library / "note.txt").write_text(
        "Target loudness is -23.0 LUFS.\n", encoding="utf-8"
    )
    engine.rebuild_library()
    assert held.count() > 0
    assert held.query(query_embeddings=[[0.0] * 8], n_results=1)["ids"][0]
    streamed = TestClient(api_app.app).post(
        "/query/stream",
        json={"query": "What is the target loudness?", "history": []},
    )
    assert streamed.status_code == 200
    assert "event: error" not in streamed.text
    assert "event: token" in streamed.text
    assert get().chroma_collection.id == held.id

    client = TestClient(api_app.app)
    upload = client.post(
        "/upload", files={"files": ("extra.txt", b"hello", "text/plain")}
    )
    assert upload.status_code == 403
    assert client.delete("/files/note.txt").status_code == 403

    def events_for(query: str) -> list[dict]:
        response = client.post("/query/stream", json={"query": query, "history": []})
        assert response.status_code == 200
        assert "event: error" not in response.text
        found = []
        for block in response.text.split("\n\n"):
            event = "message"
            data = ""
            for line in block.splitlines():
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    data += line[5:].strip()
            if data:
                found.append({"event": event, "data": __import__("json").loads(data)})
        return found

    class _Node:
        def __init__(self, text: str, score: float):
            self.metadata = {"relative_path": "note.txt", "page_label": "16"}
            self.score = score
            self._text = text

        def get_text(self) -> str:
            return self._text

    original_stream = engine._stream_deltas
    original_retrieve = engine._retrieve_nodes

    def retrieve_loudness(index, query, files, scope=None):
        return [_Node("Target loudness is -23.0 LUFS.", 0.9)], False

    def stream_loudness(prompt, temperature):
        yield "The loudness target is -23.0 LUFS. [1]"

    engine._retrieve_nodes = retrieve_loudness
    engine._stream_deltas = stream_loudness
    library_events = events_for("What loudness target is required?")
    kinds = [event["event"] for event in library_events]
    assert "token" in kinds and "sources" in kinds and kinds[-1] == "done"
    cards = [
        source
        for event in library_events
        if event["event"] == "sources"
        for source in event["data"]["sources"]
    ]
    assert cards and cards[0]["page"] == "16"

    def retrieve_weak(index, query, files, scope=None):
        return [_Node("Target loudness is -23.0 LUFS.", 0.1)], False

    def stream_draft(prompt, temperature):
        yield "Cause: [cause]. Next step: [next step]."

    engine._retrieve_nodes = retrieve_weak
    engine._stream_deltas = stream_draft
    threshold = events_for("Draft an update with placeholders for the cause.")
    notices = [
        event["data"].get("text", "")
        for event in threshold
        if event["event"] == "notice"
    ]
    assert any("not from the documents" in notice for notice in notices)
    assert not any(
        event["data"].get("sources")
        for event in threshold
        if event["event"] == "sources"
    )

    engine._retrieve_nodes = original_retrieve

    def stream_hello(prompt, temperature):
        yield "Hello."

    engine._stream_deltas = stream_hello
    greeting = events_for("hello")
    assert [event["event"] for event in greeting if event["event"] == "token"] == [
        "token"
    ]
    assert not any(
        event["data"].get("sources")
        for event in greeting
        if event["event"] == "sources"
    )

    def stream_invented(prompt, temperature):
        yield "The level "
        yield "is -99 LUFS."

    engine._retrieve_nodes = retrieve_loudness
    engine._stream_deltas = stream_invented
    invented = events_for("What loudness target is required?")
    tokens = [event["data"]["text"] for event in invented if event["event"] == "token"]
    assert tokens == ["The level ", "is -99 LUFS."]
    footnotes = [
        event["data"]["text"] for event in invented if event["event"] == "footnote"
    ]
    assert footnotes
    assert "not include that detail" in footnotes[0]
    engine._stream_deltas = original_stream
    engine._retrieve_nodes = original_retrieve

    monkeypatch.setenv("CHAT_BACKEND", "vllm")
    blocked = TestClient(api_app.app)
    assert blocked.get("/llm/models").status_code == 403
    assert blocked.post("/llm/select", json={"model": "x"}).status_code == 403
    pull = blocked.post("/llm/pull", json={"model": "x"})
    assert pull.status_code == 403
    assert "disabled when CHAT_BACKEND=vllm" in pull.json()["detail"]
