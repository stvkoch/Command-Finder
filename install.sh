#!/usr/bin/env bash
set -euo pipefail

# cf - Natural Language Shell Command Finder
# Install script for macOS/Linux

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
SHELL_FILE="$SCRIPT_DIR/shell/cf.zsh"
ZSHRC="${ZDOTDIR:-$HOME}/.zshrc"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${CYAN}[info]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ok]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC}  $*"; }
error() { echo -e "${RED}[error]${NC} $*"; exit 1; }

echo -e "${BOLD}"
echo "  _____ ___ "
echo " / ____|  _|"
echo "| |    | |_  Command Finder"
echo "| |___ |  _| v0.1.0"
echo " \_____|_|   Natural language shell search"
echo -e "${NC}"

# ── Check Python ──────────────────────────────────────────────
info "Checking Python..."
if command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PYTHON="python"
else
    error "Python 3.12+ is required but not found. Install it first."
fi

PY_VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$($PYTHON -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$($PYTHON -c 'import sys; print(sys.version_info.minor)')

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 12 ]; }; then
    error "Python 3.12+ is required (found $PY_VERSION)"
fi
ok "Python $PY_VERSION"

# ── Create virtual environment ────────────────────────────────
if [ -d "$VENV_DIR" ]; then
    info "Virtual environment already exists at $VENV_DIR"
else
    info "Creating virtual environment..."
    $PYTHON -m venv "$VENV_DIR"
    ok "Created $VENV_DIR"
fi

# ── Install package ──────────────────────────────────────────
info "Installing cf and dependencies (this may take a minute)..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -e "$SCRIPT_DIR"
ok "Installed cf $(\"$VENV_DIR/bin/cf\" --version 2>/dev/null || echo '0.1.0')"

# ── Seed database ────────────────────────────────────────────
info "Seeding command database..."
"$VENV_DIR/bin/cf" --seed 2>&1 | grep -E "^(Done|Database)" || true
ok "Database ready"

# ── Symlink to PATH ──────────────────────────────────────────
LINK_DIR="$HOME/.local/bin"
mkdir -p "$LINK_DIR"

if [ -L "$LINK_DIR/cf" ] || [ -f "$LINK_DIR/cf" ]; then
    rm "$LINK_DIR/cf"
fi
ln -s "$VENV_DIR/bin/cf" "$LINK_DIR/cf"
ok "Linked cf -> $LINK_DIR/cf"

# Check if ~/.local/bin is in PATH
if ! echo "$PATH" | tr ':' '\n' | grep -q "$LINK_DIR"; then
    warn "$LINK_DIR is not in your PATH"
    echo "     Add this to your shell profile:"
    echo "       export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# ── Shell integration ────────────────────────────────────────
echo ""
info "Setting up shell integration..."

SHELL_SOURCE_LINE="source $SHELL_FILE"

if [ -f "$ZSHRC" ] && grep -qF "$SHELL_SOURCE_LINE" "$ZSHRC"; then
    ok "Shell integration already in $ZSHRC"
else
    echo ""
    echo -e "  ${BOLD}Shell integration enables:${NC}"
    echo "    - cf \"query\" pushes the command into your prompt (print -z)"
    echo "    - Ctrl+K opens cf search as a ZLE widget"
    echo ""
    read -rp "  Add shell integration to $ZSHRC? [Y/n] " answer
    answer="${answer:-Y}"

    if [[ "$answer" =~ ^[Yy]$ ]]; then
        echo "" >> "$ZSHRC"
        echo "# cf - Natural Language Shell Command Finder" >> "$ZSHRC"
        echo "$SHELL_SOURCE_LINE" >> "$ZSHRC"
        ok "Added to $ZSHRC"
        warn "Run 'source ~/.zshrc' or restart your terminal to activate"
    else
        info "Skipped. You can add it manually later:"
        echo "       $SHELL_SOURCE_LINE"
    fi
fi

# ── Done ──────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}Installation complete!${NC}"
echo ""
echo "  Usage:"
echo "    cf \"find large files\"              # interactive selector -> readline"
echo "    cf --copy \"compress a folder\"       # copy to clipboard"
echo "    cf --print \"undo git commit\"        # print to stdout"
echo "    cf --tmux \"list processes\"          # send to tmux pane"
echo "    cf --verbose \"disk usage\"           # show similarity scores"
echo "    cf --seed --force                   # rebuild the database"
echo ""
echo "  Keybinding:"
echo "    Ctrl+K                              # open cf search widget"
echo ""
