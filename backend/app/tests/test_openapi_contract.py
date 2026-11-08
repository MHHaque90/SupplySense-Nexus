"""Phase 12A OpenAPI contract tests (route presence and strict bodies)."""

from backend.app.main import app

EXPECTED_ENDPOINTS = {
    "/api/v1/auth/me": {"get"},
    "/api/v1/dashboard/overview": {"get"},
    "/api/v1/forecast": {"get"},
    "/api/v1/inventory/overview": {"get"},
    "/api/v1/inventory/positions": {"get"},
    "/api/v1/inventory/health": {"get"},
    "/api/v1/suppliers": {"get"},
    "/api/v1/suppliers/performance": {"get"},
    "/api/v1/procurement/overview": {"get"},
    "/api/v1/procurement/open-orders": {"get"},
    "/api/v1/procurement/inbound": {"get"},
    "/api/v1/procurement/risk": {"get"},
    "/api/v1/risk": {"get"},
    "/api/v1/simulation/events": {"get"},
    "/api/v1/simulation/run": {"post"},
    "/api/v1/replay/decisions": {"get"},
    "/api/v1/replay/run": {"post"},
    "/api/v1/optimization/run": {"post"},
}


def test_openapi_lists_every_phase12a_endpoint():
    paths = app.openapi()["paths"]
    for path, methods in EXPECTED_ENDPOINTS.items():
        assert path in paths, f"missing path: {path}"
        for method in methods:
            assert method in paths[path], f"missing {method.upper()} {path}"


def test_compute_request_bodies_forbid_unknown_fields():
    schemas = app.openapi()["components"]["schemas"]
    for name in (
        "SimulationRunRequest",
        "ReplayRunRequest",
        "OptimizationRunRequest",
        "DecisionArm",
    ):
        assert name in schemas, name
        assert schemas[name].get("additionalProperties") is False, name


def test_preexisting_routes_still_registered():
    paths = app.openapi()["paths"]
    assert len(paths) >= len(EXPECTED_ENDPOINTS), sorted(paths)
    assert "/api/v1/ai/chat" in paths, "Phase 11 AI routes must stay registered"
