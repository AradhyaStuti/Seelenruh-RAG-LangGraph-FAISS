# Thin wrapper around sentence-transformers. Model loads lazily so startup is fast.
# Call warmup() early (we do it in a background task at startup) so the first request isn't slow.
from typing import Iterable
import numpy as np
from sentence_transformers import SentenceTransformer
from config import EMBEDDING_MODEL

_model: SentenceTransformer | None = None


def _get() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def is_loaded() -> bool:
    return _model is not None


def warmup() -> None:
    """Force the model into memory so the first user query is fast."""
    _get().encode(["warmup"], normalize_embeddings=True)


def embed_one(text: str) -> np.ndarray:
    vec = _get().encode([text], normalize_embeddings=True)[0]
    return vec.astype("float32")


def embed_many(texts: Iterable[str]) -> np.ndarray:
    vecs = _get().encode(list(texts), normalize_embeddings=True, batch_size=32)
    return vecs.astype("float32")


def dim() -> int:
    return _get().get_sentence_embedding_dimension()
