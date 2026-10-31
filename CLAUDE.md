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
  CPU in-container — the offline image doesn't carry CPU weights for a
  working fallback. On a Linux GPU server, `RERANK_URL`/`EMBED_URL` are left
  unset and the container runs embed/rerank in-process on CUDA; see
  [docs/server-setup.md](docs/server-setup.md) for that path (tested with
  mock models only so far).
- Key app modules (under `app/`):
  - `main.py` — process entry point; just re-exports the FastAPI app.
  - `api/app.py` — builds the FastAPI app, mounts static files, wires routers.
  - `api/deps.py` — helpers shared by routers.
  - `api/schemas.py` — request/response models.
  - `api/routers/query.py` — `POST /query` and `/query/stream`.
  - `api/routers/ingest.py` — ingestion endpoints (indexer process embeds).
  - `api/routers/library.py` — list/upload/delete and file-type stats.
  - `api/routers/llm.py` — model list/select/pull/status.
  - `api/routers/system.py` — health, system status/resources, chat page.
  - `engine.py` — Chroma, embeddings, ingestion, grounded answers.
  - `state.py` — the one process-wide state object; routes and jobs share it.
  - `config.py` — model, embedding, and timeout settings.
  - `llm/client.py` — chat client (Ollama/vLLM).
  - `llm/templates.py` — prompt templates for citation/assistant/explanation replies.
  - `llm/prompts.py` — re-exports the public prompt-text API from the modules below.
  - `llm/language.py` — notices, question-language detection, general-knowledge labelling.
  - `llm/followups.py` — conversation history, continuation cues, library routing.
  - `llm/citations.py` — finalizing citation markers, token support checks, similarity pruning.
  - `llm/excerpts.py` — excerpt display, PDF spacing repair, grounding checks.
  - `retrieval/search.py` — searches the library, balances matches across files.
  - `retrieval/bm25.py` — in-memory BM25 over the Chroma collection (hybrid retrieval).
  - `retrieval/rerank.py` — cross-encoder rerank (local model, loads on first use).
  - `retrieval/recall.py` — locates which retrieved page holds a fact (no chat model).
  - `store/chroma.py` — Chroma collection, cached index, chunk deletes.
  - `store/embeddings.py` — embedding-model identity and e5 prefixes.
  - `store/host_embed.py` — optional host embedder client (empty `EMBED_URL` keeps in-process).
  - `store/status_db.py` — SQLite file-status table (what's indexed/pending).
  - `store/search_errors.py` — shared error types for when search can't run safely.
  - `ingestion/pipeline.py` — incremental ingest, status payload, re-index timer.
  - `ingestion/plan.py` — decides which library files to add/update/leave indexed.
  - `ingestion/progress.py` — pure progress math for ingestion.
  - `ingestion/worker.py` — runs the indexer in its own process (`docker compose` `indexer` service).
  - `sources/base.py` — the interface every library source must implement.
  - `sources/filesystem.py` — the mounted folder as a source (paths, hidden files, read-only).
  - `static/` — chat UI (`index.html`, `script.js`, `style.css`, `stream_events.js`).

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

## Guardrails

- Do not read or copy files under `data/`, `chroma_data/`, `hf_cache/`,
  `tests/eval/local/`, or `.env`. They hold library documents and local config.
- Do not edit `tests/eval/heldout.json` or `tests/eval/heldout.sha256`.
- Do not write expected answers for eval rows. Engineers write them from the
  documents (`docs/eval-authoring.md`).
- Do not add outbound network calls or telemetry. `OFFLINE_MODE` must keep
  blocking them. Ports stay on `127.0.0.1`.
- The app takes its chat model only from `OLLAMA_MODEL`. Do not add a fallback
  or default model name under `app/`. Pilot models must be Apache 2.0 or MIT.

## How work flows

1. `/grill-with-docs`: align on the change, one round of questions at a time,
   until the design is settled. Terms go into `GLOSSARY.md`, hard-to-reverse
   decisions into `docs/adr/`.
2. `/to-spec`: the agreed design becomes a GitHub issue. Specs are not kept as
   files in the repo.
3. `/to-tickets`: the spec becomes vertical-slice issues with blocking edges,
   each labelled `ready-for-agent` or `ready-for-human`.
4. `/implement <N>`: one ticket per fresh session. It branches, works test
   first (`tdd`), reviews its own diff in fresh sub-agents (`code-review`),
   and opens a PR. It never merges. A person reads the diff before merging;
   for a risky change, run `code-review` again from a new session.
5. QA by hand: run the stack, ask real questions, and file what you find as
   new issues.

Use `/grill-me` instead of step 1 for a question that is not about the code.
A small fix with no design question (a doc correction, a one-line bug) can
skip steps 1 to 3, but still gets an issue and a PR.

## Agent skills

### Issue tracker

GitHub Issues on `comzis/Talkback`, through the `gh` CLI. See
`docs/agents/issue-tracker.md`.

### Triage labels

Default five labels; `ready-for-agent` means AFK, `ready-for-human` means a
person must do or check it. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root, created when
first needed. See `docs/agents/domain.md`.
