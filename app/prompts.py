"""Prompt text for grounded answers."""

import re

_CITATION = re.compile(r"\[\d+\]")
_WORD = re.compile(r"[a-z0-9]{4,}")
_REFUSAL = re.compile(
    r"cannot find|can't find|do not contain|does not contain|don't contain|"
    r"not in the (retrieved|uploaded|library|sources|documents)",
    re.IGNORECASE,
)
_STOP = {
    "that", "this", "with", "from", "your", "have", "what", "when", "where",
    "which", "about", "there", "their", "would", "could", "should", "into",
    "using", "does", "they", "them", "than", "then", "also", "just", "only",
    "some", "such", "answer", "question",
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


def assistant_prompt(query: str) -> str:
    """Prompt for a direct assistant reply with no document requirement."""
    return (
        "You are Talkback, a helpful assistant. Reply the way a person would in a conversation.\n"
        "Keep it short and natural. Use plain sentences.\n"
        "Do not use markdown, headings, or a numbered manual unless the user asked for steps.\n"
        "Do not mention documents, a library, or sources.\n"
        "If they pasted a passage, explain it briefly in your own words.\n\n"
        f"User:\n{query}\n"
        "Assistant:"
    )


_GENERIC_FILE_WORDS = {
    "python", "basics", "notes", "guide", "skills", "document", "documents",
    "manual", "intro", "introduction", "overview", "draft",
    "final", "report", "slides", "sheet",
}
_SMALL_TALK = re.compile(
    r"^(hi|hello|hey|thanks|thank you|ok|okay|yo|good morning|good afternoon|good evening)\b",
    re.IGNORECASE,
)


def named_library_files(query: str, library_files: list[str]) -> list[str]:
    """Return library filenames the question actually names."""
    lowered = (query or "").lower()
    matched = []
    for name in library_files:
        full = name.lower()
        stem = full.rsplit(".", 1)[0].strip()
        tokens = re.findall(r"[a-z0-9]{5,}", stem)
        named = (full and full in lowered) or (len(stem) >= 4 and stem in lowered)
        named = named or any(token in lowered and token not in _GENERIC_FILE_WORDS for token in tokens)
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
        "document", "documents", "library", "uploaded", "pdf", "according to",
        "in the file", "in my file", "the source", "cite ", "from the doc",
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


def explanation_prompt(query: str, library_files: list[str], excerpts: list[str]) -> str:
    """Prompt that explains pasted text and reasons only with library excerpts."""
    names = ", ".join(library_files) if library_files else "(none yet)"
    shown = "\n\n".join(f"[{index}] {text}" for index, text in enumerate(excerpts, 1))
    if not shown:
        shown = "(no matching excerpts)"
    return (
        "You are Talkback. The user is asking about their documents or pasted a passage.\n"
        f"The library contains: {names}.\n"
        "If the user pasted a passage, explain that text in plain language and walk through the lines.\n"
        "Answer from the library excerpts below. Do not add facts from outside those excerpts.\n"
        "End the answer with the excerpt number in brackets, such as [1].\n"
        "If the excerpts do not contain the answer, say that the library does not cover it and do not cite a number.\n"
        "Keep the reply short. Use plain sentences, not a markdown manual.\n\n"
        f"Library excerpts:\n{shown}\n\n"
        f"User:\n{query}\n"
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


def _has_word(haystack: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", haystack) is not None


def _excerpt_supports(answer: str, text: str) -> bool:
    """True when the reply repeats distinctive wording from one excerpt."""
    cleaned = strip_citations(answer).lower()
    words = [
        word for word in _WORD.findall((text or "").lower())
        if word not in _STOP and len(word) >= 5
    ]
    hits = sum(1 for word in dict.fromkeys(words) if _has_word(cleaned, word))
    return hits >= 2


def supporting_sources(answer: str, sources: list[dict]) -> list[dict]:
    """Keep excerpts whose wording the reply uses, preferring numbers it cited."""
    if not answer or _REFUSAL.search(answer):
        return []
    cited = [number for number in cited_source_indexes(answer) if 1 <= number <= len(sources)]
    pool = cited or list(range(1, len(sources) + 1))
    chosen = []
    for number in pool:
        source = dict(sources[number - 1])
        if not _excerpt_supports(answer, source.get("text", "")):
            continue
        source["number"] = number
        chosen.append(source)
    return chosen[:2] if not cited else chosen


def source_label(source: dict) -> str:
    """Show the folder and file, and the page when the reader stored one."""
    path = source.get("path") or source.get("source") or "Document"
    page = source.get("page")
    if page not in (None, ""):
        return f"{path} · p. {page}"
    return str(path)


def library_miss(answer: str) -> str:
    """Use the model's refusal when it already admits the gap."""
    cleaned = strip_citations(answer)
    if cleaned and _REFUSAL.search(answer or ""):
        return cleaned
    return "The library does not cover that."


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
