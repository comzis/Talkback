"""Shared errors when library search cannot run safely."""


class SearchUnavailable(Exception):
    """Host embed/rerank is required and that service is unreachable.

    Callers should tell the user search is temporarily unavailable rather than
    answering from general knowledge as if the library had been searched.
    """
