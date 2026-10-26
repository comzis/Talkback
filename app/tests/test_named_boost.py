"""Named files boost the global pool; they do not replace it."""

import pytest

pytest.importorskip("llama_index")


def test_merge_candidates_puts_named_hits_first_without_dropping_global():
    from retrieval.search import _merge_candidates

    class Node:
        def __init__(self, node_id, text):
            self.node_id = node_id
            self._text = text
            self.metadata = {}

        def get_text(self):
            return self._text

    global_nodes = [
        Node("g1", "global-a"),
        Node("g2", "global-b"),
        Node("shared", "both"),
    ]
    named_nodes = [Node("n1", "named-a"), Node("shared", "both")]
    merged = _merge_candidates(global_nodes, named_nodes, limit=4)
    assert [node.node_id for node in merged] == ["n1", "shared", "g1", "g2"]


def test_merge_candidates_respects_limit():
    from retrieval.search import _merge_candidates

    class Node:
        def __init__(self, node_id):
            self.node_id = node_id
            self.metadata = {}

        def get_text(self):
            return self.node_id

    named = [Node(f"n{i}") for i in range(3)]
    global_nodes = [Node(f"g{i}") for i in range(5)]
    merged = _merge_candidates(global_nodes, named, limit=4)
    assert [node.node_id for node in merged] == ["n0", "n1", "n2", "g0"]
