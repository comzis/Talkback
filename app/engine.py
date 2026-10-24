"""Chroma, embeddings, ingestion, and grounded answers."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import chromadb
import psutil
from llama_index.core import Settings, SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.chroma import ChromaVectorStore

from files import visible_files
from library import balance_matches, disk_signature, indexed_signature, plan_updates
from monitoring import LangChainMonitor
from progress import ingest_metrics
from prompts import assistant_prompt, explanation_prompt, strip_citations, supporting_sources

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(os.getenv("RAG_DATA_DIR", "/app/data"))
EMBED_BATCH = 1

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

monitor = LangChainMonitor()
db = None
chroma_collection = None
vector_store = None
storage_context = None
cached_index: VectorStoreIndex | None = None


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

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    connect_chroma()
    Settings.llm = Ollama(
        model=os.getenv("OLLAMA_MODEL", "gemma2:2b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434"),
        request_timeout=300.0,
    )
    Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")


def connect_chroma() -> None:
    """Retry until Chroma accepts a heartbeat, then open the library collection."""
    global db, chroma_collection, vector_store, storage_context

    host = os.getenv("CHROMA_HOST")
    port = int(os.getenv("CHROMA_PORT", "8000"))
    last_error: Exception | None = None
    for attempt in range(1, 31):
        try:
            client = chromadb.HttpClient(host=host, port=port)
            client.heartbeat()
            collection = client.get_or_create_collection("rag_collection")
            store = ChromaVectorStore(chroma_collection=collection)
            context = StorageContext.from_defaults(vector_store=store)
            db = client
            chroma_collection = collection
            vector_store = store
            storage_context = context
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
    global chroma_collection, vector_store, storage_context, cached_index

    try:
        db.delete_collection("rag_collection")
        logger.info("Removed existing rag_collection before re-ingest")
    except Exception as exc:
        logger.info("No existing rag_collection to remove: %s", exc)

    chroma_collection = db.get_or_create_collection("rag_collection")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    cached_index = None


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


def indexed_documents() -> dict[str, tuple]:
    """Return filename to stored signature for chunks already in the index."""
    if chroma_collection is None or collection_count() == 0:
        return {}
    stored = chroma_collection.get(include=["metadatas"])
    found: dict[str, tuple] = {}
    for metadata in stored.get("metadatas") or []:
        if not metadata:
            continue
        name = metadata.get("file_name")
        if name and name not in found:
            found[name] = indexed_signature(metadata)
    return found


def delete_chunks_for_file(filename: str) -> int:
    """Remove indexed chunks for one file and drop the in-memory index."""
    global cached_index
    if chroma_collection is None:
        return 0
    existing = chroma_collection.get(where={"file_name": filename})
    ids = existing.get("ids") or []
    if ids:
        chroma_collection.delete(ids=ids)
    cached_index = None
    return len(ids)


def begin_ingestion() -> bool:
    """Mark ingestion as running. Return False when a job is already active."""
    if ingestion_status["status"] == "processing":
        return False
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
    """Add new or changed files without dropping documents already indexed."""
    global cached_index

    ingest_run_id = monitor.start_run(
        name="document_ingestion",
        run_type="chain",
        inputs={"data_path": str(UPLOAD_DIR)},
        tags=["ingestion"],
    )
    try:
        started = time.time()
        ingestion_status["start_time"] = started
        ingestion_status["status"] = "processing"
        ingestion_status["message"] = "Checking the library..."
        ingestion_status["progress"] = 10

        file_list = visible_files(UPLOAD_DIR)
        by_name = {path.name: path for path in file_list}
        on_disk = {name: disk_signature(path) for name, path in by_name.items()}
        indexed = indexed_documents()
        embed_names, drop_names = plan_updates(on_disk, indexed)
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
            monitor.end_run(ingest_run_id, outputs={"status": "unchanged", "files": len(on_disk)})
            return

        paths = [by_name[name] for name in embed_names]
        documents = SimpleDirectoryReader(input_files=[str(path) for path in paths]).load_data()
        for document in documents:
            file_path = Path(document.metadata.get("file_path", ""))
            if file_path.is_file():
                document.metadata["source_mtime"] = int(file_path.stat().st_mtime)

        if not documents:
            _finish_kept(started, "No readable text in the new files. Existing documents were kept.", len(on_disk))
            monitor.end_run(ingest_run_id, outputs={"status": "no_text", "files": embed_names})
            return

        nodes = SentenceSplitter().get_nodes_from_documents(documents)
        total = len(nodes)
        ingestion_status["total"] = total
        ingestion_status["current"] = 0
        ingestion_status["message"] = f"Adding {total} chunks from {len(embed_names)} file(s)..."
        logger.info("Adding %s chunks from %s", total, embed_names)

        index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
        chunk_started = time.time()
        completed_files = 0
        active_file = None
        for offset in range(0, total, EMBED_BATCH):
            batch = nodes[offset:offset + EMBED_BATCH]
            index.insert_nodes(batch)
            done = min(offset + len(batch), total)
            ingestion_status.update(ingest_metrics(done, total, time.time() - chunk_started))
            ingestion_status["status"] = "processing"
            current_name = batch[-1].metadata.get("file_name")
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
        logger.info("Ingestion complete. Library now has %s chunks.", library_total)
        monitor.end_run(
            ingest_run_id,
            outputs={
                "status": "completed",
                "added_chunks": total,
                "added_files": embed_names,
                "library_chunks": library_total,
                "speed": speed,
            },
        )
    except Exception as exc:
        logger.exception("Ingestion failed")
        ingestion_status["status"] = "error"
        ingestion_status["message"] = "Ingestion failed"
        ingestion_status["error"] = "Ingestion failed"
        ingestion_status["progress"] = 0
        ingestion_status["current_file"] = None
        monitor.end_run(ingest_run_id, error=str(exc))


def assistant_reply(query: str) -> str:
    """Answer as a general assistant, with no document requirement."""
    return str(Settings.llm.complete(assistant_prompt(query))).strip()


def answer_query(query: str) -> dict:
    """Answer from the library when it applies, and as an assistant otherwise."""
    query_run_id = monitor.start_run(
        name="rag_query",
        run_type="chain",
        inputs={"query": query},
        tags=["query", "rag"],
    )
    try:
        if collection_count() == 0:
            reply = assistant_reply(query)
            monitor.end_run(query_run_id, outputs={"status": "assistant"})
            return {"response": reply, "sources": []}

        index = get_or_create_cached_index()
        library_files = sorted(indexed_documents())
        nodes = BalancedRetriever(index).retrieve(query)
        sources = []
        for node in nodes:
            metadata = node.metadata or {}
            file_name = metadata.get("file_name", "Unknown Source")
            display_name = file_name if file_name != "Unknown Source" else "Document"
            sources.append({
                "source": display_name,
                "text": node.get_text()[:500],
            })
        reply = str(Settings.llm.complete(explanation_prompt(
            query,
            library_files,
            [f"{source['source']}\n{source['text']}" for source in sources],
        ))).strip()
        used = supporting_sources(reply, sources)
        if not used:
            reply = strip_citations(reply)
            monitor.end_run(query_run_id, outputs={"status": "assistant"})
            return {"response": reply, "sources": []}
        sources = used

        monitor.end_run(
            query_run_id,
            outputs={"status": "completed", "sources": [source["source"] for source in sources]},
        )
        return {"response": reply, "sources": sources}
    except Exception as exc:
        logger.exception("Query failed")
        monitor.end_run(query_run_id, error=str(exc))
        raise
