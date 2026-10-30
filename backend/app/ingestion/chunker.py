import re
import hashlib
from typing import List, Dict, Any


def calculate_chunk_hash(paper_version_id: int, page_number: int, chunk_index: int, content: str) -> str:
    """Computes deterministic SHA-256 hash for a chunk."""
    raw = f"{paper_version_id}:{page_number}:{chunk_index}:{content.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def split_into_sentences(text: str) -> List[str]:
    """
    Splits text into clean, complete sentences while protecting common academic abbreviations.
    Normalizes intra-paragraph linebreaks and broken hyphenated words.
    """
    clean = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
    clean = re.sub(r'(?<!\n)\n(?!\n)', ' ', clean)
    clean = re.sub(r'[ \t]+', ' ', clean).strip()

    candidates = re.split(r'([.?!]+(?:\s+|\n+))', clean)
    sentences = []
    current = ""
    abbrevs = {
        "fig.", "tab.", "ref.", "eq.", "et al.", "e.g.", "i.e.", "vs.",
        "dr.", "prof.", "al.", "approx.", "no.", "vol.", "pp.", "dept."
    }

    for part in candidates:
        current += part
        words = current.strip().split()
        last_word = words[-1].lower() if words else ""
        if last_word in abbrevs:
            continue
        if re.search(r'[.?!]+(?:\s+|\n+)$', part):
            s = current.strip()
            if s:
                sentences.append(s)
            current = ""

    if current.strip():
        sentences.append(current.strip())

    return sentences


def chunk_text(
    text: str,
    page_number: int,
    start_chunk_index: int = 0,
    target_chunk_size: int = 600,
    chunk_overlap: int = 120,
) -> List[Dict[str, Any]]:
    """
    Splits text from a single page into overlapping semantic chunks.
    Preserves whole sentences so chunks never start or end mid-word or mid-sentence.
    """
    sentences = split_into_sentences(text)
    if not sentences:
        return []

    # If all sentences combined fit under target_chunk_size, return as single chunk
    total_len = sum(len(s) for s in sentences) + len(sentences) - 1
    if total_len <= target_chunk_size:
        return [{
            "chunk_index": start_chunk_index,
            "page_number": page_number,
            "content": " ".join(sentences),
            "character_start": 0,
            "character_end": total_len,
        }]

    chunks: List[Dict[str, Any]] = []
    current_index = start_chunk_index
    i = 0
    n = len(sentences)

    while i < n:
        chunk_sentences = []
        cur_len = 0
        j = i
        while j < n:
            s_len = len(sentences[j])
            if chunk_sentences and (cur_len + s_len + 1 > target_chunk_size):
                break
            chunk_sentences.append(sentences[j])
            cur_len += s_len + 1
            j += 1

        if not chunk_sentences and j < n:
            chunk_sentences.append(sentences[j])
            cur_len = len(sentences[j])
            j += 1

        chunk_content = " ".join(chunk_sentences).strip()
        if len(chunk_content) >= 20:
            chunks.append({
                "chunk_index": current_index,
                "page_number": page_number,
                "content": chunk_content,
                "character_start": 0,
                "character_end": len(chunk_content),
            })
            current_index += 1

        if j >= n:
            break

        # Calculate overlap in complete sentences
        overlap_sentences = 0
        overlap_chars = 0
        k = j - 1
        while k > i:
            cand_len = len(sentences[k])
            if overlap_chars + cand_len <= chunk_overlap or overlap_sentences == 0:
                overlap_chars += cand_len
                overlap_sentences += 1
                k -= 1
            else:
                break

        # Advance i
        if overlap_sentences > 0:
            i = j - overlap_sentences
        else:
            i = j

    return chunks


def chunk_paper_pages(
    pages: List[Dict[str, Any]],
    target_chunk_size: int = 600,
    chunk_overlap: int = 120,
) -> List[Dict[str, Any]]:
    """
    Processes all extracted pages for a paper version and generates
    sequential, page-anchored chunks with global chunk indices.
    """
    all_chunks: List[Dict[str, Any]] = []
    chunk_index_counter = 0

    # Ensure pages are ordered by page_number
    sorted_pages = sorted(pages, key=lambda p: p.get("page_number", 0))

    for p in sorted_pages:
        page_num = p.get("page_number", 1)
        content = p.get("content", "")
        page_chunks = chunk_text(
            text=content,
            page_number=page_num,
            start_chunk_index=chunk_index_counter,
            target_chunk_size=target_chunk_size,
            chunk_overlap=chunk_overlap,
        )
        for c in page_chunks:
            all_chunks.append(c)
            chunk_index_counter += 1

    return all_chunks
