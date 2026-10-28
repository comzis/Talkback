"""Notices, question language, and general-knowledge labelling."""

import re

from llm.followups import (
    clean_history,
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
    "search_unavailable": {
        "en": (
            "Search is temporarily unavailable. The host embedder is down and "
            "the backup model could not be loaded."
        ),
        "fr": (
            "La recherche est temporairement indisponible. L'embedder hôte est "
            "indisponible et le modèle de secours n'a pas pu être chargé."
        ),
        "es": (
            "La búsqueda no está disponible temporalmente. El embedder del host "
            "está caído y no se pudo cargar el modelo de respaldo."
        ),
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
