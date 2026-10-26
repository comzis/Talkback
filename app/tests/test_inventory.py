"""Library inventory report for a pilot folder."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "inventory"
DEMO = Path("/Users/comzis/TalkbackDemo")
SCRIPT = ROOT / "scripts" / "inventory.py"


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
    if not DEMO.is_dir():
        return
    data = _run(DEMO)
    assert data["file_count"] == 3
    assert data["scan_pdfs"] == []
    names = {item["path"] for item in data["index"]}
    assert "TechnicalDeliveryStandardsBBCLive.pdf" in names
    assert "Ansible_Network_Automation_1744044240.pdf" in names
    assert "Traffic_analysis_with_wireshark_1746771119.pdf" in names
    assert data["index_poorly"] == []
    assert data["skip"] == []
