"""Unit tests stay on the similarity path. They do not download the reranker."""

import os
import sys
from pathlib import Path

os.environ["RERANK"] = "false"
# Sibling helpers (support.py) resolve when tests are mounted away from PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parent))
