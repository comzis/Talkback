"""Decide which library files to add, update, or leave in the index."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def disk_signature(path: Path) -> tuple:
    """Return size, calendar day, and mtime for a file on disk."""
    stat = path.stat()
    day = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")
    return (int(stat.st_size), day, int(stat.st_mtime))


def indexed_signature(metadata: dict) -> tuple:
    """Return the signature stored on an indexed chunk."""
    size = int(metadata.get("file_size") or 0)
    day = str(metadata.get("last_modified_date") or "")
    mtime = metadata.get("source_mtime")
    return (size, day, int(mtime) if mtime is not None else None)


def same_version(on_disk: tuple, indexed: tuple) -> bool:
    """True when an indexed file still matches the copy on disk."""
    if on_disk[0] != indexed[0]:
        return False
    if indexed[2] is not None:
        return int(on_disk[2]) == int(indexed[2])
    return on_disk[1] == indexed[1]


def plan_updates(on_disk: dict[str, tuple], indexed: dict[str, tuple]) -> tuple[list[str], list[str]]:
    """Return files to embed and files whose old chunks should be removed.

    New files are embedded. Changed files are removed and embedded again.
    Files that disappeared from disk are removed. Unchanged files stay indexed.
    """
    embed: list[str] = []
    drop: list[str] = []
    for name, signature in on_disk.items():
        current = indexed.get(name)
        if current is None:
            embed.append(name)
        elif not same_version(signature, current):
            embed.append(name)
            drop.append(name)
    for name in indexed:
        if name not in on_disk:
            drop.append(name)
    return embed, drop


def balance_matches(nodes, per_file: int = 2, limit: int = 4):
    """Keep the best matches without letting one file take every slot."""
    selected = []
    counts: dict[str, int] = {}
    for node in nodes:
        metadata = getattr(node, "metadata", None) or {}
        name = metadata.get("file_name") or "Document"
        if counts.get(name, 0) >= per_file:
            continue
        selected.append(node)
        counts[name] = counts.get(name, 0) + 1
        if len(selected) >= limit:
            break
    return selected
