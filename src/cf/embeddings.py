import logging
import os
import sys

import numpy as np

from cf.config import MODEL_NAME

_model = None


def get_model():
    global _model
    if _model is None:
        # Suppress noisy transformer/torch logs during model load
        for name in ("sentence_transformers", "transformers", "torch",
                     "transformers.modeling_utils", "huggingface_hub"):
            logging.getLogger(name).setLevel(logging.ERROR)
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        # Suppress the "unauthenticated requests" warning
        import warnings
        warnings.filterwarnings("ignore", message=".*unauthenticated.*")

        print("Loading model...", file=sys.stderr, end=" ", flush=True)
        # Temporarily redirect stderr to suppress model loader noise
        _real_stderr = sys.stderr
        sys.stderr = open(os.devnull, "w")
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(MODEL_NAME)
        finally:
            sys.stderr.close()
            sys.stderr = _real_stderr
        print("done.", file=sys.stderr)
    return _model


def encode_text(text: str) -> np.ndarray:
    model = get_model()
    return model.encode(text, normalize_embeddings=True)


def encode_batch(texts: list[str], batch_size: int = 64) -> np.ndarray:
    model = get_model()
    return model.encode(texts, batch_size=batch_size, normalize_embeddings=True,
                        show_progress_bar=True)


def to_bytes(embedding: np.ndarray) -> bytes:
    return embedding.astype(np.float32).tobytes()
