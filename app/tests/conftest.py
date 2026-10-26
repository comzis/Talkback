"""Unit tests stay on the similarity path. They do not download the reranker."""

import os

os.environ["RERANK"] = "false"
