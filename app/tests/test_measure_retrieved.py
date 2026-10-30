"""Pure logic in scripts/measure_retrieved.py: arg parsing, cold/warm run
splitting, row formatting, and summarizing. No live engine involved."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("torch")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import measure_retrieved as mr  # noqa: E402


def test_parse_args_defaults_to_repeat_one():
    args = mr.parse_args([])
    assert args.repeat == 1


def test_parse_args_accepts_repeat_two():
    args = mr.parse_args(["--repeat", "2"])
    assert args.repeat == 2


def test_parse_args_rejects_other_repeat_values():
    with pytest.raises(SystemExit):
        mr.parse_args(["--repeat", "3"])


def test_collect_runs_single_call_for_default_repeat():
    calls = []

    def fake_timed(query):
        calls.append(query)
        return (1.0, 2.0, 3)

    runs = mr.collect_runs(fake_timed, "q", repeat=1)
    assert runs == [(1.0, 2.0, 3)]
    assert calls == ["q"]


def test_collect_runs_calls_twice_for_repeat_two_cold_then_warm():
    results = iter([(2.0, 4.0, 3), (0.5, 1.0, 3)])

    def fake_timed(query):
        return next(results)

    runs = mr.collect_runs(fake_timed, "q", repeat=2)
    assert runs == [(2.0, 4.0, 3), (0.5, 1.0, 3)]


def test_format_row_single_run_matches_legacy_columns():
    row = mr.format_row("bbc-loudness", [(1.2, 3.4, 5)])
    assert row == f"{'bbc-loudness':28} {'1.2s':>9} {'3.4s':>10} {5:3}"


def test_format_row_single_run_renders_missing_events_as_dash():
    row = mr.format_row("icmp-filter", [(None, None, 0)])
    assert "-" in row
    assert row.split()[1] == "-"


def test_format_row_cold_warm_shows_both_labels():
    row = mr.format_row("ansible-modules", [(2.0, 4.0, 3), (0.5, 1.0, 3)])
    assert "retrieved_cold=2.0s" in row
    assert "first_word_cold=4.0s" in row
    assert "retrieved_warm=0.5s" in row
    assert "first_word_warm=1.0s" in row
    assert "n=3" in row


def test_summarize_empty_results_is_empty():
    assert mr.summarize([]) == []


def test_summarize_single_run_reports_lead():
    results = [[(1.0, 3.0, 2)], [(2.0, 5.0, 2)]]
    lines = mr.summarize(results)
    assert len(lines) == 1
    assert "avg retrieved=1.5s" in lines[0]
    assert "avg first_word=4.0s" in lines[0]
    assert "lead=2.5s" in lines[0]


def test_summarize_cold_warm_reports_one_line_per_label():
    results = [
        [(2.0, 4.0, 3), (0.5, 1.0, 3)],
        [(3.0, 6.0, 3), (1.0, 2.0, 3)],
    ]
    lines = mr.summarize(results)
    assert len(lines) == 2
    assert "avg cold retrieved=2.5s" in lines[0]
    assert "avg cold first_word=5.0s" in lines[0]
    assert "max cold first_word=6.0s" in lines[0]
    assert "avg warm retrieved=0.8s" in lines[1]
    assert "avg warm first_word=1.5s" in lines[1]
    assert "max warm first_word=2.0s" in lines[1]


def test_config_line_reports_active_settings(monkeypatch):
    monkeypatch.setattr(mr.config, "rerank_candidates", lambda: 40)
    monkeypatch.setattr(mr.config, "retrieve_limit", lambda: 6)
    monkeypatch.setattr(mr.config, "hybrid_bm25", lambda: True)
    line = mr.config_line(5)
    assert line == "rerank_candidates=40 retrieve_limit=6 hybrid=True n=5"


def test_sample_ids_keeps_committed_cases_and_adds_new_one():
    original = {
        "bbc-loudness",
        "icmp-filter",
        "ansible-modules",
        "en-volume-drift",
        "en-playbook-name",
    }
    assert original.issubset(set(mr.SAMPLE_IDS))
    assert "en-tcp-retransmit-filter" in mr.SAMPLE_IDS


def test_never_reads_heldout_set():
    import ast
    import inspect

    source = inspect.getsource(mr)
    module = ast.parse(source)
    module.body = [node for node in module.body if not isinstance(node, ast.Expr)]
    code_only = ast.unparse(module)
    assert "heldout" not in code_only.lower()
