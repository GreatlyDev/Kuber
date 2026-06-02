from fastapi.testclient import TestClient

from devassist_api import main
from devassist_core.run_store import run_events_key, run_state_key
from devassist_core.schemas import ExecutionRun, RunEvent, RunStatus


class FakeStore:
    def __init__(self):
        self.runs = {}
        self.events = {}

    def get_run(self, run_id):
        return self.runs.get(run_id)

    def list_events(self, run_id):
        return self.events.get(run_id, [])


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


def test_get_run_events_returns_stored_events():
    store = FakeStore()
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
