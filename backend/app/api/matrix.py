import csv
import io
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_project_permission
from app.schemas.matrix import (
    MatrixEvidenceRow,
    MatrixEvidenceUpdate,
    ProjectMatrixResponse,
    MatrixExtractRequest,
    MatrixExtractResponse,
)
from app.evidence.extractor import extract_paper_matrix_evidence

router = APIRouter(prefix="/projects", tags=["Comparison Matrix"])


def _fetch_matrix_rows(db: Session, project_id: int) -> List[MatrixEvidenceRow]:
    """Helper to fetch all curated papers for a project with their matrix evidence."""
    sql = text("""
        SELECT
            p.id AS paper_id,
            p.title,
            p.doi,
            p.year,
            p.authors,
            p.venue,
            p.access_status,
            EXISTS(SELECT 1 FROM paper_versions pv WHERE pv.paper_id = p.id) AS has_pdf,
            pme.id AS evidence_id,
            pme.objective,
            pme.methodology,
            pme.datasets,
            pme.findings,
            pme.limitations,
            COALESCE(pme.provenance, '{}'::jsonb) AS provenance,
            COALESCE(pme.is_custom_edited, FALSE) AS is_custom_edited,
            COALESCE(pme.status, 'pending') AS status,
            pme.error_message,
            pme.updated_at
        FROM project_papers pp
        JOIN papers p ON pp.paper_id = p.id
        LEFT JOIN project_matrix_evidence pme ON pme.project_id = pp.project_id AND pme.paper_id = p.id
        WHERE pp.project_id = :project_id
        ORDER BY p.year DESC NULLS LAST, p.id DESC;
    """)
    rows = db.execute(sql, {"project_id": project_id}).mappings().fetchall()

    result = []
    for r in rows:
        result.append(
            MatrixEvidenceRow(
                id=r["evidence_id"],
                project_id=project_id,
                paper_id=r["paper_id"],
                title=r["title"],
                doi=r["doi"],
                year=r["year"],
                authors=r["authors"],
                venue=r["venue"],
                access_status=r["access_status"],
                has_pdf=bool(r["has_pdf"]),
                objective=r["objective"],
                methodology=r["methodology"],
                datasets=r["datasets"],
                findings=r["findings"],
                limitations=r["limitations"],
                provenance=dict(r["provenance"]) if r["provenance"] else {},
                is_custom_edited=bool(r["is_custom_edited"]),
                status=r["status"] if r["status"] else "pending",
                error_message=r["error_message"],
                updated_at=str(r["updated_at"]) if r["updated_at"] else None,
            )
        )
    return result


@router.get("/{project_id}/matrix", response_model=ProjectMatrixResponse)
def get_project_matrix(
    project_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves the cross-paper comparison matrix for all curated papers in a study.
    Requires viewer access.
    """
    require_project_permission(project_id, "viewer", current_user, db)

    proj = db.execute(
        text("SELECT name FROM projects WHERE id = :pid;"),
        {"pid": project_id}
    ).mappings().fetchone()
    if not proj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    rows = _fetch_matrix_rows(db, project_id)
    extracted_count = sum(1 for r in rows if r.status == "completed")

    return ProjectMatrixResponse(
        project_id=project_id,
        project_name=proj["name"],
        total_papers=len(rows),
        extracted_papers=extracted_count,
        rows=rows
    )


@router.post("/{project_id}/matrix/extract", response_model=MatrixExtractResponse)
def extract_matrix_evidence(
    project_id: int,
    payload: MatrixExtractRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Triggers structured evidence extraction across curated study papers.
    Requires editor role.
    """
    require_project_permission(project_id, "editor", current_user, db)

    # Determine papers to extract
    if payload.paper_ids and len(payload.paper_ids) > 0:
        target_ids = payload.paper_ids
    else:
        # Extract for all curated papers in the study
        curated = db.execute(
            text("""
                SELECT pp.paper_id, pme.status
                FROM project_papers pp
                LEFT JOIN project_matrix_evidence pme ON pme.project_id = pp.project_id AND pme.paper_id = pp.paper_id
                WHERE pp.project_id = :pid;
            """),
            {"pid": project_id}
        ).fetchall()

        if payload.force_reextract:
            target_ids = [r[0] for r in curated]
        else:
            # Only extract unextracted or pending papers
            target_ids = [r[0] for r in curated if r[1] != "completed"]

    extracted_count = 0
    failed_count = 0

    for pid in target_ids:
        try:
            extract_paper_matrix_evidence(
                db=db,
                project_id=project_id,
                paper_id=pid,
                force_reextract=payload.force_reextract
            )
            extracted_count += 1
        except Exception:
            failed_count += 1

    all_rows = _fetch_matrix_rows(db, project_id)

    return MatrixExtractResponse(
        project_id=project_id,
        total_requested=len(target_ids),
        extracted_count=extracted_count,
        failed_count=failed_count,
        rows=all_rows,
        message=f"Successfully extracted matrix evidence for {extracted_count} papers ({failed_count} errors)."
    )


@router.patch("/{project_id}/matrix/{paper_id}", response_model=MatrixEvidenceRow)
def update_matrix_evidence_cell(
    project_id: int,
    paper_id: int,
    payload: MatrixEvidenceUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Allows researchers to manually refine, edit, or override any cell in the comparison matrix.
    Requires editor role.
    """
    require_project_permission(project_id, "editor", current_user, db)

    # Ensure paper is curated in this project
    in_project = db.execute(
        text("SELECT 1 FROM project_papers WHERE project_id = :pid AND paper_id = :paper_id;"),
        {"pid": project_id, "paper_id": paper_id}
    ).fetchone()
    if not in_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper is not curated in this project"
        )

    # Ensure matrix row exists or insert
    existing = db.execute(
        text("SELECT id FROM project_matrix_evidence WHERE project_id = :pid AND paper_id = :paper_id;"),
        {"pid": project_id, "paper_id": paper_id}
    ).fetchone()

    if not existing:
        db.execute(
            text("""
                INSERT INTO project_matrix_evidence (
                    project_id, paper_id, objective, methodology, datasets,
                    findings, limitations, is_custom_edited, status
                )
                VALUES (
                    :pid, :paper_id, :obj, :meth, :data,
                    :find, :lim, TRUE, 'completed'
                );
            """),
            {
                "pid": project_id,
                "paper_id": paper_id,
                "obj": payload.objective,
                "meth": payload.methodology,
                "data": payload.datasets,
                "find": payload.findings,
                "lim": payload.limitations,
            }
        )
    else:
        # Dynamic update of non-null fields
        update_clauses = ["is_custom_edited = TRUE", "updated_at = CURRENT_TIMESTAMP"]
        params = {"pid": project_id, "paper_id": paper_id}

        if payload.objective is not None:
            update_clauses.append("objective = :obj")
            params["obj"] = payload.objective
        if payload.methodology is not None:
            update_clauses.append("methodology = :meth")
            params["meth"] = payload.methodology
        if payload.datasets is not None:
            update_clauses.append("datasets = :data")
            params["data"] = payload.datasets
        if payload.findings is not None:
            update_clauses.append("findings = :find")
            params["find"] = payload.findings
        if payload.limitations is not None:
            update_clauses.append("limitations = :lim")
            params["lim"] = payload.limitations

        set_sql = ", ".join(update_clauses)
        db.execute(
            text(f"UPDATE project_matrix_evidence SET {set_sql} WHERE project_id = :pid AND paper_id = :paper_id;"),
            params
        )

    db.commit()

    # Return updated row
    rows = _fetch_matrix_rows(db, project_id)
    matched = next((r for r in rows if r.paper_id == paper_id), None)
    if not matched:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matrix row not found")
    return matched


@router.get("/{project_id}/matrix/export")
def export_matrix_csv(
    project_id: int,
    format: str = Query("csv", pattern="^(csv|markdown)$"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Exports the comparison matrix as a CSV spreadsheet or Markdown table for literature review writing.
    Requires viewer role.
    """
    require_project_permission(project_id, "viewer", current_user, db)

    proj = db.execute(
        text("SELECT name FROM projects WHERE id = :pid;"),
        {"pid": project_id}
    ).mappings().fetchone()
    project_name = proj["name"] if proj else f"Project_{project_id}"

    rows = _fetch_matrix_rows(db, project_id)

    if format == "markdown":
        lines = [
            f"# Comparative Matrix: {project_name}\n",
            "| Paper | Year | Objective | Methodology | Datasets | Result & Analysis | Conclusion |",
            "| :--- | :---: | :--- | :--- | :--- | :--- | :--- |"
        ]
        for r in rows:
            clean_title = (r.title or "Untitled").replace("|", "-")
            clean_obj = (r.objective or "N/A").replace("\n", " ").replace("|", "-")
            clean_meth = (r.methodology or "N/A").replace("\n", " ").replace("|", "-")
            clean_data = (r.datasets or "N/A").replace("\n", " ").replace("|", "-")
            clean_find = (r.findings or "N/A").replace("\n", " ").replace("|", "-")
            clean_lim = (r.limitations or "N/A").replace("\n", " ").replace("|", "-")
            year_str = str(r.year) if r.year else "N/A"
            lines.append(f"| **{clean_title}** | {year_str} | {clean_obj} | {clean_meth} | {clean_data} | {clean_find} | {clean_lim} |")

        md_content = "\n".join(lines)
        return Response(
            content=md_content,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="matrix_{project_id}.md"'}
        )

    # Default CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Paper Title", "Authors", "Year", "Venue", "DOI",
        "Objective", "Methodology", "Datasets", "Result & Analysis", "Conclusion"
    ])

    for r in rows:
        writer.writerow([
            r.title or "",
            r.authors or "",
            r.year or "",
            r.venue or "",
            r.doi or "",
            r.objective or "",
            r.methodology or "",
            r.datasets or "",
            r.findings or "",
            r.limitations or ""
        ])

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="matrix_{project_id}.csv"'}
    )
