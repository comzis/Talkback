"""Report-only sensitivity scan for a pilot folder."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "sensitivity"
SCRIPT = ROOT / "scripts" / "sensitivity_scan.py"


def test_fixture_reports_secrets_and_skips_clean_text():
    sys.path.insert(0, str(ROOT / "scripts"))
    from sensitivity_scan import scan_folder

    reports = {item["path"]: item["hits"] for item in scan_folder(FIXTURE)}
    assert "clean.txt" not in reports
    leaky = reports["leaky.env"]
    assert leaky["api_key"] >= 1
    assert leaky["password"] >= 1
    assert leaky["aws_key"] >= 1
    assert leaky["email"] >= 1
    assert leaky["ipv4"] >= 1
    assert leaky["mac"] >= 1
    assert leaky["phone"] >= 1
    assert reports["key.pem"]["private_key"] >= 1


def test_sensitivity_cli_json():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(FIXTURE), "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    paths = {item["path"] for item in data["files"]}
    assert "leaky.env" in paths
    assert "key.pem" in paths
    assert "clean.txt" not in paths
