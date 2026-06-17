from fastapi.testclient import TestClient

from devassist_api import main
from devassist_api.main import app
from devassist_core.plan_repository import InMemoryPlanRepository


def setup_function():
    main.execution_runtime = None
    main.plan_repository = InMemoryPlanRepository()


def teardown_function():
    main.execution_runtime = None
    main.plan_repository = InMemoryPlanRepository()


class FakeRuntime:
    def __init__(self, dependencies):
        self.dependencies = dependencies

    def check_dependencies(self):
        return self.dependencies


class FakePlanRepository:
    def __init__(self, health):
        self.health = health

    def check_health(self):
        return self.health


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
            "plan_store": "memory",
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
            "plan_store": "memory",
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
            "plan_store": "memory",
            "redis": "unavailable",
        },
    }


def test_readyz_reports_plan_store_health():
    main.plan_repository = FakePlanRepository("ok")
    client = TestClient(app)

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {
            "kubernetes": "not_configured",
            "plan_store": "ok",
            "redis": "not_configured",
        },
    }


def test_readyz_returns_503_when_plan_store_is_unavailable():
    main.plan_repository = FakePlanRepository("unavailable")
    client = TestClient(app)

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "dependencies": {
            "kubernetes": "not_configured",
            "plan_store": "unavailable",
            "redis": "not_configured",
        },
    }
