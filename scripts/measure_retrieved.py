"""Time to the first retrieved event vs the first token (live engine).

Default (single run per case):
    docker cp scripts/measure_retrieved.py rag_api_service:/tmp/measure_retrieved.py
    docker cp tests/eval/questions.json rag_api_service:/tmp/questions.json
    docker exec -e PYTHONPATH=/app -w /app rag_api_service python /tmp/measure_retrieved.py

Cold/warm repeat (each case run twice, to show a caching/pool/limit setting's
effect on first-token latency):
    docker exec -e PYTHONPATH=/app -w /app rag_api_service \
        python /tmp/measure_retrieved.py --repeat 2

Main set only (`tests/eval/questions.json`, or `MAIN_CASES` to override the
path) — never reads `tests/eval/heldout.json`.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Callable

import config
import engine
from llm.client import wait_for_models
from retrieval.recall import search_text

MAIN = Path(os.environ.get("MAIN_CASES", "/tmp/questions.json"))
SAMPLE_IDS = [
    "bbc-loudness",
    "icmp-filter",
    "ansible-modules",
    "en-volume-drift",
    "en-playbook-name",
    "en-tcp-retransmit-filter",
]

Timing = tuple[float | None, float | None, int]
_LABELS = ("cold", "warm")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repeat",
        type=int,
        choices=(1, 2),
        default=1,
        help="Run each case once (default), or twice to report cold/warm timing.",
    )
    return parser.parse_args(argv)


def config_line(sample_size: int) -> str:
    return (
        f"rerank_candidates={config.rerank_candidates()} "
        f"retrieve_limit={config.retrieve_limit()} "
        f"hybrid={config.hybrid_bm25()} n={sample_size}"
    )


def timed(query: str) -> Timing:
    started = time.perf_counter()
    retrieved_at = None
    token_at = None
    count = 0
    for event in engine.iter_answer(query):
        kind = event["event"]
        if kind == "retrieved" and retrieved_at is None:
            retrieved_at = time.perf_counter() - started
            count = int(
                event["data"].get("count") or len(event["data"].get("sources") or [])
            )
        elif kind == "token" and token_at is None:
            token_at = time.perf_counter() - started
    return retrieved_at, token_at, count


def collect_runs(
    timed_fn: Callable[[str], Timing], query: str, repeat: int
) -> list[Timing]:
    """Run `timed_fn` against `query` `repeat` times. Run 0 is cold, run 1
    (when `repeat` is 2) is warm."""
    return [timed_fn(query) for _ in range(repeat)]


def format_row(case_id: str, runs: list[Timing]) -> str:
    if len(runs) == 1:
        retrieved, token, count = runs[0]
        r = "-" if retrieved is None else f"{retrieved:5.1f}s"
        t = "-" if token is None else f"{token:5.1f}s"
        return f"{case_id[:28]:28} {r:>9} {t:>10} {count:3}"
    parts = []
    for label, (retrieved, token, _count) in zip(_LABELS, runs):
        r = "-" if retrieved is None else f"{retrieved:.1f}s"
        t = "-" if token is None else f"{token:.1f}s"
        parts.append(f"retrieved_{label}={r} first_word_{label}={t}")
    count = runs[-1][2]
    return f"{case_id[:28]:28} " + " ".join(parts) + f" n={count}"


def summarize(results: list[list[Timing]]) -> list[str]:
    """One avg/lead line for a single run, or one avg/max line per cold/warm
    label."""
    if not results:
        return []
    repeat = len(results[0])
    lines = []
    for idx in range(repeat):
        retrieved_times = [r[idx][0] for r in results if r[idx][0] is not None]
        token_times = [r[idx][1] for r in results if r[idx][1] is not None]
        if not (retrieved_times and token_times):
            continue
        avg_r = sum(retrieved_times) / len(retrieved_times)
        avg_t = sum(token_times) / len(token_times)
        if repeat == 1:
            lines.append(
                f"avg retrieved={avg_r:.1f}s avg first_word={avg_t:.1f}s "
                f"lead={avg_t - avg_r:.1f}s"
            )
        else:
            label = _LABELS[idx]
            lines.append(
                f"avg {label} retrieved={avg_r:.1f}s "
                f"avg {label} first_word={avg_t:.1f}s "
                f"max {label} first_word={max(token_times):.1f}s"
            )
    return lines


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    engine.init()
    wait_for_models(180)
    cases = json.loads(MAIN.read_text(encoding="utf-8"))
    by_id = {case["id"]: case for case in cases}
    sample = [by_id[item] for item in SAMPLE_IDS if item in by_id]
    print(config_line(len(sample)), flush=True)
    if args.repeat == 1:
        print(f"{'id':28} {'retrieved':>9} {'first_word':>10} {'n':>3}", flush=True)
    results: list[list[Timing]] = []
    for case in sample:
        query = search_text(case, by_id)
        runs = collect_runs(timed, query, args.repeat)
        results.append(runs)
        print(format_row(case["id"], runs), flush=True)
    for line in summarize(results):
        print(line, flush=True)


if __name__ == "__main__":
    main()
