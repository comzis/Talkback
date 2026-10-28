"""Conversation history, continuation cues, and library routing."""

import re
import unicodedata

from llm._text import (
    _FILE_TOKEN_STOP,
    _STOP,
    strip_citations,
    _WORD,
)


def clean_history(history, limit: int = 8) -> list[tuple[str, str]]:
    """Keep the latest user and assistant turns. Each turn is capped so the prompt stays small.

    Pure greeting / small-talk assistant turns are dropped so they cannot leak
    into a later library answer.
    """
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
        if role == "assistant" and _is_greeting_only(text):
            continue
        turns.append((role, text[:400]))
    return turns[-limit:]


def _is_greeting_only(text: str) -> bool:
    """True when the whole turn is a greeting or thanks, not an answer."""
    cleaned = strip_citations(text or "").strip()
    if not cleaned:
        return True
    if len(cleaned) > 120 or not _SMALL_TALK.match(cleaned):
        return False
    words = re.findall(r"[a-z0-9']+", cleaned.casefold())
    return len(words) <= 12


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
    "edition",
    "volume",
    "chapter",
    "book",
    "pdf",
}


# A filename token may match at most this share of library files (IDF-style).
_FILE_TOKEN_MAX_SHARE = 0.1


_SMALL_TALK = re.compile(
    r"^(hi|hello|hey|thanks|thank you|ok|okay|yo|good morning|good afternoon|good evening|"
    r"bonjour|salut|merci|hola|gracias|buenos dias|buenas tardes)\b",
    re.IGNORECASE,
)


def _filename_tokens(name: str) -> list[str]:
    """Length ≥ 4 tokens from the file stem (basename, no extension)."""
    stem = name.lower().rsplit("/", 1)[-1].rsplit(".", 1)[0].strip()
    return re.findall(r"[a-z0-9]{4,}", stem)


def _filename_token_df(library_files: list[str]) -> dict[str, int]:
    """How many library paths contain each filename token."""
    counts: dict[str, int] = {}
    for name in library_files:
        for token in set(_filename_tokens(name)):
            counts[token] = counts.get(token, 0) + 1
    return counts


def _distinctive_filename_token(
    token: str, library_size: int, doc_freq: dict[str, int]
) -> bool:
    """True when a token is rare enough across filenames to identify a file."""
    if len(token) < 4:
        return False
    if token in _FILE_TOKEN_STOP or token in _GENERIC_FILE_WORDS:
        return False
    if library_size <= 0:
        return True
    limit = max(1, int(library_size * _FILE_TOKEN_MAX_SHARE))
    return doc_freq.get(token, 0) <= limit


def _names_file(token: str, lowered: str) -> bool:
    """True when a filename token appears in the question as its own word."""
    if token in _GENERIC_FILE_WORDS or token in _FILE_TOKEN_STOP:
        return False
    if len(token) < 4:
        return False
    return re.search(rf"\b{re.escape(token)}\b", lowered) is not None


def named_library_files(query: str, library_files: list[str]) -> list[str]:
    """Return library filenames the question actually names.

    A token counts only when it is distinctive: not an en/fr/es stopword, at
    least four characters, and present in at most a small share of filenames.
    """
    lowered = (query or "").lower()
    size = len(library_files)
    doc_freq = _filename_token_df(library_files)
    matched = []
    for name in library_files:
        full = name.lower()
        stem = full.rsplit(".", 1)[0].strip()
        if (full and full in lowered) or (len(stem) >= 4 and stem in lowered):
            matched.append(name)
            continue
        tokens = _filename_tokens(name)
        if any(
            _distinctive_filename_token(token, size, doc_freq)
            and _names_file(token, lowered)
            for token in tokens
        ):
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
