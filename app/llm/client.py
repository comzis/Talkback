"""Host chat model: warm-up, one completion, and a token stream."""

from __future__ import annotations

import logging
import threading

from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama

import config
import store.embeddings as embeddings

logger = logging.getLogger(__name__)

_models_ready = threading.Event()


def models_ready() -> bool:
    return _models_ready.is_set()


def wait_for_models(timeout: float = 180) -> None:
    """Block a query or ingest until the background warm-up has finished."""
    if _models_ready.wait(timeout):
        if Settings.embed_model is None or Settings.llm is None:
            raise RuntimeError("Local models did not finish loading.")
        return
    raise TimeoutError("Talkback is still loading the local models.")


def _warm_up() -> None:
    """Load the embedder and send one short request to host Ollama."""
    try:
        model_name = config.embed_model_name()
        Settings.llm = Ollama(
            model=config.require_ollama_model(),
            base_url=config.ollama_base_url(),
            request_timeout=config.ollama_timeout(),
            context_window=config.ollama_context(),
            keep_alive=config.ollama_keep_alive(),
            thinking=config.ollama_think(),
        )
        Settings.embed_model = HuggingFaceEmbedding(
            model_name=model_name,
            query_instruction=embeddings.query_instruction(model_name),
            text_instruction=embeddings.text_instruction(model_name),
        )
        Settings.embed_model.get_query_embedding("ping")
        Settings.llm.complete("ok")
        logger.info("Warm-up finished.")
    except Exception:
        logger.exception("Warm-up failed")
    finally:
        _models_ready.set()


def _complete(prompt: str, temperature: float | None = None) -> str:
    """Complete one prompt, pinning temperature only for that call."""
    llm = Settings.llm
    if temperature is None or not hasattr(llm, "temperature"):
        return str(llm.complete(prompt)).strip()
    previous = llm.temperature
    llm.temperature = temperature
    try:
        return str(llm.complete(prompt)).strip()
    finally:
        llm.temperature = previous


def _stream_deltas(prompt: str, temperature: float | None = None):
    """Yield text deltas from Ollama.stream_complete, which this version provides."""
    llm = Settings.llm
    previous = getattr(llm, "temperature", None)
    if temperature is not None and hasattr(llm, "temperature"):
        llm.temperature = temperature
    try:
        for chunk in llm.stream_complete(prompt):
            delta = chunk.delta or ""
            if delta:
                yield delta
    finally:
        if temperature is not None and hasattr(llm, "temperature"):
            llm.temperature = previous
