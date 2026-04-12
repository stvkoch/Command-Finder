import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

from cf import __version__

app = typer.Typer(
    name="cf",
    help="Find bash commands using natural language.",
    add_completion=False,
    no_args_is_help=True,
)


def version_callback(value: bool):
    if value:
        print(f"cf {__version__}")
        raise typer.Exit()


@app.command()
def main(
    query: Annotated[Optional[list[str]], typer.Argument(help="Natural language query")] = None,
    print_mode: Annotated[bool, typer.Option("--print", "-p", help="Print command to stdout")] = False,
    copy: Annotated[bool, typer.Option("--copy", "-c", help="Copy command to clipboard")] = False,
    tmux: Annotated[bool, typer.Option("--tmux", "-t", help="Send command to tmux pane")] = False,
    top: Annotated[int, typer.Option("--top", help="Number of results to show")] = 7,
    seed: Annotated[bool, typer.Option("--seed", help="Seed/rebuild the database")] = False,
    force: Annotated[bool, typer.Option("--force", help="Force reseed (clear existing data)")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show similarity scores")] = False,
    install_shell: Annotated[bool, typer.Option("--install-shell", help="Show shell integration instructions")] = False,
    version: Annotated[bool, typer.Option("--version", callback=version_callback, is_eager=True, help="Show version")] = False,
):
    """Find bash commands using natural language."""
    if install_shell:
        _print_shell_instructions()
        raise typer.Exit()

    if seed:
        _do_seed(force)
        raise typer.Exit()

    if not query:
        typer.echo("Please provide a search query. Example: cf 'find large files'", err=True)
        raise typer.Exit(1)

    query_str = " ".join(query)

    # Check if DB exists and has data
    from cf.config import DB_PATH
    if not DB_PATH.exists():
        typer.echo("Database not found. Run 'cf --seed' first to populate the command database.", err=True)
        raise typer.Exit(1)

    from cf.db import get_connection, get_stats, init_db
    conn = get_connection()
    init_db(conn)
    stats = get_stats(conn)
    conn.close()

    if stats["patterns"] == 0:
        typer.echo("Database is empty. Run 'cf --seed' to populate.", err=True)
        raise typer.Exit(1)

    if verbose:
        typer.echo(f"DB: {stats['commands']} commands, {stats['patterns']} patterns", err=True)
        typer.echo(f"Query: {query_str}", err=True)

    from cf.search import search
    results = search(query_str, top_k=top)

    if not results:
        typer.echo("No matching commands found.", err=True)
        raise typer.Exit(1)

    from cf.selector import select_command
    selected = select_command(results, verbose=verbose)

    if not selected:
        raise typer.Exit(0)

    from cf.output import output_clipboard, output_print, output_tmux

    if copy:
        output_clipboard(selected)
    elif tmux:
        output_tmux(selected)
    else:
        # Default: print to stdout (shell wrapper handles readline injection)
        output_print(selected)


def _do_seed(force: bool):
    typer.echo("Seeding command database...", err=True)
    from cf.seed import seed_database
    stats = seed_database(force=force)
    typer.echo(f"Database ready: {stats['commands']} commands, {stats['patterns']} patterns.", err=True)


def _print_shell_instructions():
    # Locate shell/ dir relative to the cf package source
    shell_dir = Path(__file__).resolve().parent.parent.parent / "shell"

    print(f"# cf - Shell Integration")
    print(f"# Add the following to your ~/.zshrc:")
    print(f"")
    print(f"# Option 1: Source the cf.zsh file directly")
    print(f"source {shell_dir}/cf.zsh")
    print(f"")
    print(f"# Option 2: Manual setup - paste this into ~/.zshrc:")
    print(SHELL_SNIPPET)


SHELL_SNIPPET = r"""
cf() {
    local result
    result=$(command cf --print "$@" </dev/tty 2>/dev/tty)
    if [[ -n "$result" ]]; then
        print -z "$result"
    fi
}

cf-widget() {
    local result
    result=$(command cf --print "$@" </dev/tty 2>/dev/tty)
    if [[ -n "$result" ]]; then
        BUFFER="$result"
        CURSOR=$#BUFFER
        zle reset-prompt
    fi
}
zle -N cf-widget
bindkey '^K' cf-widget

# Then restart your shell or run: source ~/.zshrc
"""
