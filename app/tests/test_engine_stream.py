"""Library answers stream before the excerpt check, and keep the words already sent."""

import pytest

pytest.importorskip("torch")

import engine


def _events(monkeypatch, deltas, grounded, supported):
    monkeypatch.setattr(
        engine, "_stream_deltas", lambda prompt, temperature: iter(deltas)
    )
    monkeypatch.setattr(
        engine, "ground_library_reply", lambda answer, sources, query="": grounded
    )
    seen = {}

    def support(answer, sources):
        seen["answer"] = answer
        return supported

    monkeypatch.setattr(engine, "supporting_sources", support)
    monkeypatch.setattr(engine, "cited_source_indexes", lambda answer: [1])
    events = list(
        engine._stream_prompt(
            "prompt",
            0.1,
            [{"number": 1, "source": "a.pdf", "text": "alpha", "page": "1"}],
            query="Tell me more.",
        )
    )
    return events, seen


def test_a_changed_library_answer_stays_on_screen(monkeypatch):
    events, seen = _events(
        monkeypatch,
        ["The level ", "is -99 LUFS."],
        "The level is -23.0 LUFS.",
        [{"number": 1, "source": "a.pdf", "text": "alpha", "page": "1"}],
    )
    tokens = [event["data"]["text"] for event in events if event["event"] == "token"]
    assert tokens == ["The level ", "is -99 LUFS."]
    footnotes = [event for event in events if event["event"] == "footnote"]
    assert footnotes == [
        {"event": "footnote", "data": {"text": "The level is -23.0 LUFS."}}
    ]
    assert seen["answer"] == "The level is -23.0 LUFS."
    sources = [event for event in events if event["event"] == "sources"]
    assert sources[0]["data"]["sources"][0]["source"] == "a.pdf"


def test_an_uncovered_english_question_does_not_call_the_model(monkeypatch):
    def fail(prompt, temperature):
        raise AssertionError("the model should not be asked")

    monkeypatch.setattr(engine, "_stream_deltas", fail)
    events = list(
        engine._stream_prompt(
            "prompt",
            0.1,
            [
                {
                    "number": 1,
                    "source": "a.pdf",
                    "text": "Live peak is -3 dBTP.",
                    "page": "16",
                }
            ],
            query="What true-peak level does the BBC standard require for radio?",
        )
    )
    tokens = [event["data"]["text"] for event in events if event["event"] == "token"]
    assert tokens == ["The library does not cover that."]
    assert [event for event in events if event["event"] == "sources"] == [
        {"event": "sources", "data": {"sources": []}}
    ]


def test_an_unchanged_library_answer_has_no_footnote(monkeypatch):
    events, seen = _events(
        monkeypatch,
        ["The level is -23.0 LUFS."],
        "The level is -23.0 LUFS.",
        [{"number": 1, "source": "a.pdf", "text": "alpha", "page": "1"}],
    )
    assert [event["event"] for event in events if event["event"] == "footnote"] == []
    assert seen["answer"] == "The level is -23.0 LUFS."
