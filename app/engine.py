"""Chroma, embeddings, ingestion, and grounded answers."""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

import chromadb
import psutil
import torch
from llama_index.core import Settings, SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.chroma import ChromaVectorStore

import config
import embeddings
from files import visible_files
from library import (
    balance_matches,
    chunk_belongs_to,
    chunk_is_legacy,
    chunk_key,
    disk_signature,
    index_plan,
    indexed_signature,
    library_key,
    read_only_requested,
    reindex_minutes,
)
from progress import ingest_metrics
from prompts import (
    GENERAL_NOTICE,
    UNMATCHED_SOURCE_NOTE,
    assistant_prompt,
    cited_source_indexes,
    explanation_prompt,
    named_library_files,
    should_search_library,
    source_label,
    supporting_sources,
)

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(os.getenv("RAG_DATA_DIR", "/app/data"))


def library_read_only() -> bool:
    """True when the data directory is a read-only mount, such as a network share."""
    return read_only_requested(os.getenv("LIBRARY_READ_ONLY"))


def start_reindex_schedule() -> None:
    """Re-run incremental indexing on a timer. Unset or 0 leaves this off."""
    minutes = reindex_minutes(os.getenv("REINDEX_INTERVAL_MINUTES"))
    if minutes is None:
        logger.info("Scheduled re-index is off.")
        return

    def loop() -> None:
        while True:
            time.sleep(minutes * 60)
            if reindex_required():
                logger.info("Scheduled re-index skipped until a full re-index.")
                continue
            if not begin_ingestion():
                logger.info("Scheduled re-index skipped because indexing is already running.")
                continue
            logger.info("Scheduled re-index started.")
            process_ingestion()

    threading.Thread(target=loop, name="talkback-reindex", daemon=True).start()
    logger.info("Scheduled re-index every %s minutes.", minutes)


def offline_mode() -> bool:
    """True unless OFFLINE_MODE is explicitly turned off for a setup download."""
    return os.getenv("OFFLINE_MODE", "true").lower() in {"1", "true", "yes"}


def apply_offline_mode() -> None:
    """Stop Hugging Face from calling the network when the cache is already present."""
    if not offline_mode():
        logger.info("OFFLINE_MODE is off. Setup may download a missing embedding model.")
        return
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    logger.info("Offline mode: the embedding model loads from the local cache only.")


ingestion_status: dict = {
    "status": "idle",
    "progress": 0,
    "current": 0,
    "total": 0,
    "message": "",
    "error": None,
    "current_file": None,
    "total_files": 0,
    "processed_files": 0,
    "start_time": None,
    "chunks_per_second": 0.0,
    "cpu_percent": 0.0,
    "memory_percent": 0.0,
    "estimated_time_remaining": 0,
}

db = None
chroma_collection = None
vector_store = None
storage_context = None
cached_index: VectorStoreIndex | None = None
_reindex_required = False


def reindex_required() -> bool:
    """True when stored vectors were embedded with a different model."""
    return _reindex_required


def files_waiting() -> bool:
    """True when the folder has files and the vector collection is empty."""
    return collection_count() == 0 and bool(visible_files(UPLOAD_DIR))


def _fresh_status(**overrides) -> dict:
    status = {
        "status": "idle",
        "progress": 0,
        "current": 0,
        "total": 0,
        "message": "",
        "error": None,
        "current_file": None,
        "total_files": 0,
        "processed_files": 0,
        "start_time": None,
        "chunks_per_second": 0.0,
        "cpu_percent": 0.0,
        "memory_percent": 0.0,
        "estimated_time_remaining": 0,
    }
    status.update(overrides)
    return status


def init() -> None:
    """Validate configuration, wait for Chroma, and load local models."""
    required = {
        "OLLAMA_MODEL": "LLM model name for Ollama",
        "CHROMA_HOST": "ChromaDB host address",
        "CHROMA_PORT": "ChromaDB port number",
    }
    missing = [f"{name} ({description})" for name, description in required.items() if not os.getenv(name)]
    if missing:
        message = "Missing required environment variables:\n" + "\n".join(f"  - {item}" for item in missing)
        logger.error(message)
        raise ValueError(message)

    apply_offline_mode()
    torch.set_num_threads(config.torch_threads())
    logger.info("Torch CPU threads set to %s", config.torch_threads())
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    connect_chroma()
    threading.Thread(target=_warm_up, name="talkback-warmup", daemon=True).start()


_models_ready = threading.Event()


def models_ready() -> bool:
    return _models_ready.is_set()


def wait_for_models(timeout: float = 180) -> None:
    """Block a query or ingest until the background warm-up has finished."""
    if _models_ready.wait(timeout):
        if Settings.embed_model is None or Settings.llm is None:
            raise RuntimeError("Local models did not finish loading.")
        return
    raise TimeoutError("Talkback is still loading the local models.")


def _warm_up() -> None:
    """Load the embedder and send one short request to host Ollama."""
    try:
        model_name = config.embed_model_name()
        Settings.llm = Ollama(
            model=config.require_ollama_model(),
            base_url=config.ollama_base_url(),
            request_timeout=config.ollama_timeout(),
            context_window=config.ollama_context(),
            keep_alive=config.ollama_keep_alive(),
        )
        Settings.embed_model = HuggingFaceEmbedding(
            model_name=model_name,
            query_instruction=embeddings.query_instruction(model_name),
            text_instruction=embeddings.text_instruction(model_name),
        )
        Settings.embed_model.get_query_embedding("ping")
        Settings.llm.complete("ok")
        logger.info("Warm-up finished.")
    except Exception:
        logger.exception("Warm-up failed")
    finally:
        _models_ready.set()


def _remember_collection(collection) -> None:
    """Keep the open collection and record whether its vectors match EMBED_MODEL."""
    global db, chroma_collection, vector_store, storage_context, _reindex_required

    count = collection.count()
    current = config.embed_model_name()
    _reindex_required = embeddings.full_reindex_required(collection.metadata, count, current)
    if count == 0:
        meta = dict(collection.metadata or {})
        if meta.get(embeddings.EMBED_META_KEY) != current:
            meta[embeddings.EMBED_META_KEY] = current
            collection.modify(metadata=meta)
        _reindex_required = False
    chroma_collection = collection
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    logger.info("Embedding model %s. Full re-index required: %s", current, _reindex_required)


def connect_chroma() -> None:
    """Retry until Chroma accepts a heartbeat, then open the library collection."""
    global db

    host = os.getenv("CHROMA_HOST")
    port = int(os.getenv("CHROMA_PORT", "8000"))
    last_error: Exception | None = None
    for attempt in range(1, 31):
        try:
            client = chromadb.HttpClient(host=host, port=port)
            client.heartbeat()
            collection = client.get_or_create_collection("rag_collection")
            db = client
            _remember_collection(collection)
            logger.info("Connected to ChromaDB on attempt %s", attempt)
            return
        except Exception as exc:
            last_error = exc
            logger.warning("ChromaDB not ready (attempt %s/30): %s", attempt, exc)
            time.sleep(2)
    raise RuntimeError(
        f"Failed to connect to ChromaDB at {host}:{port}. "
        f"Ensure the ChromaDB service is running. Error: {last_error}"
    )


def collection_count() -> int:
    if chroma_collection is None:
        return 0
    return chroma_collection.count()


def get_or_create_cached_index() -> VectorStoreIndex:
    global cached_index
    if cached_index is not None:
        return cached_index
    logger.info("Creating VectorStoreIndex from existing vector store for query")
    cached_index = VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage_context,
    )
    return cached_index


def replace_vector_collection() -> None:
    """Drop stored vectors so the next ingest replaces the library."""
    global cached_index

    try:
        db.delete_collection("rag_collection")
        logger.info("Removed existing rag_collection before re-ingest")
    except Exception as exc:
        logger.info("No existing rag_collection to remove: %s", exc)

    collection = db.get_or_create_collection(
        "rag_collection",
        metadata={embeddings.EMBED_META_KEY: config.embed_model_name()},
    )
    cached_index = None
    _remember_collection(collection)


def rebuild_library() -> None:
    """Replace every vector with the current embedding model, then clear the block."""
    global _reindex_required
    _reindex_required = True
    replace_vector_collection()
    _reindex_required = True
    process_ingestion()
    if ingestion_status.get("status") == "error":
        _reindex_required = True
        return
    _reindex_required = False
    logger.info("Full re-index finished with %s", config.embed_model_name())


class BalancedRetriever(BaseRetriever):
    """Retrieve across the library instead of letting one large file fill every slot."""

    def __init__(self, index: VectorStoreIndex, candidate_k: int = 12, per_file: int = 2, limit: int = 4):
        self._inner = index.as_retriever(similarity_top_k=candidate_k)
        self._per_file = per_file
        self._limit = limit
        super().__init__()

    def _retrieve(self, query_bundle):
        return balance_matches(
            self._inner.retrieve(query_bundle),
            per_file=self._per_file,
            limit=self._limit,
        )


def indexed_documents() -> tuple[dict[str, tuple], set[str]]:
    """Return relative path to signature, and paths still stored without relative_path."""
    if chroma_collection is None or collection_count() == 0:
        return {}, set()
    stored = chroma_collection.get(include=["metadatas"])
    found: dict[str, tuple] = {}
    legacy: set[str] = set()
    for metadata in stored.get("metadatas") or []:
        key = chunk_key(metadata)
        if not key:
            continue
        if key not in found:
            found[key] = indexed_signature(metadata)
        if chunk_is_legacy(metadata):
            legacy.add(key)
    return found, legacy


def delete_chunks_for_file(relative_path: str) -> int:
    """Remove indexed chunks for one library path and drop the in-memory index."""
    global cached_index
    if chroma_collection is None:
        return 0
    ids: set[str] = set()
    direct = chroma_collection.get(where={"relative_path": relative_path})
    ids.update(direct.get("ids") or [])
    named = chroma_collection.get(where={"file_name": Path(relative_path).name}, include=["metadatas"])
    for chunk_id, metadata in zip(named.get("ids") or [], named.get("metadatas") or []):
        if chunk_belongs_to(metadata, relative_path):
            ids.add(chunk_id)
    if ids:
        chroma_collection.delete(ids=list(ids))
    cached_index = None
    return len(ids)


_ingest_lock = threading.Lock()
_ingest_again = False


def begin_ingestion() -> bool:
    """Mark ingestion as running. Queue another pass when a job is already active."""
    global _ingest_again
    with _ingest_lock:
        if ingestion_status.get("status") == "processing":
            _ingest_again = True
            return False
        _ingest_again = False
        ingestion_status.clear()
        ingestion_status.update(_fresh_status(status="processing", message="Starting ingestion..."))
        return True


def _take_followup() -> bool:
    """Start another pass when files arrived while the last one was running."""
    global _ingest_again
    with _ingest_lock:
        if not _ingest_again:
            return False
        _ingest_again = False
        ingestion_status.clear()
        ingestion_status.update(_fresh_status(status="processing", message="Starting ingestion..."))
        return True


def _touch_resources() -> None:
    ingestion_status["cpu_percent"] = round(psutil.cpu_percent(interval=None), 1)
    ingestion_status["memory_percent"] = round(psutil.virtual_memory().percent, 1)


def _finish_kept(started: float, message: str, files: int) -> None:
    kept = collection_count()
    ingestion_status.update(_fresh_status(
        status="completed",
        message=message,
        progress=100,
        current=kept,
        total=kept,
        total_files=files,
        processed_files=files,
        start_time=started,
        cpu_percent=ingestion_status["cpu_percent"],
        memory_percent=ingestion_status["memory_percent"],
    ))


def process_ingestion() -> None:
    """Add new or changed files, and index anything that arrived during the pass."""
    while True:
        _ingest_once()
        if not _take_followup():
            return


def _ingest_once() -> None:
    """Add new or changed files without dropping documents already indexed."""
    global cached_index

    logger.info("Ingestion started for %s", UPLOAD_DIR)
    try:
        wait_for_models()
        started = time.time()
        ingestion_status["start_time"] = started
        ingestion_status["status"] = "processing"
        ingestion_status["message"] = "Checking the library..."
        ingestion_status["progress"] = 10

        file_list = visible_files(UPLOAD_DIR)
        by_key = {library_key(path, UPLOAD_DIR): path for path in file_list}
        on_disk = {key: disk_signature(path) for key, path in by_key.items()}
        indexed, legacy_keys = indexed_documents()
        embed_names, drop_names = index_plan(on_disk, indexed, legacy_keys)
        ingestion_status["total_files"] = len(embed_names)
        ingestion_status["processed_files"] = 0
        logger.info(
            "Index plan: embed %s, drop %s, keep %s",
            embed_names,
            drop_names,
            sorted(set(indexed) - set(drop_names)),
        )

        for name in drop_names:
            delete_chunks_for_file(name)

        if not embed_names:
            message = (
                f"Kept {len(on_disk)} documents already in the library. Nothing new to add."
                if on_disk else
                "Library is empty."
            )
            _finish_kept(started, message, len(on_disk))
            logger.info("Ingestion unchanged. %s files already indexed.", len(on_disk))
            return

        paths = [by_key[name] for name in embed_names]
        key_by_resolved = {path.resolve(): key for key, path in by_key.items()}
        documents = SimpleDirectoryReader(input_files=[str(path) for path in paths]).load_data()
        for document in documents:
            file_path = Path(document.metadata.get("file_path", ""))
            relative = key_by_resolved.get(file_path.resolve())
            if relative is None and file_path.is_file():
                try:
                    relative = library_key(file_path, UPLOAD_DIR)
                except ValueError:
                    relative = file_path.name
            if relative:
                document.metadata["relative_path"] = relative
            if file_path.is_file():
                document.metadata["source_mtime"] = int(file_path.stat().st_mtime)

        if not documents:
            _finish_kept(started, "No readable text in the new files. Existing documents were kept.", len(on_disk))
            logger.info("Ingestion found no readable text in %s", embed_names)
            return

        nodes = SentenceSplitter(
            chunk_size=config.chunk_size(),
            chunk_overlap=config.chunk_overlap(),
        ).get_nodes_from_documents(documents)
        total = len(nodes)
        ingestion_status["total"] = total
        ingestion_status["current"] = 0
        ingestion_status["message"] = f"Adding {total} chunks from {len(embed_names)} file(s)..."
        logger.info("Adding %s chunks from %s", total, embed_names)

        index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
        chunk_started = time.time()
        completed_files = 0
        active_file = None
        batch_size = config.embed_batch()
        for offset in range(0, total, batch_size):
            batch = nodes[offset:offset + batch_size]
            index.insert_nodes(batch)
            done = min(offset + len(batch), total)
            ingestion_status.update(ingest_metrics(done, total, time.time() - chunk_started))
            ingestion_status["status"] = "processing"
            current_name = batch[-1].metadata.get("relative_path") or batch[-1].metadata.get("file_name")
            if active_file is None:
                active_file = current_name
            elif current_name != active_file:
                completed_files += 1
                active_file = current_name
            ingestion_status["current_file"] = current_name
            ingestion_status["processed_files"] = completed_files
            ingestion_status["message"] = f"Embedded {done} of {total} new chunks"
            _touch_resources()

        elapsed = time.time() - chunk_started
        speed = total / elapsed if elapsed > 0 else 0
        cached_index = index
        library_total = collection_count()
        ingestion_status.update(_fresh_status(
            status="completed",
            message=f"Added {total} chunks from {len(embed_names)} file(s). Existing documents were kept.",
            progress=100,
            current=library_total,
            total=library_total,
            total_files=len(on_disk),
            processed_files=len(embed_names),
            chunks_per_second=round(speed, 2),
            cpu_percent=ingestion_status["cpu_percent"],
            memory_percent=ingestion_status["memory_percent"],
            start_time=started,
        ))
        logger.info(
            "Ingestion complete. Added %s chunks from %s. Library now has %s chunks.",
            total,
            embed_names,
            library_total,
        )
    except Exception as exc:
        logger.exception("Ingestion failed")
        ingestion_status["status"] = "error"
        ingestion_status["message"] = "Ingestion failed"
        ingestion_status["error"] = "Ingestion failed"
        ingestion_status["progress"] = 0
        ingestion_status["current_file"] = None
        logger.error("Ingestion failed: %s", exc)


def _complete(prompt: str, temperature: float | None = None) -> str:
    """Complete one prompt, pinning temperature only for that call."""
    llm = Settings.llm
    if temperature is None or not hasattr(llm, "temperature"):
        return str(llm.complete(prompt)).strip()
    previous = llm.temperature
    llm.temperature = temperature
    try:
        return str(llm.complete(prompt)).strip()
    finally:
        llm.temperature = previous


def _source_record(node, number: int) -> dict:
    """Keep the citation number, file, page, and excerpt for one retrieved chunk."""
    metadata = node.metadata or {}
    file_name = metadata.get("relative_path") or metadata.get("file_name") or "Document"
    page = metadata.get("page_label") or metadata.get("page_number")
    record = {
        "number": number,
        "source": file_name,
        "path": metadata.get("relative_path") or file_name,
        "text": (node.get_text() or "")[:500],
    }
    if page not in (None, ""):
        record["page"] = str(page)
    record["label"] = source_label(record)
    return record


def _retrieve_nodes(index: VectorStoreIndex, query: str, library_files: list[str]):
    """Search the library, and stay inside a file the question names."""
    per_file = config.retrieve_per_file()
    limit = config.retrieve_limit()
    nodes = index.as_retriever(similarity_top_k=config.retrieve_candidates()).retrieve(query)
    named = set(named_library_files(query, library_files))
    if named:
        preferred = [
            node for node in nodes
            if ((node.metadata or {}).get("relative_path") or (node.metadata or {}).get("file_name")) in named
        ]
        if preferred:
            return balance_matches(preferred, per_file=per_file, limit=limit)
    return balance_matches(nodes, per_file=per_file, limit=limit)


def _stream_deltas(prompt: str, temperature: float | None = None):
    """Yield text deltas from Ollama.stream_complete, which this version provides."""
    llm = Settings.llm
    previous = getattr(llm, "temperature", None)
    if temperature is not None and hasattr(llm, "temperature"):
        llm.temperature = temperature
    try:
        for chunk in llm.stream_complete(prompt):
            delta = chunk.delta or ""
            if delta:
                yield delta
    finally:
        if temperature is not None and hasattr(llm, "temperature"):
            llm.temperature = previous


def _library_matches(nodes) -> bool:
    scores = [getattr(node, "score", None) for node in nodes]
    return embeddings.relevant_enough(scores, config.relevance_threshold())


def _stream_prompt(prompt: str, temperature: float | None, sources: list | None, notice: str | None = None):
    """Stream one completion. A notice is sent before the first token."""
    if notice:
        yield {"event": "notice", "data": {"text": notice}}
    parts: list[str] = []
    for delta in _stream_deltas(prompt, temperature):
        parts.append(delta)
        yield {"event": "token", "data": {"text": delta}}
    reply = "".join(parts).strip()
    if sources is None:
        logger.info("Query answered as assistant")
        yield {"event": "sources", "data": {"sources": []}}
        yield {"event": "done", "data": {}}
        return
    used = supporting_sources(reply, sources)
    if used and not cited_source_indexes(reply):
        marks = " ".join(f"[{source['number']}]" for source in used)
        extra = f" {marks}"
        yield {"event": "token", "data": {"text": extra}}
    if not used:
        logger.info("Query kept the library draft without a matching source")
        yield {"event": "footnote", "data": {"text": UNMATCHED_SOURCE_NOTE}}
        yield {"event": "sources", "data": {"sources": []}}
        yield {"event": "done", "data": {}}
        return
    logger.info("Query cited %s", [source["source"] for source in used])
    yield {"event": "sources", "data": {"sources": used}}
    yield {"event": "done", "data": {}}


def iter_answer(query: str):
    """Yield token events, then sources. Uses Ollama.stream_complete."""
    logger.info("Query started (%s characters)", len(query or ""))
    wait_for_models()
    try:
        if collection_count() == 0 or not should_search_library(query):
            yield from _stream_prompt(assistant_prompt(query), None, None)
            return
        index = get_or_create_cached_index()
        indexed, _legacy = indexed_documents()
        library_files = sorted(indexed)
        nodes = _retrieve_nodes(index, query, library_files)
        if not _library_matches(nodes):
            logger.info("Retrieval score below %s. Answering generally.", config.relevance_threshold())
            yield from _stream_prompt(assistant_prompt(query), None, None, GENERAL_NOTICE)
            return
        sources = [_source_record(node, number) for number, node in enumerate(nodes, 1)]
        prompt = explanation_prompt(
            query,
            library_files,
            [f"{source['source']}\n{source['text']}" for source in sources],
        )
        yield from _stream_prompt(prompt, 0.1, sources)
    except Exception:
        logger.exception("Query failed")
        raise


def assistant_reply(query: str) -> str:
    """Answer as a general assistant, with no document requirement."""
    return _complete(assistant_prompt(query))


def answer_query(query: str) -> dict:
    """Answer from the library when it applies, and as an assistant otherwise."""
    text: list[str] = []
    sources: list = []
    notice = None
    footnote = None
    for event in iter_answer(query):
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
