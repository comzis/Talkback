"""Runtime settings. The chat model comes only from OLLAMA_MODEL."""

from __future__ import annotations

import os

DEFAULT_OLLAMA_BASE_URL = "http://host.docker.internal:11434"
DEFAULT_EMBED_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_EMBED_BATCH = 16
DEFAULT_OLLAMA_TIMEOUT = 300.0


def _raw(name: str) -> str:
    return (os.getenv(name) or "").strip()


def configured_model() -> str:
    """The model name from the environment, or an empty string when it is unset."""
    return _raw("OLLAMA_MODEL")


def require_ollama_model() -> str:
    model = configured_model()
    if not model:
        raise ValueError("OLLAMA_MODEL is not set. Add it to .env before starting.")
    return model


def ollama_base_url() -> str:
    return _raw("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL


def ollama_timeout() -> float:
    raw = _raw("OLLAMA_TIMEOUT")
    if not raw:
        return DEFAULT_OLLAMA_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_OLLAMA_TIMEOUT
    return value if value > 0 else DEFAULT_OLLAMA_TIMEOUT


def embed_model_name() -> str:
    return _raw("EMBED_MODEL") or DEFAULT_EMBED_MODEL


def embed_batch() -> int:
    raw = _raw("EMBED_BATCH")
    if not raw:
        return DEFAULT_EMBED_BATCH
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_EMBED_BATCH
    return value if value > 0 else DEFAULT_EMBED_BATCH
