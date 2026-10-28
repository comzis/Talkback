#!/usr/bin/env python3
"""Time the same three prompts on one or more host Ollama models.

Uses POST /api/chat so thinking can be turned off the same way Talkback does:
``think: false`` for Qwen, ``think: "low"`` for gpt-oss (boolean false still
reasons). Each row reports eval_count, visible content characters, and
thinking characters so a hidden reasoning trace is obvious.

    python scripts/compare_models.py qwen3.8:27b gpt-oss:20b qwen3.5:9b
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

PROMPTS = (
    ("en", "In one sentence, what is a gate code?"),
    ("fr", "En une phrase, qu'est-ce qu'un code de portail ?"),
    ("es", "En una frase, ¿qué es un código de puerta?"),
)


def tokens_per_second(
    eval_count: int | None, eval_duration_ns: int | None
) -> float | None:
    """Ollama reports eval_duration in nanoseconds for the generated tokens."""
    if not eval_count or not eval_duration_ns:
        return None
    return eval_count / (eval_duration_ns / 1_000_000_000)


def think_value(model: str) -> bool | str:
    """Lowest / off setting for this model family."""
    name = (model or "").lower()
    if "gpt-oss" in name:
        return "low"
    return False


def stream_chat(base_url: str, model: str, prompt: str, timeout: float = 600) -> dict:
    """Send one chat prompt with thinking off / lowest and return timings."""
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "think": think_value(model),
            "keep_alive": "10m",
            "options": {"num_ctx": 2048},
        }
    ).encode()
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()
    first_token_at = None
    content_chars = 0
    thinking_chars = 0
    final = None
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw in response:
            line = raw.decode("utf-8").strip()
            if not line:
                continue
            event = json.loads(line)
            message = event.get("message") or {}
            piece = message.get("content") or ""
            thought = message.get("thinking") or ""
            content_chars += len(piece)
            thinking_chars += len(thought)
            if first_token_at is None and piece:
                first_token_at = time.perf_counter()
            if event.get("done") is True:
                final = event
    finished = time.perf_counter()
    if final is None:
        raise RuntimeError(f"{model} ended without a done=true event")
    return {
        "model": model,
        "ttft_seconds": None
        if first_token_at is None
        else round(first_token_at - started, 3),
        "total_seconds": round(finished - started, 3),
        "tokens_per_second": None
        if (
            rate := tokens_per_second(
                final.get("eval_count"), final.get("eval_duration")
            )
        )
        is None
        else round(rate, 2),
        "eval_count": final.get("eval_count"),
        "content_chars": content_chars,
        "thinking_chars": thinking_chars,
        "think": think_value(model),
    }


def main(argv: list[str]) -> int:
    models = argv[1:]
    if not models:
        print(
            "Usage: python scripts/compare_models.py MODEL [MODEL ...]", file=sys.stderr
        )
        return 2
    base_url = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    print(
        f"{'model':<24} {'lang':<6} {'ttft_s':>8} {'tok/s':>8} {'total_s':>8} "
        f"{'eval':>5} {'out':>5} {'think':>5}"
    )
    for model in models:
        for lang, prompt in PROMPTS:
            try:
                row = stream_chat(base_url, model, prompt)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:200]
                print(f"{model:<24} {lang:<6} error {exc.code}: {detail}")
                continue
            except Exception as exc:
                print(f"{model:<24} {lang:<6} error: {exc}")
                continue
            rate = (
                ""
                if row["tokens_per_second"] is None
                else f"{row['tokens_per_second']:.2f}"
            )
            ttft = "" if row["ttft_seconds"] is None else f"{row['ttft_seconds']:.3f}"
            print(
                f"{model:<24} {lang:<6} {ttft:>8} {rate:>8} {row['total_seconds']:>8.3f} "
                f"{row['eval_count'] or 0:>5} {row['content_chars']:>5} "
                f"{row['thinking_chars']:>5}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
