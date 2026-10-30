import uuid
import pymupdf
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.core.database import SessionLocal
from app.ingestion.pdf_extractor import extract_pdf_data
from app.ingestion.storage import calculate_sha256

client = TestClient(app)


def _create_sample_pdf(page_texts: list[str]) -> bytes:
    """Generates an in-memory PDF with specified text per page using PyMuPDF."""
    doc = pymupdf.open()
    for text in page_texts:
        page = doc.new_page()
        page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _get_auth_headers(email: str, role: str = "owner") -> dict:
    """Registers a test user and returns an Authorization bearer header with the desired role."""
    password = "TestPassword123!"
    clean_email = email.strip().lower()
    client.post(
        "/api/v1/auth/register",
        json={"email": clean_email, "full_name": "Test User", "password": password}
    )
    with SessionLocal() as db:
        db.execute(
            text("UPDATE users SET role = :role WHERE email = :email;"),
            {"role": role, "email": clean_email}
        )
        db.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": clean_email, "password": password}
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_pdf_content_based_metadata_autofill():
    """Verifies that paper title, authors, and year are extracted directly from PDF content."""
    doc = pymupdf.open()
    page = doc.new_page()
    # Insert Title with prominent font size 22
    page.insert_text((50, 80), "Neural Causal Inference in Econometrics", fontsize=22)
    # Insert Authors
    page.insert_text((50, 110), "Dr. Elena Rostova, Prof. Marcus Chen", fontsize=12)
    # Insert Year and Abstract
    page.insert_text((50, 140), "Published: 2024. Abstract: We present a novel framework...", fontsize=10)
    pdf_bytes = doc.tobytes()
    doc.close()

    result = extract_pdf_data(pdf_bytes)
    assert result["metadata"]["title"] == "Neural Causal Inference in Econometrics"
    assert "Elena Rostova" in result["metadata"]["author"]
    assert result["metadata"]["year"] == 2024


def test_pdf_extractor_multi_page():
    """Verifies that PyMuPDF accurately extracts text per page and character counts."""
    p1_text = "Page 1: Deep Learning for Business Analytics and Demand Forecasting in Retail."
    p2_text = "Page 2: Methodology utilizing recurrent neural networks and comparative baselines."
    pdf_bytes = _create_sample_pdf([p1_text, p2_text])

    result = extract_pdf_data(pdf_bytes)
    assert result["status"] == "completed"
    assert result["page_count"] == 2
    assert len(result["pages"]) == 2
    assert result["pages"][0]["page_number"] == 1
    assert "Demand Forecasting" in result["pages"][0]["content"]
    assert result["pages"][1]["page_number"] == 2
    assert "recurrent neural networks" in result["pages"][1]["content"]


def test_pdf_extractor_scanned_detection():
    """Verifies that a PDF with negligible text is flagged as scanned_image_only."""
    # Create empty page without text
    pdf_bytes = _create_sample_pdf([""])
    result = extract_pdf_data(pdf_bytes)
    assert result["status"] == "scanned_image_only"
    assert result["page_count"] == 1


def test_pdf_upload_api_and_deduplication():
    """
    Verifies uploading a real PDF via /api/v1/papers/upload:
    1. Extracts pages and creates version record.
    2. Subsequent upload of identical file detects duplicate checksum.
    """
    unique_id = uuid.uuid4().hex[:8]
    headers = _get_auth_headers(f"uploader_{unique_id}@example.com", role="owner")

    p1 = f"Unique Paper {unique_id} Section 1: Algorithmic pricing in online marketplaces."
    p2 = "Section 2: Statistical evaluation and counterfactual simulations."
    pdf_bytes = _create_sample_pdf([p1, p2])
    expected_checksum = calculate_sha256(pdf_bytes)

    # 1. First upload
    response = client.post(
        "/api/v1/papers/upload",
        headers=headers,
        data={"title": f"Algorithmic Pricing {unique_id}", "year": 2024},
        files={"file": (f"pricing_{unique_id}.pdf", pdf_bytes, "application/pdf")}
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["is_duplicate"] is False
    assert data["pages_extracted"] == 2
    assert data["version"]["file_checksum"] == expected_checksum
    paper_id = data["paper"]["id"]

    # 2. Second upload with identical file content -> Deduplication trigger
    second_resp = client.post(
        "/api/v1/papers/upload",
        headers=headers,
        data={"title": "Different Title Attempt"},
        files={"file": ("duplicate.pdf", pdf_bytes, "application/pdf")}
    )
    assert second_resp.status_code == 201
    second_data = second_resp.json()
    assert second_data["is_duplicate"] is True
    assert second_data["paper"]["id"] == paper_id
    assert second_data["version"]["file_checksum"] == expected_checksum


def test_get_paper_pages_and_stream_pdf():
    """Verifies retrieval of extracted pages and streaming of raw PDF bytes."""
    unique_id = uuid.uuid4().hex[:8]
    headers = _get_auth_headers(f"reader_{unique_id}@example.com", role="owner")

    p1 = f"Page 1 Content {unique_id}: This is an in-depth introduction to the academic topic examining state-of-the-art methodology."
    p2 = f"Page 2 Content {unique_id}: Detailed experimental results, provenance verification, benchmark evaluation, and findings."
    pdf_bytes = _create_sample_pdf([p1, p2])

    upload_resp = client.post(
        "/api/v1/papers/upload",
        headers=headers,
        data={"title": f"Reader Paper {unique_id}"},
        files={"file": (f"reader_{unique_id}.pdf", pdf_bytes, "application/pdf")}
    )
    paper_id = upload_resp.json()["paper"]["id"]

    # Test GET /api/v1/papers/{id}/pages
    pages_resp = client.get(f"/api/v1/papers/{paper_id}/pages", headers=headers)
    assert pages_resp.status_code == 200
    pages = pages_resp.json()
    assert len(pages) == 2
    assert pages[0]["page_number"] == 1
    assert "in-depth introduction" in pages[0]["content"]
    assert pages[1]["page_number"] == 2
    assert "Detailed experimental" in pages[1]["content"]

    # Test GET /api/v1/papers/{id}/pdf
    stream_resp = client.get(f"/api/v1/papers/{paper_id}/pdf", headers=headers)
    assert stream_resp.status_code == 200
    assert stream_resp.headers["content-type"] == "application/pdf"
    assert stream_resp.content == pdf_bytes


def test_upload_invalid_non_pdf():
    """Verifies that non-PDF files are rejected with HTTP 400."""
    headers = _get_auth_headers(f"invalid_{uuid.uuid4().hex[:8]}@example.com", role="owner")
    invalid_bytes = b"This is plain text and definitely not a valid PDF file."

    response = client.post(
        "/api/v1/papers/upload",
        headers=headers,
        files={"file": ("malicious.exe", invalid_bytes, "application/pdf")}
    )
    assert response.status_code == 400
    assert "valid PDF header" in response.json()["detail"]


def test_upload_scanned_image_pdf_rejected():
    """Verifies that PDFs that are images or lack selectable text are rejected with HTTP 400."""
    headers = _get_auth_headers(f"scanner_{uuid.uuid4().hex[:8]}@example.com", role="owner")
    # Generate empty/raster PDF without selectable text
    scanned_bytes = _create_sample_pdf([""])

    response = client.post(
        "/api/v1/papers/upload",
        headers=headers,
        data={"title": "Scanned Document"},
        files={"file": ("scanned_photo.pdf", scanned_bytes, "application/pdf")}
    )
    assert response.status_code == 400
    assert "scanned image" in response.json()["detail"].lower()
