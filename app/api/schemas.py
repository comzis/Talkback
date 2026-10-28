"""Request and response models for the HTTP API."""

from pydantic import BaseModel


class ChatTurn(BaseModel):
    role: str
    content: str


class QueryRequest(BaseModel):
    query: str
    history: list[ChatTurn] = []
    # Relative path of a file or folder. Empty / omitted = whole library.
    scope: str | None = None


class QueryResponse(BaseModel):
    response: str
    sources: list[dict]
    notice: str | None = None
    footnote: str | None = None


class LLMSelectRequest(BaseModel):
    model: str


class LLMPullRequest(BaseModel):
    model: str
