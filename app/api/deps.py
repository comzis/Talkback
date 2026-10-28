"""Helpers shared by the API routers."""

from pathlib import Path

from fastapi import HTTPException

import engine
import store.embeddings as embeddings
from llm.client import OllamaOnly, reject_unless_ollama

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _ollama_only() -> None:
    """Block model list, select, and pull when chat is a vLLM server."""
    try:
        reject_unless_ollama()
    except OllamaOnly as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _reject_if_reindex_required() -> None:
    if engine.reindex_required():
        raise HTTPException(status_code=409, detail=embeddings.REINDEX_MESSAGE)
