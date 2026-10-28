"""Cross-encoder rerank. The model stays on this machine and loads on first use."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import config

logger = logging.getLogger(__name__)

_lock = threading.Lock()


class HostUnreachable(Exception):
    """The configured host reranker did not accept a connection."""


def clears_threshold(score: float, threshold: float) -> bool:
    """True when a reranker logit is high enough to answer from the library."""
    return score >= threshold


def best_rerank_score(nodes) -> float | None:
    """Highest logit stored on these nodes, or None when they were not reranked."""
    scores = []
    for node in nodes:
        metadata = getattr(node, "metadata", None) or {}
        if not isinstance(metadata, dict):
            continue
        score = metadata.get("rerank_score")
        if score is not None:
            scores.append(float(score))
    if not scores:
        return None
    return max(scores)


def model_cache_dir() -> Path:
    """The mounted user cache, not the container-local HF_HOME.

    Compose points HF_HOME at /cache/huggingface, which disappears when the
    container is recreated. ./hf_cache is mounted on the user cache, and that
    is where this model is stored so a restart stays offline.
    """
    return Path.home() / ".cache" / "huggingface" / "hub"


def _device():
    import torch

    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def _load():
    from state import get

    talkback = get()
    with _lock:
        if talkback.rerank_model is None:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            name = config.rerank_model_name()
            cache = str(model_cache_dir())
            device = _device()
            logger.info("Loading reranker %s from %s on %s", name, cache, device)
            talkback.rerank_tokenizer = AutoTokenizer.from_pretrained(
                name, cache_dir=cache, local_files_only=True
            )
            model = AutoModelForSequenceClassification.from_pretrained(
                name, cache_dir=cache, local_files_only=True
            )
            model.to(device)
            model.eval()
            talkback.rerank_model = model
    return talkback.rerank_model, talkback.rerank_tokenizer


def _mark(node, score: float):
    metadata = getattr(node, "metadata", None)
    if isinstance(metadata, dict):
        metadata["rerank_score"] = score
    node.score = score
    return node


def _passage(node) -> str:
    if hasattr(node, "get_content"):
        return node.get_content() or ""
    return node.get_text() or ""


def _post_scores(url: str, body: dict) -> dict:
    import httpx

    try:
        with httpx.Client(timeout=httpx.Timeout(120.0)) as client:
            response = client.post(url.rstrip("/") + "/rerank", json=body)
    except httpx.HTTPError as exc:
        raise HostUnreachable(str(exc)) from exc
    if response.status_code != 200:
        raise RuntimeError(f"Host reranker failed ({response.status_code}).")
    payload = response.json()
    scores = payload.get("scores")
    if not isinstance(scores, list):
        raise RuntimeError("Host reranker returned no scores.")
    return payload


def _host_health(url: str) -> dict | None:
    """Health payload, or None when the host process cannot be reached."""
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


def _warn_host_down(url: str) -> None:
    """One warning for an outage. A later success arms the warning again."""
    from state import get

    if get().rerank_host_warning_logged:
        return
    get().rerank_host_warning_logged = True
    logger.warning(
        "Host reranker at %s is unreachable. Scoring pairs in this container on CPU.",
        url,
    )


def _host_recovered() -> None:
    from state import get

    get().rerank_host_warning_logged = False


def active_rerank() -> dict:
    """The reranker the next query will use.

    A set RERANK_URL is probed. If that process is down, queries score pairs
    in this container and this report says so.
    """
    url = config.rerank_url()
    if not url:
        return {"mode": "container", "device": "cpu", "url": ""}
    health = _host_health(url)
    if health is None:
        _warn_host_down(url)
        return {
            "mode": "container",
            "device": "cpu",
            "url": url,
            "host": "unreachable",
        }
    _host_recovered()
    return {
        "mode": "host",
        "device": str(health.get("device") or "host"),
        "url": url,
        "host": "reachable",
    }


def rerank_nodes(query: str, nodes: list):
    """Return the same nodes, highest reranker logit first."""
    if not nodes:
        return []
    import time

    limit = config.rerank_max_length()
    # The tokenizer drops anything past the cap. Cut the string first so a long
    # chunk is not tokenised only to be thrown away.
    char_cap = limit * 4
    query_text = query[:char_cap]
    passages = [_passage(node)[:char_cap] for node in nodes]
    url = config.rerank_url()
    started = time.perf_counter()
    if url:
        try:
            payload = _post_scores(
                url,
                {"query": query_text, "passages": passages, "max_length": limit},
            )
        except HostUnreachable:
            _warn_host_down(url)
            scores, where = _local_scores(query_text, passages, limit)
        else:
            _host_recovered()
            scores = [float(score) for score in payload["scores"]]
            if len(scores) != len(nodes):
                raise RuntimeError(
                    "Host reranker returned a different number of scores."
                )
            where = str(payload.get("device") or url)
    else:
        scores, where = _local_scores(query_text, passages, limit)
    logger.info(
        "Reranked %s pairs on %s in %.3fs",
        len(passages),
        where,
        time.perf_counter() - started,
    )
    order = sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)
    return [_mark(nodes[index], scores[index]) for index in order]


def _local_scores(
    query: str, passages: list[str], limit: int
) -> tuple[list[float], str]:
    import torch

    model, tokenizer = _load()
    pairs = [[query, text] for text in passages]
    device = next(model.parameters()).device
    scores: list[float] = []
    with torch.no_grad():
        for start in range(0, len(pairs), 8):
            batch = pairs[start : start + 8]
            inputs = tokenizer(
                batch,
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=limit,
            )
            inputs = inputs.to(device)
            logits = model(**inputs, return_dict=True).logits.view(-1).float()
            scores.extend(float(score) for score in logits.tolist())
    return scores, str(device)
