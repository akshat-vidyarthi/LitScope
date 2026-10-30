import re
from typing import List, Optional, Set
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.schemas.discovery import (
    DiscoveredPaper,
    DiscoveryImportRequest,
    DiscoveryImportResponse,
)
from app.core.config import settings
from app.discovery.openalex import search_openalex
from app.discovery.crossref import search_crossref
from app.discovery.scopus import search_scopus
from app.ingestion.pipeline import ingest_pdf_bytes

USER_AGENT_HEADER = "LitScope/0.1 (mailto:akshatvidyarthi@gmail.com)"


def _normalize_title_key(title: str) -> str:
    """Produces an alphanumeric lowercase key for deduplication."""
    return re.sub(r"[^a-z0-9]", "", title.lower())


def search_scholarly_papers(
    query: str,
    provider: str = "all",
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
    limit: int = 10,
    pdf_only: bool = True,
    db: Optional[Session] = None
) -> List[DiscoveredPaper]:
    """
    Searches scholarly works across OpenAlex and/or Crossref, deduplicates results,
    strictly filters for papers with accessible PDFs, and flags items already present in the local Master Library.
    """
    clean_q = query.strip()
    if not clean_q:
        return []

    results: List[DiscoveredPaper] = []
    prov = provider.lower().strip()

    if prov == "openalex":
        results = search_openalex(clean_q, from_year=from_year, to_year=to_year, limit=limit, pdf_only=pdf_only)
    elif prov == "crossref":
        results = search_crossref(clean_q, from_year=from_year, to_year=to_year, limit=limit, pdf_only=pdf_only)
    elif prov == "scopus":
        results = search_scopus(clean_q, from_year=from_year, to_year=to_year, limit=limit, pdf_only=pdf_only)
    else:  # "all"
        # Fetch from providers with OpenAlex and Scopus prioritized for rich open-access PDFs
        oa_results = search_openalex(clean_q, from_year=from_year, to_year=to_year, limit=limit, pdf_only=pdf_only)
        scopus_results = search_scopus(clean_q, from_year=from_year, to_year=to_year, limit=limit, pdf_only=pdf_only) if settings.ELSEVIER_API_KEY else []
        cr_results = search_crossref(clean_q, from_year=from_year, to_year=to_year, limit=limit, pdf_only=pdf_only)

        seen_dois: Set[str] = set()
        seen_titles: Set[str] = set()
        combined: List[DiscoveredPaper] = []

        candidate_sources = [oa_results, scopus_results, cr_results]
        max_len = max(len(c) for c in candidate_sources)
        for i in range(max_len):
            for candidate_list in candidate_sources:
                if i < len(candidate_list):
                    paper = candidate_list[i]
                    norm_doi = paper.doi.lower().strip() if paper.doi else None
                    norm_title = _normalize_title_key(paper.title)

                    if norm_doi and norm_doi in seen_dois:
                        continue
                    if norm_title and norm_title in seen_titles:
                        continue

                    if norm_doi:
                        seen_dois.add(norm_doi)
                    if norm_title:
                        seen_titles.add(norm_title)
                    combined.append(paper)
        results = combined[:limit]

    # Double-check pdf_only constraint
    if pdf_only:
        results = [p for p in results if p.pdf_url and p.is_open_access]

    # Check local library presence if DB session provided
    if db and results:
        existing_dois: Set[str] = set()
        existing_titles: Set[str] = set()

        dois_to_check = [p.doi for p in results if p.doi]
        if dois_to_check:
            rows = db.execute(
                text("SELECT LOWER(doi) FROM papers WHERE doi IS NOT NULL AND LOWER(doi) = ANY(:dois);"),
                {"dois": [d.lower() for d in dois_to_check]}
            ).fetchall()
            for r in rows:
                existing_dois.add(r[0])

        title_keys = [_normalize_title_key(p.title) for p in results if p.title]
        if title_keys:
            rows = db.execute(
                text("SELECT normalized_title FROM papers WHERE normalized_title = ANY(:titles);"),
                {"titles": title_keys}
            ).fetchall()
            for r in rows:
                existing_titles.add(r[0])

        for p in results:
            doi_in = p.doi and p.doi.lower() in existing_dois
            title_in = _normalize_title_key(p.title) in existing_titles
            p.in_library = bool(doi_in or title_in)

    return results


def import_discovered_paper(
    db: Session,
    request: DiscoveryImportRequest,
    user_id: int
) -> DiscoveryImportResponse:
    """
    Imports a discovered paper into the canonical Master Library.
    If an open-access PDF URL is available, downloads and indexes full text.
    Optionally links the paper into an active project.
    """
    clean_title = request.title.strip()
    norm_title = _normalize_title_key(clean_title)
    authors_str = ", ".join(request.authors) if request.authors else None
    clean_doi_val = request.doi.strip() if request.doi else None

    # 1. Check if paper already exists by DOI or normalized title
    existing_paper = None
    if clean_doi_val:
        existing_paper = db.execute(
            text("SELECT id, title, doi, access_status FROM papers WHERE LOWER(doi) = LOWER(:doi);"),
            {"doi": clean_doi_val}
        ).mappings().fetchone()

    if not existing_paper and norm_title:
        existing_paper = db.execute(
            text("SELECT id, title, doi, access_status FROM papers WHERE normalized_title = :nt;"),
            {"nt": norm_title}
        ).mappings().fetchone()

    if existing_paper:
        paper_id = existing_paper["id"]
        paper_title = existing_paper["title"]
        paper_doi = existing_paper["doi"]
    else:
        # Determine initial access status
        initial_status = "abstract_only" if request.abstract else "metadata_only"
        new_paper = db.execute(
            text("""
                INSERT INTO papers (
                    title, normalized_title, doi, authors, year, venue,
                    abstract, source_url, access_status
                )
                VALUES (
                    :title, :normalized_title, :doi, :authors, :year, :venue,
                    :abstract, :source_url, :access_status
                )
                RETURNING id, title, doi;
            """),
            {
                "title": clean_title,
                "normalized_title": norm_title,
                "doi": clean_doi_val,
                "authors": authors_str,
                "year": request.year,
                "venue": request.venue,
                "abstract": request.abstract,
                "source_url": request.source_url or (f"https://doi.org/{clean_doi_val}" if clean_doi_val else None),
                "access_status": initial_status,
            }
        ).mappings().fetchone()
        db.commit()
        paper_id = new_paper["id"]
        paper_title = new_paper["title"]
        paper_doi = new_paper["doi"]

    # 2. Link to project if requested
    project_linked = False
    if request.project_id is not None:
        db.execute(
            text("""
                INSERT INTO project_papers (project_id, paper_id)
                VALUES (:pid, :paper_id)
                ON CONFLICT (project_id, paper_id) DO NOTHING;
            """),
            {"pid": request.project_id, "paper_id": paper_id}
        )
        db.commit()
        project_linked = True

    # 3. Attempt to download Open Access PDF if URL is present and paper does not already have versions
    pdf_downloaded = False
    page_count = 0
    chunks_created = 0

    has_version = db.execute(
        text("SELECT 1 FROM paper_versions WHERE paper_id = :pid;"),
        {"pid": paper_id}
    ).fetchone()

    if not has_version and request.pdf_url:
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                resp = client.get(
                    request.pdf_url,
                    headers={"User-Agent": USER_AGENT_HEADER, "Accept": "application/pdf,application/octet-stream"}
                )
                if resp.status_code == 200 and resp.content.startswith(b"%PDF-"):
                    ingest_res = ingest_pdf_bytes(
                        db=db,
                        paper_id=paper_id,
                        pdf_bytes=resp.content,
                        project_id=request.project_id,
                        user_id=user_id
                    )
                    pdf_downloaded = True
                    page_count = ingest_res["page_count"]
                    chunks_created = ingest_res["chunks_count"]
        except Exception:
            # Fallback gracefully without breaking: metadata record still safely exists
            pass

    status_msg = "Paper successfully imported to library"
    if pdf_downloaded:
        status_msg += f" with full-text PDF ({page_count} pages, {chunks_created} indexed chunks)"
    elif request.abstract:
        status_msg += " (abstract only, full-text PDF not openly accessible)"
    else:
        status_msg += " (metadata only)"

    if project_linked:
        status_msg += " and linked to project"

    return DiscoveryImportResponse(
        paper_id=paper_id,
        title=paper_title,
        doi=paper_doi,
        pdf_downloaded=pdf_downloaded,
        page_count=page_count,
        chunks_created=chunks_created,
        project_linked=project_linked,
        message=status_msg
    )
