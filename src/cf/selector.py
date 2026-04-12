import sys

from cf.search import SearchResult


def select_command(results: list[SearchResult], verbose: bool = False,
                   non_interactive: bool = False) -> str | None:
    if not results:
        print("No matching commands found.", file=sys.stderr)
        return None

    # Non-interactive mode: return top result
    if non_interactive or not sys.stdin.isatty():
        return results[0].command_template

    try:
        from simple_term_menu import TerminalMenu
        return _select_with_menu(results, verbose)
    except (ImportError, OSError):
        # OSError when /dev/tty is not available
        return _select_with_input(results, verbose)


def _format_entry(r: SearchResult, verbose: bool) -> str:
    score = f" ({r.distance:.3f})" if verbose else ""
    return f"{r.command_template}  [{r.command_name}]{score}"


def _format_preview(r: SearchResult) -> str:
    lines = [
        f"Command: {r.command_name}",
        f"Synopsis: {r.synopsis}",
        "",
        f"Pattern: {r.pattern_text}",
        f"Template: {r.command_template}",
    ]
    if r.explanation:
        lines.extend(["", f"Explanation: {r.explanation}"])
    return "\n".join(lines)


def _select_with_menu(results: list[SearchResult], verbose: bool) -> str | None:
    from simple_term_menu import TerminalMenu

    entries = [_format_entry(r, verbose) for r in results]
    previews = {i: _format_preview(r) for i, r in enumerate(results)}

    def preview_func(index):
        if index is not None and index in previews:
            return previews[index]
        return ""

    # Build preview command as a callable
    menu = TerminalMenu(
        entries,
        title="Select a command (press q to cancel):",
        preview_command=lambda idx: preview_func(
            entries.index(idx) if idx in entries else None
        ),
        preview_size=0.4,
    )
    chosen = menu.show()
    if chosen is None:
        return None
    return results[chosen].command_template


def _select_with_input(results: list[SearchResult], verbose: bool) -> str | None:
    """Fallback selector using basic input() when simple-term-menu is unavailable."""
    print("\nMatching commands:\n", file=sys.stderr)
    for i, r in enumerate(results, 1):
        score = f"  (distance: {r.distance:.3f})" if verbose else ""
        print(f"  {i}) {r.command_template}", file=sys.stderr)
        print(f"     {r.pattern_text} [{r.command_name}]{score}", file=sys.stderr)
        if r.explanation:
            print(f"     {r.explanation}", file=sys.stderr)
        print(file=sys.stderr)

    try:
        choice = input("Select [1-{}] (q to cancel): ".format(len(results)))
    except (EOFError, KeyboardInterrupt):
        return None

    if choice.strip().lower() in ("q", ""):
        return None
    try:
        idx = int(choice.strip()) - 1
        if 0 <= idx < len(results):
            return results[idx].command_template
    except ValueError:
        pass

    print("Invalid selection.", file=sys.stderr)
    return None
