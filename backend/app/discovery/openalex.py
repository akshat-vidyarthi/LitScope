import re
from typing import List, Optional, Dict, Any
import httpx
from app.schemas.discovery import DiscoveredPaper

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
USER_AGENT_HEADER = "LitScope/0.1 (mailto:akshatvidyarthi@gmail.com)"


def reconstruct_abstract(inverted_index: Optional[Dict[str, List[int]]]) -> Optional[str]:
    """Reconstructs full text abstract from OpenAlex's inverted index format."""
    if not inverted_index:
        return None
    try:
        word_positions: List[tuple[int, str]] = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort(key=lambda x: x[0])
        return " ".join(word for _, word in word_positions).strip()
    except Exception:
        return None


def clean_doi(raw_doi: Optional[str]) -> Optional[str]:
    """Normalizes DOI by removing URL prefixes."""
    if not raw_doi:
        return None
    cleaned = raw_doi.strip()
    cleaned = re.sub(r"^https?://(dx\.)?doi\.org/", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or None


def search_openalex(
    query: str,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
    limit: int = 10,
    pdf_only: bool = True
) -> List[DiscoveredPaper]:
    """
    Queries OpenAlex Works API and converts results to normalized DiscoveredPaper models.
    Supports year range filtering and strictly filters for accessible full-text PDFs.
    """
    clean_q = query.strip()
    if not clean_q:
        return []

    filters: List[str] = []

    if pdf_only:
        filters.append("has_fulltext:true")
        filters.append("is_oa:true")

    if from_year and to_year:
        if from_year == to_year:
            filters.append(f"publication_year:{from_year}")
        else:
            filters.append(f"publication_year:{min(from_year, to_year)}-{max(from_year, to_year)}")
    elif from_year:
        filters.append(f"publication_year:>{from_year - 1}")
    elif to_year:
        filters.append(f"publication_year:<{to_year + 1}")

    params: Dict[str, Any] = {
        "per-page": min(max(limit * 2 if pdf_only else limit, 1), 50),
    }

    # If query is a DOI, filter directly by DOI
    doi_match = re.match(r"^(https?://(dx\.)?doi\.org/)?(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)$", clean_q, re.IGNORECASE)
    if doi_match:
        doi_val = doi_match.group(3)
        filters.append(f"doi:https://doi.org/{doi_val}")
    else:
        params["search"] = clean_q

    if filters:
        params["filter"] = ",".join(filters)

    headers = {
        "User-Agent": USER_AGENT_HEADER,
        "Accept": "application/json"
    }

    results: List[DiscoveredPaper] = []
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.get(OPENALEX_WORKS_URL, params=params, headers=headers)
            if resp.status_code != 200:
                return []
            data = resp.json()

        works = data.get("results", [])
        for w in works:
            title = w.get("title")
            if not title:
                continue

            authors = []
            for authorship in w.get("authorships", []):
                name = authorship.get("author", {}).get("display_name")
                if name:
                    authors.append(name)

            abstract = reconstruct_abstract(w.get("abstract_inverted_index"))
            doi = clean_doi(w.get("doi"))

            # Primary and Open Access locations
            primary_loc = w.get("primary_location") or {}
            source = primary_loc.get("source") or {}
            venue = source.get("display_name") or w.get("host_venue", {}).get("name")

            oa = w.get("open_access") or {}
            is_oa = bool(oa.get("is_oa", False))

            pdf_url = (
                primary_loc.get("pdf_url")
                or oa.get("oa_url")
                or (w.get("best_oa_location") or {}).get("pdf_url")
            )

            # Strict requirement: Only return papers where PDF is actually available
            if pdf_only and not pdf_url:
                continue

            landing_page = (
                primary_loc.get("landing_page_url")
                or w.get("doi")
                or w.get("id")
            )

            results.append(
                DiscoveredPaper(
                    id=str(w.get("id") or doi or title),
                    source="openalex",
                    title=title.strip(),
                    authors=authors,
                    year=w.get("publication_year"),
                    venue=venue.strip() if venue else None,
                    doi=doi,
                    abstract=abstract,
                    citation_count=w.get("cited_by_count", 0) or 0,
                    landing_page_url=landing_page,
                    pdf_url=pdf_url,
                    is_open_access=is_oa or bool(pdf_url),
                    in_library=False
                )
            )
            if len(results) >= limit:
                break
    except Exception:
        return []

    return results
