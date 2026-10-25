"""Time indexing and one answer on a throwaway in-memory index.

Does not open the live Chroma collection. It stays out of the API image.
From the repository root, with the app dependencies installed:

    PYTHONPATH=app python scripts/bench_scratch.py --profile before
    PYTHONPATH=app python scripts/bench_scratch.py --profile after
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from pathlib import Path

PROFILES = {
    "before": {
        "embed_model": "BAAI/bge-small-en-v1.5",
        "chunk_size": 1024,
        "chunk_overlap": 200,
        "candidates": 24,
        "per_file": 2,
        "limit": 4,
        "context_window": None,
        "keep_alive": None,
        "torch_threads": None,
        "query_instruction": None,
        "text_instruction": None,
    },
    "after": {
        "embed_model": "intfloat/multilingual-e5-small",
        "chunk_size": 512,
        "chunk_overlap": 64,
        "candidates": 8,
        "per_file": 2,
        "limit": 4,
        "context_window": 4096,
        "keep_alive": "30m",
        "torch_threads": "half",
        "query_instruction": "query:",
        "text_instruction": "passage:",
    },
}

QUERY = "What is the beacon code in document 17?"


def write_corpus(root: Path, count: int = 30) -> None:
    root.mkdir(parents=True, exist_ok=True)
    filler = (
        "The maintenance note repeats that pumps, valves, and gauges are logged "
        "at the end of each shift. Operators record pressure, temperature, and "
        "the name of the person on duty. This paragraph exists so the file is "
        "long enough to split into more than one chunk. "
    )
    for number in range(1, count + 1):
        body = filler * 40
        body += f"\n\nThe beacon code for document {number} is BENCH-{number}.\n"
        (root / f"document-{number:02d}.txt").write_text(body, encoding="utf-8")


def memory_bytes() -> int | None:
    for path in (
        "/sys/fs/cgroup/memory.current",
        "/sys/fs/cgroup/memory/memory.usage_in_bytes",
    ):
        if os.path.exists(path):
            return int(Path(path).read_text().strip())
    return None


class MemoryWatch:
    def __init__(self) -> None:
        self.peak = memory_bytes() or 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.wait(0.5):
            current = memory_bytes() or 0
            if current > self.peak:
                self.peak = current

    def __enter__(self) -> "MemoryWatch":
        self._thread.start()
        return self

    def __exit__(self, *_) -> None:
        self._stop.set()
        self._thread.join(timeout=1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    profile = PROFILES[args.profile]

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"

    import torch
    from llama_index.core import Document, StorageContext, VectorStoreIndex
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.core.vector_stores import SimpleVectorStore
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    from llama_index.llms.ollama import Ollama

    from library import balance_matches

    threads = profile["torch_threads"]
    if threads == "half":
        torch.set_num_threads(max(1, (os.cpu_count() or 2) // 2))

    root = Path("/tmp/talkback-bench-docs")
    write_corpus(root)
    documents = []
    for path in sorted(root.glob("*.txt")):
        documents.append(
            Document(
                text=path.read_text(encoding="utf-8"), metadata={"file_name": path.name}
            )
        )

    embed_kwargs = {"model_name": profile["embed_model"], "embed_batch_size": 16}
    if profile["query_instruction"]:
        embed_kwargs["query_instruction"] = profile["query_instruction"]
        embed_kwargs["text_instruction"] = profile["text_instruction"]
    embed_model = HuggingFaceEmbedding(**embed_kwargs)
    nodes = SentenceSplitter(
        chunk_size=profile["chunk_size"],
        chunk_overlap=profile["chunk_overlap"],
    ).get_nodes_from_documents(documents)

    llm_kwargs = {
        "model": os.environ["OLLAMA_MODEL"],
        "base_url": os.environ.get(
            "OLLAMA_BASE_URL", "http://host.docker.internal:11434"
        ),
        "request_timeout": 300.0,
    }
    if profile["context_window"]:
        llm_kwargs["context_window"] = profile["context_window"]
    if profile["keep_alive"]:
        llm_kwargs["keep_alive"] = profile["keep_alive"]
    llm = Ollama(**llm_kwargs)

    with MemoryWatch() as watch:
        started = time.perf_counter()
        store = SimpleVectorStore()
        index = VectorStoreIndex(
            nodes,
            storage_context=StorageContext.from_defaults(vector_store=store),
            embed_model=embed_model,
            show_progress=False,
        )
        index_seconds = time.perf_counter() - started

        answer_started = time.perf_counter()
        found = index.as_retriever(similarity_top_k=profile["candidates"]).retrieve(
            QUERY
        )
        chosen = balance_matches(
            found, per_file=profile["per_file"], limit=profile["limit"]
        )
        excerpts = "\n\n".join((node.get_text() or "")[:500] for node in chosen)
        prompt = (
            "Answer from the excerpts. If they do not contain the answer, say so.\n\n"
            f"{excerpts}\n\nQuestion: {QUERY}\nAnswer:"
        )
        first_token = None
        parts: list[str] = []
        for chunk in llm.stream_complete(prompt):
            delta = chunk.delta or ""
            if delta and first_token is None:
                first_token = time.perf_counter()
            if delta:
                parts.append(delta)
        finished = time.perf_counter()
    scores = [getattr(node, "score", None) for node in chosen]
    result = {
        "profile": args.profile,
        "documents": len(documents),
        "chunks": len(nodes),
        "index_seconds": round(index_seconds, 2),
        "time_to_first_token_seconds": round(
            (first_token - answer_started) if first_token else -1, 2
        ),
        "answer_seconds": round(finished - answer_started, 2),
        "peak_container_memory_mb": round(watch.peak / (1024 * 1024), 1),
        "retrieved": len(chosen),
        "scores": scores,
        "answer_preview": "".join(parts)[:240],
    }
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
