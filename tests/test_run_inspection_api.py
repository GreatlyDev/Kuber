from fastapi.testclient import TestClient

from devassist_api import main
from devassist_core.run_store import run_events_key, run_state_key
from devassist_core.schemas import ExecutionRun, RunEvent, RunStatus


class FakeStore:
    def __init__(self):
        self.runs = {}
        self.events = {}
        self.list_runs_calls = []

    def get_run(self, run_id):
        return self.runs.get(run_id)

    def list_events(self, run_id):
        return self.events.get(run_id, [])

    def list_runs(self, status=None, limit=50, action=None, app=None, namespace=None):
        self.list_runs_calls.append(
            {
                "status": status,
                "limit": limit,
                "action": action,
                "app": app,
                "namespace": namespace,
            }
        )
        runs = list(self.runs.values())
        if status is not None:
            runs = [run for run in runs if run.status is status]
        if action is not None:
            runs = [run for run in runs if run.plan_action is action]
        if app is not None:
            runs = [run for run in runs if run.plan_app == app]
        if namespace is not None:
            runs = [run for run in runs if run.plan_namespace == namespace]
        return runs[:limit]


class FakeRuntime:
    def __init__(self, store):
        self.store = store


def setup_function():
    main.execution_runtime = None


def teardown_function():
    main.execution_runtime = None


def test_get_run_requires_configured_runtime():
    client = TestClient(main.app)

    response = client.get("/runs/run-123")

    assert response.status_code == 503
    assert response.json() == {"detail": "execution runtime is not configured"}


def test_list_runs_requires_configured_runtime():
    client = TestClient(main.app)

    response = client.get("/runs")

    assert response.status_code == 503
    assert response.json() == {"detail": "execution runtime is not configured"}


def test_list_runs_returns_recent_runs():
    store = FakeStore()
    store.runs["run-123"] = ExecutionRun(
        run_id="run-123",
        plan_id="plan-123",
        plan_summary="Deploy api in namespace dev",
        plan_action="deploy",
        plan_app="api",
        plan_namespace="dev",
        status=RunStatus.SUCCEEDED,
        redis_state_key=run_state_key("run-123"),
    )
    main.execution_runtime = FakeRuntime(store)
    client = TestClient(main.app)

    response = client.get("/runs")

    assert response.status_code == 200
    assert response.json()[0]["run_id"] == "run-123"
    assert response.json()[0]["plan_summary"] == "Deploy api in namespace dev"
    assert response.json()[0]["plan_action"] == "deploy"
    assert response.json()[0]["plan_app"] == "api"
    assert response.json()[0]["plan_namespace"] == "dev"
    assert store.list_runs_calls == [
        {
            "status": None,
            "limit": 50,
            "action": None,
            "app": None,
            "namespace": None,
        }
    ]


def test_list_runs_accepts_status_filter_and_limit():
    store = FakeStore()
    store.runs["run-succeeded"] = ExecutionRun(
        run_id="run-succeeded",
        plan_id="plan-succeeded",
        status=RunStatus.SUCCEEDED,
        redis_state_key=run_state_key("run-succeeded"),
    )
    store.runs["run-failed"] = ExecutionRun(
        run_id="run-failed",
        plan_id="plan-failed",
        status=RunStatus.FAILED,
        redis_state_key=run_state_key("run-failed"),
    )
    main.execution_runtime = FakeRuntime(store)
    client = TestClient(main.app)

    response = client.get("/runs", params={"status": "succeeded", "limit": 1})

    assert response.status_code == 200
    assert [run["run_id"] for run in response.json()] == ["run-succeeded"]
    assert store.list_runs_calls == [
        {
            "status": RunStatus.SUCCEEDED,
            "limit": 1,
            "action": None,
            "app": None,
            "namespace": None,
        }
    ]


def test_list_runs_accepts_plan_metadata_filters():
    store = FakeStore()
    store.runs["run-deploy"] = ExecutionRun(
        run_id="run-deploy",
        plan_id="plan-deploy",
        plan_summary="Deploy api in namespace dev",
        plan_action="deploy",
        plan_app="api",
        plan_namespace="dev",
        status=RunStatus.SUCCEEDED,
        redis_state_key=run_state_key("run-deploy"),
    )
    store.runs["run-scale"] = ExecutionRun(
        run_id="run-scale",
        plan_id="plan-scale",
        plan_summary="Scale api in namespace dev",
        plan_action="scale",
        plan_app="api",
        plan_namespace="dev",
        status=RunStatus.SUCCEEDED,
        redis_state_key=run_state_key("run-scale"),
    )
    main.execution_runtime = FakeRuntime(store)
    client = TestClient(main.app)

    response = client.get(
        "/runs",
        params={"action": "deploy", "app": "api", "namespace": "dev"},
    )

    assert response.status_code == 200
    assert [run["run_id"] for run in response.json()] == ["run-deploy"]
    assert store.list_runs_calls == [
        {
            "status": None,
            "limit": 50,
            "action": "deploy",
            "app": "api",
            "namespace": "dev",
        }
    ]


def test_list_runs_rejects_invalid_app_filter():
    main.execution_runtime = FakeRuntime(FakeStore())
    client = TestClient(main.app)

    response = client.get("/runs", params={"app": "API"})

    assert response.status_code == 422


def test_list_runs_rejects_invalid_namespace_filter():
    main.execution_runtime = FakeRuntime(FakeStore())
    client = TestClient(main.app)

    response = client.get("/runs", params={"namespace": "dev_env"})

    assert response.status_code == 422


def test_get_run_returns_stored_run():
    store = FakeStore()
    store.runs["run-123"] = ExecutionRun(
        run_id="run-123",
        plan_id="plan-123",
        status=RunStatus.SUCCEEDED,
        redis_state_key=run_state_key("run-123"),
    )
    main.execution_runtime = FakeRuntime(store)
    client = TestClient(main.app)

    response = client.get("/runs/run-123")

    assert response.status_code == 200
    assert response.json()["run_id"] == "run-123"
    assert response.json()["status"] == "succeeded"


def test_get_run_returns_404_for_missing_run():
    main.execution_runtime = FakeRuntime(FakeStore())
    client = TestClient(main.app)

    response = client.get("/runs/run-missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "run 'run-missing' was not found"}


def test_get_run_events_returns_404_for_missing_run():
    main.execution_runtime = FakeRuntime(FakeStore())
    client = TestClient(main.app)

    response = client.get("/runs/run-missing/events")

    assert response.status_code == 404
    assert response.json() == {"detail": "run 'run-missing' was not found"}


def test_get_run_events_returns_stored_events():
    store = FakeStore()
    store.runs["run-123"] = ExecutionRun(
        run_id="run-123",
        plan_id="plan-123",
        status=RunStatus.SUCCEEDED,
        redis_state_key=run_state_key("run-123"),
    )
    store.events["run-123"] = [
        RunEvent(
            event_id="evt-123",
            run_id="run-123",
            event_type="run.succeeded",
            message="Run succeeded",
            redis_stream_key=run_events_key("run-123"),
            payload={"messages": ["patched deployment api image"]},
        )
    ]
    main.execution_runtime = FakeRuntime(store)
    client = TestClient(main.app)

    response = client.get("/runs/run-123/events")

    assert response.status_code == 200
    assert response.json()[0]["event_type"] == "run.succeeded"
    assert response.json()[0]["payload"] == {
        "messages": ["patched deployment api image"]
    }
