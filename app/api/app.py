"""HTTP app for Talkback: static files, middleware, and routers."""

import logging
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import engine
from api.deps import STATIC_DIR
from api.routers import ingest, library, llm, query, system
from state import get

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- FastAPI App ---
app = FastAPI(title="Secure Local RAG API")

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

app.include_router(ingest.router)
app.include_router(query.router)
app.include_router(system.router)
app.include_router(library.router)
app.include_router(llm.router)
