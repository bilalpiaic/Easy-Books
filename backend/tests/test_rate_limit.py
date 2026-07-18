"""Part 1/4 of #113 — global rate-limiting middleware.

No mocking needed: RateLimitMiddleware reads its thresholds from env vars
on every request, so tests just lower them via monkeypatch instead of
looping hundreds of times."""
from fastapi.testclient import TestClient


def _signup(client, email):
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "U", "company_name": "Co", "business_model": "simple",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    # Login sets the eb_access cookie on this TestClient instance, which
    # would otherwise silently authenticate every subsequent "anonymous"
    # call in a test -- clear it so cookie-auth is opt-in via an explicit
    # Authorization header only (matches conftest.py's admin_headers fixture).
    client.cookies.clear()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_unauthenticated_requests_are_rate_limited(client: TestClient, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_UNAUTHENTICATED_PER_MIN", "3")

    for _ in range(3):
        r = client.get("/api/customers")
        assert r.status_code == 401  # no auth -- rejected downstream, but still counts

    r = client.get("/api/customers")
    assert r.status_code == 429
    assert "Rate limit" in r.json()["detail"]


def test_authenticated_requests_are_rate_limited_separately(client: TestClient, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_AUTHENTICATED_PER_MIN", "3")
    monkeypatch.setenv("RATE_LIMIT_UNAUTHENTICATED_PER_MIN", "1000")
    auth = _signup(client, "ratelimit1@t.com")

    for _ in range(3):
        r = client.get("/api/customers", headers=auth)
        assert r.status_code == 200

    r = client.get("/api/customers", headers=auth)
    assert r.status_code == 429


def test_authenticated_and_unauthenticated_buckets_are_independent(client: TestClient, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_AUTHENTICATED_PER_MIN", "2")
    monkeypatch.setenv("RATE_LIMIT_UNAUTHENTICATED_PER_MIN", "2")
    auth = _signup(client, "ratelimit2@t.com")

    # Exhaust the anon bucket -- must not affect the authenticated bucket.
    for _ in range(2):
        client.get("/api/customers")
    r = client.get("/api/customers")
    assert r.status_code == 429

    r = client.get("/api/customers", headers=auth)
    assert r.status_code == 200


def test_login_is_exempt_and_governed_only_by_its_own_throttle(client: TestClient, monkeypatch):
    """Login already has a stricter, DB-backed 10/60s-per-IP throttle
    (LoginAttempt) -- the global middleware must not additionally count or
    reject login requests below that threshold."""
    monkeypatch.setenv("RATE_LIMIT_UNAUTHENTICATED_PER_MIN", "3")
    client.post("/api/auth/signup", json={
        "email": "ratelimit3@t.com", "password": "password123",
        "full_name": "U", "company_name": "Co", "business_model": "simple",
    })

    # More attempts than the unauthenticated middleware limit (3), but under
    # login's own 10-attempt threshold -- every one should reach the login
    # handler (401 for a wrong password) rather than 429 from this middleware.
    for _ in range(5):
        r = client.post("/api/auth/login", data={"username": "ratelimit3@t.com", "password": "wrong"})
        assert r.status_code == 401
