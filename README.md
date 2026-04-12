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
$ cf "find large files older than 30 days"

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
  --top N              Number of results (default: 7)
  --verbose, -v        Show similarity scores and DB stats
  --seed               Seed/rebuild the database
  --seed --force       Clear and reseed from scratch
  --install-shell      Print zsh integration setup
  --version            Show version
```

### Keyboard shortcut

With shell integration enabled, press `Ctrl+K` anywhere in your terminal to open cf as a ZLE widget. The result is placed directly in your command line.

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
   │  cosine distance │  ~1,536 indexed patterns
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

327 commands across 13 categories:

| Category | Commands | Patterns |
|----------|----------|----------|
| filesystem | 30 | 149 |
| text_processing | 27 | 118 |
| search | 14 | 68 |
| networking | 28 | 130 |
| system | 34 | 154 |
| process | 29 | 135 |
| permissions | 21 | 96 |
| compression | 16 | 78 |
| disk | 20 | 92 |
| git | 28 | 161 |
| docker | 22 | 102 |
| package_managers | 17 | 79 |
| misc | 41 | 174 |

## Shell integration

### How readline injection works

When you source `shell/cf.zsh`, two things are set up:

1. **`cf` function** -- wraps the Python CLI. Captures the selected command and pushes it onto the zsh edit buffer using `print -z`. The command appears on your next prompt line, ready to edit or press Enter.

2. **`cf-widget`** -- a ZLE widget bound to `Ctrl+K`. When triggered, it opens the search UI and injects the result directly into `BUFFER` (the current command line).

Both use `</dev/tty` redirection so the interactive selector works correctly inside command substitution.

### Customizing the keybinding

Edit `shell/cf.zsh` or add to your `.zshrc`:

```bash
bindkey '^F' cf-widget   # Ctrl+F instead of Ctrl+K
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
