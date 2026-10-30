import re
import pymupdf
from typing import Dict, Any, List, Union, Optional, Tuple


def _clean_text(text: str) -> str:
    """Normalizes whitespace in a text string."""
    return " ".join(text.split()).strip()


def _is_suspicious_title(title: str) -> bool:
    """Checks whether a metadata title is generic junk or a filename."""
    if not title or len(title) < 4:
        return True
    lower = title.lower()
    junk = ["untitled", "microsoft word", "latex", ".pdf", ".tex", ".dvi", "template", "default"]
    return any(j in lower for j in junk)


def _extract_title_from_page(page: pymupdf.Page) -> Tuple[Optional[str], float]:
    """
    Extracts the document title by finding the largest, prominent font spans
    in the upper portion of the first page.

    Returns:
        (title_string, bottom_y_coordinate_of_title)
    """
    try:
        page_dict = page.get_text("dict")
        blocks = page_dict.get("blocks", [])

        spans_info: List[Dict[str, Any]] = []
        page_height = page.rect.height or 800

        for b in blocks:
            if "lines" not in b:
                continue
            for line in b["lines"]:
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    size = span.get("size", 0.0)
                    bbox = span.get("bbox", (0, 0, 0, 0))
                    # Only consider text in the top 45% of page
                    if text and bbox[1] < page_height * 0.45:
                        if re.match(r'^(arXiv:|ISSN|Vol\.|Proceedings|http|www\.)', text, re.IGNORECASE):
                            continue
                        spans_info.append({
                            "text": text,
                            "size": size,
                            "top": bbox[1],
                            "bottom": bbox[3],
                        })

        if not spans_info:
            return None, 0.0

        max_size = max((s["size"] for s in spans_info), default=0.0)
        if max_size < 12.0:
            return None, 0.0

        # Collect spans matching the largest font size
        title_spans = [
            s["text"] for s in spans_info
            if s["size"] >= max_size - 1.5 and len(s["text"]) > 1
        ]
        title_bottom = max((s["bottom"] for s in spans_info if s["size"] >= max_size - 1.5), default=0.0)

        candidate_title = " ".join(title_spans).strip()
        if 5 <= len(candidate_title) <= 300:
            return _clean_text(candidate_title), title_bottom

    except Exception:
        pass
    return None, 0.0


def _extract_authors_and_year_from_page(
    page: pymupdf.Page,
    title_text: Optional[str],
    title_bottom_y: float
) -> Tuple[Optional[str], Optional[int]]:
    """
    Extracts author names and publication year from page 1 content.
    Identifies authors strictly between title and abstract, filtering out affiliations and emails.
    Extracts year only when present in a clear publication context (e.g. copyright, journal, accepted).
    """
    extracted_author: Optional[str] = None
    extracted_year: Optional[int] = None

    try:
        blocks = page.get_text("blocks")

        # 1. Locate Abstract top boundary
        page_height = page.rect.height or 800
        abstract_top_y = page_height * 0.60
        for b in blocks:
            if re.search(r'\babstract\b', b[4], re.IGNORECASE):
                abstract_top_y = b[1]
                break

        # 2. Extract Authors between title bottom and abstract top
        author_names: List[str] = []
        affil_filter = re.compile(
            r'(@|school|college|university|department|dept\.|management|engineering|technology|institute|center|centre|laboratory|hospital|faculty|sciences|india|orcid|http|www|svkm|nmims|kerala|mumbai|delhi|bangalore|pune|chennai)',
            re.IGNORECASE
        )

        effective_title_bottom = title_bottom_y if title_bottom_y > 0 else 50.0

        for b in blocks:
            block_top = b[1]
            block_bottom = b[3]
            block_text = b[4].strip()

            # Must be positioned vertically between title and abstract
            if block_top >= effective_title_bottom - 10 and block_bottom <= abstract_top_y + 15:
                lines = [l.strip() for l in block_text.splitlines() if l.strip()]
                for line in lines:
                    # Skip if line matches title or part of title
                    if title_text and (line.lower() in title_text.lower() or title_text.lower() in line.lower()):
                        continue
                    # Skip affiliations, emails, institutions
                    if affil_filter.search(line):
                        continue
                    # Must be a plausible human name length
                    if len(line) < 3 or len(line) > 50:
                        continue
                    # Split potentially comma-separated or 'and'-separated authors on one line
                    candidate_parts = [p.strip() for p in re.split(r'[,;]|\band\b', line) if p.strip()]
                    for part in candidate_parts:
                        if affil_filter.search(part):
                            continue
                        if len(part) < 3 or len(part) > 50:
                            continue
                        if re.match(r'^(?:Dr\.|Prof\.|Mr\.|Ms\.)?\s*[A-Z][a-zA-Z\.\s\-\']+$', part) and len(part.split()) <= 5:
                            clean_name = _clean_text(part)
                            if clean_name not in author_names:
                                author_names.append(clean_name)

        if author_names:
            extracted_author = ", ".join(author_names)

        # 3. Extract Publication Year from explicit publication phrases only
        # (avoid matching currency amounts, sample numbers, or TeX build timestamps)
        full_text = page.get_text("text")

        pub_patterns = [
            r'(?:©|\bcopyright\b)\s*(?:©)?\s*(19\d{2}|20\d{2})\b',
            r'\b(?:published|accepted|received)(?:\s+online)?(?:\s+in)?\s*.*?\b(19\d{2}|20\d{2})\b',
            r'\b(?:proceedings\s+of|conference|symposium|vol\.\s*\d+).*?\b(19\d{2}|20\d{2})\b',
            r'\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+(19\d{2}|20\d{2})\b',
        ]

        for pat in pub_patterns:
            m = re.search(pat, full_text, re.IGNORECASE)
            if m:
                year_candidate = int(m.group(1))
                if 1950 <= year_candidate <= 2030:
                    extracted_year = year_candidate
                    break

    except Exception:
        pass

    return extracted_author, extracted_year


def extract_pdf_data(file_input: Union[str, bytes]) -> Dict[str, Any]:
    """
    Extracts text, page counts, character counts, and document metadata
    from a PDF using PyMuPDF (pymupdf).

    Autofills title and authors based on the actual content inside the PDF.
    """
    doc = None
    try:
        if isinstance(file_input, bytes):
            doc = pymupdf.open(stream=file_input, filetype="pdf")
        else:
            doc = pymupdf.open(file_input)

        page_count = len(doc)
        if page_count == 0:
            return {
                "status": "failed",
                "page_count": 0,
                "pages": [],
                "metadata": {},
                "error_message": "PDF contains no pages."
            }

        raw_meta = doc.metadata or {}

        # 1. Page by page text extraction
        pages: List[Dict[str, Any]] = []
        total_chars = 0

        for idx in range(page_count):
            page = doc.load_page(idx)
            page_text = page.get_text("text") or ""
            char_count = len(page_text.strip())
            total_chars += char_count

            pages.append({
                "page_number": idx + 1,
                "content": page_text,
                "character_count": len(page_text)
            })

        avg_chars_per_page = total_chars / page_count

        if avg_chars_per_page < 50:
            status = "scanned_image_only"
        else:
            status = "completed"

        # 2. Content-based Title Extraction
        first_page = doc.load_page(0)
        content_title, title_bottom_y = _extract_title_from_page(first_page)
        meta_title = (raw_meta.get("title") or "").strip()

        final_title = None
        if content_title:
            final_title = content_title
        elif not _is_suspicious_title(meta_title):
            final_title = meta_title

        # 3. Content-based Author & Year Extraction
        content_author, content_year = _extract_authors_and_year_from_page(first_page, final_title, title_bottom_y)

        meta_author = (raw_meta.get("author") or "").strip()
        final_author = meta_author if (meta_author and not _is_suspicious_title(meta_author)) else content_author

        extracted_metadata = {
            "title": final_title or "",
            "author": final_author or "",
            "year": content_year,
            "subject": (raw_meta.get("subject") or "").strip(),
        }

        return {
            "status": status,
            "page_count": page_count,
            "pages": pages,
            "metadata": extracted_metadata,
            "error_message": None
        }

    except Exception as e:
        return {
            "status": "failed",
            "page_count": 0,
            "pages": [],
            "metadata": {},
            "error_message": f"PDF parsing error: {str(e)}"
        }
    finally:
        if doc is not None:
            doc.close()
