# Linux GPU server setup

This is the second of Talkback's two deployment paths. The Mac path (see the
main [README](../README.md#mac) and [docs/SECURITY.md](SECURITY.md)) runs
embedding and reranking in a host process because Docker Desktop on a Mac
cannot see the Apple GPU. A Linux server with an NVIDIA GPU does not need
that: Docker on Linux can see the GPU directly, so the API and indexer
containers load the models themselves.

**Status: tested with mock models only.** The wiring in this document is
exercised by the unit suite using LlamaIndex's `MockEmbedding` and `MockLLM`
(see `app/tests/test_smoke.py`), not against a real CUDA GPU with
`BAAI/bge-m3` and `BAAI/bge-reranker-v2-m3` loaded. Treat the steps below as
the intended path, and confirm the first run against a real GPU server
before relying on it for a pilot.

## 1. Leave `RERANK_URL` and `EMBED_URL` unset

On the Mac path, these point at the host MPS service
(`scripts/rerank_host.py`, `127.0.0.1:11435`) and PR #26 made a down host
there a hard failure (`search_unavailable`) rather than a silent CPU
fallback, because the image carries no CPU-ready offline weights for that
fallback to use.

On a Linux GPU server, don't start that host service at all. Leave
`RERANK_URL` and `EMBED_URL` empty in `.env`. With both unset:

- `app/store/host_embed.py` keeps the embedding model in-process.
- `app/retrieval/rerank.py` keeps the reranker in-process. Its device
  selection (`_device()`) picks CUDA when `torch.cuda.is_available()`, else
  CPU — there is no MPS branch in that module; MPS only exists in the
  separate host script used on a Mac.

So the container, not a host process, loads both models and should use the
GPU automatically once the steps below are done.

## 2. Build the API image with a CUDA torch wheel

`app/Dockerfile` installs the **CPU** wheel of torch first, on purpose, so a
later `pip install` from `requirements.txt` cannot silently replace it with
a CUDA build:

```dockerfile
# CPU wheel first. A later install must not replace it with the CUDA build.
RUN pip install --no-cache-dir torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt \
    ...
```

CI builds and tests only this CPU image (`.github/workflows/ci.yml` installs
the same CPU wheel) — there is no CI coverage for a CUDA build. For a GPU
server, build a separate image with a CUDA wheel instead, matching the
server's installed CUDA/driver version, e.g.:

```dockerfile
RUN pip install --no-cache-dir torch==2.14.1 --index-url https://download.pytorch.org/whl/cu121 \
    && pip install --no-cache-dir -r requirements.txt
```

Drop the `banned = [...]; assert not banned` check in that `RUN` line too —
it exists specifically to keep NVIDIA CUDA wheels out of the CPU image, and
a CUDA build is expected to pull them in.

The host also needs the NVIDIA Container Toolkit installed so Docker can see
the GPU, and `docker-compose.yml` needs a `deploy.resources.reservations.devices`
GPU reservation (or `--gpus all` on a one-off `docker run`) on both the
`rag-api` and `indexer` services — neither is in the compose file today
since it targets the Mac/CPU path by default.

## 3. The model cache still has to be populated

`docker-compose.yml` already mounts `./hf_cache:/home/appuser/.cache` and
sets `HF_HOME`/`HUGGINGFACE_HUB_CACHE`/`SENTENCE_TRANSFORMERS_HOME` for both
`rag-api` and `indexer`, so this part of the compose file doesn't change
between the Mac and Linux paths. What changes is *who reads it*: with
`RERANK_URL`/`EMBED_URL` empty, it's the API and indexer containers loading
`BAAI/bge-m3` and `BAAI/bge-reranker-v2-m3` from `./hf_cache` — not a host
process — so that cache has to be populated before you set `OFFLINE_MODE=true`.

Follow the same one-time download dance as the Mac quick start: set
`OFFLINE_MODE=false`, start the stack, let both models download into
`./hf_cache`, then set `OFFLINE_MODE=true` and rebuild
(`docker compose up -d --build rag-api indexer`).

## 4. Everything else matches the README's Linux section

Build as the user that owns the library folder (`UID`/`GID` build args — the
Mac defaults of `502`/`20` will not match a typical server account), keep
port 8001 bound to `127.0.0.1`, don't publish Chroma, and put a reverse
proxy in front of 8001 if other machines need the page. See
[README.md § Linux server](../README.md#linux-server).
