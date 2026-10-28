"""Shared helpers for unit tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def load_rerank_host():
    """Load scripts/rerank_host.py without installing it as a package."""
    path = Path(__file__).resolve().parents[2] / "scripts" / "rerank_host.py"
    spec = importlib.util.spec_from_file_location("rerank_host", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module
