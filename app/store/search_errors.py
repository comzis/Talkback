"""Shared errors when library search cannot run safely."""


class SearchUnavailable(Exception):
    """Host embed/rerank is down and the in-container fallback cannot run.

    Callers should tell the user search is temporarily unavailable rather than
    answering from general knowledge as if the library had been searched.
    """
