#!/usr/bin/env python3
"""Compare Talkback chat models on the live stack.

For each model: select it, warm it, run main ×3 and held-out ×3 (unscoped and
scoped), and print pass rates plus first-sources / first-word / tok/s / memory.

Thinking is whatever the API sends (OLLAMA_THINK=false → Qwen false, gpt-oss low).

    python scripts/compare_talkback_models.py \\
        qwen3.8:27b gpt-oss:20b qwen3.5:9b
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_live_eval as evalmod  # noqa: E402

MAIN = ROOT / "tests" / "eval" / "questions.json"
HELD = ROOT / "tests" / "eval" / "heldout.json"


def stop_other_models(keep: str, candidates: list[str]) -> None:
    """Unload sibling compare models so memory and tok/s are not shared."""
    for name in candidates:
        if name == keep:
            continue
        try:
            subprocess.run(
                ["ollama", "stop", name],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            pass


def select_model(base_url: str, model: str) -> None:
    payload = json.dumps({"model": model}).encode()
    request = urllib.request.Request(
        base_url.rstrip("/") + "/llm/select",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.load(response)
    if body.get("model") != model and not str(body.get("model", "")).startswith(model):
        raise RuntimeError(f"select failed: {body}")


def ollama_memory_gib(model: str) -> float | None:
    try:
        raw = subprocess.check_output(["ollama", "ps"], text=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    for line in raw.splitlines()[1:]:
        if not line.strip():
            continue
        if line.split()[0] != model and not line.startswith(model):
            continue
        # NAME ID SIZE PROCESSOR CONTEXT ...
        parts = line.split()
        for index, part in enumerate(parts):
            if part.upper() in {"GB", "GIB"} and index > 0:
                try:
                    return float(parts[index - 1])
                except ValueError:
                    return None
            if part.lower().endswith("gb"):
                try:
                    return float(part[:-2])
                except ValueError:
                    return None
    return None


def sample_tok_s(base_url: str, queries: list[str]) -> float | None:
    """Rough decode rate from wall time and answer length (≈1 token / 4 chars)."""
    rates = []
    for query in queries:
        started = time.perf_counter()
        events, _retrieved, first = evalmod.ask(base_url, query, timeout=300)
        elapsed = time.perf_counter() - started
        answer = evalmod._answer(events)
        if first is None or elapsed <= first or not answer:
            continue
        gen = elapsed - first
        if gen <= 0:
            continue
        rates.append((len(answer) / 4) / gen)
    if not rates:
        return None
    return sum(rates) / len(rates)


def run_set(
    base_url: str,
    cases: list[dict],
    *,
    runs: int,
    scoped: bool,
) -> dict:
    by_id = {case["id"]: case for case in cases}
    passed = 0
    total = 0
    retrieved_times: list[float] = []
    token_times: list[float] = []
    lang_pass = {"fr": [0, 0], "es": [0, 0]}
    for case in cases:
        scope = case.get("file") if scoped and case.get("file") else None
        for _ in range(runs):
            history = []
            parent_id = case.get("continues")
            if parent_id:
                parent = by_id[parent_id]
                parent_scope = (
                    parent.get("file") if scoped and parent.get("file") else None
                )
                parent_events, _r, _t = evalmod.ask(
                    base_url, parent["query"], scope=parent_scope, timeout=300
                )
                history = evalmod.prior_turns(parent, parent_events)
            events, retrieved, first = evalmod.ask(
                base_url, case["query"], history, scope=scope, timeout=300
            )
            total += 1
            problems = evalmod.judge(case, events)
            if not problems:
                passed += 1
            if retrieved is not None:
                retrieved_times.append(retrieved)
            if first is not None:
                token_times.append(first)
            required = case.get("language")
            if required in lang_pass:
                lang_pass[required][1] += 1
                if not any(item.startswith("answer was not in") for item in problems):
                    lang_pass[required][0] += 1
            mark = "pass" if not problems else "fail"
            detail = "" if not problems else "  " + "; ".join(problems)
            print(
                f"  {case['id'][:28]:28} {mark} "
                f"src={'-' if retrieved is None else f'{retrieved:.1f}s'} "
                f"word={'-' if first is None else f'{first:.1f}s'}{detail}",
                flush=True,
            )
    return {
        "passed": passed,
        "total": total,
        "avg_retrieved": (
            sum(retrieved_times) / len(retrieved_times) if retrieved_times else None
        ),
        "avg_first_word": (
            sum(token_times) / len(token_times) if token_times else None
        ),
        "fr_lang": lang_pass["fr"],
        "es_lang": lang_pass["es"],
    }


def mean(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present) / len(present)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="+")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--restore", default="qwen3.8:27b")
    args = parser.parse_args()
    main_cases = evalmod.load_cases(MAIN)
    held_cases = evalmod.load_cases(HELD)
    sample_queries = [
        case["query"]
        for case in main_cases
        if case["id"]
        in {"bbc-loudness", "icmp-filter", "ansible-modules", "en-volume-drift"}
    ]
    rows = []
    try:
        for model in args.models:
            print(f"\n=== {model} ===", flush=True)
            stop_other_models(model, args.models)
            select_model(args.base_url, model)
            # Warm: one short library question so the model is resident.
            evalmod.ask(args.base_url, sample_queries[0], timeout=300)
            memory = ollama_memory_gib(model)
            print(f"memory_gib={memory}", flush=True)
            print("--- main unscoped ---", flush=True)
            main_u = run_set(args.base_url, main_cases, runs=args.runs, scoped=False)
            print("--- held-out unscoped ---", flush=True)
            held_u = run_set(args.base_url, held_cases, runs=args.runs, scoped=False)
            print("--- held-out scoped ---", flush=True)
            held_s = run_set(args.base_url, held_cases, runs=args.runs, scoped=True)
            tok = sample_tok_s(args.base_url, sample_queries)
            row = {
                "model": model,
                "main": f"{main_u['passed']}/{main_u['total']}",
                "held_unscoped": f"{held_u['passed']}/{held_u['total']}",
                "held_scoped": f"{held_s['passed']}/{held_s['total']}",
                "retrieved_s": mean(
                    [
                        main_u["avg_retrieved"],
                        held_u["avg_retrieved"],
                        held_s["avg_retrieved"],
                    ]
                ),
                "first_word_s": mean(
                    [
                        main_u["avg_first_word"],
                        held_u["avg_first_word"],
                        held_s["avg_first_word"],
                    ]
                ),
                "tok_s": tok,
                "memory_gib": memory,
                "fr_lang": f"{main_u['fr_lang'][0]}/{main_u['fr_lang'][1]}",
                "es_lang": f"{main_u['es_lang'][0]}/{main_u['es_lang'][1]}",
            }
            rows.append(row)
            print("ROW", json.dumps(row), flush=True)
    finally:
        if args.restore:
            print(f"\nRestoring {args.restore}", flush=True)
            try:
                stop_other_models(args.restore, list(args.models) + [args.restore])
                select_model(args.base_url, args.restore)
            except urllib.error.URLError as exc:
                print(f"restore failed: {exc}", flush=True)

    print(
        f"\n{'model':<16} {'main':>8} {'held_u':>8} {'held_s':>8} "
        f"{'src_s':>6} {'word_s':>7} {'tok/s':>6} {'GiB':>5} {'fr':>6} {'es':>6}"
    )
    for row in rows:
        src = "-" if row["retrieved_s"] is None else f"{row['retrieved_s']:.1f}"
        word = "-" if row["first_word_s"] is None else f"{row['first_word_s']:.1f}"
        rate = "-" if row["tok_s"] is None else f"{row['tok_s']:.1f}"
        mem = "-" if row["memory_gib"] is None else f"{row['memory_gib']:.0f}"
        print(
            f"{row['model']:<16} {row['main']:>8} {row['held_unscoped']:>8} "
            f"{row['held_scoped']:>8} {src:>6} {word:>7} {rate:>6} {mem:>5} "
            f"{row['fr_lang']:>6} {row['es_lang']:>6}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
