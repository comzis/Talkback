# app/main.py
import json
import os
import logging
import shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import List
import asyncio

import config
import retrieval.rerank as rerank
import store.embeddings as embeddings
import store.host_embed as host_embed
import engine
from state import get
from store.status_db import StatusStore
from sources.base import ReadOnlyLibrary
from llm.client import (
    OllamaOnly,
    installed_model_names,
    models_url,
    reject_unless_ollama,
)
from sources.filesystem import (
    InvalidFilename,
    filesystem_source,
    get_file_type,
    safe_relative_path,
    stored_filename,
    visible_files,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- FastAPI App ---
app = FastAPI(title="Secure Local RAG API")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.middleware("http")
async def disable_asset_cache(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


engine.init()
app.state.talkback = get()


class ChatTurn(BaseModel):
    role: str
    content: str


class QueryRequest(BaseModel):
    query: str
    history: list[ChatTurn] = []


class QueryResponse(BaseModel):
    response: str
    sources: list[dict]
    notice: str | None = None
    footnote: str | None = None


class LLMSelectRequest(BaseModel):
    model: str


class LLMPullRequest(BaseModel):
    model: str


def _ollama_only() -> None:
    """Block model list, select, and pull when chat is a vLLM server."""
    try:
        reject_unless_ollama()
    except OllamaOnly as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _reject_if_reindex_required() -> None:
    if engine.reindex_required():
        raise HTTPException(status_code=409, detail=embeddings.REINDEX_MESSAGE)


@app.post("/ingest")
async def ingest_documents():
    """Ask the indexer to add new or changed files. This process does not embed them."""
    _reject_if_reindex_required()
    if not engine.enqueue_ingestion("incremental"):
        return {"message": "Ingestion already in progress", "status": "processing"}

    return {
        "message": "Adding new documents. Files already indexed are kept.",
        "status": "processing",
    }


@app.post("/ingest/rebuild")
async def rebuild_index():
    """Ask the indexer to drop the collection and embed every file again."""
    if not engine.enqueue_ingestion("rebuild"):
        return {"message": "Ingestion already in progress", "status": "processing"}
    return {
        "message": "Full re-index started. The old vectors are being replaced.",
        "status": "processing",
    }


@app.get("/ingest/status")
async def get_ingestion_status():
    """Progress written by the indexer. This process only reads it."""
    shared = StatusStore(get().status_dir / "library.sqlite").read_job()
    if shared:
        return shared
    return get().ingestion_status


@app.get("/system/resources")
async def get_system_resources():
    """
    Get real-time CPU and memory usage from the system.
    """
    import psutil
    import time

    return {
        "cpu_percent": round(psutil.cpu_percent(interval=0.1), 1),
        "memory_percent": round(psutil.virtual_memory().percent, 1),
        "timestamp": time.time(),
    }


@app.post("/query", response_model=QueryResponse)
async def query_index(request: QueryRequest):
    """
    Handles a user's query using the RAG logic and returns a
    response with source citations, as per your guideline.
    """
    if not request.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    _reject_if_reindex_required()

    try:
        return await asyncio.to_thread(
            engine.answer_query, request.query, request.history
        )
    except Exception:
        raise HTTPException(status_code=500, detail="The query could not be completed.")


@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    """Stream answer tokens, then the sources the finished answer used."""
    if not request.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    _reject_if_reindex_required()

    def generate():
        # Safari drops a fetch stream that stays silent while retrieval starts.
        yield ": open\n\n"
        try:
            for event in engine.iter_answer(request.query, request.history):
                payload = json.dumps(event["data"], ensure_ascii=False)
                yield f"event: {event['event']}\ndata: {payload}\n\n"
        except Exception:
            logger.exception("Streamed query failed")
            yield 'event: error\ndata: {"detail": "The query could not be completed."}\n\n'

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/health")
def health_check():
    """Simple health check to confirm the API is running."""
    return {"status": "ok"}


@app.get("/system/status")
async def get_system_status():
    """
    Comprehensive system status including API, LLM, Database, and alarms.
    """
    import time

    status = {
        "timestamp": time.time(),
        "api": {"status": "online", "uptime": "running"},
        "llm": {
            "status": "unknown",
            "available": False,
            "model_configured": None,
            "response_time_ms": None,
            "error": None,
        },
        "offline_mode": engine.offline_mode(),
        "library_read_only": engine.library_read_only(),
        "reindex_required": engine.reindex_required(),
        "files_waiting": engine.files_waiting(),
        "embed_model": config.embed_model_name(),
        "embed": host_embed.active_embed(),
        "rerank": rerank.active_rerank(),
        "database": {
            "status": "unknown",
            "connected": False,
            "collection_count": 0,
            "error": None,
        },
        "alarms": [],
    }

    # Check LLM status
    try:
        llm_status = await get_llm_status()
        status["llm"] = llm_status
        if not llm_status.get("available", False):
            status["alarms"].append(
                {
                    "type": "warning",
                    "component": "llm",
                    "message": f"LLM is {llm_status.get('status', 'unknown')}: {llm_status.get('error', 'Unknown error')}",
                }
            )
    except Exception:
        status["llm"]["status"] = "error"
        logger.exception("Failed to check LLM status")
        status["llm"]["error"] = "The language model could not be reached."
        status["alarms"].append(
            {
                "type": "error",
                "component": "llm",
                "message": "The language model could not be reached.",
            }
        )

    # Check Database status
    try:
        collection_count = engine.collection_count()
        status["database"]["status"] = "online"
        status["database"]["connected"] = True
        status["database"]["collection_count"] = collection_count
    except Exception:
        status["database"]["status"] = "offline"
        status["database"]["connected"] = False
        logger.exception("Database connection error")
        status["database"]["error"] = "Database connection error"
        status["alarms"].append(
            {
                "type": "error",
                "component": "database",
                "message": "Database connection error",
            }
        )

    if status["rerank"].get("host") == "unreachable":
        status["alarms"].append(
            {
                "type": "warning",
                "component": "rerank",
                "message": "Host reranker is unreachable. Scoring pairs in the container.",
            }
        )

    # Check ingestion status for warnings
    if get().ingestion_status.get("status") == "error":
        status["alarms"].append(
            {"type": "warning", "component": "ingestion", "message": "Ingestion failed"}
        )

    return status


@app.get("/files/types")
async def get_file_types():
    """
    Get file type statistics grouped by category.
    """
    try:
        files_data = await list_uploaded_files()
        files = files_data.get("files", [])
        by_type = files_data.get("by_type", {})

        # Get detailed breakdown
        type_details = {}
        for file_type in ["document", "code", "data", "image", "other"]:
            type_files = [f for f in files if f["type"] == file_type]
            total_size = sum(f["size"] for f in type_files)

            type_details[file_type] = {
                "count": by_type.get(file_type, 0),
                "total_size": total_size,
                "files": [
                    {
                        "name": f["filename"],
                        "size": f["size"],
                        "extension": f["extension"],
                    }
                    for f in type_files[:10]  # Limit to first 10 for performance
                ],
            }

        return {
            "by_type": type_details,
            "total_files": len(files),
            "total_size": sum(f["size"] for f in files),
        }
    except Exception as e:
        logger.error(f"Error getting file types: {e}")
        raise HTTPException(
            status_code=500, detail="The request could not be completed."
        )


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the chatbot interface."""
    try:
        with open(STATIC_DIR / "index.html", "r") as f:
            return HTMLResponse(content=f.read(), headers={"Cache-Control": "no-cache"})
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Chatbot interface not found</h1>", status_code=404
        )


@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Save files into the library and index them in the same request.
    """
    try:
        filesystem_source().ensure_writable("upload")
    except ReadOnlyLibrary:
        raise HTTPException(
            status_code=403,
            detail="The library is read-only. Indexing reads the mounted folder and does not upload files.",
        )
    try:
        named_files = []
        for file in files:
            try:
                named_files.append((file, stored_filename(file.filename)))
            except InvalidFilename:
                raise HTTPException(status_code=400, detail="Invalid filename")

        uploaded_files = []
        for file, safe_name in named_files:
            file_path = get().upload_dir / safe_name
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            uploaded_files.append(safe_name)
            logger.info(f"Uploaded file: {safe_name}")

        if engine.reindex_required():
            raise HTTPException(status_code=409, detail=embeddings.REINDEX_MESSAGE)
        engine.enqueue_ingestion("incremental")

        return {
            "message": f"Added {len(uploaded_files)} file(s) and started indexing.",
            "files": uploaded_files,
            "uploaded_count": len(uploaded_files),
            "status": "processing",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during file upload: {e}")
        raise HTTPException(
            status_code=500, detail="The request could not be completed."
        )


@app.delete("/files/{filename:path}")
async def delete_uploaded_file(filename: str):
    """Delete one library file and only the chunks that came from that relative path."""
    try:
        filesystem_source().ensure_writable("delete")
    except ReadOnlyLibrary:
        raise HTTPException(
            status_code=403,
            detail="The library is read-only. Indexing reads the mounted folder and does not delete files.",
        )
    try:
        relative = safe_relative_path(filename)
    except InvalidFilename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = (get().upload_dir / relative).resolve()
    root = get().upload_dir.resolve()
    if not file_path.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        file_path.unlink()
        removed = engine.delete_chunks_for_file(relative)
    except Exception:
        logger.exception("Failed to delete %s", relative)
        raise HTTPException(status_code=500, detail="The file could not be deleted.")

    return {"deleted": relative, "chunks_removed": removed}


@app.get("/files")
async def list_uploaded_files():
    """
    List visible files currently in the data directory, sorted by file type.
    """
    try:
        status = StatusStore(get().status_dir / "library.sqlite")
        status.open()
        files = []
        for file_path in visible_files(get().upload_dir):
            rel_path = file_path.relative_to(get().upload_dir).as_posix()
            filename = Path(rel_path).name
            file_type = get_file_type(filename)
            row = status.get("filesystem", rel_path)
            files.append(
                {
                    "name": rel_path,
                    "filename": filename,
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                    "type": file_type,
                    "extension": Path(filename).suffix.lower(),
                    "index_status": None if row is None else row["status"],
                    "index_error": None if row is None else row["last_error"],
                }
            )

        # Sort by type first, then by name within each type
        type_order = {"document": 0, "code": 1, "data": 2, "image": 3, "other": 4}
        files_sorted = sorted(
            files, key=lambda x: (type_order.get(x["type"], 99), x["name"].lower())
        )

        return {
            "files": files_sorted,
            "count": len(files),
            "by_type": {
                file_type: len([f for f in files if f["type"] == file_type])
                for file_type in ["document", "code", "data", "image", "other"]
            },
        }
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(
            status_code=500, detail="The request could not be completed."
        )


@app.get("/llm/models")
async def list_llm_models():
    """
    List all available Ollama models and return the currently configured model.
    """
    _ollama_only()
    try:
        import httpx

        ollama_base = config.ollama_base_url()
        ollama_url = f"{ollama_base}/api/tags"

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(ollama_url)
            if response.status_code == 200:
                models_data = response.json().get("models", [])
                models = []
                for model in models_data:
                    models.append(
                        {
                            "name": model.get("name", ""),
                            "size": model.get("size", 0),
                            "modified": model.get("modified_at", ""),
                        }
                    )

                # Get the current model from environment
                current_model = config.configured_model()

                return {
                    "models": models,
                    "count": len(models),
                    "current_model": current_model,
                }
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to fetch models from Ollama",
                )
    except Exception as e:
        logger.error(f"Error listing LLM models: {e}")
        raise HTTPException(
            status_code=500, detail="The request could not be completed."
        )


@app.post("/llm/select")
async def select_llm_model(request: LLMSelectRequest):
    """
    Switch to a different LLM model.
    """
    _ollama_only()
    try:
        import httpx

        # First verify the model exists
        ollama_base = config.ollama_base_url()
        ollama_url = f"{ollama_base}/api/tags"

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(ollama_url)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]

                # Check if model exists (exact match or starts with)
                model_found = any(
                    m.startswith(request.model) or request.model == m
                    for m in model_names
                )

                if not model_found:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Model '{request.model}' not found. Available models: {model_names}",
                    )

                chat = get().chat
                if chat is None or not hasattr(chat, "use_model"):
                    raise HTTPException(
                        status_code=503, detail="The chat client is not ready."
                    )
                chat.use_model(request.model)
                os.environ["OLLAMA_MODEL"] = request.model
                get().cached_index = None

                logger.info(f"Switched LLM model to: {request.model}")

                return {
                    "message": f"Successfully switched to model: {request.model}",
                    "model": request.model,
                }
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to connect to Ollama",
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error selecting LLM model: {e}")
        raise HTTPException(
            status_code=500, detail="The request could not be completed."
        )


@app.post("/llm/pull")
async def pull_llm_model(request: LLMPullRequest, background_tasks: BackgroundTasks):
    """
    Pull a model through the host Ollama. Refused while OFFLINE_MODE is on.
    """
    _ollama_only()
    if engine.offline_mode():
        raise HTTPException(
            status_code=403,
            detail="Model download is disabled while OFFLINE_MODE is true. Set OFFLINE_MODE=false and restart only for a one-off setup download.",
        )
    try:
        import httpx

        ollama_base = config.ollama_base_url()
        ollama_url = f"{ollama_base}/api/pull"

        # Start the pull in background
        async def pull_model():
            try:
                async with httpx.AsyncClient(timeout=300.0) as client:
                    async with client.stream(
                        "POST", ollama_url, json={"name": request.model}
                    ) as response:
                        if response.status_code != 200:
                            logger.error(
                                f"Failed to pull model: {response.status_code}"
                            )
                            return
                        # Stream the response to show progress
                        async for line in response.aiter_lines():
                            if line:
                                logger.info(f"Ollama pull: {line}")
            except Exception as e:
                logger.error(f"Error pulling model: {e}")

        background_tasks.add_task(pull_model)

        return {
            "message": f"Started pulling model: {request.model}",
            "model": request.model,
            "status": "pulling",
        }
    except Exception as e:
        logger.error(f"Error initiating model pull: {e}")
        raise HTTPException(
            status_code=500, detail="The request could not be completed."
        )


@app.get("/llm/status")
async def get_llm_status():
    """
    Check if the LLM (Ollama) is running and responding.
    Enhanced with response time metrics.
    """
    try:
        import httpx
        import time

        backend = config.chat_backend()
        base = config.chat_base_url() if backend == "vllm" else config.ollama_base_url()
        status_url = models_url(base, backend)

        start_time = time.time()
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(status_url)
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            if response.status_code == 200:
                names = installed_model_names(response.json(), backend)
                model_name = config.configured_model()
                model_available = any(name.startswith(model_name) for name in names)

                return {
                    "status": "online",
                    "available": True,
                    "model_configured": model_name,
                    "model_available": model_available,
                    "models_installed": names,
                    "response_time_ms": round(response_time, 2),
                }
            else:
                return {
                    "status": "error",
                    "available": False,
                    "error": f"Ollama returned status {response.status_code}",
                    "response_time_ms": round(response_time, 2),
                }
    except Exception:
        logger.exception("Error checking LLM status")
        return {
            "status": "offline",
            "available": False,
            "error": "Ollama is offline",
            "response_time_ms": None,
        }
