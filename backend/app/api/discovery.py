from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.discovery import (
    DiscoverySearchResponse,
    DiscoveryImportRequest,
    DiscoveryImportResponse,
)
from app.discovery.service import (
    search_scholarly_papers,
    import_discovered_paper,
)

router = APIRouter(prefix="/discovery", tags=["Scholarly Discovery"])


@router.get("/search", response_model=DiscoverySearchResponse)
def search_papers(
    q: str = Query(..., min_length=1, description="Keywords, title, author, or DOI"),
    provider: str = Query("all", description="Source provider: 'all', 'openalex', or 'crossref'"),
    from_year: Optional[int] = Query(None, ge=1900, le=2100, description="Start publication year"),
    to_year: Optional[int] = Query(None, ge=1900, le=2100, description="End publication year"),
    pdf_only: bool = Query(True, description="Only return papers with downloadable full-text PDFs"),
    limit: int = Query(10, ge=1, le=25, description="Maximum number of items to return"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Searches scholarly works across OpenAlex and/or Crossref.
    Checks each result against the user's Master Library to show if it is already imported.
    Strictly filters for papers with available full-text PDFs by default.
    """
    valid_provider = provider.lower() if provider.lower() in {"all", "openalex", "arxiv", "crossref", "scopus"} else "all"
    results = search_scholarly_papers(
        query=q,
        provider=valid_provider,
        from_year=from_year,
        to_year=to_year,
        limit=limit,
        pdf_only=pdf_only,
        db=db,
        user_id=current_user["id"]
    )
    return DiscoverySearchResponse(
        query=q,
        provider=valid_provider,
        total_results=len(results),
        results=results
    )


@router.post("/import", response_model=DiscoveryImportResponse, status_code=status.HTTP_201_CREATED)
def import_paper(
    payload: DiscoveryImportRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Imports a discovered paper into the canonical Master Library.
    If open-access PDF is available, downloads and indexes full text.
    Optionally links the paper into an active project.
    """
    return import_discovered_paper(
        db=db,
        request=payload,
        user_id=current_user["id"]
    )
