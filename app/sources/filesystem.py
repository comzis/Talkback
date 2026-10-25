"""The mounted folder as a Source. Relative paths, hidden files, and read-only refusal."""

from __future__ import annotations

import os
from pathlib import Path

from ingestion.plan import library_key, read_only_requested
from sources.base import ReadOnlyLibrary, SourceItem


class InvalidFilename(ValueError):
    """Raised when a client filename cannot be stored safely."""


def safe_relative_path(filename: str | None) -> str:
    """Keep a relative library path and reject anything that leaves the data directory."""
    original = (filename or "").strip()
    if original.startswith("/") or original.startswith("\\"):
        raise InvalidFilename("Invalid filename")
    raw = original.replace("\\", "/").strip().lstrip("/")
    if not raw or raw in {".", ".."}:
        raise InvalidFilename("Invalid filename")
    parts = Path(raw).parts
    if any(part in {"", ".", ".."} or part.startswith(".") for part in parts):
        raise InvalidFilename("Invalid filename")
    return Path(*parts).as_posix()


def stored_filename(filename: str | None) -> str:
    """Keep a single path segment so a name cannot leave the data directory."""
    name = Path(filename or "").name.strip()
    if not name or name in {".", ".."}:
        raise InvalidFilename("Invalid filename")
    return name


def is_hidden(path: Path, root: Path) -> bool:
    """True when any path segment is a dotfile, including .gitkeep."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path
    return any(part.startswith(".") for part in relative.parts)


def visible_files(root: Path) -> list[Path]:
    """Files under root that ingest and the library list should show."""
    if not root.exists():
        return []
    files = []
    for path in root.rglob("*"):
        if path.is_file() and not is_hidden(path, root):
            files.append(path)
    return files


class FilesystemSource:
    """Today's library folder. Item ids are relative paths."""

    source_type = "filesystem"

    def __init__(self, root: Path, read_only: bool = False) -> None:
        self.root = root
        self.read_only = read_only

    def list_items(self) -> list[SourceItem]:
        items = []
        for path in visible_files(self.root):
            stat = path.stat()
            items.append(
                SourceItem(
                    id=library_key(path, self.root),
                    location=str(path),
                    title=path.name,
                    modified=stat.st_mtime,
                    size=int(stat.st_size),
                )
            )
        return items

    def read(self, locations: list[str]) -> list:
        """Same reader the ingest path used before this source existed."""
        if not locations:
            return []
        from llama_index.core import SimpleDirectoryReader

        return SimpleDirectoryReader(input_files=list(locations)).load_data()

    def deleted_ids(self, known_ids: set[str]) -> list[str]:
        present = {item.id for item in self.list_items()}
        return sorted(known_ids - present)

    def ensure_writable(self, action: str) -> None:
        if self.read_only:
            raise ReadOnlyLibrary(action)


def filesystem_source() -> FilesystemSource:
    """The library folder for this process."""
    from state import get

    return FilesystemSource(
        get().upload_dir,
        read_only=read_only_requested(os.getenv("LIBRARY_READ_ONLY")),
    )


def get_file_type(filename: str) -> str:
    """Return document, code, data, image, or other from the extension."""
    ext = Path(filename).suffix.lower()
    doc_exts = {".pdf", ".doc", ".docx", ".odt", ".txt", ".md", ".rst", ".rtf", ".epub"}
    code_exts = {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".cpp",
        ".c",
        ".h",
        ".go",
        ".rs",
        ".php",
        ".rb",
        ".swift",
        ".kt",
        ".sh",
        ".bash",
        ".zsh",
        ".yaml",
        ".yml",
        ".html",
        ".css",
        ".scss",
        ".less",
    }
    data_exts = {".xlsx", ".xls", ".csv", ".json", ".xml"}
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"}
    pres_exts = {".pptx", ".ppt", ".odp"}

    if ext in doc_exts or ext in pres_exts:
        return "document"
    if ext in code_exts:
        return "code"
    if ext in data_exts:
        return "data"
    if ext in image_exts:
        return "image"
    return "other"
