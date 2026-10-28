"""Time to the first retrieved event vs the first token (live engine).

docker cp scripts/measure_retrieved.py rag_api_service:/tmp/measure_retrieved.py
docker cp tests/eval/questions.json rag_api_service:/tmp/questions.json
docker exec -e PYTHONPATH=/app -w /app rag_api_service python /tmp/measure_retrieved.py
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

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
]


def timed(query: str) -> tuple[float | None, float | None, int]:
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


def main() -> None:
    engine.init()
    wait_for_models(180)
    cases = json.loads(MAIN.read_text(encoding="utf-8"))
    by_id = {case["id"]: case for case in cases}
    sample = [by_id[item] for item in SAMPLE_IDS if item in by_id]
    print(f"{'id':28} {'retrieved':>9} {'first_word':>10} {'n':>3}", flush=True)
    retrieved_times = []
    token_times = []
    for case in sample:
        query = search_text(case, by_id)
        retrieved, token, count = timed(query)
        if retrieved is not None:
            retrieved_times.append(retrieved)
        if token is not None:
            token_times.append(token)
        r = "-" if retrieved is None else f"{retrieved:5.1f}s"
        t = "-" if token is None else f"{token:5.1f}s"
        print(f"{case['id'][:28]:28} {r:>9} {t:>10} {count:3}", flush=True)
    if retrieved_times and token_times:
        print(
            f"avg retrieved={sum(retrieved_times) / len(retrieved_times):.1f}s "
            f"avg first_word={sum(token_times) / len(token_times):.1f}s "
            f"lead={sum(token_times) / len(token_times) - sum(retrieved_times) / len(retrieved_times):.1f}s",
            flush=True,
        )


if __name__ == "__main__":
    main()
