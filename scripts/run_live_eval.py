"""Run the demo questions against a live Talkback stack.

Usage, from the repository root, while the API is listening:

    python scripts/run_live_eval.py
    python scripts/run_live_eval.py --base-url http://127.0.0.1:8001

The questions and the facts they must contain are tests/eval/questions.json.
This does not start the stack and does not load a model itself.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "eval" / "questions.json"
PLACEHOLDER = re.compile(r"\[[^\[\]]{2,}\]")


def load_cases(path: Path = CASES) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_sse(body: str) -> list[dict]:
    events = []
    pending = body
    while "\n\n" in pending:
        block, pending = pending.split("\n\n", 1)
        event = "message"
        data = ""
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data += line[5:].strip()
        if data:
            events.append({"event": event, "data": json.loads(data)})
    return events


def _answer(events: list[dict]) -> str:
    text = "".join(
        event["data"].get("text", "") for event in events if event["event"] == "token"
    )
    return text.replace("−", "-").replace("–", "-")


def _sources(events: list[dict]) -> list[dict]:
    found = []
    for event in events:
        if event["event"] == "sources":
            found.extend(event["data"].get("sources") or [])
    return found


def _notices(events: list[dict]) -> list[str]:
    return [
        event["data"].get("text", "") for event in events if event["event"] == "notice"
    ]


def judge(case: dict, events: list[dict]) -> list[str]:
    """Return the facts that failed. An empty list means the case passed."""
    problems = []
    answer = _answer(events)
    sources = _sources(events)
    notices = _notices(events)
    if case["path"] == "library":
        if case.get("notice") and case["notice"] in notices:
            problems.append("took the general path")
        if not sources:
            problems.append("no source card")
        else:
            files = {source.get("source") or source.get("path") for source in sources}
            pages = {str(source.get("page")) for source in sources}
            if case["file"] not in files:
                problems.append(f"file was {sorted(files)}, expected {case['file']}")
            if case["page"] not in pages:
                problems.append(f"page was {sorted(pages)}, expected {case['page']}")
        for needle in case.get("answer_contains") or []:
            if needle.replace("−", "-") not in answer:
                problems.append(f"answer omitted {needle}")
    elif case["path"] == "general":
        if case["notice"] not in notices:
            problems.append("missing the general-path notice")
        if sources:
            problems.append("showed a library source")
        if case.get("placeholders") and not PLACEHOLDER.search(answer):
            problems.append("answer had no bracketed placeholder")
    else:
        problems.append(f"unknown path {case['path']}")
    return problems


def ask(base_url: str, query: str, timeout: float = 180) -> list[dict]:
    payload = json.dumps({"query": query, "history": []}).encode()
    request = urllib.request.Request(
        base_url.rstrip("/") + "/query/stream",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return parse_sse(response.read().decode())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--cases", type=Path, default=CASES)
    args = parser.parse_args()
    failed = 0
    for case in load_cases(args.cases):
        events = ask(args.base_url, case["query"])
        problems = judge(case, events)
        sources = _sources(events)
        where = ", ".join(
            f"{source.get('source')} p. {source.get('page')}" for source in sources
        )
        mark = "pass" if not problems else "fail"
        if problems:
            failed += 1
        print(f"{mark}  {case['id']}  {where or _notices(events)}")
        if problems:
            print("  " + "; ".join(problems))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
