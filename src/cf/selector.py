import sys

from cf.search import SearchResult

# Sentinel returned when user picks "Show more"
SHOW_MORE = object()

DESTRUCTIVE_MARK = "⚠ "


def _confirm_destructive(r: SearchResult) -> bool:
    """Prompt y/N on /dev/tty before returning a destructive command."""
    msg = (
        f"\n⚠  DESTRUCTIVE COMMAND\n"
        f"   {r.command_template}\n"
        f"   This may delete files, kill processes, or rewrite history.\n"
        f"   Type 'yes' to confirm: "
    )
    try:
        with open("/dev/tty", "r+") as tty:
            tty.write(msg)
            tty.flush()
            answer = tty.readline().strip().lower()
    except OSError:
        # No tty — refuse rather than silently injecting
        print("Cannot read confirmation: no tty available.", file=sys.stderr)
        return False
    return answer == "yes"


def select_command(results: list[SearchResult], verbose: bool = False,
                   non_interactive: bool = False, has_more: bool = True) -> str | None:
    if not results:
        print("No matching commands found.", file=sys.stderr)
        return None

    # Non-interactive mode: return top result
    if non_interactive or not sys.stdin.isatty():
        return results[0].command_template

    try:
        from simple_term_menu import TerminalMenu
        return _select_with_menu(results, verbose, has_more)
    except (ImportError, OSError):
        # OSError when /dev/tty is not available
        return _select_with_input(results, verbose, has_more)


def _format_entry(r: SearchResult, verbose: bool) -> str:
    score = f" ({r.distance:.3f})" if verbose else ""
    mark = DESTRUCTIVE_MARK if r.destructive else ""
    return f"{mark}{r.command_template}  [{r.command_name}]{score}"


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
    if r.destructive:
        lines.extend(["", "⚠ DESTRUCTIVE: requires confirmation before injection"])
    return "\n".join(lines)


def _select_with_menu(results: list[SearchResult], verbose: bool,
                      has_more: bool) -> str | None:
    from simple_term_menu import TerminalMenu

    entries = [_format_entry(r, verbose) for r in results]
    if has_more:
        entries.append("[+] Show more results...")

    previews = {i: _format_preview(r) for i, r in enumerate(results)}

    def preview_func(index):
        if index is not None and index in previews:
            return previews[index]
        return ""

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
    # "Show more" is the last entry
    if has_more and chosen == len(results):
        return SHOW_MORE
    selected = results[chosen]
    if selected.destructive and not _confirm_destructive(selected):
        return None
    return selected.command_template


def _select_with_input(results: list[SearchResult], verbose: bool,
                       has_more: bool) -> str | None:
    """Fallback selector using basic input() when simple-term-menu is unavailable."""
    print("\nMatching commands:\n", file=sys.stderr)
    for i, r in enumerate(results, 1):
        score = f"  (distance: {r.distance:.3f})" if verbose else ""
        mark = DESTRUCTIVE_MARK if r.destructive else ""
        print(f"  {i}) {mark}{r.command_template}", file=sys.stderr)
        print(f"     {r.pattern_text} [{r.command_name}]{score}", file=sys.stderr)
        if r.explanation:
            print(f"     {r.explanation}", file=sys.stderr)
        print(file=sys.stderr)

    if has_more:
        print(f"  +) Show more results...", file=sys.stderr)
        print(file=sys.stderr)

    try:
        choice = input("Select [1-{}{}] (q to cancel): ".format(
            len(results), "/+" if has_more else ""))
    except (EOFError, KeyboardInterrupt):
        return None

    if choice.strip().lower() in ("q", ""):
        return None
    if has_more and choice.strip() == "+":
        return SHOW_MORE
    try:
        idx = int(choice.strip()) - 1
        if 0 <= idx < len(results):
            selected = results[idx]
            if selected.destructive and not _confirm_destructive(selected):
                return None
            return selected.command_template
    except ValueError:
        pass

    print("Invalid selection.", file=sys.stderr)
    return None
