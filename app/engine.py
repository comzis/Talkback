"""Chroma, embeddings, ingestion, and grounded answers."""

from __future__ import annotations

import logging
import os
import threading

import torch
import config
from ingestion.plan import (
    read_only_requested,
)
from store.chroma import (
    collection_count,
    connect_chroma,
    delete_chunks_for_file,
    get_or_create_cached_index,
    indexed_documents,
    reindex_required,
)
from ingestion.pipeline import (
    begin_ingestion,
    enqueue_ingestion,
    files_waiting,
    process_ingestion,
    rebuild_library,
    start_initial_index,
    start_reindex_schedule,
)
from state import activate, get

__all__ = [
    "answer_query",
    "begin_ingestion",
    "collection_count",
    "enqueue_ingestion",
    "delete_chunks_for_file",
    "files_waiting",
    "init",
    "iter_answer",
    "library_read_only",
    "offline_mode",
    "process_ingestion",
    "rebuild_library",
    "reindex_required",
    "start_initial_index",
    "start_reindex_schedule",
]
from llm.client import _stream_deltas, _warm_up, wait_for_models
from retrieval.search import (
    _retrieve_nodes,
    _source_record,
)
from llm.citations import (
    correction_note,
    finalize_citations,
    passage_windows,
    source_label,
    supporting_sources,
)
from llm.excerpts import display_excerpt, ground_library_reply
from llm.followups import retrieval_text, should_search_library
from llm.language import (
    notice_for_general,
    outside_document_note,
    scrub_general_figures,
    take_stream_piece,
    user_line,
)
from llm.templates import assistant_prompt, explanation_prompt
from store.search_errors import SearchUnavailable

logger = logging.getLogger(__name__)


def library_read_only() -> bool:
    """True when the data directory is a read-only mount, such as a network share."""
    return read_only_requested(os.getenv("LIBRARY_READ_ONLY"))


def offline_mode() -> bool:
    """True unless OFFLINE_MODE is explicitly turned off for a setup download."""
    return os.getenv("OFFLINE_MODE", "true").lower() in {"1", "true", "yes"}


def apply_offline_mode() -> None:
    """Stop Hugging Face from calling the network when the cache is already present.

    huggingface_hub reads HF_HUB_OFFLINE once, at import. The container entrypoint
    exports it before Python starts. Setting the constant here covers a process
    that imported the library first.
    """
    if not offline_mode():
        logger.info(
            "OFFLINE_MODE is off. Setup may download a missing embedding model."
        )
        return
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    try:
        import huggingface_hub.constants as hf_constants

        hf_constants.HF_HUB_OFFLINE = True
    except (ImportError, AttributeError):
        logger.exception("Could not mark Hugging Face offline")
    logger.info("Offline mode: the embedding model loads from the local cache only.")


def init() -> None:
    """Validate configuration, wait for Chroma, and load local models."""
    required = {
        "OLLAMA_MODEL": "LLM model name for Ollama",
        "CHROMA_HOST": "ChromaDB host address",
        "CHROMA_PORT": "ChromaDB port number",
    }
    missing = [
        f"{name} ({description})"
        for name, description in required.items()
        if not os.getenv(name)
    ]
    if missing:
        message = "Missing required environment variables:\n" + "\n".join(
            f"  - {item}" for item in missing
        )
        logger.error(message)
        raise ValueError(message)

    apply_offline_mode()
    activate()
    torch.set_num_threads(config.torch_threads())
    logger.info("Torch CPU threads set to %s", config.torch_threads())
    get().upload_dir.mkdir(parents=True, exist_ok=True)
    connect_chroma()
    threading.Thread(target=_warm_up, name="talkback-warmup", daemon=True).start()


def _candidate_card(source: dict) -> dict:
    """File and page only. Early cards do not carry the passage text."""
    card = {
        "number": int(source.get("number") or 0),
        "source": source.get("source") or source.get("path") or "Document",
        "path": source.get("path") or source.get("source") or "Document",
        "label": source.get("label") or source_label(source),
        "used": False,
    }
    page = source.get("page")
    if page not in (None, ""):
        card["page"] = str(page)
    return card


def _final_source_cards(used: list[dict], query: str, reply: str):
    """Build the final cards straight from finalize_citations' cited sources.

    Each card already carries the dense 1..n number finalize_citations
    assigned, which matches the `[n]` markers rewritten into the displayed
    text, so no matching against the original retrieval candidates is done.
    """
    cards = []
    for source in used:
        card = dict(source)
        card["label"] = card.get("label") or source_label(card)
        card["text"] = display_excerpt(card.get("text") or "", query, reply)
        card["used"] = True
        cards.append(card)
    return cards


def _iter_streamed_token_events(prompt: str, temperature: float | None):
    """Yield token events as the model streams. Returns the text shown."""
    parts: list[str] = []
    pending = ""
    general = None
    for delta in _stream_deltas(prompt, temperature):
        if general is not None:
            general += delta
            continue
        pending += delta
        emit, pending, started = take_stream_piece(pending)
        if emit:
            parts.append(emit)
            yield {"event": "token", "data": {"text": emit}}
        if started:
            general = pending
            pending = ""
    if general is not None:
        cleaned = scrub_general_figures(general)
        if cleaned:
            parts.append(cleaned)
            yield {"event": "token", "data": {"text": cleaned}}
    elif pending:
        parts.append(pending)
        yield {"event": "token", "data": {"text": pending}}
    return "".join(parts).strip()


def _library_reply_and_correction(
    shown: str, sources: list, query: str
) -> tuple[str, str | None]:
    """Check a library reply. The note is None when nothing was actually dropped."""
    reply, dropped = ground_library_reply(shown, sources, query)
    reply = reply.strip()
    note = correction_note(dropped, reply or user_line("no_detail", query), query)
    return reply, note


def _iter_library_stream_tail(
    shown: str, reply: str, note: str | None, sources: list, query: str
):
    """Yield the events that follow a streamed library answer.

    A short footnote notes a grounding change. Markers are finalized with the
    sources event, once per sentence and renumbered. The full reply is not re-sent.
    """
    used = _close_citations(shown, supporting_sources(shown, sources), query)
    display, used = finalize_citations(shown, used)
    if note:
        yield {"event": "footnote", "data": {"text": note}}
    if not used:
        logger.info("No citation survived the check")
        yield {"event": "notice", "data": {"text": outside_document_note(query)}}
    cards = _final_source_cards(used, query, display)
    logger.info(
        "Query cited %s",
        [source["source"] for source in cards if source.get("used")],
    )
    yield {"event": "sources", "data": {"sources": cards, "text": display}}
    yield {"event": "done", "data": {}}


def _stream_prompt(
    prompt: str,
    temperature: float | None,
    sources: list | None,
    notice: str | None = None,
    query: str = "",
):
    """Stream tokens as they arrive.

    A library reply is checked against the excerpts after the stream. If that
    check changes the wording, a short footnote notes it — the full grounded
    text is never re-sent. Citation markers are finalized with the sources
    event (inline, once per sentence, renumbered). Only the sources the
    answer actually cites reach the final sources list.
    """
    if notice:
        yield {"event": "notice", "data": {"text": notice}}
    shown = yield from _iter_streamed_token_events(prompt, temperature)
    if sources is None:
        logger.info("Query answered as assistant")
        yield {"event": "sources", "data": {"sources": []}}
        yield {"event": "done", "data": {}}
        return
    reply, note = _library_reply_and_correction(shown, sources, query)
    yield from _iter_library_stream_tail(shown, reply, note, sources, query)


def _citation_similarity(sentence: str, passage: str) -> float:
    """Best cosine similarity between the sentence and a window of the passage.

    Unit tests have no embedding model. They keep the technical-token result.
    """
    from llama_index.core import Settings

    embedder = Settings.embed_model
    if embedder is None or not sentence:
        return 1.0
    pieces = passage_windows(passage)
    if not pieces:
        return 0.0
    vectors = embedder.get_text_embedding_batch([sentence, *pieces])

    def dot(left, right):
        return sum(a * b for a, b in zip(left, right))

    def norm(vector):
        return sum(value * value for value in vector) ** 0.5 or 1.0

    base = vectors[0]
    return max(dot(base, other) / (norm(base) * norm(other)) for other in vectors[1:])


def _close_citations(answer: str, sources: list, query: str = ""):
    from llm.citations import keep_close_citations

    def score(sentence, passage):
        value = _citation_similarity(sentence, passage)
        logger.info("Citation similarity %.3f", value)
        return value

    return keep_close_citations(answer, sources, score, query=query)


def iter_answer(query: str, history=None, scope: str | None = None):
    """Yield token events as they arrive, then sources.

    ``scope`` is an optional relative_path (file or folder). Empty means all.
    """
    logger.info("Query started (%s characters)", len(query or ""))
    search = retrieval_text(query, history)
    wait_for_models()
    try:
        if collection_count() == 0:
            if files_waiting() and should_search_library(search):
                logger.info(
                    "Query skipped because the library files are not indexed yet."
                )
                yield {
                    "event": "notice",
                    "data": {"text": user_line("not_indexed", query)},
                }
                yield {
                    "event": "token",
                    "data": {"text": user_line("indexing", query)},
                }
                yield {"event": "sources", "data": {"sources": []}}
                yield {"event": "done", "data": {}}
                return
            yield from _stream_prompt(
                assistant_prompt(query, history),
                None,
                None,
                notice_for_general(query, history),
            )
            return
        if not should_search_library(search):
            yield from _stream_prompt(
                assistant_prompt(query, history),
                None,
                None,
                notice_for_general(query, history),
            )
            return
        yield {"event": "status", "data": {"text": "Searching…"}}
        index = get_or_create_cached_index()
        indexed, _legacy, _incomplete = indexed_documents()
        library_files = sorted(indexed)
        nodes, _named_file = _retrieve_nodes(index, search, library_files, scope=scope)
        if not nodes:
            logger.info("No passages retrieved. Answering from general knowledge.")
            yield from _stream_prompt(
                assistant_prompt(query, history),
                None,
                None,
                notice_for_general(query, history, missed_library=True),
            )
            return
        sources = [
            _source_record(node, number, query) for number, node in enumerate(nodes, 1)
        ]
        candidates = [_candidate_card(source) for source in sources]
        yield {
            "event": "retrieved",
            "data": {"sources": candidates, "count": len(candidates)},
        }
        yield {"event": "status", "data": {"text": "Writing answer…"}}
        prompt = explanation_prompt(
            query,
            library_files,
            [f"{source['source']}\n{source['text']}" for source in sources],
            history,
        )
        yield from _stream_prompt(prompt, 0.1, sources, query=query)
    except SearchUnavailable as exc:
        # Host embed/rerank is required on Mac and is down. Tell the user
        # clearly instead of answering as if the library was searched.
        logger.warning("Search unavailable (scope=%r): %s", scope, exc)
        text = user_line("search_unavailable", query)
        yield {"event": "notice", "data": {"text": text}}
        yield {"event": "token", "data": {"text": text}}
        yield {"event": "sources", "data": {"sources": []}}
        yield {"event": "done", "data": {}}
    except Exception:
        # Log once here with the scope, then let the API layer shape the error.
        logger.exception("Query failed (scope=%r)", scope)
        raise


def answer_query(query: str, history=None, scope: str | None = None) -> dict:
    """Answer from the library when it applies, and as an assistant otherwise."""
    text: list[str] = []
    sources: list = []
    notice = None
    footnote = None
    for event in iter_answer(query, history, scope=scope):
        kind = event["event"]
        if kind == "token":
            text.append(event["data"]["text"])
        elif kind == "notice":
            notice = event["data"]["text"]
        elif kind == "footnote":
            footnote = event["data"]["text"]
        elif kind == "sources":
            sources = event["data"]["sources"]
    return {
        "response": "".join(text).strip(),
        "sources": sources,
        "notice": notice,
        "footnote": footnote,
    }
