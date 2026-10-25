"""Cross-encoder rerank. The model stays on this machine and loads on first use."""

from __future__ import annotations

import threading

import config

_lock = threading.Lock()
_model = None
_tokenizer = None


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


def _load():
    global _model, _tokenizer
    with _lock:
        if _model is None:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            name = config.rerank_model_name()
            _tokenizer = AutoTokenizer.from_pretrained(name)
            _model = AutoModelForSequenceClassification.from_pretrained(name)
            _model.eval()
    return _model, _tokenizer


def _mark(node, score: float):
    metadata = getattr(node, "metadata", None)
    if isinstance(metadata, dict):
        metadata["rerank_score"] = score
    node.score = score
    return node


def rerank_nodes(query: str, nodes: list):
    """Return the same nodes, highest reranker logit first."""
    if not nodes:
        return []
    import torch

    model, tokenizer = _load()
    pairs = [
        [query, node.get_content() if hasattr(node, "get_content") else node.get_text()]
        for node in nodes
    ]
    scored: list[tuple[float, int]] = []
    with torch.no_grad():
        for start in range(0, len(pairs), 8):
            batch = pairs[start : start + 8]
            inputs = tokenizer(
                batch,
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=512,
            )
            logits = model(**inputs, return_dict=True).logits.view(-1).float()
            for offset, score in enumerate(logits.tolist()):
                scored.append((float(score), start + offset))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [_mark(nodes[index], score) for score, index in scored]
