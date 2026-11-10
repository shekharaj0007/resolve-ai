"""Ticket embeddings.

Sentence Transformers (all-MiniLM-L6-v2) is used when the package and model
are available. Otherwise search uses a 128-dimension TF-IDF + TruncatedSVD
embedding trained with the classifiers.
"""

import logging
import os
import threading

import numpy as np

from backend.app.config import MODELS_DIR

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

logger = logging.getLogger(__name__)

_embedder = None
_lock = threading.Lock()


class SvdEmbedder:
    name = "tfidf-truncated-svd"

    def __init__(self, tfidf, svd):
        self.tfidf = tfidf
        self.svd = svd
        self.dim = int(svd.n_components)

    def encode(self, texts) -> np.ndarray:
        projected = np.asarray(self.svd.transform(self.tfidf.transform(list(texts))), dtype=np.float32)
        norms = np.linalg.norm(projected, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return projected / norms

    def save(self, path) -> None:
        import joblib

        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"tfidf": self.tfidf, "svd": self.svd}, path, compress=3)

    @classmethod
    def load(cls, path):
        import joblib

        payload = joblib.load(path)
        return cls(payload["tfidf"], payload["svd"])


class STEmbedder:
    name = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, model):
        self.model = model
        dimension = model.get_embedding_dimension() if hasattr(model, "get_embedding_dimension") else model.get_sentence_embedding_dimension()
        self.dim = int(dimension)

    def encode(self, texts) -> np.ndarray:
        vectors = self.model.encode(
            list(texts),
            batch_size=64,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)


def _try_sentence_transformer():
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        logger.info("Sentence Transformers is not installed (%s).", exc.__class__.__name__)
        return None
    try:
        model = SentenceTransformer("all-MiniLM-L6-v2")
    except Exception as exc:
        logger.warning("Could not load all-MiniLM-L6-v2 (%s). Falling back to TF-IDF SVD.", exc)
        return None
    logger.info("Loaded sentence-transformers/all-MiniLM-L6-v2.")
    return STEmbedder(model)


def get_embedder():
    global _embedder
    if _embedder is not None:
        return _embedder
    with _lock:
        if _embedder is not None:
            return _embedder
        choice = os.getenv("EMBEDDER", "auto").strip().lower()
        if choice in {"", "auto", "sentence-transformers", "st"}:
            loaded = _try_sentence_transformer()
            if loaded is not None:
                _embedder = loaded
                return _embedder
            if choice in {"sentence-transformers", "st"}:
                raise RuntimeError("Sentence Transformers was requested but is not available.")
        path = MODELS_DIR / "svd_embedder.joblib"
        if not path.exists():
            raise RuntimeError("No embedder is available. Run python -m backend.scripts.bootstrap.")
        _embedder = SvdEmbedder.load(path)
        logger.info("Using TF-IDF + TruncatedSVD embeddings.")
        return _embedder


def current_name() -> str:
    if _embedder is None:
        return "pending"
    return _embedder.name


def warm() -> None:
    try:
        get_embedder()
    except Exception as exc:
        logger.warning("Embedder warmup failed: %s", exc)


def encode(texts) -> np.ndarray:
    return get_embedder().encode(texts)


def encode_many(texts, batch_size: int = 256) -> np.ndarray:
    embedder = get_embedder()
    if not texts:
        return np.zeros((0, embedder.dim), dtype=np.float32)
    chunks = []
    total = len(texts)
    for start in range(0, total, batch_size):
        chunks.append(embedder.encode(texts[start : start + batch_size]))
        done = min(start + batch_size, total)
        print(f"Embedded {done}/{total} with {embedder.name}", flush=True)
    return np.vstack(chunks)


def pack_vector(vector) -> bytes:
    return np.asarray(vector, dtype=np.float32).ravel().tobytes()
