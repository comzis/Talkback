# Talkback

Offline RAG engineering assistant: FastAPI + ChromaDB + BM25 hybrid search,
`BAAI/bge-m3` embeddings and `BAAI/bge-reranker-v2-m3` reranking, chat via host
Ollama (`qwen3.8:27b`, `OLLAMA_THINK=false`, `OLLAMA_CONTEXT=8192` in this
checkout's `.env`). Docs, embeddings, and chat stay on this machine — see
`docs/SECURITY.md`.

## Architecture

- `docker-compose.yml` runs three services: `rag-api` (FastAPI app, serves the
  page and `/query`), `indexer` (same image, background ingestion worker),
  and `chromadb` (vector store, not published on the host).
- The library lives at the host path in `LIBRARY_PATH` (this checkout:
  `/Users/comzis/TalkbackDemo`), mounted read-only into both containers at
  `/app/data`.
- Ollama runs on the host (not in Docker) at `host.docker.internal:11434` so
  it can use the Mac GPU.
- On this Mac, embedding and reranking run in a separate host process
  (`scripts/rerank_host.py`, launchd service `com.talkback.rerank-host`,
  `127.0.0.1:11435`, Apple MPS) instead of inside the container — set via
  `RERANK_URL` / `EMBED_URL` in `.env`. If that host process is down, queries
  return a `search_unavailable` notice rather than silently falling back to
  CPU in-container (see commit `9dc55b6`). On a Linux GPU server those URLs
  are left unset and the container runs embed/rerank in-process on CUDA.
- Key app modules: `app/main.py` (HTTP API), `app/engine.py` (Chroma,
  ingestion, retrieval, answers), `app/prompts.py` (when to search, citation
  rules), `app/library.py` (file add/replace/remove), `app/config.py`
  (settings).

## Working rules

- **One agent at a time** on this repo and stack. Do not run overlapping
  agents against the same containers/branch.
- **Every change goes on a branch with a PR and CI.** Do not commit directly
  to `master`.
- **Do not merge unless the user explicitly says to.** Opening the PR and
  waiting for review is the default end state of a task.
- **Measure before and after any behavior change** using the live eval
  (`scripts/run_live_eval.py`, model `qwen3.8:27b`) — not just unit tests.
  Report evidence (actual eval output / numbers), not just a claim that it
  works.
- Never tune against `tests/eval/heldout.json` — it's report-only. Only
  `tests/eval/questions.json` (the main set) is for tuning. If held-out
  numbers move, note it, don't chase it.

## Tests

**Unit tests** (fast, no model/Chroma load; two tests skip unless LlamaIndex
and the local embedding cache are present):

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

**In-container tests** (runs the skipped LlamaIndex-dependent tests, using the
API image's installed deps; can run while the live API container stays up):

```bash
scripts/test_in_container.sh
```

**Frontend tests:**

```bash
node --test app/tests/test_stream_events.mjs
```

**Lint/format** (must pass, matches CI):

```bash
ruff check app scripts
ruff format --check app scripts
```

**Live eval** (requires the full stack up and reachable at `--base-url`,
default `http://127.0.0.1:8001`; this is the behavior-change gate):

```bash
python scripts/run_live_eval.py --runs 3
```

Add `--cases tests/eval/heldout.json` to see held-out results for reporting
only — never adjust retrieval/prompts to chase a held-out number.

CI (`.github/workflows/ci.yml`) runs ruff lint/format, unit tests, and the
frontend test on every push/PR — it does not run the live eval (no model or
stack in CI).

## Day-to-day commands

```bash
docker compose up -d --build rag-api   # after a Python/UI change
docker compose logs -f rag-api
docker compose ps
```
