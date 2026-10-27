"""Runtime settings. The chat model comes only from OLLAMA_MODEL."""

from __future__ import annotations

import os

DEFAULT_OLLAMA_BASE_URL = "http://host.docker.internal:11434"
# BAAI/bge-m3 is MIT. intfloat/multilingual-e5-small stays available via EMBED_MODEL.
DEFAULT_EMBED_MODEL = "BAAI/bge-m3"
COMPACT_EMBED_MODEL = "intfloat/multilingual-e5-small"
DEFAULT_EMBED_BATCH = 16
DEFAULT_OLLAMA_TIMEOUT = 300.0
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 64
DEFAULT_RETRIEVE_CANDIDATES = 8
DEFAULT_RETRIEVE_LIMIT = 6
DEFAULT_RETRIEVE_PER_FILE = 2
# The per-file cap starts once the hits come from more files than this.
DEFAULT_RETRIEVE_BALANCE_FILES = 5
DEFAULT_OLLAMA_CONTEXT = 4096
DEFAULT_OLLAMA_KEEP_ALIVE = "30m"
# Qwen 3.5 writes a hidden reasoning trace unless this is turned off.
DEFAULT_OLLAMA_THINK = False
# e5-small cosine scores on the real PDFs: a CV question scored about 0.79,
# and an unrelated question topped out at 0.65. 0.75 sits between them.
# Used only when the reranker is off.
DEFAULT_RELEVANCE_THRESHOLD = 0.75
# BAAI/bge-reranker-v2-m3 is Apache-2.0. It runs from the local cache.
DEFAULT_RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
DEFAULT_RERANK_CANDIDATES = 50
DEFAULT_BM25_CANDIDATES = 50
# Token cap for each query-passage pair. The forward pass does not see more.
DEFAULT_RERANK_MAX_LENGTH = 512
# Logged only. It does not choose the path. Correct pages landed as low as
# about -7.4, and the unrelated SRT draft scored about -5.2.
DEFAULT_RERANK_THRESHOLD = -7.5


def _raw(name: str) -> str:
    return (os.getenv(name) or "").strip()


def configured_model() -> str:
    """The model name from the environment, or an empty string when it is unset."""
    return _raw("OLLAMA_MODEL")


def require_ollama_model() -> str:
    model = configured_model()
    if not model:
        raise ValueError("OLLAMA_MODEL is not set. Add it to .env before starting.")
    return model


def ollama_base_url() -> str:
    return _raw("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL


def chat_backend() -> str:
    """ollama or vllm. Anything else stays ollama so a typo does not disable chat."""
    raw = _raw("CHAT_BACKEND").lower()
    if raw == "vllm":
        return "vllm"
    return "ollama"


def chat_base_url() -> str:
    """OpenAI-compatible origin. Defaults to the Ollama address."""
    return _raw("CHAT_BASE_URL") or ollama_base_url()


def ollama_timeout() -> float:
    raw = _raw("OLLAMA_TIMEOUT")
    if not raw:
        return DEFAULT_OLLAMA_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_OLLAMA_TIMEOUT
    return value if value > 0 else DEFAULT_OLLAMA_TIMEOUT


def embed_model_name() -> str:
    return _raw("EMBED_MODEL") or DEFAULT_EMBED_MODEL


def embed_batch() -> int:
    return _positive_int("EMBED_BATCH", DEFAULT_EMBED_BATCH)


def _positive_int(name: str, default: int) -> int:
    raw = _raw(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def chunk_size() -> int:
    return _positive_int("CHUNK_SIZE", DEFAULT_CHUNK_SIZE)


def chunk_overlap() -> int:
    raw = _raw("CHUNK_OVERLAP")
    if not raw:
        return DEFAULT_CHUNK_OVERLAP
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_CHUNK_OVERLAP
    return value if value >= 0 else DEFAULT_CHUNK_OVERLAP


def retrieve_candidates() -> int:
    return _positive_int("RETRIEVE_CANDIDATES", DEFAULT_RETRIEVE_CANDIDATES)


def retrieve_limit() -> int:
    return _positive_int("RETRIEVE_LIMIT", DEFAULT_RETRIEVE_LIMIT)


def retrieve_per_file() -> int:
    return _positive_int("RETRIEVE_PER_FILE", DEFAULT_RETRIEVE_PER_FILE)


def retrieve_balance_files() -> int:
    """Apply the per-file cap only when the hits span more files than this."""
    raw = _raw("RETRIEVE_BALANCE_FILES")
    if not raw:
        return DEFAULT_RETRIEVE_BALANCE_FILES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_RETRIEVE_BALANCE_FILES
    return value if value >= 0 else DEFAULT_RETRIEVE_BALANCE_FILES


def ollama_context() -> int:
    return _positive_int("OLLAMA_CONTEXT", DEFAULT_OLLAMA_CONTEXT)


def ollama_keep_alive() -> str:
    return _raw("OLLAMA_KEEP_ALIVE") or DEFAULT_OLLAMA_KEEP_ALIVE


def ollama_think() -> bool:
    """True only when OLLAMA_THINK is explicitly enabled. Default is off."""
    raw = _raw("OLLAMA_THINK").lower()
    if not raw:
        return DEFAULT_OLLAMA_THINK
    return raw in {"1", "true", "yes"}


def rerank_enabled() -> bool:
    """False only when RERANK is explicitly turned off. Default is on."""
    raw = _raw("RERANK").lower()
    if not raw:
        return True
    return raw not in {"0", "false", "no"}


def rerank_model_name() -> str:
    return _raw("RERANK_MODEL") or DEFAULT_RERANK_MODEL


def rerank_url() -> str:
    """Host reranker. Empty means score pairs inside this process."""
    return _raw("RERANK_URL")


def embed_url() -> str:
    """Host embedder. Empty means embed inside this process."""
    return _raw("EMBED_URL")


def rerank_candidates() -> int:
    return _positive_int("RERANK_CANDIDATES", DEFAULT_RERANK_CANDIDATES)


def hybrid_bm25() -> bool:
    """Merge BM25 hits into the vector pool before rerank. Default on.

    Keyword-heavy main questions (codes, field names, exact phrases) gain
    pipeline recall with reserved-slot hybrid; earlier main misses were mostly
    semantic, so they understated the benefit.
    """
    raw = _raw("HYBRID_BM25").lower()
    if not raw:
        return True
    return raw not in {"0", "false", "no"}


def bm25_candidates() -> int:
    return _positive_int("BM25_CANDIDATES", DEFAULT_BM25_CANDIDATES)


def rerank_max_length() -> int:
    return _positive_int("RERANK_MAX_LENGTH", DEFAULT_RERANK_MAX_LENGTH)


def rerank_threshold() -> float:
    raw = _raw("RERANK_THRESHOLD")
    if not raw:
        return DEFAULT_RERANK_THRESHOLD
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_RERANK_THRESHOLD


def relevance_threshold() -> float:
    raw = _raw("RELEVANCE_THRESHOLD")
    if not raw:
        return DEFAULT_RELEVANCE_THRESHOLD
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_RELEVANCE_THRESHOLD
    return value


def torch_threads() -> int:
    """CPU threads for torch. Default is half the visible cores, at least one."""
    default = max(1, (os.cpu_count() or 2) // 2)
    return _positive_int("TORCH_THREADS", default)
