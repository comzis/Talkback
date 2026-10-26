# Writing Talkback eval questions

Engineers write the questions while reading the documents. The model does not
write the expected answers. A second engineer checks each row against the PDF
before the row enters the main or held-out set.

## Rules

1. **One fact per question.** Do not combine two measurements in one case unless
   the document states them as one requirement.
2. **Record the file and page while you read.** Use the PDF page label, not the
   chunk number and not a screenshot filename.
3. **Copy phrasings from the document.** For `answer_contains` and
   `answer_any_of`, take the wording from the page (or a careful translation of
   that sentence). Do not paste a model reply.
4. Include a few **short-answer** questions (one name, one figure, one file).
5. Include a few **cross-language** questions when the library is mixed.
6. Include a few **"not in the documents"** questions (`path` = `uncovered` or
   `general`) so a wrong citation is caught.
7. Split about **70% main / 30% held-out** before any scoring. Freeze held-out.
   Do not change a rule or an expected phrasing because of a held-out miss.
8. A second engineer reviews file, page, and expected strings against the PDF.

## CSV template

Fill in [`tests/eval/questions.template.csv`](../tests/eval/questions.template.csv).
Convert it to the JSON the live runner uses:

```bash
python scripts/csv_to_eval.py tests/eval/questions.template.csv -o /tmp/questions.json
```

| Column | Required | Notes |
| --- | --- | --- |
| `id` | yes | Stable slug, unique across main and held-out |
| `set` | yes | `main` or `heldout` |
| `query` | yes | The question as an engineer would ask it |
| `path` | yes | `library`, `uncovered`, or `general` |
| `file` | library | Exact library file name |
| `pages` | library | One page or a `|`-separated list (`16` or `4\|6\|11`) |
| `language` | no | `en`, `fr`, or `es` when the reply must be in that language |
| `answer_contains` | no | `|`-separated strings that must all appear |
| `answer_any_of` | no | Facts separated by `;`. Alternatives inside a fact by `\|` |
| `card_contains` | no | `|`-separated strings that must appear on a source card |
| `continues` | no | Parent case `id` for a follow-up |
| `notice` | general | Exact general-path notice when `path` is `general` |
| `gap_about` | uncovered | Subject the library does not cover |
| `figure_labels` | uncovered | `|`-separated labels allowed on a borrowed figure |
| `placeholders` | no | `true` when the reply must include `[brackets]` |
| `known` | main only | Short note if the case is a documented limitation |
| `notes` | no | Author notes; not copied into the JSON |

## After conversion

- Put main rows in `tests/eval/questions.json` (or a new file the runner is
  pointed at with `--cases`).
- Put held-out rows in `tests/eval/heldout.json`. If you change held-out on
  purpose, update `tests/eval/heldout.sha256` in the same change.
- Run `python -m pytest app/tests/test_eval_schema.py`.
