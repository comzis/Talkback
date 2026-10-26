"""CSV authoring template converts to eval JSON."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "tests" / "eval" / "questions.template.csv"
SCRIPT = ROOT / "scripts" / "csv_to_eval.py"


def test_template_converts_main_and_heldout_rows():
    sys.path.insert(0, str(ROOT / "scripts"))
    from csv_to_eval import convert

    main = {case["id"]: case for case in convert(TEMPLATE, which="main")}
    held = {case["id"]: case for case in convert(TEMPLATE, which="heldout")}
    assert main["ex-loudness"]["page"] == "16"
    assert main["ex-loudness"]["answer_any_of"][0] == ["-23.0 LUFS", "-23 LUFS"]
    assert main["ex-playbook"]["answer_any_of"] == [["playbook", "Playbook"]]
    assert main["ex-radio"]["path"] == "uncovered"
    assert main["ex-radio"]["gap_about"] == "radio"
    assert main["ex-radio"]["figure_labels"] == ["television", "tv"]
    assert main["ex-srt"]["placeholders"] is True
    assert "ex-held-filter" not in main
    assert held["ex-held-filter"]["language"] == "fr"
    assert held["ex-held-filter"]["card_contains"] == [
        "icmp.type == 3 && icmp.code == 2"
    ]


def test_csv_to_eval_cli():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(TEMPLATE), "--set", "main"],
        check=True,
        capture_output=True,
        text=True,
    )
    cases = json.loads(result.stdout)
    assert {case["id"] for case in cases} == {
        "ex-loudness",
        "ex-playbook",
        "ex-radio",
        "ex-srt",
    }
