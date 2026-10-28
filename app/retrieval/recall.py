"""Which retrieved page holds the fact. No chat model is involved."""

from __future__ import annotations


def fact_pages(case: dict) -> list[str]:
    """Pages that contain the answer. An empty list means the library has none."""
    raw = case.get("pages", case.get("page"))
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        return [raw]
    return [str(page) for page in raw if str(page)]


def search_text(case: dict, by_id: dict[str, dict]) -> str:
    """The text the app would embed for this question, including a follow-up's topic."""
    from llm.followups import retrieval_text

    parent_id = case.get("continues")
    if not parent_id:
        return retrieval_text(case["query"])
    parent = by_id[parent_id]
    history = [{"role": "user", "content": parent["query"]}]
    return retrieval_text(case["query"], history)


def first_hit(
    ranked: list[tuple[str, str]], file_name: str, pages: list[str]
) -> int | None:
    """1-based rank of the first hit on the expected file and page."""
    wanted = set(pages)
    if not file_name or not wanted:
        return None
    for index, (name, page) in enumerate(ranked, start=1):
        if name == file_name and page in wanted:
            return index
    return None


def recall_at(ranks: list[int | None], k: int) -> tuple[int, int]:
    """How many questions place a fact page inside the first k hits."""
    hits = sum(rank is not None and rank <= k for rank in ranks)
    return hits, len(ranks)
