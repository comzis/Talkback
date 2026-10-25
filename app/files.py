"""Filename rules shared by uploads, listing, and deletion."""

from pathlib import Path


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
