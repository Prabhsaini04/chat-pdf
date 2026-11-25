from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_responds():
    response = client.get("/health")
    assert response.status_code in (200, 503)
    body = response.json()
    assert "status" in body
    assert set(body["checks"].keys()) == {"database", "redis", "ollama"}
