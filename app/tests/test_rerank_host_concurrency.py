"""GPU calls on the host service must not overlap under ThreadingHTTPServer."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import HTTPServer, ThreadingHTTPServer

from support import load_rerank_host


class _BusyScorer:
    def __init__(self, gate: "_OverlapGate") -> None:
        self.device = "cpu"
        self.name = "busy-scorer"
        self._gate = gate

    def scores(self, query: str, passages: list[str], limit: int) -> list[float]:
        with self._gate.enter("score"):
            time.sleep(0.02)
        return [float(index + len(query) + limit) for index, _ in enumerate(passages)]


class _BusyEmbedder:
    def __init__(self, gate: "_OverlapGate") -> None:
        self.device = "cpu"
        self.name = "busy-embedder"
        self._gate = gate

    def embed(self, texts: list[str]) -> list[list[float]]:
        with self._gate.enter("embed"):
            time.sleep(0.02)
        return [[float(len(text))] for text in texts]


class _OverlapGate:
    """Tracks how many GPU-style calls run at once."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.active = 0
        self.peak = 0

    def enter(self, _label: str):
        gate = self

        class _Scope:
            def __enter__(self_inner):
                with gate._lock:
                    gate.active += 1
                    gate.peak = max(gate.peak, gate.active)
                return self_inner

            def __exit__(self_inner, *_exc):
                with gate._lock:
                    gate.active -= 1

        return _Scope()


def _post(url: str, path: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        url.rstrip("/") + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode())


def test_twenty_mixed_requests_never_overlap_gpu_work():
    host = load_rerank_host()
    gate = _OverlapGate()
    models = host._Models.__new__(host._Models)
    models.rerank_cache = ""
    models.embed_cache = ""
    models._gpu_lock = threading.Lock()
    models.scorer = _BusyScorer(gate)
    models._embedder = _BusyEmbedder(gate)

    # Threading server proves the GPU lock serialises work even if HTTP is
    # concurrent. Production uses HTTPServer (single accept loop).
    server = ThreadingHTTPServer(("127.0.0.1", 0), host._handler(models))
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"

    def one(index: int) -> str:
        if index % 2 == 0:
            payload = _post(
                base,
                "/embed",
                {"texts": [f"text-{index}", f"more-{index}"]},
            )
            assert payload["count"] == 2
            return "embed"
        payload = _post(
            base,
            "/rerank",
            {"query": f"q-{index}", "passages": [f"a-{index}", f"b-{index}"]},
        )
        assert payload["pairs"] == 2
        return "rerank"

    try:
        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = [pool.submit(one, index) for index in range(20)]
            kinds = [future.result() for future in as_completed(futures)]
        assert kinds.count("embed") == 10
        assert kinds.count("rerank") == 10
        assert gate.peak == 1, f"GPU work overlapped; peak={gate.peak}"
        assert gate.active == 0
    finally:
        server.shutdown()
        server.server_close()


def test_production_server_is_single_threaded():
    host = load_rerank_host()
    assert host.HTTPServer is HTTPServer
    assert not issubclass(host.HTTPServer, ThreadingHTTPServer)


def test_bad_embed_body_is_rejected_without_gpu_work():
    host = load_rerank_host()
    gate = _OverlapGate()
    models = host._Models.__new__(host._Models)
    models.rerank_cache = ""
    models.embed_cache = ""
    models._gpu_lock = threading.Lock()
    models.scorer = _BusyScorer(gate)
    models._embedder = _BusyEmbedder(gate)
    server = HTTPServer(("127.0.0.1", 0), host._handler(models))
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        try:
            _post(f"http://127.0.0.1:{port}", "/embed", {"texts": []})
            raise AssertionError("empty texts should fail")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
        assert gate.peak == 0
    finally:
        server.shutdown()
        server.server_close()
