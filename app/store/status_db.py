"""SQLite file status. Planning reads this table instead of every chunk.

The file lives on a local volume. A missing index_complete marker is unfinished,
the same rule as classify_stored_chunks, so a finished library is not embedded again.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections import Counter
from pathlib import Path

from ingestion.plan import chunk_key, classify_stored_chunks

_SCHEMA = """
CREATE TABLE IF NOT EXISTS file_status (
    source_type TEXT NOT NULL,
    item_id TEXT NOT NULL,
    size INTEGER,
    modified_day TEXT,
    mtime INTEGER,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    last_error TEXT,
    indexed_at REAL,
    PRIMARY KEY (source_type, item_id)
)
"""

_LOCK_SCHEMA = """
CREATE TABLE IF NOT EXISTS run_lock (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    holder TEXT NOT NULL,
    heartbeat REAL NOT NULL
)
"""

_REQUEST_SCHEMA = """
CREATE TABLE IF NOT EXISTS ingest_request (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    kind TEXT NOT NULL,
    requested_at REAL NOT NULL
)
"""

_JOB_SCHEMA = """
CREATE TABLE IF NOT EXISTS ingest_job (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    payload TEXT NOT NULL
)
"""


class StatusStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._db: sqlite3.Connection | None = None

    def open(self) -> None:
        if self._db is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA busy_timeout=5000")
        self._db.execute(_SCHEMA)
        self._db.execute(_LOCK_SCHEMA)
        self._db.execute(_REQUEST_SCHEMA)
        self._db.execute(_JOB_SCHEMA)

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    def _conn(self) -> sqlite3.Connection:
        self.open()
        assert self._db is not None
        return self._db

    def empty(self) -> bool:
        row = self._conn().execute("SELECT COUNT(*) AS n FROM file_status").fetchone()
        return int(row["n"]) == 0

    def migrate(self, metadatas: list[dict | None]) -> None:
        """Fill an empty table from chunk metadata. A second call leaves it alone."""
        if not self.empty():
            return
        self._write_chunks(metadatas)

    def clear(self) -> None:
        """Drop every row. A full re-index then embeds the library again."""
        conn = self._conn()
        conn.execute("DELETE FROM file_status")
        conn.commit()

    def rebuild(self, metadatas: list[dict | None]) -> None:
        """Replace the table with what the index holds now."""
        conn = self._conn()
        conn.execute("DELETE FROM file_status")
        conn.commit()
        self._write_chunks(metadatas)

    def _write_chunks(self, metadatas: list[dict | None]) -> None:
        complete, legacy, incomplete = classify_stored_chunks(metadatas)
        counts = Counter(key for metadata in metadatas if (key := chunk_key(metadata)))
        unfinished = set(legacy) | set(incomplete)
        for item_id, signature in complete.items():
            if item_id in unfinished:
                continue
            size, day, mtime = signature
            self._upsert(
                "filesystem",
                item_id,
                size=size,
                modified_day=day,
                mtime=None if mtime is None else int(mtime),
                chunk_count=counts[item_id],
                status="complete",
                last_error=None,
                indexed_at=time.time(),
            )
        for item_id in sorted(unfinished):
            self._upsert(
                "filesystem",
                item_id,
                size=None,
                modified_day=None,
                mtime=None,
                chunk_count=counts[item_id],
                status="pending",
                last_error=None,
                indexed_at=None,
            )

    def planning_sets(self) -> tuple[dict[str, tuple], set[str], set[str]]:
        """Complete signatures, no legacy set, and ids that still need a pass.

        Pending and failed rows are the unfinished set. index_plan retries those
        the way it retries a chunk with no index_complete marker.
        """
        indexed: dict[str, tuple] = {}
        unfinished: set[str] = set()
        for row in self._conn().execute("SELECT * FROM file_status"):
            if row["status"] == "complete":
                indexed[row["item_id"]] = (
                    int(row["size"] or 0),
                    str(row["modified_day"] or ""),
                    None if row["mtime"] is None else int(row["mtime"]),
                )
            elif row["status"] in {"pending", "failed"}:
                unfinished.add(row["item_id"])
        return indexed, set(), unfinished

    def mark_pending(self, source_type: str, item_id: str) -> None:
        self._upsert(
            source_type,
            item_id,
            size=None,
            modified_day=None,
            mtime=None,
            chunk_count=0,
            status="pending",
            last_error=None,
            indexed_at=None,
        )

    def mark_complete(
        self,
        source_type: str,
        item_id: str,
        signature: tuple,
        chunk_count: int,
    ) -> None:
        size, day, mtime = signature
        self._upsert(
            source_type,
            item_id,
            size=int(size),
            modified_day=str(day),
            mtime=None if mtime is None else int(mtime),
            chunk_count=chunk_count,
            status="complete",
            last_error=None,
            indexed_at=time.time(),
        )

    def mark_failed(self, source_type: str, item_id: str, error: str) -> None:
        self._upsert(
            source_type,
            item_id,
            size=None,
            modified_day=None,
            mtime=None,
            chunk_count=0,
            status="failed",
            last_error=error,
            indexed_at=None,
        )

    def fail_pending(self, error: str) -> None:
        """A caught ingest error. A killed process leaves the row pending."""
        conn = self._conn()
        conn.execute(
            "UPDATE file_status SET status = 'failed', last_error = ? WHERE status = 'pending'",
            (error,),
        )
        conn.commit()

    def forget(self, source_type: str, item_id: str) -> None:
        conn = self._conn()
        conn.execute(
            "DELETE FROM file_status WHERE source_type = ? AND item_id = ?",
            (source_type, item_id),
        )
        conn.commit()

    def get(self, source_type: str, item_id: str) -> dict | None:
        row = (
            self._conn()
            .execute(
                "SELECT * FROM file_status WHERE source_type = ? AND item_id = ?",
                (source_type, item_id),
            )
            .fetchone()
        )
        return dict(row) if row else None

    def failed_rows(self) -> list[dict]:
        rows = self._conn().execute(
            "SELECT * FROM file_status WHERE status = 'failed' ORDER BY item_id"
        )
        return [dict(row) for row in rows]

    def try_lock(self, holder: str, stale_after: float = 30) -> bool:
        """Take the single run lock. A quiet holder is replaced so a crash can recover."""
        now = time.time()
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT holder, heartbeat FROM run_lock WHERE id = 1"
            ).fetchone()
            if (
                row is not None
                and row["holder"] != holder
                and now - float(row["heartbeat"]) < stale_after
            ):
                conn.rollback()
                return False
            conn.execute(
                """
                INSERT INTO run_lock (id, holder, heartbeat) VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    holder = excluded.holder,
                    heartbeat = excluded.heartbeat
                """,
                (holder, now),
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise

    def refresh_lock(self, holder: str) -> bool:
        cur = self._conn().execute(
            "UPDATE run_lock SET heartbeat = ? WHERE id = 1 AND holder = ?",
            (time.time(), holder),
        )
        return cur.rowcount == 1

    def unlock(self, holder: str) -> None:
        self._conn().execute(
            "DELETE FROM run_lock WHERE id = 1 AND holder = ?", (holder,)
        )

    def lock_held(self, stale_after: float = 30) -> bool:
        row = (
            self._conn()
            .execute("SELECT heartbeat FROM run_lock WHERE id = 1")
            .fetchone()
        )
        if row is None:
            return False
        return time.time() - float(row["heartbeat"]) < stale_after

    def request_run(self, kind: str) -> None:
        """Remember one waiting run. A rebuild replaces an incremental request."""
        if kind not in {"incremental", "rebuild"}:
            raise ValueError(kind)
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT kind FROM ingest_request WHERE id = 1"
            ).fetchone()
            if row is not None and row["kind"] == "rebuild":
                kind = "rebuild"
            conn.execute(
                """
                INSERT INTO ingest_request (id, kind, requested_at) VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    kind = excluded.kind,
                    requested_at = excluded.requested_at
                """,
                (kind, time.time()),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def peek_request(self) -> str | None:
        row = (
            self._conn()
            .execute("SELECT kind FROM ingest_request WHERE id = 1")
            .fetchone()
        )
        return None if row is None else str(row["kind"])

    def take_request(self) -> str | None:
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT kind FROM ingest_request WHERE id = 1"
            ).fetchone()
            conn.execute("DELETE FROM ingest_request WHERE id = 1")
            conn.commit()
            return None if row is None else str(row["kind"])
        except Exception:
            conn.rollback()
            raise

    def write_job(self, payload: dict) -> None:
        self._conn().execute(
            """
            INSERT INTO ingest_job (id, payload) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
            """,
            (json.dumps(payload),),
        )

    def read_job(self) -> dict | None:
        row = (
            self._conn()
            .execute("SELECT payload FROM ingest_job WHERE id = 1")
            .fetchone()
        )
        if row is None:
            return None
        return json.loads(row["payload"])

    def _upsert(
        self,
        source_type: str,
        item_id: str,
        *,
        size: int | None,
        modified_day: str | None,
        mtime: int | None,
        chunk_count: int,
        status: str,
        last_error: str | None,
        indexed_at: float | None,
    ) -> None:
        conn = self._conn()
        conn.execute(
            """
            INSERT INTO file_status (
                source_type, item_id, size, modified_day, mtime,
                chunk_count, status, last_error, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_type, item_id) DO UPDATE SET
                size = excluded.size,
                modified_day = excluded.modified_day,
                mtime = excluded.mtime,
                chunk_count = excluded.chunk_count,
                status = excluded.status,
                last_error = excluded.last_error,
                indexed_at = excluded.indexed_at
            """,
            (
                source_type,
                item_id,
                size,
                modified_day,
                mtime,
                chunk_count,
                status,
                last_error,
                indexed_at,
            ),
        )
        conn.commit()


def _chunk_metadatas():
    from state import get
    from store.chroma import collection_count

    collection = get().chroma_collection
    if collection is None or collection_count() == 0:
        return []
    stored = collection.get(include=["metadatas"])
    return stored.get("metadatas") or []


def main(argv: list[str] | None = None) -> None:
    """migrate copies Chroma metadata into an empty table. rebuild replaces the table."""
    import os
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if args not in (["migrate"], ["rebuild"]):
        raise SystemExit("Usage: python -m store.status_db migrate|rebuild")
    from state import activate, get
    from store.chroma import connect_chroma

    os.environ.setdefault("STATUS_DIR", "/app/status")
    activate()
    connect_chroma()
    store = StatusStore(get().status_dir / "library.sqlite")
    store.open()
    metadatas = _chunk_metadatas()
    if args == ["migrate"]:
        store.migrate(metadatas)
    else:
        store.rebuild(metadatas)
    indexed, _legacy, unfinished = store.planning_sets()
    print(
        f"{args[0]}: {len(indexed)} complete, {len(unfinished)} unfinished, "
        f"{len(store.failed_rows())} failed"
    )


if __name__ == "__main__":
    main()
