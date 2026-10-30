"""Library answers stream before the excerpt check, and keep the words already sent."""

import pytest

pytest.importorskip("torch")

import engine


def _events(monkeypatch, deltas, grounded, supported, dropped=()):
    monkeypatch.setattr(
        engine, "_stream_deltas", lambda prompt, temperature: iter(deltas)
    )
    monkeypatch.setattr(
        engine,
        "ground_library_reply",
        lambda answer, sources, query="": (grounded, list(dropped)),
    )
    seen = {}

    def support(answer, sources):
        seen["answer"] = answer
        return supported

    monkeypatch.setattr(engine, "supporting_sources", support)
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
        dropped=["The level is -99 LUFS."],
    )
    tokens = [event["data"]["text"] for event in events if event["event"] == "token"]
    assert tokens == ["The level ", "is -99 LUFS."]
    footnotes = [event for event in events if event["event"] == "footnote"]
    assert len(footnotes) == 1
    note = footnotes[0]["data"]["text"]
    assert "-23.0" not in note
    assert "excerpts" in note.lower() or "detail" in note.lower()
    assert seen["answer"] == "The level is -99 LUFS."
    sources = [event for event in events if event["event"] == "sources"]
    assert sources[0]["data"]["sources"][0]["source"] == "a.pdf"
    assert sources[0]["data"]["sources"][0]["used"] is True
    assert "text" in sources[0]["data"]["sources"][0]
    assert "text" in sources[0]["data"]


def test_a_french_question_still_calls_the_model(monkeypatch):
    called = {}

    def stream(prompt, temperature):
        called["yes"] = True
        yield "La sonie est -23.0 LUFS."

    monkeypatch.setattr(engine, "_stream_deltas", stream)
    monkeypatch.setattr(
        engine,
        "ground_library_reply",
        lambda answer, sources, query="": (answer, []),
    )
    monkeypatch.setattr(
        engine,
        "supporting_sources",
        lambda answer, sources: [
            {
                "number": 1,
                "source": "a.pdf",
                "text": "Live loudness is -23.0 LUFS.",
                "page": "16",
            }
        ],
    )
    events = list(
        engine._stream_prompt(
            "prompt",
            0.1,
            [
                {
                    "number": 1,
                    "source": "a.pdf",
                    "text": "Live loudness is -23.0 LUFS.",
                    "page": "16",
                }
            ],
            query="Quelle est la sonie exigée ?",
        )
    )
    assert called.get("yes") is True
    tokens = [event["data"]["text"] for event in events if event["event"] == "token"]
    assert tokens == ["La sonie est -23.0 LUFS."]


def test_no_surviving_citation_shows_the_outside_note(monkeypatch):
    events, _seen = _events(
        monkeypatch,
        ["Cause: [cause]. Next step: [next step]."],
        "Cause: [cause]. Next step: [next step].",
        [],
    )
    notices = [event["data"]["text"] for event in events if event["event"] == "notice"]
    assert notices == ["This answer is not from the documents and may not match them."]
    sources = [event for event in events if event["event"] == "sources"]
    assert sources[0]["data"]["sources"] == []


def test_an_unchanged_library_answer_has_no_footnote(monkeypatch):
    events, seen = _events(
        monkeypatch,
        ["The level is -23.0 LUFS."],
        "The level is -23.0 LUFS.",
        [{"number": 1, "source": "a.pdf", "text": "alpha", "page": "1"}],
    )
    assert [event["event"] for event in events if event["event"] == "footnote"] == []
    assert seen["answer"] == "The level is -23.0 LUFS."


def _drain(generator):
    """Collect yielded events and the generator's return value."""
    events = []
    try:
        while True:
            events.append(next(generator))
    except StopIteration as stop:
        return events, stop.value


def test_token_events_return_the_shown_text(monkeypatch):
    monkeypatch.setattr(
        engine, "_stream_deltas", lambda prompt, temperature: iter(["a ", "b"])
    )
    monkeypatch.setattr(engine, "take_stream_piece", lambda text: (text, "", False))
    events, shown = _drain(engine._iter_streamed_token_events("p", 0.1))
    assert [e["data"]["text"] for e in events] == ["a ", "b"]
    assert shown == "a b"


def test_token_events_flush_pending_text(monkeypatch):
    monkeypatch.setattr(
        engine, "_stream_deltas", lambda prompt, temperature: iter(["tail "])
    )
    monkeypatch.setattr(engine, "take_stream_piece", lambda text: ("", text, False))
    events, shown = _drain(engine._iter_streamed_token_events("p", None))
    assert [e["data"]["text"] for e in events] == ["tail "]
    assert shown == "tail"


def test_token_events_scrub_general_tail(monkeypatch):
    monkeypatch.setattr(
        engine, "_stream_deltas", lambda prompt, temperature: iter(["x", "y", "z"])
    )

    def piece(text):
        return ("", text, True) if text == "x" else (text, "", False)

    monkeypatch.setattr(engine, "take_stream_piece", piece)
    monkeypatch.setattr(engine, "scrub_general_figures", lambda text: text.upper())
    events, shown = _drain(engine._iter_streamed_token_events("p", None))
    assert [e["data"]["text"] for e in events] == ["XYZ"]
    assert shown == "XYZ"


def test_correction_note_none_when_nothing_dropped(monkeypatch):
    monkeypatch.setattr(
        engine,
        "ground_library_reply",
        lambda answer, sources, query="": (answer + " ", []),
    )
    assert engine._library_reply_and_correction("ok", [], "q") == ("ok", None)


def test_correction_note_when_something_dropped(monkeypatch):
    monkeypatch.setattr(
        engine,
        "ground_library_reply",
        lambda answer, sources, query="": ("fixed", ["bad"]),
    )
    reply, note = engine._library_reply_and_correction("bad", [], "q")
    assert reply == "fixed"
    assert note == engine.user_line("no_detail", "q")
    assert "fixed" not in note


def test_correction_note_empty_uses_no_detail_line(monkeypatch):
    monkeypatch.setattr(
        engine, "ground_library_reply", lambda answer, sources, query="": ("", ["bad"])
    )
    reply, note = engine._library_reply_and_correction("bad", [], "q")
    assert reply == ""
    assert note == engine.user_line("no_detail", "q")


def _tail(monkeypatch, used, note):
    source = {"number": 1, "source": "a.pdf", "text": "alpha", "page": "1"}
    monkeypatch.setattr(engine, "supporting_sources", lambda shown, sources: used)
    monkeypatch.setattr(
        engine, "_close_citations", lambda shown, supported, query="": supported
    )
    return list(engine._iter_library_stream_tail("shown", "reply", note, [source], "q"))


def test_tail_finalizes_citations_into_sources_text(monkeypatch):
    used = [{"number": 1, "source": "a.pdf", "text": "alpha", "page": "1"}]
    events = _tail(monkeypatch, used, None)
    assert [e["event"] for e in events] == ["sources", "done"]
    assert events[0]["data"]["sources"][0]["used"] is True
    assert "text" in events[0]["data"]


def test_tail_notice_and_footnote_when_nothing_cited(monkeypatch):
    events = _tail(monkeypatch, [], "fixed")
    assert [e["event"] for e in events] == ["footnote", "notice", "sources", "done"]
    assert events[0]["data"]["text"] == "fixed"
    assert events[2]["data"]["sources"] == []


def test_tail_shows_only_cited_candidates_numbered_to_match_the_text(monkeypatch):
    """The sources event must carry only the candidates the answer actually
    cited (c.pdf and e.pdf here, not a/b/d/f.pdf), numbered 1..n to match
    finalize_citations' renumbered markers in the displayed text exactly,
    with each excerpt windowed by display_excerpt and used explicitly True.
    """
    candidates = [
        {"number": 1, "source": "a.pdf", "text": "aaa", "page": "1"},
        {"number": 2, "source": "b.pdf", "text": "bbb", "page": "1"},
        {"number": 3, "source": "c.pdf", "text": "ccc", "page": "1"},
        {"number": 4, "source": "d.pdf", "text": "ddd", "page": "1"},
        {"number": 5, "source": "e.pdf", "text": "eee", "page": "1"},
        {"number": 6, "source": "f.pdf", "text": "fff", "page": "1"},
    ]
    # The model actually cited original candidates 3 and 5.
    shown = "Alpha fact [3]. Beta fact [5]."
    supported = [
        {"number": 3, "source": "c.pdf", "text": "ccc", "page": "1"},
        {"number": 5, "source": "e.pdf", "text": "eee", "page": "1"},
    ]
    monkeypatch.setattr(engine, "supporting_sources", lambda shown, sources: supported)
    monkeypatch.setattr(
        engine, "_close_citations", lambda shown, supported, query="": supported
    )
    monkeypatch.setattr(
        engine, "display_excerpt", lambda text, query, reply: f"windowed:{text}"
    )

    events = list(engine._iter_library_stream_tail(shown, shown, None, candidates, "q"))
    sources_event = next(e for e in events if e["event"] == "sources")
    cards = sources_event["data"]["sources"]
    displayed_text = sources_event["data"]["text"]

    # Only the two cited candidates appear -- a.pdf/b.pdf/d.pdf/f.pdf are gone.
    assert [card["source"] for card in cards] == ["c.pdf", "e.pdf"]
    # Renumbered 1..n, matching the markers finalize_citations rewrote into the text.
    assert [card["number"] for card in cards] == [1, 2]
    assert "[1]" in displayed_text and "[2]" in displayed_text
    assert "[3]" not in displayed_text and "[5]" not in displayed_text
    # Excerpt text goes through the display_excerpt window, not the raw chunk.
    assert [card["text"] for card in cards] == ["windowed:ccc", "windowed:eee"]
    assert all(card["used"] is True for card in cards)


def test_stream_prompt_general_answer_short_circuits(monkeypatch):
    monkeypatch.setattr(
        engine, "_stream_deltas", lambda prompt, temperature: iter(["hi"])
    )
    monkeypatch.setattr(engine, "take_stream_piece", lambda text: (text, "", False))
    events = list(engine._stream_prompt("p", None, None, notice="n"))
    assert [e["event"] for e in events] == ["notice", "token", "sources", "done"]
    assert events[2]["data"] == {"sources": []}


def test_iter_answer_reports_search_unavailable_instead_of_failing(monkeypatch):
    from store.search_errors import SearchUnavailable

    monkeypatch.setattr(engine, "wait_for_models", lambda: None)
    monkeypatch.setattr(engine, "collection_count", lambda: 10)
    monkeypatch.setattr(engine, "should_search_library", lambda search: True)
    monkeypatch.setattr(
        engine,
        "get_or_create_cached_index",
        lambda: (_ for _ in ()).throw(SearchUnavailable("down")),
    )
    events = list(engine.iter_answer("What loudness does the BBC document require?"))
    assert [e["event"] for e in events] == [
        "status",
        "notice",
        "token",
        "sources",
        "done",
    ]
    assert "temporarily unavailable" in events[1]["data"]["text"].lower()
    assert events[2]["data"]["text"] == events[1]["data"]["text"]
    assert events[3]["data"]["sources"] == []
