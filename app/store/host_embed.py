"""Optional host embeddings. Empty EMBED_URL keeps the in-process model."""

from __future__ import annotations

import logging
from typing import Any

import config
import store.embeddings as embeddings
from store.search_errors import SearchUnavailable

logger = logging.getLogger(__name__)


class HostUnreachable(Exception):
    """The configured host embedder did not accept a connection."""


def _host_required(exc: Exception | None = None) -> SearchUnavailable:
    err = SearchUnavailable(
        "Search is temporarily unavailable. The host embedder is down."
    )
    if exc is not None:
        err.__cause__ = exc
    return err


def embed_url() -> str:
    return config.embed_url()


def _warn_host_down(url: str) -> None:
    from state import get

    if get().embed_host_warning_logged:
        return
    get().embed_host_warning_logged = True
    logger.warning(
        "Host embedder at %s is unreachable. Library search needs that service.",
        url,
    )


def _host_recovered() -> None:
    from state import get

    get().embed_host_warning_logged = False


def _post_embeddings(url: str, texts: list[str]) -> dict:
    import httpx

    try:
        with httpx.Client(timeout=httpx.Timeout(300.0)) as client:
            response = client.post(url.rstrip("/") + "/embed", json={"texts": texts})
    except httpx.HTTPError as exc:
        raise HostUnreachable(str(exc)) from exc
    if response.status_code != 200:
        raise RuntimeError(f"Host embedder failed ({response.status_code}).")
    payload = response.json()
    vectors = payload.get("embeddings")
    if not isinstance(vectors, list):
        raise RuntimeError("Host embedder returned no embeddings.")
    return payload


def _host_health(url: str) -> dict | None:
    import httpx

    try:
        response = httpx.get(url.rstrip("/") + "/health", timeout=httpx.Timeout(2.0))
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def active_embed() -> dict:
    """The embedder the next call will use."""
    url = config.embed_url()
    if not url:
        return {"mode": "container", "device": "cpu", "url": ""}
    health = _host_health(url)
    if health is None:
        _warn_host_down(url)
        return {
            "mode": "unavailable",
            "device": "",
            "url": url,
            "host": "unreachable",
        }
    _host_recovered()
    device = health.get("embed_device") or health.get("device") or "host"
    return {
        "mode": "host",
        "device": str(device),
        "url": url,
        "host": "reachable",
        "embed_loaded": bool(health.get("embed_loaded")),
    }


def _local_embed_model(model_name: str, batch: int):
    """In-process HuggingFace embedder (Linux GPU server path when EMBED_URL is empty)."""
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    return HuggingFaceEmbedding(
        model_name=model_name,
        query_instruction=embeddings.query_instruction(model_name),
        text_instruction=embeddings.text_instruction(model_name),
        embed_batch_size=batch,
    )


def build_embed_model():
    """Host embedder when EMBED_URL is set; otherwise HuggingFace in-process.

    When EMBED_URL is set, a down host raises SearchUnavailable. There is no
    in-container CPU fallback: Mac stacks need the host MPS service, and the
    Linux server leaves EMBED_URL empty so this process uses the GPU directly.
    """
    from llama_index.core.base.embeddings.base import BaseEmbedding
    from pydantic import Field, PrivateAttr

    model_name = config.embed_model_name()
    url = config.embed_url()
    batch = config.embed_batch()

    class HostOrLocalEmbedding(BaseEmbedding):
        """POST /embed on the host, or HuggingFace when no host URL is set."""

        embed_endpoint: str = Field(default="")
        _local: Any = PrivateAttr(default=None)
        _query_instruction: str | None = PrivateAttr(default=None)
        _text_instruction: str | None = PrivateAttr(default=None)

        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self._query_instruction = embeddings.query_instruction(self.model_name)
            self._text_instruction = embeddings.text_instruction(self.model_name)

        @classmethod
        def class_name(cls) -> str:
            return "HostOrLocalEmbedding"

        def _prepare(self, text: str, *, is_query: bool) -> str:
            if is_query:
                return embeddings.embedded_query(self.model_name, text)
            return embeddings.embedded_passage(self.model_name, text)

        def _ensure_local(self):
            if self._local is None:
                logger.info("Loading in-process embedder %s", self.model_name)
                self._local = _local_embed_model(self.model_name, self.embed_batch_size)
            return self._local

        def _embed_batch(
            self, texts: list[str], *, is_query: bool
        ) -> list[list[float]]:
            prepared = [self._prepare(text, is_query=is_query) for text in texts]
            if not self.embed_endpoint:
                local = self._ensure_local()
                if is_query:
                    return [local.get_query_embedding(text) for text in texts]
                return local.get_text_embedding_batch(texts)

            try:
                payload = _post_embeddings(self.embed_endpoint, prepared)
            except HostUnreachable as exc:
                _warn_host_down(self.embed_endpoint)
                raise _host_required(exc) from exc

            _host_recovered()
            vectors = payload["embeddings"]
            if len(vectors) != len(texts):
                raise RuntimeError(
                    "Host embedder returned a different number of embeddings."
                )
            return [[float(value) for value in row] for row in vectors]

        def _get_query_embedding(self, query: str) -> list[float]:
            return self._embed_batch([query], is_query=True)[0]

        def _get_text_embedding(self, text: str) -> list[float]:
            return self._embed_batch([text], is_query=False)[0]

        def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
            return self._embed_batch(texts, is_query=False)

        async def _aget_query_embedding(self, query: str) -> list[float]:
            return self._get_query_embedding(query)

        async def _aget_text_embedding(self, text: str) -> list[float]:
            return self._get_text_embedding(text)

        async def _aget_text_embeddings(self, texts: list[str]) -> list[list[float]]:
            return self._get_text_embeddings(texts)

    return HostOrLocalEmbedding(
        model_name=model_name,
        embed_batch_size=batch,
        embed_endpoint=url,
    )
