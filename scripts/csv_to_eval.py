"""Convert an authoring CSV into Talkback eval JSON.

Usage, from the repository root:

    python scripts/csv_to_eval.py tests/eval/questions.template.csv
    python scripts/csv_to_eval.py filled.csv -o /tmp/questions.json --set main
    python scripts/csv_to_eval.py filled.csv -o /tmp/heldout.json --set heldout

See docs/eval-authoring.md for the column meanings. This does not call the API.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def _split_pipe(raw: str) -> list[str]:
    return [part.strip() for part in (raw or "").split("|") if part.strip()]


def _split_facts(raw: str) -> list[list[str]]:
    """Semicolon separates facts; pipe separates alternative phrasings."""
    facts = []
    for group in (raw or "").split(";"):
        options = _split_pipe(group)
        if options:
            facts.append(options)
    return facts


def _truthy(raw: str) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes", "y"}


def _bucket(row: dict) -> str:
    return (row.get("set") or "").strip().lower().replace("held-out", "heldout")


def row_to_case(row: dict) -> dict:
    case: dict = {
        "id": (row.get("id") or "").strip(),
        "query": (row.get("query") or "").strip(),
        "path": (row.get("path") or "").strip(),
    }
    if not case["id"] or not case["query"] or not case["path"]:
        raise ValueError(f"id, query, and path are required: {row}")
    file_name = (row.get("file") or "").strip()
    if file_name:
        case["file"] = file_name
    pages = _split_pipe(row.get("pages") or "")
    if len(pages) == 1:
        case["page"] = pages[0]
    elif pages:
        case["pages"] = pages
    language = (row.get("language") or "").strip()
    if language:
        case["language"] = language
    contains = _split_pipe(row.get("answer_contains") or "")
    if contains:
        case["answer_contains"] = contains
    any_of = _split_facts(row.get("answer_any_of") or "")
    if any_of:
        case["answer_any_of"] = any_of
    cards = _split_pipe(row.get("card_contains") or "")
    if cards:
        case["card_contains"] = cards
    continues = (row.get("continues") or "").strip()
    if continues:
        case["continues"] = continues
    notice = (row.get("notice") or "").strip()
    if notice:
        case["notice"] = notice
    gap = (row.get("gap_about") or "").strip()
    if gap:
        case["gap_about"] = gap
    labels = _split_pipe(row.get("figure_labels") or "")
    if labels:
        case["figure_labels"] = labels
    if _truthy(row.get("placeholders") or ""):
        case["placeholders"] = True
    known = (row.get("known") or "").strip()
    if known:
        case["known"] = known
    return case


def convert(path: Path, which: str | None = None) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    cases = []
    for row in rows:
        if not any((value or "").strip() for value in row.values()):
            continue
        if which and _bucket(row) != which:
            continue
        cases.append(row_to_case(row))
    return cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument(
        "--set",
        choices=("main", "heldout"),
        help="Keep only this set column value",
    )
    args = parser.parse_args(argv)
    if not args.csv.is_file():
        print(f"CSV not found: {args.csv}", file=sys.stderr)
        return 1
    try:
        cases = convert(args.csv, which=args.set)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    text = json.dumps(cases, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
