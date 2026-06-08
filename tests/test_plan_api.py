from fastapi.testclient import TestClient

from devassist_api import main
from devassist_api.main import app, plan_repository
from devassist_core.policy import PolicyDecision


def setup_function():
    plan_repository.clear()
    main.execution_runtime = None


def teardown_function():
    main.execution_runtime = None


class FakePolicyRuntime:
    def __init__(self, decision):
        self.decision = decision
        self.validated_plan_ids = []

    def validate(self, plan):
        self.validated_plan_ids.append(plan.plan_id)
        return self.decision


def test_creates_draft_plan_from_text_without_executing():
    client = TestClient(app)

    response = client.post(
        "/plans",
        json={"text": "deploy api to dev with image example/api:1.0.0"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["approved"] is False
    assert body["summary"] == "Deploy api in namespace dev"
    assert body["intent"]["raw_text"] == "deploy api to dev with image example/api:1.0.0"


def test_create_plan_returns_400_for_invalid_intent():
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/plans",
        json={"text": "deploy api to dev"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": {
            "message": "invalid pipeline intent",
            "errors": ["Value error, image is required for deploy intents"],
        }
    }


def test_gets_created_plan():
    client = TestClient(app)
    created = client.post(
        "/plans",
        json={"text": "deploy api to dev with image example/api:1.0.0"},
    ).json()

    response = client.get(f"/plans/{created['plan_id']}")

    assert response.status_code == 200
    assert response.json()["plan_id"] == created["plan_id"]


def test_approves_plan_and_policy_allows_it():
    client = TestClient(app)
    created = client.post(
        "/plans",
        json={"text": "deploy api to dev with image example/api:1.0.0"},
    ).json()

    approved = client.post(
        f"/plans/{created['plan_id']}/approve",
        json={"approved_by": "great"},
    )
    policy = client.get(f"/plans/{created['plan_id']}/policy")

    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"] == "great"
    assert policy.json() == {"allowed": True, "reasons": []}


def test_policy_rejects_draft_mutating_plan():
    client = TestClient(app)
    created = client.post(
        "/plans",
        json={"text": "deploy api to dev with image example/api:1.0.0"},
    ).json()

    response = client.get(f"/plans/{created['plan_id']}/policy")

    assert response.status_code == 200
    assert response.json() == {
        "allowed": False,
        "reasons": ["mutating Kubernetes actions require an approved ExecutionPlan"],
    }


def test_policy_endpoint_uses_runtime_policy_when_configured():
    runtime = FakePolicyRuntime(
        PolicyDecision(
            allowed=False,
            reasons=["namespace 'staging' is outside the configured namespace allowlist"],
        )
    )
    main.execution_runtime = runtime
    client = TestClient(app)
    created = client.post(
        "/plans",
        json={"text": "deploy api to staging with image example/api:1.0.0"},
    ).json()
    client.post(
        f"/plans/{created['plan_id']}/approve",
        json={"approved_by": "great"},
    )

    response = client.get(f"/plans/{created['plan_id']}/policy")

    assert response.status_code == 200
    assert response.json() == {
        "allowed": False,
        "reasons": ["namespace 'staging' is outside the configured namespace allowlist"],
    }
    assert runtime.validated_plan_ids == [created["plan_id"]]


def test_rejects_plan():
    client = TestClient(app)
    created = client.post(
        "/plans",
        json={"text": "deploy api to dev with image example/api:1.0.0"},
    ).json()

    response = client.post(f"/plans/{created['plan_id']}/reject")

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_approve_rejected_plan_returns_400():
    client = TestClient(app)
    created = client.post(
        "/plans",
        json={"text": "deploy api to dev with image example/api:1.0.0"},
    ).json()
    client.post(f"/plans/{created['plan_id']}/reject")

    response = client.post(
        f"/plans/{created['plan_id']}/approve",
        json={"approved_by": "great"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "only draft ExecutionPlans can be approved"}


def test_reject_approved_plan_returns_400():
    client = TestClient(app)
    created = client.post(
        "/plans",
        json={"text": "deploy api to dev with image example/api:1.0.0"},
    ).json()
    client.post(
        f"/plans/{created['plan_id']}/approve",
        json={"approved_by": "great"},
    )

    response = client.post(f"/plans/{created['plan_id']}/reject")

    assert response.status_code == 400
    assert response.json() == {"detail": "only draft ExecutionPlans can be rejected"}
