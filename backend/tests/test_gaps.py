import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _get_auth_headers():
    test_email = f"gap_tester_{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post("/api/v1/auth/register", json={
        "email": test_email,
        "password": "Password123!",
        "full_name": "Gap Researcher"
    })
    token = reg.json().get("access_token")
    if not token:
        login = client.post("/api/v1/auth/login", json={"email": test_email, "password": "Password123!"})
        token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_research_gaps_lifecycle():
    headers = _get_auth_headers()

    # 1. Create a Project
    proj_res = client.post("/api/v1/projects", json={
        "name": f"Gap Study {uuid.uuid4().hex[:6]}",
        "description": "Evidence-based candidate research-gap analysis test"
    }, headers=headers)
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 2. Get Empty Gaps Summary
    empty_res = client.get(f"/api/v1/projects/{project_id}/gaps", headers=headers)
    assert empty_res.status_code == 200
    summary = empty_res.json()
    assert summary["project_id"] == project_id
    assert summary["total_gaps"] == 0
    assert summary["papers_count"] == 0

    # 3. Add 2 Curated Papers with Evidence
    p1_res = client.post("/api/v1/papers", json={
        "title": "Classical Banknote Feature Extraction via HSV Color Space",
        "authors": "A. Sharma, B. Patel",
        "year": 2015,
        "venue": "IEEE Conf Image Proc",
        "doi": f"10.1109/gap.{uuid.uuid4().hex[:8]}",
        "abstract": "We develop an automated inspection system using HSV thresholding and segmentation on flatbed scanned images of 100 Rs and 500 Rs notes. Evaluated on 60 laboratory samples. Limitations: Further work is required to handle physical creasing and lighting fluctuations."
    }, headers=headers)
    assert p1_res.status_code == 201
    p1_id = p1_res.json()["id"]

    client.post(f"/api/v1/projects/{project_id}/papers", json={
        "paper_id": p1_id,
        "inclusion_status": "included",
        "notes": "Paper 1"
    }, headers=headers)

    p2_res = client.post("/api/v1/papers", json={
        "title": "Canny Edge Detection and Template Matching for Currency Verification",
        "authors": "C. Verma, D. Rao",
        "year": 2016,
        "venue": "Int J Comput Vision",
        "doi": f"10.1109/gap.{uuid.uuid4().hex[:8]}",
        "abstract": "Proposes grayscale template matching for Indian currency verification. Evaluated on 40 crisp notes using flat scanner. Limitation: Only evaluated under clean laboratory environment, soiled notes were not tested."
    }, headers=headers)
    assert p2_res.status_code == 201
    p2_id = p2_res.json()["id"]

    client.post(f"/api/v1/projects/{project_id}/papers", json={
        "paper_id": p2_id,
        "inclusion_status": "included",
        "notes": "Paper 2"
    }, headers=headers)

    # 4. Generate Candidate Gaps
    gen_res = client.post(f"/api/v1/projects/{project_id}/gaps/generate", headers=headers)
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert gen_data["papers_count"] == 2
    assert gen_data["total_gaps"] > 0
    first_gap = gen_data["gaps"][0]
    gap_id = first_gap["id"]
    assert first_gap["review_status"] == "pending"

    # 5. Researcher Validates the Gap and Adds Notes
    update_res = client.patch(
        f"/api/v1/projects/{project_id}/gaps/{gap_id}",
        json={
            "review_status": "validated",
            "researcher_notes": "Essential gap for my thesis RQ2.",
            "refined_question": "How do deep convolutional features perform on crumpled banknotes?"
        },
        headers=headers
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["review_status"] == "validated"
    assert updated["researcher_notes"] == "Essential gap for my thesis RQ2."
    assert "crumpled" in updated["refined_question"]

    # 6. Add Custom Gap
    custom_res = client.post(
        f"/api/v1/projects/{project_id}/gaps",
        json={
            "paper_id": p1_id,
            "gap_title": "Lack of Multi-Spectral Infrared Validation",
            "gap_type": "methodological",
            "description": "None of the papers inspect ultraviolet or infrared security threads.",
            "confidence_status": "supported_within_collection",
            "researcher_notes": "Recommended by advisor."
        },
        headers=headers
    )
    assert custom_res.status_code == 200
    custom_gap = custom_res.json()
    assert custom_gap["gap_title"] == "Lack of Multi-Spectral Infrared Validation"
    assert custom_gap["review_status"] == "validated"

    # 7. Export Gaps as CSV
    csv_res = client.get(f"/api/v1/projects/{project_id}/gaps/export?format=csv", headers=headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    assert "Gap Title" in csv_res.text

    # 8. Export Gaps as Markdown
    md_res = client.get(f"/api/v1/projects/{project_id}/gaps/export?format=markdown", headers=headers)
    assert md_res.status_code == 200
    assert "text/markdown" in md_res.headers["content-type"]
    assert "# Research Gap Analysis" in md_res.text

    # 9. Delete Gap
    del_res = client.delete(f"/api/v1/projects/{project_id}/gaps/{custom_gap['id']}", headers=headers)
    assert del_res.status_code == 204
