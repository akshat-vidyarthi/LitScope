import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_project_lifecycle():
    # 1. Create a project
    payload = {
        "name": "Generative AI in Operations",
        "description": "Investigating productivity shifts in logistics operations",
        "research_question": "What is the empirical effect of GenAI copilots on dispatch latency?",
        "scope": "2023-2026 enterprise case studies",
        "inclusion_criteria": "Peer-reviewed or verified preprint empirical studies",
        "exclusion_criteria": "Purely theoretical or opinion pieces"
    }
    create_res = client.post("/api/v1/projects", json=payload)
    assert create_res.status_code == 201
    project_data = create_res.json()
    assert project_data["id"] is not None
    assert project_data["name"] == payload["name"]
    project_id = project_data["id"]

    # 2. Get the project by ID
    get_res = client.get(f"/api/v1/projects/{project_id}")
    assert get_res.status_code == 200
    assert get_res.json()["research_question"] == payload["research_question"]

    # 3. List projects
    list_res = client.get("/api/v1/projects")
    assert list_res.status_code == 200
    projects = list_res.json()
    assert any(p["id"] == project_id for p in projects)


def test_master_library_and_curation():
    test_doi = f"10.1016/j.trb.{uuid.uuid4().hex[:8]}"
    # 1. Add canonical paper to master library
    paper_payload = {
        "title": "Autonomous Fleet Routing using Diffusion Models",
        "doi": test_doi,
        "authors": "Zhang, W., & Kumar, R.",
        "year": 2024,
        "venue": "Transportation Research Part B",
        "abstract": "We evaluate diffusion-based path planning against traditional heuristic solvers.",
        "access_status": "metadata_only"
    }
    paper_res = client.post("/api/v1/papers", json=paper_payload)
    assert paper_res.status_code == 201
    paper_data = paper_res.json()
    paper_id = paper_data["id"]
    assert paper_data["title"] == paper_payload["title"]

    # 2. Prevent duplicate DOI
    dup_res = client.post("/api/v1/papers", json=paper_payload)
    assert dup_res.status_code == 409

    # 3. Search papers in library
    search_res = client.get("/api/v1/papers?search=Fleet")
    assert search_res.status_code == 200
    papers = search_res.json()
    assert any(p["id"] == paper_id for p in papers)

    # 4. Create a project to curate this paper into
    proj_res = client.post("/api/v1/projects", json={"name": "Fleet AI Review"})
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 5. Curate paper into the project
    curate_payload = {
        "paper_id": paper_id,
        "inclusion_status": "included",
        "notes": "Direct benchmark for diffusion algorithms in routing."
    }
    curate_res = client.post(f"/api/v1/projects/{project_id}/papers", json=curate_payload)
    assert curate_res.status_code == 201
    curate_data = curate_res.json()
    assert curate_data["paper_id"] == paper_id
    assert curate_data["inclusion_status"] == "included"

    # 6. List curated papers for this project
    curated_list = client.get(f"/api/v1/projects/{project_id}/papers")
    assert curated_list.status_code == 200
    curated = curated_list.json()
    assert len(curated) == 1
    assert curated[0]["paper_id"] == paper_id
    assert curated[0]["title"] == paper_payload["title"]
    assert curated[0]["notes"] == curate_payload["notes"]
