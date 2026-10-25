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


def read_only_requested(value: str | None) -> bool:
    """True only when LIBRARY_READ_ONLY is explicitly enabled. Default is writable."""
    if value is None or not str(value).strip():
        return False
    return str(value).strip().lower() in {"1", "true", "yes"}


def reindex_minutes(value: str | None) -> int | None:
    """Return a positive interval, or None when scheduled re-indexing is off."""
    if value is None or not str(value).strip():
        return None
    minutes = int(str(value).strip())
    return minutes if minutes > 0 else None


def library_key(path: Path, root: Path) -> str:
    """Return the posix path of a library file relative to the data root."""
    return path.resolve().relative_to(root.resolve()).as_posix()


def chunk_key(metadata: dict | None) -> str | None:
    """Return the library path stored on a chunk, or the old file name."""
    metadata = metadata or {}
    relative = str(metadata.get("relative_path") or "").replace("\\", "/").strip()
    if relative:
        return relative
    name = str(metadata.get("file_name") or "").replace("\\", "/").strip()
    if name and "/" not in name:
        return name
    return None


def chunk_is_legacy(metadata: dict | None) -> bool:
    """True when a chunk was indexed before relative paths were stored."""
    return not str((metadata or {}).get("relative_path") or "").strip()


def chunk_is_complete(metadata: dict | None) -> bool:
    """True when this chunk was stored after the whole file had been embedded."""
    value = (metadata or {}).get("index_complete")
    if value is True:
        return True
    return str(value).strip().lower() in {"1", "true", "yes"}


def classify_stored_chunks(
    metadatas: list[dict | None],
) -> tuple[dict[str, tuple], set[str], set[str]]:
    """Split stored chunks into complete signatures, legacy keys, and unfinished files.

    A file counts as indexed only when every one of its chunks has index_complete.
    Chunks written before that marker, including a crash mid-file, are unfinished.
    """
    complete: dict[str, tuple] = {}
    legacy: set[str] = set()
    all_complete: dict[str, bool] = {}
    for metadata in metadatas:
        key = chunk_key(metadata)
        if not key:
            continue
        if chunk_is_legacy(metadata):
            legacy.add(key)
        finished = chunk_is_complete(metadata)
        all_complete[key] = (
            finished if key not in all_complete else all_complete[key] and finished
        )
        if finished and key not in complete:
            complete[key] = indexed_signature(metadata)
    incomplete = {key for key, finished in all_complete.items() if not finished}
    for key in incomplete:
        complete.pop(key, None)
    return complete, legacy, incomplete


def chunk_belongs_to(metadata: dict | None, relative_path: str) -> bool:
    """True when a chunk came from this library path and no other file of the same name."""
    metadata = metadata or {}
    target = relative_path.replace("\\", "/").strip()
    stored = str(metadata.get("relative_path") or "").replace("\\", "/").strip()
    if stored:
        return stored == target
    name = str(metadata.get("file_name") or "").strip()
    return bool(name) and "/" not in target and name == target


def index_plan(
    on_disk: dict[str, tuple],
    indexed: dict[str, tuple],
    legacy_keys: set[str] | None = None,
    incomplete_keys: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Plan embeds and drops, and rewrite legacy or unfinished files.

    Existing indexes stored only file_name. Those chunks are removed and embedded
    again once, so the new metadata carries relative_path. A file that moved to a
    new relative path is a drop of the old key plus an embed of the new one.
    A file with any chunk missing index_complete is removed and embedded again.
    """
    embed, drop = plan_updates(on_disk, indexed)
    rewrite = set(legacy_keys or ()) | set(incomplete_keys or ())
    for key in sorted(rewrite):
        if key in on_disk and key not in embed:
            embed.append(key)
        if key not in drop:
            drop.append(key)
    return embed, drop


def plan_updates(
    on_disk: dict[str, tuple], indexed: dict[str, tuple]
) -> tuple[list[str], list[str]]:
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
        name = metadata.get("relative_path") or metadata.get("file_name") or "Document"
        if counts.get(name, 0) >= per_file:
            continue
        selected.append(node)
        counts[name] = counts.get(name, 0) + 1
        if len(selected) >= limit:
            break
    return selected
