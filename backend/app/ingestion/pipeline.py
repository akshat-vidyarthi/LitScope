import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.ingestion.storage import (
    validate_pdf_content,
    save_pdf_to_disk,
)
from app.ingestion.pdf_extractor import extract_pdf_data
from app.ingestion.chunker import chunk_paper_pages, calculate_chunk_hash
from app.ingestion.embedder import embed_texts


def ingest_pdf_bytes(
    db: Session,
    paper_id: int,
    pdf_bytes: bytes,
    project_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Validates, persists, extracts text, chunks, embeds, and indexes a PDF for a canonical paper.
    Updates access_status to 'full_text_available'.
    """
    validate_pdf_content(pdf_bytes)
    file_path, checksum, file_size = save_pdf_to_disk(pdf_bytes)
    extracted = extract_pdf_data(file_path)

    # 1. Check if version with this checksum already exists
    existing_ver = db.execute(
        text("SELECT id FROM paper_versions WHERE file_checksum = :chk;"),
        {"chk": checksum}
    ).fetchone()

    if existing_ver:
        version_id = existing_ver[0]
    else:
        version_row = db.execute(
            text("""
                INSERT INTO paper_versions (
                    paper_id, file_path, file_checksum, file_size_bytes,
                    page_count, extraction_status, error_message
                )
                VALUES (
                    :paper_id, :file_path, :checksum, :file_size,
                    :page_count, :status, :error
                )
                RETURNING id;
            """),
            {
                "paper_id": paper_id,
                "file_path": file_path,
                "checksum": checksum,
                "file_size": file_size,
                "page_count": extracted["page_count"],
                "status": extracted["status"],
                "error": None,
            }
        ).mappings().fetchone()
        version_id = version_row["id"]

        # 2. Insert pages
        for p in extracted["pages"]:
            db.execute(
                text("""
                    INSERT INTO paper_pages (
                        paper_version_id, page_number, content, character_count
                    )
                    VALUES (
                        :version_id, :page_number, :content, :character_count
                    )
                    ON CONFLICT (paper_version_id, page_number) DO NOTHING;
                """),
                {
                    "version_id": version_id,
                    "page_number": p["page_number"],
                    "content": p["content"],
                    "character_count": p["character_count"],
                }
            )

        # 3. Generate semantic chunks and embeddings
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

    # 4. Update paper access_status to full_text_available
    db.execute(
        text("""
            UPDATE papers
            SET access_status = 'full_text_available', updated_at = CURRENT_TIMESTAMP
            WHERE id = :paper_id;
        """),
        {"paper_id": paper_id}
    )

    # 5. Link to project if requested
    project_linked = False
    if project_id is not None:
        db.execute(
            text("""
                INSERT INTO project_papers (project_id, paper_id)
                VALUES (:pid, :paper_id)
                ON CONFLICT (project_id, paper_id) DO NOTHING;
            """),
            {"pid": project_id, "paper_id": paper_id}
        )
        project_linked = True

    # 6. Audit event
    if user_id is not None:
        db.execute(
            text("""
                INSERT INTO audit_events (user_id, project_id, action, details)
                VALUES (:uid, :pid, 'paper_ingested', CAST(:details AS JSONB));
            """),
            {
                "uid": user_id,
                "pid": project_id,
                "details": json.dumps({
                    "paper_id": paper_id,
                    "checksum": checksum,
                    "page_count": extracted["page_count"]
                })
            }
        )

    db.commit()

    return {
        "version_id": version_id,
        "page_count": extracted["page_count"],
        "chunks_count": len(chunks) if 'chunks' in locals() and chunks else 0,
        "project_linked": project_linked
    }
