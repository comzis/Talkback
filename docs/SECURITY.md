# Security

Talkback is an on-prem proof of concept. Documents, embeddings, and answers stay on the machine that runs it.

## What runs where

| Piece | Where it runs | What it sees |
| --- | --- | --- |
| Browser UI | Your machine, page served by the API | The question you type and the answer that comes back |
| Talkback API | Docker container `rag_api_service` | Library files, chunks, and the prompt sent to Ollama |
| Indexer | Docker container `rag_indexer_service`, same image as the API | Library files and the chunks it writes. It does not serve the page |
| Embeddings | Inside the indexer while it writes the library, and inside the API for the question vector. Both load the model from the local Hugging Face cache | Document text, and the question text |
| File status | SQLite file `./status/library.sqlite`, mounted at `/app/status` for the API and the indexer | File names, index state, and the ingest queue. Not published on a port |
| ChromaDB | Docker container `chromadb_service` | Chunk text and vectors |
| Ollama | Host process, not a container | The prompt for each answer. It stays on the host so it can use that machine's GPU |

There is no LangSmith client and no telemetry endpoint.

## Ports

| Port | Process | Who should reach it |
| --- | --- | --- |
| 127.0.0.1:8001 | Talkback API. The container still listens on 8001; Docker publishes that port on loopback only | This machine |
| Chroma 8000 | ChromaDB, not published. The API and the indexer use `chromadb:8000` on the Docker network | Those two containers. For host debugging, publish `127.0.0.1:8002:8000` and do not use `8002:8000` |
| none | `./status` is a volume mount, not a port. The indexer writes a heartbeat under `/tmp` inside its own container for its healthcheck | The API and the indexer |
| 11434 | Host Ollama | The API container, via `host.docker.internal` |

## Outbound network

`OFFLINE_MODE` defaults to `true`.

While it is true:

- `app/entrypoint.sh` exports `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and `HF_DATASETS_OFFLINE=1` before Python starts. Hugging Face reads those names when its library is imported, so setting them later does not stop the calls. The embedding model then loads only from `./hf_cache`.
- `POST /llm/pull` is refused. The Add Model button is hidden.

The only outbound calls are one-off model downloads during setup, and only when you set `OFFLINE_MODE=false` and restart:

- `ollama pull <model>` on the host
- the first embedding-model download, if `./hf_cache` does not already contain it

After those files are on disk, set `OFFLINE_MODE=true` again. With the network disconnected and the models cached, the API can answer and the indexer can update the local library. Both containers run the same entrypoint, so both export the Hugging Face offline flags before Python starts. The status database stays in `./status` on the host. It is not a network service.

## Demo check

```bash
# models and ./hf_cache already present, OFFLINE_MODE unset or true
docker compose up -d
curl -s http://localhost:8001/system/status
curl -s -X POST http://localhost:8001/llm/pull -H 'Content-Type: application/json' -d '{"model":"example"}'
# expect HTTP 403
curl -s -X POST http://localhost:8001/query -H 'Content-Type: application/json' -d '{"query":"hello"}'
```
