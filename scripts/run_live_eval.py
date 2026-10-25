"""Run the demo questions against a live Talkback stack.

Usage, from the repository root, while the API is listening:

    python scripts/run_live_eval.py
    python scripts/run_live_eval.py --base-url http://127.0.0.1:8001 --runs 3

Each question is asked --runs times (default 3). The report shows the pass
rate and every cited page, including a page that appears on only one run.
tests/eval/heldout.json is a separate set. Score it, and do not change a
rule because of those results. This does not start the stack and does not
load a model itself.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "eval" / "questions.json"
PLACEHOLDER = re.compile(r"\[[^\[\]]{2,}\]")
FIGURE = re.compile(
    r"[-−–]?\d+(?:[.,]\d+)?\s*(?:dBTP|LUFS|LKFS|dBFS|LU)\b",
    re.IGNORECASE,
)
SPANISH = re.compile(
    r"[áéíóúüñ¿¡]|\b(?:los|las|del|para|que|módulos?|modulos?|configurar|equipos)\b",
    re.IGNORECASE,
)
FRENCH = re.compile(
    r"[àâçéèêëïîôùûüœ]|\b(?:les|des|une|dans|avec|filtre|détails|details|plus de)\b",
    re.IGNORECASE,
)
NOT_COVERED = re.compile(
    r"not in the (?:documents|library|excerpts)|"
    r"does not cover|do not cover|not covered|"
    r"do not (?:state|include|contain)|does not (?:state|include|contain)|"
    r"ne couvre pas|pas dans les documents|ne contient pas|"
    r"no cubre|no está en los documentos|no contiene|"
    r"ne portent pas sur|no trata de",
    re.IGNORECASE,
)
_UNIT = re.compile(r"(\d)\s*(dBTP|LUFS|LKFS|dBFS|LU)\b", re.IGNORECASE)


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


def _fold(text: str) -> str:
    """Make minus signs and unit spacing comparable across replies."""
    folded = text.replace("−", "-").replace("–", "-")
    return _UNIT.sub(r"\1 \2", folded)


def _answer(events: list[dict]) -> str:
    text = "".join(
        event["data"].get("text", "") for event in events if event["event"] == "token"
    )
    return _fold(text)


def prior_turns(parent: dict, events: list[dict]) -> list[dict]:
    """The parent question and its reply, as the next request's history."""
    return [
        {"role": "user", "content": parent["query"]},
        {"role": "assistant", "content": _answer(events)[:400]},
    ]


def _sources(events: list[dict]) -> list[dict]:
    found = []
    for event in events:
        if event["event"] == "sources":
            found.extend(event["data"].get("sources") or [])
    return found


def _footnote(events: list[dict]) -> str:
    return "\n".join(
        event["data"].get("text", "")
        for event in events
        if event["event"] == "footnote"
    )


def _notices(events: list[dict]) -> list[str]:
    return [
        event["data"].get("text", "") for event in events if event["event"] == "notice"
    ]


def _mentions(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE) is not None


def _split_sentences(text: str) -> list[str]:
    return [
        part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()
    ]


def _has_label(text: str, labels: list[str]) -> bool:
    return any(_mentions(text, label) for label in labels)


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


def _uncovered_problems(case: dict, shown: str, sources: list[dict]) -> list[str]:
    """Score a question the library does not answer.

    A figure is allowed when the reply says the subject is not covered and the
    sentence labels that figure as another medium, such as television. A figure
    stated as the subject's own value fails.
    """
    labels = [str(label) for label in case.get("figure_labels") or []]
    subject = str(case.get("gap_about") or "")
    if not labels:
        problems = []
        if FIGURE.search(shown):
            problems.append("invented a figure")
        elif sources and not NOT_COVERED.search(shown):
            problems.append("cited a document without saying it is not covered")
        return problems
    problems = []
    previous = ""
    for sentence in _split_sentences(shown):
        if not FIGURE.search(sentence):
            previous = sentence
            continue
        labelled = _has_label(sentence, labels) or (
            _has_label(previous, labels)
            and not (subject and _mentions(sentence, subject))
        )
        claims_subject = (
            subject
            and _mentions(sentence, subject)
            and not NOT_COVERED.search(sentence)
        )
        if claims_subject or (
            subject and _mentions(sentence, subject) and not labelled
        ):
            problems.append(f"presented a figure as the {subject} value")
        elif not labelled:
            problems.append("figure was not labelled as " + " / ".join(labels))
        previous = sentence
    says_gap = bool(NOT_COVERED.search(shown)) and (
        not subject or _mentions(shown, subject)
    )
    if not says_gap:
        if sources and not FIGURE.search(shown):
            problems.append("cited a document without saying it is not covered")
        elif FIGURE.search(shown) and not any(
            item.startswith("presented a figure") for item in problems
        ):
            problems.append("did not say the documents do not cover it")
    return _unique(problems)


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
            if _fold(needle) not in answer:
                problems.append(f"answer omitted {needle}")
        for group in case.get("answer_any_of") or []:
            if not any(_fold(needle) in answer for needle in group):
                problems.append("answer omitted one of " + " / ".join(group))
        cards = _fold(" ".join(source.get("text") or "" for source in sources))
        for needle in case.get("card_contains") or []:
            if _fold(needle) not in cards:
                problems.append(f"source card omitted {needle}")
        if case.get("language") == "es" and not SPANISH.search(answer):
            problems.append("answer was not in Spanish")
        if case.get("language") == "fr" and not FRENCH.search(answer):
            problems.append("answer was not in French")
    elif case["path"] == "uncovered":
        shown = _fold(answer + "\n" + _footnote(events))
        problems.extend(_uncovered_problems(case, shown, sources))
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
            if case.get("path") == "uncovered":
                preview = " ".join(_answer(events).split())
                note = " ".join(_footnote(events).split())
                if note:
                    preview = f"{preview} [footnote: {note}]"
                line += "  answer: " + preview[:500]
        lines.append(line)
    pages = ", ".join(seen) if seen else "none"
    header = f"{passed}/{len(runs)}  {case['id']}  pages seen: {pages}"
    return passed, [header, *lines]


def ask(
    base_url: str,
    query: str,
    history: list[dict] | None = None,
    timeout: float = 180,
) -> tuple[list[dict], float | None]:
    """Return the events and the seconds until the first token event."""
    payload = json.dumps({"query": query, "history": history or []}).encode()
    request = urllib.request.Request(
        base_url.rstrip("/") + "/query/stream",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()
    first: float | None = None
    body = bytearray()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        while True:
            part = response.read(512)
            if not part:
                break
            body.extend(part)
            if first is None and b"event: token" in body:
                first = time.perf_counter() - started
    return parse_sse(body.decode()), first


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument(
        "--id", action="append", default=[], help="Run only these case ids"
    )
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    missed = 0
    cases = load_cases(args.cases)
    if args.id:
        wanted = set(args.id)
        cases = [case for case in cases if case["id"] in wanted]
        missing = wanted - {case["id"] for case in cases}
        if missing:
            parser.error("unknown case id: " + ", ".join(sorted(missing)))
    by_id = {case["id"]: case for case in cases}
    for case in cases:
        results = []
        for _ in range(args.runs):
            history = []
            parent_id = case.get("continues")
            if parent_id:
                parent = by_id[parent_id]
                parent_events, _parent_first = ask(args.base_url, parent["query"])
                history = prior_turns(parent, parent_events)
            results.append(ask(args.base_url, case["query"], history))
        runs = [events for events, _first in results]
        firsts = [first for _events, first in results]
        passed, lines = summarise(case, runs)
        missed += args.runs - passed
        shown = ", ".join(
            "n/a" if first is None else f"{first:.1f}s" for first in firsts
        )
        lines.insert(1, f"  first word {shown}")
        print("\n".join(lines))
    return 1 if missed else 0


if __name__ == "__main__":
    raise SystemExit(main())
