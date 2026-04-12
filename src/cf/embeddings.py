import hashlib
import logging
import os
import sys
from pathlib import Path

import numpy as np

from cf.config import EMBEDDING_DIM, MODEL_NAME, ONNX_DIR

_model = None
_onnx_session = None
_onnx_tokenizer = None

# Embedding cache directory: avoids re-encoding on reseed
CACHE_DIR = Path.home() / ".local" / "share" / "cf" / "cache"


# ── ONNX fast path (no torch/transformers) ───────────────────

def _onnx_available() -> bool:
    return (ONNX_DIR / "model.onnx").exists() and (ONNX_DIR / "tokenizer.json").exists()


def _get_onnx():
    global _onnx_session, _onnx_tokenizer
    if _onnx_session is None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 4
        _onnx_session = ort.InferenceSession(
            str(ONNX_DIR / "model.onnx"), sess_options=opts,
            providers=["CPUExecutionProvider"],
        )
        _onnx_tokenizer = Tokenizer.from_file(str(ONNX_DIR / "tokenizer.json"))
        _onnx_tokenizer.enable_padding(pad_id=0, pad_token="[PAD]", length=128)
        _onnx_tokenizer.enable_truncation(max_length=128)
    return _onnx_session, _onnx_tokenizer


def _encode_onnx(text: str) -> np.ndarray:
    session, tokenizer = _get_onnx()
    encoded = tokenizer.encode(text)
    input_ids = np.array([encoded.ids], dtype=np.int64)
    attention_mask = np.array([encoded.attention_mask], dtype=np.int64)
    token_type_ids = np.zeros_like(input_ids)

    outputs = session.run(None, {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "token_type_ids": token_type_ids,
    })
    # Mean pooling over token embeddings, masked by attention
    token_embeddings = outputs[0]  # (1, seq_len, 384)
    mask = attention_mask[:, :, np.newaxis].astype(np.float32)
    pooled = (token_embeddings * mask).sum(axis=1) / mask.sum(axis=1)
    # L2 normalize
    norm = np.linalg.norm(pooled, axis=1, keepdims=True)
    return (pooled / norm)[0]


def _encode_onnx_batch(texts: list[str]) -> np.ndarray:
    session, tokenizer = _get_onnx()
    encoded_batch = tokenizer.encode_batch(texts)

    max_len = max(len(e.ids) for e in encoded_batch)
    batch_size = len(texts)

    input_ids = np.zeros((batch_size, max_len), dtype=np.int64)
    attention_mask = np.zeros((batch_size, max_len), dtype=np.int64)
    token_type_ids = np.zeros((batch_size, max_len), dtype=np.int64)

    for i, e in enumerate(encoded_batch):
        length = len(e.ids)
        input_ids[i, :length] = e.ids
        attention_mask[i, :length] = e.attention_mask

    outputs = session.run(None, {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "token_type_ids": token_type_ids,
    })
    token_embeddings = outputs[0]
    mask = attention_mask[:, :, np.newaxis].astype(np.float32)
    pooled = (token_embeddings * mask).sum(axis=1) / mask.sum(axis=1)
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    return pooled / norms


# ── Full model path (sentence-transformers + torch) ──────────

def _get_full_model():
    global _model
    if _model is None:
        for name in ("sentence_transformers", "transformers", "torch",
                     "transformers.modeling_utils", "huggingface_hub"):
            logging.getLogger(name).setLevel(logging.ERROR)
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        import warnings
        warnings.filterwarnings("ignore", message=".*unauthenticated.*")

        print("Loading model...", file=sys.stderr, end=" ", flush=True)
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


# ── Public API ───────────────────────────────────────────────

def encode_text(text: str) -> np.ndarray:
    if _onnx_available():
        return _encode_onnx(text)
    model = _get_full_model()
    return model.encode(text, normalize_embeddings=True)


def encode_batch(texts: list[str], batch_size: int = 128) -> np.ndarray:
    """Batch encode with disk cache. Skips model entirely on cache hit."""
    cache_path = _cache_path(texts)
    if cache_path.exists():
        print("Using cached embeddings.", file=sys.stderr)
        return np.load(cache_path)

    if _onnx_available():
        embeddings = _encode_onnx_batch(texts)
    else:
        model = _get_full_model()
        embeddings = model.encode(
            texts, batch_size=batch_size, normalize_embeddings=True,
            show_progress_bar=True,
        )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache_path, embeddings)
    return embeddings


def export_onnx() -> Path:
    """Export the model to ONNX format for fast loading. One-time operation."""
    print("Exporting model to ONNX (one-time)...", file=sys.stderr, end=" ", flush=True)
    model = _get_full_model()

    ONNX_DIR.mkdir(parents=True, exist_ok=True)

    # Export tokenizer
    model.tokenizer.save_pretrained(str(ONNX_DIR))

    # Export model to ONNX via torch (force CPU for tracing)
    import torch
    transformer = model[0].auto_model.cpu()
    tokenizer = model.tokenizer

    dummy = tokenizer("hello world", return_tensors="pt", padding=True, truncation=True)
    for k in dummy:
        dummy[k] = dummy[k].cpu()
    if "token_type_ids" not in dummy:
        dummy["token_type_ids"] = torch.zeros_like(dummy["input_ids"])

    torch.onnx.export(
        transformer,
        (dummy["input_ids"], dummy["attention_mask"], dummy["token_type_ids"]),
        str(ONNX_DIR / "model.onnx"),
        input_names=["input_ids", "attention_mask", "token_type_ids"],
        output_names=["token_embeddings"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "seq"},
            "attention_mask": {0: "batch", 1: "seq"},
            "token_type_ids": {0: "batch", 1: "seq"},
            "token_embeddings": {0: "batch", 1: "seq"},
        },
        opset_version=14,
        dynamo=False,
    )
    print("done.", file=sys.stderr)
    print(f"ONNX model saved to {ONNX_DIR}", file=sys.stderr)
    return ONNX_DIR


def to_bytes(embedding: np.ndarray) -> bytes:
    return np.ascontiguousarray(embedding, dtype=np.float32).tobytes()


def _cache_path(texts: list[str]) -> Path:
    """Deterministic cache key from the content of all texts."""
    h = hashlib.sha256("\n".join(texts).encode()).hexdigest()[:16]
    return CACHE_DIR / f"embeddings_{MODEL_NAME}_{len(texts)}_{h}.npy"
