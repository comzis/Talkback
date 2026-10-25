"""Index the library in its own process.

The API asks for a run by writing a row. This process holds the lock row
while it embeds, so a second process does not start another run.
"""

from __future__ import annotations

import logging
import os
import signal
import time

logger = logging.getLogger(__name__)


def next_kind(store) -> str | None:
    """The waiting request, unless a run already holds the lock."""
    if store.lock_held():
        return None
    return store.peek_request()


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    import engine
    from ingestion.pipeline import (
        begin_ingestion,
        finish_ingestion,
        open_status,
        process_ingestion,
        rebuild_library,
        start_initial_index,
        start_reindex_schedule,
    )

    engine.init()
    start_reindex_schedule()
    start_initial_index()

    def stop(_signum, _frame) -> None:
        finish_ingestion()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    while True:
        time.sleep(2)
        store = open_status()
        kind = next_kind(store)
        if kind is None:
            continue
        if not begin_ingestion():
            continue
        try:
            kind = store.take_request()
            if kind == "rebuild":
                logger.info("Full re-index requested.")
                rebuild_library()
            elif kind:
                logger.info("Incremental index requested.")
                process_ingestion()
        finally:
            finish_ingestion()


if __name__ == "__main__":
    main()
