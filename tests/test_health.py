from fastapi.testclient import TestClient

from devassist_api import main
from devassist_api.main import app


def setup_function():
    main.execution_runtime = None


def teardown_function():
    main.execution_runtime = None


class FakeRuntime:
    def __init__(self, dependencies):
        self.dependencies = dependencies

    def check_dependencies(self):
        return self.dependencies


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


def test_readyz_reports_configured_runtime_dependencies():
    main.execution_runtime = FakeRuntime(
        {
            "kubernetes": "ok",
            "redis": "ok",
        }
    )
    client = TestClient(app)

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {
            "kubernetes": "ok",
            "redis": "ok",
        },
    }


def test_readyz_returns_503_when_runtime_dependency_is_unavailable():
    main.execution_runtime = FakeRuntime(
        {
            "kubernetes": "ok",
            "redis": "unavailable",
        }
    )
    client = TestClient(app)

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "dependencies": {
            "kubernetes": "ok",
            "redis": "unavailable",
        },
    }
