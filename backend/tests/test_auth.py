import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_user_registration_and_login():
    test_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword123!"

    # 1. Register a new user
    reg_payload = {
        "email": test_email,
        "password": password,
        "full_name": "Alice Researcher"
    }
    reg_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    user_data = reg_res.json()
    assert user_data["email"] == test_email
    assert user_data["full_name"] == "Alice Researcher"
    assert "hashed_password" not in user_data  # Ensure password hash is never exposed

    # 2. Prevent duplicate email registration
    dup_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert dup_res.status_code == 409

    # 3. Fail login with incorrect password
    bad_login = client.post("/api/v1/auth/login", json={"email": test_email, "password": "WrongPassword"})
    assert bad_login.status_code == 401

    # 4. Successful login
    login_res = client.post("/api/v1/auth/login", json={"email": test_email, "password": password})
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    token = token_data["access_token"]

    # 5. Access protected /auth/me with Bearer token
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == test_email

    # 6. Reject /auth/me without token
    unauth_res = client.get("/api/v1/auth/me")
    assert unauth_res.status_code == 401
