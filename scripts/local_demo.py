import argparse
from dataclasses import dataclass

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


class ApiError(Exception):
    pass


def run_demo(client, request: LocalDemoRequest = LocalDemoRequest()) -> LocalDemoResult:
    base_url = request.base_url.rstrip("/")

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
    args = parser.parse_args()

    with httpx.Client(timeout=20) as client:
        result = run_demo(
            client,
            LocalDemoRequest(
                base_url=args.base_url,
                text=args.text,
                approved_by=args.approved_by,
            ),
        )

    print(f"Plan: {result.plan_id}")
    print(f"Run: {result.run_id}")
    print(f"Status: {result.run_status}")


if __name__ == "__main__":
    main()
