import re
import httpx
from typing import List, Dict, Any
from app.core.config import settings


SYSTEM_ACADEMIC_PROMPT = """You are an academic research assistant for LitScope.
Synthesize a clear, rigorous, and direct answer to the user's research question using ONLY the provided evidence passages.

STRICT ACADEMIC GUIDELINES:
1. Every factual claim must be explicitly attributed to its source using the exact citation format provided (e.g. [Paper Title, p. X]).
2. Synthesize findings across multiple papers and pages rather than copy-pasting raw text chunks.
3. Contrast and compare experimental results, methodologies, and limitations where applicable.
4. Do NOT extrapolate, hallucinate, or assume facts not directly stated in the evidence passages.
5. If the provided evidence does not contain sufficient information to answer the question, state:
   "The curated papers in this project do not contain sufficient evidence to answer this question."
6. Write in professional, objective academic prose."""


def format_evidence_context(evidence_chunks: List[Dict[str, Any]]) -> str:
    """Formats retrieved chunks into numbered context blocks with explicit citation headers."""
    passages = []
    for i, c in enumerate(evidence_chunks, 1):
        citation = c.get("citation", f"[{c.get('paper_title', 'Paper')}, p. {c.get('page_number', 1)}]")
        passages.append(f"Passage [{i}] Source: {citation}\n{c.get('content', '').strip()}")
    return "\n\n".join(passages)


def _call_ollama(prompt: str, context: str) -> str | None:
    """Attempts to generate an answer via local Ollama instance."""
    try:
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_ACADEMIC_PROMPT},
                {"role": "user", "content": f"EVIDENCE PASSAGES:\n{context}\n\nRESEARCH QUESTION:\n{prompt}"}
            ],
            "stream": False,
            "options": {"temperature": 0.1}
        }
        with httpx.Client(timeout=httpx.Timeout(20.0, connect=1.0)) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("message", {}).get("content", "").strip()
                if content:
                    return content
    except Exception:
        pass
    return None


def _call_gemini(prompt: str, context: str) -> str | None:
    """Attempts to generate an answer via Google Gemini API if GEMINI_API_KEY is configured."""
    if not settings.GEMINI_API_KEY:
        return None

    # Prioritize flash-lite for sub-second latency and high availability
    models_to_try = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"]
    if settings.GEMINI_MODEL and settings.GEMINI_MODEL not in models_to_try:
        models_to_try.insert(0, settings.GEMINI_MODEL)

    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_ACADEMIC_PROMPT}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"EVIDENCE PASSAGES:\n{context}\n\nRESEARCH QUESTION:\n{prompt}"}]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 4096
        }
    }

    for model_name in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
            with httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
                resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            text = parts[0].get("text", "").strip()
                            if text:
                                return text
        except Exception:
            continue
    return None


def _call_groq(prompt: str, context: str) -> str | None:
    """Attempts to generate an answer via Groq API (fast Llama-3) if GROQ_API_KEY is configured."""
    if not settings.GROQ_API_KEY:
        return None
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
        payload = {
            "model": settings.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_ACADEMIC_PROMPT},
                {"role": "user", "content": f"EVIDENCE PASSAGES:\n{context}\n\nRESEARCH QUESTION:\n{prompt}"}
            ],
            "temperature": 0.1,
            "max_tokens": 1024
        }
        with httpx.Client(timeout=httpx.Timeout(20.0, connect=2.0)) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "").strip()
                    if content:
                        return content
    except Exception:
        pass
    return None


def _call_openai(prompt: str, context: str) -> str | None:
    """Attempts to generate an answer via OpenAI-compatible endpoint if configured."""
    if not settings.OPENAI_API_KEY:
        return None
    try:
        base_url = (settings.OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
        headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
        payload = {
            "model": settings.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_ACADEMIC_PROMPT},
                {"role": "user", "content": f"EVIDENCE PASSAGES:\n{context}\n\nRESEARCH QUESTION:\n{prompt}"}
            ],
            "temperature": 0.1,
            "max_tokens": 1024
        }
        with httpx.Client(timeout=httpx.Timeout(25.0, connect=2.0)) as client:
            resp = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "").strip()
                    if content:
                        return content
    except Exception:
        pass
    return None


def _score_sentence(sentence: str, query_terms: List[str]) -> float:
    s_lower = sentence.lower()
    score = 0.0
    for term in query_terms:
        if term in s_lower:
            score += 1.0 + (len(term) / 10.0)
    return score


def _is_valid_academic_sentence(s: str) -> bool:
    """Filters out raw formulas, table fragments, and isolated section headers."""
    if len(s) < 25 or len(s) > 400:
        return False
    # Filter out pure mathematical formulas
    if re.search(r'P\([A-Za-z0-9_|,\s]+\)\s*=', s) or s.count('=') > 1 or s.endswith('/'):
        return False
    # Filter out uppercase section headers
    if re.match(r'^(?:[IVXLCDM]+\.|\d+\.)\s*[A-Z\s]{4,}$', s):
        return False
    # Filter out table header rows
    if re.search(r'\b(TABLE|FIG|FIGURE)\b', s, re.IGNORECASE) and ('Precision' in s or 'Recall' in s or 'F1' in s):
        return False
    # Must start with a capital letter or quote
    if not (s[0].isupper() or s[0] in ('"', "'")):
        return False
    return True


def _extractive_synthesis(question: str, evidence_chunks: List[Dict[str, Any]]) -> str:
    """
    Intelligent academic extractive synthesis baseline.
    Extracts relevant full sentences matching the question and organizes them
    into coherent, citation-grounded narrative findings.
    """
    stop_words = {
        "what", "was", "the", "of", "using", "and", "in", "to", "for", "a",
        "an", "is", "are", "were", "with", "on", "how", "why", "which", "does", "did"
    }
    raw_terms = [re.sub(r'[^a-z0-9]', '', w.lower()) for w in question.split()]
    q_terms = [w for w in raw_terms if len(w) > 2 and w not in stop_words]
    if "bias" in q_terms and "bayes" not in q_terms:
        q_terms.append("bayes")

    evidence_by_citation: Dict[str, List[str]] = {}

    for chunk in evidence_chunks[:4]:
        citation = chunk.get("citation", f"[{chunk.get('paper_title', 'Paper')}, p. {chunk.get('page_number', 1)}]")
        content = chunk.get("content", "")

        sentences = [s.strip() for s in re.split(r'(?<=[.?!])\s+', content)]
        scored_sentences = []
        for s in sentences:
            if not _is_valid_academic_sentence(s):
                continue
            score = _score_sentence(s, q_terms)
            scored_sentences.append((score, s))

        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        top = [s for score, s in scored_sentences if score > 0][:2]

        if not top and scored_sentences:
            top = [scored_sentences[0][1]]

        if top:
            if citation not in evidence_by_citation:
                evidence_by_citation[citation] = []
            for s in top:
                if s not in evidence_by_citation[citation]:
                    evidence_by_citation[citation].append(s)

    lines = ["Based on the literature curated in this project:\n"]
    for citation, s_list in evidence_by_citation.items():
        joined_text = " ".join(s_list)
        lines.append(f"• According to evidence in {citation}:\n  {joined_text}\n")

    lines.append("*(Note: Running in local extractive mode without an active LLM. For full AI reasoning and narrative synthesis, connect Ollama locally or add a GEMINI_API_KEY / GROQ_API_KEY in backend/.env)*")
    return "\n".join(lines).strip()


def synthesize_answer(
    question: str,
    evidence_chunks: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Synthesizes a grounded answer from retrieved project evidence chunks.
    Extracts citation tags and returns answer text with explicit citations list.
    """
    if not evidence_chunks:
        return {
            "answer": "No papers have been added to this project yet, or no relevant text was found to answer this question.",
            "citations": []
        }

    context = format_evidence_context(evidence_chunks)
    generated_text = None

    # 1. Try local Ollama
    if settings.LLM_PROVIDER in ("auto", "ollama"):
        generated_text = _call_ollama(question, context)

    # 2. Try Gemini
    if not generated_text and settings.LLM_PROVIDER in ("auto", "gemini"):
        generated_text = _call_gemini(question, context)

    # 3. Try Groq
    if not generated_text and settings.LLM_PROVIDER in ("auto", "groq"):
        generated_text = _call_groq(question, context)

    # 4. Try OpenAI
    if not generated_text and settings.LLM_PROVIDER in ("auto", "openai"):
        generated_text = _call_openai(question, context)

    # 5. Deterministic extractive synthesis fallback
    if not generated_text:
        generated_text = _extractive_synthesis(question, evidence_chunks)

    # 6. Extract all citations in [Title, p. X] format
    extracted_citations = re.findall(r'\[([^\]]+,\s*p\.\s*\d+)\]', generated_text)
    if extracted_citations:
        citations = list(dict.fromkeys([f"[{c}]" for c in extracted_citations]))
    else:
        # Fallback: include citations from top evidence chunks
        citations = list(dict.fromkeys([c.get("citation") for c in evidence_chunks if c.get("citation")]))

    return {
        "answer": generated_text,
        "citations": citations
    }
