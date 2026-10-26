# Talkback

A local RAG app for chatting with a private document library. Talkback answers like an assistant. When a question is about a file in the library, or a passage is pasted in, the reply stays on the retrieved excerpts and cites the file and page.

Repository: https://github.com/comzis/Talkback

The chat window is the main view. The library, system status, and upload area sit in the side column.

## What it does

- Keeps documents, embeddings, and chat on this machine. Ollama runs on the host. ChromaDB stores the vectors.
- Adds a file in one step. Drop a file on the library panel, or click the drop area and choose one. Talkback saves it and starts indexing. Uploading the same name replaces that file only.
- Leaves files that have not changed in the index. New and changed files are embedded. Removed files drop their chunks.
- Answers greetings and general questions with no sources. A question that names a library file is answered from that file. Each cited claim keeps its source number, with the page and excerpt beside it.
- Uses the model named by `OLLAMA_MODEL` in `.env`. There is no built-in chat-model name. Embeddings default to `BAAI/bge-m3` (MIT, French, English, and Spanish). `intfloat/multilingual-e5-small` remains available by setting `EMBED_MODEL`. The embedding model downloads once, and only when `OFFLINE_MODE=false`.
- Reranks the top 20 chunks with `BAAI/bge-reranker-v2-m3` (Apache-2.0, local cache) and keeps four. Each query-passage pair is capped at 512 tokens. On a GPU server the reranker should run on the GPU. On this Mac, in Docker, six main-set questions reached the first word in about 28 seconds at 15 or 20 candidates and about 44 seconds at 30. Main-set recall at 4 and at 8 stayed 14/15 for all three. The reranker score is logged and does not choose the path. The model always sees the top passages. A citation is kept when its filters, dotted fields, numbers with units, standard codes, and file names sit in a retrieved passage; a token found in a different passage is re-attributed there. Words in parentheses are not checked. If no citation survives, the reply is marked as not from the documents.
- Streams the reply into the chat, then shows the folder, file, and page for each source the answer used. The **Stop** button cancels the stream. `POST /query` still returns the full answer in one response.

## Quick start

Talkback needs Docker, Ollama on the host, about 8 GB of RAM, and several GB of free disk for the image and model. The same compose file runs on a Mac and on a Linux server. `host.docker.internal` is mapped to the host gateway, so the container reaches Ollama on either machine.

### Mac

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and [Ollama](https://ollama.com/). The image builds as UID `502` and GID `20` unless you override them. If the library files are not readable in the container, rebuild with your ids:

```bash
docker compose build --build-arg UID="$(id -u)" --build-arg GID="$(id -g)"
docker compose up -d
```

### Linux server

Install Docker Engine and the Docker Compose plugin, and install Ollama on the host so it can use the machine's GPU. Build as the user that owns the library folder. The Mac default of UID `502` will not match a typical server account.

```bash
docker compose build --build-arg UID="$(id -u)" --build-arg GID="$(id -g)"
docker compose up -d
```

Keep port 8001 bound to `127.0.0.1`. Put a reverse proxy in front of it if other machines need the page. Do not publish Chroma.

### Configure and start

```bash
git clone https://github.com/comzis/Talkback.git
cd Talkback
cp .env.example .env
```

Set `OLLAMA_MODEL` in `.env` to a model you have pulled on the host. Pilot models must be Apache 2.0 or MIT licensed. Check the license on the model card before you choose one. Talkback does not ship a default model name. Set `LIBRARY_PATH` to the absolute path of the document folder. Compose mounts that folder at `/app/data` for the API and the indexer, and refuses to start when it is missing.

`CHROMA_PORT=8000` is the port inside the Docker network. Chroma is not published on the host. The database files are in `./chroma_data`. The file-status database is in `./status`. The API is published on `127.0.0.1:8001` only.

```bash
ollama pull "$OLLAMA_MODEL"
docker compose up --build -d
docker compose ps
```

`ollama pull` reads the name from your shell. If the variable is only in `.env`, pass the same name explicitly.

The API image is large because it includes a CPU build of PyTorch. With `OFFLINE_MODE=true` (the default) the container exports the Hugging Face offline flags before Python starts, and the embedding model loads only from `./hf_cache`. Download it once with `OFFLINE_MODE=false`, then turn offline mode back on. See the demo checklist.

Open http://localhost:8001

Drop a file into the library panel, or put files in `LIBRARY_PATH` and let the indexer pick them up. Then ask in the chat.

There is no login. The API listens on all interfaces inside the container and is published only on `127.0.0.1:8001`, so other devices on the network cannot open it.

## Asking questions

| You ask | Talkback does |
| --- | --- |
| `hello`, or a short general question such as `What is 2 + 2?` | Replies as an assistant and attaches no documents |
| A question that names a library file, such as `What does the campaign say about privacy?` | Searches that file and cites the page |
| A pasted passage | Explains the passage and cites the library where an excerpt supports the explanation |
| A document question the excerpts do not support | Says the library does not cover it, and does not invent a citation |

Document answers use a low temperature so the reply stays close to the excerpt. The source number in the sentence matches the number in the source list.

## Supported files

Documents and text: PDF, Word, OpenDocument, TXT, Markdown, RST, RTF, EPUB.

Presentations and tables: PowerPoint, Excel, CSV.

Data and code: JSON, XML, HTML, and common source files such as Python, JavaScript, TypeScript, Java, C/C++, Go, and Rust.

Images can be uploaded. Text is taken from files the reader can parse. A scanned PDF with no text layer will not add searchable chunks.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `OLLAMA_MODEL` | Model name in host Ollama. Required. No built-in fallback | set in `.env` |
| `OLLAMA_BASE_URL` | Ollama address as seen from the API container | `http://host.docker.internal:11434` |
| `CHAT_BACKEND` | `ollama` or `vllm`. `vllm` disables `/llm/models`, `/llm/select`, and `/llm/pull` | `ollama` |
| `CHAT_BASE_URL` | OpenAI-compatible origin when it is not `OLLAMA_BASE_URL` | `OLLAMA_BASE_URL` |
| `EMBED_MODEL` | Local embedding model. `intfloat/multilingual-e5-small` is the smaller option | `BAAI/bge-m3` |
| `EMBED_BATCH` | Chunks per embedding batch. Progress updates after each batch | `16` |
| `CHUNK_SIZE` | Chunk size in tokens | `512` |
| `CHUNK_OVERLAP` | Overlap between chunks | `64` |
| `RETRIEVE_CANDIDATES` | Chunks retrieved before the reranker, unless `RERANK_CANDIDATES` is higher | `8` |
| `RERANK_MODEL` | Local cross-encoder. Apache-2.0 | `BAAI/bge-reranker-v2-m3` |
| `RERANK_CANDIDATES` | Chunks scored by the reranker | `20` |
| `RERANK_MAX_LENGTH` | Token cap for each query-passage pair. Use the GPU on a GPU server | `512` |
| `RERANK_THRESHOLD` | Logged only. It does not choose the path | `-7.5` |
| `RERANK` | Set to `false` to use the similarity threshold instead | `true` |
| `RETRIEVE_LIMIT` | Chunks kept for the answer | `4` |
| `RETRIEVE_PER_FILE` | Maximum chunks from one file, once the hits span more files than `RETRIEVE_BALANCE_FILES` | `2` |
| `RETRIEVE_BALANCE_FILES` | Per-file cap applies only above this many files. Three PDFs do not trigger it | `3` |
| `RELEVANCE_THRESHOLD` | Best e5 score required before a library answer | `0.75` |
| `OLLAMA_CONTEXT` | Ollama context window (`num_ctx`) | `4096` |
| `OLLAMA_KEEP_ALIVE` | How long Ollama keeps the model loaded | `30m` |
| `OLLAMA_THINK` | Send a hidden reasoning trace before the reply | `false` |
| `TORCH_THREADS` | Torch CPU threads | half the cores |
| `OFFLINE_MODE` | Load embeddings from the local cache and refuse `/llm/pull` | `true` |
| `LIBRARY_PATH` | Host folder mounted at `/app/data` for the API and the indexer. Required | set in `.env` |
| `LIBRARY_READ_ONLY` | Treat the data directory as a read-only mount | `false` |
| `REINDEX_INTERVAL_MINUTES` | Repeat incremental indexing. Unset or `0` keeps it off | off |
| `CHROMA_HOST` | Chroma service name on the Docker network | `chromadb` |
| `CHROMA_PORT` | Chroma port on the Docker network | `8000` |

Pilot models must be Apache 2.0 or MIT licensed. Check the model card before you set `OLLAMA_MODEL`.

Chat uses `POST /v1/chat/completions`. With `CHAT_BACKEND=ollama` the request includes `keep_alive` and, when `OLLAMA_THINK=false`, `reasoning_effort` set to `none`. With `CHAT_BACKEND=vllm` those Ollama fields are left out, and the model list, model switch, and model pull endpoints are disabled. The vLLM path is not tested against a real vLLM server. Library answers stream as the model writes them. If a check against the excerpts changes the wording, the correction is a footnote and the words already shown stay.

Change the model from the **Change Model** button in System Pulse, or set `OLLAMA_MODEL` and run `docker compose restart rag-api`. Pull any new model on the host first with `ollama pull`, using the name from the model card.

If files in `./data` are not writable inside the container, rebuild the API with your user id:

```bash
docker compose build --build-arg UID="$(id -u)" --build-arg GID="$(id -g)" rag-api
docker compose up -d
```

On a Mac the compose file builds as UID `502` and GID `20` unless you pass other ids. On a Linux server, pass `UID` and `GID` from `id -u` and `id -g`, as in the Linux quick start.

## Layout

```
Talkback/
├── app/
│   ├── main.py           # HTTP API and the Talkback page
│   ├── engine.py         # Chroma, ingestion, retrieval, answers
│   ├── prompts.py        # When to search, and how a citation is kept
│   ├── library.py        # Which files to add, replace, or leave indexed
│   ├── files.py          # Safe filenames and the library listing
│   ├── config.py         # Model, embedding, and timeout settings
│   ├── static/           # Chat UI
│   ├── tests/            # Library plan, prompts, and citation checks
│   ├── requirements.txt
│   └── Dockerfile
├── data/                 # Library files (gitignored)
├── chroma_data/          # Vector store (gitignored)
├── hf_cache/             # Embedding model cache (gitignored)
├── docker-compose.yml
├── .env.example          # Copy to .env and set OLLAMA_MODEL
├── docs/SECURITY.md      # What runs where, and what may leave the machine
└── .env                  # Local config (gitignored)
```

Static files and Python are copied into the API image. After a UI or Python change:

```bash
docker compose up -d --build rag-api
```

Run the unit tests from the repository root. They do not load the model or Chroma. Two tests stay skipped unless LlamaIndex and the local embedding cache are already installed.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

The API image has LlamaIndex, so the skipped tests can run there. `scripts/test_in_container.sh` starts a one-off container from that image and mounts the tests in. The running API can stay up.

## API

- `GET /` serves the Talkback page
- `POST /upload` saves files and starts indexing
- `POST /ingest` indexes files already on disk
- `GET /ingest/status` reports indexing progress
- `GET /files` lists the library
- `DELETE /files/{filename}` deletes one file and its chunks
- `POST /query` answers one question. The body is `{"query": "..."}`. The response is `{"response": "...", "sources": [...]}`
- `POST /query/stream` sends the same answer as server-sent events: `token`, then `sources` (or `replace` when the reply is not grounded), then `done`
- `GET /health` is the API health check
- `GET /llm/models` and `POST /llm/select` manage host Ollama models. `POST /llm/pull` is refused while `OFFLINE_MODE=true`

`POST /query` has no conversation memory. Each question is answered on its own.

## Troubleshooting

**The model is missing.** Pull it on the host, not in a container:

```bash
ollama pull <model-from-the-model-card>
ollama list
```

**The page is up but answers fail.** Confirm Ollama is reachable from the container:

```bash
docker exec rag_api_service python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/tags', timeout=5).status)"
```

**Containers are not healthy.** The API waits for Chroma, then loads the embedding model. Give the first start a few minutes, then:

```bash
docker compose ps
docker compose logs -f rag-api
```

**A file uploaded and nothing is searchable.** Indexing runs in the background after the upload. Watch Ingestion and Embeddings in System Pulse. If the status stays on an error, read `docker compose logs rag-api`.

Windows: see TODO.

## Demo checklist

Use this for the on-prem proof of concept. The promise is that no library text or chat leaves the machine.

1. Pick a pilot model whose model card says Apache 2.0 or MIT. Pull it on the host with `ollama pull`, and set that name as `OLLAMA_MODEL` in `.env`.
2. Set `OFFLINE_MODE=false`, start the stack, and wait until the embedding model is cached in `./hf_cache`. Set `OFFLINE_MODE=true` and run `docker compose up -d --build rag-api`.
3. `docker-compose.yml` mounts `./data`, so **Drop a file** adds documents and delete stays available. Ollama stays on the Mac (Metal). The API and Chroma stay in Docker Desktop.
4. Startup indexes files that are missing or unfinished. If the library list is still empty, open Talkback, click **Re-index**, then **Re-index changed files**. You can also run `curl -X POST http://127.0.0.1:8001/ingest`.
5. Disconnect the network.
6. Open http://127.0.0.1:8001 and ask a question about one of the files. Tokens should appear as they are generated, then the folder, file, and page. `curl -X POST http://127.0.0.1:8001/llm/pull -H 'Content-Type: application/json' -d '{"model":"test"}'` returns 403.

Setup for this branch is `README.md` and `docs/SECURITY.md`. Older notes were removed from `docs/archive/`; git history still has them.

`docs/SECURITY.md` lists the processes and ports.

## Privacy

Documents, chunks, and chat requests stay on this machine and go to the host Ollama process. Embeddings are computed in the API container. There is no LangSmith client and no telemetry endpoint. The only outbound calls are one-off model downloads during setup, and only when `OFFLINE_MODE=false`.

## License

Private use. All rights reserved.
