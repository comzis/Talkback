# Security

Talkback is an on-prem proof of concept. Documents, embeddings, and answers stay on the machine that runs it.

## What runs where

| Piece | Where it runs | What it sees |
| --- | --- | --- |
| Browser UI | Your machine, page served by the API | The question you type and the answer that comes back |
| Talkback API | Docker container `rag_api_service` | Library files, chunks, and the prompt sent to Ollama |
| Embeddings | Inside the API container, from the local Hugging Face cache | Document text while indexing |
| ChromaDB | Docker container `chromadb_service` | Chunk text and vectors |
| Ollama | Host process, not a container | The prompt for each answer. This keeps Apple Silicon GPU access. |

There is no LangSmith client and no telemetry endpoint.

## Ports

| Port | Process | Who should reach it |
| --- | --- | --- |
| 127.0.0.1:8001 | Talkback API. The container still listens on 8001; Docker publishes that port on loopback only | This machine |
| Chroma 8000 | ChromaDB, not published. The API uses `chromadb:8000` on the Docker network | The API container. For host debugging, publish `127.0.0.1:8002:8000` and do not use `8002:8000` |
| 11434 | Host Ollama | The API container, via `host.docker.internal` |

## Outbound network

`OFFLINE_MODE` defaults to `true`.

While it is true:

- `app/entrypoint.sh` exports `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and `HF_DATASETS_OFFLINE=1` before Python starts. Hugging Face reads those names when its library is imported, so setting them later does not stop the calls. The embedding model then loads only from `./hf_cache`.
- `POST /llm/pull` is refused. The Add Model button is hidden.

The only outbound calls are one-off model downloads during setup, and only when you set `OFFLINE_MODE=false` and restart:

- `ollama pull <model>` on the host
- the first embedding-model download, if `./hf_cache` does not already contain it

After those files are on disk, set `OFFLINE_MODE=true` again. With the network disconnected and the models cached, the API can start, index the local library, and answer.

## Demo check

```bash
# models and ./hf_cache already present, OFFLINE_MODE unset or true
docker compose up -d
curl -s http://localhost:8001/system/status
curl -s -X POST http://localhost:8001/llm/pull -H 'Content-Type: application/json' -d '{"model":"example"}'
# expect HTTP 403
curl -s -X POST http://localhost:8001/query -H 'Content-Type: application/json' -d '{"query":"hello"}'
```
