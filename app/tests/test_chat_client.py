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
    assert body["think"] is False
    assert body["options"] == {"num_ctx": 8192, "temperature": 0.1}
    assert "reasoning_effort" not in body
    assert body["messages"] == [{"role": "user", "content": "hello"}]
    assert client.chat_url("http://host.docker.internal:11434", "ollama") == (
        "http://host.docker.internal:11434/api/chat"
    )
    assert client.chat_url("http://host.docker.internal:11434/v1", "ollama") == (
        "http://host.docker.internal:11434/api/chat"
    )
    assert client.think_value("qwen3.5:9b", False) is False
    assert client.think_value("gpt-oss:20b", False) == "low"
    assert client.think_value("gpt-oss:20b", True) == "medium"
    oss = client.chat_request_body(
        backend="ollama",
        model="gpt-oss:20b",
        prompt="hello",
        temperature=0.1,
        keep_alive="3h",
        context=8192,
        think=False,
    )
    assert oss["think"] == "low"


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


def test_ollama_stream_reads_content_and_skips_thinking():
    httpx = pytest.importorskip("httpx")
    client_mod = _client()
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content.decode())
        payload = "\n".join(
            [
                json.dumps(
                    {
                        "message": {
                            "role": "assistant",
                            "thinking": "hidden",
                            "content": "",
                        }
                    }
                ),
                json.dumps({"message": {"role": "assistant", "content": "Hi"}}),
                json.dumps(
                    {
                        "message": {"role": "assistant", "content": " there"},
                        "done": True,
                        "prompt_eval_count": 4,
                        "eval_count": 8,
                        "eval_duration": 400_000_000,
                    }
                ),
            ]
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
    assert client.eval_count == 8
    assert client.eval_duration_ns == 400_000_000
    assert seen["url"] == "http://chat.local/api/chat"
    assert seen["body"]["keep_alive"] == "3h"
    assert seen["body"]["think"] is False
    assert seen["body"]["options"]["num_ctx"] == 8192


def test_vllm_stream_reads_openai_deltas():
    httpx = pytest.importorskip("httpx")
    client_mod = _client()
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        payload = (
            'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":" there"}}]}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(200, text=payload)

    client = client_mod.ChatClient(
        base_url="http://chat.local",
        model="qwen",
        backend="vllm",
        timeout=5,
        context=8192,
        keep_alive="3h",
        think=False,
        transport=httpx.MockTransport(handler),
    )
    assert "".join(client.stream("hello", temperature=0.1)) == "Hi there"
    assert seen["url"] == "http://chat.local/v1/chat/completions"


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
