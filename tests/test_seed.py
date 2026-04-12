"""Tests for cf.seed module — seed file loading and database population."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from cf.config import EMBEDDING_DIM
from cf.seed import load_seed_files


class TestLoadSeedFiles:
    def test_loads_json_files(self, seed_json_file):
        result = load_seed_files(seed_json_file)
        assert len(result) == 1
        assert result[0]["category"] == "test"

    def test_returns_empty_for_missing_dir(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = load_seed_files(empty_dir)
        assert result == []

    def test_loads_multiple_files(self, tmp_path):
        data_dir = tmp_path / "commands"
        data_dir.mkdir()
        for name in ("a.json", "b.json"):
            with open(data_dir / name, "w") as f:
                json.dump({
                    "category": name.split(".")[0],
                    "commands": [{
                        "name": "test",
                        "synopsis": "test",
                        "description": "test",
                        "patterns": [],
                    }],
                }, f)
        result = load_seed_files(data_dir)
        assert len(result) == 2

    def test_preserves_command_structure(self, seed_json_file):
        result = load_seed_files(seed_json_file)
        cmds = result[0]["commands"]
        assert len(cmds) == 2
        assert cmds[0]["name"] == "ls"
        assert len(cmds[0]["patterns"]) == 2


class TestSeedDatabase:
    @patch("cf.seed.encode_batch")
    @patch("cf.seed.load_seed_files")
    def test_seed_inserts_correct_counts(self, mock_load, mock_encode, tmp_db, sample_seed_data):
        db_path, conn = tmp_db
        conn.close()

        mock_load.return_value = [sample_seed_data]
        mock_encode.return_value = np.random.randn(3, EMBEDDING_DIM).astype(np.float32)

        from cf.seed import seed_database
        stats = seed_database(db_path=db_path)

        assert stats["commands"] == 2
        assert stats["patterns"] == 3

    @patch("cf.seed.encode_batch")
    @patch("cf.seed.load_seed_files")
    def test_force_clears_before_insert(self, mock_load, mock_encode, tmp_db, sample_seed_data):
        db_path, conn = tmp_db
        from cf.db import insert_commands_batch
        insert_commands_batch(conn, [("old", "cat", "old", "Old command")])
        conn.commit()
        conn.close()

        mock_load.return_value = [sample_seed_data]
        mock_encode.return_value = np.random.randn(3, EMBEDDING_DIM).astype(np.float32)

        from cf.seed import seed_database
        stats = seed_database(db_path=db_path, force=True)

        assert stats["commands"] == 2

    @patch("cf.seed.load_seed_files", return_value=[])
    def test_returns_zeros_when_no_seed_files(self, mock_load, tmp_db):
        db_path, conn = tmp_db
        conn.close()

        from cf.seed import seed_database
        stats = seed_database(db_path=db_path)
        assert stats == {"commands": 0, "patterns": 0}

    @patch("cf.seed.encode_batch")
    @patch("cf.seed.load_seed_files")
    def test_deduplicates_commands_by_category_and_name(self, mock_load, mock_encode, tmp_path):
        data = {
            "category": "fs",
            "commands": [
                {
                    "name": "ls",
                    "synopsis": "ls",
                    "description": "List",
                    "patterns": [
                        {"type": "ex", "text": "pat1", "command": "ls -la"},
                    ],
                },
                {
                    "name": "ls",
                    "synopsis": "ls",
                    "description": "List",
                    "patterns": [
                        {"type": "ex", "text": "pat2", "command": "ls -a"},
                    ],
                },
            ],
        }

        mock_load.return_value = [data]
        mock_encode.return_value = np.random.randn(2, EMBEDDING_DIM).astype(np.float32)

        db_path = tmp_path / "test.db"
        from cf.seed import seed_database
        stats = seed_database(db_path=db_path)

        assert stats["commands"] == 1
        assert stats["patterns"] == 2
