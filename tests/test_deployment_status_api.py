from datetime import UTC, datetime

from fastapi.testclient import TestClient

from devassist_api import main
from devassist_core.kubernetes_executor import KubernetesExecutionResult
from devassist_core.policy import PolicyDecision
from devassist_core.schemas import DeploymentAction, DeploymentState


class FakeExecutor:
    def __init__(self):
        self.plans = []

    def execute(self, plan):
        self.plans.append(plan)
        return KubernetesExecutionResult(
            applied=False,
            policy=PolicyDecision(allowed=True, reasons=[]),
            deployment_state=DeploymentState(
                app="api",
                namespace="dev",
                desired_image=None,
                current_image="hashicorp/http-echo:1.0",
                replicas=1,
                available_replicas=1,
                observed_at=datetime(2026, 6, 2, tzinfo=UTC),
            ),
            messages=[],
        )


class FakeRuntime:
    def __init__(self, executor):
        self.executor = executor


def setup_function():
    main.execution_runtime = None


def teardown_function():
    main.execution_runtime = None


def test_deployment_state_requires_configured_runtime():
    client = TestClient(main.app)

    response = client.get("/deployments/dev/api/state")

    assert response.status_code == 503
    assert response.json() == {"detail": "execution runtime is not configured"}


def test_deployment_state_reads_status_through_executor():
    executor = FakeExecutor()
    main.execution_runtime = FakeRuntime(executor)
    client = TestClient(main.app)

    response = client.get("/deployments/dev/api/state")

    assert response.status_code == 200
    assert response.json()["app"] == "api"
    assert response.json()["namespace"] == "dev"
    assert response.json()["current_image"] == "hashicorp/http-echo:1.0"
    assert response.json()["available_replicas"] == 1
    assert len(executor.plans) == 1
    assert executor.plans[0].intent.action is DeploymentAction.STATUS
    assert executor.plans[0].requires_approval is False


def test_deployment_state_returns_404_when_executor_has_no_state():
    class NoStateExecutor:
        def execute(self, plan):
            return KubernetesExecutionResult(
                applied=False,
                policy=PolicyDecision(allowed=True, reasons=[]),
                deployment_state=None,
                messages=[],
            )

    main.execution_runtime = FakeRuntime(NoStateExecutor())
    client = TestClient(main.app)

    response = client.get("/deployments/dev/missing/state")

    assert response.status_code == 404
    assert response.json() == {"detail": "deployment 'dev/missing' was not found"}


def test_deployment_state_returns_policy_error_when_namespace_is_blocked():
    class PolicyDeniedExecutor:
        def execute(self, plan):
            return KubernetesExecutionResult(
                applied=False,
                policy=PolicyDecision(
                    allowed=False,
                    reasons=["namespace 'prod' is outside the local MVP allowlist"],
                ),
                deployment_state=None,
                messages=[],
            )

    main.execution_runtime = FakeRuntime(PolicyDeniedExecutor())
    client = TestClient(main.app)

    response = client.get("/deployments/prod/api/state")

    assert response.status_code == 403
    assert response.json() == {
        "detail": ["namespace 'prod' is outside the local MVP allowlist"]
    }
