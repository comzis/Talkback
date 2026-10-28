"""RERANK_URL sends pairs to the host. An empty value keeps the local model."""

import pytest

from support import load_rerank_host


def _host_module():
    return load_rerank_host()


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


def test_unreachable_host_uses_the_container_and_warns_once(monkeypatch, caplog):
    import retrieval.rerank as rerank

    monkeypatch.setenv("RERANK_URL", "http://rerank.local")
    rerank._host_warning_logged = False
    monkeypatch.setattr(
        rerank,
        "_post_scores",
        lambda url, body: (_ for _ in ()).throw(rerank.HostUnreachable("down")),
    )
    monkeypatch.setattr(
        rerank, "_local_scores", lambda query, passages, limit: ([1.5], "cpu")
    )

    class Node:
        def __init__(self):
            self.metadata = {}
            self.score = None

        def get_content(self):
            return "passage"

    with caplog.at_level("WARNING"):
        first = rerank.rerank_nodes("query", [Node()])
        second = rerank.rerank_nodes("query", [Node()])
    assert first[0].metadata["rerank_score"] == 1.5
    assert second[0].metadata["rerank_score"] == 1.5
    warnings = [record for record in caplog.records if "unreachable" in record.message]
    assert len(warnings) == 1


def test_active_rerank_reports_a_down_host_as_container(monkeypatch):
    import retrieval.rerank as rerank

    monkeypatch.setenv("RERANK_URL", "http://rerank.local")
    rerank._host_warning_logged = False
    monkeypatch.setattr(rerank, "_host_health", lambda url: None)
    report = rerank.active_rerank()
    assert report["mode"] == "container"
    assert report["host"] == "unreachable"
    again = rerank.active_rerank()
    assert again["mode"] == "container"


def test_active_rerank_reports_the_host_device(monkeypatch):
    import retrieval.rerank as rerank

    monkeypatch.setenv("RERANK_URL", "http://rerank.local")
    monkeypatch.setattr(rerank, "_host_health", lambda url: {"device": "mps"})
    report = rerank.active_rerank()
    assert report == {
        "mode": "host",
        "device": "mps",
        "url": "http://rerank.local",
        "host": "reachable",
    }


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
