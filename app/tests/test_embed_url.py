"""EMBED_URL sends texts to the host. An empty value keeps the local model."""

import pytest

from support import load_rerank_host


def _host_module():
    return load_rerank_host()


def test_blank_embed_url_stays_in_process(monkeypatch):
    import config

    monkeypatch.delenv("EMBED_URL", raising=False)
    assert config.embed_url() == ""


def test_active_embed_reports_a_down_host_as_container(monkeypatch):
    import store.host_embed as host_embed

    monkeypatch.setenv("EMBED_URL", "http://embed.local")
    host_embed._host_warning_logged = False
    monkeypatch.setattr(host_embed, "_host_health", lambda url: None)
    report = host_embed.active_embed()
    assert report["mode"] == "container"
    assert report["host"] == "unreachable"


def test_active_embed_reports_the_host_device(monkeypatch):
    import store.host_embed as host_embed

    monkeypatch.setenv("EMBED_URL", "http://embed.local")
    monkeypatch.setattr(
        host_embed,
        "_host_health",
        lambda url: {"device": "mps", "embed_device": "mps", "embed_loaded": True},
    )
    report = host_embed.active_embed()
    assert report == {
        "mode": "host",
        "device": "mps",
        "url": "http://embed.local",
        "host": "reachable",
        "embed_loaded": True,
    }


def test_host_embed_batch_posts_prepared_texts(monkeypatch):
    pytest.importorskip("llama_index")
    import store.host_embed as host_embed

    monkeypatch.setenv("EMBED_URL", "http://embed.local")
    monkeypatch.setenv("EMBED_MODEL", "BAAI/bge-m3")
    seen = {}

    def fake_post(url, texts):
        seen["url"] = url
        seen["texts"] = texts
        return {
            "embeddings": [[0.1, 0.2], [0.3, 0.4]],
            "device": "mps",
        }

    monkeypatch.setattr(host_embed, "_post_embeddings", fake_post)
    model = host_embed.build_embed_model()
    vectors = model.get_text_embedding_batch(["a", "b"])
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert seen["url"] == "http://embed.local"
    assert seen["texts"] == ["a", "b"]


def test_unreachable_host_falls_back_once(monkeypatch, caplog):
    pytest.importorskip("llama_index")
    import store.host_embed as host_embed

    monkeypatch.setenv("EMBED_URL", "http://embed.local")
    host_embed._host_warning_logged = False
    monkeypatch.setattr(
        host_embed,
        "_post_embeddings",
        lambda url, texts: (_ for _ in ()).throw(host_embed.HostUnreachable("down")),
    )

    class Local:
        def get_text_embedding_batch(self, texts):
            return [[1.0] for _ in texts]

        def get_query_embedding(self, text):
            return [1.0]

    model = host_embed.build_embed_model()
    model._local = Local()

    with caplog.at_level("WARNING"):
        first = model.get_text_embedding_batch(["a"])
        second = model.get_text_embedding_batch(["b"])
    assert first == [[1.0]]
    assert second == [[1.0]]
    warnings = [record for record in caplog.records if "unreachable" in record.message]
    assert len(warnings) == 1


def test_host_module_still_prefers_cuda_then_mps():
    host = _host_module()
    assert host.pick_device(True, True) == "cuda"
    assert host.pick_device(False, True) == "mps"
