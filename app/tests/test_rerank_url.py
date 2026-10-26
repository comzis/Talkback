"""RERANK_URL sends pairs to the host. An empty value keeps the local model."""

import importlib.util
from pathlib import Path

import pytest


def _host_module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "rerank_host.py"
    spec = importlib.util.spec_from_file_location("rerank_host", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_device_prefers_cuda_then_mps_then_cpu():
    host = _host_module()
    assert host.pick_device(True, True) == "cuda"
    assert host.pick_device(False, True) == "mps"
    assert host.pick_device(False, False) == "cpu"


def test_blank_rerank_url_stays_in_process(monkeypatch):
    import config

    monkeypatch.delenv("RERANK_URL", raising=False)
    assert config.rerank_url() == ""


def test_remote_rerank_orders_scores_and_does_not_load_the_model(monkeypatch):
    import retrieval.rerank as rerank

    monkeypatch.setenv("RERANK_URL", "http://rerank.local")
    seen = {}

    def fake_post(url, body):
        seen["url"] = url
        seen["body"] = body
        return {"scores": [0.2, 3.5, -1.0], "device": "mps"}

    monkeypatch.setattr(rerank, "_post_scores", fake_post)
    monkeypatch.setattr(
        rerank,
        "_load",
        lambda: (_ for _ in ()).throw(AssertionError("local model loaded")),
    )

    class Node:
        def __init__(self, text):
            self.text = text
            self.metadata = {}
            self.score = None

        def get_content(self):
            return self.text

    ordered = rerank.rerank_nodes("query", [Node("a"), Node("b"), Node("c")])
    assert [node.get_content() for node in ordered] == ["b", "a", "c"]
    assert ordered[0].metadata["rerank_score"] == 3.5
    assert seen["url"] == "http://rerank.local"
    assert seen["body"]["passages"] == ["a", "b", "c"]
    assert seen["body"]["max_length"] == 512


def test_remote_rerank_rejects_a_short_score_list(monkeypatch):
    import retrieval.rerank as rerank

    monkeypatch.setenv("RERANK_URL", "http://rerank.local")
    monkeypatch.setattr(rerank, "_post_scores", lambda url, body: {"scores": [1.0]})

    class Node:
        def __init__(self):
            self.metadata = {}

        def get_content(self):
            return "a"

    with pytest.raises(RuntimeError):
        rerank.rerank_nodes("query", [Node(), Node()])
