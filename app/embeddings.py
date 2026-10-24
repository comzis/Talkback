"""Embedding-model identity and the e5 prefixes.

HuggingFaceEmbedding.format_query and format_text join an instruction with
one space and then strip:

    f"{instruction} {text}".strip()

Pass "query:" and "passage:" with no trailing space. The strings that get
embedded are then exactly "query: <text>" and "passage: <text>".
"""

from __future__ import annotations

LEGACY_EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_META_KEY = "embed_model"
REINDEX_MESSAGE = (
    "Full re-index needed. The embedding model changed, so the current vectors cannot be queried."
)


def is_e5(model_name: str) -> bool:
    return "e5" in (model_name or "").lower()


def query_instruction(model_name: str) -> str | None:
    """Prefix token for questions. None lets the embedder use its own default."""
    if is_e5(model_name):
        return "query:"
    return None


def text_instruction(model_name: str) -> str | None:
    """Prefix token for indexed chunks. None lets the embedder use its own default."""
    if is_e5(model_name):
        return "passage:"
    return None


def join_instruction(instruction: str, text: str) -> str:
    """Match the installed HuggingFaceEmbedding join: one space, then strip."""
    return f"{instruction} {text}".strip()


def embedded_query(model_name: str, text: str) -> str:
    instruction = query_instruction(model_name)
    if not instruction:
        return text
    return join_instruction(instruction, text)


def embedded_passage(model_name: str, text: str) -> str:
    instruction = text_instruction(model_name)
    if not instruction:
        return text
    return join_instruction(instruction, text)


def collection_embed_model(metadata: dict | None, count: int) -> str | None:
    """Model that wrote the vectors. Empty collections have nothing to compare.

    Vectors with no recorded name were written by BAAI/bge-small-en-v1.5.
    """
    if count <= 0:
        return None
    stored = (metadata or {}).get(EMBED_META_KEY)
    if stored:
        return str(stored)
    return LEGACY_EMBED_MODEL


def full_reindex_required(metadata: dict | None, count: int, current: str) -> bool:
    stored = collection_embed_model(metadata, count)
    if stored is None:
        return False
    return stored != current
