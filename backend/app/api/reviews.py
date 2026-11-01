import json
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_project_permission
from app.schemas.reviews import (
    LiteratureReviewGenerateRequest,
    LiteratureReviewResponse,
    LiteratureReviewListResponse,
    ReviewReference,
)
from app.synthesis.literature_review_generator import generate_continuous_literature_review

router = APIRouter(prefix="/projects/{project_id}/reviews", tags=["literature-reviews"])


@router.get("", response_model=LiteratureReviewListResponse)
def get_project_reviews(
    project_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetches the current latest literature review draft and prior generation history for a project.
    """
    require_project_permission(project_id, "viewer", current_user, db)

    # 1. Included papers count
    count_row = db.execute(
        text("""
            SELECT COUNT(*) FROM project_papers
            WHERE project_id = :project_id AND inclusion_status = 'included';
        """),
        {"project_id": project_id}
    ).fetchone()
    papers_count = count_row[0] if count_row else 0

    # 2. Fetch reviews history
    rows = db.execute(
        text("""
            SELECT id, project_id, target_word_count, actual_word_count, review_text, paper_references, created_at
            FROM project_literature_reviews
            WHERE project_id = :project_id
            ORDER BY created_at DESC;
        """),
        {"project_id": project_id}
    ).mappings().fetchall()

    history = []
    for r in rows:
        refs_raw = r["paper_references"]
        refs = json.loads(refs_raw) if isinstance(refs_raw, str) else (refs_raw or [])
        history.append({
            "id": r["id"],
            "project_id": r["project_id"],
            "target_word_count": r["target_word_count"],
            "actual_word_count": r["actual_word_count"],
            "review_text": r["review_text"],
            "paper_references": refs,
            "created_at": r["created_at"],
        })

    current_review = history[0] if history else None

    return {
        "current_review": current_review,
        "history": history,
        "papers_count": papers_count,
    }


@router.post("/generate", response_model=LiteratureReviewResponse, status_code=status.HTTP_201_CREATED)
def generate_review(
    project_id: int,
    payload: LiteratureReviewGenerateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Synthesizes a continuous academic literature review connecting all included papers
    matching the requested word count (e.g. 200w, 350w, 500w, or custom).
    """
    require_project_permission(project_id, "editor", current_user, db)

    # Fetch project details
    proj = db.execute(
        text("SELECT name, research_question FROM projects WHERE id = :id;"),
        {"id": project_id}
    ).mappings().fetchone()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    result = generate_continuous_literature_review(
        project_id=project_id,
        target_word_count=payload.target_word_count,
        db=db,
        project_name=proj["name"],
        research_question=proj["research_question"],
    )

    if not result["paper_references"] and result["actual_word_count"] == 0:
        raise HTTPException(
            status_code=400,
            detail="No papers have been added or included in this project to synthesize."
        )

    # Insert into database
    sql_insert = text("""
        INSERT INTO project_literature_reviews (
            project_id, target_word_count, actual_word_count, review_text, paper_references
        )
        VALUES (
            :project_id, :target_word_count, :actual_word_count, :review_text, CAST(:refs AS JSONB)
        )
        RETURNING id, project_id, target_word_count, actual_word_count, review_text, paper_references, created_at;
    """)

    row = db.execute(
        sql_insert,
        {
            "project_id": project_id,
            "target_word_count": result["target_word_count"],
            "actual_word_count": result["actual_word_count"],
            "review_text": result["review_text"],
            "refs": json.dumps(result["paper_references"]),
        }
    ).mappings().fetchone()
    db.commit()

    refs_data = row["paper_references"]
    refs = json.loads(refs_data) if isinstance(refs_data, str) else (refs_data or [])

    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "target_word_count": row["target_word_count"],
        "actual_word_count": row["actual_word_count"],
        "review_text": row["review_text"],
        "paper_references": refs,
        "created_at": row["created_at"],
    }


@router.get("/export")
def export_review(
    project_id: int,
    format: str = Query("markdown", pattern="^(markdown|bibtex)$"),
    review_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Exports the literature review and its structured references as Markdown (.md) or BibTeX (.bib).
    """
    require_project_permission(project_id, "viewer", current_user, db)

    proj = db.execute(
        text("SELECT name FROM projects WHERE id = :id;"),
        {"id": project_id}
    ).mappings().fetchone()
    project_name = proj["name"] if proj else f"Project_{project_id}"

    # Fetch targeted review or latest
    if review_id:
        row = db.execute(
            text("""
                SELECT id, target_word_count, actual_word_count, review_text, paper_references, created_at
                FROM project_literature_reviews
                WHERE id = :review_id AND project_id = :project_id;
            """),
            {"review_id": review_id, "project_id": project_id}
        ).mappings().fetchone()
    else:
        row = db.execute(
            text("""
                SELECT id, target_word_count, actual_word_count, review_text, paper_references, created_at
                FROM project_literature_reviews
                WHERE project_id = :project_id
                ORDER BY created_at DESC
                LIMIT 1;
            """),
            {"project_id": project_id}
        ).mappings().fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="No literature review found for this project")

    refs_data = row["paper_references"]
    refs: List[dict] = json.loads(refs_data) if isinstance(refs_data, str) else (refs_data or [])

    if format == "bibtex":
        bib_entries = []
        for r in refs:
            # Generate citation key: e.g. Darade2016
            first_author = "Author"
            if r.get("authors"):
                raw = re.split(r'[,;&]|\band\b', r["authors"])[0].strip()
                last = raw.split()[-1] if raw else "Author"
                first_author = re.sub(r'[^a-zA-Z]', '', last) or "Author"
            year = r.get("year") or 2024
            key = f"{first_author.lower()}{year}_{r['ref_index']}"

            title = r.get("title", "").replace("{", "").replace("}", "")
            authors = r.get("authors") or "Unknown"
            doi_str = f"  doi = {{{r['doi']}}},\n" if r.get("doi") else ""

            entry = f"""@article{{{key},
  author = {{{authors}}},
  title = {{{title}}},
  year = {{{year}}},
{doi_str}  note = {{LitScope Reference [{r['ref_index']}]}}
}}"""
            bib_entries.append(entry)

        content = "\n\n".join(bib_entries)
        filename = f"literature_review_references_{project_id}.bib"
        return Response(
            content=content,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    # Markdown export
    lines = [
        f"# Literature Review: {project_name}",
        f"\n**Synthesized Word Count:** {row['actual_word_count']} words (Target: {row['target_word_count']}w)",
        f"**Date:** {row['created_at'].strftime('%Y-%m-%d %H:%M UTC')}",
        "\n---\n",
        row["review_text"],
        "\n---\n",
        "## References\n",
    ]

    for r in refs:
        doi_part = f" DOI: https://doi.org/{r['doi']}" if r.get("doi") else ""
        lines.append(f"[{r['ref_index']}] {r.get('authors') or 'Anonymous'}. \"{r['title']}\" ({r.get('year') or 'n.d.'}).{doi_part}")

    content = "\n".join(lines)
    filename = f"literature_review_{project_id}.md"
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
