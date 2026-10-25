"""The process object is created once and holds the status the UI polls."""

import pytest

import state


@pytest.fixture(autouse=True)
def _isolated_process():
    state.reset_for_tests()
    yield
    state.reset_for_tests()


def test_activate_returns_the_same_object():
    first = state.activate()
    second = state.activate()
    assert first is second
    assert first.ingestion_status["status"] == "idle"
    assert first.needs_reindex is False
    assert first.cached_index is None


def test_get_before_start_fails():
    with pytest.raises(RuntimeError):
        state.get()
