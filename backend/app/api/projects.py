from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectPaperLink, CuratedPaperResponse

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    """Creates a new research project with explicit research question and scope."""
    sql = text("""
        INSERT INTO projects (
            name, description, research_question, scope,
            inclusion_criteria, exclusion_criteria
        )
        VALUES (
            :name, :description, :research_question, :scope,
            :inclusion_criteria, :exclusion_criteria
        )
        RETURNING
            id, name, description, research_question, scope,
            inclusion_criteria, exclusion_criteria, owner_id,
            created_at, updated_at;
    """)

    result = db.execute(
        sql,
        {
            "name": payload.name,
            "description": payload.description,
            "research_question": payload.research_question,
            "scope": payload.scope,
            "inclusion_criteria": payload.inclusion_criteria,
            "exclusion_criteria": payload.exclusion_criteria,
        }
    )
    row = result.mappings().fetchone()
    db.commit()
    return row


@router.get("", response_model=List[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    """Lists all research projects ordered by most recent."""
    sql = text("""
        SELECT
            id, name, description, research_question, scope,
            inclusion_criteria, exclusion_criteria, owner_id,
            created_at, updated_at
        FROM projects
        ORDER BY created_at DESC;
    """)
    result = db.execute(sql)
    return result.mappings().fetchall()


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    """Retrieves a single project by its ID."""
    sql = text("""
        SELECT
            id, name, description, research_question, scope,
            inclusion_criteria, exclusion_criteria, owner_id,
            created_at, updated_at
        FROM projects
        WHERE id = :project_id;
    """)
    row = db.execute(sql, {"project_id": project_id}).mappings().fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found."
        )
    return row


@router.post("/{project_id}/papers", status_code=status.HTTP_201_CREATED)
def curate_paper_into_project(
    project_id: int,
    payload: ProjectPaperLink,
    db: Session = Depends(get_db)
):
    """
    Curates a canonical paper from the master library into a specific project.
    Prevents duplicate entries via unique constraint.
    """
    # 1. Verify project exists
    check_project = db.execute(
        text("SELECT id FROM projects WHERE id = :p_id;"),
        {"p_id": project_id}
    ).fetchone()
    if not check_project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    # 2. Verify paper exists in master library
    check_paper = db.execute(
        text("SELECT id FROM papers WHERE id = :paper_id;"),
        {"paper_id": payload.paper_id}
    ).fetchone()
    if not check_paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found in library.")

    # 3. Insert or update curation status
    sql = text("""
        INSERT INTO project_papers (project_id, paper_id, inclusion_status, notes)
        VALUES (:project_id, :paper_id, :status, :notes)
        ON CONFLICT (project_id, paper_id) DO UPDATE
        SET inclusion_status = EXCLUDED.inclusion_status,
            notes = EXCLUDED.notes
        RETURNING id, project_id, paper_id, inclusion_status, notes, date_added;
    """)

    result = db.execute(
        sql,
        {
            "project_id": project_id,
            "paper_id": payload.paper_id,
            "status": payload.inclusion_status,
            "notes": payload.notes,
        }
    )
    row = result.mappings().fetchone()
    db.commit()
    return row


@router.get("/{project_id}/papers", response_model=List[CuratedPaperResponse])
def list_curated_papers(project_id: int, db: Session = Depends(get_db)):
    """Lists all papers curated into a specific project with their curation status and notes."""
    sql = text("""
        SELECT
            pp.id AS link_id,
            pp.project_id,
            pp.paper_id,
            p.title,
            p.doi,
            p.year,
            p.authors,
            pp.inclusion_status,
            pp.notes,
            pp.date_added
        FROM project_papers pp
        JOIN papers p ON pp.paper_id = p.id
        WHERE pp.project_id = :project_id
        ORDER BY pp.date_added DESC;
    """)
    result = db.execute(sql, {"project_id": project_id})
    return result.mappings().fetchall()
