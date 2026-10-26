"""Prompt text for grounded answers."""

import re
import unicodedata

_CITATION = re.compile(r"\[\d+\]")
_WORD = re.compile(r"[a-z0-9]{2,}")
_REFUSAL = re.compile(
    r"cannot find|can't find|do not contain|does not contain|don't contain|"
    r"not in the (retrieved|uploaded|library|sources|documents)|"
    r"ne couvre pas|ne contiennent pas ce|"
    r"no cubre|no incluyen ese",
    re.IGNORECASE,
)
_STOP = {
    "that",
    "this",
    "with",
    "from",
    "your",
    "have",
    "what",
    "when",
    "where",
    "which",
    "about",
    "there",
    "their",
    "would",
    "could",
    "should",
    "into",
    "using",
    "does",
    "they",
    "them",
    "than",
    "then",
    "also",
    "just",
    "only",
    "some",
    "such",
    "answer",
    "question",
    "is",
    "in",
    "the",
    "of",
    "to",
    "an",
    "it",
    "on",
    "for",
    "and",
    "or",
    "be",
    "at",
    "by",
    "my",
    "me",
    "do",
    "if",
    "so",
    "we",
    "you",
    "are",
    "was",
    "were",
    "can",
    "how",
    "who",
    "why",
    "not",
    "but",
    "its",
}


def citation_prompt(library_files: list[str]) -> str:
    """Build the answer prompt, including every document still in the library."""
    names = ", ".join(library_files) if library_files else "(none yet)"
    return (
        "You are a helpful assistant. The user can ask anything.\n"
        f"The library contains these documents: {names}.\n"
        "If the sources below answer the question, use them and cite each claim "
        "with a source number in square brackets, such as [1] or [2].\n"
        "If the sources do not answer the question, reply from your own knowledge "
        "as an assistant. Do not cite sources, and do not say you are waiting for a document.\n"
        "---------------------\n"
        "Context: {context_str}\n"
        "---------------------\n"
        "Question: {query_str}\n"
        "Answer: "
    )


GENERAL_NOTICE = "No matching documents found; answering generally."
UNMATCHED_SOURCE_NOTE = "No source could be matched to this answer."
NOT_INDEXED_NOTICE = "These files are in the library folder but are not indexed yet."
_OUTSIDE_DOCUMENT = {
    "en": "This answer is not from the documents and may not match them.",
    "fr": "Cette réponse ne vient pas des documents et peut ne pas leur correspondre.",
    "es": "Esta respuesta no procede de los documentos y puede no coincidir con ellos.",
}
_GENERAL_MARK = {
    "en": "From general knowledge:",
    "fr": "D'après les connaissances générales :",
    "es": "Según el conocimiento general:",
}
_GENERAL_FIGURE = re.compile(
    r"(?<![\w.])[±+\-−–]?\s*\d+(?:[.,]\d+)?\s*"
    r"(?:dBTP|dBFS|LUFS|LKFS|dB|LU|ms|Mbit/s|kbit/s|Gbit/s)\b",
    re.IGNORECASE,
)
_VERIFY_FIGURE = "not from the documents, verify"
_SPANISH_QUESTION = re.compile(
    r"[¿¡ñ]|\b(?:qué|puedes|detalle|módulos|modulos|más)\b",
    re.IGNORECASE,
)
_FRENCH_QUESTION = re.compile(
    r"[àâçéèêëïîôùûüœ]|\b(?:donne|détails|details|filtre)\b",
    re.IGNORECASE,
)


def _plain_apostrophe(text: str) -> str:
    return (text or "").replace("’", "'").replace("‘", "'")


def scrub_general_figures(text: str) -> str:
    """Replace measurements inside a labelled general-knowledge remark.

    Figures before the label stay. The label itself stays.
    """
    normalized = _plain_apostrophe(text)
    found_at = None
    found = ""
    for mark in _GENERAL_MARK.values():
        at = normalized.find(mark)
        if at != -1 and (found_at is None or at < found_at):
            found_at = at
            found = mark
    if found_at is None:
        return text
    tail = normalized[found_at + len(found) :]
    return text[:found_at] + found + _GENERAL_FIGURE.sub(_VERIFY_FIGURE, tail)


def take_stream_piece(pending: str) -> tuple[str, str, bool]:
    """Split one buffer into text to send, text to keep, and whether the mark started.

    A suffix that could still grow into the general-knowledge label is kept.
    """
    normalized = _plain_apostrophe(pending)
    found_at = None
    for mark in _GENERAL_MARK.values():
        at = normalized.find(mark)
        if at != -1 and (found_at is None or at < found_at):
            found_at = at
    if found_at is not None:
        return pending[:found_at], normalized[found_at:], True
    limit = max(len(mark) for mark in _GENERAL_MARK.values())
    hold = 0
    for size in range(1, min(limit, len(normalized)) + 1):
        suffix = normalized[-size:]
        if any(mark.startswith(suffix) for mark in _GENERAL_MARK.values()):
            hold = size
    if hold:
        return pending[:-hold], pending[-hold:], False
    return pending, "", False


def question_language(query: str) -> str:
    """English, French, or Spanish, from the question itself."""
    text = query or ""
    if _SPANISH_QUESTION.search(text):
        return "es"
    if _FRENCH_QUESTION.search(text):
        return "fr"
    return "en"


_USER_LINES = {
    "general": {
        "en": GENERAL_NOTICE,
        "fr": "Aucun document correspondant ; réponse générale.",
        "es": "No hay documentos que coincidan; respuesta general.",
    },
    "unmatched": {
        "en": UNMATCHED_SOURCE_NOTE,
        "fr": "Aucune source ne correspond à cette réponse.",
        "es": "Ninguna fuente coincide con esta respuesta.",
    },
    "not_indexed": {
        "en": NOT_INDEXED_NOTICE,
        "fr": "Ces fichiers sont dans le dossier de la bibliothèque mais ne sont pas encore indexés.",
        "es": "Estos archivos están en la carpeta de la biblioteca pero aún no están indexados.",
    },
    "indexing": {
        "en": "Indexing has started. Ask again once it finishes.",
        "fr": "L'indexation a commencé. Redemandez quand elle sera terminée.",
        "es": "La indexación ha empezado. Vuelve a preguntar cuando termine.",
    },
    "no_example": {
        "en": "The retrieved excerpts do not include a worked example.",
        "fr": "Les extraits récupérés ne contiennent pas d'exemple complet.",
        "es": "Los fragmentos recuperados no incluyen un ejemplo completo.",
    },
    "no_detail": {
        "en": "The retrieved excerpts do not include that detail.",
        "fr": "Les extraits récupérés ne contiennent pas ce détail.",
        "es": "Los fragmentos recuperados no incluyen ese detalle.",
    },
    "not_covered": {
        "en": "The library does not cover that.",
        "fr": "La bibliothèque ne couvre pas cela.",
        "es": "La biblioteca no cubre eso.",
    },
}


def user_line(kind: str, query: str = "") -> str:
    """A notice or fallback in the language of the question."""
    return _USER_LINES[kind][question_language(query)]


def outside_document_note(query: str) -> str:
    """Visible warning that a general reply is not a document fact."""
    return _OUTSIDE_DOCUMENT[question_language(query)]


def follows_previous_answer(history) -> bool:
    """True when this question comes after an earlier reply in the conversation."""
    return any(role == "assistant" for role, _text in clean_history(history))


def notice_for_general(
    query: str, history=None, *, missed_library: bool = False
) -> str | None:
    """Notice for a reply that is not using the library.

    Right after an earlier answer, the note is in the question's language and
    says the reply is not from the documents. A first question that misses the
    library gets the general-path notice in the question's language.
    """
    if follows_previous_answer(history):
        return outside_document_note(query)
    if missed_library:
        return user_line("general", query)
    return None


def clean_history(history, limit: int = 8) -> list[tuple[str, str]]:
    """Keep the latest user and assistant turns. Each turn is capped so the prompt stays small."""
    turns = []
    for item in history or []:
        if isinstance(item, dict):
            role, content = item.get("role"), item.get("content")
        elif isinstance(item, (tuple, list)) and len(item) == 2:
            role, content = item
        else:
            role, content = getattr(item, "role", None), getattr(item, "content", None)
        if role not in ("user", "assistant"):
            continue
        text = " ".join(str(content or "").split())
        if not text:
            continue
        turns.append((role, text[:400]))
    return turns[-limit:]


def format_history(history, *, continue_from_passages: bool = False) -> str:
    """Earlier turns, placed above the latest question."""
    turns = clean_history(history)
    if not turns:
        return ""
    lines = [
        f"{'User' if role == 'user' else 'Assistant'}: {text}" for role, text in turns
    ]
    if continue_from_passages:
        closing = (
            "The latest line asks you to continue. "
            "Prefer facts from the same page or passage as the earlier answer "
            "that were not already stated, including measurements and limits that answer left out. "
            "Use a different page only after that page has nothing further to add. "
            "Do not repeat that answer.\n\n"
        )
    else:
        closing = (
            "Answer the latest question as a continuation of these turns. "
            "Do not start over.\n\n"
        )
    return "Earlier in this conversation:\n" + "\n".join(lines) + "\n" + closing


def _loose(text: str) -> str:
    """Lower-case, drop accents, and collapse a letter repeated three times or more.

    'telll me more' and 'más detalle' then match the same phrases as the
    spelled forms. The match does not depend on any one document.
    """
    folded = unicodedata.normalize("NFKD", text or "")
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    folded = folded.lower()
    folded = re.sub(r"(.)\1{2,}", r"\1\1", folded)
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


_CONTINUATION = re.compile(
    r"\b("
    r"tell me more|more detail|more details|in more detail|more detailed|"
    r"what about|how about|elaborate|go on|continue|the same|another|"
    r"give an example|an example|for example|"
    r"each step|step by step|the steps|explain the steps|explain each|"
    r"walk me through|walk through|break it down|break down|explain that|explain this|"
    r"plus de details|plus de detail|donne moi plus|davantage|"
    r"mas detalle|mas detalles|puedes dar mas|cuentame mas|continua|"
    r"un exemple|par exemple|etape par etape|les etapes|"
    r"un ejemplo|por ejemplo|paso a paso|los pasos"
    r")\b"
)
_CONTINUATION_WORDS = {
    "tell",
    "more",
    "detail",
    "details",
    "detailed",
    "elaborate",
    "continue",
    "same",
    "another",
    "give",
    "example",
    "step",
    "steps",
    "explain",
    "walk",
    "through",
    "break",
    "down",
    "plus",
    "donne",
    "moi",
    "davantage",
    "mas",
    "detalle",
    "detalles",
    "puedes",
    "dar",
    "cuentame",
    "continua",
    "exemple",
    "etape",
    "etapes",
    "ejemplo",
    "paso",
    "pasos",
}


def _continuation_only(query: str) -> bool:
    """True when the line only asks to go on, with no new subject of its own."""
    words = [
        word
        for word in _loose(query).split()
        if word not in _STOP and word not in _CONTINUATION_WORDS
    ]
    return not words


_EXAMPLE_ASK = re.compile(
    r"\b(give an example|an example|for example|un exemple|par exemple|un ejemplo|por ejemplo)\b"
)
_STEPS_ASK = re.compile(
    r"\b(each step|step by step|the steps|explain the steps|explain each|"
    r"etape par etape|les etapes|paso a paso|los pasos)\b"
)


def asks_for_steps(query: str) -> bool:
    """True when the user wants the procedure, not a one-line summary."""
    return _STEPS_ASK.search(_loose(query)) is not None


def asks_for_example(query: str) -> bool:
    """True when the user wants one concrete case from the document."""
    return _EXAMPLE_ASK.search(_loose(query)) is not None


def is_follow_up(query: str) -> bool:
    """True when the line continues the previous topic instead of starting a new one."""
    text = (query or "").strip()
    if not text or _SMALL_TALK.match(text):
        return False
    if _CONTINUATION.search(_loose(text)):
        return True
    words = [word for word in _WORD.findall(text.lower()) if word not in _STOP]
    return len(text) <= 20 and len(words) <= 1


def retrieval_text(query: str, history=None) -> str:
    """Search text for this question. A follow-up keeps the earlier topic in the search."""
    current = (query or "").strip()
    turns = clean_history(history)
    if not turns or not is_follow_up(current):
        return current
    users = [
        text
        for role, text in turns
        if role == "user" and not is_follow_up(text) and not _SMALL_TALK.match(text)
    ]
    topic = users[-1] if users else ""
    if topic and _continuation_only(current):
        return topic
    words = [word for word in _WORD.findall(current.lower()) if word not in _STOP]
    spoken = ""
    if len(words) <= 1:
        assistants = [text for role, text in turns if role == "assistant"]
        spoken = " ".join(assistants[-2:])[:180]
    return "\n".join(part for part in (current, topic, spoken) if part)


def assistant_prompt(query: str, history=None) -> str:
    """Prompt for a direct assistant reply with no document requirement."""
    return (
        "You are Talkback, a helpful assistant. Reply the way a person would in a conversation.\n"
        "Reply in the language of the user's question, even when a source is in another language. "
        "Keep file names and quoted text in their original language.\n"
        "Keep it short and natural. Use plain sentences.\n"
        "Do not use markdown, headings, or a numbered manual unless the user asked for steps.\n"
        + (
            "The latest line continues the conversation above. Answer it from those turns. "
            "Do not greet the user and do not ask which topic they mean.\n"
            if clean_history(history)
            else "Do not mention documents, a library, or sources.\n"
        )
        + "If they pasted a passage, explain it briefly in your own words.\n\n"
        f"{format_history(history)}"
        f"User:\n{query}\n"
        "Assistant:"
    )


_GENERIC_FILE_WORDS = {
    "python",
    "basics",
    "notes",
    "guide",
    "skills",
    "document",
    "documents",
    "manual",
    "intro",
    "introduction",
    "overview",
    "draft",
    "final",
    "report",
    "slides",
    "sheet",
}
_SMALL_TALK = re.compile(
    r"^(hi|hello|hey|thanks|thank you|ok|okay|yo|good morning|good afternoon|good evening|"
    r"bonjour|salut|merci|hola|gracias|buenos dias|buenas tardes)\b",
    re.IGNORECASE,
)


def _names_file(token: str, lowered: str) -> bool:
    """True when a filename token appears in the question as its own word."""
    if token in _GENERIC_FILE_WORDS:
        return False
    if len(token) < 5:
        return re.search(rf"\b{re.escape(token)}\b", lowered) is not None
    return token in lowered


def named_library_files(query: str, library_files: list[str]) -> list[str]:
    """Return library filenames the question actually names."""
    lowered = (query or "").lower()
    matched = []
    for name in library_files:
        full = name.lower()
        stem = full.rsplit(".", 1)[0].strip()
        tokens = re.findall(r"[a-z0-9]{2,}", stem)
        named = (full and full in lowered) or (len(stem) >= 4 and stem in lowered)
        named = named or any(_names_file(token, lowered) for token in tokens)
        if named:
            matched.append(name)
    return matched


def asks_about_library(query: str, library_files: list[str]) -> bool:
    """True when the user is asking about the library or pasted a passage to explain."""
    text = (query or "").strip()
    lowered = text.lower()
    if text.count("\n") >= 1 and len(text) > 40:
        return True
    cues = (
        "document",
        "documents",
        "library",
        "uploaded",
        "pdf",
        "according to",
        "in the file",
        "in my file",
        "the source",
        "cite ",
        "from the doc",
    )
    if any(cue in lowered for cue in cues):
        return True
    return bool(named_library_files(query, library_files))


def should_search_library(query: str) -> bool:
    """False for a greeting or a note too short to be a library question."""
    text = (query or "").strip()
    if len(text) < 12:
        return False
    if _SMALL_TALK.match(text) and "\n" not in text and len(text) < 48:
        return False
    words = [word for word in _WORD.findall(text.lower()) if word not in _STOP]
    return bool(words) or (text.count("\n") >= 1 and len(text) > 40)


def excerpts_mention(query: str, texts: list[str]) -> bool:
    """True when a retrieved excerpt uses a distinctive word from the question."""
    words = [word for word in _WORD.findall((query or "").lower()) if word not in _STOP]
    if not words:
        return False
    blob = " ".join(texts).lower()
    return any(word in blob for word in words)


def explanation_prompt(
    query: str, library_files: list[str], excerpts: list[str], history=None
) -> str:
    """Prompt that explains pasted text and reasons only with library excerpts."""
    names = ", ".join(library_files) if library_files else "(none yet)"
    shown = "\n\n".join(f"[{index}] {text}" for index, text in enumerate(excerpts, 1))
    if not shown:
        shown = "(no matching excerpts)"
    if asks_for_steps(query):
        shape = (
            "The user asked for the steps. Walk through each step the excerpts describe, in order. "
            "Number the steps as 1. 2. 3. Use only what the excerpts say.\n"
        )
    elif asks_for_example(query):
        shape = (
            "The user asked for an example. Give one concrete example from the excerpts, "
            "copying the filter, command, or action exactly. "
            "If the excerpts do not show one, say the excerpts do not include a worked example. "
            "Do not invent a filter or a command.\n"
        )
    else:
        shape = "Keep the reply short. Use plain sentences, not a markdown manual.\n"
    return (
        "You are Talkback. The user is asking about their documents or pasted a passage.\n"
        "Reply in the language of the user's question, even when a source is in another language. "
        "Keep file names and quoted text in their original language.\n"
        f"The library contains: {names}.\n"
        "If the user pasted a passage, explain that text in plain language and walk through the lines.\n"
        "If the excerpts answer the question, answer from them and end with the excerpt number in brackets, such as [1]. "
        "Do not add general knowledge to a cited answer.\n"
        "If they do not answer the question, say so and do not cite the excerpts. "
        f'A further remark that the excerpts do not support must start with "{_GENERAL_MARK[question_language(query)]}" '
        "and must not contain a measurement.\n"
        "Do not invent a measurement. Never write a dBTP, LUFS, LU, or dB figure unless the excerpts answer the question and contain that figure.\n"
        "When the user asked for placeholders, write each one in square brackets.\n"
        f"{shape}\n"
        f"{format_history(history, continue_from_passages=_continuation_only(query))}"
        f"Library excerpts:\n{shown}\n\n"
        f"User:\n{query}\n"
        "If the excerpts do not answer the question, do not write a dBTP, LUFS, LU, or dB number.\n"
        "Assistant:"
    )


def answered_from_sources(text: str) -> bool:
    """True when a reply cites the library and does not refuse the question."""
    if not text or _REFUSAL.search(text):
        return False
    return _CITATION.search(text) is not None


def cited_source_indexes(text: str) -> list[int]:
    """Return the source numbers used in a reply, in first-seen order."""
    indexes = []
    seen = set()
    for match in re.findall(r"\[(\d+)\]", text or ""):
        number = int(match)
        if number in seen:
            continue
        seen.add(number)
        indexes.append(number)
    return indexes


_FENCE = re.compile(r"```[a-z]*\n?([\s\S]*?)```", re.IGNORECASE)
_INLINE = re.compile(r"`([^`]{2,120})`")
_COMPARE = re.compile(
    r"\b[A-Za-z][\w.]*(?:\[[^\]]+\])?\s*(?:==|!=)\s*[A-Za-z0-9_:.\-\[\]]{1,60}"
)
_CONTAINS_LITERAL = re.compile(r"\bcontains\s+[\"“'][^\"”']{1,60}[\"”']", re.IGNORECASE)
_DOTTED = re.compile(r"\b[A-Za-z]{2,}(?:\.[A-Za-z0-9]{2,})+\b")
_LONG_NUMBER = re.compile(r"\b\d{2,}\b")
_CODE = re.compile(r"\b(?:type|code)\s+\d+\b", re.IGNORECASE)
_EXAMPLE_LEAD = re.compile(
    r"^(here(?:'s| is)|this (?:filter|example)|use this|an example of)\b",
    re.IGNORECASE,
)


def _flat(text: str) -> str:
    text = (
        (text or "")
        .replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("‘", "'")
    )
    return re.sub(r"\s+", " ", text).casefold()


def _source_blob(sources: list[dict]) -> str:
    return _flat("\n".join(source.get("text") or "" for source in sources))


def _unsupported_fragment(fragment: str, blob: str) -> bool:
    folded = _flat(fragment).strip(" `\"'")
    return len(folded) >= 2 and folded not in blob


def _shows_example(text: str, blob: str) -> bool:
    """True when the reply still contains a filter or command that the excerpts contain."""
    if _CONTAINS_LITERAL.search(text) or _COMPARE.search(text):
        return True
    return any(
        not _unsupported_fragment(match, blob) for match in _INLINE.findall(text)
    )


def _sentence_invents(sentence: str, blob: str) -> bool:
    """True when a sentence adds a filter, command, dotted name, or number the excerpts omit."""
    body = strip_citations(sentence)
    pieces = [match for match in _INLINE.findall(body)]
    pieces.extend(match.group(0) for match in _COMPARE.finditer(body))
    pieces.extend(match.group(0) for match in _CONTAINS_LITERAL.finditer(body))
    pieces.extend(match.group(0) for match in _DOTTED.finditer(body))
    pieces.extend(match.group(0) for match in _CODE.finditer(body))
    pieces.extend(_LONG_NUMBER.findall(body))
    return any(_unsupported_fragment(piece, blob) for piece in pieces)


_PDF_WORD = {
    "a",
    "an",
    "as",
    "at",
    "be",
    "by",
    "do",
    "if",
    "in",
    "is",
    "it",
    "no",
    "of",
    "on",
    "or",
    "so",
    "to",
    "we",
    "and",
    "the",
    "for",
    "not",
    "you",
    "but",
    "can",
    "its",
    "may",
    "any",
    "all",
    "has",
    "are",
    "was",
    "one",
    "our",
    "out",
    "use",
    "see",
    "how",
    "with",
    "from",
    "that",
    "this",
    "have",
    "your",
    "into",
    "over",
    "than",
    "then",
    "them",
    "they",
    "what",
    "when",
    "will",
    "also",
    "each",
    "just",
    "only",
    "some",
    "more",
    "most",
    "such",
    "want",
    "view",
    "byte",
    "after",
    "take",
    "look",
    "due",
    "per",
    "via",
}
_EXAMPLE_HEAD = re.compile(r"Example\s+\d+\s*:", re.IGNORECASE)
_FILTER_SPAN = re.compile(
    r"\((?:[^()\n]|\([^()\n]*\))+\)(?:\s*(?:\|\||&&)\s*\((?:[^()\n]|\([^()\n]*\))+\))*"
)


def prompt_passage(text: str) -> str:
    """Full chunk text for the prompt and the grounding check."""
    return repair_pdf_spacing(text or "")


def display_excerpt(text: str, query: str = "", answer: str = "") -> str:
    """Clip the source card to the part of the chunk that matches the answer.

    The window used to be the first 500 characters, which hid a filter that
    started later in the same chunk.
    """
    limit = 900 if asks_for_example(query) or asks_for_steps(query) else 500
    body = repair_pdf_spacing(text or "")
    if not body:
        return ""
    start = _excerpt_start(body, answer, query)
    return body[start : start + limit].lstrip()


def _fold_match(text: str) -> str:
    return (text or "").replace("−", "-").replace("–", "-").lower()


def _excerpt_start(body: str, answer: str, query: str) -> int:
    """Index where the card should open, just before the matching phrase."""
    folded = _fold_match(body)
    anchor = _answer_anchor(folded, _fold_match(answer))
    if anchor is None and (asks_for_example(query) or asks_for_steps(query)):
        match = re.search(r"example\s+\d+\s*:", folded)
        if not match:
            match = re.search(r"contains\s+[\"“']|==", folded)
        if match:
            anchor = match.start()
    if not anchor:
        return 0
    return max(0, anchor - 40)


def _answer_anchor(body: str, answer: str) -> int | None:
    """Where the longest answer phrase sits in the chunk."""
    spans = [span.strip() for span in re.split(r"(?<=[.!?])\s+|\n+", answer or "")]
    spans += re.findall(r"\([^()]{0,160}\)", answer or "")
    spans += re.findall(r"-?\d+(?:[.,]\d+)?\s*(?:dbtp|lufs|lkfs|lu)\b", answer or "")
    best_at = None
    best_len = 7
    for span in spans:
        compact = " ".join(span.split())
        if len(compact) <= best_len:
            continue
        at = body.find(compact)
        if at >= 0:
            best_at = at
            best_len = len(compact)
    return best_at


def repair_pdf_spacing(text: str) -> str:
    """Join words the PDF extractor split, such as 'cont ain'."""

    def once(line: str) -> str:
        tokens = line.split(" ")
        changed = True
        while changed:
            changed = False
            merged = []
            index = 0
            while index < len(tokens):
                left = tokens[index]
                right = tokens[index + 1] if index + 1 < len(tokens) else ""
                broken = (
                    left
                    and right
                    and (
                        (
                            len(left) == 1
                            and right[:2].lower() in {"ft", "ck", "ng", "sr", "tl"}
                        )
                        or (
                            left.lower() not in _PDF_WORD
                            and right.lower() not in _PDF_WORD
                            and left[-1:].islower()
                            and right[:1].islower()
                            and (len(left) <= 3 or (len(left) <= 4 and len(right) <= 3))
                        )
                    )
                )
                if broken:
                    merged.append(left + right)
                    index += 2
                    changed = True
                    continue
                merged.append(left)
                index += 1
            tokens = merged
        return " ".join(tokens)

    return "\n".join(
        re.sub(r" {2,}", " ", once(line)) for line in (text or "").split("\n")
    )


def _filter_span(text: str):
    """The worked filter in an excerpt, parentheses included."""
    for match in _FILTER_SPAN.finditer(text or ""):
        if "==" in match.group(0) or "contains" in match.group(0).lower():
            return match
    return _CONTAINS_LITERAL.search(text or "") or _COMPARE.search(text or "")


def _example_blocks(text: str) -> list[str]:
    marks = list(_EXAMPLE_HEAD.finditer(text or ""))
    blocks = []
    for index, mark in enumerate(marks):
        end = (
            marks[index + 1].start()
            if index + 1 < len(marks)
            else min(len(text), mark.end() + 650)
        )
        block = text[mark.start() : end].strip()
        if _filter_span(block):
            blocks.append(block)
    return blocks


def _best_example(sources: list[dict], query: str = "") -> tuple[str, int] | None:
    """The first worked example in the excerpts. The query is not used to prefer one document."""
    del query
    for source in sources:
        text = repair_pdf_spacing(source.get("text") or "")
        blocks = _example_blocks(text)
        if blocks:
            return blocks[0], int(source.get("number") or 0)
    return None


def _plain_reply(text: str) -> str:
    """Drop markdown and a trailing offer of more questions."""
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", text or "")
    cleaned = re.sub(r"(?m)^\s*#+\s*", "", cleaned)
    kept = []
    for line in cleaned.split("\n"):
        if re.match(r"let me know\b", line.strip(), re.IGNORECASE):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _format_example(block: str) -> tuple[str, list[str]]:
    """Heading, the explanation, and the filter on its own step."""
    span = _filter_span(block)
    http = re.search(r"https?://", block, re.IGNORECASE)
    if http and (span is None or http.start() < span.start()):
        prose = block[: http.start()].strip()
        filt = re.sub(r"\s+", " ", span.group(0)).strip() if span else ""
        block = f"{prose} {filt}".strip()
    elif span:
        block = block[: span.end()]
    flat = re.sub(r"\s+", " ", block).strip()
    flat = re.sub(
        r"^(Example\s+\d+\s*:\s*.{0,50}?)(?=\s+(?:If|Suppose|One|To|There|The|You|When|Several)\b)",
        r"\1\n",
        flat,
        count=1,
        flags=re.IGNORECASE,
    )
    parts = [part.strip() for part in flat.split("\n") if part.strip()]
    title = parts[0]
    body = " ".join(parts[1:]) if len(parts) > 1 else ""
    span = _filter_span(flat)
    filter_line = re.sub(r"\s+", " ", span.group(0)).strip() if span else ""
    sentences = []
    for sentence in re.split(r"(?<=[.!?])\s+", body):
        sentence = sentence.strip()
        if filter_line:
            sentence = sentence.replace(filter_line, "").strip(" .;")
        if sentence and not _filter_span(sentence):
            sentences.append(sentence)
    if filter_line:
        sentences.append(filter_line)
    return title, sentences[:4]


def _steps_from_sources(sources: list[dict], query: str) -> str | None:
    """Number the worked example from the excerpts instead of a loose paraphrase."""
    found = _best_example(sources, query)
    if not found:
        return None
    block, number = found
    title, sentences = _format_example(block)
    if not sentences:
        return None
    numbered = "\n".join(
        f"{index}. {sentence}" for index, sentence in enumerate(sentences, 1)
    )
    mark = f" [{number}]" if number else ""
    return f"{title}{mark}\n{numbered}"


def _quote_example(sources: list[dict], query: str) -> str | None:
    """One complete example, starting at its heading and ending at its filter."""
    found = _best_example(sources, query)
    if not found:
        return None
    block, number = found
    title, sentences = _format_example(block)
    if not sentences:
        return None
    mark = f" [{number}]" if number else ""
    return f"{title}. {' '.join(sentences)}{mark}"


def ground_library_reply(answer: str, sources: list[dict], query: str = "") -> str:
    """Drop filters, commands, and numbers that the retrieved excerpts do not contain."""
    if asks_for_steps(query):
        walked = _steps_from_sources(sources, query)
        if walked:
            return walked
    if asks_for_example(query):
        quoted = _quote_example(sources, query)
        if quoted:
            return quoted
    if not answer:
        return answer
    answer = _plain_reply(answer)
    blob = _source_blob(sources)
    text = answer
    for match in list(_FENCE.finditer(text)):
        if _unsupported_fragment(match.group(1), blob):
            text = text.replace(match.group(0), "")
    kept = []
    for line in re.split(r"\n+", text):
        for sentence in re.split(r"(?<!\d)(?<=[.!?])\s+(?=[A-Z])", line.strip()):
            sentence = sentence.strip()
            if not sentence or _sentence_invents(sentence, blob):
                continue
            if re.fullmatch(r"(?:\[\d+\]\s*)+", sentence):
                continue
            kept.append(sentence)
    cleaned = "\n".join(kept).strip()
    if not _shows_example(cleaned, blob):
        cleaned = "\n".join(
            sentence
            for sentence in cleaned.split("\n")
            if not _EXAMPLE_LEAD.match(sentence.strip())
        ).strip()
    if asks_for_example(query) and not _shows_example(cleaned, blob):
        found = _quote_example(sources, query)
        if found:
            cleaned = found if not cleaned else f"{cleaned}\n{found}"
        elif not cleaned:
            cleaned = user_line("no_example", query)
        else:
            cleaned = f"{cleaned}\n{user_line('no_example', query)}"
    if not strip_citations(cleaned).strip():
        return user_line("no_detail", query)
    return cleaned


_FILE_TOKEN = re.compile(
    r"\b[\w.-]+\.(?:pdf|ini|txt|ya?ml|cfg|conf|json|csv)\b",
    re.IGNORECASE,
)
_MEASURE_WITH_UNIT = re.compile(
    r"(?<![\w.])([±+-]?)\s*(\d+(?:\.\d+)?)\s*(dbtp|dbfs|lufs|lkfs|db|lu)\b"
)
_STANDARD_CODE = re.compile(r"\btech\s*(\d{3,4})\b")
_DOTTED_FIELD = re.compile(r"\b[a-z][a-z0-9_]+\.[a-z][a-z0-9_.]*\b")
_FILTER_NAME = r"[a-z_][\w.]*"
_FILTER_VALUE = r"[a-z0-9_\"'-]+"
_FILTER_ATOM = rf"{_FILTER_NAME}\s*==\s*{_FILTER_VALUE}"
_FILTER_EXPR = re.compile(
    rf"(?:{_FILTER_ATOM})(?:\s*(?:&&|\|\|)\s*(?:{_FILTER_ATOM}))+"
    rf"|{_FILTER_ATOM}"
    rf"|{_FILTER_NAME}(?:\s*(?:&&|\|\|)\s*{_FILTER_NAME})+"
)


def _compact(text: str) -> str:
    folded = (text or "").replace("−", "-").replace("–", "-").replace(",", ".")
    return re.sub(r"\s+", "", folded).casefold()


def _loosen(text: str) -> str:
    """Separate a number glued to a unit, as in 1.0LU or -1dBTP."""
    folded = (text or "").replace("−", "-").replace("–", "-").replace(",", ".")
    folded = folded.casefold()
    folded = re.sub(r"(?<=\d)(?=[a-z])", " ", folded)
    return re.sub(r"(?<=[a-z])(?=\d)", " ", folded)


def _canon_measure(sign: str, number: str, unit: str) -> str:
    """One form for 0.5 / 0,5 and for − / -."""
    prefix = "±" if sign == "±" else "-" if sign == "-" else ""
    return f"{prefix}{number} {unit}"


def technical_tokens(text: str) -> list[tuple[str, str]]:
    """Filters, dotted fields, numbers with units, standard codes, and file names.

    A parenthesis group of ordinary words, such as "(Option A)" or "(LRA)",
    is not a token. A bare number is not a token either.
    """
    loose = _loosen(strip_citations(text))
    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, value: str) -> None:
        item = (kind, value)
        if item not in seen:
            seen.add(item)
            found.append(item)

    for match in _MEASURE_WITH_UNIT.finditer(loose):
        add("measure", _canon_measure(match.group(1), match.group(2), match.group(3)))
    for match in _STANDARD_CODE.finditer(loose):
        add("code", match.group(1))
    for match in _FILE_TOKEN.finditer(loose):
        add("file", match.group(0).casefold())
    for match in _DOTTED_FIELD.finditer(loose):
        if _FILE_TOKEN.fullmatch(match.group(0)):
            continue
        add("field", match.group(0))
    for match in _FILTER_EXPR.finditer(loose):
        add("filter", _compact(match.group(0)))
    return found


def _token_in(kind: str, value: str, passage: str) -> bool:
    loose = _loosen(passage)
    if kind == "measure":
        present = {
            _canon_measure(match.group(1), match.group(2), match.group(3))
            for match in _MEASURE_WITH_UNIT.finditer(loose)
        }
        if value in present:
            return True
        # "0.5 LU" is the same figure as "±0.5 LU". A minus is not.
        if value[:1] not in "-±":
            return f"±{value}" in present
        return False
    if kind == "code":
        return re.search(rf"\btech\s*{re.escape(value)}\b", loose) is not None
    if kind == "filter":
        return value in _compact(loose)
    return re.search(rf"(?<!\w){re.escape(value)}(?!\w)", loose) is not None


def _passage_supports(
    tokens: list[tuple[str, str]], passage: str
) -> list[tuple[str, str]]:
    return [token for token in tokens if _token_in(token[0], token[1], passage)]


def supporting_sources(answer: str, sources: list[dict]) -> list[dict]:
    """Keep the passages that contain the reply's technical tokens.

    The model's own [n] markers are the starting point. A token that is missing
    from the cited passage is re-attributed to another retrieved passage that
    has it. A token that is in none of them drops the citation. Ordinary words
    in parentheses are ignored. A reply that never writes a source number is
    not given one afterwards.
    """
    if not answer or _REFUSAL.search(answer):
        return []
    cited = [
        number for number in cited_source_indexes(answer) if 1 <= number <= len(sources)
    ]
    if not cited:
        return []
    tokens = technical_tokens(answer)
    if not tokens:
        chosen = []
        for number in cited:
            source = dict(sources[number - 1])
            source["number"] = number
            chosen.append(source)
        return chosen
    kept: list[int] = []
    covered: set[tuple[str, str]] = set()
    for number in cited:
        held = _passage_supports(tokens, sources[number - 1].get("text", ""))
        if not held:
            continue
        kept.append(number - 1)
        covered.update(held)
    for token in tokens:
        if token in covered:
            continue
        for index, source in enumerate(sources):
            if not _token_in(token[0], token[1], source.get("text", "")):
                continue
            if index not in kept:
                kept.append(index)
            covered.add(token)
            break
        else:
            return []
    chosen = []
    for index in kept:
        source = dict(sources[index])
        source["number"] = index + 1
        chosen.append(source)
    return chosen


# Calibrated on main-set sentences against the cited passage (bge-m3, best 700-character
# window). Relevant sentences, including Spanish and French, scored about 0.60 to 0.76.
# An SRT incident draft against the television pages scored about 0.45 to 0.49.
CITATION_MIN_SIMILARITY = 0.55


def passage_windows(text: str, size: int = 700, step: int = 350) -> list[str]:
    """Overlapping slices of a passage, so a short sentence can match one part of it."""
    folded = " ".join((text or "").split())
    if not folded:
        return []
    if len(folded) <= size:
        return [folded]
    cuts = []
    start = 0
    while start < len(folded):
        cuts.append(folded[start : start + size])
        if start + size >= len(folded):
            break
        start += step
    return cuts


def citing_sentence(answer: str, number: int) -> str:
    """The sentence that carries this source number, without the marker.

    A marker that sits after the full stop, or alone on the next line, still
    belongs to that sentence. A draft with no full stops is scored a line at
    a time, so a trailing marker is not compared with the whole draft.
    """
    parts = re.split(r"(?<=[.!?])\s+|\n+", (answer or "").strip())
    merged: list[str] = []
    for part in parts:
        if merged and re.fullmatch(r"(?:\[\d+\]\s*)+", part):
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    hits = [part for part in merged if re.search(rf"\[{number}\]", part)]
    return _CITATION.sub("", " ".join(hits)).strip()


def keep_close_citations(answer: str, sources: list[dict], score) -> list[dict]:
    """Drop a citation whose sentence is not close to the cited passage.

    A citation the model did not write has no sentence to compare, so the
    technical-token check stands. `score` returns the bge-m3 similarity.
    """
    kept = []
    for source in sources:
        number = int(source.get("number") or 0)
        if not re.search(rf"\[{number}\]", answer or ""):
            kept.append(source)
            continue
        sentence = citing_sentence(answer, number)
        if (
            sentence
            and float(score(sentence, source.get("text") or ""))
            >= CITATION_MIN_SIMILARITY
        ):
            kept.append(source)
    return kept


def source_label(source: dict) -> str:
    """Show the folder and file, and the page when the reader stored one."""
    path = source.get("path") or source.get("source") or "Document"
    page = source.get("page")
    if page not in (None, ""):
        return f"{path} · p. {page}"
    return str(path)


def library_miss(answer: str, query: str = "") -> str:
    """Use the model's refusal when it already admits the gap."""
    cleaned = strip_citations(answer)
    if cleaned and _REFUSAL.search(answer or ""):
        return cleaned
    return user_line("not_covered", query)


def strip_citations(text: str) -> str:
    """Remove source markers when the reply is not grounded in the library."""
    return _CITATION.sub("", text or "").strip()


def grounded_in_sources(answer: str, source_texts: list[str]) -> bool:
    """True when the reply cites the library and its wording appears in those sources."""
    if not answered_from_sources(answer):
        return False
    cleaned = _CITATION.sub(" ", answer.lower())
    words = [word for word in _WORD.findall(cleaned) if word not in _STOP]
    if len(words) < 2:
        return False
    blob = " ".join(source_texts).lower()
    hits = sum(1 for word in words if word in blob)
    return hits >= 2


CITATION_QA_TEMPLATE = citation_prompt([])
