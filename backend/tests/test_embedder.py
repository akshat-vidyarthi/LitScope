import pytest
from app.ingestion.embedder import embed_texts, embed_query, cosine_similarity


def test_embed_texts_dimension_and_count():
    """Verifies that embed_texts produces 384-dimensional embeddings for each input string."""
    texts = [
        "Convolutional neural networks for automated currency counterfeit classification.",
        "Stochastic gradient descent with momentum and adaptive learning rates.",
    ]
    vectors = embed_texts(texts)
    assert len(vectors) == 2
    assert len(vectors[0]) == 384
    assert len(vectors[1]) == 384
    assert isinstance(vectors[0][0], float)


def test_embed_query_dimension():
    """Verifies single query embedding."""
    vec = embed_query("What algorithms were tested for forgery detection?")
    assert len(vec) == 384
    assert isinstance(vec[0], float)


def test_cosine_similarity_semantic_ranking():
    """
    Verifies that semantically related texts have higher cosine similarity
    than unrelated texts.
    """
    q_vec = embed_query("runtime bottlenecks in distributed deep learning")
    related_vec = embed_query("throughput saturation and latency degradation across GPU clusters")
    unrelated_vec = embed_query("medieval pottery techniques in fourteenth century Europe")

    sim_related = cosine_similarity(q_vec, related_vec)
    sim_unrelated = cosine_similarity(q_vec, unrelated_vec)

    assert sim_related > sim_unrelated
    assert sim_related > 0.60
    assert (sim_related - sim_unrelated) > 0.15
