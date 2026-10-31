import uuid
import pymupdf
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.core.database import SessionLocal
from app.synthesis.generator import synthesize_answer, format_evidence_context

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
        json={"email": clean_email, "full_name": "Synthesis Tester", "password": password}
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


def test_synthesize_answer_empty_evidence():
    """Empty evidence returns a clear refusal message without hallucinating."""
    res = synthesize_answer("What is the optimal learning rate?", [])
    assert "No papers have been added" in res["answer"]
    assert res["citations"] == []


def test_synthesize_answer_with_citations():
    """Verifies that evidence passages are cited in the output."""
    chunks = [
        {
            "content": "Random Forest achieved 98.4% accuracy on the test set.",
            "citation": "[Currency Detection, p. 3]",
            "paper_title": "Currency Detection",
            "page_number": 3
        },
        {
            "content": "Support Vector Machines required 4.2x longer training latency.",
            "citation": "[Currency Detection, p. 4]",
            "paper_title": "Currency Detection",
            "page_number": 4
        }
    ]
    res = synthesize_answer("What were the empirical results of Random Forest and SVM?", chunks)
    assert len(res["answer"]) > 20
    assert len(res["citations"]) > 0
    assert any("p. 3" in c or "p. 4" in c for c in res["citations"])


def test_project_ask_api_and_query_history():
    """
    Verifies full end-to-end RAG question answering:
    1. POST /api/v1/projects/{id}/ask retrieves evidence and generates grounded answer.
    2. GET /api/v1/projects/{id}/queries verifies audit persistence.
    """
    uid = uuid.uuid4().hex[:8]
    headers = _get_auth_headers(f"ask_{uid}@example.com", role="owner")

    # 1. Create project
    proj = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": f"Algorithmic Trading {uid}", "research_question": "Execution latency in automated market making"}
    ).json()

    # 2. Upload paper with specific empirical finding
    finding_text = (
        "Order execution latency was reduced by 34 milliseconds when utilizing sub-millisecond FPGA accelerators. "
        "High-frequency limit order books exhibited 12% lower slippage during volatile macroeconomic announcements."
    )
    pdf_bytes = _create_sample_pdf([finding_text])
    client.post(
        "/api/v1/papers/upload",
        headers=headers,
        data={"title": f"FPGA Market Making {uid}", "project_id": proj["id"]},
        files={"file": (f"fpga_{uid}.pdf", pdf_bytes, "application/pdf")}
    )

    # 3. Ask research question
    ask_resp = client.post(
        f"/api/v1/projects/{proj['id']}/ask",
        headers=headers,
        json={"question": "By how much was order execution latency reduced using FPGA accelerators?", "top_k": 3}
    )
    assert ask_resp.status_code == 200, ask_resp.text
    data = ask_resp.json()
    assert data["project_id"] == proj["id"]
    assert "34 milliseconds" in data["answer"] or "FPGA" in data["answer"]
    assert len(data["retrieved_chunks"]) > 0
    assert len(data["citations"]) > 0
    assert data["retrieved_chunks"][0]["page_number"] == 1

    # 4. Verify query history persistence
    hist_resp = client.get(f"/api/v1/projects/{proj['id']}/queries", headers=headers)
    assert hist_resp.status_code == 200
    queries = hist_resp.json()
    assert len(queries) >= 1
    assert queries[0]["id"] == data["id"]
    assert queries[0]["question"] == "By how much was order execution latency reduced using FPGA accelerators?"


def test_project_ask_single_paper_filter():
    """
    Verifies that supplying paper_id in POST /ask restricts retrieval
    strictly to the requested paper rather than searching all project papers.
    """
    uid = uuid.uuid4().hex[:8]
    headers = _get_auth_headers(f"filter_{uid}@example.com", role="owner")

    # 1. Create project
    proj = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": f"Paper Scope Test {uid}", "research_question": "Domain specific analysis"}
    ).json()

    # 2. Upload Paper A
    text_a = "Quantum key distribution achieves unconditional information-theoretic security against eavesdropping."
    pdf_a = _create_sample_pdf([text_a])
    resp_a = client.post(
        "/api/v1/papers/upload",
        headers=headers,
        data={"title": f"Quantum Paper {uid}", "project_id": proj["id"]},
        files={"file": (f"quantum_{uid}.pdf", pdf_a, "application/pdf")}
    ).json()
    paper_a_id = resp_a["paper"]["id"]

    # 3. Upload Paper B
    text_b = "Proximal policy optimization enables continuous robotic arm trajectory generation in zero-gravity."
    pdf_b = _create_sample_pdf([text_b])
    resp_b = client.post(
        "/api/v1/papers/upload",
        headers=headers,
        data={"title": f"Robotics Paper {uid}", "project_id": proj["id"]},
        files={"file": (f"robotics_{uid}.pdf", pdf_b, "application/pdf")}
    ).json()
    paper_b_id = resp_b["paper"]["id"]

    # 4. Query specifically restricted to Paper A
    ask_a = client.post(
        f"/api/v1/projects/{proj['id']}/ask",
        headers=headers,
        json={
            "question": "What security properties are achieved?",
            "top_k": 3,
            "paper_id": paper_a_id,
        }
    )
    assert ask_a.status_code == 200, ask_a.text
    data_a = ask_a.json()
    assert len(data_a["retrieved_chunks"]) > 0
    # Chunks must strictly come from paper_a
    for chunk in data_a["retrieved_chunks"]:
        assert chunk["paper_id"] == paper_a_id

    # 5. Query specifically restricted to Paper B
    ask_b = client.post(
        f"/api/v1/projects/{proj['id']}/ask",
        headers=headers,
        json={
            "question": "What optimization algorithm is utilized?",
            "top_k": 3,
            "paper_id": paper_b_id,
        }
    )
    assert ask_b.status_code == 200, ask_b.text
    data_b = ask_b.json()
    assert len(data_b["retrieved_chunks"]) > 0
    # Chunks must strictly come from paper_b
    for chunk in data_b["retrieved_chunks"]:
        assert chunk["paper_id"] == paper_b_id

    # 6. Query without paper_id (all papers)
    ask_all = client.post(
        f"/api/v1/projects/{proj['id']}/ask",
        headers=headers,
        json={
            "question": "Describe security and robotic trajectory algorithms",
            "top_k": 5,
        }
    )
    assert ask_all.status_code == 200, ask_all.text
    data_all = ask_all.json()
    assert len(data_all["retrieved_chunks"]) > 0
