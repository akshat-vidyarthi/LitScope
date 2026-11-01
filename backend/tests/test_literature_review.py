import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from tests.test_synthesis import _create_sample_pdf

client = TestClient(app)


def _get_auth_headers(email: str = "review_user@example.com", role: str = "owner"):
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": "Review Tester"}
    )
    if reg_resp.status_code == 200:
        token = reg_resp.json()["access_token"]
    else:
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "password123"}
        )
        token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_literature_review_workflow():
    """
    Tests Phase 8: Continuous Literature Review Generation & Export
    1. Project creation and paper curation
    2. Generation with target word count (200w and 350w)
    3. Retrieval of review history
    4. Markdown and BibTeX exports
    """
    uid = uuid.uuid4().hex[:8]
    headers = _get_auth_headers(f"review_{uid}@example.com")

    # 1. Create project
    proj_resp = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": f"Currency Forgery Detection {uid}",
            "research_question": "What automated vision and classification methods effectively detect counterfeit banknotes?"
        }
    )
    assert proj_resp.status_code in (200, 201)
    project_id = proj_resp.json()["id"]

    # 2. Upload Paper 1
    pdf1 = _create_sample_pdf([
        "Automatic Recognition of Fake Indian Currency Note. Sonali R. Darade, G. R. Gidveer (2016). "
        "The proposed system utilizes digital image processing to identify genuine notes and achieved 90.45% accuracy."
    ])
    p1_resp = client.post(
        "/api/v1/papers/upload",
        headers=headers,
        data={"title": f"Automatic Recognition of Fake Indian Currency Note {uid}", "authors": "Sonali R. Darade, G. R. Gidveer", "year": "2016", "project_id": project_id},
        files={"file": (f"p1_{uid}.pdf", pdf1, "application/pdf")}
    )
    assert p1_resp.status_code in (200, 201)

    # Upload Paper 2
    pdf2 = _create_sample_pdf([
        "Comparative Analysis of Machine Learning Classifiers for Banknote Verification. Santhiya et al. (2020). "
        "Evaluated Random Forest, SVM, KNN, and Gradient Boost Classifiers on 500 digital banknote samples. Gradient Boost reached 99.2% accuracy."
    ])
    p2_resp = client.post(
        "/api/v1/papers/upload",
        headers=headers,
        data={"title": f"Comparative Analysis of Classifiers {uid}", "authors": "Santhiya, B. and Upadhyaya, K.", "year": "2020", "project_id": project_id},
        files={"file": (f"p2_{uid}.pdf", pdf2, "application/pdf")}
    )
    assert p2_resp.status_code in (200, 201)

    # 3. GET /reviews initially
    init_resp = client.get(f"/api/v1/projects/{project_id}/reviews", headers=headers)
    assert init_resp.status_code == 200
    init_data = init_resp.json()
    assert init_data["current_review"] is None
    assert init_data["papers_count"] == 2

    # 4. POST /reviews/generate with 200 words
    gen_resp = client.post(
        f"/api/v1/projects/{project_id}/reviews/generate",
        headers=headers,
        json={"target_word_count": 200}
    )
    assert gen_resp.status_code == 201, gen_resp.text
    review_data = gen_resp.json()
    assert review_data["project_id"] == project_id
    assert review_data["target_word_count"] == 200
    assert review_data["actual_word_count"] > 30
    assert len(review_data["paper_references"]) == 2
    # Verify that the text mentions the author citation label or bracket reference
    assert "[1]" in review_data["review_text"] or "Darade" in review_data["review_text"]
    assert "[2]" in review_data["review_text"] or "Santhiya" in review_data["review_text"]

    # 5. POST /reviews/generate with 350 words
    gen_resp_350 = client.post(
        f"/api/v1/projects/{project_id}/reviews/generate",
        headers=headers,
        json={"target_word_count": 350}
    )
    assert gen_resp_350.status_code == 201
    review_350 = gen_resp_350.json()
    assert review_350["target_word_count"] == 350

    # 6. Verify history contains both
    history_resp = client.get(f"/api/v1/projects/{project_id}/reviews", headers=headers)
    assert history_resp.status_code == 200
    h_data = history_resp.json()
    assert h_data["current_review"]["id"] == review_350["id"]
    assert len(h_data["history"]) == 2

    # 7. Test Export Markdown
    exp_md = client.get(f"/api/v1/projects/{project_id}/reviews/export?format=markdown", headers=headers)
    assert exp_md.status_code == 200
    assert "Literature Review" in exp_md.text
    assert "## References" in exp_md.text

    # 8. Test Export BibTeX
    exp_bib = client.get(f"/api/v1/projects/{project_id}/reviews/export?format=bibtex", headers=headers)
    assert exp_bib.status_code == 200
    assert "@article{" in exp_bib.text
    assert "LitScope Reference" in exp_bib.text


def test_humanizer_de_watermarking():
    """
    Tests the Anti-Watermark / Humanizer pipeline:
    1. Zero-width character & hidden byte removal
    2. Protection of citations and empirical metrics
    3. Replacement of tell-tale AI clichés and logit-sampling crutches
    """
    from app.synthesis.humanizer import dewatermark_academic_prose

    sample_ai_text = (
        "This research \u200bdelves into\uFEFF automated banknote authentication. "
        "Vidyarthi et al. [1] utilized a lightweight model attaining 94.48% accuracy on 7,000 images, "
        "which is a testament to statistical texture analysis. Together, these studies underscore "
        "the pivotal role of LBP Entropy."
    )

    cleaned = dewatermark_academic_prose(sample_ai_text)

    # 1. Zero-width characters removed
    assert "\u200b" not in cleaned
    assert "\ufeff" not in cleaned

    # 2. Citations and numbers preserved exactly
    assert "[1]" in cleaned
    assert "94.48%" in cleaned
    assert "7,000" in cleaned
    assert "LBP" in cleaned

    # 3. AI clichés neutralized
    assert "delves into" not in cleaned.lower()
    assert "testament to" not in cleaned.lower()
    assert "underscores" not in cleaned.lower()
    assert "pivotal" not in cleaned.lower()
    assert "examines" in cleaned or "studied" in cleaned
    assert "key" in cleaned or "central" in cleaned

