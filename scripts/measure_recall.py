"""Retrieval-only recall for the eval questions. This does not call the chat model.

Ask the index for the top 20 chunks by similarity score and record whether the
page that holds the fact is inside the first 4, 8, and 20. A question that
names a file is searched inside that file, which is what the app does. The
live path asks for fewer candidates before it answers. Questions with an empty
pages list have no fact in the library and stay out of the recall rate.
Print the held-out set on its own. Do not change a rule because of it.

    python scripts/measure_recall.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from retrieval.recall import fact_pages, first_hit, recall_at, search_text

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "tests" / "eval" / "questions.json"
HELD = ROOT / "tests" / "eval" / "heldout.json"
CUTS = (4, 8, 20)


def load_cases(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def node_place(node) -> tuple[str, str, float | None]:
    metadata = node.metadata or {}
    name = metadata.get("relative_path") or metadata.get("file_name") or ""
    page = metadata.get("page_label") or metadata.get("page_number") or ""
    return str(name), str(page), getattr(node, "score", None)


def ranked_places(index, query: str, library_files: list[str], top_k: int):
    """Highest-scoring chunks. Named files boost the global pool, as the app does.

    Rank is the similarity score. The prose-versus-link reorder and the trim to
    four excerpts happen later, when an answer is built.
    """
    from llm.prompts import named_library_files
    from retrieval.search import _merge_candidates, _retrieve_named

    global_nodes = index.as_retriever(similarity_top_k=top_k).retrieve(query)
    named = named_library_files(query, library_files)
    nodes = global_nodes
    if named:
        pinned = _retrieve_named(index, query, named, top_k)
        if pinned:
            nodes = _merge_candidates(global_nodes, pinned, top_k)
    nodes = sorted(
        nodes, key=lambda node: getattr(node, "score", None) or 0, reverse=True
    )
    return nodes, bool(named)


def open_index():
    """Connect to Chroma and load the embedder. The chat model stays unloaded."""
    from llama_index.core import Settings
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    import config
    import store.embeddings as embeddings
    from state import activate
    from store.chroma import (
        connect_chroma,
        get_or_create_cached_index,
        indexed_documents,
    )

    activate()
    connect_chroma()
    model_name = config.embed_model_name()
    Settings.embed_model = HuggingFaceEmbedding(
        model_name=model_name,
        query_instruction=embeddings.query_instruction(model_name),
        text_instruction=embeddings.text_instruction(model_name),
    )
    index = get_or_create_cached_index()
    indexed, _legacy, _incomplete = indexed_documents()
    return index, sorted(indexed), model_name


def measure(index, files: list[str], cases: list[dict], top_k: int) -> list[dict]:
    by_id = {case["id"]: case for case in cases}
    rows = []
    for case in cases:
        query = search_text(case, by_id)
        nodes, named = ranked_places(index, query, files, top_k)
        places = [node_place(node) for node in nodes]
        ranked = [(name, page) for name, page, _score in places]
        expected = fact_pages(case)
        top = places[0] if places else ("", "", None)
        rows.append(
            {
                "id": case["id"],
                "file": case.get("file") or "",
                "expected": expected,
                "rank": first_hit(ranked, case.get("file") or "", expected),
                "named": named,
                "top_file": top[0],
                "top_page": top[1],
                "top_score": top[2],
                "query": query,
            }
        )
    return rows


def _rate_line(rows: list[dict]) -> str:
    ranks = [row["rank"] for row in rows if row["expected"]]
    parts = []
    for k in CUTS:
        hits, total = recall_at(ranks, k)
        parts.append(f"recall@{k} {hits}/{total}")
    return "  " + "  ".join(parts)


def _short(name: str) -> str:
    return Path(name).name if name else "?"


def format_report(title: str, rows: list[dict]) -> str:
    lines = [title, _rate_line(rows)]
    for row in rows:
        score = row["top_score"]
        score_text = f"{score:.3f}" if isinstance(score, float) else "n/a"
        top = f"{_short(row['top_file'])} p.{row['top_page']} {score_text}"
        if not row["expected"]:
            lines.append(f"  {row['id']}  no fact page  top {top}")
            continue
        rank = "miss" if row["rank"] is None else f"rank {row['rank']}"
        lines.append(
            f"  {row['id']}  {rank}  expected p.{'/'.join(row['expected'])}  top {top}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main", type=Path, default=MAIN)
    parser.add_argument("--heldout", type=Path, default=HELD)
    parser.add_argument("--top-k", type=int, default=20)
    args = parser.parse_args()
    index, files, model_name = open_index()
    print(f"embedder {model_name}  files {len(files)}  top {args.top_k}")
    main_rows = measure(index, files, load_cases(args.main), args.top_k)
    held_rows = measure(index, files, load_cases(args.heldout), args.top_k)
    print(format_report("main", main_rows))
    print(format_report("held-out", held_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
