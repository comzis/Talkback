#!/usr/bin/env python3
"""Soak the live API and report container RSS every 50 questions.

Uses the main eval questions, cycling until N queries are done. The host
embed/rerank service should be up so this measures API growth only.

    python scripts/soak_api_memory.py --base-url http://127.0.0.1:8001 --count 200
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
MAIN = ROOT / "tests" / "eval" / "questions.json"


def container_rss_mib(name: str) -> float:
    out = subprocess.check_output(
        ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", name],
        text=True,
    )
    used = out.split("/", 1)[0].strip()
    number = float("".join(ch for ch in used if ch.isdigit() or ch == "."))
    if used.lower().endswith("gib"):
        return number * 1024
    if used.lower().endswith("mib"):
        return number
    if used.lower().endswith("kib"):
        return number / 1024
    return number


def ask(base_url: str, query: str, timeout: float) -> dict:
    body = json.dumps({"query": query}).encode()
    request = urllib.request.Request(
        base_url.rstrip("/") + "/query",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def memory_snapshot(base_url: str) -> dict:
    request = urllib.request.Request(base_url.rstrip("/") + "/system/memory")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--container", default="rag_api_service")
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--questions", type=Path, default=MAIN)
    args = parser.parse_args()

    cases = json.loads(args.questions.read_text())
    queries = [case["query"] for case in cases]
    if not queries:
        print("no questions", file=sys.stderr)
        return 2

    samples = []

    def record(label: str, n: int) -> None:
        rss = container_rss_mib(args.container)
        try:
            snap = memory_snapshot(args.base_url)
        except Exception as exc:
            snap = {"error": str(exc)}
        row = {"at": label, "n": n, "rss_miB": round(rss, 1), "api": snap}
        samples.append(row)
        print(json.dumps(row), flush=True)

    record("start", 0)
    for i in range(1, args.count + 1):
        query = queries[(i - 1) % len(queries)]
        t0 = time.time()
        try:
            payload = ask(args.base_url, query, args.timeout)
            ok = bool(payload.get("response"))
            notice = payload.get("notice")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            ok = False
            notice = str(exc)
        print(
            f"q={i} ok={ok} {time.time() - t0:5.1f}s notice={notice!r} "
            f"query={query[:60]!r}",
            flush=True,
        )
        if i % 50 == 0 or i == args.count:
            record(f"after_{i}", i)
    print("--- summary ---", flush=True)
    for row in samples:
        print(
            f"{row['at']:10} n={row['n']:3} rss_miB={row['rss_miB']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
