from scripts.local_demo import ApiError, LocalDemoRequest, run_demo


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload
        self.text = str(payload)

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, responses, get_responses=None):
        self.responses = list(responses)
        self.get_responses = list(get_responses or [])
        self.gets = []
        self.posts = []

    def get(self, url):
        self.gets.append({"url": url})
        return self.get_responses.pop(0)

    def post(self, url, json=None):
        self.posts.append({"url": url, "json": json})
        return self.responses.pop(0)


def test_local_demo_creates_approves_and_runs_plan():
    client = FakeClient(
        [
            FakeResponse(201, {"plan_id": "plan-123"}),
            FakeResponse(200, {"plan_id": "plan-123", "status": "approved"}),
            FakeResponse(201, {"run_id": "run-123", "status": "succeeded"}),
        ],
        get_responses=[
            FakeResponse(
                200,
                {
                    "status": "ready",
                    "dependencies": {
                        "kubernetes": "ok",
                        "plan_store": "ok",
                        "redis": "ok",
                    },
                },
            )
        ],
    )

    result = run_demo(
        client,
        LocalDemoRequest(
            base_url="http://localhost:8000",
            text="deploy api to dev with image hashicorp/http-echo:1.0",
            approved_by="great",
        ),
    )

    assert result.plan_id == "plan-123"
    assert result.run_id == "run-123"
    assert result.run_status == "succeeded"
    assert client.gets == [{"url": "http://localhost:8000/readyz"}]
    assert client.posts == [
        {
            "url": "http://localhost:8000/plans",
            "json": {"text": "deploy api to dev with image hashicorp/http-echo:1.0"},
        },
        {
            "url": "http://localhost:8000/plans/plan-123/approve",
            "json": {"approved_by": "great"},
        },
        {
            "url": "http://localhost:8000/plans/plan-123/runs",
            "json": None,
        },
    ]


def test_local_demo_surfaces_api_errors():
    client = FakeClient(
        [FakeResponse(503, {"detail": "execution runtime is not configured"})],
        get_responses=[FakeResponse(200, {"status": "ready"})],
    )

    try:
        run_demo(client, LocalDemoRequest())
    except ApiError as exc:
        assert str(exc) == "POST http://localhost:8000/plans failed with 503: {'detail': 'execution runtime is not configured'}"
    else:
        raise AssertionError("expected API error")


def test_local_demo_stops_when_readiness_http_check_fails():
    client = FakeClient(
        [],
        get_responses=[
            FakeResponse(
                503,
                {
                    "status": "not_ready",
                    "dependencies": {"plan_store": "unavailable"},
                },
            )
        ],
    )

    try:
        run_demo(client, LocalDemoRequest())
    except ApiError as exc:
        assert str(exc) == "GET http://localhost:8000/readyz failed with 503: {'status': 'not_ready', 'dependencies': {'plan_store': 'unavailable'}}"
    else:
        raise AssertionError("expected API error")

    assert client.posts == []


def test_local_demo_stops_when_readiness_body_is_not_ready():
    client = FakeClient(
        [],
        get_responses=[
            FakeResponse(
                200,
                {
                    "status": "not_ready",
                    "dependencies": {"kubernetes": "not_configured"},
                },
            )
        ],
    )

    try:
        run_demo(client, LocalDemoRequest())
    except ApiError as exc:
        assert str(exc) == "DevAssist is not ready: {'kubernetes': 'not_configured'}"
    else:
        raise AssertionError("expected API error")

    assert client.posts == []
