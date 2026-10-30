import uuid
import pymupdf
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.core.database import SessionLocal

client = TestClient(app)


def _create_sample_pdf(page_texts: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in page_texts:
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(50, 50, 550, 750), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _get_auth_headers(email: str, role: str = "owner") -> dict:
    password = "TestPassword123!"
    clean_email = email.strip().lower()
    client.post(
        "/api/v1/auth/register",
        json={"email": clean_email, "full_name": "Test Researcher", "password": password}
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


def test_project_scoped_hybrid_retrieval():
    """
    Verifies that:
    1. Retrieval is strictly isolated to papers in the queried project.
    2. Chunks from other projects are never leaked.
    3. Retrieved chunks include score, exact page number, and citation.
    """
    uid = uuid.uuid4().hex[:8]
    headers = _get_auth_headers(f"rag_{uid}@example.com", role="owner")

    # 1. Create Project A (Robotics) and Project B (Healthcare)
    proj_a = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": f"Robotics {uid}", "research_question": "Path planning in multi-robot swarms"}
    ).json()

    proj_b = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": f"Healthcare {uid}", "research_question": "Clinical trials in cardiovascular disease"}
    ).json()

    # 2. Upload Paper A to Project A
    robotics_text_p1 = (
        "Kinematic path planning for autonomous mobile robots under dynamic obstacle constraints. "
        "We propose an A* heuristic combined with potential fields to optimize trajectory smoothness."
    )
    pdf_a = _create_sample_pdf([robotics_text_p1])
    client.post(
        "/api/v1/papers/upload",
        headers=headers,
        data={"title": f"Robotic Path Planning {uid}", "project_id": proj_a["id"]},
        files={"file": (f"robotics_{uid}.pdf", pdf_a, "application/pdf")}
    )

    # 3. Upload Paper B to Project B
    medical_text_p1 = (
        "Randomized controlled trial of ACE inhibitors for heart failure patients in acute care. "
        "Blood pressure and ejection fraction were monitored across a twelve month cohort."
    )
    pdf_b = _create_sample_pdf([medical_text_p1])
    client.post(
        "/api/v1/papers/upload",
        headers=headers,
        data={"title": f"Cardiology Clinical Trial {uid}", "project_id": proj_b["id"]},
        files={"file": (f"cardiology_{uid}.pdf", pdf_b, "application/pdf")}
    )

    # 4. Query Project A for robot trajectory
    query_resp_a = client.post(
        f"/api/v1/projects/{proj_a['id']}/retrieve",
        headers=headers,
        json={"query": "How are robot trajectories optimized around obstacles?", "top_k": 3}
    )
    assert query_resp_a.status_code == 200, query_resp_a.text
    results_a = query_resp_a.json()
    assert len(results_a) > 0
    # Must match Paper A
    assert f"Robotic Path Planning {uid}" in results_a[0]["paper_title"]
    assert "trajectory" in results_a[0]["content"].lower()
    assert results_a[0]["page_number"] == 1
    assert "p. 1" in results_a[0]["citation"]

    # CRITICAL CHECK: Verify Project A does NOT contain any cardiology chunks from Project B
    for r in results_a:
        assert "heart" not in r["content"].lower()
        assert "blood pressure" not in r["content"].lower()

    # 5. Query Project B for cardiovascular treatments
    query_resp_b = client.post(
        f"/api/v1/projects/{proj_b['id']}/retrieve",
        headers=headers,
        json={"query": "What medications were monitored in heart failure trials?", "top_k": 3}
    )
    assert query_resp_b.status_code == 200
    results_b = query_resp_b.json()
    assert len(results_b) > 0
    assert f"Cardiology Clinical Trial {uid}" in results_b[0]["paper_title"]
    assert "blood pressure" in results_b[0]["content"].lower()


def test_empty_project_retrieval_returns_empty():
    """An empty project with no papers should return an empty list without error."""
    uid = uuid.uuid4().hex[:8]
    headers = _get_auth_headers(f"empty_{uid}@example.com", role="owner")
    empty_proj = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": f"Empty Project {uid}"}
    ).json()

    resp = client.post(
        f"/api/v1/projects/{empty_proj['id']}/retrieve",
        headers=headers,
        json={"query": "Anything at all"}
    )
    assert resp.status_code == 200
    assert resp.json() == []
