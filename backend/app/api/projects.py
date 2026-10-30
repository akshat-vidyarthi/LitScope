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
    ProjectMemberUpdate,
    ProjectMemberResponse,
    RetrievalQuery,
    RetrievedChunkResponse,
    ProjectAskRequest,
    ProjectQueryResponse,
)
import json
import re
from app.retrieval.engine import retrieve_project_evidence
from app.synthesis.generator import synthesize_answer

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
    res = dict(project_row)
    res["member_count"] = 1
    return res


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
            SELECT p.id, p.name, p.description, p.research_question, p.scope,
                   p.inclusion_criteria, p.exclusion_criteria, p.owner_id,
                   p.created_at, p.updated_at,
                   (SELECT COUNT(*) FROM project_members pm WHERE pm.project_id = p.id) AS member_count
            FROM projects p
            ORDER BY p.created_at DESC;
        """)
        result = db.execute(sql)
    else:
        # Regular user sees projects they are a member of
        sql = text("""
            SELECT DISTINCT p.id, p.name, p.description, p.research_question, p.scope,
                            p.inclusion_criteria, p.exclusion_criteria, p.owner_id,
                            p.created_at, p.updated_at,
                            (SELECT COUNT(*) FROM project_members pm WHERE pm.project_id = p.id) AS member_count
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
        SELECT p.id, p.name, p.description, p.research_question, p.scope,
               p.inclusion_criteria, p.exclusion_criteria, p.owner_id,
               p.created_at, p.updated_at,
               (SELECT COUNT(*) FROM project_members pm WHERE pm.project_id = p.id) AS member_count
        FROM projects p
        WHERE p.id = :project_id;
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


@router.delete("/{project_id}/papers/{paper_id}", status_code=status.HTTP_200_OK)
def remove_curated_paper_from_project(
    project_id: int,
    paper_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Removes a paper from this project's curated study collection.
    Note: Does NOT delete the paper from the master research library.
    Requires at least 'editor' role.
    """
    require_project_permission(project_id, "editor", current_user, db)

    db.execute(
        text("DELETE FROM project_papers WHERE project_id = :project_id AND paper_id = :paper_id;"),
        {"project_id": project_id, "paper_id": paper_id}
    )

    # Log audit event
    db.execute(
        text("""
            INSERT INTO audit_events (user_id, project_id, action, details)
            VALUES (:user_id, :project_id, 'paper_removed_from_project', :details);
        """),
        {
            "user_id": current_user["id"],
            "project_id": project_id,
            "details": f'{{"paper_id": {paper_id}}}'
        }
    )
    db.commit()
    return {"message": f"Paper #{paper_id} removed from project #{project_id}."}


@router.post("/{project_id}/retrieve", response_model=List[RetrievedChunkResponse])
def retrieve_evidence_for_project(
    project_id: int,
    payload: RetrievalQuery,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Performs project-scoped hybrid retrieval (semantic vector + full-text keyword)
    across all papers curated as 'included' in this project.
    Requires at least 'viewer' role in the project.
    """
    require_project_permission(project_id, "viewer", current_user, db)
    return retrieve_project_evidence(project_id, payload.query, payload.top_k, db)


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


@router.patch("/{project_id}/members/{user_id}", response_model=ProjectMemberResponse)
def update_project_member_role(
    project_id: int,
    user_id: int,
    payload: ProjectMemberUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Updates an existing collaborator's access role (editor or viewer).
    Requires 'owner' role. Cannot change the project owner's role.
    """
    require_project_permission(project_id, "owner", current_user, db)

    if payload.role not in ["editor", "viewer"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be either 'editor' or 'viewer'."
        )

    # Cannot alter project owner
    owner_check = db.execute(
        text("SELECT owner_id FROM projects WHERE id = :project_id;"),
        {"project_id": project_id}
    ).fetchone()
    if owner_check and owner_check[0] == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change access role of the primary project owner."
        )

    sql = text("""
        UPDATE project_members
        SET role = :role
        WHERE project_id = :project_id AND user_id = :user_id
        RETURNING id AS membership_id, project_id, user_id, role, created_at;
    """)
    row = db.execute(sql, {"project_id": project_id, "user_id": user_id, "role": payload.role}).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collaborator not found in this project.")

    target_user = db.execute(
        text("SELECT email, full_name FROM users WHERE id = :user_id;"),
        {"user_id": user_id}
    ).mappings().fetchone()

    db.execute(
        text("""
            INSERT INTO audit_events (user_id, project_id, action, details)
            VALUES (:user_id, :project_id, 'member_role_updated', :details);
        """),
        {
            "user_id": current_user["id"],
            "project_id": project_id,
            "details": f'{{"target_user_id": {user_id}, "new_role": "{payload.role}"}}'
        }
    )
    db.commit()

    return {
        "membership_id": row["membership_id"],
        "project_id": project_id,
        "user_id": user_id,
        "email": target_user["email"],
        "full_name": target_user["full_name"],
        "role": payload.role,
        "created_at": row["created_at"],
    }


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


@router.post("/{project_id}/ask", response_model=ProjectQueryResponse)
def ask_project_research_question(
    project_id: int,
    payload: ProjectAskRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Asks a research question grounded strictly in the project's curated papers:
    1. Performs project-scoped hybrid retrieval to gather supporting passages.
    2. Synthesizes a grounded answer with page citations [Title, p. X].
    3. Persists the Q&A run into project_queries.
    """
    require_project_permission(project_id, "viewer", current_user, db)

    # 1. Retrieve evidence
    evidence = retrieve_project_evidence(project_id, payload.question, payload.top_k, db)

    # 2. Synthesize answer with citations
    synthesis = synthesize_answer(payload.question, evidence)
    answer_text = synthesis["answer"]
    citations_list = synthesis["citations"]

    # 3. Persist query run
    sql_insert = text("""
        INSERT INTO project_queries (
            project_id, user_id, question, answer, retrieved_chunks
        )
        VALUES (
            :project_id, :user_id, :question, :answer, CAST(:chunks AS JSONB)
        )
        RETURNING id, project_id, question, answer, retrieved_chunks, created_at;
    """)

    row = db.execute(
        sql_insert,
        {
            "project_id": project_id,
            "user_id": current_user["id"],
            "question": payload.question.strip(),
            "answer": answer_text,
            "chunks": json.dumps(evidence),
        }
    ).mappings().fetchone()
    db.commit()

    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "question": row["question"],
        "answer": row["answer"],
        "citations": citations_list,
        "retrieved_chunks": evidence,
        "created_at": row["created_at"],
    }


@router.get("/{project_id}/queries", response_model=List[ProjectQueryResponse])
def list_project_queries(
    project_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves the history of research questions and answers for a project."""
    require_project_permission(project_id, "viewer", current_user, db)

    sql = text("""
        SELECT id, project_id, question, answer, retrieved_chunks, created_at
        FROM project_queries
        WHERE project_id = :project_id
        ORDER BY created_at DESC;
    """)

    rows = db.execute(sql, {"project_id": project_id}).mappings().fetchall()
    results = []
    for r in rows:
        chunks = r["retrieved_chunks"] if isinstance(r["retrieved_chunks"], list) else json.loads(r["retrieved_chunks"])
        extracted_citations = re.findall(r'\[([^\]]+,\s*p\.\s*\d+)\]', r["answer"])
        if extracted_citations:
            citations = list(dict.fromkeys([f"[{c}]" for c in extracted_citations]))
        else:
            citations = [c.get("citation") for c in chunks if c.get("citation")]

        results.append({
            "id": r["id"],
            "project_id": r["project_id"],
            "question": r["question"],
            "answer": r["answer"],
            "citations": citations,
            "retrieved_chunks": chunks,
            "created_at": r["created_at"],
        })
    return results


@router.delete("/{project_id}/queries/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_query(
    project_id: int,
    query_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deletes a past research query run. Requires at least viewer role."""
    require_project_permission(project_id, "viewer", current_user, db)
    db.execute(
        text("DELETE FROM project_queries WHERE id = :query_id AND project_id = :project_id;"),
        {"query_id": query_id, "project_id": project_id}
    )
    db.commit()
