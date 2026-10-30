from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.paper import PaperCreate, PaperResponse

router = APIRouter(prefix="/papers", tags=["Master Library"])


@router.post("", response_model=PaperResponse, status_code=status.HTTP_201_CREATED)
def add_paper_to_library(
    payload: PaperCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Adds a canonical paper record to the master library.
    Requires an authenticated user.
    Checks for duplicates by DOI if present.
    """
    # 1. Check duplicate DOI
    if payload.doi:
        existing = db.execute(
            text("SELECT id, title FROM papers WHERE doi = :doi;"),
            {"doi": payload.doi}
        ).mappings().fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Paper with DOI '{payload.doi}' already exists (ID: {existing['id']}: {existing['title']})."
            )

    # 2. Normalize title for clean matching
    normalized = " ".join(payload.title.strip().lower().split())

    # 3. Insert canonical record
    sql = text("""
        INSERT INTO papers (
            title, normalized_title, doi, authors, year,
            venue, abstract, source_url, access_status
        )
        VALUES (
            :title, :normalized_title, :doi, :authors, :year,
            :venue, :abstract, :source_url, :access_status
        )
        RETURNING
            id, title, normalized_title, doi, authors, year,
            venue, abstract, source_url, access_status,
            created_at, updated_at;
    """)

    result = db.execute(
        sql,
        {
            "title": payload.title.strip(),
            "normalized_title": normalized,
            "doi": payload.doi.strip() if payload.doi else None,
            "authors": payload.authors,
            "year": payload.year,
            "venue": payload.venue,
            "abstract": payload.abstract,
            "source_url": payload.source_url,
            "access_status": payload.access_status,
        }
    )
    row = result.mappings().fetchone()
    db.commit()
    return row


@router.get("", response_model=List[PaperResponse])
def list_library_papers(
    search: Optional[str] = Query(None, description="Keyword search in title or abstract"),
    year: Optional[int] = Query(None, description="Filter by publication year"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lists papers in the canonical master library.
    Enforces access boundaries:
    - Primary Owner/Admin: Sees all papers in the master library.
    - Collaborator (Editor/Viewer): Only sees papers curated into projects they belong to.
    """
    params: dict = {}

    if current_user.get("role") == "owner":
        query_str = """
            SELECT id, title, normalized_title, doi, authors, year,
                   venue, abstract, source_url, access_status,
                   created_at, updated_at
            FROM papers
            WHERE 1=1
        """
    else:
        # Collaborator only sees papers belonging to their permitted projects
        query_str = """
            SELECT DISTINCT p.id, p.title, p.normalized_title, p.doi, p.authors, p.year,
                            p.venue, p.abstract, p.source_url, p.access_status,
                            p.created_at, p.updated_at
            FROM papers p
            JOIN project_papers pp ON p.id = pp.paper_id
            JOIN project_members pm ON pp.project_id = pm.project_id
            WHERE pm.user_id = :user_id
        """
        params["user_id"] = current_user["id"]

    if search:
        query_str += " AND (title ILIKE :search OR abstract ILIKE :search)"
        params["search"] = f"%{search}%"

    if year:
        query_str += " AND year = :year"
        params["year"] = year

    query_str += " ORDER BY year DESC NULLS LAST, created_at DESC;"

    result = db.execute(text(query_str), params)
    return result.mappings().fetchall()


@router.get("/{paper_id}", response_model=PaperResponse)
def get_paper(
    paper_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves a single canonical paper by its ID, checking permissions."""
    if current_user.get("role") != "owner":
        # Check if user has permission to see this paper via any of their projects
        check_access = db.execute(
            text("""
                SELECT 1
                FROM project_papers pp
                JOIN project_members pm ON pp.project_id = pm.project_id
                WHERE pp.paper_id = :paper_id AND pm.user_id = :user_id;
            """),
            {"paper_id": paper_id, "user_id": current_user["id"]}
        ).fetchone()

        if not check_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You do not have permission to view this paper."
            )

    sql = text("""
        SELECT id, title, normalized_title, doi, authors, year,
               venue, abstract, source_url, access_status,
               created_at, updated_at
        FROM papers
        WHERE id = :paper_id;
    """)
    row = db.execute(sql, {"paper_id": paper_id}).mappings().fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with ID {paper_id} not found."
        )
    return row
