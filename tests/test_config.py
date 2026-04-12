"""Tests for cf.config module."""

from pathlib import Path

from cf.config import DATA_DIR, DB_DIR, DB_PATH, EMBEDDING_DIM, MODEL_NAME, ONNX_DIR


class TestConfigConstants:
    def test_model_name_is_miniml(self):
        assert MODEL_NAME == "all-MiniLM-L6-v2"

    def test_embedding_dim_matches_model(self):
        assert EMBEDDING_DIM == 384

    def test_data_dir_points_to_commands(self):
        assert DATA_DIR.name == "commands"
        assert DATA_DIR.parent.name == "data"

    def test_db_dir_under_local_share(self):
        assert DB_DIR == Path.home() / ".local" / "share" / "cf"

    def test_db_path_is_sqlite_file(self):
        assert DB_PATH.name == "cf.db"
        assert DB_PATH.parent == DB_DIR

    def test_onnx_dir_under_db_dir(self):
        assert ONNX_DIR == DB_DIR / "onnx"

    def test_seed_files_exist(self):
        json_files = list(DATA_DIR.glob("*.json"))
        assert len(json_files) >= 1, "Expected at least one seed JSON file"
