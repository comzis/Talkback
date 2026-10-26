# Status database

Talkback keeps file-index state, the ingest lock, the request queue, and the
job payload in one SQLite file: `library.sqlite` at `/app/status` inside the
API and indexer containers.

## Why it uses a named volume

Both containers used to share `./status` through Docker Desktop's macOS file
sharing, with `PRAGMA journal_mode=WAL`. That layout creates `-wal` and `-shm`
sidecar files on the Mac host. Under concurrent use SQLite can raise
`sqlite3.OperationalError: disk I/O error` on `run_lock`. The indexer log on
2026-10-25 showed that error before the worker loop died.

A short concurrent stress test (three containers, 800 lock updates each) did
**not** reproduce the error on a bind mount that day; the failure is
intermittent. The database now lives on the named Docker volume
`talkback_status` (inside the Docker VM's own disk), and journal mode is
`DELETE` so no WAL sidecars cross the VM boundary.

## Backup

Compose prefixes the volume with the project name. List it first:

```bash
docker volume ls | grep talkback_status
```

Then copy the file out (replace the volume name if yours differs):

```bash
docker run --rm \
  -v talkback-refactor_talkback_status:/status \
  -v "$PWD:/backup" \
  alpine cp /status/library.sqlite /backup/library.sqlite.bak
```

## Inspect, migrate, rebuild

`migrate` fills an empty table from Chroma. `rebuild` replaces every row from
the current Chroma metadata. Both use `STATUS_DIR` (default `/app/status`):

```bash
docker compose run --rm rag-api python -m store.status_db migrate
docker compose run --rm rag-api python -m store.status_db rebuild
```

Shell on the volume:

```bash
docker run --rm -it \
  -v talkback-refactor_talkback_status:/app/status \
  talkback-refactor-rag-api bash
```

## Copy an old `./status` file into the volume once

If you still have `./status/library.sqlite` from before the named volume:

```bash
docker run --rm \
  -v talkback-refactor_talkback_status:/status \
  -v "$PWD/status:/src:ro" \
  alpine sh -c 'cp /src/library.sqlite /status/library.sqlite && chown -R 502:20 /status'
```

Use the image UID/GID from the compose build (default `502:20`). Recreate the API
and indexer afterward so they mount the volume.
