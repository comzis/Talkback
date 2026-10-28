"""Incremental ingest, the status payload, and the re-index timer."""

from __future__ import annotations

import logging
import os
import socket
import threading
import time
from pathlib import Path

import psutil
from llama_index.core import VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter

import config
from ingestion.plan import disk_signature, index_plan, library_key, reindex_minutes
from ingestion.progress import ingest_metrics
from llm.client import wait_for_models
from sources.filesystem import filesystem_source
from state import get
from store.chroma import (
    chunk_metadatas,
    collection_count,
    delete_chunks_for_file,
    mark_file_complete,
    reindex_required,
    replace_vector_collection,
)
from store.status_db import StatusStore

logger = logging.getLogger(__name__)

# SimpleDirectoryReader keeps file_path and page_label, and drops these.
# relative_path and source_mtime stay, because the demo tag embedded them.
_READER_BOOKKEEPING = (
    "file_name",
    "file_type",
    "file_size",
    "creation_date",
    "last_modified_date",
    "last_accessed_date",
)
# Added after the demo tag. They must not enter the embedding or an LLM prompt.
_SOURCE_BOOKKEEPING = ("source_type", "source_id")


def _hide_from_models(node, keys: tuple[str, ...]) -> None:
    for key in keys:
        if key not in node.excluded_embed_metadata_keys:
            node.excluded_embed_metadata_keys.append(key)
        if key not in node.excluded_llm_metadata_keys:
            node.excluded_llm_metadata_keys.append(key)


_heartbeat_stop: threading.Event | None = None


def lock_holder() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def _publish() -> None:
    """Copy the in-memory progress so the API process can read it."""
    open_status().write_job(dict(get().ingestion_status))


def _beat(holder: str, stop: threading.Event) -> None:
    while not stop.wait(10):
        if not open_status().refresh_lock(holder):
            logger.error("Lost the ingest lock.")
            return


def _start_heartbeat(holder: str) -> None:
    global _heartbeat_stop
    _stop_heartbeat()
    _heartbeat_stop = threading.Event()
    threading.Thread(
        target=_beat,
        args=(holder, _heartbeat_stop),
        name="talkback-ingest-lock",
        daemon=True,
    ).start()


def _stop_heartbeat() -> None:
    global _heartbeat_stop
    if _heartbeat_stop is not None:
        _heartbeat_stop.set()
        _heartbeat_stop = None


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
                logger.info(
                    "Scheduled re-index skipped because indexing is already running."
                )
                continue
            logger.info("Scheduled re-index started.")
            try:
                process_ingestion()
            finally:
                finish_ingestion()

    threading.Thread(target=loop, name="talkback-reindex", daemon=True).start()
    logger.info("Scheduled re-index every %s minutes.", minutes)


def start_initial_index() -> None:
    """Index files on disk that are missing or were only partly stored."""

    def run() -> None:
        started = False
        try:
            wait_for_models()
            if reindex_required():
                return
            if not begin_ingestion():
                return
            started = True
            logger.info("Checking the library for files that are not fully indexed.")
            process_ingestion()
        except Exception:
            logger.exception("Initial index failed")
        finally:
            if started:
                finish_ingestion()

    threading.Thread(target=run, name="talkback-initial-index", daemon=True).start()


def files_waiting() -> bool:
    """True when the folder has files and the vector collection is empty."""
    return collection_count() == 0 and bool(filesystem_source().list_items())


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
        "finished_at": get().last_indexed_at,
        "chunks_per_second": 0.0,
        "cpu_percent": 0.0,
        "memory_percent": 0.0,
        "estimated_time_remaining": 0,
    }
    status.update(overrides)
    return status


def rebuild_library() -> None:
    """Replace every vector with the current embedding model, then clear the block."""
    get().needs_reindex = True
    replace_vector_collection()
    open_status().clear()
    get().needs_reindex = True
    process_ingestion()
    if get().ingestion_status.get("status") == "error":
        get().needs_reindex = True
        return
    get().needs_reindex = False
    logger.info("Full re-index finished with %s", config.embed_model_name())


def enqueue_ingestion(kind: str = "incremental") -> bool:
    """Ask the indexer to run. False when a run already holds the lock."""
    store = open_status()
    store.request_run(kind)
    return not store.lock_held()


def begin_ingestion() -> bool:
    """Mark ingestion as running. A second process waits its turn on the lock row."""
    with get().ingest_lock:
        if get().ingestion_status.get("status") == "processing":
            get().ingest_again = True
            return False
        holder = lock_holder()
        if not open_status().try_lock(holder):
            return False
        get().ingest_again = False
        _start_heartbeat(holder)
        get().ingestion_status.clear()
        get().ingestion_status.update(
            _fresh_status(status="processing", message="Starting ingestion...")
        )
        _publish()
        return True


def finish_ingestion() -> None:
    """Release the lock row when the run that acquired it has finished."""
    _stop_heartbeat()
    open_status().unlock(lock_holder())


def _take_followup() -> bool:
    """Start another pass when files arrived while the last one was running."""
    with get().ingest_lock:
        if not get().ingest_again:
            return False
        get().ingest_again = False
        get().ingestion_status.clear()
        get().ingestion_status.update(
            _fresh_status(status="processing", message="Starting ingestion...")
        )
        return True


def _touch_resources() -> None:
    get().ingestion_status["cpu_percent"] = round(psutil.cpu_percent(interval=None), 1)
    get().ingestion_status["memory_percent"] = round(psutil.virtual_memory().percent, 1)


def _note_indexed() -> None:
    """Remember when a pass finished, including one that found nothing new."""
    from retrieval import bm25 as bm25_index

    bm25_index.invalidate()
    get().last_indexed_at = time.time()


def _finish_kept(started: float, message: str, files: int) -> None:
    kept = collection_count()
    _note_indexed()
    get().ingestion_status.update(
        _fresh_status(
            status="completed",
            message=message,
            progress=100,
            current=kept,
            total=kept,
            total_files=files,
            processed_files=files,
            start_time=started,
            cpu_percent=get().ingestion_status["cpu_percent"],
            memory_percent=get().ingestion_status["memory_percent"],
        )
    )
    _publish()


def nodes_for_index(documents, source):
    """Split, then record the source. The splitter counts metadata toward the chunk size.

    relative_path and source_mtime are already on the documents, as they were
    before source_type existed. Adding those two fields first changes the boundaries.
    """
    nodes = SentenceSplitter(
        chunk_size=config.chunk_size(),
        chunk_overlap=config.chunk_overlap(),
    ).get_nodes_from_documents(documents)
    for node in nodes:
        item_id = str((node.metadata or {}).get("relative_path") or "").strip()
        if item_id:
            source.describe_chunk(item_id, node.metadata)
        _hide_from_models(node, _READER_BOOKKEEPING + _SOURCE_BOOKKEEPING)
    return nodes


def process_ingestion() -> None:
    """Add new or changed files, and index anything that arrived during the pass."""
    while True:
        _ingest_once()
        if not _take_followup():
            return


def open_status() -> StatusStore:
    """The local status file. It is not stored on the library share."""
    store = StatusStore(get().status_dir / "library.sqlite")
    store.open()
    return store


def _ingest_once() -> None:
    """Add new or changed files without dropping documents already indexed."""
    logger.info("Ingestion started for %s", get().upload_dir)
    status: StatusStore | None = None
    try:
        wait_for_models()
        started = time.time()
        get().ingestion_status["start_time"] = started
        get().ingestion_status["status"] = "processing"
        get().ingestion_status["message"] = "Checking the library..."
        get().ingestion_status["progress"] = 10
        _publish()

        source = filesystem_source()
        status = open_status()
        if status.empty():
            status.migrate(chunk_metadatas())
        items = source.list_items()
        by_key = {item.id: item for item in items}
        on_disk = {item.id: disk_signature(Path(item.location)) for item in items}
        indexed, legacy_keys, incomplete_keys = status.planning_sets()
        embed_names, drop_names = index_plan(
            on_disk, indexed, legacy_keys, incomplete_keys
        )
        known = set(indexed) | set(legacy_keys) | set(incomplete_keys)
        for name in source.deleted_ids(known):
            if name not in drop_names:
                drop_names.append(name)
        get().ingestion_status["total_files"] = len(embed_names)
        get().ingestion_status["processed_files"] = 0
        logger.info(
            "Index plan: embed %s, drop %s, keep %s",
            embed_names,
            drop_names,
            sorted(set(indexed) - set(drop_names)),
        )

        for name in drop_names:
            delete_chunks_for_file(name)
            status.forget(source.source_type, name)

        if not embed_names:
            message = (
                f"Kept {len(on_disk)} documents already in the library. Nothing new to add."
                if on_disk
                else "Library is empty."
            )
            _finish_kept(started, message, len(on_disk))
            logger.info("Ingestion unchanged. %s files already indexed.", len(on_disk))
            return

        paths = [Path(by_key[name].location) for name in embed_names]
        key_by_resolved = {path.resolve(): key for key, path in zip(embed_names, paths)}
        documents = source.read([str(path) for path in paths])
        from llm.prompts import normalize_extracted_text

        for document in documents:
            text = document.get_content() if hasattr(document, "get_content") else None
            if text is None:
                text = getattr(document, "text", "") or ""
            normalized = normalize_extracted_text(text)
            if hasattr(document, "set_content"):
                document.set_content(normalized)
            else:
                document.text = normalized
            file_path = Path(document.metadata.get("file_path", ""))
            relative = key_by_resolved.get(file_path.resolve())
            if relative is None and file_path.is_file():
                try:
                    relative = library_key(file_path, get().upload_dir)
                except ValueError:
                    relative = file_path.name
            if relative:
                document.metadata["relative_path"] = relative
            if file_path.is_file():
                document.metadata["source_mtime"] = int(file_path.stat().st_mtime)

        if not documents:
            for name in embed_names:
                status.mark_failed(source.source_type, name, "No readable text")
            _finish_kept(
                started,
                "No readable text in the new files. Existing documents were kept.",
                len(on_disk),
            )
            logger.info("Ingestion found no readable text in %s", embed_names)
            return

        nodes = nodes_for_index(documents, source)
        total = len(nodes)
        get().ingestion_status["total"] = total
        get().ingestion_status["current"] = 0
        get().ingestion_status["message"] = (
            f"Adding {total} chunks from {len(embed_names)} file(s)..."
        )
        logger.info("Adding %s chunks from %s", total, embed_names)

        index = VectorStoreIndex.from_vector_store(
            get().vector_store, storage_context=get().storage_context
        )
        chunk_started = time.time()
        batch_size = config.embed_batch()
        nodes_by_file: dict[str, list] = {}
        for node in nodes:
            key = (node.metadata or {}).get("relative_path") or (
                node.metadata or {}
            ).get("file_name")
            nodes_by_file.setdefault(key, []).append(node)
        done = 0
        completed_files = 0
        for name in embed_names:
            file_nodes = nodes_by_file.get(name, [])
            if not file_nodes:
                status.mark_failed(source.source_type, name, "No readable text")
                continue
            status.mark_pending(source.source_type, name)
            get().ingestion_status["current_file"] = name
            for offset in range(0, len(file_nodes), batch_size):
                batch = file_nodes[offset : offset + batch_size]
                index.insert_nodes(batch)
                done += len(batch)
                get().ingestion_status.update(
                    ingest_metrics(done, total, time.time() - chunk_started)
                )
                get().ingestion_status["status"] = "processing"
                get().ingestion_status["processed_files"] = completed_files
                get().ingestion_status["message"] = (
                    f"Embedded {done} of {total} new chunks"
                )
                _touch_resources()
                _publish()
            mark_file_complete(name)
            status.mark_complete(
                source.source_type, name, on_disk[name], len(file_nodes)
            )
            completed_files += 1
            get().ingestion_status["processed_files"] = completed_files

        elapsed = time.time() - chunk_started
        speed = total / elapsed if elapsed > 0 else 0
        get().cached_index = index
        library_total = collection_count()
        _note_indexed()
        get().ingestion_status.update(
            _fresh_status(
                status="completed",
                message=f"Added {total} chunks from {len(embed_names)} file(s). Existing documents were kept.",
                progress=100,
                current=library_total,
                total=library_total,
                total_files=len(on_disk),
                processed_files=len(embed_names),
                chunks_per_second=round(speed, 2),
                cpu_percent=get().ingestion_status["cpu_percent"],
                memory_percent=get().ingestion_status["memory_percent"],
                start_time=started,
            )
        )
        _publish()
        logger.info(
            "Ingestion complete. Added %s chunks from %s. Library now has %s chunks.",
            total,
            embed_names,
            library_total,
        )
    except Exception as exc:
        if status is not None:
            status.fail_pending("Ingestion failed")
        logger.exception("Ingestion failed")
        get().ingestion_status["status"] = "error"
        get().ingestion_status["message"] = "Ingestion failed"
        get().ingestion_status["error"] = "Ingestion failed"
        get().ingestion_status["progress"] = 0
        get().ingestion_status["current_file"] = None
        _publish()
        logger.error("Ingestion failed: %s", exc)
