from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_project_permission
from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectPaperLink,
    CuratedPaperResponse,
    ProjectMemberAdd,
    ProjectMemberResponse,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Creates a new research project.
    Sets the current authenticated user as owner and automatically adds them
    as a project member with role 'owner'.
    """
    sql = text("""
        INSERT INTO projects (
            name, description, research_question, scope,
            inclusion_criteria, exclusion_criteria, owner_id
        )
        VALUES (
            :name, :description, :research_question, :scope,
            :inclusion_criteria, :exclusion_criteria, :owner_id
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
            "owner_id": current_user["id"],
        }
    )
    project_row = result.mappings().fetchone()
    project_id = project_row["id"]

    # Automatically add owner to project_members
    db.execute(
        text("""
            INSERT INTO project_members (project_id, user_id, role)
            VALUES (:project_id, :user_id, 'owner')
            ON CONFLICT (project_id, user_id) DO NOTHING;
        """),
        {"project_id": project_id, "user_id": current_user["id"]}
    )

    # Log audit event
    db.execute(
        text("""
            INSERT INTO audit_events (user_id, project_id, action, details)
            VALUES (:user_id, :project_id, 'project_created', :details);
        """),
        {
            "user_id": current_user["id"],
            "project_id": project_id,
            "details": f'{{"name": "{payload.name}"}}'
        }
    )
    db.commit()
    return project_row


@router.get("", response_model=List[ProjectResponse])
def list_projects(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lists research projects.
    Returns projects where the user is an owner, editor, or viewer.
    (System administrators see all projects).
    """
    if current_user.get("role") == "owner":
        # System administrator sees all projects
        sql = text("""
            SELECT id, name, description, research_question, scope,
                   inclusion_criteria, exclusion_criteria, owner_id,
                   created_at, updated_at
            FROM projects
            ORDER BY created_at DESC;
        """)
        result = db.execute(sql)
    else:
        # Regular user sees projects they are a member of
        sql = text("""
            SELECT DISTINCT p.id, p.name, p.description, p.research_question, p.scope,
                            p.inclusion_criteria, p.exclusion_criteria, p.owner_id,
                            p.created_at, p.updated_at
            FROM projects p
            JOIN project_members pm ON p.id = pm.project_id
            WHERE pm.user_id = :user_id OR p.owner_id = :user_id
            ORDER BY p.created_at DESC;
        """)
        result = db.execute(sql, {"user_id": current_user["id"]})

    return result.mappings().fetchall()


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves project details. Enforces member permission check."""
    require_project_permission(project_id, "viewer", current_user, db)

    sql = text("""
        SELECT id, name, description, research_question, scope,
               inclusion_criteria, exclusion_criteria, owner_id,
               created_at, updated_at
        FROM projects
        WHERE id = :project_id;
    """)
    row = db.execute(sql, {"project_id": project_id}).mappings().fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project #{project_id} not found."
        )
    return row


# --- Project Curation (Requires Editor role) ---

@router.post("/{project_id}/papers", status_code=status.HTTP_201_CREATED)
def curate_paper_into_project(
    project_id: int,
    payload: ProjectPaperLink,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Curates a canonical paper into a project.
    Requires at least 'editor' role. Viewers cannot curate.
    """
    require_project_permission(project_id, "editor", current_user, db)

    # 1. Verify paper exists in master library
    check_paper = db.execute(
        text("SELECT id FROM papers WHERE id = :paper_id;"),
        {"paper_id": payload.paper_id}
    ).fetchone()
    if not check_paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found in library.")

    # 2. Insert or update curation status
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

    # Log audit event
    db.execute(
        text("""
            INSERT INTO audit_events (user_id, project_id, action, details)
            VALUES (:user_id, :project_id, 'paper_curated', :details);
        """),
        {
            "user_id": current_user["id"],
            "project_id": project_id,
            "details": f'{{"paper_id": {payload.paper_id}, "status": "{payload.inclusion_status}"}}'
        }
    )
    db.commit()
    return row


@router.get("/{project_id}/papers", response_model=List[CuratedPaperResponse])
def list_curated_papers(
    project_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists all papers curated into a project. Requires 'viewer' role."""
    require_project_permission(project_id, "viewer", current_user, db)

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


# --- Project Membership & Collaborator Invitations (Requires Owner role) ---

@router.post("/{project_id}/members", status_code=status.HTTP_201_CREATED)
def add_project_member(
    project_id: int,
    payload: ProjectMemberAdd,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Invites / adds a collaborator to the project with role 'editor' or 'viewer'.
    Requires 'owner' role.
    """
    require_project_permission(project_id, "owner", current_user, db)

    if payload.role not in ["editor", "viewer"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be either 'editor' or 'viewer'."
        )

    # 1. Look up user by email
    target_user = db.execute(
        text("SELECT id, email, full_name FROM users WHERE email = :email;"),
        {"email": payload.email.strip().lower()}
    ).mappings().fetchone()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email '{payload.email}' not found. They must register an account first."
        )

    # 2. Add or update membership in project_members
    sql = text("""
        INSERT INTO project_members (project_id, user_id, role)
        VALUES (:project_id, :user_id, :role)
        ON CONFLICT (project_id, user_id) DO UPDATE
        SET role = EXCLUDED.role
        RETURNING id, project_id, user_id, role, created_at;
    """)

    result = db.execute(
        sql,
        {
            "project_id": project_id,
            "user_id": target_user["id"],
            "role": payload.role
        }
    )
    membership_row = result.mappings().fetchone()

    # Log audit event
    db.execute(
        text("""
            INSERT INTO audit_events (user_id, project_id, action, details)
            VALUES (:user_id, :project_id, 'member_added', :details);
        """),
        {
            "user_id": current_user["id"],
            "project_id": project_id,
            "details": f'{{"invited_email": "{target_user["email"]}", "role": "{payload.role}"}}'
        }
    )
    db.commit()

    return {
        "membership_id": membership_row["id"],
        "project_id": project_id,
        "user_id": target_user["id"],
        "email": target_user["email"],
        "full_name": target_user["full_name"],
        "role": payload.role,
        "created_at": membership_row["created_at"],
    }


@router.get("/{project_id}/members", response_model=List[ProjectMemberResponse])
def list_project_members(
    project_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists all members and their roles for a project. Requires 'viewer' role."""
    require_project_permission(project_id, "viewer", current_user, db)

    sql = text("""
        SELECT
            pm.id AS membership_id,
            pm.project_id,
            pm.user_id,
            u.email,
            u.full_name,
            pm.role,
            pm.created_at
        FROM project_members pm
        JOIN users u ON pm.user_id = u.id
        WHERE pm.project_id = :project_id
        ORDER BY pm.role = 'owner' DESC, pm.created_at ASC;
    """)
    result = db.execute(sql, {"project_id": project_id})
    return result.mappings().fetchall()


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_member(
    project_id: int,
    user_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Removes a collaborator from the project. Requires 'owner' role."""
    require_project_permission(project_id, "owner", current_user, db)

    # Cannot remove project owner
    project = db.execute(
        text("SELECT owner_id FROM projects WHERE id = :p_id;"),
        {"p_id": project_id}
    ).mappings().fetchone()
    if project and project["owner_id"] == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the primary project owner."
        )

    db.execute(
        text("DELETE FROM project_members WHERE project_id = :p_id AND user_id = :u_id;"),
        {"p_id": project_id, "u_id": user_id}
    )
    db.execute(
        text("""
            INSERT INTO audit_events (user_id, project_id, action, details)
            VALUES (:user_id, :project_id, 'member_removed', :details);
        """),
        {
            "user_id": current_user["id"],
            "project_id": project_id,
            "details": f'{{"removed_user_id": {user_id}}}'
        }
    )
    db.commit()
