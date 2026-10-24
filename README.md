# Talkback

A local RAG app for chatting with a private document library. Talkback answers like an assistant. When a question is about a file in the library, or a passage is pasted in, the reply stays on the retrieved excerpts and cites the file and page.

Repository: https://github.com/comzis/Talkback

The chat window is the main view. The library, system status, and upload area sit in the side column.

## What it does

- Keeps documents, embeddings, and chat on this machine. Ollama runs on the host. ChromaDB stores the vectors.
- Adds a file in one step. Drop a file on the library panel, or click the drop area and choose one. Talkback saves it and starts indexing. Uploading the same name replaces that file only.
- Leaves files that have not changed in the index. New and changed files are embedded. Removed files drop their chunks.
- Answers greetings and general questions with no sources. A question that names a library file is answered from that file. Each cited claim keeps its source number, with the page and excerpt beside it.
- Uses `gemma2:2b` through Ollama by default, and `BAAI/bge-small-en-v1.5` for embeddings. The embedding model downloads once, on first start.

LangSmith monitoring is off unless you turn it on. When it is enabled, traces leave the machine.

## Quick start

### Prerequisites

- Docker Desktop
- [Ollama](https://ollama.com/) running on the host
- About 8 GB of RAM and several GB of free disk for the image and model

### 1. Clone and configure

```bash
git clone https://github.com/comzis/Talkback.git
cd Talkback

cat > .env << EOF
OLLAMA_MODEL=gemma2:2b
OLLAMA_BASE_URL=http://host.docker.internal:11434
CHROMA_HOST=chromadb
CHROMA_PORT=8000
EOF
```

`CHROMA_PORT=8000` is the port inside the Docker network. From the host, Chroma is published on port **8002**, because 8000 is often already taken.

### 2. Pull the model and start the stack

```bash
ollama pull gemma2:2b
docker compose up --build -d
docker compose ps
```

The API image is large because it includes a CPU build of PyTorch. The first start also downloads the embedding model into `./hf_cache`.

### 3. Open Talkback

http://localhost:8001

Drop a file into the library panel. Indexing starts on its own. Then ask in the chat.

There is no login. The API listens on all interfaces inside the container and is published on port 8001.

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
| `OLLAMA_MODEL` | Model name in host Ollama | `gemma2:2b` |
| `OLLAMA_BASE_URL` | Ollama address as seen from the API container | `http://host.docker.internal:11434` |
| `CHROMA_HOST` | Chroma service name on the Docker network | `chromadb` |
| `CHROMA_PORT` | Chroma port on the Docker network | `8000` |
| `LANGCHAIN_MONITORING` | Send traces to LangSmith | off |
| `LANGCHAIN_PROJECT` | LangSmith project name | `Talkback` |

Change the model from the **Change Model** button in System Pulse, or set `OLLAMA_MODEL` and run `docker compose restart rag-api`. Pull any new model on the host first:

```bash
ollama pull llama3
```

`gemma2:2b` is the fast default. A larger local model holds a longer, more careful answer more steadily.

If files in `./data` are not writable inside the container, rebuild the API with your user id:

```bash
docker compose build --build-arg UID="$(id -u)" --build-arg GID="$(id -g)" rag-api
docker compose up -d
```

The compose file currently builds as UID `502` and GID `20`.

## Layout

```
Talkback/
├── app/
│   ├── main.py           # HTTP API and the Talkback page
│   ├── engine.py         # Chroma, ingestion, retrieval, answers
│   ├── prompts.py        # When to search, and how a citation is kept
│   ├── library.py        # Which files to add, replace, or leave indexed
│   ├── files.py          # Safe filenames and the library listing
│   ├── monitoring.py     # Optional LangSmith traces
│   ├── static/           # Chat UI
│   ├── tests/            # Library plan, prompts, and citation checks
│   ├── requirements.txt
│   └── Dockerfile
├── data/                 # Library files (gitignored)
├── chroma_data/          # Vector store (gitignored)
├── hf_cache/             # Embedding model cache (gitignored)
├── docker-compose.yml
└── .env                  # Local config (gitignored)
```

Static files and Python are copied into the API image. After a UI or Python change:

```bash
docker compose up -d --build rag-api
```

Run the unit tests from `app/`. They do not load the model or Chroma.

```bash
cd app && python3 -m unittest tests.test_library
```

## API

- `GET /` serves the Talkback page
- `POST /upload` saves files and starts indexing
- `POST /ingest` indexes files already on disk
- `GET /ingest/status` reports indexing progress
- `GET /files` lists the library
- `DELETE /files/{filename}` deletes one file and its chunks
- `POST /query` answers one question. The body is `{"query": "..."}`. The response is `{"response": "...", "sources": [...]}`
- `GET /health` is the API health check
- `GET /llm/models`, `POST /llm/select`, and `POST /llm/pull` manage Ollama models

`POST /query` has no conversation memory. Each question is answered on its own.

## Troubleshooting

**The model is missing.** Pull it on the host, not in a container:

```bash
ollama pull gemma2:2b
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

## Privacy

Documents, chunks, and chat requests stay on this machine and go to the local Ollama process. Embeddings are computed in the API container.

Turning on LangSmith monitoring sends query and indexing traces to LangSmith. Leave it off for a fully local demo.

## License

Private use. All rights reserved.
