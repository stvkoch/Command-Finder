"""Tests for cf.db module — schema, CRUD, caching, and vector search."""

import sqlite3

import numpy as np
import pytest

from cf.config import EMBEDDING_DIM
from cf.db import (
    bulk_load_pragmas,
    cache_query,
    clear_all,
    get_cached_query,
    get_connection,
    get_stats,
    init_db,
    insert_commands_batch,
    insert_embeddings_batch,
    insert_patterns_batch,
    restore_pragmas,
    search_similar,
)
from cf.embeddings import to_bytes


class TestGetConnection:
    def test_returns_sqlite_connection(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = get_connection(db_path)
        assert isinstance(conn, sqlite3.Connection)
        conn.close()

    def test_creates_parent_directories(self, tmp_path):
        db_path = tmp_path / "nested" / "dirs" / "test.db"
        conn = get_connection(db_path)
        assert db_path.parent.exists()
        conn.close()

    def test_wal_mode_enabled(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = get_connection(db_path)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        conn.close()

    def test_foreign_keys_enabled(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = get_connection(db_path)
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        conn.close()

    def test_sqlite_vec_loaded(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = get_connection(db_path)
        result = conn.execute("SELECT vec_version()").fetchone()
        assert result is not None
        conn.close()


class TestInitDb:
    def test_creates_commands_table(self, tmp_db):
        _, conn = tmp_db
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='commands'"
        ).fetchone()
        assert row is not None

    def test_creates_patterns_table(self, tmp_db):
        _, conn = tmp_db
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='patterns'"
        ).fetchone()
        assert row is not None

    def test_creates_query_cache_table(self, tmp_db):
        _, conn = tmp_db
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='query_cache'"
        ).fetchone()
        assert row is not None

    def test_creates_pattern_embeddings_virtual_table(self, tmp_db):
        _, conn = tmp_db
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pattern_embeddings'"
        ).fetchone()
        assert row is not None

    def test_idempotent(self, tmp_db):
        _, conn = tmp_db
        init_db(conn)
        init_db(conn)
        row = conn.execute("SELECT COUNT(*) FROM commands").fetchone()
        assert row[0] == 0


class TestInsertCommandsBatch:
    def test_returns_correct_ids(self, tmp_db):
        _, conn = tmp_db
        ids = insert_commands_batch(conn, [
            ("ls", "filesystem", "ls [opts]", "List files"),
            ("cd", "filesystem", "cd [dir]", "Change directory"),
        ])
        assert len(ids) == 2
        assert ids[1] == ids[0] + 1

    def test_data_persisted(self, tmp_db):
        _, conn = tmp_db
        insert_commands_batch(conn, [
            ("grep", "search", "grep [opts] pat", "Search patterns"),
        ])
        conn.commit()
        row = conn.execute("SELECT name, category FROM commands WHERE name='grep'").fetchone()
        assert row == ("grep", "search")


class TestInsertPatternsBatch:
    def test_returns_correct_ids(self, tmp_db):
        _, conn = tmp_db
        cmd_ids = insert_commands_batch(conn, [
            ("ls", "fs", "ls", "List"),
        ])
        pat_ids = insert_patterns_batch(conn, [
            (cmd_ids[0], "example", "list files", "ls -la", "Show details", 0),
            (cmd_ids[0], "example", "hidden files", "ls -a", None, 0),
        ])
        assert len(pat_ids) == 2
        assert pat_ids[1] == pat_ids[0] + 1

    def test_foreign_key_constraint(self, tmp_db):
        _, conn = tmp_db
        with pytest.raises(sqlite3.IntegrityError):
            insert_patterns_batch(conn, [
                (9999, "example", "text", "template", None, 0),
            ])


class TestInsertEmbeddingsBatch:
    def test_inserts_embeddings(self, tmp_db, random_embedding):
        _, conn = tmp_db
        cmd_ids = insert_commands_batch(conn, [("ls", "fs", "ls", "List")])
        pat_ids = insert_patterns_batch(conn, [
            (cmd_ids[0], "example", "list files", "ls -la", None, 0),
        ])
        emb = random_embedding(seed=0)
        insert_embeddings_batch(conn, [(pat_ids[0], to_bytes(emb))])
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM pattern_embeddings").fetchone()[0]
        assert count == 1


class TestQueryCache:
    def test_miss_returns_none(self, tmp_db):
        _, conn = tmp_db
        assert get_cached_query(conn, "nonexistent") is None

    def test_cache_roundtrip(self, tmp_db, embedding_bytes):
        _, conn = tmp_db
        data = embedding_bytes(seed=7)
        cache_query(conn, "list files", data)
        result = get_cached_query(conn, "list files")
        assert result == data

    def test_cache_upsert(self, tmp_db, embedding_bytes):
        _, conn = tmp_db
        first = embedding_bytes(seed=1)
        second = embedding_bytes(seed=2)
        cache_query(conn, "same key", first)
        cache_query(conn, "same key", second)
        result = get_cached_query(conn, "same key")
        assert result == second


class TestSearchSimilar:
    def test_returns_results(self, populated_db, embedding_bytes):
        _, conn = populated_db
        query_emb = embedding_bytes(seed=0)
        results = search_similar(conn, query_emb, top_k=5)
        assert len(results) > 0

    def test_result_structure(self, populated_db, embedding_bytes):
        _, conn = populated_db
        query_emb = embedding_bytes(seed=0)
        results = search_similar(conn, query_emb, top_k=5)
        r = results[0]
        assert "command_template" in r
        assert "pattern_text" in r
        assert "explanation" in r
        assert "command_name" in r
        assert "command_description" in r
        assert "synopsis" in r
        assert "distance" in r

    def test_ordered_by_distance(self, populated_db, embedding_bytes):
        _, conn = populated_db
        query_emb = embedding_bytes(seed=0)
        results = search_similar(conn, query_emb, top_k=5)
        distances = [r["distance"] for r in results]
        assert distances == sorted(distances)

    def test_respects_top_k(self, populated_db, embedding_bytes):
        _, conn = populated_db
        query_emb = embedding_bytes(seed=0)
        results = search_similar(conn, query_emb, top_k=1)
        assert len(results) == 1


class TestGetStats:
    def test_empty_db(self, tmp_db):
        _, conn = tmp_db
        stats = get_stats(conn)
        assert stats == {"commands": 0, "patterns": 0}

    def test_after_inserts(self, populated_db):
        _, conn = populated_db
        stats = get_stats(conn)
        assert stats["commands"] == 2
        assert stats["patterns"] == 3


class TestClearAll:
    def test_clears_everything(self, populated_db, embedding_bytes):
        _, conn = populated_db
        cache_query(conn, "test query", embedding_bytes(seed=99))
        clear_all(conn)
        stats = get_stats(conn)
        assert stats == {"commands": 0, "patterns": 0}
        assert get_cached_query(conn, "test query") is None


class TestBulkPragmas:
    def test_bulk_and_restore_round_trip(self, tmp_db):
        _, conn = tmp_db
        bulk_load_pragmas(conn)
        sync = conn.execute("PRAGMA synchronous").fetchone()[0]
        assert sync == 0  # OFF

        restore_pragmas(conn)
        sync = conn.execute("PRAGMA synchronous").fetchone()[0]
        assert sync == 1  # NORMAL
