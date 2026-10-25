"""Run the demo questions against a live Talkback stack.

Usage, from the repository root, while the API is listening:

    python scripts/run_live_eval.py
    python scripts/run_live_eval.py --base-url http://127.0.0.1:8001 --runs 3

Each question is asked --runs times (default 3). The report shows the pass
rate and every cited page, including a page that appears on only one run.
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
SPANISH = re.compile(
    r"[áéíóúüñ¿¡]|\b(?:los|las|del|para|que|módulos?|modulos?|configurar|equipos)\b",
    re.IGNORECASE,
)


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
            expected = _expected_pages(case)
            if case["file"] not in files:
                problems.append(f"file was {sorted(files)}, expected {case['file']}")
            if not set(expected) & pages:
                label = " or ".join(expected)
                problems.append(f"page was {sorted(pages)}, expected {label}")
        for needle in case.get("answer_contains") or []:
            if needle.replace("−", "-") not in answer:
                problems.append(f"answer omitted {needle}")
        if case.get("language") == "es" and not SPANISH.search(answer):
            problems.append("answer was not in Spanish")
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


def _expected_pages(case: dict) -> list[str]:
    raw = case.get("pages", case.get("page"))
    if isinstance(raw, str):
        return [raw]
    return [str(page) for page in raw]


def cited_pages(events: list[dict]) -> list[str]:
    """Pages named on source cards, in the order the cards arrived."""
    pages = []
    for source in _sources(events):
        page = source.get("page")
        if page is None:
            continue
        label = str(page)
        if label not in pages:
            pages.append(label)
    return pages


def summarise(case: dict, runs: list[list[dict]]) -> tuple[int, list[str]]:
    """Pass count and the report lines for one question."""
    passed = 0
    seen: list[str] = []
    lines = []
    for index, events in enumerate(runs, start=1):
        problems = judge(case, events)
        if not problems:
            passed += 1
        for page in cited_pages(events):
            if page not in seen:
                seen.append(page)
        sources = _sources(events)
        where = ", ".join(
            f"{source.get('source')} p. {source.get('page')}" for source in sources
        )
        mark = "pass" if not problems else "fail"
        detail = where or "; ".join(_notices(events)) or "(no cards)"
        line = f"  {index} {mark}  {detail}"
        if problems:
            line += "  " + "; ".join(problems)
        lines.append(line)
    pages = ", ".join(seen) if seen else "none"
    header = f"{passed}/{len(runs)}  {case['id']}  pages seen: {pages}"
    return passed, [header, *lines]


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
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    missed = 0
    for case in load_cases(args.cases):
        runs = [ask(args.base_url, case["query"]) for _ in range(args.runs)]
        passed, lines = summarise(case, runs)
        missed += args.runs - passed
        print("\n".join(lines))
    return 1 if missed else 0


if __name__ == "__main__":
    raise SystemExit(main())
