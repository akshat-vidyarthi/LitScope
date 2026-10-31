import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.ingestion.embedder import embed_query, cosine_similarity


def retrieve_project_evidence(
    project_id: int,
    query: str,
    top_k: int = 5,
    db: Session = None,
    paper_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Executes project-scoped hybrid retrieval:
    1. Filters candidate chunks strictly to papers with inclusion_status = 'included' in the project.
    2. Optionally filters to a specific paper_id if provided.
    3. Performs PostgreSQL full-text search (tsvector/plainto_tsquery).
    4. Computes semantic vector cosine similarity using BGE-small embeddings.
    5. Combines vector and keyword relevance scores.
    5. Returns top_k chunks sorted by final relevance score.
    """
    clean_query = query.strip()
    if not clean_query or db is None:
        return []

    # 1. Fetch chunks belonging strictly to included papers in this project (optionally single paper)
    where_conditions = [
        "pp.project_id = :project_id",
        "pp.inclusion_status = 'included'",
    ]
    params: Dict[str, Any] = {"project_id": project_id, "query": clean_query}

    if paper_id is not None:
        where_conditions.append("c.paper_id = :paper_id")
        params["paper_id"] = paper_id

    where_clause = " AND ".join(where_conditions)

    sql = text(f"""
        SELECT
            c.id AS chunk_id,
            c.paper_id,
            c.page_number,
            c.chunk_index,
            c.content,
            c.embedding,
            p.title AS paper_title,
            p.authors AS paper_authors,
            p.year AS paper_year,
            ts_rank_cd(c.tsv_content, plainto_tsquery('english', :query)) AS keyword_rank
        FROM paper_chunks c
        JOIN papers p ON p.id = c.paper_id
        JOIN project_papers pp ON pp.paper_id = c.paper_id
        WHERE {where_clause};
    """)

    rows = db.execute(sql, params).mappings().fetchall()
    if not rows:
        return []

    # 2. Compute query vector
    query_vec = embed_query(clean_query)

    # 3. Score chunks
    scored_results = []
    max_kw_rank = max((r["keyword_rank"] for r in rows), default=0.0)

    for r in rows:
        vec_score = 0.0
        embedding_val = r["embedding"]
        if embedding_val:
            chunk_vec = json.loads(embedding_val) if isinstance(embedding_val, str) else embedding_val
            vec_score = cosine_similarity(query_vec, chunk_vec)

        # Normalized keyword score
        kw_score = (r["keyword_rank"] / max_kw_rank) if max_kw_rank > 0 else 0.0

        # Weighted hybrid score: 70% semantic vector, 30% exact keyword match
        final_score = (0.70 * vec_score) + (0.30 * kw_score)

        title = r["paper_title"]
        page_num = r["page_number"]
        short_title = title[:45] + "..." if len(title) > 48 else title
        citation = f"[{short_title}, p. {page_num}]"

        scored_results.append({
            "chunk_id": r["chunk_id"],
            "paper_id": r["paper_id"],
            "paper_title": r["paper_title"],
            "paper_authors": r["paper_authors"],
            "paper_year": r["paper_year"],
            "page_number": r["page_number"],
            "content": r["content"],
            "score": round(final_score, 4),
            "citation": citation,
        })

    # Sort descending by score
    scored_results.sort(key=lambda x: x["score"], reverse=True)
    return scored_results[:top_k]
