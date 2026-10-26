#!/bin/sh
# Start the Mac reranker and embedder on the Apple GPU. The API reaches it at
# http://host.docker.internal:11435 when RERANK_URL / EMBED_URL are set.
# On a Linux GPU server, do not use this. Build the API image with a CUDA
# torch wheel so those models stay in the container.

set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
venv="$root/.rerank-host"
cache="$root/hf_cache/huggingface/hub"
embed_cache="$root/hf_cache/llama_index"
python=${PYTHON:-}
if [ -z "$python" ]; then
  if command -v python3.13 >/dev/null 2>&1; then
    python=python3.13
  else
    python=python3
  fi
fi

if [ ! -x "$venv/bin/python" ]; then
  "$python" -m venv "$venv"
  "$venv/bin/pip" install --upgrade pip
  "$venv/bin/pip" install torch transformers sentence-transformers
elif ! "$venv/bin/python" -c "import sentence_transformers" 2>/dev/null; then
  "$venv/bin/pip" install sentence-transformers
fi

export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export PYTORCH_ENABLE_MPS_FALLBACK=1
exec "$venv/bin/python" "$root/scripts/rerank_host.py" \
  --cache "$cache" \
  --embed-cache "$embed_cache" \
  --host 127.0.0.1 \
  --port 11435
