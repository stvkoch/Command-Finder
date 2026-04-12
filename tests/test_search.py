"""Tests for cf.search module — query normalization, dedup, search pipeline."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from cf.config import EMBEDDING_DIM
from cf.search import SearchResult, _normalize_query, search


class TestNormalizeQuery:
    def test_lowercases(self):
        assert _normalize_query("FIND FILES") == "files find"

    def test_strips_stopwords(self):
        assert _normalize_query("how to find a file") == "file find"

    def test_sorts_tokens(self):
        assert _normalize_query("delete old files") == "delete files old"

    def test_all_stopwords_fallback(self):
        result = _normalize_query("the a an")
        assert result != ""
        assert "a" in result

    def test_empty_string(self):
        assert _normalize_query("") == ""

    def test_deterministic_different_order(self):
        assert _normalize_query("files list") == _normalize_query("list files")

    def test_single_meaningful_word(self):
        assert _normalize_query("the process") == "process"


class TestSearchResult:
    def test_dataclass_fields(self):
        r = SearchResult(
            command_template="ls -la",
            pattern_text="list files",
            explanation="Shows all",
            command_name="ls",
            command_description="List directory",
            synopsis="ls [opts]",
            distance=0.5,
        )
        assert r.command_template == "ls -la"
        assert r.distance == 0.5

    def test_optional_explanation(self):
        r = SearchResult(
            command_template="pwd",
            pattern_text="current dir",
            explanation=None,
            command_name="pwd",
            command_description="Print working directory",
            synopsis="pwd",
            distance=0.1,
        )
        assert r.explanation is None


class TestSearch:
    @patch("cf.search.get_connection")
    @patch("cf.search.init_db")
    @patch("cf.search.get_cached_query", return_value=None)
    @patch("cf.search.cache_query")
    @patch("cf.search.search_similar")
    def test_deduplicates_by_template(
        self, mock_search_sim, mock_cache_q, mock_get_cache, mock_init, mock_conn
    ):
        mock_connection = MagicMock()
        mock_conn.return_value = mock_connection

        mock_search_sim.return_value = [
            {
                "command_template": "ls -la",
                "pattern_text": "list all files",
                "explanation": "first match",
                "command_name": "ls",
                "command_description": "List",
                "synopsis": "ls",
                "distance": 0.1,
            },
            {
                "command_template": "ls -la",
                "pattern_text": "show all files",
                "explanation": "duplicate template",
                "command_name": "ls",
                "command_description": "List",
                "synopsis": "ls",
                "distance": 0.2,
            },
            {
                "command_template": "ls -a",
                "pattern_text": "hidden files",
                "explanation": None,
                "command_name": "ls",
                "command_description": "List",
                "synopsis": "ls",
                "distance": 0.3,
            },
        ]

        with patch("cf.embeddings.encode_text") as mock_encode, \
             patch("cf.embeddings.to_bytes") as mock_to_bytes:
            mock_encode.return_value = np.zeros(EMBEDDING_DIM, dtype=np.float32)
            mock_to_bytes.return_value = b"\x00" * (EMBEDDING_DIM * 4)

            results = search("list files", top_k=10, db_path="/fake/path")

        assert len(results) == 2
        templates = [r.command_template for r in results]
        assert "ls -la" in templates
        assert "ls -a" in templates

    @patch("cf.search.get_connection")
    @patch("cf.search.init_db")
    @patch("cf.search.get_cached_query", return_value=None)
    @patch("cf.search.cache_query")
    @patch("cf.search.search_similar")
    def test_keeps_lowest_distance_on_dedup(
        self, mock_search_sim, mock_cache_q, mock_get_cache, mock_init, mock_conn
    ):
        mock_conn.return_value = MagicMock()

        mock_search_sim.return_value = [
            {
                "command_template": "ls -la",
                "pattern_text": "second match (worse)",
                "explanation": None,
                "command_name": "ls",
                "command_description": "List",
                "synopsis": "ls",
                "distance": 0.5,
            },
            {
                "command_template": "ls -la",
                "pattern_text": "first match (better)",
                "explanation": None,
                "command_name": "ls",
                "command_description": "List",
                "synopsis": "ls",
                "distance": 0.1,
            },
        ]

        with patch("cf.embeddings.encode_text") as mock_encode, \
             patch("cf.embeddings.to_bytes") as mock_to_bytes:
            mock_encode.return_value = np.zeros(EMBEDDING_DIM, dtype=np.float32)
            mock_to_bytes.return_value = b"\x00" * (EMBEDDING_DIM * 4)

            results = search("list files", top_k=10, db_path="/fake/path")

        assert len(results) == 1
        assert results[0].distance == 0.1
        assert results[0].pattern_text == "first match (better)"

    @patch("cf.search.get_connection")
    @patch("cf.search.init_db")
    @patch("cf.search.get_cached_query")
    @patch("cf.search.search_similar", return_value=[])
    def test_uses_cached_embedding(
        self, mock_search_sim, mock_get_cache, mock_init, mock_conn
    ):
        mock_conn.return_value = MagicMock()
        cached_bytes = b"\x01" * (EMBEDDING_DIM * 4)
        mock_get_cache.return_value = cached_bytes

        results = search("test query", db_path="/fake/path")

        mock_search_sim.assert_called_once()
        call_args = mock_search_sim.call_args
        assert call_args[0][1] == cached_bytes

    @patch("cf.search.get_connection")
    @patch("cf.search.init_db")
    @patch("cf.search.get_cached_query", return_value=None)
    @patch("cf.search.cache_query")
    @patch("cf.search.search_similar")
    def test_respects_top_k(
        self, mock_search_sim, mock_cache_q, mock_get_cache, mock_init, mock_conn
    ):
        mock_conn.return_value = MagicMock()

        mock_search_sim.return_value = [
            {
                "command_template": f"cmd{i}",
                "pattern_text": f"pattern {i}",
                "explanation": None,
                "command_name": f"cmd{i}",
                "command_description": f"desc {i}",
                "synopsis": f"cmd{i}",
                "distance": float(i) / 10,
            }
            for i in range(10)
        ]

        with patch("cf.embeddings.encode_text") as mock_encode, \
             patch("cf.embeddings.to_bytes") as mock_to_bytes:
            mock_encode.return_value = np.zeros(EMBEDDING_DIM, dtype=np.float32)
            mock_to_bytes.return_value = b"\x00" * (EMBEDDING_DIM * 4)

            results = search("test", top_k=3, db_path="/fake/path")

        assert len(results) == 3

    @patch("cf.search.get_connection")
    @patch("cf.search.init_db")
    @patch("cf.search.get_cached_query", return_value=None)
    @patch("cf.search.cache_query")
    @patch("cf.search.search_similar", return_value=[])
    def test_empty_results(
        self, mock_search_sim, mock_cache_q, mock_get_cache, mock_init, mock_conn
    ):
        mock_conn.return_value = MagicMock()

        with patch("cf.embeddings.encode_text") as mock_encode, \
             patch("cf.embeddings.to_bytes") as mock_to_bytes:
            mock_encode.return_value = np.zeros(EMBEDDING_DIM, dtype=np.float32)
            mock_to_bytes.return_value = b"\x00" * (EMBEDDING_DIM * 4)

            results = search("gibberish query xyz", db_path="/fake/path")

        assert results == []
