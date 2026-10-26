# Pilot corpus checklist

New engineering documents go into a subfolder of the existing library. Leave
`LIBRARY_PATH` pointed at `/Users/comzis/TalkbackDemo`. Do not change the
library root and do not upload folders from the GUI.

## 1. Copy the files

- Create `/Users/comzis/TalkbackDemo/engineering/` if it does not exist.
- Copy about 50–100 non-sensitive files into that subfolder.
- Prefer PDFs with a text layer, Markdown, and plain text. Scans and images
  index poorly (see the inventory report).
- Leave the three demo PDFs in the library root (or elsewhere under
  `TalkbackDemo`) so the existing demo eval stays usable.

## 2. Inventory

Run inventory on the engineering subfolder only:

```bash
python scripts/inventory.py /Users/comzis/TalkbackDemo/engineering
```

Check:

- File counts by type and total size
- PDFs listed as scans (little or no text layer)
- Files Talkback would **index**, **index poorly**, or **skip**

Remove or replace scans before indexing if you can.

## 3. Sensitivity scan (report only)

```bash
python scripts/sensitivity_scan.py /Users/comzis/TalkbackDemo/engineering
```

Review every hit (credentials, API keys, private keys, emails, phones, IP/MAC
lists). The script does not change files. Drop or redact anything that must
not enter the local index.

## 4. Exclusions (optional)

Put a `.talkbackignore` file at the library root to skip files without
deleting them. One pattern per line (`#` comments allowed). Basename
patterns match anywhere under the library; paths with `/` match the relative
path. Finder metadata (`.DS_Store`, `._*`) is always skipped.

## 5. Incremental re-index

Keep the stack running with the usual `LIBRARY_PATH`. Do **not** wipe Chroma
or force a full rebuild for this drop.

In the UI, use **Re-index** (or the normal indexer poll) so only new and
changed files under `engineering/` are added. Wait until `/system/status`
shows the collection count risen and no reindex alarm.

Confirm Docker has enough memory (16 GiB in the README) and that the host
reranker (and embedder, if `EMBED_URL` is set) is up.

## 6. Smoke five questions

Ask five hand-written questions about the new files (UI or `/query/stream`):

1. A short factual question with a known page in `engineering/`
2. A cross-language question if the corpus is mixed
3. A short one-line answer (name, figure, or file)
4. A question the new files do not cover
5. A follow-up (“tell me more”) after a library hit

Confirm citations name the engineering file, language is right, and uncovered
questions do not keep a card.

## 7. Eval

Demo-quality evals stay in the tracked JSON under `tests/eval/`. Questions
about copyrighted engineering books must live only under
`tests/eval/local/` (gitignored). Do not commit book text.

1. Engineers fill `tests/eval/questions.template.csv` (see
   [eval-authoring.md](eval-authoring.md)), with `file` paths that match the
   library (for example `engineering/some-guide.pdf`).
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
