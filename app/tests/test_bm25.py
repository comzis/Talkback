"""BM25 hybrid helpers."""

import pytest

pytest.importorskip("rank_bm25")


def test_tokenize_keeps_alnum_words():
    from retrieval.bm25 import _tokenize

    assert _tokenize("LUFS ±1.0 and icmp.type") == [
        "lufs",
        "and",
        "icmp",
        "type",
    ]


def test_hybrid_bm25_defaults_off(monkeypatch):
    import config

    monkeypatch.delenv("HYBRID_BM25", raising=False)
    assert config.hybrid_bm25() is False
    monkeypatch.setenv("HYBRID_BM25", "true")
    assert config.hybrid_bm25() is True
