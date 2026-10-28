"""RERANK_URL sends pairs to the host. An empty value keeps the local model."""

import pytest

from support import load_rerank_host
import state


@pytest.fixture(autouse=True)
def _process():
    state.reset_for_tests()
    state.activate()
    yield
    state.reset_for_tests()


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


def test_unreachable_host_raises_search_unavailable(monkeypatch, caplog):
    import retrieval.rerank as rerank
    from store.search_errors import SearchUnavailable

    monkeypatch.setenv("RERANK_URL", "http://rerank.local")
    state.get().rerank_host_warning_logged = False
    monkeypatch.setattr(
        rerank,
        "_post_scores",
        lambda url, body: (_ for _ in ()).throw(rerank.HostUnreachable("down")),
    )
    monkeypatch.setattr(
        rerank,
        "_local_scores",
        lambda query, passages, limit: (_ for _ in ()).throw(
            AssertionError("local model used")
        ),
    )

    class Node:
        def __init__(self):
            self.metadata = {}
            self.score = None

        def get_content(self):
            return "passage"

    with caplog.at_level("WARNING"):
        with pytest.raises(SearchUnavailable, match="host reranker is down"):
            rerank.rerank_nodes("query", [Node()])
    warnings = [record for record in caplog.records if "unreachable" in record.message]
    assert len(warnings) == 1


def test_active_rerank_reports_a_down_host_as_unavailable(monkeypatch):
    import retrieval.rerank as rerank

    monkeypatch.setenv("RERANK_URL", "http://rerank.local")
    state.get().rerank_host_warning_logged = False
    monkeypatch.setattr(rerank, "_host_health", lambda url: None)
    report = rerank.active_rerank()
    assert report["mode"] == "unavailable"
    assert report["host"] == "unreachable"
    again = rerank.active_rerank()
    assert again["mode"] == "unavailable"


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
