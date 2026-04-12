import os
from importlib.resources import files
from pathlib import Path

MODEL_NAME = os.environ.get("CF_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.environ.get("CF_EMBEDDING_DIM", 384))
DEFAULT_TOP_K = int(os.environ.get("CF_TOP", 7))
DEFAULT_MAX_TOP_K = int(os.environ.get("CF_MAX_TOP", 50))

DATA_DIR = Path(os.environ.get("CF_DATA_DIR", str(files("cf") / "data" / "commands")))
DB_DIR = Path(os.environ.get("CF_DB_DIR", str(Path.home() / ".local" / "share" / "cf")))
DB_PATH = DB_DIR / os.environ.get("CF_DB_NAME", "cf.db")
ONNX_DIR = DB_DIR / "onnx"
