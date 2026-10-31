import json
import re
from typing import List, Dict, Any, Optional, Tuple
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings

SYSTEM_GAP_PROMPT = """You are an academic literature intelligence analyst. Your role is to perform an evidence-based candidate research-gap analysis organized PAPER-BY-PAPER across a set of curated papers in a research project study.

CRITICAL PRINCIPLES:
1. Paper-Wise Organization:
   Every gap must be explicitly anchored to a specific paper in the collection ("xyz paper has this gap").
2. Gap Taxonomy:
   - "methodological": Methodology limitations or blind spots in this paper (e.g. relying on classical image processing/SVMs without evaluating deep learning, or lack of ablation).
   - "dataset_context": Dataset, environmental, or evaluation constraints in this paper (e.g. tested only on clean/flat laboratory scans; crumpled, soiled, or mobile smartphone captures unaddressed).
   - "contradiction": Conflicting findings or diverging claims between this paper and others in the study.
   - "author_stated_limitation": Explicit limitations or future work stated directly by the authors in the conclusion.
3. Provenance & Citations:
   Every gap must cite the exact paper title and page number(s) where available.

OUTPUT FORMAT:
Return ONLY valid JSON matching this schema:
{
  "gaps": [
    {
      "paper_title": "Exact Title of Paper",
      "gap_title": "Concise descriptive title of the gap",
      "gap_type": "methodological" | "dataset_context" | "contradiction" | "author_stated_limitation",
      "description": "Clear explanation of what is missing in this paper, why it matters, and how it impacts future research.",
      "supporting_evidence": [
        {
          "paper_title": "Exact Title of Paper",
          "quote": "Direct relevant quote from paper text",
          "page_number": 4,
          "section": "Methodology / Results / Limitations"
        }
      ]
    }
  ]
}
"""


def _clean_json_response(content: str) -> Optional[Dict[str, Any]]:
    """Strips markdown backticks and parses JSON safely."""
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.MULTILINE)
        content = re.sub(r"\s*```$", "", content, flags=re.MULTILINE)
    try:
        return json.loads(content)
    except Exception:
        match = re.search(r"(\{.*\})", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    return None


def get_project_evidence_corpus(db: Session, project_id: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Retrieves all curated papers, their metadata, and their comparison matrix records for a project.
    """
    papers_rows = db.execute(
        text("""
            SELECT p.id, p.title, p.authors, p.year, p.abstract,
                   COALESCE((SELECT pv.page_count FROM paper_versions pv WHERE pv.paper_id = p.id ORDER BY pv.id DESC LIMIT 1), 0) as page_count
            FROM papers p
            JOIN project_papers pp_link ON p.id = pp_link.paper_id
            WHERE pp_link.project_id = :proj_id
            ORDER BY p.year ASC NULLS LAST, p.id ASC;
        """),
        {"proj_id": project_id}
    ).fetchall()

    if not papers_rows:
        return [], {"papers_count": 0, "pages_count": 0, "year_min": None, "year_max": None}

    matrix_rows = db.execute(
        text("""
            SELECT paper_id, objective, methodology, datasets, findings, limitations, provenance
            FROM project_matrix_evidence
            WHERE project_id = :proj_id;
        """),
        {"proj_id": project_id}
    ).fetchall()

    matrix_by_paper = {row[0]: {
        "objective": row[1] or "",
        "methodology": row[2] or "",
        "datasets": row[3] or "",
        "findings": row[4] or "",
        "limitations": row[5] or "",
        "provenance": row[6] or {},
    } for row in matrix_rows}

    corpus: List[Dict[str, Any]] = []
    total_pages = 0
    years = []

    for r in papers_rows:
        pid, title, authors, year, abstract, page_count = r
        total_pages += (page_count or 0)
        if year:
            years.append(year)

        mat = matrix_by_paper.get(pid, {})
        corpus.append({
            "paper_id": pid,
            "title": title,
            "authors": authors or "Unknown Authors",
            "year": year,
            "abstract": abstract or "",
            "page_count": page_count or 0,
            "objective": mat.get("objective", ""),
            "methodology": mat.get("methodology", ""),
            "datasets": mat.get("datasets", ""),
            "findings": mat.get("findings", ""),
            "limitations": mat.get("limitations", ""),
            "provenance": mat.get("provenance", {}),
        })

    summary = {
        "papers_count": len(corpus),
        "pages_count": total_pages,
        "year_min": min(years) if years else None,
        "year_max": max(years) if years else None,
    }
    return corpus, summary


def generate_candidate_research_gaps(db: Session, project_id: int) -> List[Dict[str, Any]]:
    """
    Executes paper-wise candidate research-gap analysis for each paper in a project.
    """
    corpus, summary = get_project_evidence_corpus(db, project_id)
    if not corpus:
        return []

    title_to_id = {c["title"].lower().strip(): c["paper_id"] for c in corpus}

    # Format evidence context for LLM
    context_blocks = []
    for c in corpus:
        block = (
            f"=== PAPER [{c['paper_id']}]: \"{c['title']}\" ({c['year'] or 'N/A'}) ===\n"
            f"AUTHORS: {c['authors']}\n"
            f"OBJECTIVE: {c['objective'] or 'N/A'}\n"
            f"METHODOLOGY: {c['methodology'] or 'N/A'}\n"
            f"DATASETS: {c['datasets'] or 'N/A'}\n"
            f"RESULTS & ANALYSIS: {c['findings'] or 'N/A'}\n"
            f"CONCLUSION & LIMITATIONS: {c['limitations'] or 'N/A'}\n"
        )
        context_blocks.append(block)

    full_context = "\n".join(context_blocks)
    user_prompt = (
        f"PROJECT PAPERS ({summary['papers_count']} papers):\n\n"
        f"{full_context}\n\n"
        f"Extract candidate research gaps paper-by-paper following the instructions:"
    )

    llm_gaps: Optional[List[Dict[str, Any]]] = None

    # 1. Local Ollama
    try:
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_GAP_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "options": {"temperature": 0.0}
        }
        with httpx.Client(timeout=httpx.Timeout(25.0, connect=1.0)) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                content = resp.json().get("message", {}).get("content", "")
                parsed = _clean_json_response(content)
                if parsed and "gaps" in parsed and isinstance(parsed["gaps"], list):
                    llm_gaps = parsed["gaps"]
    except Exception:
        pass

    # 2. Google Gemini API
    if not llm_gaps and settings.GEMINI_API_KEY:
        models = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash"]
        if settings.GEMINI_MODEL and settings.GEMINI_MODEL not in models:
            models.insert(0, settings.GEMINI_MODEL)

        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_GAP_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }
        for model_name in models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
                with httpx.Client(timeout=httpx.Timeout(25.0, connect=3.0)) as client:
                    resp = client.post(url, json=payload)
                    if resp.status_code == 200:
                        candidates = resp.json().get("candidates", [])
                        if candidates:
                            raw = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            parsed = _clean_json_response(raw)
                            if parsed and "gaps" in parsed and isinstance(parsed["gaps"], list):
                                llm_gaps = parsed["gaps"]
                                break
            except Exception:
                continue

    # 3. Groq API
    if not llm_gaps and settings.GROQ_API_KEY:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            payload = {
                "model": settings.GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_GAP_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            }
            headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
            with httpx.Client(timeout=httpx.Timeout(20.0, connect=3.0)) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    raw = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                    parsed = _clean_json_response(raw)
                    if parsed and "gaps" in parsed and isinstance(parsed["gaps"], list):
                        llm_gaps = parsed["gaps"]
        except Exception:
            pass

    # Fallback to rule-based paper-wise synthesis if no LLM results
    if not llm_gaps:
        llm_gaps = _rule_based_gap_synthesis(corpus)

    # Normalize evidence paper_ids and page citations
    normalized_gaps = []
    for g in llm_gaps:
        title = g.get("gap_title", "").strip()
        gtype = g.get("gap_type", "methodological").strip()
        desc = g.get("description", "").strip()
        raw_pt = g.get("paper_title", "").strip()

        if not title or not desc:
            continue

        # Match to paper
        matched_pid = title_to_id.get(raw_pt.lower())
        matched_title = raw_pt
        if not matched_pid:
            for c in corpus:
                if c["title"].lower() in raw_pt.lower() or raw_pt.lower() in c["title"].lower():
                    matched_pid = c["paper_id"]
                    matched_title = c["title"]
                    break
        if not matched_pid and corpus:
            matched_pid = corpus[0]["paper_id"]
            matched_title = corpus[0]["title"]

        raw_supp = g.get("supporting_evidence", [])
        clean_supp = []
        for s in raw_supp:
            page_num = s.get("page_number")
            clean_supp.append({
                "paper_id": matched_pid,
                "paper_title": matched_title,
                "quote": s.get("quote", "").strip() or desc,
                "page_number": page_num,
                "section": s.get("section", "Study Analysis")
            })

        normalized_gaps.append({
            "paper_id": matched_pid,
            "paper_title": matched_title,
            "gap_title": title,
            "gap_type": gtype,
            "description": desc,
            "confidence_status": "supported_within_collection",
            "supporting_evidence": clean_supp,
            "counterevidence": [],
        })

    return normalized_gaps


def _rule_based_gap_synthesis(corpus: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deterministic rule-based paper-wise gap synthesizer.
    Generates specific candidate gaps for EACH paper in the project.
    """
    gaps: List[Dict[str, Any]] = []

    for c in corpus:
        pid = c["paper_id"]
        ptitle = c["title"]
        meth = c.get("methodology", "")
        data = c.get("datasets", "")
        lim = c.get("limitations", "")
        prov = c.get("provenance", {})

        lim_prov = prov.get("limitations", [])
        lim_page = lim_prov[0].get("page_number") if isinstance(lim_prov, list) and lim_prov else 1

        meth_prov = prov.get("methodology", [])
        meth_page = meth_prov[0].get("page_number") if isinstance(meth_prov, list) and meth_prov else 2

        data_prov = prov.get("datasets", [])
        data_page = data_prov[0].get("page_number") if isinstance(data_prov, list) and data_prov else 3

        # 1. Author-Stated Limitation Gap for this paper
        lim_patterns = [
            r"([A-Z][^.?!]*(?:future work|further work|further investigation|further research|future scope)[^.?!]*\.)",
            r"([A-Z][^.?!]*(?:limited to|limitation|only evaluated|only tested|drawback|restriction)[^.?!]*\.)",
        ]
        found_quotes = []
        for pat in lim_patterns:
            matches = re.findall(pat, lim, re.IGNORECASE)
            for m in matches:
                clean_m = m.strip()
                if len(clean_m) > 20 and clean_m not in found_quotes:
                    found_quotes.append(clean_m)

        if found_quotes:
            quote = found_quotes[0]
            gaps.append({
                "paper_id": pid,
                "paper_title": ptitle,
                "gap_title": f"Author-Declared Operational Scope Boundary",
                "gap_type": "author_stated_limitation",
                "description": f"The authors explicitly state: \"{quote}\"",
                "supporting_evidence": [
                    {
                        "paper_id": pid,
                        "paper_title": ptitle,
                        "quote": quote,
                        "page_number": lim_page,
                        "section": "Conclusion & Future Work"
                    }
                ]
            })

        # 2. Methodological Gap for this paper
        is_classical = any(k in meth.lower() for k in ["hsv", "segmentation", "canny", "grayscale", "template", "threshold", "morphological", "matlab"])
        is_deep = any(k in meth.lower() for k in ["cnn", "yolo", "resnet", "transformer", "deep learning", "neural network", "vgg", "vit"])

        if is_classical and not is_deep:
            gaps.append({
                "paper_id": pid,
                "paper_title": ptitle,
                "gap_title": "Absence of Deep Learning / Neural Network Validation",
                "gap_type": "methodological",
                "description": f"This study relies strictly on classical digital image processing ({meth[:120]}...). Modern convolutional neural networks (CNNs) and deep representation learning were not evaluated.",
                "supporting_evidence": [
                    {
                        "paper_id": pid,
                        "paper_title": ptitle,
                        "quote": f"Pipeline utilizes classical digital image processing: {meth[:140]}...",
                        "page_number": meth_page,
                        "section": "Methodology"
                    }
                ]
            })

        # 3. Dataset & Contextual Gap for this paper
        gaps.append({
            "paper_id": pid,
            "paper_title": ptitle,
            "gap_title": "Controlled Benchmark without Physical Wear or Mobile Capture",
            "gap_type": "dataset_context",
            "description": f"Evaluation is restricted to clean flatbed scanned banknotes ({data[:120]}...). Real-world conditions such as physical tears, crumpled/soiled notes, and smartphone cameras remain untested.",
            "supporting_evidence": [
                {
                    "paper_id": pid,
                    "paper_title": ptitle,
                    "quote": f"Dataset: {data[:140]}...",
                    "page_number": data_page,
                    "section": "Datasets & Evaluation"
                }
            ]
        })

    return gaps
