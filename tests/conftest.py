"""Shared fixtures for cf test suite."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from cf.config import EMBEDDING_DIM
from cf.search import SearchResult


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite database with sqlite-vec loaded and schema initialized."""
    db_path = tmp_path / "test.db"
    from cf.db import get_connection, init_db

    conn = get_connection(db_path)
    init_db(conn)
    yield db_path, conn
    conn.close()


@pytest.fixture
def random_embedding():
    """Generate a random L2-normalized embedding vector."""
    def _make(seed=42):
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(EMBEDDING_DIM).astype(np.float32)
        vec /= np.linalg.norm(vec)
        return vec
    return _make


@pytest.fixture
def embedding_bytes(random_embedding):
    """Generate random embedding as bytes ready for sqlite-vec."""
    def _make(seed=42):
        vec = random_embedding(seed)
        return np.ascontiguousarray(vec, dtype=np.float32).tobytes()
    return _make


@pytest.fixture
def sample_seed_data():
    """Minimal seed data matching the JSON schema used by load_seed_files."""
    return {
        "category": "test",
        "commands": [
            {
                "name": "ls",
                "synopsis": "ls [options] [file...]",
                "description": "List directory contents",
                "patterns": [
                    {
                        "type": "example",
                        "text": "list files in a directory",
                        "command": "ls -la",
                        "explanation": "Show all files with details",
                    },
                    {
                        "type": "example",
                        "text": "show hidden files",
                        "command": "ls -a",
                        "explanation": "Include dotfiles",
                    },
                ],
            },
            {
                "name": "pwd",
                "synopsis": "pwd",
                "description": "Print working directory",
                "patterns": [
                    {
                        "type": "example",
                        "text": "print current directory",
                        "command": "pwd",
                        "explanation": None,
                    },
                ],
            },
        ],
    }


@pytest.fixture
def seed_json_file(tmp_path, sample_seed_data):
    """Write sample seed data to a temp JSON file and return the directory."""
    data_dir = tmp_path / "commands"
    data_dir.mkdir()
    with open(data_dir / "test.json", "w") as f:
        json.dump(sample_seed_data, f)
    return data_dir


@pytest.fixture
def populated_db(tmp_db, random_embedding):
    """A temporary DB pre-populated with a few commands, patterns, and embeddings."""
    db_path, conn = tmp_db
    from cf.db import insert_commands_batch, insert_embeddings_batch, insert_patterns_batch
    from cf.embeddings import to_bytes

    cmd_ids = insert_commands_batch(conn, [
        ("ls", "filesystem", "ls [options]", "List directory contents"),
        ("grep", "search", "grep [options] pattern [file]", "Search text patterns"),
    ])

    pat_rows = [
        (cmd_ids[0], "example", "list files in a directory", "ls -la", "Show details", 0),
        (cmd_ids[0], "example", "show hidden files", "ls -a", "Include dotfiles", 0),
        (cmd_ids[1], "example", "search for text in files", "grep -r 'pattern' .", "Recursive search", 0),
    ]
    pat_ids = insert_patterns_batch(conn, pat_rows)

    emb_rows = [
        (pat_ids[i], to_bytes(random_embedding(seed=i)))
        for i in range(len(pat_ids))
    ]
    insert_embeddings_batch(conn, emb_rows)
    conn.commit()

    yield db_path, conn


@pytest.fixture
def sample_results():
    """A list of SearchResult objects for selector/output tests."""
    return [
        SearchResult(
            command_template="ls -la",
            pattern_text="list files in a directory",
            explanation="Show all files with details",
            command_name="ls",
            command_description="List directory contents",
            synopsis="ls [options] [file...]",
            distance=0.123,
        ),
        SearchResult(
            command_template="ls -a",
            pattern_text="show hidden files",
            explanation="Include dotfiles",
            command_name="ls",
            command_description="List directory contents",
            synopsis="ls [options] [file...]",
            distance=0.456,
        ),
        SearchResult(
            command_template="find . -name '*.txt'",
            pattern_text="find text files",
            explanation=None,
            command_name="find",
            command_description="Search for files in a directory hierarchy",
            synopsis="find [path] [expression]",
            distance=0.789,
        ),
    ]
