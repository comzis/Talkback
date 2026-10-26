"""Compose takes the library folder from the environment."""

from pathlib import Path

COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.yml"


def test_compose_takes_the_library_path_from_the_environment():
    text = COMPOSE.read_text(encoding="utf-8")
    mount = "${LIBRARY_PATH:?set LIBRARY_PATH in .env}:/app/data:ro"
    assert text.count(mount) == 2
    assert "/Users/" not in text


def test_compose_keeps_the_status_db_on_a_named_volume():
    text = COMPOSE.read_text(encoding="utf-8")
    assert text.count("talkback_status:/app/status") == 2
    assert "./status:/app/status" not in text
    assert "talkback_status:" in text.split("volumes:")[-1]
