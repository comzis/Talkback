"""Report what Talkback would do with the files in a folder.

Usage, from the repository root:

    python scripts/inventory.py /path/to/library
    python scripts/inventory.py tests/fixtures/inventory

Counts files by extension, totals the size, flags PDFs with almost no
extractable text (likely scans), and groups each file as index, index
poorly, or skip. Hidden paths and macOS sidecars match
app/sources/filesystem.py. This script does not change any file.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

# Keep these sets aligned with app/sources/filesystem.get_file_type.
_DOC = {".pdf", ".doc", ".docx", ".odt", ".txt", ".md", ".rst", ".rtf", ".epub"}
_PRES = {".pptx", ".ppt", ".odp"}
_CODE = {
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
_DATA = {".xlsx", ".xls", ".csv", ".json", ".xml"}
_IMAGE = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"}
# A PDF with fewer extractable characters per page is treated as a scan.
_SCAN_CHARS_PER_PAGE = 40
_SCAN_MIN_CHARS = 80


def is_hidden(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path
    return any(part.startswith(".") for part in relative.parts)


def is_macos_metadata(path: Path) -> bool:
    return path.name == ".DS_Store" or path.name.startswith("._")


def file_kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _DOC or ext in _PRES:
        return "document"
    if ext in _CODE:
        return "code"
    if ext in _DATA:
        return "data"
    if ext in _IMAGE:
        return "image"
    return "other"


def walk_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def pdf_text_stats(path: Path) -> tuple[int | None, int | None]:
    """Return (character count, page count). None means the tool failed."""
    if shutil.which("pdftotext"):
        try:
            text = subprocess.check_output(
                ["pdftotext", "-q", str(path), "-"],
                stderr=subprocess.DEVNULL,
                timeout=60,
            )
            pages = subprocess.check_output(
                ["pdfinfo", str(path)],
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
            page_count = None
            for line in pages.decode("utf-8", errors="replace").splitlines():
                if line.lower().startswith("pages:"):
                    page_count = int(line.split(":", 1)[1].strip())
                    break
            return len(text.decode("utf-8", errors="replace").strip()), page_count
        except (subprocess.SubprocessError, ValueError, OSError):
            pass
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        chars = 0
        for page in reader.pages:
            chars += len((page.extract_text() or "").strip())
        return chars, len(reader.pages)
    except Exception:
        return None, None


def is_scan_pdf(path: Path) -> bool | None:
    """True when the PDF has almost no extractable text. None if unknown."""
    if path.suffix.lower() != ".pdf":
        return False
    chars, pages = pdf_text_stats(path)
    if chars is None:
        return None
    if pages is None or pages < 1:
        pages = 1
    if chars < _SCAN_MIN_CHARS:
        return True
    return (chars / pages) < _SCAN_CHARS_PER_PAGE


def fate(path: Path, root: Path) -> str:
    """index, index_poorly, or skip."""
    if is_hidden(path, root) or is_macos_metadata(path):
        return "skip"
    if path.stat().st_size == 0:
        return "index_poorly"
    kind = file_kind(path)
    if kind == "image":
        return "index_poorly"
    if kind == "other":
        return "skip"
    if path.suffix.lower() == ".pdf":
        scan = is_scan_pdf(path)
        if scan is True:
            return "index_poorly"
        if scan is None:
            return "index_poorly"
    if kind in {"code", "data"}:
        return "index_poorly"
    return "index"


def inventory(root: Path) -> dict:
    root = root.resolve()
    files = walk_files(root)
    by_ext: Counter[str] = Counter()
    by_fate: dict[str, list[dict]] = {
        "index": [],
        "index_poorly": [],
        "skip": [],
    }
    total_size = 0
    scans: list[str] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        size = path.stat().st_size
        total_size += size
        ext = path.suffix.lower() or "(none)"
        by_ext[ext] += 1
        decision = fate(path, root)
        scan = is_scan_pdf(path) if path.suffix.lower() == ".pdf" else False
        if scan is True:
            scans.append(rel)
        by_fate[decision].append(
            {
                "path": rel,
                "size": size,
                "kind": file_kind(path),
                "scan_pdf": scan is True,
            }
        )
    return {
        "root": str(root),
        "file_count": len(files),
        "total_size": total_size,
        "by_extension": dict(sorted(by_ext.items())),
        "scan_pdfs": scans,
        "index": by_fate["index"],
        "index_poorly": by_fate["index_poorly"],
        "skip": by_fate["skip"],
    }


def _size_label(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n / 1024:.1f} KiB"
    if n < 1024**3:
        return f"{n / 1024**2:.1f} MiB"
    return f"{n / 1024**3:.2f} GiB"


def format_report(data: dict) -> str:
    lines = [
        f"Library: {data['root']}",
        f"Files: {data['file_count']}  Total size: {_size_label(data['total_size'])}",
        "",
        "By extension:",
    ]
    for ext, count in data["by_extension"].items():
        lines.append(f"  {ext}: {count}")
    lines.append("")
    if data["scan_pdfs"]:
        lines.append("PDFs with little or no text layer (likely scans):")
        for path in data["scan_pdfs"]:
            lines.append(f"  {path}")
    else:
        lines.append("PDFs with little or no text layer (likely scans): none")
    for label, key in (
        ("Would index well", "index"),
        ("Would index poorly", "index_poorly"),
        ("Would skip", "skip"),
    ):
        items = data[key]
        lines.append("")
        lines.append(f"{label} ({len(items)}):")
        if not items:
            lines.append("  (none)")
            continue
        for item in items:
            note = "  [scan]" if item.get("scan_pdf") else ""
            lines.append(
                f"  {item['path']}  {_size_label(item['size'])}  {item['kind']}{note}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Library folder to inspect")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the machine-readable inventory instead of the text report",
    )
    args = parser.parse_args(argv)
    if not args.folder.exists():
        print(f"Folder not found: {args.folder}", file=sys.stderr)
        return 1
    if not args.folder.is_dir():
        print(f"Not a folder: {args.folder}", file=sys.stderr)
        return 1
    data = inventory(args.folder)
    if args.json:
        import json

        print(json.dumps(data, indent=2))
    else:
        print(format_report(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
