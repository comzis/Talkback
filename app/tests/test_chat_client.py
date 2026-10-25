"""The chat client speaks OpenAI completions. vLLM is exercised with a fake transport.

The vLLM path is not tested against a real vLLM server.
"""

import json

import pytest


def _client():
    pytest.importorskip("httpx")
    import llm.client as client

    return client


def test_ollama_body_pins_keep_alive_and_skips_reasoning():
    client = _client()
    body = client.chat_request_body(
        backend="ollama",
        model="qwen",
        prompt="hello",
        temperature=0.1,
        keep_alive="3h",
        context=8192,
        think=False,
    )
    assert body["keep_alive"] == "3h"
    assert body["options"] == {"num_ctx": 8192}
    assert body["reasoning_effort"] == "none"
    assert body["messages"] == [{"role": "user", "content": "hello"}]
    assert client.completions_url("http://host.docker.internal:11434") == (
        "http://host.docker.internal:11434/v1/chat/completions"
    )


def test_vllm_body_omits_ollama_fields():
    client = _client()
    body = client.chat_request_body(
        backend="vllm",
        model="qwen",
        prompt="hello",
        temperature=None,
        keep_alive="3h",
        context=8192,
        think=False,
    )
    assert "keep_alive" not in body
    assert "options" not in body
    assert "reasoning_effort" not in body


def test_stream_reads_content_deltas():
    httpx = pytest.importorskip("httpx")
    client_mod = _client()
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content.decode())
        payload = (
            'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":" there"}}]}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(200, text=payload)

    client = client_mod.ChatClient(
        base_url="http://chat.local",
        model="qwen",
        backend="ollama",
        timeout=5,
        context=8192,
        keep_alive="3h",
        think=False,
        transport=httpx.MockTransport(handler),
    )
    assert "".join(client.stream("hello", temperature=0.1)) == "Hi there"
    assert seen["body"]["keep_alive"] == "3h"


def test_vllm_status_reads_the_models_list():
    client = _client()
    assert client.models_url("http://vllm:8000", "vllm") == "http://vllm:8000/v1/models"
    assert client.models_url("http://ollama:11434", "ollama").endswith("/api/tags")
    names = client.installed_model_names({"data": [{"id": "qwen"}]}, "vllm")
    assert names == ["qwen"]


def test_vllm_backend_disables_ollama_endpoints(monkeypatch):
    client = _client()
    monkeypatch.setenv("CHAT_BACKEND", "vllm")
    with pytest.raises(client.OllamaOnly):
        client.reject_unless_ollama()
