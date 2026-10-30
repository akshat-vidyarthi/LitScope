import os
from typing import List, Optional
import numpy as np

# Suppress Hugging Face symlink warning on Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

_EMBEDDER_INSTANCE = None
DEFAULT_MODEL_NAME = "BAAI/bge-small-en-v1.5"


def get_embedder(model_name: str = DEFAULT_MODEL_NAME):
    """Returns a singleton instance of the FastEmbed TextEmbedding model."""
    global _EMBEDDER_INSTANCE
    if _EMBEDDER_INSTANCE is None:
        from fastembed import TextEmbedding
        _EMBEDDER_INSTANCE = TextEmbedding(model_name=model_name)
    return _EMBEDDER_INSTANCE


def embed_texts(texts: List[str], model_name: str = DEFAULT_MODEL_NAME) -> List[List[float]]:
    """
    Generates normalized 384-dimensional vector embeddings for a list of text strings.
    Returns list of float lists suitable for JSON serialization in PostgreSQL.
    """
    if not texts:
        return []
    embedder = get_embedder(model_name)
    # FastEmbed returns a generator of numpy arrays
    embeddings = list(embedder.embed(texts))
    return [vec.tolist() for vec in embeddings]


def embed_query(query: str, model_name: str = DEFAULT_MODEL_NAME) -> List[float]:
    """Generates a normalized 384-dimensional vector embedding for a single query."""
    embedder = get_embedder(model_name)
    embeddings = list(embedder.embed([query]))
    return embeddings[0].tolist()


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Computes cosine similarity between two normalized vectors."""
    a = np.array(vec1, dtype=np.float32)
    b = np.array(vec2, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
