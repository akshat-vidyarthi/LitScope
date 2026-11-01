import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def get_auth_headers():
    email = f"test_{uuid.uuid4().hex[:6]}@example.com"
    pwd = "TestPassword123!"
    client.post("/api/v1/auth/register", json={"email": email, "password": pwd, "full_name": "Test User"})
    login = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_project_lifecycle():
    headers = get_auth_headers()
    # 1. Create a project
    payload = {
        "name": "Generative AI in Operations",
        "description": "Investigating productivity shifts in logistics operations",
        "research_question": "What is the empirical effect of GenAI copilots on dispatch latency?",
        "scope": "2023-2026 enterprise case studies",
        "inclusion_criteria": "Peer-reviewed or verified preprint empirical studies",
        "exclusion_criteria": "Purely theoretical or opinion pieces"
    }
    create_res = client.post("/api/v1/projects", json=payload, headers=headers)
    assert create_res.status_code == 201
    project_data = create_res.json()
    assert project_data["id"] is not None
    assert project_data["name"] == payload["name"]
    project_id = project_data["id"]

    # 2. Get the project by ID
    get_res = client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["research_question"] == payload["research_question"]

    # 2.5 Update the project (name, scope, research_question)
    update_payload = {
        "name": "Updated GenAI Operations Study",
        "scope": "2024-2027 enterprise case studies",
        "research_question": "What is the measurable reduction in dispatch latency?",
    }
    update_res = client.patch(f"/api/v1/projects/{project_id}", json=update_payload, headers=headers)
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["name"] == "Updated GenAI Operations Study"
    assert updated_data["scope"] == "2024-2027 enterprise case studies"
    assert updated_data["research_question"] == "What is the measurable reduction in dispatch latency?"

    # 3. List projects
    list_res = client.get("/api/v1/projects", headers=headers)
    assert list_res.status_code == 200
    projects = list_res.json()
    assert any(p["id"] == project_id for p in projects)


def test_master_library_and_curation():
    headers = get_auth_headers()
    test_doi = f"10.1016/j.trb.{uuid.uuid4().hex[:8]}"

    # 1. Create a project
    proj_res = client.post("/api/v1/projects", json={"name": "Fleet AI Review"}, headers=headers)
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 2. Add canonical paper to master library
    paper_payload = {
        "title": "Autonomous Fleet Routing using Diffusion Models",
        "doi": test_doi,
        "authors": "Zhang, W., & Kumar, R.",
        "year": 2024,
        "venue": "Transportation Research Part B",
        "abstract": "We evaluate diffusion-based path planning against traditional heuristic solvers.",
        "access_status": "metadata_only"
    }
    paper_res = client.post("/api/v1/papers", json=paper_payload, headers=headers)
    assert paper_res.status_code == 201
    paper_data = paper_res.json()
    paper_id = paper_data["id"]
    assert paper_data["title"] == paper_payload["title"]

    # 3. Prevent duplicate DOI
    dup_res = client.post("/api/v1/papers", json=paper_payload, headers=headers)
    assert dup_res.status_code == 409

    # 4. Curate paper into the project
    curate_payload = {
        "paper_id": paper_id,
        "inclusion_status": "included",
        "notes": "Direct benchmark for diffusion algorithms in routing."
    }
    curate_res = client.post(f"/api/v1/projects/{project_id}/papers", json=curate_payload, headers=headers)
    assert curate_res.status_code == 201
    curate_data = curate_res.json()
    assert curate_data["paper_id"] == paper_id
    assert curate_data["inclusion_status"] == "included"

    # 5. List curated papers for this project
    curated_list = client.get(f"/api/v1/projects/{project_id}/papers", headers=headers)
    assert curated_list.status_code == 200
    curated = curated_list.json()
    assert len(curated) == 1
    assert curated[0]["paper_id"] == paper_id
    assert curated[0]["title"] == paper_payload["title"]
    assert curated[0]["notes"] == curate_payload["notes"]

    # 6. Search papers in library (visible now that it is curated in their project)
    search_res = client.get("/api/v1/papers?search=Fleet", headers=headers)
    assert search_res.status_code == 200
    papers = search_res.json()
    assert any(p["id"] == paper_id for p in papers)
