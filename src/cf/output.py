import os
import subprocess
import sys


def output_print(command: str) -> None:
    print(command)


def output_clipboard(command: str) -> None:
    try:
        subprocess.run(["pbcopy"], input=command.encode(), check=True)
        print(f"Copied to clipboard: {command}", file=sys.stderr)
    except FileNotFoundError:
        # Fallback for Linux
        try:
            subprocess.run(["xclip", "-selection", "clipboard"],
                           input=command.encode(), check=True)
            print(f"Copied to clipboard: {command}", file=sys.stderr)
        except FileNotFoundError:
            print("No clipboard tool found (pbcopy/xclip). Printing instead:", file=sys.stderr)
            print(command)


def output_tmux(command: str) -> None:
    pane = os.environ.get("TMUX_PANE")
    if not pane:
        print("Not in a tmux session. Printing instead:", file=sys.stderr)
        print(command)
        return
    subprocess.run(["tmux", "send-keys", "-t", pane, "-l", command], check=True)
    print(f"Sent to tmux pane: {command}", file=sys.stderr)
