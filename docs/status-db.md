# Status database

Talkback keeps file-index state, the ingest lock, the request queue, and the
job payload in one SQLite file: `library.sqlite` under `/app/status` in the
API and indexer containers.

## Disk I/O errors on `run_lock`

Both containers shared `./status` through Docker Desktop's macOS file sharing,
with `PRAGMA journal_mode=WAL`. That creates `-wal` and `-shm` sidecar files on
the Mac host. The indexer log on 2026-10-25 raised
`sqlite3.OperationalError: disk I/O error` while reading `run_lock`, then the
worker loop died.

A concurrent stress test (three containers, 800 lock updates each) did **not**
reproduce the error today on a bind mount. The failure is intermittent and
matches a known class of SQLite problems when WAL files cross the Docker
Desktop VM boundary. The intended fix is a named Docker volume (filesystem
inside the VM) and, if needed, `journal_mode=DELETE` so no WAL sidecars are
shared with the Mac host.
