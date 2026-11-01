import re
from typing import Dict, Any, List, Optional


def extract_citations(text: str) -> List[Dict[str, Any]]:
    """
    Extracts all citation pills in [Paper Title, p. X] format.
    Returns list of dicts: {"raw": str, "title": str, "page": int}
    """
    pattern = r'\[([^\]]+?),\s*p\.\s*(\d+)\]'
    matches = re.finditer(pattern, text)
    results = []
    for m in matches:
        title = m.group(1).strip()
        page = int(m.group(2))
        results.append({
            "raw": m.group(0),
            "title": title,
            "page": page
        })
    return results


def evaluate_citation_fidelity(
    generated_text: str,
    papers_metadata: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Verifies that all citations in the generated response match real papers
    and valid page numbers in the curated project.
    
    papers_metadata format:
    [{"title": "Paper Name", "page_count": 12, ...}]
    """
    citations = extract_citations(generated_text)
    if not citations:
        return {
            "total_citations": 0,
            "valid_citations": 0,
            "hallucinated_citations": 0,
            "fidelity_score": 1.0,  # No invalid citations claimed
            "details": []
        }

    # Normalize titles for matching
    paper_map = {}
    for p in papers_metadata:
        norm = " ".join(p.get("title", "").lower().split())
        paper_map[norm] = p.get("page_count", 999)

    valid_count = 0
    hallucinated_count = 0
    details = []

    for c in citations:
        c_title_norm = " ".join(c["title"].lower().split())
        page_num = c["page"]

        # Check if title matches any available paper
        matched_title = None
        matched_max_page = 999
        for p_title, max_page in paper_map.items():
            if c_title_norm in p_title or p_title in c_title_norm:
                matched_title = p_title
                matched_max_page = max_page
                break

        if matched_title is not None and 1 <= page_num <= matched_max_page:
            valid_count += 1
            details.append({"citation": c["raw"], "status": "valid", "reason": "matches paper and page range"})
        else:
            hallucinated_count += 1
            reason = "paper title not in project" if matched_title is None else f"page {page_num} exceeds paper total {matched_max_page}"
            details.append({"citation": c["raw"], "status": "hallucinated", "reason": reason})

    fidelity_score = round(valid_count / len(citations), 3) if citations else 1.0

    return {
        "total_citations": len(citations),
        "valid_citations": valid_count,
        "hallucinated_citations": hallucinated_count,
        "fidelity_score": fidelity_score,
        "details": details
    }


def calculate_lexical_grounding_score(statement: str, evidence_passages: List[str]) -> float:
    """
    Computes lexical alignment score (token overlap ratio) between the generated
    claim and the ground truth evidence passages to detect unsubstantiated claims.
    """
    if not statement or not evidence_passages:
        return 0.0

    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "and", "or", "in", "on", "at",
        "to", "for", "with", "by", "that", "this", "these", "those", "of", "from",
        "according", "evidence", "paper", "based"
    }

    # Extract informative tokens
    statement_words = set(
        w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', statement)
        if w.lower() not in stop_words
    )
    if not statement_words:
        return 1.0

    combined_evidence = " ".join(evidence_passages).lower()
    evidence_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', combined_evidence))

    overlap = statement_words.intersection(evidence_words)
    score = len(overlap) / len(statement_words)
    return round(score, 3)
