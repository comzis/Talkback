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


def test_an_english_question_the_excerpts_do_not_mention_is_not_covered():
    sources = [
        {
            "text": "Live programmes must not exceed -3 dBTP. The item fails above -1 dBTP."
        }
    ]
    radio = "What true-peak level does the BBC standard require for radio?"
    loudness = "What audio loudness level do the BBC live technical delivery standards require?"
    assert prompts.excerpts_cover(radio, sources) is False
    covered = [{"text": "Audio loudness for live technical delivery is -23.0 LUFS."}]
    assert prompts.excerpts_cover(loudness, covered) is True
    assert prompts.excerpts_cover("Tell me more.", sources) is True


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


def test_a_first_question_keeps_the_standing_notice():
    assert (
        prompts.notice_for_general(
            "Draft an incident update", None, missed_library=True
        )
        == prompts.GENERAL_NOTICE
    )
    assert prompts.notice_for_general("hello", None) is None
