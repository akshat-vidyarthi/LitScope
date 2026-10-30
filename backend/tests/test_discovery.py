import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.discovery.openalex import reconstruct_abstract, clean_doi as clean_oa_doi
from app.discovery.crossref import strip_jats_tags, clean_doi as clean_cr_doi

client = TestClient(app)


def _get_auth_headers():
    test_email = f"disc_{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post("/api/v1/auth/register", json={
        "email": test_email,
        "password": "Password123!",
        "full_name": "Discovery Tester"
    })
    token = reg.json().get("access_token")
    if not token:
        login = client.post("/api/v1/auth/login", json={"email": test_email, "password": "Password123!"})
        token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_reconstruct_abstract_inverted_index():
    inverted_index = {
        "Attention": [0],
        "is": [1],
        "all": [2],
        "you": [3],
        "need": [4],
        "for": [5],
        "transformers.": [6]
    }
    abstract = reconstruct_abstract(inverted_index)
    assert abstract == "Attention is all you need for transformers."

    assert reconstruct_abstract(None) is None
    assert reconstruct_abstract({}) is None


def test_clean_doi_helpers():
    assert clean_oa_doi("https://doi.org/10.1038/s41586-020-2649-2") == "10.1038/s41586-020-2649-2"
    assert clean_cr_doi("http://dx.doi.org/10.1145/3292500.3330964") == "10.1145/3292500.3330964"
    assert clean_oa_doi("10.1016/j.cell.2020.08.012") == "10.1016/j.cell.2020.08.012"
    assert clean_cr_doi(None) is None


def test_strip_jats_tags():
    raw = "<jats:p>This study demonstrates <jats:italic>novel findings</jats:italic> in transformers.</jats:p>"
    cleaned = strip_jats_tags(raw)
    assert cleaned == "This study demonstrates novel findings in transformers."
    assert strip_jats_tags(None) is None


@patch("app.discovery.service.search_openalex")
def test_discovery_search_endpoint(mock_search_oa):
    from app.schemas.discovery import DiscoveredPaper
    mock_search_oa.return_value = [
        DiscoveredPaper(
            id="https://openalex.org/W123",
            source="openalex",
            title="Attention Is All You Need",
            authors=["Ashish Vaswani"],
            year=2017,
            venue="NeurIPS",
            doi="10.48550/arxiv.1706.03762",
            abstract="The dominant sequence transduction models...",
            citation_count=95000,
            landing_page_url="https://arxiv.org/abs/1706.03762",
            pdf_url="https://arxiv.org/pdf/1706.03762.pdf",
            is_open_access=True,
            in_library=False
        )
    ]

    headers = _get_auth_headers()
    response = client.get("/api/v1/discovery/search?q=attention&provider=openalex&from_year=2015&to_year=2020&limit=5", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "attention"
    assert data["provider"] == "openalex"
    assert data["total_results"] == 1
    first_res = data["results"][0]
    assert first_res["title"] == "Attention Is All You Need"
    assert first_res["source"] == "openalex"
    assert "Ashish Vaswani" in first_res["authors"]
    assert first_res["year"] == 2017
    assert first_res["is_open_access"] is True
    assert first_res["pdf_url"] is not None


def test_discovery_import_endpoint():
    headers = _get_auth_headers()

    # 1. Create a project to test linking
    proj_res = client.post("/api/v1/projects", json={
        "name": f"Discovery Study {uuid.uuid4().hex[:6]}",
        "description": "Testing discovery connector import"
    }, headers=headers)
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 2. Import a discovered paper with unique title and DOI
    unique_suffix = uuid.uuid4().hex[:8]
    unique_title = f"Discovery Neural Architecture {unique_suffix}"
    unique_doi = f"10.1000/{unique_suffix}"
    import_payload = {
        "title": unique_title,
        "authors": ["Researcher One", "Researcher Two"],
        "year": 2024,
        "venue": "NeurIPS",
        "doi": unique_doi,
        "abstract": "A novel discovery mechanism for scholarly knowledge.",
        "project_id": project_id
    }

    import_res = client.post("/api/v1/discovery/import", json=import_payload, headers=headers)
    assert import_res.status_code == 201
    res_data = import_res.json()
    assert res_data["title"] == unique_title
    assert res_data["doi"] == unique_doi
    assert res_data["project_linked"] is True
    assert res_data["paper_id"] is not None

    # 3. Verify it shows up in the project papers list
    papers_res = client.get(f"/api/v1/projects/{project_id}/papers", headers=headers)
    assert papers_res.status_code == 200
    curated_papers = papers_res.json()
    assert any(p["doi"] == unique_doi for p in curated_papers)

    # 4. Verify canonical deduplication: importing the same title again reuses the existing paper
    dup_res = client.post("/api/v1/discovery/import", json=import_payload, headers=headers)
    assert dup_res.status_code == 201
    assert dup_res.json()["paper_id"] == res_data["paper_id"]


@patch("app.discovery.scopus._resolve_doi_pdf")
@patch("httpx.Client.get")
def test_scopus_search_connector(mock_http_get, mock_resolve_pdf):
    from app.discovery.scopus import search_scopus
    mock_resolve_pdf.return_value = "https://example.com/scopus_paper.pdf"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "search-results": {
            "entry": [
                {
                    "dc:title": "Quantum Error Correction at Scale",
                    "dc:creator": "Fowler A.",
                    "prism:publicationName": "Nature",
                    "prism:coverDate": "2023-01-15",
                    "prism:doi": "10.1038/s41586-023-01234-x",
                    "citedby-count": "450",
                    "openaccess": "1",
                    "dc:description": "High-fidelity surface code operations."
                }
            ]
        }
    }
    mock_http_get.return_value = mock_resp

    results = search_scopus("quantum error correction", limit=5, pdf_only=True)
    assert len(results) == 1
    assert results[0].title == "Quantum Error Correction at Scale"
    assert results[0].source == "scopus"
    assert results[0].year == 2023
    assert results[0].venue == "Nature"
    assert results[0].pdf_url == "https://example.com/scopus_paper.pdf"
    assert results[0].citation_count == 450
