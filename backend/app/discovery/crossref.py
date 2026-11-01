import re
from typing import List, Optional, Dict, Any
import httpx
from app.schemas.discovery import DiscoveredPaper

CROSSREF_WORKS_URL = "https://api.crossref.org/works"
USER_AGENT_HEADER = "LitScope/0.1 (mailto:akshatvidyarthi@gmail.com)"


def strip_jats_tags(raw_text: Optional[str]) -> Optional[str]:
    """Strips JATS XML tags, HTML tags, and redundant whitespace from Crossref abstracts."""
    if not raw_text:
        return None
    cleaned = re.sub(r"<[^>]+>", " ", raw_text)
    cleaned = " ".join(cleaned.split()).strip()
    return cleaned or None


def clean_doi(raw_doi: Optional[str]) -> Optional[str]:
    """Normalizes DOI by removing URL prefixes."""
    if not raw_doi:
        return None
    cleaned = raw_doi.strip()
    cleaned = re.sub(r"^https?://(dx\.)?doi\.org/", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or None


def _parse_crossref_item(item: Dict[str, Any], pdf_only: bool = True) -> Optional[DiscoveredPaper]:
    """Parses a single Crossref JSON item into a DiscoveredPaper model."""
    titles = item.get("title", [])
    if not titles or not titles[0]:
        return None
    title = titles[0].strip()

    authors: List[str] = []
    for a in item.get("author", []):
        given = a.get("given", "").strip()
        family = a.get("family", "").strip()
        if given and family:
            authors.append(f"{given} {family}")
        elif family:
            authors.append(family)
        elif given:
            authors.append(given)

    # Published year from date-parts
    published = item.get("published-print") or item.get("published-online") or item.get("created") or {}
    date_parts = published.get("date-parts", [[]])[0]
    year = date_parts[0] if (date_parts and len(date_parts) > 0 and isinstance(date_parts[0], int)) else None

    # Venue container-title
    container_titles = item.get("container-title", [])
    venue = container_titles[0].strip() if container_titles and container_titles[0] else None

    doi = clean_doi(item.get("DOI"))
    abstract = strip_jats_tags(item.get("abstract"))
    citations = item.get("is-referenced-by-count", 0) or 0

    # Locate open-access PDF in link array or resource URL
    pdf_url: Optional[str] = None
    links = item.get("link", [])
    for link in links:
        content_type = link.get("content-type", "")
        if "pdf" in content_type:
            pdf_url = link.get("URL")
            break

    # Strict requirement: Only return papers where PDF is actually available (no metadata-only records)
    if not pdf_url or not pdf_url.strip().startswith("http"):
        return None

    landing_page = item.get("URL") or (f"https://doi.org/{doi}" if doi else None)

    return DiscoveredPaper(
        id=str(doi or title),
        source="crossref",
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        doi=doi,
        abstract=abstract,
        citation_count=citations,
        landing_page_url=landing_page,
        pdf_url=pdf_url,
        is_open_access=bool(pdf_url),
        in_library=False
    )


def search_crossref(
    query: str,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
    limit: int = 10,
    pdf_only: bool = True
) -> List[DiscoveredPaper]:
    """
    Queries Crossref Works API and converts items to normalized DiscoveredPaper models.
    Supports direct DOI lookup, full-text keyword query, and year filters.
    """
    clean_q = query.strip()
    if not clean_q:
        return []

    headers = {
        "User-Agent": USER_AGENT_HEADER,
        "Accept": "application/json"
    }

    doi_match = re.match(r"^(https?://(dx\.)?doi\.org/)?(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)$", clean_q, re.IGNORECASE)

    results: List[DiscoveredPaper] = []
    try:
        with httpx.Client(timeout=12.0) as client:
            if doi_match:
                doi_val = doi_match.group(3)
                resp = client.get(f"{CROSSREF_WORKS_URL}/{doi_val}", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    item = data.get("message", {})
                    paper = _parse_crossref_item(item, pdf_only=pdf_only)
                    if paper:
                        results.append(paper)
                        return results

            # Regular keyword search with year filter
            params: Dict[str, Any] = {
                "query": clean_q,
                "rows": min(max(limit * 3 if pdf_only else limit, 1), 60)
            }

            filters: List[str] = []
            if from_year and to_year:
                filters.append(f"from-pub-date:{min(from_year, to_year)}-01-01")
                filters.append(f"until-pub-date:{max(from_year, to_year)}-12-31")
            elif from_year:
                filters.append(f"from-pub-date:{from_year}-01-01")
            elif to_year:
                filters.append(f"until-pub-date:{to_year}-12-31")

            if filters:
                params["filter"] = ",".join(filters)

            resp = client.get(CROSSREF_WORKS_URL, params=params, headers=headers)
            if resp.status_code != 200:
                return []
            data = resp.json()

        items = data.get("message", {}).get("items", [])
        for it in items:
            paper = _parse_crossref_item(it, pdf_only=pdf_only)
            if paper:
                results.append(paper)
            if len(results) >= limit:
                break
    except Exception:
        return []

    return results
