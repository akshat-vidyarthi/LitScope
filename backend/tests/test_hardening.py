import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.rate_limiter import limiter


@pytest.fixture(autouse=True)
def reset_limiter():
    """Clear in-memory rate limiter state before each test."""
    limiter._requests.clear()
    yield
    limiter._requests.clear()


client = TestClient(app)


def test_health_check_exempt_from_rate_limiting():
    """Health endpoint must remain reachable without rate limiting."""
    for _ in range(50):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


def test_auth_rate_limiting_enforcement():
    """Authentication endpoints must block after 10 requests within a minute."""
    for i in range(10):
        resp = client.post("/api/v1/auth/login", json={"username": f"user{i}", "password": "wrongpassword"})
        # Should return 401 Unauthorized or 400, not 429 yet
        assert resp.status_code in [400, 401]

    # 11th request must be rejected with 429 Too Many Requests
    resp = client.post("/api/v1/auth/login", json={"username": "user11", "password": "wrongpassword"})
    assert resp.status_code == 429
    data = resp.json()
    assert "Rate limit exceeded" in data["detail"]
    assert "retry_after" in data
    assert resp.headers.get("Retry-After") is not None


def test_upload_non_pdf_rejected():
    """Uploading non-PDF file should be rejected with 400 Bad Request."""
    username = "harden_user_test"
    password = "password123!"
    client.post("/api/v1/auth/register", json={"username": username, "password": password})
    login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    token = login.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("test.txt", b"Hello world text", "text/plain")}
    resp = client.post("/api/v1/papers/upload", files=files, headers=headers)
    assert resp.status_code == 400
    assert "PDF" in resp.json()["detail"]
