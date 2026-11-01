import json
import re
from typing import Dict, Any, Optional, List, Tuple
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings

SYSTEM_MATRIX_PROMPT = """You are an expert scientific literature reviewer for LitScope.
Your task is to analyze the provided research paper passages and extract structured comparative evidence across 5 core research dimensions.

STRICT INSTRUCTIONS:
1. Extract factual information based ONLY on the provided evidence passages. Do NOT extrapolate or assume.
2. For each field, provide:
   - "summary": A well-formed, complete academic summary (1-3 complete grammatical sentences). Each summary MUST begin cleanly with a clear subject and end with proper terminal punctuation (period). Never start abruptly with dangling conjunctions or cut off mid-thought; retain the full context of the claim.
   - "page": The exact integer page number where this evidence is grounded (or null if absent).
   - "quote": A brief verbatim sentence or phrase from the text confirming this claim.
3. If a dimension is not reported or cannot be determined from the passages, set "summary" to "Not explicitly reported in retrieved passages" and "page" to null.
4. Output MUST be a single valid JSON object strictly matching this schema:

{
  "objective": {
    "summary": "Core research question, problem statement, or goal addressed.",
    "page": 1,
    "quote": "Direct quote from text"
  },
  "methodology": {
    "summary": "Core algorithm, model architecture, mathematical framework, or experimental design.",
    "page": 2,
    "quote": "Direct quote from text"
  },
  "datasets": {
    "summary": "Specific datasets, benchmarks, sample sizes, or corpora used for evaluation.",
    "page": 4,
    "quote": "Direct quote from text"
  },
  "findings": {
    "summary": "Result & Analysis: Core findings, experimental outcomes, results, or evaluation analysis reported in the paper. Look under sections or headings such as 'Results', 'Result', 'Result & Analysis', 'Performance Analysis', 'Experimental Results', 'Evaluation', 'Testing', or 'Discussion'. If quantitative metrics (accuracy %, benchmark numbers, error rates, speed/latency) are reported, extract those figures; if the study reports qualitative or functional evaluation (e.g. system successfully tested on 100/500/1000 Rs notes, recognized genuine vs counterfeit notes, displayed result in GUI/LCD), synthesize those experimental outcomes. NEVER return 'Not explicitly reported' if the paper contains a Results, Performance Analysis, or Evaluation section.",
    "page": 4,
    "quote": "Direct quote from text"
  },
  "conclusion": {
    "summary": "Conclusion: Synthesized research conclusions, core takeaways, and experimental validation from the paper's conclusion section. Provide a coherent, multi-sentence academic summary (2-3 complete sentences capturing the full scope of what was demonstrated and concluded, not just the first few words or first line).",
    "page": 8,
    "quote": "Direct quote from text"
  }
}
"""


def gather_paper_evidence_context(db: Session, paper_id: int) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Selects representative evidence chunks across paper pages for structured matrix extraction.
    Uses pattern matching and keyword scoring to ensure chunks containing experimental metrics,
    accuracy/percentages, evaluation tables, and comparative benchmarks are retrieved even
    when explicit section headings are absent.

    Specifically locates the Conclusion section while filtering out bibliography/references.
    """
    chunks_rows = db.execute(
        text("""
            SELECT id, page_number, chunk_index, content
            FROM paper_chunks
            WHERE paper_id = :pid
            ORDER BY page_number ASC, chunk_index ASC;
        """),
        {"pid": paper_id}
    ).fetchall()

    passages: List[Dict[str, Any]] = []

    if chunks_rows:
        total = len(chunks_rows)
        selected_indices = set()

        # 1. Always include early chunks (Title, Abstract, Introduction, Objective)
        for i in range(min(2, total)):
            selected_indices.add(i)

        # Patterns for identification and filtering
        ref_pattern = re.compile(
            r"\b(?:references|bibliography|works cited|literature cited)\b|doi:\s*10\.\d+|vol\.\s*\d+,\s*no\.\s*\d+",
            re.IGNORECASE
        )
        conclusion_heading_pattern = re.compile(
            r"\b(?:conclusion|conclusions|concluding remarks|conclusions and future work|summary and conclusion|discussion and conclusions?)\b",
            re.IGNORECASE
        )
        conclusion_phrase_pattern = re.compile(
            r"\b(?:in conclusion|to conclude|we conclude|this work demonstrated|this research demonstrates|future work|limitations?|overall,\s+the\s+findings|in this study)\b",
            re.IGNORECASE
        )
        metric_pattern = re.compile(
            r"\b(?:\d+(?:\.\d+)?%|accuracy|precision|recall|f1(?:-score)?|auc|roc|bleu|rouge|map|rmse|mae|latency|throughput|error rate|fps|sota|baseline|outperform|outperformed|surpassed|achieved|improvement|benchmark|table\s+\d+|figure\s+\d+|p\s*<\s*0\.0\d+)\b",
            re.IGNORECASE
        )
        method_pattern = re.compile(
            r"\b(?:architecture|algorithm|pipeline|neural network|transformer|framework|dataset|corpus|samples|experiment|baseline|evaluated)\b",
            re.IGNORECASE
        )

        # 2. Specifically score and prioritize Conclusion chunks (excluding reference lists)
        conclusion_scores: List[Tuple[int, int]] = []
        for idx, row in enumerate(chunks_rows):
            text_c = row[3]
            bracket_cites = len(re.findall(r"\[\d+\]", text_c))
            if bracket_cites >= 4 or text_c.strip().startswith("REFERENCES") or text_c.strip().startswith("References"):
                continue  # skip bibliography chunks

            c_score = 0
            if conclusion_heading_pattern.search(text_c):
                c_score += 15
            if conclusion_phrase_pattern.search(text_c):
                c_score += 8

            if c_score > 0:
                conclusion_scores.append((idx, c_score))

        conclusion_scores.sort(key=lambda x: x[1], reverse=True)
        # Add top 3 conclusion chunks
        for idx, _ in conclusion_scores[:3]:
            selected_indices.add(idx)

        # If no explicit conclusion chunk found, walk backwards from end skipping bibliography
        if not conclusion_scores and total > 2:
            added_late = 0
            for rev_idx in range(total - 1, -1, -1):
                text_c = chunks_rows[rev_idx][3]
                bracket_cites = len(re.findall(r"\[\d+\]", text_c))
                if bracket_cites < 4 and not text_c.strip().startswith("REFERENCES"):
                    selected_indices.add(rev_idx)
                    added_late += 1
                    if added_late >= 2:
                        break

        # 3. Specifically score and prioritize Result & Analysis chunks (Results, Performance Analysis, Evaluation)
        result_heading_pattern = re.compile(
            r"\b(?:(?:[ivx]+\.|\d+\.)?\s*(?:results?|result\s*(?:&|and)\s*analysis|results?\s*(?:&|and)\s*discussion|experimental\s*(?:results?|evaluation|analysis|validation)|experiments?|performance\s*(?:analysis|evaluation|results?)|simulation\s*(?:results?|analysis)|system\s*(?:evaluation|testing)|evaluation(?:\s*results?)?|test\s*results?|findings|comparative\s*analysis))\b",
            re.IGNORECASE
        )
        result_phrase_pattern = re.compile(
            r"\b(?:results?\s*(?:show|demonstrate|indicate|obtained|reveal|confirm|achieved|displayed)|in this section result|performance\s*analysis|recognition\s*of\s*(?:genuine|fake)|recognised\s*as\s*(?:genuine|fake)|correctly\s*(?:identified|recognised|detected)|evaluation\s*shows?|test\s*results?|confusion\s*matrix|error\s*rate|accuracy\s*of)\b",
            re.IGNORECASE
        )

        result_scores: List[Tuple[int, int]] = []
        for idx, row in enumerate(chunks_rows):
            if idx in selected_indices:
                continue
            text_content = row[3]
            h_matches = len(result_heading_pattern.findall(text_content))
            p_matches = len(result_phrase_pattern.findall(text_content))
            m_matches = len(metric_pattern.findall(text_content))
            has_pct = len(re.findall(r"\d+(?:\.\d+)?%", text_content))
            r_score = (h_matches * 20) + (p_matches * 8) + (m_matches * 3) + (has_pct * 5)
            if r_score > 0:
                result_scores.append((idx, r_score))

        result_scores.sort(key=lambda x: x[1], reverse=True)
        # Add top 4 result chunks (and continuation chunk if heading was matched)
        for idx, _ in result_scores[:4]:
            selected_indices.add(idx)
            if idx + 1 < total:
                selected_indices.add(idx + 1)

        # 4. Score remaining chunks for methodology & datasets
        method_scores: List[Tuple[int, int]] = []
        for idx, row in enumerate(chunks_rows):
            if idx in selected_indices:
                continue
            text_content = row[3]
            meth_score = len(method_pattern.findall(text_content))
            if meth_score > 0:
                method_scores.append((idx, meth_score))

        method_scores.sort(key=lambda x: x[1], reverse=True)
        for idx, _ in method_scores[:2]:
            selected_indices.add(idx)

        chosen = [chunks_rows[i] for i in sorted(selected_indices) if i < total]
        for row in chosen:
            passages.append({
                "page": row[1],
                "content": row[3].strip()
            })
    else:
        # Fall back to canonical paper abstract
        paper_row = db.execute(
            text("SELECT title, abstract FROM papers WHERE id = :pid;"),
            {"pid": paper_id}
        ).mappings().fetchone()

        if paper_row and paper_row["abstract"]:
            passages.append({
                "page": 1,
                "content": f"Title: {paper_row['title']}\n\nAbstract: {paper_row['abstract']}"
            })

    formatted_context_list = []
    for idx, p in enumerate(passages, 1):
        formatted_context_list.append(f"--- PASSAGE [{idx}] (Page {p['page']}) ---\n{p['content']}")

    return "\n\n".join(formatted_context_list), passages


def _clean_json_response(raw_text: str) -> Optional[Dict[str, Any]]:
    """Cleans model output and parses JSON safely."""
    if not raw_text:
        return None
    cleaned = raw_text.strip()
    # Strip markdown code blocks
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"```$", "", cleaned, flags=re.MULTILINE).strip()

    try:
        return json.loads(cleaned)
    except Exception:
        # Fallback regex search for outer JSON object
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    return None


def _call_llm_for_matrix(context: str, paper_title: str) -> Optional[Dict[str, Any]]:
    """Routes structured extraction request to available LLM provider."""
    user_prompt = f"PAPER TITLE: {paper_title}\n\nEVIDENCE PASSAGES:\n{context}\n\nExtract the structured comparative evidence JSON:"

    # 1. Local Ollama
    try:
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_MATRIX_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "options": {"temperature": 0.0}
        }
        with httpx.Client(timeout=httpx.Timeout(20.0, connect=1.0)) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                content = resp.json().get("message", {}).get("content", "")
                parsed = _clean_json_response(content)
                if parsed and "objective" in parsed:
                    return parsed
    except Exception:
        pass

    # 2. Google Gemini API
    if settings.GEMINI_API_KEY:
        models = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash"]
        if settings.GEMINI_MODEL and settings.GEMINI_MODEL not in models:
            models.insert(0, settings.GEMINI_MODEL)

        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_MATRIX_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
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
                            if parsed and "objective" in parsed:
                                return parsed
            except Exception:
                continue

    # 3. Groq API
    if settings.GROQ_API_KEY:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            payload = {
                "model": settings.GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_MATRIX_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.0,
                "response_format": {"type": "json_object"}
            }
            headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
            with httpx.Client(timeout=httpx.Timeout(20.0, connect=3.0)) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    raw = resp.json()["choices"][0]["message"]["content"]
                    parsed = _clean_json_response(raw)
                    if parsed and "objective" in parsed:
                        return parsed
        except Exception:
            pass

    return None


def _format_complete_sentence(text: str, max_chars: int = 350) -> str:
    """
    Ensures extracted text forms complete, natural grammatical sentences:
    - Strips leading fragments, lone conjunctions ('and', 'or', 'but'), numbers, or bracketed citations.
    - Capitalizes the opening word properly.
    - Preserves full context and avoids mid-word or mid-clause truncation.
    - Guarantees termination with a valid punctuation mark (. ! ?).
    """
    if not text:
        return ""
    cleaned = " ".join(text.split()).strip()

    # 1. Clean abrupt starts (leading numbers, bracketed citations, lone conjunctions, punctuation)
    cleaned = re.sub(r'^(?:\[\d+(?:,\s*\d+)*\]|\(\d{4}\)|[\d\.\-\)\:\,\;\s]+)+', '', cleaned)
    cleaned = re.sub(r'^(?:and|or|but|furthermore|moreover|also|where|which|that|in\s+addition,?\s*)\s+', '', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip()

    if not cleaned:
        return ""

    # Capitalize the first character
    if cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]

    # 2. If within limit and ends with punctuation, return directly
    if len(cleaned) <= max_chars and cleaned.endswith(('.', '!', '?')):
        return cleaned

    # If within limit but missing terminal punctuation, add '.'
    if len(cleaned) <= max_chars:
        return cleaned.rstrip(',;:- ') + '.'

    # Pattern for true sentence-ending punctuation (avoids decimals like 94.2% or abbreviations like et al.)
    pattern = r'(?<!\d)(?<!et al)(?<!e\.g)(?<!i\.e)(?<!Fig)(?<![A-Z])[\.!\?](?:\s+|$)'

    sub = cleaned[:max_chars]
    matches = [m.end() for m in re.finditer(pattern, sub)]
    if matches and matches[-1] >= 40:
        return cleaned[:matches[-1]].strip()

    # If full sentence finishes within next 100 characters, include it
    extended = cleaned[:max_chars + 100]
    ext_matches = [m.end() for m in re.finditer(pattern, extended)]
    if ext_matches and ext_matches[-1] >= 40:
        return cleaned[:ext_matches[-1]].strip()

    # Otherwise slice cleanly at last word boundary
    last_space = sub.rfind(' ')
    if last_space > 40:
        return sub[:last_space].rstrip(',;:- ') + '.'
    return sub.rstrip(',;:- ') + '.'


def _rule_based_fallback_extraction(context: str, paper_title: str) -> Dict[str, Any]:
    """Deterministic heuristic extraction if no LLM inference server is reachable."""
    sentences = re.split(r"(?<=[.!?])\s+", context)

    objective = "Investigates problem statement and experimental setup detailed in study."
    methodology = "Proposed architecture and experimental methodology detailed in text."
    datasets = "Evaluated on standard benchmarks and empirical datasets referenced in paper."
    findings = "Quantitative experimental evaluation and findings detailed in paper."
    limitations = "Synthesizes experimental conclusions and constraints discussed in study."

    best_finding_score = 0

    metric_kw = ["accuracy", "f1", "f-score", "precision", "recall", "auc", "roc", "bleu", "rouge",
                 "error rate", "outperform", "outperformed", "achieves", "achieved", "improvement",
                 "baseline", "benchmark", "results show", "empirical", "table", "state-of-the-art"]

    for s in sentences:
        s_clean = s.strip()
        if len(s_clean) < 15 or len(s_clean) > 350:
            continue
        lower = s_clean.lower()

        # Objective
        if any(k in lower for k in ["we propose", "in this paper we", "our goal", "this work presents", "we introduce", "this study aims"]):
            objective = _format_complete_sentence(s_clean, 350)

        # Methodology
        elif any(k in lower for k in ["methodology", "architecture", "algorithm", "neural network", "pipeline", "framework"]):
            methodology = _format_complete_sentence(s_clean, 350)

        # Datasets
        elif any(k in lower for k in ["dataset", "benchmark", "corpus", "samples", "collected from", "training set"]):
            datasets = _format_complete_sentence(s_clean, 350)

        # Result & Analysis scoring
        score = sum(1 for k in metric_kw if k in lower)
        has_pct = len(re.findall(r"\d+(?:\.\d+)?%", s_clean))
        has_num = bool(re.search(r"\b\d+(?:\.\d+)?\b", s_clean))
        total_m_score = score + (has_pct * 3) + (1 if has_num and score > 0 else 0)

        if total_m_score > best_finding_score:
            best_finding_score = total_m_score
            findings = _format_complete_sentence(s_clean, 350)

    # Robust Multi-Sentence Result & Analysis Section Extraction
    result_match = re.search(
        r"(?:(?:\b(?:v|vi|vii|iv|iii|\d+)\.\s*)?(?:results?|result\s*(?:&|and)\s*analysis|results?\s*(?:&|and)\s*discussion|experimental\s*(?:results?|evaluation)|performance\s*(?:analysis|evaluation)|evaluation(?:\s*results?)?|test\s*results?)\s*[:\.\-]?\s*)(.+?)(?=(?:\b(?:v|vi|vii|iv|iii|\d+)\.\s*(?:conclusion|acknowledg|references|discussion)\b|\b(?:conclusion|acknowledgment|references)\b|\Z))",
        context,
        re.IGNORECASE | re.DOTALL
    )
    if result_match:
        result_raw = result_match.group(1).strip()
        clean_r = re.sub(r"(?:Fig(?:\.|ure)?\s*[-]?\d+\.?|Table\s*\d+\.?).*?(?=\.|\n|$)", "", result_raw)
        clean_r = re.sub(r"---+.*?---+", "", clean_r)
        clean_r = " ".join(clean_r.split())
        r_sentences = [rs.strip() for rs in re.split(r"(?<=[.!?])\s+", clean_r) if len(rs.strip()) > 15]
        if r_sentences:
            findings = _format_complete_sentence(" ".join(r_sentences[:3]), 400)

    # Robust Multi-Sentence Conclusion Extraction
    conclusion_match = re.search(
        r"(?:(?:\b(?:v|vi|vii|iv|iii)\.\s*)?conclusion[s]?(?:\s*(?:and|&)\s*future\s*work)?\s*[:\.\-]?\s*)(.+?)(?=(?:\b(?:references|bibliography|acknowledg|appendix)\b|\Z))",
        context,
        re.IGNORECASE | re.DOTALL
    )
    if conclusion_match:
        conclusion_raw = conclusion_match.group(1).strip()
        clean_c = re.sub(r"(?:Fig(?:\.|ure)?\s*\d+\.?|Table\s*\d+\.?).*?(?=\.|\n|$)", "", conclusion_raw)
        c_sentences = [cs.strip() for cs in re.split(r"(?<=[.!?])\s+", clean_c) if len(cs.strip()) > 20]
        if c_sentences:
            limitations = _format_complete_sentence(" ".join(c_sentences[:3]), 400)
    else:
        conclusion_kw = [
            "in conclusion", "to conclude", "conclude that", "in summary",
            "this research demonstrates", "this work demonstrates", "we demonstrated",
            "findings indicate", "overall, the findings", "limitation", "threats to validity"
        ]
        best_c_score = 0
        for i, s in enumerate(sentences):
            s_clean = s.strip()
            if len(s_clean) < 20:
                continue
            lower = s_clean.lower()
            c_score = sum(1 for k in conclusion_kw if k in lower)
            if c_score > best_c_score:
                best_c_score = c_score
                next_s = sentences[i+1].strip() if i+1 < len(sentences) and len(sentences[i+1].strip()) > 15 else ""
                combined = f"{s_clean} {next_s}".strip() if next_s else s_clean
                limitations = _format_complete_sentence(combined, 400)

    return {
        "objective": {"summary": objective, "page": 1, "quote": None},
        "methodology": {"summary": methodology, "page": 2, "quote": None},
        "datasets": {"summary": datasets, "page": 3, "quote": None},
        "findings": {"summary": findings, "page": 4, "quote": None},
        "limitations": {"summary": limitations, "page": 5, "quote": None},
    }


def extract_paper_matrix_evidence(
    db: Session,
    project_id: int,
    paper_id: int,
    force_reextract: bool = False
) -> Dict[str, Any]:
    """
    Extracts structured comparative dimensions for a single paper within a project.
    Persists and caches the result in project_matrix_evidence.
    """
    # 1. Check existing record
    existing = db.execute(
        text("""
            SELECT id, objective, methodology, datasets, findings, limitations,
                   provenance, is_custom_edited, status, error_message, updated_at
            FROM project_matrix_evidence
            WHERE project_id = :pid AND paper_id = :paper_id;
        """),
        {"pid": project_id, "paper_id": paper_id}
    ).mappings().fetchone()

    if existing and existing["status"] == "completed" and not force_reextract:
        return dict(existing)

    # 2. Gather paper title and context
    paper_row = db.execute(
        text("SELECT title FROM papers WHERE id = :pid;"),
        {"pid": paper_id}
    ).mappings().fetchone()

    if not paper_row:
        raise ValueError(f"Paper ID {paper_id} not found")

    context, passages = gather_paper_evidence_context(db, paper_id)

    # 3. Run extraction
    extracted_json = _call_llm_for_matrix(context, paper_row["title"])
    if not extracted_json:
        extracted_json = _rule_based_fallback_extraction(context, paper_row["title"])

    # 4. Normalize fields and provenance
    obj_item = extracted_json.get("objective") or {}
    meth_item = extracted_json.get("methodology") or {}
    data_item = extracted_json.get("datasets") or {}
    find_item = extracted_json.get("findings") or {}
    lim_item = extracted_json.get("conclusion") or extracted_json.get("limitations") or {}

    objective_text = obj_item.get("summary") if isinstance(obj_item, dict) else str(obj_item or "")
    methodology_text = meth_item.get("summary") if isinstance(meth_item, dict) else str(meth_item or "")
    datasets_text = data_item.get("summary") if isinstance(data_item, dict) else str(data_item or "")
    findings_text = find_item.get("summary") if isinstance(find_item, dict) else str(find_item or "")
    limitations_text = lim_item.get("summary") if isinstance(lim_item, dict) else str(lim_item or "")

    # Ensure answers have no abrupt starts or cut-offs and retain complete context
    if objective_text and "not explicitly reported" not in objective_text.lower():
        objective_text = _format_complete_sentence(objective_text, 350)
    if methodology_text and "not explicitly reported" not in methodology_text.lower():
        methodology_text = _format_complete_sentence(methodology_text, 350)
    if datasets_text and "not explicitly reported" not in datasets_text.lower():
        datasets_text = _format_complete_sentence(datasets_text, 350)
    if findings_text and "not explicitly reported" not in findings_text.lower():
        findings_text = _format_complete_sentence(findings_text, 400)
    if limitations_text and "not explicitly reported" not in limitations_text.lower():
        limitations_text = _format_complete_sentence(limitations_text, 400)

    provenance_map = {
        "objective": {"page": obj_item.get("page"), "quote": obj_item.get("quote")} if isinstance(obj_item, dict) else {},
        "methodology": {"page": meth_item.get("page"), "quote": meth_item.get("quote")} if isinstance(meth_item, dict) else {},
        "datasets": {"page": data_item.get("page"), "quote": data_item.get("quote")} if isinstance(data_item, dict) else {},
        "findings": {"page": find_item.get("page"), "quote": find_item.get("quote")} if isinstance(find_item, dict) else {},
        "limitations": {"page": lim_item.get("page"), "quote": lim_item.get("quote")} if isinstance(lim_item, dict) else {},
        "conclusion": {"page": lim_item.get("page"), "quote": lim_item.get("quote")} if isinstance(lim_item, dict) else {},
    }

    # 5. Persist into project_matrix_evidence
    upsert_row = db.execute(
        text("""
            INSERT INTO project_matrix_evidence (
                project_id, paper_id, objective, methodology, datasets,
                findings, limitations, provenance, is_custom_edited, status, updated_at
            )
            VALUES (
                :pid, :paper_id, :obj, :meth, :data,
                :find, :lim, CAST(:prov AS JSONB), FALSE, 'completed', CURRENT_TIMESTAMP
            )
            ON CONFLICT (project_id, paper_id) DO UPDATE
            SET objective = EXCLUDED.objective,
                methodology = EXCLUDED.methodology,
                datasets = EXCLUDED.datasets,
                findings = EXCLUDED.findings,
                limitations = EXCLUDED.limitations,
                provenance = EXCLUDED.provenance,
                status = 'completed',
                updated_at = CURRENT_TIMESTAMP
            WHERE project_matrix_evidence.is_custom_edited = FALSE OR :force = TRUE
            RETURNING id, project_id, paper_id, objective, methodology, datasets,
                      findings, limitations, provenance, is_custom_edited, status, updated_at;
        """),
        {
            "pid": project_id,
            "paper_id": paper_id,
            "obj": objective_text,
            "meth": methodology_text,
            "data": datasets_text,
            "find": findings_text,
            "lim": limitations_text,
            "prov": json.dumps(provenance_map),
            "force": force_reextract
        }
    ).mappings().fetchone()

    db.commit()
    return dict(upsert_row)
