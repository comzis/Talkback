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
        "You are a helpful assistant. The user can ask a question or paste lines of text.\n"
        "If they pasted a passage, explain what it says and walk through the lines.\n"
        "Answer directly in plain language. Do not say you are waiting for a document.\n\n"
        f"User:\n{query}\n"
        "Assistant:"
    )


def explanation_prompt(query: str, library_files: list[str], excerpts: list[str]) -> str:
    """Prompt that explains pasted text and reasons with library excerpts."""
    names = ", ".join(library_files) if library_files else "(none yet)"
    shown = "\n\n".join(f"[{index}] {text}" for index, text in enumerate(excerpts, 1))
    if not shown:
        shown = "(no matching excerpts)"
    return (
        "You are a helpful assistant. The user can ask a question or paste lines from a document.\n"
        f"The library contains: {names}.\n"
        "If the user pasted a passage, explain that text in plain language and walk through the lines.\n"
        "Reason with the library excerpts when they relate to the passage or question, "
        "and cite each claim with a source number such as [1] or [2].\n"
        "If the excerpts do not apply, explain or answer from your own knowledge and do not cite them.\n"
        "Do not say you are waiting for a document.\n\n"
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


def supporting_sources(answer: str, sources: list[dict]) -> list[dict]:
    """Keep excerpts the reply cites, or excerpts whose wording the reply explains."""
    texts = [source.get("text", "") for source in sources]
    if grounded_in_sources(answer, texts):
        chosen = [
            sources[number - 1]
            for number in cited_source_indexes(answer)
            if 1 <= number <= len(sources)
        ]
        return chosen or sources
    cleaned = strip_citations(answer).lower()
    kept = []
    for source in sources:
        words = [
            word for word in _WORD.findall(source.get("text", "").lower())
            if word not in _STOP and len(word) >= 5
        ]
        hits = sum(1 for word in words if word in cleaned)
        if hits >= 2:
            kept.append(source)
    return kept


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
