"""Phase 12A identity endpoint tests (``GET /api/v1/auth/me``).

Covers the envelope, the derived data label, missing/malformed/unknown/
inactive credentials (401), and the no-secret-leak guarantee.
"""

from backend.app.core.security import generate_api_key
from backend.app.tests.api_support import (
    RAW_ANALYST_KEY,
    RAW_INACTIVE_KEY,
    assert_envelope,
    assert_error,
    auth,
    seed_api_org,
)


async def test_auth_me_returns_identity(ai_client):
    org_id = await seed_api_org()
    response = await ai_client.get("/api/v1/auth/me", headers=auth(RAW_ANALYST_KEY))
    assert response.status_code == 200
    body = response.json()
    data = assert_envelope(body, label="derived")
    assert data["role"] == "analyst"
    assert data["organization_id"] == org_id
    assert data["is_active"] is True
    assert data["user_id"]
    assert "@" in data["email"]
    for secret in ("api_key", "api_key_hash", "password_hash", "password"):
        assert secret not in data, secret
    assert body["meta"]["source"] == "authenticated_identity"


async def test_auth_me_requires_bearer_key(ai_client):
    response = await ai_client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert_error(response.json(), "UNAUTHORIZED")


async def test_auth_me_rejects_malformed_header(ai_client):
    response = await ai_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Basic not-a-bearer-token"}
    )
    assert response.status_code == 401
    assert_error(response.json(), "UNAUTHORIZED")


async def test_auth_me_rejects_unknown_valid_key(ai_client):
    await seed_api_org()
    response = await ai_client.get(
        "/api/v1/auth/me", headers=auth(generate_api_key())
    )
    assert response.status_code == 401
    assert_error(response.json(), "UNAUTHORIZED")


async def test_auth_me_rejects_inactive_user(ai_client):
    await seed_api_org()
    response = await ai_client.get("/api/v1/auth/me", headers=auth(RAW_INACTIVE_KEY))
    assert response.status_code == 401
    assert_error(response.json(), "UNAUTHORIZED")
