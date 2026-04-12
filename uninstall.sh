#!/usr/bin/env bash
set -euo pipefail

# cf - Natural Language Shell Command Finder
# Uninstall script for macOS/Linux

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
SHELL_FILE="$SCRIPT_DIR/shell/cf.zsh"
ZSHRC="${ZDOTDIR:-$HOME}/.zshrc"
LINK_DIR="$HOME/.local/bin"
DATA_DIR="$HOME/.local/share/cf"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

info()  { echo -e "${CYAN}[info]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ok]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC}  $*"; }
skip()  { echo -e "${DIM}[skip]${NC}  $*"; }

echo -e "${BOLD}"
echo "  _____ ___ "
echo " / ____|  _|"
echo "| |    | |_  Command Finder"
echo "| |___ |  _| Uninstaller"
echo " \_____|_|"
echo -e "${NC}"

# ── Confirm ──────────────────────────────────────────────────
echo -e "  ${BOLD}This will remove:${NC}"
[ -d "$VENV_DIR" ]               && echo "    - Virtual environment  ($VENV_DIR)"
[ -L "$LINK_DIR/cf" ] || [ -f "$LINK_DIR/cf" ] && echo "    - Symlink              ($LINK_DIR/cf)"
[ -d "$DATA_DIR" ]               && echo "    - Database & cache     ($DATA_DIR)"
[ -f "$ZSHRC" ] && grep -qF "source $SHELL_FILE" "$ZSHRC" 2>/dev/null \
                                 && echo "    - Shell integration    ($ZSHRC entry)"
echo ""

read -rp "  Proceed with uninstall? [y/N] " answer
answer="${answer:-N}"

if [[ ! "$answer" =~ ^[Yy]$ ]]; then
    echo "  Cancelled."
    exit 0
fi

echo ""

# ── Remove symlink ───────────────────────────────────────────
if [ -L "$LINK_DIR/cf" ]; then
    # Verify it points to our venv before removing
    LINK_TARGET="$(readlink "$LINK_DIR/cf" 2>/dev/null || true)"
    if [[ "$LINK_TARGET" == *"$SCRIPT_DIR"* ]]; then
        rm "$LINK_DIR/cf"
        ok "Removed symlink $LINK_DIR/cf"
    else
        warn "Symlink $LINK_DIR/cf points elsewhere ($LINK_TARGET), skipping"
    fi
elif [ -f "$LINK_DIR/cf" ]; then
    warn "$LINK_DIR/cf is a file, not a symlink — skipping (remove manually if needed)"
else
    skip "No symlink at $LINK_DIR/cf"
fi

# ── Remove shell integration from .zshrc ─────────────────────
SHELL_SOURCE_LINE="source $SHELL_FILE"
SHELL_COMMENT="# cf - Natural Language Shell Command Finder"

if [ -f "$ZSHRC" ] && grep -qF "$SHELL_SOURCE_LINE" "$ZSHRC" 2>/dev/null; then
    # Create backup before modifying
    cp "$ZSHRC" "$ZSHRC.bak.cf"

    # Remove the source line and the comment line above it
    grep -vF "$SHELL_SOURCE_LINE" "$ZSHRC.bak.cf" | grep -vF "$SHELL_COMMENT" > "$ZSHRC"

    # Clean up trailing blank lines left behind
    sed -i '' -e :a -e '/^\n*$/{$d;N;ba' -e '}' "$ZSHRC" 2>/dev/null || true

    ok "Removed shell integration from $ZSHRC"
    info "Backup saved to $ZSHRC.bak.cf"
else
    skip "No shell integration found in $ZSHRC"
fi

# ── Remove database and cache ────────────────────────────────
if [ -d "$DATA_DIR" ]; then
    rm -rf "$DATA_DIR"
    ok "Removed database and cache ($DATA_DIR)"
else
    skip "No data directory at $DATA_DIR"
fi

# ── Remove virtual environment ───────────────────────────────
if [ -d "$VENV_DIR" ]; then
    rm -rf "$VENV_DIR"
    ok "Removed virtual environment ($VENV_DIR)"
else
    skip "No virtual environment at $VENV_DIR"
fi

# ── Done ─────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}Uninstall complete.${NC}"
echo ""
echo "  The project source code is still at:"
echo "    $SCRIPT_DIR"
echo ""
echo "  To reinstall:  ./install.sh"
echo "  To fully remove:  rm -rf $SCRIPT_DIR"
echo ""
