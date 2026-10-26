# Adding a source

A source is a read-only or writable place Talkback can index. Confluence and Jira are not implemented. A new source is another class that satisfies `sources.base.Source`. The interface does not take a user. Later, per-folder permissions belong on retrieval, plus an identity on the API, not on `Source`.

## What the class provides

- `source_type`: a short stable name, such as `filesystem`.
- `list_items()`: each item has a stable `id`, a `location` (path or URL), a `title`, a modified time, and a size.
- `read(locations)`: the text of those items. When the reader knows a page number, it stays on the result metadata (`page_label` or `page_number`).
- `deleted_ids(known_ids)`: ids Talkback already stored that are no longer listed.
- `ensure_writable(action)`: raise `ReadOnlyLibrary` for an upload or a delete the source cannot accept. The API turns that into the existing 403 responses.

`FilesystemSource` is the mounted folder. Item ids are relative paths. Dotfiles stay hidden. Read-only mode refuses upload and delete and still allows indexing.

## Chunk metadata

New chunks store `source_type` and `source_id` next to `relative_path`. `source_id` is the item id. Chunks indexed before this field existed have no `source_type` and stay searchable by `relative_path`. Adding the field must not be treated as an embedding-model change, and it must not force a full re-index.

Ingestion should call the source for the file list, the text, and the deletions. It should not grow a second copy of the folder walk.
