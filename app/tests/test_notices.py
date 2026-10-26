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
    assert "Do not add general knowledge to a cited answer." in text
    assert 'must start with "From general knowledge:"' in text
    assert "must not contain a measurement" in text
    assert "square brackets" in text
    assert "Do not invent a measurement" in text
    assert "dBTP" in text
    french = prompts.explanation_prompt("Quel filtre ?", ["a.pdf"], ["-23.0 LUFS"])
    assert "D'après les connaissances générales" in french
    spanish = prompts.explanation_prompt("¿Qué nivel?", ["a.pdf"], ["-23.0 LUFS"])
    assert "Según el conocimiento general" in spanish


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


def test_a_bare_number_is_not_a_technical_token():
    sources = [
        {
            "number": 1,
            "source": "wire.pdf",
            "text": "Wireshark captures packets on a network.",
            "page": "4",
        }
    ]
    kept = prompts.supporting_sources("The outage lasted 10 minutes. [1]", sources)
    assert [item["page"] for item in kept] == ["4"]


def test_a_measurement_missing_from_every_passage_drops_the_citation():
    sources = [
        {
            "number": 1,
            "source": "wire.pdf",
            "text": "Wireshark captures packets on a network.",
        }
    ]
    assert prompts.supporting_sources("The level is -23.0 LUFS. [1]", sources) == []


def test_plain_parentheses_do_not_drop_a_citation():
    option = [
        {
            "text": "OPTION A: Main and Backup links are geographically separate.",
            "page": "33",
        }
    ]
    kept = prompts.supporting_sources(
        "Les liens sont géographiquement séparés (Option A). [1]", option
    )
    assert [item["page"] for item in kept] == ["33"]
    agent = [{"text": "Agentless Architecture: Ansible uses SSH.", "page": "4"}]
    assert (
        prompts.supporting_sources(
            "No hace falta un programa residente (agentless). [2]",
            [{}, agent[0]],
        )[0]["page"]
        == "4"
    )
    rollback = [
        {"text": "Store configurations in Git and roll back if needed.", "page": "4"}
    ]
    assert (
        prompts.supporting_sources(
            "Las configuraciones se guardan para una reversión (rollback). [1]",
            rollback,
        )[0]["page"]
        == "4"
    )


def test_a_unit_in_parentheses_wording_still_has_to_match():
    speech = [
        {
            "text": "Speech content in factual programmes should aim for an LRA of no more than 6LU.",
            "page": "16",
        }
    ]
    answer = (
        "Speech content in factual programmes should aim for a Loudness Range "
        "(LRA) of no more than 6 LU. [1]"
    )
    assert [item["page"] for item in prompts.supporting_sources(answer, speech)] == [
        "16"
    ]
    voice = [
        {
            "text": "Where Mode 2 is used, voice over in the centre channel should be approximately 3LU higher.",
            "page": "33",
        }
    ]
    mode = (
        "En mode 2, le commentaire (ou voix off) doit être environ 3 LU plus élevé. [1]"
    )
    assert [item["page"] for item in prompts.supporting_sources(mode, voice)] == ["33"]


def test_a_figure_found_in_another_passage_is_re_attributed():
    sources = [
        {"text": "Dialogue must be clear for a first-time viewer.", "page": "16"},
        {"text": "Live (including as-live) -23.0 LUFS ±1.0LU", "page": "16b"},
    ]
    answer = "La sonoridad exigida es de -23.0 LUFS con un margen de ±1.0 LU. [1]"
    kept = prompts.supporting_sources(answer, sources)
    assert [item["number"] for item in kept] == [2]
    assert kept[0]["page"] == "16b"


def test_numbers_match_across_decimal_commas_and_minus_signs():
    sources = [
        {
            "text": "Non-live programmes are -23.0 LUFS ±0.5LU and fail above −1dBTP.",
            "page": "16",
        }
    ]
    answer = "La tolerancia es 0,5 LU y el pico es −1 dBTP. [1]"
    assert [item["page"] for item in prompts.supporting_sources(answer, sources)] == [
        "16"
    ]


def test_a_standard_code_is_re_attributed_or_dropped():
    sources = [
        {"text": "Meters must comply with EBU Tech 3343.", "page": "16"},
        {"text": "See EBU Tech 3341 for the meter.", "page": "17"},
    ]
    answer = "Meters must comply with EBU Tech 3341. [1]"
    kept = prompts.supporting_sources(answer, sources)
    assert [item["page"] for item in kept] == ["17"]
    assert prompts.supporting_sources(answer, sources[:1]) == []


def test_a_filter_and_a_file_name_are_re_attributed():
    pages = [
        {"text": "Wireshark shows ICMP errors on the network.", "page": "4"},
        {"text": "Display filter: icmp.type == 3 && icmp.code == 2", "page": "34"},
    ]
    answer = "Le filtre est icmp.type == 3 && icmp.code == 2. [1]"
    assert [item["page"] for item in prompts.supporting_sources(answer, pages)] == [
        "34"
    ]
    files = [
        {"text": "Modules are predefined functions.", "page": "4"},
        {"text": "The inventory file hosts.ini lists each device.", "page": "6"},
    ]
    inventory = "El archivo que enumera los dispositivos es hosts.ini. [1]"
    assert [item["page"] for item in prompts.supporting_sources(inventory, files)] == [
        "6"
    ]


def test_tell_me_more_asks_for_facts_not_already_given():
    history = [
        ("user", "What audio loudness level do the BBC standards require?"),
        ("assistant", "Live programmes target -23.0 LUFS."),
    ]
    text = prompts.explanation_prompt(
        "Tell me more.",
        ["a.pdf"],
        ["line-up tone on page 17", "Live programmes target -23.0 LUFS on page 16"],
        history,
    )
    assert "same page or passage" in text
    assert "Do not repeat that answer." in text
    assert text.index("[1] line-up tone") < text.index("[2] Live programmes")
    fresh = prompts.explanation_prompt("What is the level?", ["a.pdf"], ["-23.0 LUFS"])
    assert "same page or passage" not in fresh
    other = prompts.explanation_prompt(
        "What about the deadline?",
        ["a.pdf"],
        ["Monday."],
        [("user", "What does the agreement say?")],
    )
    assert "not already in the earlier answer" not in other


def test_a_distant_sentence_loses_its_citation():
    sources = [
        {
            "number": 1,
            "text": "OPTION C: A single link, with no backup is acceptable.",
            "page": "33",
        }
    ]
    answer = "Incident update: the SRT outage lasted 10 minutes. [1]"
    assert (
        prompts.keep_close_citations(answer, sources, lambda sentence, passage: 0.49)
        == []
    )
    kept = prompts.keep_close_citations(answer, sources, lambda sentence, passage: 0.70)
    assert [item["page"] for item in kept] == ["33"]
    assert prompts.CITATION_MIN_SIMILARITY == 0.55


def test_a_short_correct_reply_is_scored_with_the_question():
    sources = [
        {
            "number": 1,
            "text": "Playbook: YAML file that contains automation instructions.",
            "page": "4",
        }
    ]
    answer = "Se llama Playbook. [1]"
    query = (
        "¿Cómo se llama el fichero de instrucciones de automatización escrito en YAML?"
    )
    seen = []

    def score(sentence, passage):
        seen.append(sentence)
        return 0.66

    kept = prompts.keep_close_citations(answer, sources, score, query=query)
    assert [item["page"] for item in kept] == ["4"]
    assert query in seen[0]
    assert "Playbook" in seen[0]
    assert prompts.citation_compare_text("Se llama Playbook.", query).startswith(
        "¿Cómo"
    )
    wrong = prompts.keep_close_citations(
        "Paris. [1]", sources, lambda sentence, passage: 0.99, query=query
    )
    assert wrong == []


def test_an_unmarked_citation_is_not_scored():
    sources = [{"number": 1, "text": "anything", "page": "4"}]
    kept = prompts.keep_close_citations(
        "No marker here.", sources, lambda sentence, passage: 0.0
    )
    assert kept == sources


def test_the_sentence_next_to_the_marker_is_the_one_compared():
    answer = "The outage lasted 10 minutes. The filter is icmp.type == 3. [2]"
    assert "icmp.type" in prompts.citing_sentence(answer, 2)
    assert "outage" not in prompts.citing_sentence(answer, 2)
    draft = (
        "Incident Update: SRT Outage\n\n"
        "Duration: 10 minutes\n"
        "- [Placeholder for long-term fix]\n\n"
        "[3]"
    )
    sentence = prompts.citing_sentence(draft, 3)
    assert "long-term fix" in sentence
    assert "SRT" not in sentence


def test_a_general_remark_loses_its_measurements():
    raw = (
        "The excerpts are about television. From general knowledge: "
        "radio true peak is -1 dBTP and the delay is 40 ms at 5 Mbit/s."
    )
    cleaned = prompts.scrub_general_figures(raw)
    assert "-1" not in cleaned
    assert "dBTP" not in cleaned
    assert "40" not in cleaned
    assert "Mbit/s" not in cleaned
    assert cleaned.count("not from the documents, verify") == 3
    assert "television" in cleaned
    french = "D'après les connaissances générales : le niveau est de -23,0 LUFS."
    assert "LUFS" not in prompts.scrub_general_figures(french)
    cited = "Live programmes are -23.0 LUFS. [1]"
    assert prompts.scrub_general_figures(cited) == cited


def test_the_stream_holds_a_partial_general_label():
    emit, keep, started = prompts.take_stream_piece("From general")
    assert emit == ""
    assert started is False
    assert keep == "From general"
    emit, keep, started = prompts.take_stream_piece(
        "The excerpts do not answer. From general knowledge: radio is -1 dBTP."
    )
    assert emit == "The excerpts do not answer. "
    assert started is True
    assert keep.startswith("From general knowledge:")


def test_a_first_question_keeps_the_standing_notice():
    assert (
        prompts.notice_for_general(
            "Draft an incident update", None, missed_library=True
        )
        == prompts.GENERAL_NOTICE
    )
    assert prompts.notice_for_general("hello", None) is None
