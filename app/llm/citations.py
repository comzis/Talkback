"""Source citations: finalizing markers, technical tokens, support checks, and similarity pruning."""

import re

from llm._text import (
    _CITATION,
    _STOP,
    strip_citations,
    _WORD,
)
from llm.language import (
    user_line,
)


_REFUSAL = re.compile(
    r"cannot find|can't find|do not contain|does not contain|don't contain|"
    r"not in the (retrieved|uploaded|library|sources|documents)|"
    r"ne couvre pas|ne contiennent pas ce|"
    r"no cubre|no incluyen ese",
    re.IGNORECASE,
)


def answered_from_sources(text: str) -> bool:
    """True when a reply cites the library and does not refuse the question."""
    if not text or _REFUSAL.search(text):
        return False
    return _CITATION.search(text) is not None


def cited_source_indexes(text: str) -> list[int]:
    """Return the source numbers used in a reply, in first-seen order."""
    indexes = []
    seen = set()
    for match in re.findall(r"\[(\d+)\]", text or ""):
        number = int(match)
        if number in seen:
            continue
        seen.add(number)
        indexes.append(number)
    return indexes


def correction_note(shown: str, reply: str, query: str = "") -> str | None:
    """Short footnote when grounding changed the reply. Never the full text again."""
    if not reply or _same_answer_body(shown, reply):
        return None
    if reply in {user_line("no_detail", query), user_line("no_example", query)}:
        return reply
    return user_line("no_detail", query)


def _same_answer_body(left: str, right: str) -> bool:
    """True when two replies match after citations and whitespace are ignored."""

    def norm(text: str) -> str:
        return re.sub(r"\s+", " ", strip_citations(text or "")).strip().casefold()

    return norm(left) == norm(right)


def _strip_trailing_citation_dump(answer: str, allowed: set[int]) -> str:
    """Drop an end-of-answer marker dump; keep legitimate sentence-end citations."""
    text = (answer or "").rstrip()
    match = re.search(r"((?:\s*\[\d+\])+)\s*$", text)
    if not match:
        return text
    trailing = match.group(1)
    marks = [int(item) for item in re.findall(r"\[(\d+)\]", trailing)]
    if not marks:
        return text
    prefix = text[: match.start()].rstrip()
    earlier = {int(item) for item in re.findall(r"\[(\d+)\]", prefix)}
    unique = list(dict.fromkeys(marks))
    # Classic dump: repeats markers already used, and/or mixes in dead numbers.
    if earlier and all(number in earlier or number not in allowed for number in marks):
        return prefix
    if len(marks) != len(unique):
        return (prefix + " " + " ".join(f"[{number}]" for number in unique)).strip()
    return text


def _citation_source_index(
    sources: list[dict],
) -> tuple[set[int], dict[int, dict]]:
    """Allowed marker numbers and a mutable copy of each source card."""
    allowed = {int(source.get("number") or 0) for source in sources}
    by_old = {
        int(source["number"]): dict(source)
        for source in sources
        if int(source.get("number") or 0) in allowed
    }
    return allowed, by_old


def _take_unique_citation_marks(
    numbers: list[int], *, allowed: set[int], order: list[int]
) -> list[int]:
    """Keep first occurrence of each allowed marker and extend cite order."""
    kept: list[int] = []
    seen: set[int] = set()
    for number in numbers:
        if number not in allowed or number in seen:
            continue
        kept.append(number)
        seen.add(number)
        if number not in order:
            order.append(number)
    return kept


_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)


def _split_on_code_fences(text: str) -> list[tuple[bool, str]]:
    """Split text into (is_code, segment) pieces; fenced code keeps its exact text."""
    pieces: list[tuple[bool, str]] = []
    pos = 0
    for match in _CODE_FENCE.finditer(text):
        if match.start() > pos:
            pieces.append((False, text[pos : match.start()]))
        pieces.append((True, match.group(0)))
        pos = match.end()
    if pos < len(text):
        pieces.append((False, text[pos:]))
    return pieces


def _parse_cited_sentences(
    answer: str, *, allowed: set[int], order: list[int]
) -> list[tuple[str, list[int]]]:
    """Split the answer into (body, marks) pairs with inline markers only.

    A fenced code block is kept as a single, untouched piece: no line
    stripping, no marker extraction, and no sentence splitting inside it.
    """
    answer = _strip_trailing_citation_dump(answer or "", allowed)
    sentences: list[tuple[str, list[int]]] = []
    for is_code, segment in _split_on_code_fences(answer):
        if is_code:
            sentences.append((segment, []))
            continue
        sentences.extend(_parse_prose_sentences(segment, allowed=allowed, order=order))
    return sentences


def _parse_prose_sentences(
    text: str, *, allowed: set[int], order: list[int]
) -> list[tuple[str, list[int]]]:
    """Sentence-split one code-fence-free segment into (body, marks) pairs."""
    sentences: list[tuple[str, list[int]]] = []
    for line in re.split(r"\n+", text):
        line = line.strip()
        if not line:
            continue
        for part in re.split(r"(?<=[.!?])\s+", line):
            part = part.strip()
            if not part:
                continue
            leading = re.match(r"^((?:\[\d+\]\s*)+)", part)
            lead_marks: list[int] = []
            if leading:
                lead_marks = [
                    int(match) for match in re.findall(r"\[(\d+)\]", leading.group(1))
                ]
                part = part[leading.end() :].strip()
            marks = [int(match) for match in re.findall(r"\[(\d+)\]", part)]
            body = re.sub(r"\s*\[\d+\]", "", part).strip()
            body = re.sub(r"\s+", " ", body).strip()
            if not body:
                # Markers left alone after a split belong to the previous sentence.
                if (lead_marks or marks) and sentences:
                    prev_body, prev_marks = sentences[-1]
                    sentences[-1] = (
                        prev_body,
                        _take_unique_citation_marks(
                            prev_marks + lead_marks + marks,
                            allowed=allowed,
                            order=order,
                        ),
                    )
                continue
            if lead_marks and sentences:
                prev_body, prev_marks = sentences[-1]
                sentences[-1] = (
                    prev_body,
                    _take_unique_citation_marks(
                        prev_marks + lead_marks, allowed=allowed, order=order
                    ),
                )
            sentences.append(
                (
                    body,
                    _take_unique_citation_marks(marks, allowed=allowed, order=order),
                )
            )
    return sentences


def _citation_number_mapping(order: list[int], allowed: set[int]) -> dict[int, int]:
    """Map old marker numbers to dense 1..n, appending uncited cards last."""
    mapping = {old: new for new, old in enumerate(order, start=1)}
    for number in sorted(allowed):
        if number not in mapping:
            mapping[number] = len(mapping) + 1
            order.append(number)
    return mapping


def _render_renumbered_answer(
    sentences: list[tuple[str, list[int]]], mapping: dict[int, int]
) -> str:
    """Join sentence bodies with renumbered trailing markers."""
    lines = []
    for body, marks in sentences:
        if not marks:
            lines.append(body)
            continue
        unique = []
        seen: set[int] = set()
        for number in marks:
            mapped = mapping.get(number)
            if mapped is None or mapped in seen:
                continue
            unique.append(mapped)
            seen.add(mapped)
        lines.append(body + "".join(f" [{number}]" for number in unique))
    return "\n".join(lines).strip()


def _renumber_source_cards(
    order: list[int], by_old: dict[int, dict], mapping: dict[int, int]
) -> list[dict]:
    """Apply the new numbers onto copies of the surviving source cards."""
    renumbered = []
    for old in order:
        source = by_old[old]
        source["number"] = mapping[old]
        renumbered.append(source)
    return renumbered


def finalize_citations(answer: str, sources: list[dict]) -> tuple[str, list[dict]]:
    """Keep markers inline once per sentence, drop dead ones, renumber cards 1..n."""
    if not sources:
        pieces = []
        for is_code, segment in _split_on_code_fences(answer or ""):
            if is_code:
                pieces.append(segment)
                continue
            cleaned = re.sub(r"\s*\[\d+\]", "", segment)
            cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
            pieces.append(re.sub(r" {2,}", " ", cleaned))
        return "".join(pieces).strip(), []

    allowed, by_old = _citation_source_index(sources)
    order: list[int] = []
    sentences = _parse_cited_sentences(answer, allowed=allowed, order=order)
    mapping = _citation_number_mapping(order, allowed)
    text = _render_renumbered_answer(sentences, mapping)
    return text, _renumber_source_cards(order, by_old, mapping)


_FILE_TOKEN = re.compile(
    r"\b[\w.-]+\.(?:pdf|ini|txt|ya?ml|cfg|conf|json|csv)\b",
    re.IGNORECASE,
)


_MEASURE_WITH_UNIT = re.compile(
    r"(?<![\w.])([±+-]?)\s*(\d+(?:\.\d+)?)\s*(dbtp|dbfs|lufs|lkfs|db|lu)\b"
)


_STANDARD_CODE = re.compile(r"\btech\s*(\d{3,4})\b")


_DOTTED_FIELD = re.compile(r"\b[a-z][a-z0-9_]+\.[a-z][a-z0-9_.]*\b")


_FILTER_NAME = r"[a-z_][\w.]*"


_FILTER_VALUE = r"[a-z0-9_\"'-]+"


_FILTER_ATOM = rf"{_FILTER_NAME}\s*==\s*{_FILTER_VALUE}"


_FILTER_EXPR = re.compile(
    rf"(?:{_FILTER_ATOM})(?:\s*(?:&&|\|\|)\s*(?:{_FILTER_ATOM}))+"
    rf"|{_FILTER_ATOM}"
    rf"|{_FILTER_NAME}(?:\s*(?:&&|\|\|)\s*{_FILTER_NAME})+"
)


def _compact(text: str) -> str:
    folded = (text or "").replace("−", "-").replace("–", "-").replace(",", ".")
    return re.sub(r"\s+", "", folded).casefold()


def _loosen(text: str) -> str:
    """Separate a number glued to a unit, as in 1.0LU or -1dBTP."""
    folded = (text or "").replace("−", "-").replace("–", "-").replace(",", ".")
    folded = folded.casefold()
    folded = re.sub(r"(?<=\d)(?=[a-z])", " ", folded)
    return re.sub(r"(?<=[a-z])(?=\d)", " ", folded)


def _canon_measure(sign: str, number: str, unit: str) -> str:
    """One form for 0.5 / 0,5 and for − / -."""
    prefix = "±" if sign == "±" else "-" if sign == "-" else ""
    return f"{prefix}{number} {unit}"


def technical_tokens(text: str) -> list[tuple[str, str]]:
    """Filters, dotted fields, numbers with units, standard codes, and file names.

    A parenthesis group of ordinary words, such as "(Option A)" or "(LRA)",
    is not a token. A bare number is not a token either.
    """
    loose = _loosen(strip_citations(text))
    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, value: str) -> None:
        item = (kind, value)
        if item not in seen:
            seen.add(item)
            found.append(item)

    for match in _MEASURE_WITH_UNIT.finditer(loose):
        add("measure", _canon_measure(match.group(1), match.group(2), match.group(3)))
    for match in _STANDARD_CODE.finditer(loose):
        add("code", match.group(1))
    for match in _FILE_TOKEN.finditer(loose):
        add("file", match.group(0).casefold())
    for match in _DOTTED_FIELD.finditer(loose):
        if _FILE_TOKEN.fullmatch(match.group(0)):
            continue
        add("field", match.group(0))
    for match in _FILTER_EXPR.finditer(loose):
        add("filter", _compact(match.group(0)))
    return found


def _token_in(kind: str, value: str, passage: str) -> bool:
    loose = _loosen(passage)
    if kind == "measure":
        present = {
            _canon_measure(match.group(1), match.group(2), match.group(3))
            for match in _MEASURE_WITH_UNIT.finditer(loose)
        }
        if value in present:
            return True
        # "0.5 LU" is the same figure as "±0.5 LU". A minus is not.
        if value[:1] not in "-±":
            return f"±{value}" in present
        return False
    if kind == "code":
        return re.search(rf"\btech\s*{re.escape(value)}\b", loose) is not None
    if kind == "filter":
        return value in _compact(loose)
    return re.search(rf"(?<!\w){re.escape(value)}(?!\w)", loose) is not None


def _passage_supports(
    tokens: list[tuple[str, str]], passage: str
) -> list[tuple[str, str]]:
    return [token for token in tokens if _token_in(token[0], token[1], passage)]


def supporting_sources(answer: str, sources: list[dict]) -> list[dict]:
    """Keep the passages that contain the reply's technical tokens.

    The model's own [n] markers are the starting point. A token that is missing
    from the cited passage is re-attributed to another retrieved passage that
    has it. A token that is in none of them drops the citation. Ordinary words
    in parentheses are ignored. A reply that never writes a source number is
    not given one afterwards.
    """
    if not answer or _REFUSAL.search(answer):
        return []
    cited = [
        number for number in cited_source_indexes(answer) if 1 <= number <= len(sources)
    ]
    if not cited:
        return []
    tokens = technical_tokens(answer)
    if not tokens:
        chosen = []
        for number in cited:
            source = dict(sources[number - 1])
            source["number"] = number
            chosen.append(source)
        return chosen
    kept: list[int] = []
    covered: set[tuple[str, str]] = set()
    for number in cited:
        held = _passage_supports(tokens, sources[number - 1].get("text", ""))
        if not held:
            continue
        kept.append(number - 1)
        covered.update(held)
    for token in tokens:
        if token in covered:
            continue
        for index, source in enumerate(sources):
            if not _token_in(token[0], token[1], source.get("text", "")):
                continue
            if index not in kept:
                kept.append(index)
            covered.add(token)
            break
        else:
            return []
    chosen = []
    for index in kept:
        source = dict(sources[index])
        source["number"] = index + 1
        chosen.append(source)
    return chosen


# Calibrated on main-set sentences against the cited passage (bge-m3, best 700-character
# window). Relevant sentences, including Spanish and French, scored about 0.60 to 0.76.
# An SRT incident draft against the television pages scored about 0.45 to 0.49.
CITATION_MIN_SIMILARITY = 0.55


# A short reply such as "Se llama Playbook." scores low against a long page on its
# own. Join it with the question so the comparison keeps the topic. A short reply
# that shares no content word with the passage still drops, so a wrong one-word
# answer cannot ride the question's similarity.
SHORT_CITATION_WORDS = 8


def passage_windows(text: str, size: int = 700, step: int = 350) -> list[str]:
    """Overlapping slices of a passage, so a short sentence can match one part of it."""
    folded = " ".join((text or "").split())
    if not folded:
        return []
    if len(folded) <= size:
        return [folded]
    cuts = []
    start = 0
    while start < len(folded):
        cuts.append(folded[start : start + size])
        if start + size >= len(folded):
            break
        start += step
    return cuts


def citing_sentence(answer: str, number: int) -> str:
    """The sentence that carries this source number, without the marker.

    A marker that sits after the full stop, or alone on the next line, still
    belongs to that sentence. A draft with no full stops is scored a line at
    a time, so a trailing marker is not compared with the whole draft. A
    fenced code block (matching `_split_on_code_fences`) is one atomic unit,
    so a marker alone on the line right after its closing fence attaches to
    the fenced content, not the bare delimiter.
    """
    merged: list[str] = []
    for is_code, segment in _split_on_code_fences((answer or "").strip()):
        if is_code:
            merged.append(segment)
            continue
        for part in re.split(r"(?<=[.!?])\s+|\n+", segment.strip()):
            if not part:
                continue
            if merged and re.fullmatch(r"(?:\[\d+\]\s*)+", part):
                merged[-1] = f"{merged[-1]} {part}"
            else:
                merged.append(part)
    hits = [part for part in merged if re.search(rf"\[{number}\]", part)]
    return _CITATION.sub("", " ".join(hits)).strip()


def _citation_words(text: str) -> list[str]:
    return [word for word in (text or "").split() if word]


def citation_compare_text(sentence: str, query: str = "") -> str:
    """Text compared to the passage. Short replies include the question."""
    if len(_citation_words(sentence)) < SHORT_CITATION_WORDS and (query or "").strip():
        return f"{query.strip()} {sentence.strip()}"
    return sentence


def sentence_touches_passage(sentence: str, passage: str) -> bool:
    """True when a content word from the sentence appears in the passage."""
    folded = (passage or "").casefold()
    for word in re.findall(r"[a-z0-9à-ÿœ]+", (sentence or "").casefold()):
        if len(word) < 3 or word in _STOP:
            continue
        if re.search(rf"\b{re.escape(word)}\b", folded):
            return True
    return False


def keep_close_citations(
    answer: str, sources: list[dict], score, query: str = ""
) -> list[dict]:
    """Drop a citation whose sentence is not close to the cited passage.

    A citation the model did not write has no sentence to compare, so the
    technical-token check stands. `score` returns the bge-m3 similarity.
    A short sentence is scored with the question, and only when it still
    shares a content word with the passage.
    """
    kept = []
    for source in sources:
        number = int(source.get("number") or 0)
        if not re.search(rf"\[{number}\]", answer or ""):
            kept.append(source)
            continue
        sentence = citing_sentence(answer, number)
        if not sentence:
            continue
        passage = source.get("text") or ""
        if (
            len(_citation_words(sentence)) < SHORT_CITATION_WORDS
            and (query or "").strip()
        ):
            if not sentence_touches_passage(sentence, passage):
                continue
        compared = citation_compare_text(sentence, query)
        if float(score(compared, passage)) >= CITATION_MIN_SIMILARITY:
            kept.append(source)
    return kept


def source_label(source: dict) -> str:
    """Show the folder and file, and the page when the reader stored one."""
    path = source.get("path") or source.get("source") or "Document"
    page = source.get("page")
    if page not in (None, ""):
        return f"{path} · p. {page}"
    return str(path)


def library_miss(answer: str, query: str = "") -> str:
    """Use the model's refusal when it already admits the gap."""
    cleaned = strip_citations(answer)
    if cleaned and _REFUSAL.search(answer or ""):
        return cleaned
    return user_line("not_covered", query)


def grounded_in_sources(answer: str, source_texts: list[str]) -> bool:
    """True when the reply cites the library and its wording appears in those sources."""
    if not answered_from_sources(answer):
        return False
    cleaned = _CITATION.sub(" ", answer.lower())
    words = [word for word in _WORD.findall(cleaned) if word not in _STOP]
    if len(words) < 2:
        return False
    blob = " ".join(source_texts).lower()
    hits = sum(1 for word in words if word in blob)
    return hits >= 2
