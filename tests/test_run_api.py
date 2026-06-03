from fastapi.testclient import TestClient

from devassist_api import main
from devassist_core.execution_runtime import ExecutionRunFailedError
from devassist_core.policy import PolicyDecision
from devassist_core.run_store import run_state_key
from devassist_core.schemas import ExecutionRun, RunStatus


class FakeExecutionRuntime:
    def __init__(self):
        self.executed_plan_ids = []

    def execute(self, plan):
        self.executed_plan_ids.append(plan.plan_id)
        return ExecutionRun(
            run_id="run-123",
            plan_id=plan.plan_id,
            status=RunStatus.SUCCEEDED,
            redis_state_key=run_state_key("run-123"),
        )


class FakePolicyRuntime(FakeExecutionRuntime):
    def __init__(self, decision):
        super().__init__()
        self.decision = decision

    def validate(self, plan):
        return self.decision


class FakeFailingRuntime(FakeExecutionRuntime):
    def execute(self, plan):
        self.executed_plan_ids.append(plan.plan_id)
        run = ExecutionRun(
            run_id="run-failed",
            plan_id=plan.plan_id,
            status=RunStatus.FAILED,
            redis_state_key=run_state_key("run-failed"),
        )
        raise ExecutionRunFailedError(run=run, error="cluster unavailable")


def setup_function():
    main.plan_repository.clear()
    main.execution_runtime = None


def test_execution_endpoint_requires_configured_runtime():
    client = TestClient(main.app)
    created = client.post(
        "/plans",
        json={"text": "deploy api to dev with image example/api:1.0.0"},
    ).json()
    client.post(
        f"/plans/{created['plan_id']}/approve",
        json={"approved_by": "great"},
    )

    response = client.post(f"/plans/{created['plan_id']}/runs")

    assert response.status_code == 503
    assert response.json() == {"detail": "execution runtime is not configured"}


def test_execution_endpoint_runs_approved_plan_with_runtime():
    runtime = FakeExecutionRuntime()
    main.execution_runtime = runtime
    client = TestClient(main.app)
    created = client.post(
        "/plans",
        json={"text": "deploy api to dev with image example/api:1.0.0"},
    ).json()
    client.post(
        f"/plans/{created['plan_id']}/approve",
        json={"approved_by": "great"},
    )

    response = client.post(f"/plans/{created['plan_id']}/runs")

    assert response.status_code == 201
    assert response.json()["status"] == "succeeded"
    assert response.json()["plan_id"] == created["plan_id"]
    assert runtime.executed_plan_ids == [created["plan_id"]]


def test_execution_endpoint_returns_failed_run_details_when_execution_fails():
    runtime = FakeFailingRuntime()
    main.execution_runtime = runtime
    client = TestClient(main.app)
    created = client.post(
        "/plans",
        json={"text": "deploy api to dev with image example/api:1.0.0"},
    ).json()
    client.post(
        f"/plans/{created['plan_id']}/approve",
        json={"approved_by": "great"},
    )

    response = client.post(f"/plans/{created['plan_id']}/runs")

    assert response.status_code == 500
    assert response.json() == {
        "detail": {
            "message": "execution failed",
            "run_id": "run-failed",
            "status": "failed",
            "error": "cluster unavailable",
            "events_path": "/runs/run-failed/events",
        }
    }
    assert runtime.executed_plan_ids == [created["plan_id"]]


def test_execution_endpoint_returns_policy_error_for_draft_plan():
    runtime = FakeExecutionRuntime()
    main.execution_runtime = runtime
    client = TestClient(main.app)
    created = client.post(
        "/plans",
        json={"text": "deploy api to dev with image example/api:1.0.0"},
    ).json()

    response = client.post(f"/plans/{created['plan_id']}/runs")

    assert response.status_code == 403
    assert response.json() == {
        "detail": ["mutating Kubernetes actions require an approved ExecutionPlan"]
    }
    assert runtime.executed_plan_ids == []


def test_execution_endpoint_returns_policy_error_for_rejected_status_plan():
    runtime = FakeExecutionRuntime()
    main.execution_runtime = runtime
    client = TestClient(main.app)
    created = client.post("/plans", json={"text": "status api in dev"}).json()
    client.post(f"/plans/{created['plan_id']}/reject")

    response = client.post(f"/plans/{created['plan_id']}/runs")

    assert response.status_code == 403
    assert response.json() == {"detail": ["rejected ExecutionPlans cannot be run"]}
    assert runtime.executed_plan_ids == []


def test_execution_endpoint_uses_runtime_policy_before_running_plan():
    runtime = FakePolicyRuntime(
        PolicyDecision(
            allowed=False,
            reasons=["namespace 'staging' is outside the configured namespace allowlist"],
        )
    )
    main.execution_runtime = runtime
    client = TestClient(main.app)
    created = client.post(
        "/plans",
        json={"text": "deploy api to staging with image example/api:1.0.0"},
    ).json()
    client.post(
        f"/plans/{created['plan_id']}/approve",
        json={"approved_by": "great"},
    )

    response = client.post(f"/plans/{created['plan_id']}/runs")

    assert response.status_code == 403
    assert response.json() == {
        "detail": ["namespace 'staging' is outside the configured namespace allowlist"]
    }
    assert runtime.executed_plan_ids == []
