"""OpenAI-compatible chat client.

Host Ollama 0.40.6 accepts keep_alive on POST /v1/chat/completions. The same
call ignores think:false for Qwen and still fills the reasoning field, so a
disabled trace is sent as reasoning_effort "none".

The vLLM path is not tested against a real vLLM server. Tests use a fake
httpx transport.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import httpx

import config
import store.embeddings as embeddings
from state import get

logger = logging.getLogger(__name__)


class OllamaOnly(Exception):
    """An Ollama endpoint was called while CHAT_BACKEND=vllm.

    The vLLM path is not tested against a real vLLM server.
    """


def reject_unless_ollama() -> None:
    if config.chat_backend() == "vllm":
        raise OllamaOnly(
            "This endpoint talks to Ollama and is disabled when CHAT_BACKEND=vllm."
        )


def completions_url(base: str) -> str:
    root = base.rstrip("/")
    if root.endswith("/v1"):
        return root + "/chat/completions"
    return root + "/v1/chat/completions"


def models_url(base: str, backend: str) -> str:
    """Ollama lists /api/tags. A vLLM server lists /v1/models.

    The vLLM path is not tested against a real vLLM server.
    """
    root = base.rstrip("/")
    if backend == "vllm":
        if root.endswith("/v1"):
            return root + "/models"
        return root + "/v1/models"
    return root + "/api/tags"


def installed_model_names(payload: dict, backend: str) -> list[str]:
    """Names from an Ollama tag list or a vLLM /v1/models payload.

    The vLLM shape is not tested against a real vLLM server.
    """
    if backend == "vllm":
        return [str(item.get("id") or "") for item in payload.get("data") or []]
    return [str(item.get("name") or "") for item in payload.get("models") or []]


def chat_request_body(
    *,
    backend: str,
    model: str,
    prompt: str,
    temperature: float | None,
    keep_alive: str,
    context: int,
    think: bool,
) -> dict:
    """One chat-completions body. Ollama fields are omitted for vLLM."""
    body: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }
    if temperature is not None:
        body["temperature"] = temperature
    if backend == "ollama":
        body["keep_alive"] = keep_alive
        body["options"] = {"num_ctx": context}
        if not think:
            body["reasoning_effort"] = "none"
    return body


class ChatClient:
    """Streams /v1/chat/completions. One prompt is one user message."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        backend: str,
        timeout: float,
        context: int,
        keep_alive: str,
        think: bool,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url
        self.model = model
        self.backend = backend
        self.timeout = timeout
        self.context = context
        self.keep_alive = keep_alive
        self.think = think
        self._transport = transport

    def use_model(self, model: str) -> None:
        self.model = model

    def complete(self, prompt: str, temperature: float | None = None) -> str:
        return "".join(self.stream(prompt, temperature)).strip()

    def stream(self, prompt: str, temperature: float | None = None) -> Iterator[str]:
        body = chat_request_body(
            backend=self.backend,
            model=self.model,
            prompt=prompt,
            temperature=temperature,
            keep_alive=self.keep_alive,
            context=self.context,
            think=self.think,
        )
        timeout = httpx.Timeout(self.timeout)
        with httpx.Client(timeout=timeout, transport=self._transport) as client:
            with client.stream(
                "POST", completions_url(self.base_url), json=body
            ) as response:
                if response.status_code != 200:
                    response.read()
                    raise RuntimeError(
                        f"Chat completion failed ({response.status_code})."
                    )
                for line in response.iter_lines():
                    delta = _delta_text(line)
                    if delta:
                        yield delta


def _delta_text(line: str) -> str:
    text = (line or "").strip()
    if not text.startswith("data:"):
        return ""
    data = text[5:].strip()
    if not data or data == "[DONE]":
        return ""
    payload = json.loads(data)
    choices = payload.get("choices") or []
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    return delta.get("content") or ""


def build_chat_client() -> ChatClient:
    return ChatClient(
        base_url=config.chat_base_url(),
        model=config.require_ollama_model(),
        backend=config.chat_backend(),
        timeout=config.ollama_timeout(),
        context=config.ollama_context(),
        keep_alive=config.ollama_keep_alive(),
        think=config.ollama_think(),
    )


def models_ready() -> bool:
    return get().models_ready.is_set()


def wait_for_models(timeout: float = 180) -> None:
    """Block a query or ingest until the background warm-up has finished."""
    from llama_index.core import Settings

    if get().models_ready.wait(timeout):
        if Settings.embed_model is None or get().chat is None:
            raise RuntimeError("Local models did not finish loading.")
        return
    raise TimeoutError("Talkback is still loading the local models.")


def _warm_up() -> None:
    """Load the embedder and send one short request to the chat server."""
    from llama_index.core import Settings
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    try:
        model_name = config.embed_model_name()
        get().chat = build_chat_client()
        Settings.embed_model = HuggingFaceEmbedding(
            model_name=model_name,
            query_instruction=embeddings.query_instruction(model_name),
            text_instruction=embeddings.text_instruction(model_name),
        )
        Settings.embed_model.get_query_embedding("ping")
        get().chat.complete("ok")
        logger.info("Warm-up finished.")
    except Exception:
        logger.exception("Warm-up failed")
    finally:
        get().models_ready.set()


def _complete(prompt: str, temperature: float | None = None) -> str:
    """Complete one prompt, pinning temperature only for that call."""
    chat = get().chat
    if chat is None:
        raise RuntimeError("The chat client is not ready.")
    return chat.complete(prompt, temperature)


def _stream_deltas(prompt: str, temperature: float | None = None):
    """Yield text deltas from the OpenAI-compatible chat stream."""
    chat = get().chat
    if chat is None:
        raise RuntimeError("The chat client is not ready.")
    yield from chat.stream(prompt, temperature)
