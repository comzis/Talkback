"""Score reranker pairs on this machine's GPU.

Docker on a Mac cannot see the Apple GPU, so the API calls this process the
same way it calls Ollama. CUDA wins when it is present, then MPS, then CPU.
A Linux GPU server should run the reranker inside the container on CUDA
instead of starting this process.
"""

from __future__ import annotations

import argparse
import json
import os
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


def _handler(scorer: _Scorer):
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
            self._send(
                200,
                {"status": "ok", "device": str(scorer.device), "model": scorer.name},
            )

        def do_POST(self) -> None:
            if self.path.split("?", 1)[0] != "/rerank":
                self._send(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length") or "0")
            try:
                body = json.loads(self.rfile.read(length).decode() or "{}")
                query = str(body.get("query") or "")
                passages = body.get("passages") or []
                limit = int(body.get("max_length") or 512)
                if not isinstance(passages, list) or not query:
                    raise ValueError("query and passages are required")
                texts = [str(item) for item in passages]
                scores = scorer.scores(query, texts, limit)
            except Exception as exc:
                self._send(400, {"error": str(exc)})
                return
            self._send(
                200,
                {"scores": scores, "device": str(scorer.device), "pairs": len(scores)},
            )

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Host reranker for the Talkback API")
    parser.add_argument("--cache", required=True, help="Hugging Face hub directory")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11435)
    args = parser.parse_args()
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    scorer = _Scorer(args.cache)
    server = ThreadingHTTPServer((args.host, args.port), _handler(scorer))
    print(
        f"rerank-host listening on {args.host}:{args.port} device={scorer.device}",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
