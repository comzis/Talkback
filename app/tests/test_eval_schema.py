"""Schema checks for the main and held-out eval files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "tests" / "eval" / "questions.json"
HELD = ROOT / "tests" / "eval" / "heldout.json"
HELD_HASH = ROOT / "tests" / "eval" / "heldout.sha256"

_REQUIRED = {"id", "query", "path"}
_PATHS = {"library", "uncovered", "general"}


def _load(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    return data


def _check_case(case: dict, *, allow_known: bool) -> None:
    missing = _REQUIRED - set(case)
    assert not missing, f"{case.get('id')}: missing {sorted(missing)}"
    assert case["path"] in _PATHS, f"{case['id']}: bad path {case['path']}"
    if case["path"] == "library":
        assert case.get("file"), f"{case['id']}: library case needs file"
        assert case.get("page") is not None or case.get("pages") is not None, (
            f"{case['id']}: library case needs page or pages"
        )
    if "known" in case and not allow_known:
        raise AssertionError(f"{case['id']}: known is only allowed on the main set")
    if "continues" in case:
        assert isinstance(case["continues"], str) and case["continues"]


def test_main_and_heldout_schema_and_ids():
    main = _load(MAIN)
    held = _load(HELD)
    main_ids = [case["id"] for case in main]
    held_ids = [case["id"] for case in held]
    assert len(main_ids) == len(set(main_ids)), "duplicate id in questions.json"
    assert len(held_ids) == len(set(held_ids)), "duplicate id in heldout.json"
    overlap = set(main_ids) & set(held_ids)
    assert not overlap, f"id overlap between main and held-out: {sorted(overlap)}"
    for case in main:
        _check_case(case, allow_known=True)
    for case in held:
        _check_case(case, allow_known=False)
    continues = {case["continues"] for case in main if case.get("continues")} | {
        case["continues"] for case in held if case.get("continues")
    }
    known_ids = set(main_ids) | set(held_ids)
    assert continues <= known_ids, (
        f"continues points outside the sets: {continues - known_ids}"
    )


def test_heldout_file_hash_is_frozen():
    recorded = HELD_HASH.read_text(encoding="utf-8").strip().split()[0]
    digest = hashlib.sha256(HELD.read_bytes()).hexdigest()
    assert digest == recorded, (
        "heldout.json changed. If the move is intentional, update "
        "tests/eval/heldout.sha256 after review. Do not edit held-out to "
        "match a model answer."
    )
