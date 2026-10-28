"""LLM model endpoints: list, select, pull, and status."""

import logging
import os

from fastapi import APIRouter, BackgroundTasks, HTTPException

import config
import engine
from api.deps import _ollama_only
from api.schemas import LLMPullRequest, LLMSelectRequest
from llm.client import installed_model_names, models_url
from state import get

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/llm/models")
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
        # Existing behavior: an upstream HTTPException is also reported as 500.
        logger.exception("Error listing LLM models")
        raise HTTPException(
            status_code=500, detail="The request could not be completed."
        ) from e


@router.post("/llm/select")
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
        logger.exception("Error selecting LLM model %s", request.model)
        raise HTTPException(
            status_code=500, detail="The request could not be completed."
        ) from e


@router.post("/llm/pull")
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
            except Exception:
                # Background task: no client is waiting, so log and stop.
                logger.exception("Error pulling model %s", request.model)

        background_tasks.add_task(pull_model)

        return {
            "message": f"Started pulling model: {request.model}",
            "model": request.model,
            "status": "pulling",
        }
    except Exception as e:
        logger.exception("Error initiating model pull for %s", request.model)
        raise HTTPException(
            status_code=500, detail="The request could not be completed."
        ) from e


@router.get("/llm/status")
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
        # Any failure (network, bad JSON, config) means offline; callers expect a dict.
        logger.exception("Error checking LLM status")
        return {
            "status": "offline",
            "available": False,
            "error": "Ollama is offline",
            "response_time_ms": None,
        }
