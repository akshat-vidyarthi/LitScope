import re
import xml.etree.ElementTree as ET
from typing import List, Optional
import httpx
from app.schemas.discovery import DiscoveredPaper

ARXIV_API_URL = "https://export.arxiv.org/api/query"
USER_AGENT_HEADER = "LitScope/0.1 (mailto:akshatvidyarthi@gmail.com)"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def search_arxiv(
    query: str,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
    limit: int = 10,
    pdf_only: bool = True
) -> List[DiscoveredPaper]:
    """
    Queries arXiv API and converts Atom XML entries into DiscoveredPaper models.
    Guarantees open-access PDF URLs for academic indexing.
    """
    clean_q = query.strip()
    if not clean_q:
        return []

    # Format arXiv search query
    params = {
        "search_query": f"all:{clean_q}",
        "start": 0,
        "max_results": min(max(limit * 2, 5), 30),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    headers = {
        "User-Agent": USER_AGENT_HEADER,
    }

    results: List[DiscoveredPaper] = []
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(ARXIV_API_URL, params=params, headers=headers)
            if resp.status_code != 200:
                return []
            root = ET.fromstring(resp.text)

        entries = root.findall("atom:entry", ATOM_NS)
        for entry in entries:
            title_elem = entry.find("atom:title", ATOM_NS)
            if title_elem is None or not title_elem.text:
                continue
            title = " ".join(title_elem.text.strip().split())

            # Authors
            authors = []
            for author_elem in entry.findall("atom:author", ATOM_NS):
                name_elem = author_elem.find("atom:name", ATOM_NS)
                if name_elem is not None and name_elem.text:
                    authors.append(name_elem.text.strip())

            # Publication year
            published_elem = entry.find("atom:published", ATOM_NS)
            year = None
            if published_elem is not None and published_elem.text:
                try:
                    year = int(published_elem.text[:4])
                except Exception:
                    pass

            if from_year and year and year < from_year:
                continue
            if to_year and year and year > to_year:
                continue

            # Summary / Abstract
            summary_elem = entry.find("atom:summary", ATOM_NS)
            abstract = " ".join(summary_elem.text.strip().split()) if (summary_elem is not None and summary_elem.text) else None

            # DOI
            doi_elem = entry.find("arxiv:doi", ATOM_NS)
            doi = doi_elem.text.strip() if (doi_elem is not None and doi_elem.text) else None

            # Landing URL and PDF URL
            id_elem = entry.find("atom:id", ATOM_NS)
            landing_url = id_elem.text.strip() if (id_elem is not None and id_elem.text) else ""

            pdf_url = None
            for link in entry.findall("atom:link", ATOM_NS):
                if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                    pdf_url = link.attrib.get("href")
                    break

            if not pdf_url and landing_url and "arxiv.org/abs/" in landing_url:
                pdf_url = landing_url.replace("/abs/", "/pdf/") + ".pdf"

            # Strict requirement: Only return papers where full-text PDF is available (no metadata-only records)
            if not pdf_url or not pdf_url.strip().startswith("http"):
                continue

            paper_id = str(doi or landing_url or f"arxiv-{title[:40]}")
            results.append(DiscoveredPaper(
                id=paper_id,
                source="arxiv",
                title=title,
                authors=authors,
                year=year,
                venue="arXiv",
                doi=doi,
                abstract=abstract,
                citation_count=0,
                landing_page_url=landing_url,
                pdf_url=pdf_url,
                is_open_access=True,
                in_library=False
            ))
            if len(results) >= limit:
                break
    except Exception:
        pass

    return results
