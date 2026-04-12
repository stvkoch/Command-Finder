"""Tests for cf.cli module — CLI integration via typer.testing."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cf import __version__
from cf.cli import app

runner = CliRunner()


class TestVersionFlag:
    def test_shows_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output


class TestNoArgs:
    def test_shows_help_or_error_with_no_args(self):
        result = runner.invoke(app, [])
        assert "cf" in result.output.lower() or "Usage" in result.output


class TestInstallShell:
    def test_prints_shell_instructions(self):
        result = runner.invoke(app, ["--install-shell"])
        assert result.exit_code == 0
        assert "cf" in result.output
        assert "zshrc" in result.output.lower() or "source" in result.output.lower()


class TestSeedCommand:
    @patch("cf.cli._do_seed")
    def test_seed_calls_do_seed(self, mock_seed):
        result = runner.invoke(app, ["--seed"])
        assert result.exit_code == 0
        mock_seed.assert_called_once_with(False)

    @patch("cf.cli._do_seed")
    def test_seed_force(self, mock_seed):
        result = runner.invoke(app, ["--seed", "--force"])
        assert result.exit_code == 0
        mock_seed.assert_called_once_with(True)


class TestQueryWithoutDB:
    @patch("cf.config.DB_PATH")
    def test_errors_when_no_db(self, mock_path):
        mock_path.exists.return_value = False
        result = runner.invoke(app, ["find large files"])
        assert result.exit_code == 1
        assert "Database not found" in result.output or "seed" in result.output.lower()


class TestQueryFlow:
    @patch("cf.output.output_print")
    @patch("cf.selector.select_command", return_value="ls -la")
    @patch("cf.search.search")
    @patch("cf.db.get_stats", return_value={"commands": 10, "patterns": 50})
    @patch("cf.db.init_db")
    @patch("cf.db.get_connection")
    @patch("cf.config.DB_PATH")
    def test_full_search_flow_print(
        self, mock_path, mock_conn, mock_init, mock_stats, mock_search, mock_select, mock_print
    ):
        mock_path.exists.return_value = True
        mock_connection = MagicMock()
        mock_conn.return_value = mock_connection

        from cf.search import SearchResult
        mock_search.return_value = [
            SearchResult("ls -la", "list files", "detail", "ls", "List", "ls [opts]", 0.1)
        ]

        result = runner.invoke(app, ["list", "files"])
        assert result.exit_code == 0
        mock_print.assert_called_once_with("ls -la")

    @patch("cf.selector.select_command", return_value=None)
    @patch("cf.search.search")
    @patch("cf.db.get_stats", return_value={"commands": 10, "patterns": 50})
    @patch("cf.db.init_db")
    @patch("cf.db.get_connection")
    @patch("cf.config.DB_PATH")
    def test_no_selection_exits_clean(
        self, mock_path, mock_conn, mock_init, mock_stats, mock_search, mock_select
    ):
        mock_path.exists.return_value = True
        mock_conn.return_value = MagicMock()

        from cf.search import SearchResult
        mock_search.return_value = [
            SearchResult("ls -la", "list files", None, "ls", "List", "ls", 0.1)
        ]

        result = runner.invoke(app, ["list", "files"])
        assert result.exit_code == 0

    @patch("cf.search.search", return_value=[])
    @patch("cf.db.get_stats", return_value={"commands": 10, "patterns": 50})
    @patch("cf.db.init_db")
    @patch("cf.db.get_connection")
    @patch("cf.config.DB_PATH")
    def test_no_results_exits_with_error(
        self, mock_path, mock_conn, mock_init, mock_stats, mock_search
    ):
        mock_path.exists.return_value = True
        mock_conn.return_value = MagicMock()

        result = runner.invoke(app, ["gibberish xyz"])
        assert result.exit_code == 1

    @patch("cf.db.get_stats", return_value={"commands": 0, "patterns": 0})
    @patch("cf.db.init_db")
    @patch("cf.db.get_connection")
    @patch("cf.config.DB_PATH")
    def test_empty_db_prompts_seed(
        self, mock_path, mock_conn, mock_init, mock_stats
    ):
        mock_path.exists.return_value = True
        mock_conn.return_value = MagicMock()

        result = runner.invoke(app, ["find files"])
        assert result.exit_code == 1
        assert "empty" in result.output.lower() or "seed" in result.output.lower()


class TestOutputModes:
    @patch("cf.output.output_clipboard")
    @patch("cf.selector.select_command", return_value="git status")
    @patch("cf.search.search")
    @patch("cf.db.get_stats", return_value={"commands": 10, "patterns": 50})
    @patch("cf.db.init_db")
    @patch("cf.db.get_connection")
    @patch("cf.config.DB_PATH")
    def test_copy_mode(
        self, mock_path, mock_conn, mock_init, mock_stats, mock_search, mock_select, mock_clip
    ):
        mock_path.exists.return_value = True
        mock_conn.return_value = MagicMock()

        from cf.search import SearchResult
        mock_search.return_value = [
            SearchResult("git status", "check git", None, "git", "Git", "git", 0.1)
        ]

        result = runner.invoke(app, ["--copy", "check", "git"])
        mock_clip.assert_called_once_with("git status")

    @patch("cf.output.output_tmux")
    @patch("cf.selector.select_command", return_value="docker ps")
    @patch("cf.search.search")
    @patch("cf.db.get_stats", return_value={"commands": 10, "patterns": 50})
    @patch("cf.db.init_db")
    @patch("cf.db.get_connection")
    @patch("cf.config.DB_PATH")
    def test_tmux_mode(
        self, mock_path, mock_conn, mock_init, mock_stats, mock_search, mock_select, mock_tmux
    ):
        mock_path.exists.return_value = True
        mock_conn.return_value = MagicMock()

        from cf.search import SearchResult
        mock_search.return_value = [
            SearchResult("docker ps", "list containers", None, "docker", "Docker", "docker", 0.1)
        ]

        result = runner.invoke(app, ["--tmux", "list", "containers"])
        mock_tmux.assert_called_once_with("docker ps")
