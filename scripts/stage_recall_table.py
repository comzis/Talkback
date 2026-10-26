"""Print the scale-test stage table (vector / rerank / pipeline / cap / cite).

docker cp scripts/stage_recall_table.py rag_api_service:/tmp/
docker cp tests/eval/questions.json tests/eval/heldout.json rag_api_service:/tmp/
docker exec -e PYTHONPATH=/app -w /app rag_api_service python /tmp/stage_recall_table.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import config
import engine
from engine import _citation_similarity
from llm.client import wait_for_models
from llm.prompts import keep_close_citations, named_library_files, supporting_sources
from retrieval.recall import fact_pages, first_hit, search_text
from retrieval.rerank import rerank_nodes
from retrieval.search import _keep, _order_nodes, _retrieve_named, _retrieve_nodes
from sources.filesystem import visible_files
from state import get
from llama_index.core import VectorStoreIndex

MAIN = Path("/tmp/questions.json")
HELD = Path("/tmp/heldout.json")


def fp(node):
    m = node.metadata or {}
    return (
        m.get("relative_path") or m.get("file_name") or "?",
        str(m.get("page_label") or m.get("page_number") or ""),
    )


def fmt(x):
    return x if x is not None else "miss"


def main() -> None:
    engine.init()
    wait_for_models(180)
    index = VectorStoreIndex.from_vector_store(
        get().vector_store, storage_context=get().storage_context
    )
    lib = [str(p.relative_to("/app/data")) for p in visible_files(Path("/app/data"))]
    rerank_k = max(config.retrieve_candidates(), config.rerank_candidates())
    print(
        f"config candidates={config.retrieve_candidates()} "
        f"rerank_candidates={config.rerank_candidates()} effective={rerank_k} "
        f"per_file={config.retrieve_per_file()} limit={config.retrieve_limit()} "
        f"balance_after={config.retrieve_balance_files()}"
    )
    print(
        f"{'suite':8} {'id':26} {'named':5} {'v20':>4} {'v50':>4} {'v100':>4} "
        f"{'rr_pool':>10} {'pipe':>4} {'cap_rm':6} {'cite':12} note"
    )
    first_word_samples = []
    for path, suite in [(MAIN, "main"), (HELD, "held")]:
        cases = json.loads(path.read_text(encoding="utf-8"))
        by_id = {c["id"]: c for c in cases}
        for case in cases:
            if case.get("path") == "general" or not case.get("file"):
                continue
            q = search_text(case, by_id)
            pages = set(fact_pages(case))
            want = case["file"]
            named = named_library_files(q, lib)

            t0 = time.perf_counter()
            raw = index.as_retriever(similarity_top_k=100).retrieve(q)
            first_word_samples.append(time.perf_counter() - t0)
            ranked = [fp(n) for n in raw]
            v20 = first_hit(ranked[:20], want, list(pages))
            v50 = first_hit(ranked[:50], want, list(pages))
            v100 = first_hit(ranked, want, list(pages))

            in_pool = first_hit(ranked[:rerank_k], want, list(pages))
            if in_pool is None:
                rr_disp = "not_in_pool"
                rr = None
                ordered = []
            else:
                ordered = (
                    rerank_nodes(q, raw[:rerank_k])
                    if config.rerank_enabled()
                    else raw[:rerank_k]
                )
                rr = first_hit([fp(n) for n in ordered], want, list(pages))
                rr_disp = fmt(rr)

            nodes, boosted = _retrieve_nodes(index, q, lib)
            pipe = first_hit([fp(n) for n in nodes], want, list(pages))

            if boosted and named:
                pinned = _retrieve_named(index, q, named, rerank_k)
                from retrieval.search import _merge_candidates

                merged = _merge_candidates(raw[:rerank_k], pinned, rerank_k)
                ord2 = _order_nodes(merged, q) if merged else []
                before = first_hit([fp(n) for n in ord2], want, list(pages))
                kept = _keep(ord2, config.retrieve_per_file(), config.retrieve_limit())
                after = first_hit([fp(n) for n in kept], want, list(pages))
                cap_rm = "yes" if before and not after else "no"
            else:
                before = rr
                after = pipe
                cap_rm = "yes" if before and not after else "no"

            cite = "n/a"
            if pipe:
                sources = []
                for i, n in enumerate(nodes, 1):
                    m = n.metadata or {}
                    sources.append(
                        {
                            "number": i,
                            "source": m.get("relative_path"),
                            "path": m.get("relative_path"),
                            "page": str(m.get("page_label") or ""),
                            "text": n.get_text() or "",
                            "label": "",
                        }
                    )
                facts = []
                for group in case.get("answer_any_of") or []:
                    if group:
                        facts.append(group[0])
                facts += list(case.get("answer_contains") or [])
                num = next(
                    (
                        s["number"]
                        for s in sources
                        if s["source"] == want and s["page"] in pages
                    ),
                    1,
                )
                fake = (
                    (" ".join(facts)) if facts else "See the standard."
                ) + f" [{num}]"
                used = keep_close_citations(
                    fake,
                    supporting_sources(fake, sources),
                    _citation_similarity,
                    query=case["query"],
                )
                if not any(
                    s.get("source") == want and str(s.get("page") or "") in pages
                    for s in sources
                ):
                    cite = "not_in_prompt"
                elif not used:
                    cite = "yes"
                elif not any(
                    s.get("source") == want and str(s.get("page") or "") in pages
                    for s in used
                ):
                    cite = "other_page"
                else:
                    cite = "no"

            note = ""
            if named:
                note = "boost:" + ",".join(Path(n).name[:18] for n in named[:2])
            if v100 is None:
                note = (note + " " if note else "") + "missing@100"
            elif v20 is None:
                note = (note + " " if note else "") + f"vec@{v100}"

            print(
                f"{suite:8} {case['id'][:26]:26} {str(bool(named)):5} "
                f"{fmt(v20):>4} {fmt(v50):>4} {fmt(v100):>4} {str(rr_disp):>10} "
                f"{fmt(pipe):>4} {cap_rm:6} {cite:12} {note[:40]}"
            )

    if first_word_samples:
        avg = sum(first_word_samples) / len(first_word_samples)
        print(
            f"vector_search_latency_s n={len(first_word_samples)} "
            f"avg={avg:.3f} max={max(first_word_samples):.3f}"
        )


if __name__ == "__main__":
    main()
