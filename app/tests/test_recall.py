"""Recall accounting. The live index is not required."""

import json
from pathlib import Path

import config
from retrieval.recall import fact_pages, first_hit, recall_at, search_text
from retrieval.rerank import best_rerank_score, clears_threshold, model_cache_dir

ROOT = Path(__file__).resolve().parents[2]


def _cases(name: str) -> list[dict]:
    path = ROOT / "tests" / "eval" / name
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_case_records_whether_a_fact_page_exists():
    main = _cases("questions.json")
    held = _cases("heldout.json")
    empty = {case["id"] for case in main if not fact_pages(case)}
    assert empty == {"srt-outage", "bbc-radio-peak"}
    for case in main + held:
        assert "pages" in case or "page" in case
        if case["id"] not in empty:
            assert case.get("file")
            assert fact_pages(case)


def test_a_hit_is_the_expected_file_and_page():
    ranked = [("Other.pdf", "16"), ("Guide.pdf", "4"), ("Guide.pdf", "16")]
    assert first_hit(ranked, "Guide.pdf", ["16"]) == 3
    assert first_hit(ranked, "Guide.pdf", ["4", "6"]) == 2
    assert first_hit(ranked, "Missing.pdf", ["16"]) is None
    assert first_hit(ranked, "Guide.pdf", []) is None


def test_recall_counts_only_questions_that_have_a_fact_page():
    assert recall_at([1, 6, 21, None], 4) == (1, 4)
    assert recall_at([1, 6, 21, None], 8) == (2, 4)
    assert recall_at([1, 6, 21, None], 20) == (2, 4)


def test_the_rerank_threshold_keeps_main_set_library_questions():
    threshold = config.rerank_threshold()
    assert threshold == -7.5
    assert clears_threshold(-7.4, threshold)
    assert clears_threshold(-5.2, threshold)
    assert not clears_threshold(-8.0, threshold)
    kept = type("Node", (), {"metadata": {"rerank_score": -7.4}})()
    plain = type("Node", (), {"metadata": {}})()
    assert best_rerank_score([kept, plain]) == -7.4
    assert best_rerank_score([plain]) is None
    assert model_cache_dir().parts[-3:] == (".cache", "huggingface", "hub")


def test_a_follow_up_searches_the_previous_question():
    parent = {
        "id": "bbc-loudness",
        "query": "What audio loudness level do the BBC live technical delivery standards require?",
    }
    follow = {"id": "bbc-more", "continues": "bbc-loudness", "query": "Tell me more."}
    text = search_text(follow, {"bbc-loudness": parent})
    assert text == parent["query"]
    assert search_text(parent, {"bbc-loudness": parent}) == parent["query"]
