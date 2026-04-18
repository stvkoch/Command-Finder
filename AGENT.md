# AGENT.md — Command Finder (`cf`)

Quick-reference for any AI coding agent (Claude, Cursor, Aider, Copilot, etc.) operating on this repo. For the full writeup see `CLAUDE.md`.

## TL;DR

- `cf` turns a natural-language query into a shell command via vector search over pre-embedded "patterns".
- **Source of truth = `src/cf/data/commands/*.json`.** Edit JSON, then run `cf --seed --force`.
- Never hand-edit the SQLite database. It is regenerated from JSON.

## Architecture at a glance

```
User query
  → sentence-transformers (all-MiniLM-L6-v2, 384-dim) → query embedding
  → sqlite-vec vector search over pattern_embeddings
  → top-K patterns → join to commands → interactive selector
  → selected command → stdout / readline / clipboard / tmux
```

Key files:

| File | Role |
|------|------|
| `src/cf/cli.py` | Typer CLI. `cf`, `cf --seed`, `cf --print`, `cf --copy`, `cf --tmux`. |
| `src/cf/seed.py` | Reads all JSON → batch-inserts into SQLite + vec0. |
| `src/cf/db.py` | Schema, batch inserts, `search_similar()`, PRAGMA tuning. |
| `src/cf/embeddings.py` | sentence-transformers + ONNX wrapper. Cached encoding. |
| `src/cf/search.py` | Query encode + vector search + dedup. |
| `src/cf/selector.py` | `simple-term-menu` UI with "Show more". |
| `src/cf/data/commands/*.json` | Seed data. **This is what agents usually edit.** |
| `shell/cf.zsh` | `print -z` readline injection + `Ctrl+F` ZLE widget. |

## Database schema

```sql
commands(id, name, category, synopsis, description)
patterns(id, command_id FK, pattern_type, text, command_template, explanation)
pattern_embeddings  -- vec0 virtual table, PK pattern_id, FLOAT[384]
query_cache(query_text PK, embedding BLOB)
```

Dedup key: `(category, name)` — see `seed.py::cmd_seen`. Patterns attach to the deduped command.

## Seeding flow (`seed.py::seed_database`)

1. `load_seed_files()` → reads every `*.json` in `DATA_DIR`.
2. Flatten to `cmd_rows` + `pat_meta`, deduping by `(category, name)`.
3. `encode_batch([p.text for p in patterns])` — single batched embedding call.
4. `bulk_load_pragmas` → speed-tuned inserts:
   - `insert_commands_batch` → returns generated IDs.
   - `insert_patterns_batch(command_id=...)` → returns pattern IDs.
   - `insert_embeddings_batch(pattern_id, bytes)` into the vec0 table.
5. `restore_pragmas`, commit, close.

Re-running with `--force` is safe: embedding encoding is cached, so only new `pattern.text` strings cost CPU.

## Adding a command — minimal recipe

Find the right category file under `src/cf/data/commands/` (or create `<new-category>.json`). Append a command to the `commands` array:

```json
{
  "name": "fd",
  "synopsis": "fd [pattern] [path]",
  "description": "User-friendly alternative to find",
  "patterns": [
    {
      "type": "example",
      "text": "find files by name quickly",
      "command": "fd <pattern>",
      "explanation": "Recursively searches for files matching the pattern"
    },
    {
      "type": "example",
      "text": "search for files with a specific extension",
      "command": "fd -e <ext>",
      "explanation": "Filters results to files with the given extension"
    }
  ]
}
```

Then:

```bash
python -m json.tool src/cf/data/commands/<file>.json > /dev/null   # validate
cf --seed --force                                                  # rebuild DB
cf "<natural-language query for the new entry>"                    # smoke test
```

## Pattern-writing rules

- **`text`** is the embedded string. Write it as user intent ("compress a folder to tar.gz"), not man-page language.
- **`command`** is the injected shell command. Must be runnable, copy-pasteable, with placeholders (`<file>`, `/path/to/dir`) where concrete values would mislead.
- **More patterns per command = better recall.** Add 3–8 paraphrased `text` entries that share or vary the `command`.
- **Category uniqueness**: don't re-add a command that already lives in another category file.
- **`pattern_type`**: use `"example"` unless you are introducing a new type end-to-end.

## Things agents should NOT do

- Do not insert, update, or delete rows in `cf.db` directly. The DB is disposable.
- Do not commit `cf.db`, `.venv/`, or the ONNX model. `.gitignore` already excludes them.
- Do not change `EMBEDDING_DIM` without also changing the model — the vec0 column dimension is fixed at schema creation.
- Do not switch `seed.py` to per-row inserts; keep the batched Phase 1/2/3 structure.
- Do not add backwards-compat shims for renamed JSON fields. Update all files and reseed.
- Do not write comments explaining what code does; `CLAUDE.md` and this file are the documentation.

## Validation checklist after changes

- [ ] JSON files still parse (`python -m json.tool`).
- [ ] `cf --seed --force` runs cleanly and reports non-zero counts.
- [ ] `pytest` passes.
- [ ] A representative natural-language query returns the expected new entry in the top results.
- [ ] `README.md` coverage table reflects new categories/counts if materially changed.

## Environment

- Python 3.12+, macOS or Linux.
- Config via env vars: `CF_TOP`, `CF_MAX_TOP`, `CF_MODEL`, `CF_EMBEDDING_DIM`, `CF_DB_DIR`, `CF_DB_NAME`, `CF_DATA_DIR`.
- Default DB dir: `~/.local/share/cf/`.
- Default model: `all-MiniLM-L6-v2` (384-dim).
