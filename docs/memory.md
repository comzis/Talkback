# Talkback API memory

Measured on the consolidated main-checkout stack (Docker Desktop, Mac host
embed/rerank on MPS).

## Steady state

| Condition | `rag_api_service` RSS |
|---|---|
| Host embed/rerank up, after one BBC smoke query | ~0.5–1.1 GiB |
| Host stopped (SearchUnavailable; no local model load) | ~same band |

When `EMBED_URL` / `RERANK_URL` point at the host service, Talkback does **not**
load HuggingFace embed or transformers rerank weights inside the API container.
If the host is down, queries return the `search_unavailable` notice.

## Growth during a live eval (before fix)

With the host up, `compare_talkback_models.py --runs 1` was sampled every 30s
for ~30 minutes. RSS climbed from ~1.3 GiB to ~5.3 GiB. A later 20-query probe
grew ~70 MiB per question.

**Cause:** every library query called `indexed_documents()`, which pulled all
~12k chunk metadatas from Chroma (~33 MiB pickle size) and classified them.
Those short-lived allocations drove worker RSS up for the life of the process.
BM25 and the LlamaIndex `VectorStoreIndex` were already cached once; the
in-container embed/rerank models were not loaded (host stayed up).

**Fix:** cache the classified library-path maps in process state and refresh
when the collection count changes or after ingest/delete. Soak test:
`scripts/soak_api_memory.py` (200 questions; RSS at start, every 50, and end).

After the fix, `scripts/soak_api_memory.py --count 200` stayed flat:

| Sample | `rag_api_service` RSS |
|---|---|
| start (warm BM25 + library cache) | 510.8 MiB |
| after 50 | 513.6 MiB |
| after 100 | 513.8 MiB |
| after 150 | 513.5 MiB |
| after 200 | 513.2 MiB |

Fixed caches: BM25 11834 docs, library index 14 files, docstore 0, no
in-container embed/rerank weights.

## Host process

`scripts/rerank_host.py` holds the MPS embedder and reranker. Expect roughly
the size of bge-m3 + bge-reranker-v2-m3 on the host (order of several GiB
combined while both are loaded). It is managed by launchd
`com.talkback.rerank-host` with KeepAlive; restarts are logged in
`logs/rerank-host-restarts.log`.

## Deploy notes

- **Mac (this stack):** keep `EMBED_URL` / `RERANK_URL` on the host MPS
  service. That service is required for library search.
- **Linux GPU server:** leave those URLs empty so the container loads embed and
  rerank on the machine GPU (in-process path).
- There is no in-container CPU fallback when a host URL is configured: the
  offline weight mount was incomplete, loads failed in seconds, and a working
  CPU load would add several GiB to the API worker.
