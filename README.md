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
      policy.py
      schemas.py
tests/
  test_health.py
  test_langchain_parser.py
  test_plan_builder.py
  test_policy_validator.py
  test_schemas.py
```

## Local Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the API and development dependencies:

```powershell
python -m pip install -e .[dev]
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

## Local Dependencies

Redis is part of the MVP architecture for run state and event streams. The current phase only defines Redis keys in the strict schemas; the Redis client implementation comes later.

For local development, run Redis with Docker when needed:

```powershell
docker run --rm -p 6379:6379 redis:7
```

Kubernetes mutation is not implemented yet. When added, DevAssist will use the official Kubernetes Python client against a local/dev cluster such as kind, minikube, or Docker Desktop Kubernetes.

## Current Phase

Implemented in Phase 0/1:

- Monorepo structure
- FastAPI health and readiness endpoints
- Strict Pydantic schemas for intent, plans, runs, events, and deployment state
- Policy validator with tests
- Execution plan builder with tests
- Deterministic LangChain-shaped parser stub with tests
- README setup instructions

Not implemented yet:

- Real LangChain model calls
- Redis persistence layer
- Kubernetes API execution
- Approval UI/API
- Production deployment manifests
