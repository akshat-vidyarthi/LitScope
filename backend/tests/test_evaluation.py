from app.evaluation.grounding import (
    extract_citations,
    evaluate_citation_fidelity,
    calculate_lexical_grounding_score
)
from app.evaluation.benchmark import calculate_retrieval_metrics


def test_citation_extraction_and_fidelity():
    text = "The authors propose an attention-based encoder [Attention is All You Need, p. 3] with 8 heads [Attention is All You Need, p. 5]."
    citations = extract_citations(text)
    assert len(citations) == 2
    assert citations[0]["title"] == "Attention is All You Need"
    assert citations[0]["page"] == 3
    assert citations[1]["page"] == 5

    papers = [{"title": "Attention is All You Need", "page_count": 15}]
    eval_result = evaluate_citation_fidelity(text, papers)
    assert eval_result["total_citations"] == 2
    assert eval_result["valid_citations"] == 2
    assert eval_result["hallucinated_citations"] == 0
    assert eval_result["fidelity_score"] == 1.0


def test_citation_hallucination_detection():
    # Citation references paper that doesn't exist, and page exceeding max
    text = "Recent claims [Nonexistent Paper, p. 2] demonstrate 99% accuracy [Attention is All You Need, p. 99]."
    papers = [{"title": "Attention is All You Need", "page_count": 10}]
    eval_result = evaluate_citation_fidelity(text, papers)
    assert eval_result["total_citations"] == 2
    assert eval_result["valid_citations"] == 0
    assert eval_result["hallucinated_citations"] == 2
    assert eval_result["fidelity_score"] == 0.0


def test_lexical_grounding_score():
    statement = "The model achieved 94.2 percent accuracy on the GLUE benchmark dataset."
    evidence = [
        "In our empirical experiments, the model achieved 94.2 percent accuracy on the GLUE benchmark dataset."
    ]
    score = calculate_lexical_grounding_score(statement, evidence)
    assert score >= 0.8

    unsupported_statement = "Quantum supercomputing solved the protein folding mystery in three seconds."
    unsupported_score = calculate_lexical_grounding_score(unsupported_statement, evidence)
    assert unsupported_score < 0.2


def test_retrieval_benchmark_metrics():
    queries = [
        {"query": "attention mechanisms", "expected_keyword": "transformer", "project_id": 1},
        {"query": "residual connections", "expected_keyword": "resnet", "project_id": 1}
    ]

    # Mock retrieval function returning ranked chunks
    def mock_retrieval(pid, query, limit=5):
        if "attention" in query:
            return [{"content": "The transformer uses self-attention."}]
        elif "residual" in query:
            return [{"content": "Unrelated text"}, {"content": "Deep resnet utilizes residual skips."}]
        return []

    metrics = calculate_retrieval_metrics(queries, mock_retrieval)
    assert metrics["total_queries"] == 2
    assert metrics["hit_rate_at_1"] == 0.5   # first query at rank 1
    assert metrics["hit_rate_at_3"] == 1.0   # both in top 3
    assert metrics["mean_reciprocal_rank"] == 0.75  # (1.0 + 0.5) / 2
    assert metrics["average_latency_ms"] >= 0.0
