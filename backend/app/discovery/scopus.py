import re
from typing import List, Optional, Dict, Any
import httpx
from app.core.config import settings
from app.schemas.discovery import DiscoveredPaper

SCOPUS_SEARCH_URL = "https://api.elsevier.com/content/search/scopus"
USER_AGENT_HEADER = "LitScope/0.1 (mailto:akshatvidyarthi@gmail.com)"


def clean_doi(raw_doi: Optional[str]) -> Optional[str]:
    """Normalizes DOI by removing URL prefixes."""
    if not raw_doi:
        return None
    cleaned = raw_doi.strip()
    cleaned = re.sub(r"^https?://(dx\.)?doi\.org/", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or None


def _resolve_doi_pdf(doi: str) -> Optional[str]:
    """Resolves open-access full-text PDF URL for a given DOI via OpenAlex/Unpaywall."""
    if not doi:
        return None
    try:
        url = f"https://api.openalex.org/works/https://doi.org/{doi}"
        headers = {"User-Agent": USER_AGENT_HEADER, "Accept": "application/json"}
        with httpx.Client(timeout=6.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                best_loc = data.get("best_oa_location") or {}
                return best_loc.get("pdf_url") or data.get("open_access", {}).get("oa_url")
    except Exception:
        pass
    return None


def search_scopus(
    query: str,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
    limit: int = 10,
    pdf_only: bool = True
) -> List[DiscoveredPaper]:
    """
    Searches Elsevier Scopus database and converts results to normalized DiscoveredPaper models.
    Requires ELSEVIER_API_KEY in configuration.
    Strictly filters for papers with verified full-text PDFs when pdf_only is True.
    """
    api_key = settings.ELSEVIER_API_KEY
    if not api_key:
        return []

    clean_q = query.strip()
    if not clean_q:
        return []

    # Build Scopus boolean search query
    doi_match = re.match(r"^(https?://(dx\.)?doi\.org/)?(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)$", clean_q, re.IGNORECASE)
    if doi_match:
        query_clause = f"DOI({doi_match.group(3)})"
    else:
        # Sanitize special chars for Scopus search syntax
        sanitized = re.sub(r"[^\w\s-]", " ", clean_q)
        query_clause = f"TITLE-ABS-KEY({sanitized.strip()})"

    clauses = [query_clause]

    if pdf_only:
        clauses.append("OPENACCESS(1)")

    if from_year and to_year:
        if from_year == to_year:
            clauses.append(f"PUBYEAR IS {from_year}")
        else:
            clauses.append(f"PUBYEAR > {min(from_year, to_year) - 1} AND PUBYEAR < {max(from_year, to_year) + 1}")
    elif from_year:
        clauses.append(f"PUBYEAR > {from_year - 1}")
    elif to_year:
        clauses.append(f"PUBYEAR < {to_year + 1}")

    full_query = " AND ".join(clauses)

    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/json",
        "User-Agent": USER_AGENT_HEADER
    }
    if settings.ELSEVIER_INST_TOKEN:
        headers["X-ELS-Insttoken"] = settings.ELSEVIER_INST_TOKEN

    params = {
        "query": full_query,
        "count": min(max(limit * 2 if pdf_only else limit, 1), 25),
        "sort": "relevancy",
    }

    results: List[DiscoveredPaper] = []
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.get(SCOPUS_SEARCH_URL, headers=headers, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()

        entries = data.get("search-results", {}).get("entry", [])
        for entry in entries:
            title = entry.get("dc:title")
            if not title:
                continue

            creator = entry.get("dc:creator")
            authors = [creator.strip()] if creator else []

            venue = entry.get("prism:publicationName")
            doi = clean_doi(entry.get("prism:doi"))

            cover_date = entry.get("prism:coverDate") or ""
            year_match = re.match(r"^(\d{4})", cover_date)
            year = int(year_match.group(1)) if year_match else None

            cited_by = 0
            try:
                cited_by = int(entry.get("citedby-count", 0))
            except (ValueError, TypeError):
                pass

            is_oa = entry.get("openaccess") == "1" or entry.get("openaccessFlag") is True

            # Locate landing page
            scopus_links = entry.get("link", [])
            landing_page = None
            for l in scopus_links:
                if l.get("@ref") == "scopus":
                    landing_page = l.get("@href")
                    break
            if not landing_page and doi:
                landing_page = f"https://doi.org/{doi}"

            # Resolve direct PDF URL
            pdf_url = None
            if doi and is_oa:
                pdf_url = _resolve_doi_pdf(doi)

            # Strict requirement: Only return papers where PDF is actually available
            if pdf_only and not pdf_url:
                continue

            abstract = entry.get("dc:description")

            results.append(
                DiscoveredPaper(
                    id=str(doi or entry.get("dc:identifier") or title),
                    source="scopus",
                    title=title.strip(),
                    authors=authors,
                    year=year,
                    venue=venue.strip() if venue else None,
                    doi=doi,
                    abstract=abstract.strip() if abstract else None,
                    citation_count=cited_by,
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
