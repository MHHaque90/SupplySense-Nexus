"""Phase 12A CORS tests (localhost dev origins, no wildcard).

The dashboard frontend runs from ``http://localhost:5173`` in
development; preflight must allow it with credentials while unknown
origins never receive an Access-Control-Allow-Origin header.
"""

from backend.app.core.config import settings
from backend.app.tests.api_support import RAW_ANALYST_KEY, auth

ALLOWED_ORIGIN = "http://localhost:5173"
DISALLOWED_ORIGIN = "https://evil.example"


def test_cors_configuration_allows_local_dev_without_wildcard():
    assert ALLOWED_ORIGIN in settings.CORS_ORIGINS, settings.CORS_ORIGINS
    assert "*" not in settings.CORS_ORIGINS, settings.CORS_ORIGINS


async def test_preflight_allows_local_dev_origin(ai_client):
    response = await ai_client.options(
        "/api/v1/auth/me",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code in (200, 204), response.text
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    assert response.headers.get("access-control-allow-credentials") == "true"
    allowed_headers = response.headers.get("access-control-allow-headers", "")
    assert "authorization" in allowed_headers.lower(), allowed_headers


async def test_unknown_origin_never_gets_cors_headers(ai_client):
    preflight = await ai_client.options(
        "/api/v1/auth/me",
        headers={
            "Origin": DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert (
        preflight.headers.get("access-control-allow-origin") != DISALLOWED_ORIGIN
    ), preflight.headers
    actual = await ai_client.get(
        "/api/v1/auth/me",
        headers={"Origin": DISALLOWED_ORIGIN, **auth(RAW_ANALYST_KEY)},
    )
    assert (
        actual.headers.get("access-control-allow-origin") != DISALLOWED_ORIGIN
    ), actual.headers
