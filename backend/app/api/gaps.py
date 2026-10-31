import csv
import io
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_project_permission
from app.schemas.gaps import (
    ResearchGapResponse,
    ResearchGapUpdate,
    ResearchGapCreate,
    GapAnalysisSummaryResponse,
    EvidenceItem,
    CounterEvidenceItem,
)
from app.evidence.gap_analyzer import (
    generate_candidate_research_gaps,
    get_project_evidence_corpus,
)

router = APIRouter(prefix="/projects", tags=["Research Gaps"])


def _fetch_project_gaps(db: Session, project_id: int) -> List[ResearchGapResponse]:
    """Fetches all stored research gaps for a project."""
    rows = db.execute(
        text("""
            SELECT g.id, g.project_id, g.paper_id, p.title AS paper_title,
                   g.gap_title, g.gap_type, g.description,
                   g.confidence_status, g.supporting_evidence, g.counterevidence,
                   g.review_status, g.researcher_notes, g.refined_question,
                   g.created_at, g.updated_at
            FROM project_research_gaps g
            LEFT JOIN papers p ON g.paper_id = p.id
            WHERE g.project_id = :pid
            ORDER BY 
                p.title ASC NULLS LAST,
                CASE g.review_status
                    WHEN 'validated' THEN 1
                    WHEN 'refined' THEN 2
                    WHEN 'pending' THEN 3
                    WHEN 'dismissed' THEN 4
                    ELSE 5
                END ASC,
                g.id ASC;
        """),
        {"pid": project_id}
    ).mappings().fetchall()

    result = []
    for r in rows:
        supp_raw = r["supporting_evidence"] if r["supporting_evidence"] else []
        supp = [EvidenceItem(**item) for item in supp_raw] if isinstance(supp_raw, list) else []

        counter_raw = r["counterevidence"] if r["counterevidence"] else []
        counter = [CounterEvidenceItem(**item) for item in counter_raw] if isinstance(counter_raw, list) else []

        result.append(
            ResearchGapResponse(
                id=r["id"],
                project_id=r["project_id"],
                paper_id=r["paper_id"],
                paper_title=r["paper_title"],
                gap_title=r["gap_title"],
                gap_type=r["gap_type"],
                description=r["description"],
                confidence_status=r["confidence_status"],
                supporting_evidence=supp,
                counterevidence=counter,
                review_status=r["review_status"],
                researcher_notes=r["researcher_notes"],
                refined_question=r["refined_question"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
        )
    return result


@router.get("/{project_id}/gaps", response_model=GapAnalysisSummaryResponse)
def get_project_gaps(
    project_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves the evidence-based candidate research gaps for a project.
    """
    require_project_permission(project_id, "viewer", current_user, db)

    proj = db.execute(
        text("SELECT name FROM projects WHERE id = :pid;"),
        {"pid": project_id}
    ).mappings().fetchone()
    if not proj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    _, summary = get_project_evidence_corpus(db, project_id)
    gaps = _fetch_project_gaps(db, project_id)

    validated = sum(1 for g in gaps if g.review_status in ["validated", "refined"])
    pending = sum(1 for g in gaps if g.review_status == "pending")
    dismissed = sum(1 for g in gaps if g.review_status == "dismissed")

    return GapAnalysisSummaryResponse(
        project_id=project_id,
        papers_count=summary["papers_count"],
        pages_count=summary["pages_count"],
        year_min=summary["year_min"],
        year_max=summary["year_max"],
        gaps=gaps,
        total_gaps=len(gaps),
        validated_count=validated,
        pending_count=pending,
        dismissed_count=dismissed,
    )


@router.post("/{project_id}/gaps/generate", response_model=GapAnalysisSummaryResponse)
def generate_project_gaps(
    project_id: int,
    preserve_validated: bool = Query(True, description="Whether to keep previously validated/refined gaps"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Executes cross-paper candidate research-gap analysis and persists generated gaps.
    Requires editor access.
    """
    require_project_permission(project_id, "editor", current_user, db)

    proj = db.execute(
        text("SELECT name FROM projects WHERE id = :pid;"),
        {"pid": project_id}
    ).mappings().fetchone()
    if not proj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Generate candidate gaps via analyzer
    candidates = generate_candidate_research_gaps(db, project_id)

    # If preserving validated gaps, delete only pending and dismissed
    if preserve_validated:
        db.execute(
            text("""
                DELETE FROM project_research_gaps 
                WHERE project_id = :pid AND review_status NOT IN ('validated', 'refined');
            """),
            {"pid": project_id}
        )
    else:
        db.execute(
            text("DELETE FROM project_research_gaps WHERE project_id = :pid;"),
            {"pid": project_id}
        )

    # Insert new candidate gaps
    for c in candidates:
        supp_json = json.dumps(c.get("supporting_evidence", []))
        counter_json = json.dumps(c.get("counterevidence", []))

        db.execute(
            text("""
                INSERT INTO project_research_gaps (
                    project_id, paper_id, gap_title, gap_type, description,
                    confidence_status, supporting_evidence, counterevidence,
                    review_status
                ) VALUES (
                    :pid, :paper_id, :title, :gtype, :desc,
                    :conf, CAST(:supp AS jsonb), CAST(:counter AS jsonb),
                    'pending'
                );
            """),
            {
                "pid": project_id,
                "paper_id": c.get("paper_id"),
                "title": c["gap_title"],
                "gtype": c["gap_type"],
                "desc": c["description"],
                "conf": c["confidence_status"],
                "supp": supp_json,
                "counter": counter_json,
            }
        )

    db.commit()

    return get_project_gaps(project_id, current_user, db)


@router.patch("/{project_id}/gaps/{gap_id}", response_model=ResearchGapResponse)
def update_project_gap(
    project_id: int,
    gap_id: int,
    body: ResearchGapUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Updates researcher review status, notes, or refined question for a candidate gap.
    Requires editor access.
    """
    require_project_permission(project_id, "editor", current_user, db)

    gap = db.execute(
        text("SELECT id FROM project_research_gaps WHERE id = :gid AND project_id = :pid;"),
        {"gid": gap_id, "pid": project_id}
    ).fetchone()
    if not gap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research gap not found")

    updates = []
    params = {"gid": gap_id, "pid": project_id}

    if body.review_status is not None:
        updates.append("review_status = :review_status")
        params["review_status"] = body.review_status
    if body.researcher_notes is not None:
        updates.append("researcher_notes = :researcher_notes")
        params["researcher_notes"] = body.researcher_notes
    if body.refined_question is not None:
        updates.append("refined_question = :refined_question")
        params["refined_question"] = body.refined_question

    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        set_clause = ", ".join(updates)
        db.execute(
            text(f"UPDATE project_research_gaps SET {set_clause} WHERE id = :gid AND project_id = :pid;"),
            params
        )
        db.commit()

    # Re-fetch single gap
    all_gaps = _fetch_project_gaps(db, project_id)
    matched = next((g for g in all_gaps if g.id == gap_id), None)
    if not matched:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research gap not found")
    return matched


@router.post("/{project_id}/gaps", response_model=ResearchGapResponse)
def create_custom_gap(
    project_id: int,
    body: ResearchGapCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually creates a custom candidate research gap for the project study.
    Requires editor access.
    """
    require_project_permission(project_id, "editor", current_user, db)

    supp_json = json.dumps([s.dict() for s in (body.supporting_evidence or [])])
    counter_json = json.dumps([c.dict() for c in (body.counterevidence or [])])

    desc = body.description.strip() if body.description else f"Custom candidate research gap for paper."

    row = db.execute(
        text("""
            INSERT INTO project_research_gaps (
                project_id, paper_id, gap_title, gap_type, description,
                confidence_status, supporting_evidence, counterevidence,
                review_status, researcher_notes, refined_question
            ) VALUES (
                :pid, :paper_id, :title, :gtype, :desc,
                :conf, CAST(:supp AS jsonb), CAST(:counter AS jsonb),
                'validated', :notes, :question
            ) RETURNING id;
        """),
        {
            "pid": project_id,
            "paper_id": body.paper_id,
            "title": body.gap_title,
            "gtype": body.gap_type,
            "desc": desc,
            "conf": body.confidence_status or "supported_within_collection",
            "supp": supp_json,
            "counter": counter_json,
            "notes": body.researcher_notes,
            "question": body.refined_question,
        }
    ).fetchone()
    db.commit()

    gap_id = row[0]
    all_gaps = _fetch_project_gaps(db, project_id)
    matched = next((g for g in all_gaps if g.id == gap_id), None)
    if not matched:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve created gap")
    return matched


@router.delete("/{project_id}/gaps/{gap_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_gap(
    project_id: int,
    gap_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deletes a candidate research gap from the project.
    Requires editor access.
    """
    require_project_permission(project_id, "editor", current_user, db)

    res = db.execute(
        text("DELETE FROM project_research_gaps WHERE id = :gid AND project_id = :pid;"),
        {"gid": gap_id, "pid": project_id}
    )
    if res.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research gap not found")
    db.commit()
    return None


@router.get("/{project_id}/gaps/export")
def export_project_gaps(
    project_id: int,
    format: str = Query("csv", pattern="^(csv|markdown)$"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Exports the project's candidate research gaps as CSV or Markdown.
    """
    require_project_permission(project_id, "viewer", current_user, db)

    proj = db.execute(
        text("SELECT name FROM projects WHERE id = :pid;"),
        {"pid": project_id}
    ).mappings().fetchone()
    if not proj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    gaps = _fetch_project_gaps(db, project_id)
    project_name = proj["name"]

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID",
            "Gap Title",
            "Gap Type",
            "Confidence Status",
            "Review Status",
            "Description",
            "Supporting Evidence",
            "Counterevidence",
            "Researcher Notes",
            "Refined Question",
        ])
        for g in gaps:
            supp_str = " | ".join([f"[{s.paper_title}, p.{s.page_number}]: {s.quote}" for s in g.supporting_evidence])
            counter_str = " | ".join([f"[{c.paper_title}, p.{c.page_number}]: {c.quote}" for c in g.counterevidence])
            writer.writerow([
                g.id,
                g.gap_title,
                g.gap_type,
                g.confidence_status,
                g.review_status,
                g.description,
                supp_str,
                counter_str,
                g.researcher_notes or "",
                g.refined_question or "",
            ])
        csv_bytes = output.getvalue().encode("utf-8-sig")
        filename = f"{project_name.lower().replace(' ', '_')}_research_gaps.csv"
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    # Markdown format
    md_lines = [
        f"# Research Gap Analysis: {project_name}",
        f"*Generated by LitScope Intelligence Platform*",
        "",
        "---",
        "",
        f"**Total Identified Gaps:** {len(gaps)}",
        f"**Validated Gaps:** {sum(1 for g in gaps if g.review_status in ['validated', 'refined'])}",
        "",
        "## Candidate Gaps",
        "",
    ]
    for idx, g in enumerate(gaps, 1):
        md_lines.append(f"### {idx}. {g.gap_title}")
        md_lines.append(f"- **Type:** `{g.gap_type}` | **Confidence:** `{g.confidence_status}` | **Status:** `{g.review_status.upper()}`")
        md_lines.append(f"- **Description:** {g.description}")
        if g.supporting_evidence:
            md_lines.append("- **Supporting Evidence:**")
            for s in g.supporting_evidence:
                page_str = f" (Page {s.page_number})" if s.page_number else ""
                md_lines.append(f"  * *\"{s.quote}\"* — **{s.paper_title}**{page_str}")
        if g.counterevidence:
            md_lines.append("- **Counterevidence / Qualifications:**")
            for c in g.counterevidence:
                page_str = f" (Page {c.page_number})" if c.page_number else ""
                md_lines.append(f"  * *\"{c.quote}\"* — **{c.paper_title}**{page_str} ({c.explanation or 'Contradicts / qualifies'})")
        if g.refined_question:
            md_lines.append(f"- **Refined Research Question:** > {g.refined_question}")
        if g.researcher_notes:
            md_lines.append(f"- **Researcher Notes:** {g.researcher_notes}")
        md_lines.append("")

    md_content = "\n".join(md_lines).encode("utf-8")
    filename = f"{project_name.lower().replace(' ', '_')}_research_gaps.md"
    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
