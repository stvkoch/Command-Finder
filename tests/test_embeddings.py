"""Tests for cf.embeddings module — encoding, caching, bytes conversion."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from cf.config import EMBEDDING_DIM, MODEL_NAME
from cf.embeddings import _cache_path, to_bytes


class TestToBytes:
    def test_output_is_bytes(self):
        vec = np.ones(EMBEDDING_DIM, dtype=np.float32)
        assert isinstance(to_bytes(vec), bytes)

    def test_byte_length_matches_dim(self):
        vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        result = to_bytes(vec)
        assert len(result) == EMBEDDING_DIM * 4  # float32 = 4 bytes

    def test_roundtrip_preserves_values(self):
        rng = np.random.default_rng(123)
        vec = rng.standard_normal(EMBEDDING_DIM).astype(np.float32)
        restored = np.frombuffer(to_bytes(vec), dtype=np.float32)
        np.testing.assert_array_almost_equal(vec, restored)

    def test_converts_float64_to_float32(self):
        vec = np.ones(EMBEDDING_DIM, dtype=np.float64)
        result = to_bytes(vec)
        assert len(result) == EMBEDDING_DIM * 4

    def test_non_contiguous_array(self):
        vec = np.ones((2, EMBEDDING_DIM), dtype=np.float32)[0, ::1]
        result = to_bytes(vec)
        assert len(result) == EMBEDDING_DIM * 4


class TestCachePath:
    def test_returns_path_object(self):
        result = _cache_path(["hello", "world"])
        assert isinstance(result, Path)

    def test_includes_model_name(self):
        result = _cache_path(["test"])
        assert MODEL_NAME in result.name

    def test_includes_count(self):
        result = _cache_path(["a", "b", "c"])
        assert "_3_" in result.name

    def test_deterministic(self):
        texts = ["same", "inputs"]
        assert _cache_path(texts) == _cache_path(texts)

    def test_different_inputs_different_paths(self):
        assert _cache_path(["hello"]) != _cache_path(["goodbye"])

    def test_npy_extension(self):
        assert _cache_path(["test"]).suffix == ".npy"


class TestEncodeText:
    @patch("cf.embeddings._onnx_available", return_value=False)
    @patch("cf.embeddings._get_full_model")
    def test_uses_full_model_when_no_onnx(self, mock_model, mock_onnx):
        mock_encoder = MagicMock()
        mock_encoder.encode.return_value = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        mock_model.return_value = mock_encoder

        from cf.embeddings import encode_text
        result = encode_text("test query")

        mock_encoder.encode.assert_called_once_with("test query", normalize_embeddings=True)
        assert result.shape == (EMBEDDING_DIM,)

    @patch("cf.embeddings._onnx_available", return_value=True)
    @patch("cf.embeddings._encode_onnx")
    def test_uses_onnx_when_available(self, mock_encode, mock_onnx):
        mock_encode.return_value = np.zeros(EMBEDDING_DIM, dtype=np.float32)

        from cf.embeddings import encode_text
        result = encode_text("test query")

        mock_encode.assert_called_once_with("test query")
        assert result.shape == (EMBEDDING_DIM,)


class TestEncodeBatch:
    @patch("cf.embeddings._onnx_available", return_value=False)
    @patch("cf.embeddings._get_full_model")
    def test_caches_to_disk(self, mock_model, mock_onnx, tmp_path):
        mock_encoder = MagicMock()
        embeddings = np.random.randn(2, EMBEDDING_DIM).astype(np.float32)
        mock_encoder.encode.return_value = embeddings
        mock_model.return_value = mock_encoder

        with patch("cf.embeddings.CACHE_DIR", tmp_path / "cache"):
            from cf.embeddings import encode_batch
            texts = ["unique_test_text_a_12345", "unique_test_text_b_67890"]
            result = encode_batch(texts)
            np.testing.assert_array_equal(result, embeddings)

            # Second call should hit cache (model not called again)
            mock_encoder.encode.reset_mock()
            result2 = encode_batch(texts)
            mock_encoder.encode.assert_not_called()
            np.testing.assert_array_equal(result2, embeddings)
