import pytest

from scripts.smoke_check import ApiError, SmokeCheckRequest, run_smoke_check


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self.payload = payload
        self.text = text

    def json(self):
        if self.payload is None:
            raise ValueError("response did not contain JSON")
        return self.payload


class FakeClient:
    def __init__(self, get_responses=None, post_responses=None):
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.gets = []
        self.posts = []

    def get(self, url):
        self.gets.append({"url": url})
        return self.get_responses.pop(0)

    def post(self, url, json=None):
        self.posts.append({"url": url, "json": json})
        return self.post_responses.pop(0)


def test_smoke_check_exercises_safe_local_mvp_without_running_plan():
    client = FakeClient(
        get_responses=[
            FakeResponse(200, {"status": "ok"}),
            FakeResponse(
                200,
                {
                    "status": "ready",
                    "dependencies": {
                        "kubernetes": "not_configured",
                        "plan_store": "memory",
                        "redis": "not_configured",
                    },
                },
            ),
            FakeResponse(200, text="<section id=\"approval-list\"></section>"),
            FakeResponse(200, text="async function loadPendingApprovals() {}"),
            FakeResponse(200, text=".approval-list {}"),
            FakeResponse(
                200,
                [
                    {
                        "plan": {"plan_id": "plan-123"},
                        "policy": {
                            "allowed": False,
                            "reasons": ["needs approval"],
                        },
                    }
                ],
            ),
            FakeResponse(200, {"allowed": False, "reasons": ["needs approval"]}),
            FakeResponse(200, {"allowed": True, "reasons": []}),
        ],
        post_responses=[
            FakeResponse(201, {"plan_id": "plan-123"}),
            FakeResponse(200, {"plan_id": "plan-123", "status": "approved"}),
        ],
    )

    result = run_smoke_check(
        client,
        SmokeCheckRequest(
            base_url="http://localhost:8000",
            text="deploy api to dev with image hashicorp/http-echo:1.0",
            approved_by="great",
        ),
    )

    assert result.plan_id == "plan-123"
    assert result.health_status == "ok"
    assert result.ready_status == "ready"
    assert result.dashboard_loaded is True
    assert result.pending_approval_count == 1
    assert result.policy_before_allowed is False
    assert result.policy_after_allowed is True
    assert result.approved_status == "approved"
    assert client.gets == [
        {"url": "http://localhost:8000/healthz"},
        {"url": "http://localhost:8000/readyz"},
        {"url": "http://localhost:8000/approvals/dashboard"},
        {"url": "http://localhost:8000/assets/approval-dashboard.js"},
        {"url": "http://localhost:8000/assets/approval-dashboard.css"},
        {"url": "http://localhost:8000/approvals/pending?limit=25"},
        {"url": "http://localhost:8000/plans/plan-123/policy"},
        {"url": "http://localhost:8000/plans/plan-123/policy"},
    ]
    assert client.posts == [
        {
            "url": "http://localhost:8000/plans",
            "json": {"text": "deploy api to dev with image hashicorp/http-echo:1.0"},
        },
        {
            "url": "http://localhost:8000/plans/plan-123/approve",
            "json": {"approved_by": "great"},
        },
    ]


def test_smoke_check_surfaces_dashboard_errors():
    client = FakeClient(
        get_responses=[
            FakeResponse(200, {"status": "ok"}),
            FakeResponse(200, {"status": "ready", "dependencies": {}}),
            FakeResponse(404, {"detail": "not found"}),
        ]
    )

    with pytest.raises(ApiError) as exc:
        run_smoke_check(client, SmokeCheckRequest())

    assert str(exc.value) == (
        "GET http://localhost:8000/approvals/dashboard failed with 404: "
        "{'detail': 'not found'}"
    )
