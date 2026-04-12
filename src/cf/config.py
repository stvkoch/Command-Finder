from importlib.resources import files
from pathlib import Path

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
DEFAULT_TOP_K = 7

DATA_DIR = Path(str(files("cf") / "data" / "commands"))
DB_DIR = Path.home() / ".local" / "share" / "cf"
DB_PATH = DB_DIR / "cf.db"
