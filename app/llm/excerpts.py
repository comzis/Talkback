"""Excerpt display, PDF spacing repair, and grounding of library replies."""

import re
import unicodedata

from llm._text import (
    strip_citations,
)
from llm.citations import (
    _canon_measure,
    _compact,
    _loosen,
    _MEASURE_WITH_UNIT,
    technical_tokens,
)
from llm.followups import (
    asks_for_example,
    asks_for_steps,
)
from llm.language import (
    user_line,
)


_FENCE = re.compile(r"```[a-z]*\n?([\s\S]*?)```", re.IGNORECASE)


_INLINE = re.compile(r"`([^`]{2,120})`")


_COMPARE = re.compile(
    r"\b[A-Za-z][\w.]*(?:\[[^\]]+\])?\s*(?:==|!=)\s*[A-Za-z0-9_:.\-\[\]]{1,60}"
)


_CONTAINS_LITERAL = re.compile(r"\bcontains\s+[\"“'][^\"”']{1,60}[\"”']", re.IGNORECASE)


_DOTTED = re.compile(r"\b[A-Za-z]{2,}(?:\.[A-Za-z0-9]{2,})+\b")


_LONG_NUMBER = re.compile(r"\b\d{2,}\b")


_CODE = re.compile(r"\b(?:type|code)\s+\d+\b", re.IGNORECASE)


_EXAMPLE_LEAD = re.compile(
    r"^(here(?:'s| is)|this (?:filter|example)|use this|an example of)\b",
    re.IGNORECASE,
)


def _flat(text: str) -> str:
    text = (
        (text or "")
        .replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("‘", "'")
    )
    return re.sub(r"\s+", " ", text).casefold()


def _source_blob(sources: list[dict]) -> str:
    return _flat("\n".join(source.get("text") or "" for source in sources))


def _unsupported_fragment(fragment: str, blob: str) -> bool:
    folded = _flat(fragment).strip(" `\"'")
    return len(folded) >= 2 and folded not in blob


def _shows_example(text: str, blob: str) -> bool:
    """True when the reply still contains a filter or command that the excerpts contain."""
    if _CONTAINS_LITERAL.search(text) or _COMPARE.search(text):
        return True
    return any(
        not _unsupported_fragment(match, blob) for match in _INLINE.findall(text)
    )


def _sentence_invents(sentence: str, blob: str) -> bool:
    """True when a sentence adds a filter, command, dotted name, or number the excerpts omit."""
    body = strip_citations(sentence)
    pieces = [match for match in _INLINE.findall(body)]
    pieces.extend(match.group(0) for match in _COMPARE.finditer(body))
    pieces.extend(match.group(0) for match in _CONTAINS_LITERAL.finditer(body))
    pieces.extend(match.group(0) for match in _DOTTED.finditer(body))
    pieces.extend(match.group(0) for match in _CODE.finditer(body))
    pieces.extend(_LONG_NUMBER.findall(body))
    return any(_unsupported_fragment(piece, blob) for piece in pieces)


_PDF_WORD = {
    "a",
    "an",
    "as",
    "at",
    "be",
    "by",
    "do",
    "if",
    "in",
    "is",
    "it",
    "no",
    "of",
    "on",
    "or",
    "so",
    "to",
    "we",
    "and",
    "the",
    "for",
    "not",
    "you",
    "but",
    "can",
    "its",
    "may",
    "any",
    "all",
    "has",
    "are",
    "was",
    "one",
    "our",
    "out",
    "use",
    "see",
    "how",
    "with",
    "from",
    "that",
    "this",
    "have",
    "your",
    "into",
    "over",
    "than",
    "then",
    "them",
    "they",
    "what",
    "when",
    "will",
    "also",
    "each",
    "just",
    "only",
    "some",
    "more",
    "most",
    "such",
    "want",
    "view",
    "byte",
    "after",
    "take",
    "look",
    "due",
    "per",
    "via",
}


_EXAMPLE_HEAD = re.compile(r"Example\s+\d+\s*:", re.IGNORECASE)


_FILTER_SPAN = re.compile(
    r"\((?:[^()\n]|\([^()\n]*\))+\)(?:\s*(?:\|\||&&)\s*\((?:[^()\n]|\([^()\n]*\))+\))*"
)


def normalize_extracted_text(text: str) -> str:
    """NFKC plus PDF spacing repair. Used at index time and for card excerpts."""
    return repair_pdf_spacing(unicodedata.normalize("NFKC", text or ""))


def prompt_passage(text: str) -> str:
    """Full chunk text for the prompt and the grounding check."""
    return normalize_extracted_text(text or "")


def display_excerpt(text: str, query: str = "", answer: str = "") -> str:
    """Clip the source card to the part of the chunk that matches the answer.

    Prefer a window that holds the answer's technical tokens (filters, dotted
    field names, numbers with units, codes). When the answer has none, open on
    the window most similar to the answer text.
    """
    limit = 900 if asks_for_example(query) or asks_for_steps(query) else 500
    body = normalize_extracted_text(text or "")
    if not body:
        return ""
    start = _excerpt_start(body, answer, query, limit)
    return body[start : start + limit].lstrip()


def _fold_match(text: str) -> str:
    return (text or "").replace("−", "-").replace("–", "-").lower()


def _excerpt_start(body: str, answer: str, query: str, limit: int = 500) -> int:
    """Index where the card should open, just before the matching evidence."""
    tokens = technical_tokens(answer)
    if tokens:
        anchor = _technical_anchor(body, tokens)
        if anchor is not None:
            return max(0, anchor - 40)
        return 0
    return _similar_window_start(body, answer or query, limit)


def _technical_anchor(body: str, tokens: list[tuple[str, str]]) -> int | None:
    """Earliest index in the chunk that holds an answer technical token."""
    positions = [
        at
        for kind, value in tokens
        if (at := _token_index(kind, value, body)) is not None
    ]
    if not positions:
        return None
    return min(positions)


def _token_index(kind: str, value: str, body: str) -> int | None:
    """Byte index of a technical token inside the display chunk, or None."""
    folded = _fold_match(body)
    if kind == "field":
        match = re.search(rf"(?<!\w){re.escape(value)}(?!\w)", folded)
        return match.start() if match else None
    if kind == "file":
        match = re.search(rf"(?<!\w){re.escape(value)}(?!\w)", folded, re.IGNORECASE)
        return match.start() if match else None
    if kind == "code":
        match = re.search(rf"\btech\s*{re.escape(value)}\b", folded, re.IGNORECASE)
        return match.start() if match else None
    if kind == "measure":
        for match in _MEASURE_WITH_UNIT.finditer(_loosen(body)):
            if _canon_measure(match.group(1), match.group(2), match.group(3)) == value:
                # _loosen only inserts spaces; search the folded original form.
                number = match.group(2)
                unit = match.group(3)
                found = re.search(
                    rf"{re.escape(number)}\s*{re.escape(unit)}\b",
                    folded,
                    re.IGNORECASE,
                )
                return found.start() if found else match.start()
        return None
    if kind == "filter":
        compact = _compact(body)
        at = compact.find(value)
        if at < 0:
            return None
        return _index_from_compact(body, at)
    return None


def _index_from_compact(body: str, compact_at: int) -> int:
    """Map an index in ``_compact(body)`` back to an index in ``body``."""
    seen = 0
    for index, char in enumerate(body or ""):
        piece = char.replace("−", "-").replace("–", "-").replace(",", ".")
        if not piece or piece.isspace():
            continue
        folded = piece.casefold()
        if seen <= compact_at < seen + len(folded):
            return index
        seen += len(folded)
    return 0


def _similar_window_start(body: str, needle: str, limit: int) -> int:
    """Start of the window that shares the most content words with needle."""
    if not (needle or "").strip() or len(body) <= limit:
        return 0
    needle_words = set(re.findall(r"[a-z0-9]{4,}", _fold_match(needle)))
    if not needle_words:
        return 0
    best_at = 0
    best_score = -1
    step = max(40, limit // 4)
    last = max(1, len(body) - limit + 1)
    for start in range(0, last, step):
        window = _fold_match(body[start : start + limit])
        score = len(needle_words & set(re.findall(r"[a-z0-9]{4,}", window)))
        if score > best_score:
            best_score = score
            best_at = start
    return best_at


def repair_pdf_spacing(text: str) -> str:
    """Join words the PDF extractor split, such as 'cont ain'."""

    def once(line: str) -> str:
        tokens = line.split(" ")
        changed = True
        while changed:
            changed = False
            merged = []
            index = 0
            while index < len(tokens):
                left = tokens[index]
                right = tokens[index + 1] if index + 1 < len(tokens) else ""
                broken = (
                    left
                    and right
                    and (
                        (
                            len(left) == 1
                            and right[:2].lower() in {"ft", "ck", "ng", "sr", "tl"}
                        )
                        or (
                            left.lower() not in _PDF_WORD
                            and right.lower() not in _PDF_WORD
                            and left[-1:].islower()
                            and right[:1].islower()
                            and (len(left) <= 3 or (len(left) <= 4 and len(right) <= 3))
                        )
                    )
                )
                if broken:
                    merged.append(left + right)
                    index += 2
                    changed = True
                    continue
                merged.append(left)
                index += 1
            tokens = merged
        return " ".join(tokens)

    return "\n".join(
        re.sub(r" {2,}", " ", once(line)) for line in (text or "").split("\n")
    )


def _filter_span(text: str):
    """The worked filter in an excerpt, parentheses included."""
    for match in _FILTER_SPAN.finditer(text or ""):
        if "==" in match.group(0) or "contains" in match.group(0).lower():
            return match
    return _CONTAINS_LITERAL.search(text or "") or _COMPARE.search(text or "")


def _example_blocks(text: str) -> list[str]:
    marks = list(_EXAMPLE_HEAD.finditer(text or ""))
    blocks = []
    for index, mark in enumerate(marks):
        end = (
            marks[index + 1].start()
            if index + 1 < len(marks)
            else min(len(text), mark.end() + 650)
        )
        block = text[mark.start() : end].strip()
        if _filter_span(block):
            blocks.append(block)
    return blocks


def _best_example(sources: list[dict], query: str = "") -> tuple[str, int] | None:
    """The first worked example in the excerpts. The query is not used to prefer one document."""
    del query
    for source in sources:
        text = repair_pdf_spacing(source.get("text") or "")
        blocks = _example_blocks(text)
        if blocks:
            return blocks[0], int(source.get("number") or 0)
    return None


def _plain_reply(text: str) -> str:
    """Drop markdown and a trailing offer of more questions."""
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", text or "")
    cleaned = re.sub(r"(?m)^\s*#+\s*", "", cleaned)
    kept = []
    for line in cleaned.split("\n"):
        if re.match(r"let me know\b", line.strip(), re.IGNORECASE):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _format_example(block: str) -> tuple[str, list[str]]:
    """Heading, the explanation, and the filter on its own step."""
    span = _filter_span(block)
    http = re.search(r"https?://", block, re.IGNORECASE)
    if http and (span is None or http.start() < span.start()):
        prose = block[: http.start()].strip()
        filt = re.sub(r"\s+", " ", span.group(0)).strip() if span else ""
        block = f"{prose} {filt}".strip()
    elif span:
        block = block[: span.end()]
    flat = re.sub(r"\s+", " ", block).strip()
    flat = re.sub(
        r"^(Example\s+\d+\s*:\s*.{0,50}?)(?=\s+(?:If|Suppose|One|To|There|The|You|When|Several)\b)",
        r"\1\n",
        flat,
        count=1,
        flags=re.IGNORECASE,
    )
    parts = [part.strip() for part in flat.split("\n") if part.strip()]
    title = parts[0]
    body = " ".join(parts[1:]) if len(parts) > 1 else ""
    span = _filter_span(flat)
    filter_line = re.sub(r"\s+", " ", span.group(0)).strip() if span else ""
    sentences = []
    for sentence in re.split(r"(?<=[.!?])\s+", body):
        sentence = sentence.strip()
        if filter_line:
            sentence = sentence.replace(filter_line, "").strip(" .;")
        if sentence and not _filter_span(sentence):
            sentences.append(sentence)
    if filter_line:
        sentences.append(filter_line)
    return title, sentences[:4]


def _steps_from_sources(sources: list[dict], query: str) -> str | None:
    """Number the worked example from the excerpts instead of a loose paraphrase."""
    found = _best_example(sources, query)
    if not found:
        return None
    block, number = found
    title, sentences = _format_example(block)
    if not sentences:
        return None
    numbered = "\n".join(
        f"{index}. {sentence}" for index, sentence in enumerate(sentences, 1)
    )
    mark = f" [{number}]" if number else ""
    return f"{title}{mark}\n{numbered}"


def _quote_example(sources: list[dict], query: str) -> str | None:
    """One complete example, starting at its heading and ending at its filter."""
    found = _best_example(sources, query)
    if not found:
        return None
    block, number = found
    title, sentences = _format_example(block)
    if not sentences:
        return None
    mark = f" [{number}]" if number else ""
    return f"{title}. {' '.join(sentences)}{mark}"


def _structured_library_reply(sources: list[dict], query: str) -> str | None:
    """Return the numbered steps or quoted example when the query asks for one."""
    if asks_for_steps(query):
        walked = _steps_from_sources(sources, query)
        if walked:
            return walked
    if asks_for_example(query):
        quoted = _quote_example(sources, query)
        if quoted:
            return quoted
    return None


def _strip_unsupported_fences(text: str, blob: str) -> str:
    """Remove fenced blocks whose contents the excerpts do not contain."""
    for match in list(_FENCE.finditer(text)):
        if _unsupported_fragment(match.group(1), blob):
            text = text.replace(match.group(0), "")
    return text


def _keep_supported_sentences(text: str, blob: str) -> str:
    """Keep sentences that invent nothing and are not bare citation markers."""
    kept = []
    for line in re.split(r"\n+", text):
        for sentence in re.split(r"(?<!\d)(?<=[.!?])\s+(?=[A-Z])", line.strip()):
            sentence = sentence.strip()
            if not sentence or _sentence_invents(sentence, blob):
                continue
            if re.fullmatch(r"(?:\[\d+\]\s*)+", sentence):
                continue
            kept.append(sentence)
    return "\n".join(kept).strip()


def _drop_ungrounded_example_leads(cleaned: str, blob: str) -> str:
    """Drop "Here is..." lead-ins when no supported example remains."""
    if _shows_example(cleaned, blob):
        return cleaned
    return "\n".join(
        sentence
        for sentence in cleaned.split("\n")
        if not _EXAMPLE_LEAD.match(sentence.strip())
    ).strip()


def _append_example_if_needed(cleaned: str, sources: list[dict], query: str) -> str:
    """Add a quoted example, or a no-example notice, when one was asked for."""
    if not asks_for_example(query) or _shows_example(cleaned, _source_blob(sources)):
        return cleaned
    found = _quote_example(sources, query)
    if found:
        return found if not cleaned else f"{cleaned}\n{found}"
    notice = user_line("no_example", query)
    return notice if not cleaned else f"{cleaned}\n{notice}"


def _or_no_detail(cleaned: str, query: str) -> str:
    """Fall back to the no-detail line when only citations remain."""
    if not strip_citations(cleaned).strip():
        return user_line("no_detail", query)
    return cleaned


def ground_library_reply(answer: str, sources: list[dict], query: str = "") -> str:
    """Drop filters, commands, and numbers that the retrieved excerpts do not contain."""
    structured = _structured_library_reply(sources, query)
    if structured:
        return structured
    if not answer:
        return answer
    blob = _source_blob(sources)
    text = _strip_unsupported_fences(_plain_reply(answer), blob)
    cleaned = _keep_supported_sentences(text, blob)
    cleaned = _drop_ungrounded_example_leads(cleaned, blob)
    cleaned = _append_example_if_needed(cleaned, sources, query)
    return _or_no_detail(cleaned, query)
