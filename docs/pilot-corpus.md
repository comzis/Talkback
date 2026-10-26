# Pilot corpus checklist

Use this when the engineering document folder is ready. Do not point
`LIBRARY_PATH` at a company folder until inventory and the sensitivity scan
are clean enough for a local demo.

## 1. Copy the files

- Put about 50–100 non-sensitive files in a dedicated folder on the machine
  that runs Docker.
- Prefer PDFs with a text layer, Markdown, and plain text. Scans and images
  index poorly (see the inventory report).
- Keep the three demo PDFs out of this folder (or use a separate compose
  project) so demo tuning stays frozen.

## 2. Set `LIBRARY_PATH`

In `.env` (not committed):

```bash
LIBRARY_PATH=/absolute/path/to/pilot-folder
```

Compose already mounts that path read-only into the API and the indexer.

## 3. Inventory

```bash
python scripts/inventory.py "$LIBRARY_PATH"
```

Check:

- File counts by type and total size
- PDFs listed as scans (little or no text layer)
- Files Talkback would **index**, **index poorly**, or **skip**

Remove or replace scans and secrets before indexing if you can.

## 4. Sensitivity scan (report only)

```bash
python scripts/sensitivity_scan.py "$LIBRARY_PATH"
```

Review every hit (credentials, API keys, private keys, emails, phones, IP/MAC
lists). The script does not change files. Drop or redact anything that must
not enter the local index.

## 5. Full rebuild

Give Docker Desktop at least 16 GiB. With the host reranker installed
(`scripts/install-rerank-host.sh`), start the stack and rebuild the library:

```bash
docker compose up -d --build
# Wait until /system/status shows the new collection count and no reindex alarm.
```

If the folder replaces an older library with a different embedding identity,
follow the README full re-index steps. Confirm `OFFLINE_MODE` stays on after
models are cached.

## 6. Smoke five questions

Ask five hand-written questions in the UI (or via `/query/stream`):

1. A short factual question with a known page
2. A cross-language question if the corpus is mixed
3. A short one-line answer (name, figure, or file)
4. A question the corpus does not cover
5. A follow-up (“tell me more”) after a library hit

Confirm citations, language, and that uncovered questions do not keep a card.

## 7. Eval

1. Engineers fill `tests/eval/questions.template.csv` (see
   [eval-authoring.md](eval-authoring.md)).
2. Convert with `scripts/csv_to_eval.py` into main and held-out JSON.
3. Freeze held-out and refresh `tests/eval/heldout.sha256` if that file is
   replaced.
4. Run `python -m pytest app/tests/test_eval_schema.py`.
5. With the API up:

```bash
python -u scripts/run_live_eval.py --cases path/to/main.json --runs 3
python -u scripts/run_live_eval.py --cases path/to/heldout.json --runs 3
```

Tune only from the main set. Report held-out; do not change rules from it.
