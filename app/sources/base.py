"""What every library source has to provide. A source does not know the user."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SourceItem:
    """One listable thing. `id` stays stable when the title changes."""

    id: str
    location: str
    title: str
    modified: float
    size: int


class ReadOnlyLibrary(PermissionError):
    """Raised when a source refuses an upload or a delete."""

    def __init__(self, action: str) -> None:
        self.action = action
        super().__init__(action)


class Source(Protocol):
    """List items, read their text, and say which known ids have gone."""

    source_type: str

    def list_items(self) -> list[SourceItem]:
        """Items currently available, using each item's stable id."""

    def read(self, locations: list[str]) -> list:
        """Text for those locations. Page numbers live on each result's metadata when the reader has them."""

    def deleted_ids(self, known_ids: set[str]) -> list[str]:
        """Known ids that are no longer in list_items, in a stable order."""

    def ensure_writable(self, action: str) -> None:
        """Raise ReadOnlyLibrary when this source cannot accept an upload or a delete."""
