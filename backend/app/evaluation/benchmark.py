import time
from typing import List, Dict, Any


def calculate_retrieval_metrics(
    query_benchmarks: List[Dict[str, Any]],
    retrieval_fn
) -> Dict[str, Any]:
    """
    Evaluates retrieval engine against standard benchmarks.
    Each benchmark item: {"query": str, "expected_keyword": str, "project_id": int}
    
    Returns:
    - hit_rate_at_1
    - hit_rate_at_3
    - mean_reciprocal_rank (MRR)
    - average_latency_ms
    """
    total = len(query_benchmarks)
    if total == 0:
        return {"hit_rate_at_1": 0.0, "hit_rate_at_3": 0.0, "mrr": 0.0, "avg_latency_ms": 0.0}

    hits_at_1 = 0
    hits_at_3 = 0
    rr_sum = 0.0
    latencies = []

    for item in query_benchmarks:
        q = item["query"]
        expected = item["expected_keyword"].lower()
        project_id = item.get("project_id", 1)

        start = time.perf_counter()
        try:
            results = retrieval_fn(project_id, q, limit=5)
        except Exception:
            results = []
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)

        # Check ranks
        found_rank = None
        for rank, chunk in enumerate(results, 1):
            content = chunk.get("content", "").lower()
            if expected in content:
                found_rank = rank
                break

        if found_rank == 1:
            hits_at_1 += 1
            hits_at_3 += 1
            rr_sum += 1.0
        elif found_rank and found_rank <= 3:
            hits_at_3 += 1
            rr_sum += 1.0 / found_rank
        elif found_rank:
            rr_sum += 1.0 / found_rank

    return {
        "total_queries": total,
        "hit_rate_at_1": round(hits_at_1 / total, 3),
        "hit_rate_at_3": round(hits_at_3 / total, 3),
        "mean_reciprocal_rank": round(rr_sum / total, 3),
        "average_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0
    }
