from fastapi.testclient import TestClient

from devassist_api.main import app


def test_healthz_returns_ok_status():
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_reports_dependency_placeholders():
    client = TestClient(app)

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {
            "kubernetes": "not_configured",
            "redis": "not_configured",
        },
    }
