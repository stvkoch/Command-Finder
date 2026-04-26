# CLAUDE.md — Command Finder (`cf`)

Guidance for Claude Code agents working in this repository. Read this before editing code or adding command entries.

## What this project is

`cf` is a natural-language shell command finder. A user types `cf "find large files older than 30 days"` and gets an interactive picker of real shell commands. The selected command is injected into the zsh readline buffer, copied to the clipboard, printed, or sent to tmux.

Under the hood:

1. `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim) encodes the query.
2. `sqlite-vec` performs cosine-distance vector search over indexed **patterns**.
3. `simple-term-menu` renders an interactive selector.
4. `shell/cf.zsh` pushes the chosen command onto the zsh edit buffer via `print -z`.

## Project layout

```
src/cf/
├── cli.py              # Typer entry point (cf ...)
├── config.py           # Env vars, paths, model name (CF_TOP, CF_MODEL, CF_DB_DIR, CF_DATA_DIR)
├── db.py               # SQLite + sqlite-vec schema and batch inserts
├── embeddings.py       # sentence-transformers / ONNX wrapper
├── search.py           # Vector search + dedup
├── seed.py             # Reads data/commands/*.json and populates the DB
├── selector.py         # Interactive terminal menu
├── output.py           # stdout / clipboard / tmux output handlers
└── data/commands/      # JSON seed files — the source of truth for commands
```

- DB lives at `$CF_DB_DIR/cf.db` (default `~/.local/share/cf/cf.db`).
- Seed JSON files live at `src/cf/data/commands/*.json` and ship with the package (`pyproject.toml` → `package-data`).

## How seeding works

`cf --seed` (or `cf --seed --force` to wipe first) runs `src/cf/seed.py → seed_database()`. It:

1. **Loads** every `*.json` under `DATA_DIR` via `load_seed_files()`.
2. **Flattens** them into three ordered lists:
   - `cmd_rows` — `(name, category, synopsis, description)`, deduped by `(category, name)`.
   - `pat_meta` — `(cmd_index, type, text, command_template, explanation)`.
3. **Encodes** every `pattern.text` in a single batch via `embeddings.encode_batch()` (cached — safe to re-run).
4. **Bulk-inserts** into SQLite using `bulk_load_pragmas` for speed, in this order:
   - `insert_commands_batch` → returns auto-generated `cmd_ids`.
   - `insert_patterns_batch` with resolved `command_id` → returns `pat_ids`.
   - `insert_embeddings_batch` into the `vec0` virtual table, keyed by `pattern_id`.
5. **Restores** safe PRAGMAs and commits.

### DB schema (`db.py::init_db`)

- `commands(id, name, category, synopsis, description)`
- `patterns(id, command_id FK, pattern_type, text, command_template, explanation)`
- `pattern_embeddings` — virtual `vec0(pattern_id PRIMARY KEY, embedding FLOAT[384])`
- `query_cache(query_text PK, embedding BLOB)` — memoizes encoded user queries.

Each **pattern** gets its own embedding. The search is pattern-level, not command-level — that's why good recall depends on writing multiple phrasings of the same task.

## Adding database entries (the common task for agents)

The database is **derived** from `src/cf/data/commands/*.json`. Never hand-insert rows into SQLite — edit the JSON and reseed.

### JSON file shape

One category per file. Filename should match the `category` field (e.g. `git.json` → `"category": "git"`).

```json
{
  "category": "git",
  "commands": [
    {
      "name": "git commit",
      "synopsis": "git commit [options]",
      "description": "Record changes to the repository",
      "patterns": [
        {
          "type": "example",
          "text": "commit staged changes with a message",
          "command": "git commit -m \"message\"",
          "explanation": "Records all staged changes with the given commit message"
        },
        {
          "type": "example",
          "text": "discard local changes and reset to upstream",
          "command": "git reset --hard origin/main",
          "explanation": "Drops all local commits and uncommitted changes",
          "destructive": true
        }
      ]
    }
  ]
}
```

### Field rules

- **`category`** — must match the surrounding file; used as the grouping key.
- **`name`** — canonical command name (`"git commit"`, `"tar"`, `"docker run"`). `(category, name)` is the dedup key in `seed.py`; duplicates collapse into one `commands` row but their patterns merge.
- **`synopsis`** — man-page style usage line. One line.
- **`description`** — one-sentence purpose. Shown in the selector preview.
- **`patterns[]`** — **this is what gets searched**. Each entry is one embedding.
  - **`type`** — currently always `"example"`. Keep it unless you have a reason.
  - **`text`** — natural-language description of *what the user wants to do*. Write how a user would phrase the task, not how the command works. This is the embedded string.
  - **`command`** — the exact shell command that will be injected into the user's prompt. Must be runnable; use placeholders like `<file>`, `/path/to/dir`, `name` where appropriate.
  - **`explanation`** — one-line explanation shown in the selector preview. Optional but recommended.
  - **`destructive`** — optional boolean (default `false`). Set `true` for commands that delete files, kill processes, rewrite git history, wipe volumes, or otherwise cause irreversible changes. The selector marks these with a ⚠ prefix and prompts a `yes`/N double-confirmation before injecting/copying the command. Examples: `rm -rf`, `kill -9`, `git push --force`, `git reset --hard`, `git clean -fd`, `find -delete`, `truncate`, `dd`, `docker rm -f`, `docker volume rm`, `docker system prune`. Don't mark non-destructive operations (read-only flags, `kill -HUP` reloads, `chmod` grants) — alarm fatigue defeats the prompt.

### Writing good patterns

- **Multiple phrasings per use case.** Users say "delete empty folders", "remove empty dirs", "clean up empty directories" — add all three as separate patterns with the same `command`. More patterns = better recall.
- **Phrase from the user's intent**, not the flag. ✅ "compress a directory into a tar.gz" — ❌ "tar -czf flag".
- **One command per pattern.** Don't chain pipelines unless that *is* the idiom (e.g. `ps aux | grep`).
- **Keep `command` copy-pasteable.** A user will press Enter on it. Prefer generic placeholders over real paths.
- **Don't duplicate across files.** If `grep` belongs to `text_processing`, don't re-add it under `search`.

### Workflow for adding entries

1. Decide the category — reuse an existing file when possible (`ls src/cf/data/commands/`). Only create a new file if the category is genuinely new, and name the file `<category>.json`.
2. Add the command object (or new patterns to an existing command) in JSON. Keep valid JSON — commas, quoting, escaped quotes inside `command`.
3. Validate: `python -m json.tool src/cf/data/commands/<file>.json > /dev/null`.
4. Rebuild the DB: `cf --seed --force` (wipes and repopulates; encoding is cached so re-runs are fast).
5. Smoke-test with a natural-language query: `cf "<what you'd type>"` and confirm the new command ranks well.
6. Update the coverage table in `README.md` if you added a new category or substantially changed counts.

### Common mistakes to avoid

- Adding a command whose `patterns[]` are just restatements of `name` — the embedding needs semantic variety to match real queries.
- Forgetting to reseed after editing JSON. The DB is not rebuilt automatically.
- Editing the SQLite DB directly — it will be overwritten on the next `--seed --force`.
- Creating a new JSON file without a matching `"category"` field. `seed.py` trusts the field, not the filename, but mismatches make the repo confusing.
- Adding backwards-compat shims for field renames. This schema is small — if you change a field, change it everywhere and reseed.

## Running / testing

```bash
# Install in editable mode
pip install -e .

# Seed
cf --seed --force

# Run
cf "find files modified in the last day"

# Tests
pytest
```

## Conventions for this repo

- Python 3.12+, type hints, `pathlib.Path` over `os.path`.
- Keep `seed.py` batch-oriented — do not re-introduce per-row inserts.
- Embeddings are cached; never bypass the cache with ad-hoc encode loops.
- The `vec0` virtual table dimension (`EMBEDDING_DIM`, default 384) must match the model. Don't change one without the other.
- Don't commit the generated DB, ONNX model, or `.venv`.
