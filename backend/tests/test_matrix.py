import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _get_auth_headers():
    test_email = f"matrix_{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post("/api/v1/auth/register", json={
        "email": test_email,
        "password": "Password123!",
        "full_name": "Matrix Researcher"
    })
    token = reg.json().get("access_token")
    if not token:
        login = client.post("/api/v1/auth/login", json={"email": test_email, "password": "Password123!"})
        token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_matrix_lifecycle():
    headers = _get_auth_headers()

    # 1. Create a Project
    proj_res = client.post("/api/v1/projects", json={
        "name": f"Matrix Comparative Study {uuid.uuid4().hex[:6]}",
        "description": "Cross-paper comparison matrix test"
    }, headers=headers)
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 2. Get Empty Matrix
    empty_mat = client.get(f"/api/v1/projects/{project_id}/matrix", headers=headers)
    assert empty_mat.status_code == 200
    mat_data = empty_mat.json()
    assert mat_data["total_papers"] == 0
    assert len(mat_data["rows"]) == 0

    # 3. Add a Paper to Master Library & Curate to Project
    paper_res = client.post("/api/v1/papers", json={
        "title": "Attention Is All You Need",
        "authors": "Vaswani et al.",
        "year": 2017,
        "venue": "NeurIPS",
        "doi": f"10.5555/{uuid.uuid4().hex[:8]}",
        "abstract": "We propose the Transformer, a model architecture eschewing recurrence and relying entirely on attention mechanisms to draw global dependencies between input and output. Evaluated on WMT 2014 English-to-German and English-to-French benchmarks. Results show state-of-the-art BLEU score of 28.4. Limitations include quadratic computational complexity with sequence length."
    }, headers=headers)
    assert paper_res.status_code == 201
    paper_id = paper_res.json()["id"]

    # Curate into project
    cur_res = client.post(f"/api/v1/projects/{project_id}/papers", json={
        "paper_id": paper_id,
        "inclusion_status": "included",
        "notes": "Foundational transformer paper"
    }, headers=headers)
    assert cur_res.status_code == 201

    # 4. Matrix should now list the paper with pending status
    mat_after_curation = client.get(f"/api/v1/projects/{project_id}/matrix", headers=headers)
    assert mat_after_curation.status_code == 200
    rows = mat_after_curation.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["paper_id"] == paper_id
    assert rows[0]["status"] == "pending"

    # 5. Trigger Evidence Extraction
    extract_res = client.post(f"/api/v1/projects/{project_id}/matrix/extract", json={
        "paper_ids": [paper_id],
        "force_reextract": False
    }, headers=headers)
    assert extract_res.status_code == 200
    ext_data = extract_res.json()
    assert ext_data["extracted_count"] == 1
    extracted_row = ext_data["rows"][0]
    assert extracted_row["status"] == "completed"
    assert extracted_row["objective"] is not None
    assert extracted_row["methodology"] is not None
    assert extracted_row["datasets"] is not None
    assert extracted_row["findings"] is not None
    assert extracted_row["limitations"] is not None

    # 6. Manual Cell Edit (PATCH)
    custom_finding = "Achieves superior BLEU score of 28.4 on WMT 2014 En-De benchmark."
    patch_res = client.patch(f"/api/v1/projects/{project_id}/matrix/{paper_id}", json={
        "findings": custom_finding
    }, headers=headers)
    assert patch_res.status_code == 200
    patched_row = patch_res.json()
    assert patched_row["findings"] == custom_finding
    assert patched_row["is_custom_edited"] is True

    # 7. Export Matrix as CSV
    csv_res = client.get(f"/api/v1/projects/{project_id}/matrix/export?format=csv", headers=headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    csv_body = csv_res.text
    assert "Paper Title" in csv_body
    assert "Attention Is All You Need" in csv_body
    assert custom_finding in csv_body

    # 8. Export Matrix as Markdown
    md_res = client.get(f"/api/v1/projects/{project_id}/matrix/export?format=markdown", headers=headers)
    assert md_res.status_code == 200
    assert "text/markdown" in md_res.headers["content-type"]
    md_body = md_res.text
    assert "| Paper | Year | Objective | Methodology |" in md_body
    assert "Attention Is All You Need" in md_body
