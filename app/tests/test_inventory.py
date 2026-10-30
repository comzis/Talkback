"""Library inventory report for a pilot folder."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "inventory"
SCRIPT = ROOT / "scripts" / "inventory.py"

TALKBACK_DEMO_PDF_DIR = "TALKBACK_DEMO_PDF_DIR"


def _run(folder: Path) -> dict:
    sys.path.insert(0, str(ROOT / "scripts"))
    from inventory import inventory

    return inventory(folder)


def test_fixture_folder_groups_index_poor_and_skip():
    data = _run(FIXTURE)
    assert data["file_count"] == 9
    indexed = {item["path"] for item in data["index"]}
    poor = {item["path"] for item in data["index_poorly"]}
    skipped = {item["path"] for item in data["skip"]}
    assert indexed == {"guide.md", "notes.txt", "subdir/hello.pdf"}
    assert "scan.pdf" in poor
    assert "photo.png" in poor
    assert "sample.py" in poor
    assert ".hidden.txt" in skipped
    assert ".DS_Store" in skipped
    assert "binary.xyz" in skipped
    assert data["scan_pdfs"] == ["scan.pdf"]
    assert data["by_extension"][".pdf"] == 2


def test_inventory_cli_prints_json():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(FIXTURE), "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    assert data["file_count"] == 9


def test_demo_pdfs_index_well_when_present():
    """Opt-in: set TALKBACK_DEMO_PDF_DIR to a folder containing exactly the
    three named demo PDFs (and nothing else) to run this test. Unset, it
    reports as skipped rather than silently passing with no assertions run.
    """
    demo_dir = os.environ.get(TALKBACK_DEMO_PDF_DIR)
    if not demo_dir:
        pytest.skip(
            f"{TALKBACK_DEMO_PDF_DIR} is not set; skipping demo PDF inventory check"
        )
    data = _run(Path(demo_dir))
    assert data["file_count"] == 3
    assert data["scan_pdfs"] == []
    names = {item["path"] for item in data["index"]}
    assert "TechnicalDeliveryStandardsBBCLive.pdf" in names
    assert "Ansible_Network_Automation_1744044240.pdf" in names
    assert "Traffic_analysis_with_wireshark_1746771119.pdf" in names
    assert data["index_poorly"] == []
    assert data["skip"] == []
