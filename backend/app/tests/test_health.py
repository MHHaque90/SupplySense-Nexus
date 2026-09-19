"""Health endpoint tests."""

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_read_root():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app_name" in data
    assert "version" in data


def test_read_root_live():
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200


def test_read_root_ready():
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
