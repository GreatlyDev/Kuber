# Local MVP Demo Walkthrough

This walkthrough is the repo-facing demo script for DevAssist. It is meant to show the finished local MVP clearly without pretending it is a production deployment.

## What You Are Demonstrating

DevAssist is a Kubernetes-native AI-assisted CI/CD orchestrator with a safety-first control plane. The demo shows that a natural-language deployment request can become a strict, inspectable execution plan; that mutating Kubernetes actions stay blocked until a human approves the plan; and that run state is designed around Redis-backed records and events.

The important resume points are:

- FastAPI control plane for plan, approval, run, readiness, and deployment-state APIs
- Strict Pydantic schemas and deterministic validation
- Human approval gate before mutating Kubernetes actions
- Redis-backed run state and event timeline
- Kubernetes Python API client integration instead of command execution
- Docker Compose local workflow, container build, and GitHub Actions smoke checks

## Safe Demo Path

Use this path when you want to show the MVP without touching a live Kubernetes deployment.

```powershell
docker compose up --build
```

In a second terminal:

```powershell
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
python scripts/smoke_check.py
python scripts/local_demo.py --plan-only
```

The smoke check verifies health, readiness, dashboard assets, pending approvals, policy preview, and approval. The plan-only demo creates a plan, checks policy before approval, checks pending approvals, approves the plan, and checks policy again. It does not call `/runs`.

To manually use the approval dashboard, create a draft plan:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/plans -ContentType "application/json" -Body '{"text":"deploy api to dev with image hashicorp/http-echo:1.0"}'
```

Then open:

```text
http://localhost:8000/approvals/dashboard
```

Approve or reject the draft plan in the browser. The dashboard uses the existing approval endpoints and does not execute Kubernetes actions.

Stop the stack when you are done:

```powershell
docker compose down
```

## Live Kubernetes Path

Use this path only when Docker Desktop Kubernetes, kind, or minikube is pointed at a local development cluster. DevAssist does not shell out to `kubectl`; manual `kubectl` commands are only for preparing and inspecting the local cluster.

Prepare the demo app:

```powershell
kubectl apply -f deploy/local/demo-app.yaml
kubectl get deployment api -n dev
```

Start the local runtime helper:

```powershell
.\scripts\start-local-dev.ps1
```

In a second terminal, run the full demo:

```powershell
python scripts/local_demo.py
```

The full demo creates a plan, approves it, and calls `/runs` to execute the approved plan through the configured runtime. After the run, inspect the stored run data:

```powershell
curl "http://localhost:8000/runs?limit=10"
curl http://localhost:8000/runs/<run-id>
curl http://localhost:8000/runs/<run-id>/events
```

You can also inspect the Kubernetes deployment state through DevAssist:

```powershell
curl http://localhost:8000/deployments/dev/api/state
```

Stop the API with `Ctrl+C`, then stop the local Redis container:

```powershell
.\scripts\stop-local-dev.ps1
```

## Interview Talking Points

Use this short explanation when introducing the project:

DevAssist is a local Kubernetes-native CI/CD orchestrator that demonstrates how to put guardrails around AI-assisted infrastructure workflows. The AI-shaped parser can interpret deployment language, but it only produces structured intent. The API turns that intent into a strict execution plan, validates it through deterministic policy, requires human approval for mutating actions, and only then lets an injected Kubernetes API client patch or inspect deployments.

The project also shows practical DevOps habits: health and readiness endpoints, Redis-backed run state and event streams, Dockerized local services, a non-root API container, GitHub Actions tests, a live API smoke check, local Kubernetes runbooks, and a browser approval dashboard. The local MVP is intentionally scoped: real model calls and hosted deployment are deferred so the core safety model remains clear and testable.
