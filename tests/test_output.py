"""Tests for cf.output module — print, clipboard, tmux output sinks."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from cf.output import output_clipboard, output_print, output_tmux


class TestOutputPrint:
    def test_prints_command(self, capsys):
        output_print("ls -la")
        captured = capsys.readouterr()
        assert captured.out.strip() == "ls -la"


class TestOutputClipboard:
    @patch("subprocess.run")
    def test_uses_pbcopy_on_macos(self, mock_run):
        output_clipboard("git status")
        mock_run.assert_called_once_with(
            ["pbcopy"], input=b"git status", check=True
        )

    @patch("subprocess.run", side_effect=[FileNotFoundError, MagicMock()])
    def test_falls_back_to_xclip(self, mock_run):
        output_clipboard("git status")
        assert mock_run.call_count == 2
        second_call = mock_run.call_args_list[1]
        assert second_call[0][0] == ["xclip", "-selection", "clipboard"]

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_prints_when_no_clipboard_tool(self, mock_run, capsys):
        output_clipboard("git status")
        captured = capsys.readouterr()
        assert "git status" in captured.out


class TestOutputTmux:
    @patch.dict("os.environ", {"TMUX_PANE": "%1"})
    @patch("subprocess.run")
    def test_sends_to_tmux_pane(self, mock_run):
        output_tmux("docker ps")
        mock_run.assert_called_once_with(
            ["tmux", "send-keys", "-t", "%1", "-l", "docker ps"], check=True
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_prints_when_not_in_tmux(self, capsys):
        output_tmux("docker ps")
        captured = capsys.readouterr()
        assert "docker ps" in captured.out
