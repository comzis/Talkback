"""Score reranker pairs and embed texts on this machine's GPU.

Docker on a Mac cannot see the Apple GPU, so the API calls this process the
same way it calls Ollama. CUDA wins when it is present, then MPS, then CPU.
A Linux GPU server should run these models inside the container on CUDA
instead of starting this process.
"""

from __future__ import annotations

import argparse
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def pick_device(cuda: bool, mps: bool) -> str:
    """Prefer an NVIDIA GPU, then an Apple GPU, then the CPU."""
    if cuda:
        return "cuda"
    if mps:
        return "mps"
    return "cpu"


def _torch_device():
    import torch

    name = pick_device(
        torch.cuda.is_available(),
        bool(
            getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()
        ),
    )
    return torch.device(name)


class _Scorer:
    def __init__(self, cache: str) -> None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.device = _torch_device()
        name = os.environ.get("RERANK_MODEL") or "BAAI/bge-reranker-v2-m3"
        self.name = name
        self.tokenizer = AutoTokenizer.from_pretrained(
            name, cache_dir=cache, local_files_only=True
        )
        self.model = AutoModelForSequenceClassification.from_pretrained(
            name, cache_dir=cache, local_files_only=True
        )
        self.model.to(self.device)
        self.model.eval()

    def scores(self, query: str, passages: list[str], limit: int) -> list[float]:
        import torch

        pairs = [[query, text] for text in passages]
        found: list[float] = []
        with torch.no_grad():
            for start in range(0, len(pairs), 8):
                batch = pairs[start : start + 8]
                inputs = self.tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    return_tensors="pt",
                    max_length=limit,
                )
                inputs = {key: value.to(self.device) for key, value in inputs.items()}
                logits = self.model(**inputs, return_dict=True).logits.view(-1).float()
                found.extend(float(score) for score in logits.cpu().tolist())
        return found


class _Embedder:
    """bge-m3 (or EMBED_MODEL) via sentence-transformers on the host GPU."""

    def __init__(self, cache: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.device = _torch_device()
        name = os.environ.get("EMBED_MODEL") or "BAAI/bge-m3"
        self.name = name
        self.model = SentenceTransformer(
            name,
            device=str(self.device),
            cache_folder=cache,
            local_files_only=True,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]


class _Models:
    """Reranker loads at start. Embedder loads on the first /embed call."""

    def __init__(self, rerank_cache: str, embed_cache: str) -> None:
        self.rerank_cache = rerank_cache
        self.embed_cache = embed_cache
        self.scorer = _Scorer(rerank_cache)
        self._embedder: _Embedder | None = None
        self._embed_lock = threading.Lock()

    def embedder(self) -> _Embedder:
        with self._embed_lock:
            if self._embedder is None:
                print("rerank-host loading embedder", flush=True)
                self._embedder = _Embedder(self.embed_cache)
                print(
                    f"rerank-host embedder ready device={self._embedder.device} "
                    f"model={self._embedder.name}",
                    flush=True,
                )
            return self._embedder


def _handler(models: _Models):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            print(f"rerank-host {self.address_string()} {fmt % args}", flush=True)

        def _send(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path.split("?", 1)[0] != "/health":
                self._send(404, {"error": "not found"})
                return
            embedder = models._embedder
            self._send(
                200,
                {
                    "status": "ok",
                    "device": str(models.scorer.device),
                    "model": models.scorer.name,
                    "embed_loaded": embedder is not None,
                    "embed_device": str(embedder.device) if embedder else None,
                    "embed_model": embedder.name if embedder else None,
                },
            )

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            length = int(self.headers.get("Content-Length") or "0")
            try:
                body = json.loads(self.rfile.read(length).decode() or "{}")
            except Exception as exc:
                self._send(400, {"error": str(exc)})
                return

            if path == "/rerank":
                try:
                    query = str(body.get("query") or "")
                    passages = body.get("passages") or []
                    limit = int(body.get("max_length") or 512)
                    if not isinstance(passages, list) or not query:
                        raise ValueError("query and passages are required")
                    texts = [str(item) for item in passages]
                    scores = models.scorer.scores(query, texts, limit)
                except Exception as exc:
                    self._send(400, {"error": str(exc)})
                    return
                self._send(
                    200,
                    {
                        "scores": scores,
                        "device": str(models.scorer.device),
                        "pairs": len(scores),
                    },
                )
                return

            if path == "/embed":
                try:
                    texts = body.get("texts") or []
                    if not isinstance(texts, list) or not texts:
                        raise ValueError("texts is required")
                    prepared = [str(item) for item in texts]
                    embedder = models.embedder()
                    vectors = embedder.embed(prepared)
                except Exception as exc:
                    self._send(400, {"error": str(exc)})
                    return
                self._send(
                    200,
                    {
                        "embeddings": vectors,
                        "device": str(embedder.device),
                        "model": embedder.name,
                        "count": len(vectors),
                    },
                )
                return

            self._send(404, {"error": "not found"})

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Host reranker and embedder for the Talkback API"
    )
    parser.add_argument(
        "--cache", required=True, help="Reranker Hugging Face hub directory"
    )
    parser.add_argument(
        "--embed-cache",
        default="",
        help="Sentence-transformers cache (defaults to sibling llama_index cache)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11435)
    args = parser.parse_args()
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    embed_cache = args.embed_cache
    if not embed_cache:
        # HuggingFaceEmbedding stores BAAI/bge-m3 under llama_index/, not hub/.
        embed_cache = os.path.join(os.path.dirname(args.cache), "..", "llama_index")
        embed_cache = os.path.abspath(embed_cache)
    models = _Models(args.cache, embed_cache)
    server = ThreadingHTTPServer((args.host, args.port), _handler(models))
    print(
        f"rerank-host listening on {args.host}:{args.port} "
        f"rerank_device={models.scorer.device} embed_cache={embed_cache}",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
