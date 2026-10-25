"""A general reply after an earlier answer is marked in the question's language."""

import llm.prompts as prompts


def test_a_follow_up_that_misses_the_library_is_marked():
    history = [
        ("user", "What audio loudness level do the BBC standards require?"),
        ("assistant", "Live programmes target -23.0 LUFS."),
    ]
    note = prompts.notice_for_general("telll me more", history, missed_library=True)
    assert note == "This answer is not from the documents and may not match them."
    assert "telll me more" not in (note or "")


def test_the_warning_follows_the_question_language():
    history = [("assistant", "Le filtre est icmp.type == 3.")]
    french = prompts.notice_for_general("Donne-moi plus de détails", history)
    spanish = prompts.notice_for_general("¿Puedes dar más detalle?", history)
    assert french.startswith("Cette réponse")
    assert "documents" in french
    assert spanish.startswith("Esta respuesta")
    assert "documentos" in spanish


def test_notices_and_fallbacks_follow_the_question_language():
    assert (
        prompts.user_line("general", "Draft an incident update")
        == prompts.GENERAL_NOTICE
    )
    assert prompts.user_line("general", "Quel filtre ICMP ?").startswith("Aucun")
    assert prompts.user_line("not_covered", "¿Qué módulos?").startswith("La biblioteca")
    assert prompts.user_line("no_detail", "Donne-moi le détail").startswith(
        "Les extraits"
    )
    assert prompts.library_miss("I think it is Paris.", "¿Qué dice?") == (
        "La biblioteca no cubre eso."
    )


def test_the_prompt_answers_from_passages_or_general_knowledge():
    text = prompts.explanation_prompt("What is the level?", ["a.pdf"], ["-23.0 LUFS"])
    assert "answer from them" in text
    assert "general knowledge" in text
    assert "square brackets" in text
    assert "Do not invent a measurement" in text
    assert "dBTP" in text


def test_spanish_loudness_keeps_its_citation_without_english_words():
    passage = "Live programmes shall measure -23.0 LUFS with a tolerance of ±1.0LU."
    answer = (
        "Para un programa en directo, la sonoridad exigida es de -23.0 LUFS "
        "con un margen de ±1.0 LU. [1]"
    )
    sources = [
        {
            "number": 1,
            "source": "TechnicalDeliveryStandardsBBCLive.pdf",
            "text": passage,
            "page": "16",
        }
    ]
    kept = prompts.supporting_sources(answer, sources)
    assert [item["page"] for item in kept] == ["16"]
    wrong = [
        {
            "number": 1,
            "source": "notes.pdf",
            "text": "Stereo line-up tone.",
            "page": "17",
        }
    ]
    assert prompts.supporting_sources(answer, wrong) == []


def test_a_citation_is_dropped_when_the_passage_lacks_the_number():
    sources = [
        {
            "number": 1,
            "source": "wire.pdf",
            "text": "Wireshark captures packets on a network.",
        }
    ]
    assert (
        prompts.supporting_sources("The outage lasted 10 minutes. [1]", sources) == []
    )


def test_a_first_question_keeps_the_standing_notice():
    assert (
        prompts.notice_for_general(
            "Draft an incident update", None, missed_library=True
        )
        == prompts.GENERAL_NOTICE
    )
    assert prompts.notice_for_general("hello", None) is None
