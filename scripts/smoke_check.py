import argparse
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class SmokeCheckRequest:
    base_url: str = "http://localhost:8000"
    text: str = "deploy api to dev with image hashicorp/http-echo:1.0"
    approved_by: str = "great"


@dataclass(frozen=True)
class SmokeCheckResult:
    plan_id: str
    health_status: str
    ready_status: str
    dashboard_loaded: bool
    pending_approval_count: int
    policy_before_allowed: bool
    policy_after_allowed: bool
    approved_status: str


class ApiError(Exception):
    pass


def run_smoke_check(
    client,
    request: SmokeCheckRequest = SmokeCheckRequest(),
) -> SmokeCheckResult:
    base_url = request.base_url.rstrip("/")

    health = _get_json(client, f"{base_url}/healthz")
    ready = _get_json(client, f"{base_url}/readyz")
    if ready.get("status") != "ready":
        raise ApiError(f"DevAssist is not ready: {ready.get('dependencies', {})}")

    dashboard = _get_text(client, f"{base_url}/approvals/dashboard")
    _get_text(client, f"{base_url}/assets/approval-dashboard.js")
    _get_text(client, f"{base_url}/assets/approval-dashboard.css")

    plan = _post_json(
        client,
        f"{base_url}/plans",
        {"text": request.text},
    )
    plan_id = plan["plan_id"]
    pending_approvals = _get_json(client, f"{base_url}/approvals/pending?limit=25")
    policy_before = _get_json(client, f"{base_url}/plans/{plan_id}/policy")

    approved = _post_json(
        client,
        f"{base_url}/plans/{plan_id}/approve",
        {"approved_by": request.approved_by},
    )
    policy_after = _get_json(client, f"{base_url}/plans/{plan_id}/policy")

    return SmokeCheckResult(
        plan_id=plan_id,
        health_status=health["status"],
        ready_status=ready["status"],
        dashboard_loaded='id="approval-list"' in dashboard,
        pending_approval_count=len(pending_approvals),
        policy_before_allowed=policy_before["allowed"],
        policy_after_allowed=policy_after["allowed"],
        approved_status=approved["status"],
    )


def _get_json(client, url: str) -> Any:
    response = client.get(url)
    body = response.json()
    if response.status_code >= 400:
        raise ApiError(f"GET {url} failed with {response.status_code}: {body}")
    return body


def _get_text(client, url: str) -> str:
    response = client.get(url)
    if response.status_code >= 400:
        raise ApiError(
            f"GET {url} failed with {response.status_code}: {_safe_json(response)}"
        )
    return response.text


def _post_json(client, url: str, payload: dict[str, str]) -> dict[str, Any]:
    response = client.post(url, json=payload)
    body = response.json()
    if response.status_code >= 400:
        raise ApiError(f"POST {url} failed with {response.status_code}: {body}")
    return body


def _safe_json(response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local DevAssist smoke check.")
    parser.add_argument("--base-url", default=SmokeCheckRequest.base_url)
    parser.add_argument("--text", default=SmokeCheckRequest.text)
    parser.add_argument("--approved-by", default=SmokeCheckRequest.approved_by)
    args = parser.parse_args()

    with httpx.Client(timeout=20) as client:
        result = run_smoke_check(
            client,
            SmokeCheckRequest(
                base_url=args.base_url,
                text=args.text,
                approved_by=args.approved_by,
            ),
        )

    print(f"Health: {result.health_status}")
    print(f"Readiness: {result.ready_status}")
    print(f"Dashboard loaded: {result.dashboard_loaded}")
    print(f"Plan: {result.plan_id}")
    print(f"Pending approvals: {result.pending_approval_count}")
    print(f"Policy before approval allowed: {result.policy_before_allowed}")
    print(f"Approved status: {result.approved_status}")
    print(f"Policy after approval allowed: {result.policy_after_allowed}")


if __name__ == "__main__":
    main()
