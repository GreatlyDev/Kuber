# DevAssist

DevAssist is a Kubernetes-native AI-assisted CI/CD orchestrator. The MVP is built for local development clusters and focuses on safe intent parsing, explicit execution plans, deterministic validation, and event/state storage in Redis.

## MVP Safety Rules

- The LLM may parse natural language into structured intent, but it must never execute commands.
- Mutating Kubernetes actions require an explicitly approved `ExecutionPlan`.
- Schemas are strict and reject unknown fields.
- Run state and run events are modeled for Redis-backed storage.
- Kubernetes integration will use the Kubernetes API client, not `kubectl` shell execution.
- Production-only features, arbitrary shell execution, and model retraining are out of scope.

## Repository Layout

```text
apps/
  api/
    devassist_api/
      main.py
packages/
  core/
    devassist_core/
      langchain_parser.py
      plan_builder.py
      plan_repository.py
      policy.py
      run_service.py
      run_store.py
      schemas.py
tests/
  test_health.py
  test_langchain_parser.py
  test_plan_builder.py
  test_policy_validator.py
  test_schemas.py
```

## Local Setup

Recommended tools for working on this project:

- Python 3.12
- Git
- Docker Desktop, for local Redis and later local Kubernetes
- GitHub CLI, optional but helpful for PRs and CI checks
- `kubectl`, helpful for learning and inspecting clusters manually, though DevAssist itself will use the Kubernetes API client rather than shelling out to `kubectl`
- kind or minikube, optional later if you do not use Docker Desktop Kubernetes

You do not need all Kubernetes tooling on day one. For the current code, Python and Git are enough to run tests; Redis becomes useful when manually exercising run state locally, and Kubernetes becomes useful in the next implementation phase.

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the API and development dependencies:

```powershell
python -m pip install -e .[dev]
```

Copy the example environment file when local services are added:

```powershell
Copy-Item .env.example .env
```

Run the test suite:

```powershell
python -m pytest
```

Start the API:

```powershell
python -m uvicorn devassist_api.main:app --reload --port 8000
```

Health endpoints:

- `GET /healthz`
- `GET /readyz`

Plan endpoints:

- `POST /plans`
- `GET /plans`
- `GET /plans/{plan_id}`
- `POST /plans/{plan_id}/approve`
- `POST /plans/{plan_id}/reject`
- `GET /plans/{plan_id}/policy`

Plan approval is intentionally separate from execution. These endpoints can create, inspect, approve, reject, and validate an `ExecutionPlan`, but they do not run Kubernetes actions.

Run queueing is also guarded. `queue_execution_run` validates the plan policy first, then records a queued `ExecutionRun` and `run.queued` event through Redis-backed storage. It still does not execute Kubernetes actions.

## Local Dependencies

Redis is used for run state and run event streams. `RedisRunStore` stores each `ExecutionRun` in a Redis hash and each `RunEvent` in a Redis stream using deterministic keys:

- `devassist:runs:{run_id}`
- `devassist:runs:{run_id}:events`

For local development, run Redis with Docker when needed:

```powershell
docker run --rm -p 6379:6379 redis:7
```

Kubernetes mutation is not implemented yet. When added, DevAssist will use the official Kubernetes Python client against a local/dev cluster such as kind, minikube, or Docker Desktop Kubernetes.

## CI

GitHub Actions runs `python -m pytest` on pull requests and pushes to `main`.

## Current Scope

Implemented so far:

- Monorepo structure
- FastAPI health and readiness endpoints
- Strict Pydantic schemas for intent, plans, runs, events, and deployment state
- Policy validator with tests
- Execution plan builder with tests
- In-memory plan repository and approval API with tests
- Deterministic LangChain-shaped parser stub with tests
- Guarded run queueing service with tests
- Redis-backed run state and run event store with tests
- README setup instructions

Not implemented yet:

- Real LangChain model calls
- Kubernetes API execution
- Approval UI/API
- Production deployment manifests
