```
      ___           ___
     /  /\         /  /\
    /  /:/        /  /:/_
   /  /:/        /  /:/ /\
  /  /:/  ___   /  /:/ /:/
 /__/:/  /  /\ /__/:/ /:/
 \  \:\ /  /:/ \  \:\/:/
  \  \:\  /:/   \  \::/
   \  \:\/:/     \  \:\
    \  \::/       \  \:\
     \__\/         \__\/

   ╔═══════════════════════════╗
   ║   c o m m a n d           ║
   ║          f i n d e r      ║
   ╚═══════════════════════════╝
```

# cf - Command Finder

Find shell commands using natural language. Type what you want to do, get the command.

```
$ cf find large files older than 30 days

  > find . -size +100M -mtime +30 -type f
    find / -size +100M -type f
    find . -mtime +30 -type f -delete

  [arrows: navigate] [enter: select] [q: cancel]
```
or

```
$ find large files older than 30 days # CTRL+f

  > find . -size +100M -mtime +30 -type f
    find / -size +100M -type f
    find . -mtime +30 -type f -delete

  [arrows: navigate] [enter: select] [q: cancel]
```


The selected command is injected directly into your shell prompt, ready to edit or run.

## Install

```bash
git clone <repo-url> ~/codes/cf
cd ~/codes/cf
./install.sh
```

The install script:
- Creates a Python virtual environment
- Installs dependencies (sentence-transformers, sqlite-vec, etc.)
- Seeds the database with 327 commands and 1,536 searchable patterns
- Downloads the embedding model (~80MB, one-time)
- Symlinks `cf` to `~/.local/bin/`
- Optionally adds shell integration to `~/.zshrc`

### Manual install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cf --seed
```

Then add to `~/.zshrc`:

```bash
source /path/to/cf/shell/cf.zsh
```

### Requirements

- Python 3.12+
- macOS or Linux
- ~200MB disk (model + dependencies)

## Usage

### Basic search

```bash
cf "compress a directory"
# Interactive selector appears, chosen command goes to your prompt
```

### Output modes

```bash
cf "query"                    # Default: inject into zsh readline buffer
cf --print "query"            # Print to stdout
cf --copy  "query"            # Copy to clipboard (pbcopy/xclip)
cf --tmux  "query"            # Send to current tmux pane
```

### Options

```
cf [OPTIONS] QUERY...

Options:
  --print, -p          Print command to stdout
  --copy, -c           Copy to clipboard
  --tmux, -t           Send to tmux pane via send-keys
  --top N              Number of results (default: 7, env: CF_TOP)
  --verbose, -v        Show similarity scores and DB stats
  --seed               Seed/rebuild the database and export ONNX model
  --seed --force       Clear and reseed from scratch
  --install-shell      Print zsh integration setup instructions
  --version            Show version
```

### Configuration

All settings can be configured via environment variables. Set them in `~/.zshrc` for permanent defaults:

| Environment variable | Default | Description |
|---------------------|---------|-------------|
| `CF_TOP` | `7` | Number of results to show |
| `CF_MAX_TOP` | `50` | Maximum results when using "Show more" |
| `CF_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers embedding model |
| `CF_EMBEDDING_DIM` | `384` | Embedding dimensions (must match model) |
| `CF_DB_DIR` | `~/.local/share/cf` | Database and cache directory |
| `CF_DB_NAME` | `cf.db` | Database filename |
| `CF_DATA_DIR` | *(package default)* | Path to seed JSON files |

```bash
# Example: show 15 results by default, use a different data dir
export CF_TOP=15
export CF_DB_DIR="$HOME/.cf"
```

The `--top` flag overrides `CF_TOP` for a single invocation.

### Navigating results

The selector shows `CF_TOP` results by default (7 if unset). Scroll to the bottom and select `[+] Show more results...` to load 10 more at a time (up to 50 max). Use `--top N` to change the count for a single run:

```bash
cf --top 15 "find files"     # Start with 15 results
```

### Keyboard shortcut

With shell integration enabled, press `Ctrl+F` anywhere in your terminal to open cf as a ZLE widget:

- **Text on the line**: type a query then press `Ctrl+F` -- it searches and replaces the line with the selected command
- **Empty prompt**: press `Ctrl+F` -- it shows a `cf>` prompt to type your query

### Shell integration setup

```bash
cf --install-shell           # Print setup instructions
```

Or add directly to `~/.zshrc`:

```bash
source /path/to/cf/shell/cf.zsh
```

This enables:
- `cf "query"` pushes the selected command into your prompt via `print -z`
- `Ctrl+F` opens the search widget inline as a ZLE widget

## How it works

```
 "find files larger than 1GB"
            |
            v
   ┌─────────────────┐
   │  Encode query    │  sentence-transformers
   │  (all-MiniLM)    │  384-dim embedding
   └────────┬────────┘
            │
   ┌────────v────────┐
   │  Vector search   │  sqlite-vec
   │  cosine distance │  ~1,909 indexed patterns
   └────────┬────────┘
            │
   ┌────────v────────┐
   │  Interactive     │  simple-term-menu
   │  selector        │  with preview
   └────────┬────────┘
            │
   ┌────────v────────┐
   │  Output          │  readline / clipboard
   │                  │  / tmux / stdout
   └──────────────────┘
```

Each shell command has multiple **patterns** indexed separately -- natural language descriptions like "find files larger than 100MB", "search for big files on disk", "locate large files". This means your query matches the *specific use case*, not just the command name.

## Command coverage

389 commands across 15 categories, 1,909 searchable patterns:

| Category | Commands | Patterns | Highlights |
|----------|----------|----------|------------|
| filesystem | 34 | 156 | ls, cp, mv, rm, find, rsync, du, df, ln, stat |
| text_processing | 34 | 136 | grep, sed, awk, cut, sort, uniq, diff, tr, wc |
| search | 14 | 71 | find, locate, fd, rg, fzf, xargs, parallel |
| networking | 33 | 143 | curl, wget, ssh, scp, ping, dig, netstat, nmap |
| system | 34 | 154 | uname, systemctl, journalctl, free, lscpu, env |
| process | 32 | 140 | ps, top, kill, tmux, crontab, strace, lsof |
| permissions | 21 | 96 | chmod, chown, sudo, useradd, passwd, setfacl |
| compression | 16 | 78 | tar, gzip, zip, xz, 7z, zstd, bzip2 |
| disk | 20 | 92 | fdisk, mkfs, mount, lsblk, smartctl, ncdu |
| git | 28 | 161 | init, clone, commit, branch, rebase, stash, bisect |
| docker | 22 | 102 | run, build, compose, exec, logs, kubectl |
| package_managers | 17 | 125 | apt, brew, pip, npm, **npx (45 patterns)**, cargo |
| perl_oneliners | 21 | 211 | substitution, regex, calculations, ROT13, CSV |
| macos | 19 | 58 | open, pbcopy, defaults, caffeinate, say |
| misc | 44 | 186 | jq, bc, alias, history, tput, bat, man, fzf |

## Shell integration

### How readline injection works

When you source `shell/cf.zsh`, two things are set up:

1. **`cf` function** -- wraps the Python CLI. Captures the selected command and pushes it onto the zsh edit buffer using `print -z`. The command appears on your next prompt line, ready to edit or press Enter.

2. **`cf-widget`** -- a ZLE widget bound to `Ctrl+F`. If you have text on the line, it uses that as the query. On an empty prompt, it shows a `cf>` input. The result is injected directly into `BUFFER` (the current command line).

Both use `</dev/tty` redirection so the interactive selector works correctly inside command substitution.

### Selector keybindings

Inside the interactive selector menu:

| Key | Action |
|-----|--------|
| `Up` / `k` | Move up |
| `Down` / `j` | Move down |
| `Enter` | Select command |
| `q` / `Esc` | Cancel |
| Select `[+] Show more...` | Load 10 more results |

### Customizing the shell keybinding

Edit `shell/cf.zsh` or add to your `.zshrc`:

```bash
bindkey '^K' cf-widget   # Ctrl+K instead of Ctrl+F
```

## Adding commands

Seed data lives in `src/cf/data/commands/*.json`. To add commands:

1. Edit or create a JSON file in that directory:

```json
{
  "category": "my_tools",
  "commands": [
    {
      "name": "mytool",
      "synopsis": "mytool [options] <arg>",
      "description": "What mytool does",
      "patterns": [
        {
          "type": "example",
          "text": "natural language description of this use case",
          "command": "mytool --flag value",
          "explanation": "brief explanation"
        }
      ]
    }
  ]
}
```

2. Rebuild the database:

```bash
cf --seed --force
```

### Tips for good patterns

- Write `text` as natural language -- how you'd describe the task, not the command
- Include multiple phrasings: "delete empty folders", "remove directories that are empty", "clean up empty dirs"
- Each pattern gets its own embedding, so more patterns = better recall
- The `command` field is what gets injected -- make it a real, runnable command

## Project structure

```
.
├── install.sh              # One-step installer
├── pyproject.toml          # Python package config
├── shell/
│   └── cf.zsh              # Zsh integration (source in .zshrc)
├── src/cf/
│   ├── cli.py              # Typer CLI entry point
│   ├── config.py           # Paths, model name, constants
│   ├── db.py               # SQLite + sqlite-vec layer
│   ├── embeddings.py       # sentence-transformers wrapper
│   ├── output.py           # Print / clipboard / tmux handlers
│   ├── search.py           # Vector search + dedup
│   ├── seed.py             # JSON loader + DB population
│   ├── selector.py         # Interactive terminal menu
│   └── data/commands/      # 13 JSON seed files
└── tests/
```

## License

MIT
