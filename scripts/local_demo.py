import argparse
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class LocalDemoRequest:
    base_url: str = "http://localhost:8000"
    text: str = "deploy api to dev with image hashicorp/http-echo:1.0"
    approved_by: str = "great"


@dataclass(frozen=True)
class LocalDemoResult:
    plan_id: str
    run_id: str
    run_status: str


@dataclass(frozen=True)
class PlanOnlyDemoResult:
    plan_id: str
    approved_status: str
    policy_before_allowed: bool
    policy_after_allowed: bool
    pending_approval_count: int


class ApiError(Exception):
    pass


def run_demo(client, request: LocalDemoRequest = LocalDemoRequest()) -> LocalDemoResult:
    base_url = request.base_url.rstrip("/")

    _check_readiness(client, f"{base_url}/readyz")

    plan = _post(
        client,
        f"{base_url}/plans",
        {"text": request.text},
    )
    plan_id = plan["plan_id"]

    _post(
        client,
        f"{base_url}/plans/{plan_id}/approve",
        {"approved_by": request.approved_by},
    )

    run = _post(
        client,
        f"{base_url}/plans/{plan_id}/runs",
        None,
    )
    return LocalDemoResult(
        plan_id=plan_id,
        run_id=run["run_id"],
        run_status=run["status"],
    )


def run_plan_only_demo(
    client,
    request: LocalDemoRequest = LocalDemoRequest(),
) -> PlanOnlyDemoResult:
    base_url = request.base_url.rstrip("/")

    _check_readiness(client, f"{base_url}/readyz")

    plan = _post(
        client,
        f"{base_url}/plans",
        {"text": request.text},
    )
    plan_id = plan["plan_id"]
    policy_before = _get(client, f"{base_url}/plans/{plan_id}/policy")
    pending_approvals = _get(client, f"{base_url}/approvals/pending?limit=10")

    approved = _post(
        client,
        f"{base_url}/plans/{plan_id}/approve",
        {"approved_by": request.approved_by},
    )
    policy_after = _get(client, f"{base_url}/plans/{plan_id}/policy")

    return PlanOnlyDemoResult(
        plan_id=plan_id,
        approved_status=approved["status"],
        policy_before_allowed=policy_before["allowed"],
        policy_after_allowed=policy_after["allowed"],
        pending_approval_count=len(pending_approvals),
    )


def _check_readiness(client, url: str) -> None:
    body = _get(client, url)
    if body.get("status") != "ready":
        raise ApiError(f"DevAssist is not ready: {body.get('dependencies', {})}")


def _get(client, url: str) -> Any:
    response = client.get(url)
    body = response.json()
    if response.status_code >= 400:
        raise ApiError(f"GET {url} failed with {response.status_code}: {body}")
    return body


def _post(client, url: str, payload: dict[str, str] | None) -> dict:
    response = client.post(url, json=payload)
    if response.status_code >= 400:
        raise ApiError(
            f"POST {url} failed with {response.status_code}: {response.json()}"
        )
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local DevAssist demo flow.")
    parser.add_argument("--base-url", default=LocalDemoRequest.base_url)
    parser.add_argument("--text", default=LocalDemoRequest.text)
    parser.add_argument("--approved-by", default=LocalDemoRequest.approved_by)
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Create, inspect, and approve a plan without running Kubernetes execution.",
    )
    args = parser.parse_args()

    with httpx.Client(timeout=20) as client:
        request = LocalDemoRequest(
            base_url=args.base_url,
            text=args.text,
            approved_by=args.approved_by,
        )
        if args.plan_only:
            plan_result = run_plan_only_demo(client, request)
            print(f"Plan: {plan_result.plan_id}")
            print(f"Pending approvals: {plan_result.pending_approval_count}")
            print(f"Policy before approval allowed: {plan_result.policy_before_allowed}")
            print(f"Approved status: {plan_result.approved_status}")
            print(f"Policy after approval allowed: {plan_result.policy_after_allowed}")
            return

        result = run_demo(client, request)

    print(f"Plan: {result.plan_id}")
    print(f"Run: {result.run_id}")
    print(f"Status: {result.run_status}")


if __name__ == "__main__":
    main()
