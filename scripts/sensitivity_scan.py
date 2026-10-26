"""Report-only scan for common secrets and personal data in a folder.

Usage, from the repository root:

    python scripts/sensitivity_scan.py /path/to/library
    python scripts/sensitivity_scan.py tests/fixtures/sensitivity

Looks for credentials, API keys, private keys, IP and MAC addresses,
email addresses, and phone numbers. It does not change any file. Binary
and image files are skipped. Output is one short block per file that
had a hit, plus a summary.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_TEXT_EXT = {
    ".txt",
    ".md",
    ".rst",
    ".csv",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".py",
    ".js",
    ".ts",
    ".sh",
    ".bash",
    ".zsh",
    ".env",
    ".ini",
    ".cfg",
    ".conf",
    ".html",
    ".css",
    ".sql",
    ".log",
    ".pdf",
    ".docx",
    ".doc",
    ".odt",
    ".rtf",
    ".pem",
    ".key",
}
_SKIP_NAMES = {".DS_Store"}
_MAX_BYTES = 2_000_000

_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "private_key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
            re.IGNORECASE,
        ),
    ),
    (
        "api_key",
        re.compile(
            r"(?i)(?:api[_-]?key|apikey|access[_-]?token|secret[_-]?key|"
            r"auth[_-]?token)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,})"
        ),
    ),
    (
        "aws_key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
    (
        "password",
        re.compile(r"(?i)(?:password|passwd|pwd)\s*[=:]\s*['\"]?([^\s'\"]{6,})"),
    ),
    (
        "email",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
    (
        "phone",
        re.compile(
            r"(?<!\w)(?:\+\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4}(?!\w)"
        ),
    ),
    (
        "ipv4",
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
        ),
    ),
    (
        "mac",
        re.compile(
            r"\b(?:[0-9A-Fa-f]{2}([-:]))(?:[0-9A-Fa-f]{2}\1){4}[0-9A-Fa-f]{2}\b"
        ),
    ),
]


def is_hidden(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path
    return any(part.startswith(".") for part in relative.parts)


def readable_text(path: Path) -> str | None:
    if path.name in _SKIP_NAMES or path.name.startswith("._"):
        return None
    if path.suffix.lower() == ".pdf":
        return _pdf_text(path)
    if path.suffix.lower() not in _TEXT_EXT and path.suffix.lower() not in {
        "",
        ".text",
    }:
        return None
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if len(raw) > _MAX_BYTES:
        raw = raw[:_MAX_BYTES]
    if b"\x00" in raw[:4096]:
        return None
    return raw.decode("utf-8", errors="replace")


def _pdf_text(path: Path) -> str | None:
    import shutil
    import subprocess

    if shutil.which("pdftotext"):
        try:
            return subprocess.check_output(
                ["pdftotext", "-q", str(path), "-"],
                stderr=subprocess.DEVNULL,
                timeout=60,
            ).decode("utf-8", errors="replace")
        except (subprocess.SubprocessError, OSError):
            return None
    try:
        from pypdf import PdfReader

        return "\n".join(
            (page.extract_text() or "") for page in PdfReader(str(path)).pages
        )
    except Exception:
        return None


def scan_text(text: str) -> dict[str, int]:
    hits: dict[str, int] = {}
    for name, pattern in _RULES:
        found = pattern.findall(text)
        if not found:
            continue
        # Phone numbers are noisy; require at least 7 digits in the match.
        if name == "phone":
            count = 0
            for match in pattern.finditer(text):
                digits = re.sub(r"\D", "", match.group(0))
                if len(digits) >= 7:
                    count += 1
            if count:
                hits[name] = count
            continue
        hits[name] = len(found)
    return hits


def scan_folder(root: Path) -> list[dict]:
    root = root.resolve()
    reports = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if is_hidden(path, root):
            continue
        text = readable_text(path)
        if text is None:
            continue
        hits = scan_text(text)
        if not hits:
            continue
        reports.append(
            {
                "path": path.relative_to(root).as_posix(),
                "hits": hits,
            }
        )
    return reports


def format_report(root: Path, reports: list[dict]) -> str:
    lines = [
        f"Sensitivity scan (report only): {root.resolve()}",
        f"Files with hits: {len(reports)}",
        "",
    ]
    if not reports:
        lines.append("No credentials, keys, emails, phones, IPs, or MACs found.")
        return "\n".join(lines)
    for item in reports:
        parts = [f"{kind}×{count}" for kind, count in sorted(item["hits"].items())]
        lines.append(f"{item['path']}: {', '.join(parts)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if not args.folder.is_dir():
        print(f"Not a folder: {args.folder}", file=sys.stderr)
        return 1
    reports = scan_folder(args.folder)
    if args.json:
        import json

        print(
            json.dumps({"root": str(args.folder.resolve()), "files": reports}, indent=2)
        )
    else:
        print(format_report(args.folder, reports))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
