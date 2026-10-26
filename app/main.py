"""Process entry. Uvicorn loads main:app."""

from api.app import app

__all__ = ["app"]
