import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def create_authenticated_user(name: str):
    email = f"{name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:6]}@example.com"
    pwd = "TestPassword123!"
    client.post("/api/v1/auth/register", json={"email": email, "password": pwd, "full_name": name})
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    token = login_res.json()["access_token"]
    user_id = login_res.json()["user"]["id"]
    return {"email": email, "user_id": user_id, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


def test_project_multi_user_permissions():
    user_a = create_authenticated_user("Researcher Alice")
    user_b = create_authenticated_user("Collaborator Bob")
    user_c = create_authenticated_user("Outside Charlie")

    # 1. Alice creates Private Project
    p_res = client.post(
        "/api/v1/projects",
        json={"name": "Alice Confidential Study", "scope": "Private 2026"},
        headers=user_a["headers"]
    )
    assert p_res.status_code == 201
    project_id = p_res.json()["id"]

    # 2. Bob (uninvited) tries to access Alice's project -> 403 Forbidden
    uninvited_res = client.get(f"/api/v1/projects/{project_id}", headers=user_b["headers"])
    assert uninvited_res.status_code == 403

    # 3. Alice invites Bob as a 'viewer'
    invite_res = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"email": user_b["email"], "role": "viewer"},
        headers=user_a["headers"]
    )
    assert invite_res.status_code == 201

    # 4. Bob can now view the project
    bob_view = client.get(f"/api/v1/projects/{project_id}", headers=user_b["headers"])
    assert bob_view.status_code == 200

    # 5. Create a paper in master library (Alice as Owner)
    paper_res = client.post(
        "/api/v1/papers",
        json={"title": "Quantum Fleet Algorithms", "year": 2025},
        headers=user_a["headers"]
    )
    assert paper_res.status_code == 201
    paper_id = paper_res.json()["id"]

    # 5b. Unauthenticated access to master library is rejected
    assert client.get("/api/v1/papers").status_code == 401

    # 6. Bob (viewer) tries to curate paper -> 403 Forbidden (requires editor)
    bob_curate_fail = client.post(
        f"/api/v1/projects/{project_id}/papers",
        json={"paper_id": paper_id, "inclusion_status": "included"},
        headers=user_b["headers"]
    )
    assert bob_curate_fail.status_code == 403

    # 7. Alice promotes Bob to 'editor'
    promote_res = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"email": user_b["email"], "role": "editor"},
        headers=user_a["headers"]
    )
    assert promote_res.status_code == 201

    # 8. Bob (editor) can now curate the paper
    bob_curate_success = client.post(
        f"/api/v1/projects/{project_id}/papers",
        json={"paper_id": paper_id, "inclusion_status": "included", "notes": "Bob curated this."},
        headers=user_b["headers"]
    )
    assert bob_curate_success.status_code == 201

    # 9. Bob (editor) tries to invite Charlie -> 403 Forbidden (only owner can invite)
    bob_invite_fail = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"email": user_c["email"], "role": "viewer"},
        headers=user_b["headers"]
    )
    assert bob_invite_fail.status_code == 403

    # 10. Alice removes Bob from project
    del_res = client.delete(f"/api/v1/projects/{project_id}/members/{user_b['user_id']}", headers=user_a["headers"])
    assert del_res.status_code == 204

    # 11. Bob tries to access again -> 403 Forbidden
    bob_locked_out = client.get(f"/api/v1/projects/{project_id}", headers=user_b["headers"])
    assert bob_locked_out.status_code == 403
