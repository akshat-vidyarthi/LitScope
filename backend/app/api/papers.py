import os
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.paper import (
    PaperCreate,
    PaperUpdate,
    PaperResponse,
    PaperVersionResponse,
    PaperPageResponse,
    PaperUploadResponse,
)
from app.ingestion.storage import (
    validate_pdf_content,
    calculate_sha256,
    save_pdf_to_disk,
)
from app.ingestion.pdf_extractor import extract_pdf_data
from app.ingestion.chunker import chunk_paper_pages, calculate_chunk_hash
from app.ingestion.embedder import embed_texts

router = APIRouter(prefix="/papers", tags=["Master Library"])


def _row_to_paper_response(row: dict) -> dict:
    """Helper to convert flat query row with version fields into nested PaperResponse structure."""
    version = None
    if row.get("version_id") is not None:
        version = {
            "id": row["version_id"],
            "paper_id": row["id"],
            "file_path": row["file_path"],
            "file_checksum": row["file_checksum"],
            "file_size_bytes": row["file_size_bytes"],
            "page_count": row["page_count"],
            "extraction_status": row["extraction_status"],
            "error_message": row["error_message"],
            "created_at": row["version_created_at"],
        }
    return {
        "id": row["id"],
        "title": row["title"],
        "normalized_title": row["normalized_title"],
        "doi": row["doi"],
        "authors": row["authors"],
        "year": row["year"],
        "venue": row["venue"],
        "abstract": row["abstract"],
        "source_url": row["source_url"],
        "access_status": row["access_status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "latest_version": version,
    }


def check_paper_access(paper_id: int, current_user: dict, db: Session) -> None:
    """Verifies user has permission to access a paper (in their personal library or in a project they belong to)."""
    check = db.execute(
        text("""
            SELECT 1
            FROM papers p
            LEFT JOIN user_library_papers ulp ON ulp.paper_id = p.id AND ulp.user_id = :user_id
            LEFT JOIN project_papers pp ON p.id = pp.paper_id
            LEFT JOIN project_members pm ON pp.project_id = pm.project_id AND pm.user_id = :user_id
            WHERE p.id = :paper_id AND (ulp.user_id IS NOT NULL OR pm.user_id IS NOT NULL);
        """),
        {"paper_id": paper_id, "user_id": current_user["id"]}
    ).fetchone()

    if not check:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You do not have permission to access this paper."
        )


@router.post("", response_model=PaperResponse, status_code=status.HTTP_201_CREATED)
def add_paper_to_library(
    payload: PaperCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Adds a canonical metadata record to the master library."""
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

    normalized = " ".join(payload.title.strip().lower().split())

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
    # Link to user's personal master library
    db.execute(
        text("""
            INSERT INTO user_library_papers (user_id, paper_id)
            VALUES (:user_id, :paper_id)
            ON CONFLICT (user_id, paper_id) DO NOTHING;
        """),
        {"user_id": current_user["id"], "paper_id": row["id"]}
    )
    db.commit()
    return _row_to_paper_response(dict(row))


@router.post("/upload", response_model=PaperUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_paper_pdf(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    doi: Optional[str] = Form(None),
    authors: Optional[str] = Form(None),
    year: Optional[int] = Form(None),
    project_id: Optional[int] = Form(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Uploads an academic PDF, computes SHA-256 checksum for deduplication,
    extracts text and page numbers with PyMuPDF, detects scanned documents,
    and stores versions and pages.
    """
    # 1. If project_id provided, verify write permission
    if project_id is not None:
        member = db.execute(
            text("SELECT role FROM project_members WHERE project_id = :pid AND user_id = :uid;"),
            {"pid": project_id, "uid": current_user["id"]}
        ).mappings().fetchone()
        if not member or member["role"] not in ["owner", "editor"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to add papers to this project."
            )

    # 1b. Validate filename extension
    if file.filename and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents (.pdf) are supported."
        )

    # 2. Read raw file bytes and validate
    content = await file.read()
    try:
        validate_pdf_content(content)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # 3. Extract text and page numbers using PyMuPDF and detect scanned image documents
    extracted = extract_pdf_data(content)
    if extracted["status"] == "scanned_image_only":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded PDF appears to be a scanned image or photo without selectable digital text. Only documents with readable text are supported."
        )
    if extracted["status"] == "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=extracted.get("error_message") or "Failed to process the uploaded PDF document."
        )

    # 4. Compute checksum
    checksum = calculate_sha256(content)

    # 5. Check for duplicate version by SHA-256
    existing_version_row = db.execute(
        text("""
            SELECT id, paper_id, file_path, file_checksum, file_size_bytes,
                   page_count, extraction_status, error_message, created_at
            FROM paper_versions
            WHERE file_checksum = :checksum;
        """),
        {"checksum": checksum}
    ).mappings().fetchone()

    if existing_version_row:
        paper_id = existing_version_row["paper_id"]
        paper_row = db.execute(
            text("SELECT * FROM papers WHERE id = :id;"),
            {"id": paper_id}
        ).mappings().fetchone()

        # Update metadata if user provided manual overrides
        updates = {}
        if title and title.strip():
            updates["title"] = title.strip()
            updates["normalized_title"] = " ".join(title.strip().lower().split())
        if year is not None:
            updates["year"] = year
        if authors and authors.strip():
            updates["authors"] = authors.strip()

        if updates:
            set_clauses = [f"{k} = :{k}" for k in updates.keys()]
            updates["id"] = paper_id
            db.execute(
                text(f"UPDATE papers SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP WHERE id = :id;"),
                updates
            )
            db.commit()
            paper_row = db.execute(
                text("SELECT * FROM papers WHERE id = :id;"),
                {"id": paper_id}
            ).mappings().fetchone()

        # Always link paper to current user's personal master library
        db.execute(
            text("""
                INSERT INTO user_library_papers (user_id, paper_id)
                VALUES (:user_id, :paper_id)
                ON CONFLICT (user_id, paper_id) DO NOTHING;
            """),
            {"user_id": current_user["id"], "paper_id": paper_id}
        )

        if project_id is not None:
            db.execute(
                text("""
                    INSERT INTO project_papers (project_id, paper_id, inclusion_status)
                    VALUES (:pid, :paper_id, 'included')
                    ON CONFLICT (project_id, paper_id) DO UPDATE
                    SET inclusion_status = 'included';
                """),
                {"pid": project_id, "paper_id": paper_id}
            )
            db.execute(
                text("""
                    INSERT INTO audit_events (user_id, project_id, action, details)
                    VALUES (:uid, :pid, 'paper_curated', CAST(:details AS JSONB));
                """),
                {
                    "uid": current_user["id"],
                    "pid": project_id,
                    "details": json.dumps({
                        "paper_id": paper_id,
                        "source": "pdf_upload_duplicate",
                        "inclusion_status": "included"
                    })
                }
            )
            db.commit()

        page_count = db.execute(
            text("SELECT count(*) FROM paper_pages WHERE paper_version_id = :vid;"),
            {"vid": existing_version_row["id"]}
        ).scalar() or 0

        paper_dict = dict(paper_row)
        paper_dict["version_id"] = existing_version_row["id"]
        paper_dict["file_path"] = existing_version_row["file_path"]
        paper_dict["file_checksum"] = existing_version_row["file_checksum"]
        paper_dict["file_size_bytes"] = existing_version_row["file_size_bytes"]
        paper_dict["page_count"] = existing_version_row["page_count"]
        paper_dict["extraction_status"] = existing_version_row["extraction_status"]
        paper_dict["error_message"] = existing_version_row["error_message"]
        paper_dict["version_created_at"] = existing_version_row["created_at"]

        return {
            "paper": _row_to_paper_response(paper_dict),
            "version": dict(existing_version_row),
            "pages_extracted": page_count,
            "is_duplicate": True,
            "message": "This paper is already in your library and has been added to your project." if project_id else "This paper is already in your library."
        }

    # 6. Persist file to local disk
    file_path, checksum, file_size = save_pdf_to_disk(content)

    # 7. Resolve paper metadata
    # Priority: explicit form parameter > PDF content/metadata > fallback
    resolved_title = title or extracted["metadata"].get("title") or "Untitled Research Paper"
    resolved_authors = authors or extracted["metadata"].get("author") or None
    resolved_year = year or extracted["metadata"].get("year") or None
    normalized_title = " ".join(resolved_title.strip().lower().split())

    # Check if a canonical paper already matches DOI or normalized title
    paper_row = None
    if doi:
        paper_row = db.execute(
            text("SELECT * FROM papers WHERE doi = :doi;"),
            {"doi": doi.strip()}
        ).mappings().fetchone()

    if not paper_row:
        paper_row = db.execute(
            text("SELECT * FROM papers WHERE normalized_title = :normalized;"),
            {"normalized": normalized_title}
        ).mappings().fetchone()

    if not paper_row:
        # Create canonical paper record
        sql_insert_paper = text("""
            INSERT INTO papers (
                title, normalized_title, doi, authors, year, access_status
            )
            VALUES (
                :title, :normalized_title, :doi, :authors, :year, 'full_text_available'
            )
            RETURNING *;
        """)
        paper_row = db.execute(
            sql_insert_paper,
            {
                "title": resolved_title.strip(),
                "normalized_title": normalized_title,
                "doi": doi.strip() if doi else None,
                "authors": resolved_authors,
                "year": resolved_year,
            }
        ).mappings().fetchone()

    paper_id = paper_row["id"]

    # 8. Create paper_versions record
    sql_insert_version = text("""
        INSERT INTO paper_versions (
            paper_id, file_path, file_checksum, file_size_bytes,
            page_count, extraction_status, error_message
        )
        VALUES (
            :paper_id, :file_path, :file_checksum, :file_size_bytes,
            :page_count, :extraction_status, :error_message
        )
        RETURNING *;
    """)
    version_row = db.execute(
        sql_insert_version,
        {
            "paper_id": paper_id,
            "file_path": file_path,
            "file_checksum": checksum,
            "file_size_bytes": file_size,
            "page_count": extracted["page_count"],
            "extraction_status": extracted["status"],
            "error_message": extracted["error_message"],
        }
    ).mappings().fetchone()

    version_id = version_row["id"]

    # 9. Insert extracted pages
    for p in extracted["pages"]:
        db.execute(
            text("""
                INSERT INTO paper_pages (
                    paper_version_id, page_number, content, character_count
                )
                VALUES (
                    :version_id, :page_number, :content, :character_count
                );
            """),
            {
                "version_id": version_id,
                "page_number": p["page_number"],
                "content": p["content"],
                "character_count": p["character_count"],
            }
        )

    # 10. Generate and insert semantic chunks with page provenance and embeddings
    chunks = chunk_paper_pages(extracted["pages"])
    if chunks:
        chunk_texts = [c["content"] for c in chunks]
        vectors = embed_texts(chunk_texts)
        for c, vec in zip(chunks, vectors):
            c_hash = calculate_chunk_hash(version_id, c["page_number"], c["chunk_index"], c["content"])
            db.execute(
                text("""
                    INSERT INTO paper_chunks (
                        paper_id, paper_version_id, page_number, chunk_index,
                        content, character_start, character_end, content_hash, embedding
                    )
                    VALUES (
                        :paper_id, :version_id, :page_number, :chunk_index,
                        :content, :character_start, :character_end, :content_hash, CAST(:embedding AS JSONB)
                    )
                    ON CONFLICT (paper_version_id, chunk_index) DO NOTHING;
                """),
                {
                    "paper_id": paper_id,
                    "version_id": version_id,
                    "page_number": c["page_number"],
                    "chunk_index": c["chunk_index"],
                    "content": c["content"],
                    "character_start": c["character_start"],
                    "character_end": c["character_end"],
                    "content_hash": c_hash,
                    "embedding": json.dumps(vec),
                }
            )

    # 10. Link to project if requested
    if project_id is not None:
        db.execute(
            text("""
                INSERT INTO project_papers (project_id, paper_id, inclusion_status)
                VALUES (:pid, :paper_id, 'included')
                ON CONFLICT (project_id, paper_id) DO UPDATE
                SET inclusion_status = 'included';
            """),
            {"pid": project_id, "paper_id": paper_id}
        )

    # 10. Link paper to user's personal master library
    db.execute(
        text("""
            INSERT INTO user_library_papers (user_id, paper_id)
            VALUES (:uid, :paper_id)
            ON CONFLICT (user_id, paper_id) DO NOTHING;
        """),
        {"uid": current_user["id"], "paper_id": paper_id}
    )

    # 11. Audit event
    db.execute(
        text("""
            INSERT INTO audit_events (user_id, project_id, action, details)
            VALUES (:uid, :pid, 'paper_uploaded', CAST(:details AS JSONB));
        """),
        {
            "uid": current_user["id"],
            "pid": project_id,
            "details": json.dumps({
                "paper_id": paper_id,
                "checksum": checksum,
                "page_count": extracted["page_count"],
                "status": extracted["status"]
            })
        }
    )

    db.commit()

    paper_dict = dict(paper_row)
    paper_dict["version_id"] = version_row["id"]
    paper_dict["file_path"] = version_row["file_path"]
    paper_dict["file_checksum"] = version_row["file_checksum"]
    paper_dict["file_size_bytes"] = version_row["file_size_bytes"]
    paper_dict["page_count"] = version_row["page_count"]
    paper_dict["extraction_status"] = version_row["extraction_status"]
    paper_dict["error_message"] = version_row["error_message"]
    paper_dict["version_created_at"] = version_row["created_at"]

    return {
        "paper": _row_to_paper_response(paper_dict),
        "version": dict(version_row),
        "pages_extracted": len(extracted["pages"]),
        "is_duplicate": False,
        "message": f"Extraction successful • {extracted['page_count']} pages extracted."
    }


@router.get("", response_model=List[PaperResponse])
def list_library_papers(
    search: Optional[str] = Query(None, description="Keyword search in title or abstract"),
    year: Optional[int] = Query(None, description="Filter by publication year"),
    pdf_only: bool = Query(False, description="Filter to only include papers with full-text PDFs"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lists papers in the authenticated user's master library.
    Ensures strict per-user library separability.
    Optionally filters strictly for papers with available full-text PDFs.
    """
    params: dict = {"user_id": current_user["id"]}

    lateral_join = "JOIN LATERAL" if pdf_only else "LEFT JOIN LATERAL"
    pdf_filter = "AND v.file_path IS NOT NULL" if pdf_only else ""

    query_str = f"""
        SELECT DISTINCT p.id, p.title, p.normalized_title, p.doi, p.authors, p.year,
                        p.venue, p.abstract, p.source_url, p.access_status,
                        p.created_at, p.updated_at,
                        v.id AS version_id, v.file_path, v.file_checksum, v.file_size_bytes,
                        v.page_count, v.extraction_status, v.error_message, v.created_at AS version_created_at
        FROM papers p
        LEFT JOIN user_library_papers ulp ON ulp.paper_id = p.id AND ulp.user_id = :user_id
        LEFT JOIN project_papers pp ON pp.paper_id = p.id
        LEFT JOIN project_members pm ON pm.project_id = pp.project_id AND pm.user_id = :user_id
        LEFT JOIN projects proj ON proj.id = pp.project_id AND proj.owner_id = :user_id
        {lateral_join} (
            SELECT id, file_path, file_checksum, file_size_bytes, page_count,
                   extraction_status, error_message, created_at
            FROM paper_versions
            WHERE paper_id = p.id
            ORDER BY created_at DESC
            LIMIT 1
        ) v ON true
        WHERE (ulp.user_id IS NOT NULL OR pm.user_id IS NOT NULL OR proj.owner_id IS NOT NULL)
          {pdf_filter}
    """

    if search:
        query_str += " AND (p.title ILIKE :search OR p.abstract ILIKE :search)"
        params["search"] = f"%{search}%"

    if year:
        query_str += " AND p.year = :year"
        params["year"] = year

    query_str += " ORDER BY p.year DESC NULLS LAST, p.created_at DESC;"

    rows = db.execute(text(query_str), params).mappings().fetchall()
    return [_row_to_paper_response(dict(r)) for r in rows]


@router.get("/{paper_id}", response_model=PaperResponse)
def get_paper(
    paper_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves a single canonical paper by its ID, including latest version info."""
    check_paper_access(paper_id, current_user, db)

    sql = text("""
        SELECT p.id, p.title, p.normalized_title, p.doi, p.authors, p.year,
               p.venue, p.abstract, p.source_url, p.access_status,
               p.created_at, p.updated_at,
               v.id AS version_id, v.file_path, v.file_checksum, v.file_size_bytes,
               v.page_count, v.extraction_status, v.error_message, v.created_at AS version_created_at
        FROM papers p
        LEFT JOIN LATERAL (
            SELECT id, file_path, file_checksum, file_size_bytes, page_count,
                   extraction_status, error_message, created_at
            FROM paper_versions
            WHERE paper_id = p.id
            ORDER BY created_at DESC
            LIMIT 1
        ) v ON true
        WHERE p.id = :paper_id;
    """)
    row = db.execute(sql, {"paper_id": paper_id}).mappings().fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with ID {paper_id} not found."
        )
    return _row_to_paper_response(dict(row))


@router.get("/{paper_id}/versions", response_model=List[PaperVersionResponse])
def get_paper_versions(
    paper_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists all versions associated with a paper."""
    check_paper_access(paper_id, current_user, db)
    rows = db.execute(
        text("""
            SELECT id, paper_id, file_path, file_checksum, file_size_bytes,
                   page_count, extraction_status, error_message, created_at
            FROM paper_versions
            WHERE paper_id = :paper_id
            ORDER BY created_at DESC;
        """),
        {"paper_id": paper_id}
    ).mappings().fetchall()
    return rows


@router.get("/{paper_id}/pages", response_model=List[PaperPageResponse])
def get_paper_pages(
    paper_id: int,
    version_id: Optional[int] = Query(None, description="Optional specific version ID; defaults to latest"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves extracted pages for the paper reader interface."""
    check_paper_access(paper_id, current_user, db)

    # Determine version
    if version_id is None:
        target_version = db.execute(
            text("SELECT id FROM paper_versions WHERE paper_id = :pid ORDER BY created_at DESC LIMIT 1;"),
            {"pid": paper_id}
        ).mappings().fetchone()
        if not target_version:
            return []
        version_id = target_version["id"]

    pages = db.execute(
        text("""
            SELECT id, paper_version_id, page_number, content, character_count, created_at
            FROM paper_pages
            WHERE paper_version_id = :vid
            ORDER BY page_number ASC;
        """),
        {"vid": version_id}
    ).mappings().fetchall()
    return pages


@router.get("/{paper_id}/pdf")
def download_paper_pdf(
    paper_id: int,
    version_id: Optional[int] = Query(None, description="Optional specific version ID; defaults to latest"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Streams the raw PDF file for authorized users."""
    check_paper_access(paper_id, current_user, db)

    paper = db.execute(
        text("SELECT title FROM papers WHERE id = :id;"),
        {"id": paper_id}
    ).mappings().fetchone()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found.")

    if version_id is None:
        ver = db.execute(
            text("SELECT file_path FROM paper_versions WHERE paper_id = :pid ORDER BY created_at DESC LIMIT 1;"),
            {"pid": paper_id}
        ).mappings().fetchone()
    else:
        ver = db.execute(
            text("SELECT file_path FROM paper_versions WHERE id = :vid AND paper_id = :pid;"),
            {"vid": version_id, "pid": paper_id}
        ).mappings().fetchone()

    if not ver or not os.path.exists(ver["file_path"]):
        raise HTTPException(status_code=404, detail="PDF file not found on disk.")

    safe_title = "".join(c for c in paper["title"] if c.isalnum() or c in (" ", "-", "_")).strip()[:50]
    return FileResponse(
        ver["file_path"],
        media_type="application/pdf",
        filename=f"{safe_title or 'paper'}.pdf"
    )


@router.post("/{paper_id}/retry", response_model=PaperVersionResponse)
def retry_paper_extraction(
    paper_id: int,
    version_id: Optional[int] = Query(None, description="Optional version ID; defaults to latest"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retries text extraction on an existing stored PDF.
    Useful if a worker previously failed or an updated extraction heuristic is deployed.
    """
    check_paper_access(paper_id, current_user, db)

    if version_id is None:
        ver = db.execute(
            text("SELECT * FROM paper_versions WHERE paper_id = :pid ORDER BY created_at DESC LIMIT 1;"),
            {"pid": paper_id}
        ).mappings().fetchone()
    else:
        ver = db.execute(
            text("SELECT * FROM paper_versions WHERE id = :vid AND paper_id = :pid;"),
            {"vid": version_id, "pid": paper_id}
        ).mappings().fetchone()

    if not ver or not os.path.exists(ver["file_path"]):
        raise HTTPException(status_code=404, detail="PDF file not found on disk.")

    # Re-extract
    with open(ver["file_path"], "rb") as f:
        file_bytes = f.read()

    extracted = extract_pdf_data(file_bytes)

    # Delete existing pages for this version and re-insert
    db.execute(text("DELETE FROM paper_chunks WHERE paper_version_id = :vid;"), {"vid": ver["id"]})
    db.execute(text("DELETE FROM paper_pages WHERE paper_version_id = :vid;"), {"vid": ver["id"]})

    for p in extracted["pages"]:
        db.execute(
            text("""
                INSERT INTO paper_pages (paper_version_id, page_number, content, character_count)
                VALUES (:version_id, :page_number, :content, :character_count);
            """),
            {
                "version_id": ver["id"],
                "page_number": p["page_number"],
                "content": p["content"],
                "character_count": p["character_count"],
            }
        )

    # Re-generate and insert semantic chunks with embeddings
    retry_chunks = chunk_paper_pages(extracted["pages"])
    if retry_chunks:
        retry_texts = [c["content"] for c in retry_chunks]
        retry_vectors = embed_texts(retry_texts)
        for c, vec in zip(retry_chunks, retry_vectors):
            c_hash = calculate_chunk_hash(ver["id"], c["page_number"], c["chunk_index"], c["content"])
            db.execute(
                text("""
                    INSERT INTO paper_chunks (
                        paper_id, paper_version_id, page_number, chunk_index,
                        content, character_start, character_end, content_hash, embedding
                    )
                    VALUES (
                        :paper_id, :version_id, :page_number, :chunk_index,
                        :content, :character_start, :character_end, :content_hash, CAST(:embedding AS JSONB)
                    )
                    ON CONFLICT (paper_version_id, chunk_index) DO NOTHING;
                """),
                {
                    "paper_id": paper_id,
                    "version_id": ver["id"],
                    "page_number": c["page_number"],
                    "chunk_index": c["chunk_index"],
                    "content": c["content"],
                    "character_start": c["character_start"],
                    "character_end": c["character_end"],
                    "content_hash": c_hash,
                    "embedding": json.dumps(vec),
                }
            )

    # Update version status
    updated_ver = db.execute(
        text("""
            UPDATE paper_versions
            SET page_count = :page_count,
                extraction_status = :status,
                error_message = :error_message
            WHERE id = :id
            RETURNING *;
        """),
        {
            "id": ver["id"],
            "page_count": extracted["page_count"],
            "status": extracted["status"],
            "error_message": extracted["error_message"],
        }
    ).mappings().fetchone()

    # Update canonical paper title, authors, and year if improved by re-extraction
    meta = extracted.get("metadata", {})
    paper_updates = {}
    if meta.get("title"):
        paper_updates["title"] = meta["title"]
        paper_updates["normalized_title"] = " ".join(meta["title"].lower().split())
    if meta.get("author"):
        paper_updates["authors"] = meta["author"]
    if meta.get("year"):
        paper_updates["year"] = meta["year"]

    if paper_updates:
        set_clauses = [f"{k} = :{k}" for k in paper_updates.keys()]
        paper_updates["pid"] = paper_id
        db.execute(
            text(f"UPDATE papers SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP WHERE id = :pid;"),
            paper_updates
        )

    db.commit()
    return updated_ver


@router.patch("/{paper_id}", response_model=PaperResponse)
def update_paper_metadata(
    paper_id: int,
    payload: PaperUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Updates metadata (title, authors, year) for an existing paper."""
    check_paper_access(paper_id, current_user, db)

    updates = {}
    if payload.title is not None and payload.title.strip():
        updates["title"] = payload.title.strip()
        updates["normalized_title"] = " ".join(payload.title.strip().lower().split())
    if payload.authors is not None:
        updates["authors"] = payload.authors.strip() if payload.authors.strip() else None
    if payload.year is not None:
        updates["year"] = payload.year
    if payload.venue is not None:
        updates["venue"] = payload.venue.strip() if payload.venue.strip() else None
    if payload.abstract is not None:
        updates["abstract"] = payload.abstract.strip() if payload.abstract.strip() else None

    if updates:
        set_clauses = [f"{k} = :{k}" for k in updates.keys()]
        updates["pid"] = paper_id
        db.execute(
            text(f"UPDATE papers SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP WHERE id = :pid;"),
            updates
        )
        db.commit()

    return get_paper(paper_id, current_user, db)

