# Talkback API memory

Measured on the consolidated main-checkout stack (Docker Desktop, Mac host
embed/rerank on MPS), 28 Oct 2026.

## Steady state

| Condition | `rag_api_service` RSS |
|---|---|
| Host embed/rerank up, after one BBC smoke query | ~1.1 GiB |
| Host stopped (SearchUnavailable path, no local model load) | ~1.2 GiB |

The in-container HuggingFace embedder and transformers reranker load **lazily
and once** (`HostOrLocalEmbedding._ensure_local`, `retrieval.rerank._load`).
They are not loaded when the host is healthy. When the host is down and the
offline cache cannot satisfy a load, Talkback returns the
`search_unavailable` notice instead of loading forever or answering as if the
library had been searched.

## Growth during a live eval

With the host up, `compare_talkback_models.py --runs 1` (main + held-out) was
sampled every 30s via `docker stats` for ~30 minutes (60 samples):

| Sample | Approx. wall time | `rag_api_service` RSS |
|---|---|---|
| 1 | start | 1.26 GiB |
| 15 | ~7 min | ~2.5 GiB |
| 30 | ~15 min | ~3.5 GiB |
| 45 | ~22 min | ~4.3 GiB |
| 60 | ~30 min | 5.24 GiB |
| end (after tok/s sample) | ~34 min | 5.32 GiB |

Earlier long ×3 parity runs on the same path reached ~8 GiB. That growth is
**not** the in-container fallback models (host stayed up for the whole run).
It tracks session length: Chroma/LlamaIndex retrieval state and Python heap
retained across requests inside one uvicorn worker. Restarting the API
container resets RSS to the steady-state band above.

## Host process

`scripts/rerank_host.py` holds the MPS embedder and reranker. Expect roughly
the size of bge-m3 + bge-reranker-v2-m3 on the host (order of several GiB
combined while both are loaded). It is managed by launchd
`com.talkback.rerank-host` with KeepAlive; restarts are logged in
`logs/rerank-host-restarts.log`.

## Practical guidance

- Keep `EMBED_URL` / `RERANK_URL` pointed at the host service for normal use.
- Budget ~2 GiB for a warm API with host helpers, and expect several GiB more
  during a long eval without a container restart.
- Do not rely on the in-container fallback for production traffic; it is a
  safety net and may refuse with `search_unavailable` when offline weights
  are missing.
