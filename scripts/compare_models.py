#!/usr/bin/env python3
"""Time the same three prompts on one or more host Ollama models.

Verified against Ollama 0.40.6. POST /api/generate with stream=true returns
newline-delimited JSON. Each line has `response` (new text) and `done`.
The final line has done=true, eval_count, and eval_duration in nanoseconds.

    python scripts/compare_models.py qwen3:8b qwen3.5:9b
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


def tokens_per_second(eval_count: int | None, eval_duration_ns: int | None) -> float | None:
    """Ollama reports eval_duration in nanoseconds for the generated tokens."""
    if not eval_count or not eval_duration_ns:
        return None
    return eval_count / (eval_duration_ns / 1_000_000_000)


def stream_generate(base_url: str, model: str, prompt: str, timeout: float = 600) -> dict:
    """Send one prompt and return wall-clock times plus the final Ollama stats."""
    payload = json.dumps({"model": model, "prompt": prompt, "stream": True}).encode()
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()
    first_token_at = None
    final = None
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw in response:
            line = raw.decode("utf-8").strip()
            if not line:
                continue
            event = json.loads(line)
            if first_token_at is None and event.get("response"):
                first_token_at = time.perf_counter()
            if event.get("done") is True:
                final = event
    finished = time.perf_counter()
    if final is None:
        raise RuntimeError(f"{model} ended without a done=true event")
    return {
        "model": model,
        "ttft_seconds": None if first_token_at is None else round(first_token_at - started, 3),
        "total_seconds": round(finished - started, 3),
        "tokens_per_second": None
        if (rate := tokens_per_second(final.get("eval_count"), final.get("eval_duration"))) is None
        else round(rate, 2),
        "eval_count": final.get("eval_count"),
    }


def main(argv: list[str]) -> int:
    models = argv[1:]
    if not models:
        print("Usage: python scripts/compare_models.py MODEL [MODEL ...]", file=sys.stderr)
        return 2
    base_url = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    print(f"{'model':<24} {'lang':<6} {'ttft_s':>8} {'tok/s':>8} {'total_s':>8}")
    for model in models:
        for lang, prompt in PROMPTS:
            try:
                row = stream_generate(base_url, model, prompt)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:200]
                print(f"{model:<24} {lang:<6} error {exc.code}: {detail}")
                continue
            except Exception as exc:
                print(f"{model:<24} {lang:<6} error: {exc}")
                continue
            rate = "" if row["tokens_per_second"] is None else f"{row['tokens_per_second']:.2f}"
            ttft = "" if row["ttft_seconds"] is None else f"{row['ttft_seconds']:.3f}"
            print(f"{model:<24} {lang:<6} {ttft:>8} {rate:>8} {row['total_seconds']:>8.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
