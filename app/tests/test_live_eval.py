"""The live demo questions judge a saved transcript without calling the stack."""

import importlib.util
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[2] / "scripts" / "run_live_eval.py"
spec = importlib.util.spec_from_file_location("run_live_eval", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def _token(text: str) -> dict:
    return {"event": "token", "data": {"text": text}}


def _source(file_name: str, page: str) -> dict:
    return {
        "event": "sources",
        "data": {"sources": [{"source": file_name, "page": page, "text": "x"}]},
    }


def test_cases_cover_the_four_demo_questions():
    cases = {case["id"]: case for case in runner.load_cases()}
    assert {
        "bbc-loudness",
        "icmp-filter",
        "ansible-modules",
        "srt-outage",
    } <= set(cases)
    assert cases["bbc-loudness"]["page"] == "16"
    assert cases["icmp-filter"]["page"] == "34"
    assert cases["ansible-modules"]["pages"] == ["4", "6"]
    assert cases["ansible-modules"]["language"] == "es"
    assert "ios_config" in cases["ansible-modules"]["answer_contains"]
    assert cases["srt-outage"]["path"] == "general"


def test_library_case_requires_the_expected_page():
    case = runner.load_cases()[0]
    events = [
        _token("The level is -23.0 LUFS, tolerance 1.0 LU."),
        _source("TechnicalDeliveryStandardsBBCLive.pdf", "4"),
        {"event": "done", "data": {}},
    ]
    assert runner.judge(case, events) == ["page was ['4'], expected 16"]


def test_ansible_accepts_page_4_or_6_in_spanish():
    case = runner.load_cases()[2]
    spanish = [
        _token("El módulo es ios_config."),
        _source("Ansible_Network_Automation_1744044240.pdf", "4"),
        {"event": "done", "data": {}},
    ]
    assert runner.judge(case, spanish) == []
    english = [
        _token("The module is ios_config."),
        _source("Ansible_Network_Automation_1744044240.pdf", "6"),
        {"event": "done", "data": {}},
    ]
    assert runner.judge(case, english) == ["answer was not in Spanish"]
    other_page = [
        _token("El módulo es ios_config."),
        _source("Ansible_Network_Automation_1744044240.pdf", "5"),
        {"event": "done", "data": {}},
    ]
    assert runner.judge(case, other_page) == ["page was ['5'], expected 4 or 6"]


def test_general_case_requires_the_notice_and_a_placeholder():
    case = runner.load_cases()[3]
    missing = [_token("The outage lasted 10 minutes because a fiber was cut.")]
    assert "missing the general-path notice" in runner.judge(case, missing)
    events = [
        {"event": "notice", "data": {"text": case["notice"]}},
        _token("Cause: [Insert Root Cause]. Next steps: [Insert Next Steps]."),
        {"event": "sources", "data": {"sources": []}},
        {"event": "done", "data": {}},
    ]
    assert runner.judge(case, events) == []


def test_repeated_runs_keep_every_cited_page():
    case = runner.load_cases()[2]
    page_six = [
        _token("El módulo es ios_config."),
        _source("Ansible_Network_Automation_1744044240.pdf", "6"),
    ]
    page_four = [
        _token("El módulo es ios_config."),
        _source("Ansible_Network_Automation_1744044240.pdf", "4"),
    ]
    passed, lines = runner.summarise(case, [page_four, page_six, page_six])
    assert passed == 3
    assert lines[0] == "3/3  ansible-modules  pages seen: 4, 6"
    assert "p. 4" in lines[1]
    assert "p. 6" in lines[2]


def test_follow_ups_continue_the_parent_question():
    cases = {case["id"]: case for case in runner.load_cases()}
    assert cases["bbc-more"]["continues"] == "bbc-loudness"
    assert cases["bbc-more-typo"]["query"] == "telll me more"
    assert cases["icmp-more"]["continues"] == "icmp-filter"
    assert cases["ansible-more"]["continues"] == "ansible-modules"
    assert cases["bbc-radio-peak"]["path"] == "uncovered"
    parent_events = [
        _token("Live loudness is -23.0 LUFS, tolerance 1.0 LU."),
        _source("TechnicalDeliveryStandardsBBCLive.pdf", "16"),
    ]
    history = runner.prior_turns(cases["bbc-loudness"], parent_events)
    assert history[0] == {
        "role": "user",
        "content": cases["bbc-loudness"]["query"],
    }
    assert history[1]["role"] == "assistant"
    assert "-23.0 LUFS" in history[1]["content"]


def test_true_peak_follow_up_requires_both_limits():
    case = {item["id"]: item for item in runner.load_cases()}["bbc-more-typo"]
    invented = [
        _token("The true peak is -1.0 dBTP."),
        {"event": "sources", "data": {"sources": []}},
    ]
    problems = runner.judge(case, invented)
    assert "no source card" in problems
    assert "answer omitted -3 dBTP" in problems
    held = [
        _token("Do not exceed -3 dBTP. The item fails above -1 dBTP."),
        _source("TechnicalDeliveryStandardsBBCLive.pdf", "16"),
    ]
    assert runner.judge(case, held) == []


def test_an_uncovered_question_must_not_invent_a_figure():
    case = {item["id"]: item for item in runner.load_cases()}["bbc-radio-peak"]
    invented = [
        _token("Radio requires -3 dBTP."),
        _source("TechnicalDeliveryStandardsBBCLive.pdf", "16"),
    ]
    problems = runner.judge(case, invented)
    assert "cited a document" in problems
    assert "invented a figure" in problems
    refusal = [
        _token("The library documents do not state a true-peak level for radio."),
        {"event": "sources", "data": {"sources": []}},
    ]
    assert runner.judge(case, refusal) == []
