## Evolve without losing data

Read current files and the manifest with `spaces_read_files`. For ordered exact replacements
across files, use `spaces_edit_files` with the returned `rev` as `base_rev`.
The whole final candidate must pass diagnostics. It publishes one revision or none.
Errors include the zero-based `edit_index` and `path`. Binary content cannot be
edited as text. Use whole-file writes to replace assets.

Read the current files before a single-file change. Use `spaces_edit_file` for a unique exact
replacement. If it reports zero or multiple matches, read again and choose a
longer unique snippet. Use `spaces_write_files` for multiple whole-file changes.
Pass `base_rev` equal to the `head_rev` just read. A stale head is `conflict`.
Re-read before retrying. A file value of `null` deletes that file.

Keep the collection names and stored shape unless the feature needs a migration.
When changing shape, increment `data.version` and include declarative migrations
in `space.json`. Example for version 1 to 2:

```json
{"data":{"version":2,"collections":{"papers":{"description":"Library items"}},
"migrations":[{"to":2,"ops":[
  {"op":"rename_field","collection":"papers","from":"stat","to":"status"},
  {"op":"set_default","collection":"papers","field":"priority","value":"normal"}
]}]}}
```

Supported operations are `rename_field`, `set_default`, `delete_field`,
`rename_collection`, and `copy_collection`. The host creates a recovery point.
Preview destructive schema changes for user approval. Never reset collections
to make new code fit old data. Code and records have separate lifecycles.
