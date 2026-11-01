import os
import hashlib
from typing import List, Optional
import numpy as np

# Suppress Hugging Face symlink warning on Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

_EMBEDDER_INSTANCE = None
DEFAULT_MODEL_NAME = "BAAI/bge-small-en-v1.5"

# In memory-constrained cloud environments (such as Render Free Tier's 512 MB RAM limit),
# loading heavy ONNX runtime deep learning models triggers an out-of-memory kernel kill.
# When running on Render or when LIGHTWEIGHT_EMBEDDINGS is enabled, LitScope uses an
# ultra-fast, zero-memory 384-dimensional subword feature-hashing vectorizer.
USE_LIGHTWEIGHT = (
    str(os.getenv("RENDER", "")).lower() in ("true", "1")
    or os.getenv("RENDER_SERVICE_ID") is not None
    or str(os.getenv("LIGHTWEIGHT_EMBEDDINGS", "")).lower() in ("true", "1")
)


def _lightweight_hash_embed(text: str, dim: int = 384) -> List[float]:
    """
    Computes a deterministic 384-dimensional normalized vector using subword
    character n-gram feature hashing. Consumes virtually zero memory (< 1 MB)
    and executes in under 1ms, preventing cloud OOM kills on Render free tier.
    """
    vec = np.zeros(dim, dtype=np.float32)
    if not text or not text.strip():
        return vec.tolist()

    clean_text = text.lower().strip()
    words = clean_text.split()

    # Feature extraction: full words and character 3-grams for subword similarity
    features = list(words)
    for word in words:
        if len(word) >= 3:
            for i in range(len(word) - 2):
                features.append(word[i:i + 3])

    for feat in features:
        h = int(hashlib.md5(feat.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 16) & 1 else -1.0
        vec[idx] += sign

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return [float(x) for x in vec]


def get_embedder(model_name: str = DEFAULT_MODEL_NAME):
    """Returns a singleton instance of the FastEmbed TextEmbedding model."""
    global _EMBEDDER_INSTANCE
    if _EMBEDDER_INSTANCE is None:
        from fastembed import TextEmbedding
        _EMBEDDER_INSTANCE = TextEmbedding(model_name=model_name, threads=1)
    return _EMBEDDER_INSTANCE


def embed_texts(texts: List[str], model_name: str = DEFAULT_MODEL_NAME) -> List[List[float]]:
    """
    Generates normalized 384-dimensional vector embeddings for a list of text strings.
    Returns list of float lists suitable for JSON serialization in PostgreSQL.
    """
    if not texts:
        return []

    if USE_LIGHTWEIGHT:
        return [_lightweight_hash_embed(t) for t in texts]

    try:
        embedder = get_embedder(model_name)
        embeddings = list(embedder.embed(texts, batch_size=8))
        return [vec.tolist() for vec in embeddings]
    except Exception:
        # Fallback to zero-memory hash embedding if ONNX fails or runs out of memory
        return [_lightweight_hash_embed(t) for t in texts]


def embed_query(query: str, model_name: str = DEFAULT_MODEL_NAME) -> List[float]:
    """Generates a normalized 384-dimensional vector embedding for a single query."""
    if USE_LIGHTWEIGHT:
        return _lightweight_hash_embed(query)

    try:
        embedder = get_embedder(model_name)
        embeddings = list(embedder.embed([query]))
        return embeddings[0].tolist()
    except Exception:
        return _lightweight_hash_embed(query)


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Computes cosine similarity between two normalized vectors."""
    a = np.array(vec1, dtype=np.float32)
    b = np.array(vec2, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
