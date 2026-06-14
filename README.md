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
      runtime.py
deploy/
  local/
    demo-app.yaml
docs/
  local-kubernetes-runbook.md
packages/
  core/
    devassist_core/
      execution_runtime.py
      kubernetes_client.py
      kubernetes_executor.py
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
scripts/
  local_demo.py
  start-local-dev.ps1
  stop-local-dev.ps1
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

You can also build and run the API container locally. The image keeps live execution disabled by default, runs the API as a non-root user, and includes a Docker healthcheck for `/healthz`. This is a safe way to practice containerizing the FastAPI service and checking health endpoints:

```powershell
docker build -t devassist-api:local .
docker run --rm -p 8000:8000 devassist-api:local
curl http://localhost:8000/healthz
```

For the local Redis plus Kubernetes execution workflow on Windows, use the helper script from the repo root:

```powershell
.\scripts\start-local-dev.ps1
```

That script starts a named Redis container, sets `PYTHONPATH` to this checkout's `apps/api` and `packages/core` folders, enables local execution, and starts FastAPI on `http://127.0.0.1:8000`. It does not call `kubectl`; DevAssist still uses the Kubernetes Python API client.

When you are done, stop the API with `Ctrl+C`. To stop the Redis container:

```powershell
.\scripts\stop-local-dev.ps1
```

Health endpoints:

- `GET /healthz`
- `GET /readyz`

`/readyz` reports `not_configured` dependencies when live execution is disabled. When the runtime is enabled, it pings Redis and performs a read-only Kubernetes Apps API resource check; unavailable dependencies return `503`.

Plan endpoints:

- `GET /deployments/{namespace}/{app_name}/state`
- `POST /plans`
- `GET /plans`
- `GET /plans/{plan_id}`
- `POST /plans/{plan_id}/approve`
- `POST /plans/{plan_id}/reject`
- `POST /plans/{plan_id}/runs`
- `GET /plans/{plan_id}/policy`
- `GET /runs`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/events`

Plan approval is intentionally separate from execution. These endpoints can create, inspect, approve, reject, and validate an `ExecutionPlan`, but they do not run Kubernetes actions. Plan decisions are one-way: only draft plans can be approved or rejected. Plans track `created_at` and `updated_at` timestamps so approval and rejection decisions are inspectable. Rejected plans are denied by policy for every action, including read-only status checks. `GET /plans` accepts `status` and `limit` query parameters for quick local inspection:

```powershell
curl "http://localhost:8000/plans?status=approved&limit=10"
```

The MVP parser is deterministic and schema-backed. It can parse local-friendly deploy, scale, and status phrases, and it returns `400` when text cannot produce a valid `PipelineIntent` instead of inventing missing mutating inputs:

```text
deploy api to dev with image example/api:1.0.0
scale api in dev to 3 replicas
status api in dev
```

Run queueing is also guarded. `queue_execution_run` validates the plan policy first, then records a queued `ExecutionRun` and `run.queued` event through Redis-backed storage. It still does not execute Kubernetes actions.

Kubernetes execution is handled through an injected Kubernetes API client interface. Draft mutating plans are blocked before any client method is called. The MVP Kubernetes executor supports `deploy`, `scale`, and `status` actions. Approved deploy and scale plans patch Kubernetes deployments through API-client-style methods; status plans read deployment state without approval and return `404` when the Kubernetes API reports that the Deployment does not exist. Schema-level actions that the MVP executor does not implement yet, such as `restart` and `rollback`, are denied by policy before any Kubernetes client method is called.

`build_apps_v1_api` creates an official Kubernetes `AppsV1Api` client. It supports local kubeconfig, in-cluster config, and an auto mode that tries in-cluster config first before falling back to kubeconfig.

The run execution API requires an explicitly configured execution runtime. By default it returns `503` instead of creating a live Kubernetes client on its own. When configured, the runtime queues a run, records `run.started`, executes through the Kubernetes executor, and records `run.succeeded` or `run.failed`. Executor policy denial is recorded as `run.failed` rather than success. Failed execution responses include the failed `run_id` and an `events_path` so the recorded event timeline remains inspectable.

Run history is Redis-backed. `GET /runs` lists recent runs from a deterministic Redis sorted-set index, newest first. Runs include the originating plan summary, action, app, and namespace so history remains readable while the MVP plan repository is still in-memory. Use `status`, `action`, `app`, `namespace`, and `plan_id` to filter results, and `limit` to bound them. The `app` and `namespace` filters use the same Kubernetes name format as parsed intents:

```powershell
curl "http://localhost:8000/runs?status=succeeded&limit=20"
curl "http://localhost:8000/runs?action=deploy&app=api&namespace=dev"
curl "http://localhost:8000/runs?plan_id=<plan-id>"
```

Run event inspection is tied to a stored run. `GET /runs/{run_id}/events` returns `404` when the run id is unknown instead of returning an empty timeline. Use `event_type` and `limit` to narrow the timeline while debugging:

```powershell
curl "http://localhost:8000/runs/<run-id>/events?event_type=run.failed&limit=1"
```

Runtime wiring is controlled by environment variables:

- `DEVASSIST_EXECUTION_ENABLED=false` keeps live execution disabled by default.
- `REDIS_URL=redis://localhost:6379/0` points the runtime at Redis.
- `KUBERNETES_CONFIG_MODE=auto` supports `auto`, `kubeconfig`, or `in_cluster`.
- `KUBERNETES_CONTEXT=` can select a local kubeconfig context such as `docker-desktop`.
- `DEVASSIST_ALLOWED_NAMESPACES=dev` narrows the namespaces DevAssist may touch. If unset, the local-friendly default allowlist is `default,dev,local,staging`.

Namespace allowlisting is enforced by the deterministic policy validator before run queueing and by the Kubernetes executor before API-client calls. Keep the local helper narrowed to `dev` unless you intentionally add another local namespace for practice.

`GET /plans/{plan_id}/policy` uses the configured runtime policy when execution is enabled, so policy preview and run execution enforce the same namespace allowlist.

## Local Dependencies

Redis is used for run state and run event streams. `RedisRunStore` stores each `ExecutionRun` in a Redis hash and each `RunEvent` in a Redis stream using deterministic keys:

- `devassist:runs:{run_id}`
- `devassist:runs:{run_id}:events`

For local development, run Redis with Docker when needed:

```powershell
docker run --name devassist-redis -p 6379:6379 redis:7
```

The Windows helper at `scripts/start-local-dev.ps1` will start that container for you and reuse it on later runs. The companion `scripts/stop-local-dev.ps1` stops only the named local Redis container.

The current executor is written around the official Kubernetes Python client's `AppsV1Api` method shapes. Tests use fakes, so no cluster is required in CI. For local manual testing later, Docker Desktop Kubernetes, kind, or minikube can provide the kubeconfig that `build_apps_v1_api` loads. Set `DEVASSIST_EXECUTION_ENABLED=true` only when Redis is running and your Kubernetes context is pointed at a dev cluster.

For local Kubernetes practice, see `docs/local-kubernetes-runbook.md`. The demo manifest at `deploy/local/demo-app.yaml` creates an `api` Deployment and Service in the `dev` namespace.
The helper script at `scripts/local_demo.py` calls DevAssist's API to create, approve, and run the demo plan.

## CI

GitHub Actions runs `python -m pytest` and builds the local API container image on pull requests and pushes to `main`. The CI container job only verifies `docker build`; it does not push images to a registry.

## Current Scope

Implemented so far:

- Monorepo structure
- FastAPI health and readiness endpoints
- Strict Pydantic schemas for intent, plans, runs, events, and deployment state
- Policy validator with tests
- Execution plan builder with tests
- In-memory plan repository and approval API with tests
- Read-only deployment status API with tests
- Runtime readiness checks for Redis and Kubernetes with tests
- Guarded run execution API with tests
- Run and run event inspection API with tests
- Recent run history API with tests
- Opt-in local runtime wiring through Redis and Kubernetes client settings
- Deterministic LangChain-shaped parser stub with tests
- Execution runtime with Redis run lifecycle events and tests
- Guarded run queueing service with tests
- Redis-backed run state and run event store with tests
- Local/in-cluster Kubernetes client setup with tests
- Guarded Kubernetes API executor for deploy, scale, and status plans with tests
- Local Kubernetes demo manifest and runbook
- Local demo API script with tests
- Local API Dockerfile and `.dockerignore`
- Windows local developer start/stop scripts
- README setup instructions

Not implemented yet:

- Real LangChain model calls
- Approval UI/API
- Production deployment manifest
