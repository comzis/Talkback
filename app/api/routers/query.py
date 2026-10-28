"""POST /query and /query/stream."""

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

import engine
from api.deps import _reject_if_reindex_required
from api.schemas import QueryRequest, QueryResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
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
            engine.answer_query, request.query, request.history, request.scope
        )
    except Exception as e:
        logger.exception("Query failed")
        raise HTTPException(
            status_code=500, detail="The query could not be completed."
        ) from e


@router.post("/query/stream")
async def query_stream(request: QueryRequest):
    """Stream status, retrieved candidates, answer tokens, then final sources."""
    if not request.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    _reject_if_reindex_required()

    def generate():
        # Safari drops a fetch stream that stays silent while retrieval starts.
        yield ": open\n\n"
        try:
            for event in engine.iter_answer(
                request.query, request.history, scope=request.scope
            ):
                payload = json.dumps(event["data"], ensure_ascii=False)
                yield f"event: {event['event']}\ndata: {payload}\n\n"
        except Exception:
            # Headers are already sent, so report the failure as an SSE error event.
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
