# Local Kubernetes Runbook

This runbook is for manually trying DevAssist against a local development cluster. DevAssist still uses the Kubernetes Python API client internally; the `kubectl` commands here are only for you to prepare and inspect your local cluster.

## Prerequisites

- Docker Desktop installed
- Kubernetes enabled in Docker Desktop, or a local cluster from kind/minikube
- `kubectl` installed and pointed at the local dev cluster
- Redis running locally

## Prepare The Demo App

Apply the local demo app:

```powershell
kubectl apply -f deploy/local/demo-app.yaml
```

Check the deployment:

```powershell
kubectl get deployment api -n dev
kubectl get service api -n dev
```

The demo app is named `api` in namespace `dev` so it matches DevAssist's deterministic parser examples, such as:

```text
deploy api to dev with image hashicorp/http-echo:1.0
scale api in dev to 1 replica
status api in dev
```

Mutating parser inputs must include the required fields. For example, `scale api in dev` is rejected because DevAssist will not invent a replica count.

## Run Redis

The easiest Windows local path is to let the helper script at `scripts/start-local-dev.ps1` start Redis and the API together:

```powershell
.\scripts\start-local-dev.ps1
```

Stop the API with `Ctrl+C`. Stop the local Redis container with `scripts/stop-local-dev.ps1` when you are done:

```powershell
.\scripts\stop-local-dev.ps1
```

If you want to run Redis manually instead:

```powershell
docker run --name devassist-redis -p 6379:6379 redis:7
```

## Run The API Container

The API image is useful for practicing container builds and health checks. It starts with live execution disabled unless you pass runtime environment variables, runs as a non-root user, and includes a Docker healthcheck for `/healthz`, so it does not need Redis or Kubernetes just to boot:

```powershell
docker build -t devassist-api:local .
docker run --rm -p 8000:8000 devassist-api:local
curl http://localhost:8000/healthz
```

To run the API and Redis together without enabling live Kubernetes execution:

```powershell
docker compose up --build
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
python scripts/local_demo.py --plan-only
docker compose down
```

Compose keeps Redis private to the project network, so it will not conflict with a manually started `devassist-redis` container on `localhost:6379`. The `--plan-only` demo checks readiness, creates a plan, previews policy before approval, checks the pending approval queue, approves the plan, and previews policy again without creating a run or mutating Kubernetes.

To see the browser approval queue, create a draft plan and open `http://localhost:8000/approvals/dashboard` before approving it:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/plans -ContentType "application/json" -Body '{"text":"deploy api to dev with image hashicorp/http-echo:1.0"}'
```

For the full Redis plus Kubernetes execution workflow, use the PowerShell helper below while the MVP is still local-first.

## Enable DevAssist Runtime

Copy `.env.example` to `.env` and set:

```text
DEVASSIST_EXECUTION_ENABLED=true
REDIS_URL=redis://localhost:6379/0
DEVASSIST_PLAN_STORE=redis
KUBERNETES_CONFIG_MODE=auto
KUBERNETES_CONTEXT=docker-desktop
DEVASSIST_ALLOWED_NAMESPACES=dev
```

If your current kubeconfig context already points at the right dev cluster, leave `KUBERNETES_CONTEXT` blank.

Start the API with those environment values loaded in your PowerShell session:

```powershell
$env:DEVASSIST_EXECUTION_ENABLED="true"
$env:REDIS_URL="redis://localhost:6379/0"
$env:DEVASSIST_PLAN_STORE="redis"
$env:KUBERNETES_CONFIG_MODE="auto"
$env:KUBERNETES_CONTEXT="docker-desktop"
$env:DEVASSIST_ALLOWED_NAMESPACES="dev"
$env:PYTHONPATH="$PWD\apps\api;$PWD\packages\core"
python -m uvicorn devassist_api.main:app --reload --port 8000
```

The `PYTHONPATH` line keeps Python pinned to this checkout. That is useful if you have worked from another local clone before.

Check runtime readiness after startup:

```powershell
curl http://localhost:8000/readyz
```

Readiness always reports plan storage health. With `DEVASSIST_PLAN_STORE=redis`, `plan_store` should be `ok`; if Redis is unavailable, `/readyz` returns `503`. When execution is enabled, readiness also pings Redis for run storage and checks the Kubernetes Apps API using the Python client.

In a second PowerShell window, run the local demo flow:

```powershell
python scripts/local_demo.py
```

The script checks `/readyz` first, then calls DevAssist's API to create a plan, approve it, and run it. It does not call `kubectl`. Use `python scripts/local_demo.py --plan-only` when you want to practice the approval flow without creating an execution run.

Before running a plan, you can preview the deterministic policy decision:

```powershell
curl http://localhost:8000/plans/<plan-id>/policy
```

When the runtime is enabled, this preview uses the same namespace allowlist that execution uses.

You can filter the plan list while the API process is running. With `DEVASSIST_PLAN_STORE=redis`, created and approved plans survive API restarts as long as the local Redis container is still running:

```powershell
curl "http://localhost:8000/plans?status=approved&limit=10"
```

To review draft plans that still need a human approval decision, use the pending approval queue. Each item includes the plan plus the same deterministic policy preview used before execution:

```powershell
curl "http://localhost:8000/approvals/pending?limit=10"
```

You can also open `http://localhost:8000/approvals/dashboard` to approve or reject draft plans in the local browser UI. The dashboard calls only the existing approval endpoints and does not create execution runs.

Use the printed run id to inspect the stored run and event timeline:

```powershell
curl "http://localhost:8000/runs?limit=10"
curl http://localhost:8000/runs/<run-id>
curl http://localhost:8000/runs/<run-id>/events
```

Run responses include `plan_summary`, `plan_action`, `plan_app`, and `plan_namespace` so the Redis-backed run history remains understandable even if local plan storage is reset.

If execution fails, the API response includes a failed `run_id` and `events_path`. Use those values with the same run inspection endpoints to see the stored `run.failed` event. Executor policy denial is also recorded as a failed run.

```powershell
curl "http://localhost:8000/runs/<run-id>/events?event_type=run.failed&limit=1"
```

If a run id is unknown, both the run detail and event timeline endpoints return `404`.

Filter recent runs by status when you want a quick history view:

```powershell
curl "http://localhost:8000/runs?status=succeeded&limit=10"
curl "http://localhost:8000/runs?action=deploy&app=api&namespace=dev"
curl "http://localhost:8000/runs?plan_id=<plan-id>"
```

The `app` and `namespace` filters follow the same Kubernetes name format as parsed intents.

Inspect the deployment state through DevAssist's Kubernetes API-client path:

```powershell
curl http://localhost:8000/deployments/dev/api/state
```

If the Deployment does not exist, DevAssist returns `404` from this endpoint instead of treating the Kubernetes client response as an unhandled server error.

After the run finishes, inspect Kubernetes manually:

```powershell
kubectl get deployment api -n dev
kubectl describe deployment api -n dev
```

## Safety Notes

- Use only a local/dev cluster for this MVP.
- Only draft `ExecutionPlan` records can be approved or rejected.
- Inspect `created_at` and `updated_at` on plan responses when you want to see when a plan was created or decided.
- The MVP executor supports `deploy`, `scale`, and `status`. Unsupported schema actions such as `restart` and `rollback` are denied by policy.
- Mutating actions still require an approved `ExecutionPlan`.
- Rejected `ExecutionPlan` records cannot be run, even for read-only status checks.
- DevAssist does not shell out to `kubectl`; manual `kubectl` commands are for setup and inspection only.
- Keep `DEVASSIST_EXECUTION_ENABLED=false` unless Redis is running and your kubeconfig points at the intended dev cluster.
- Keep `DEVASSIST_ALLOWED_NAMESPACES=dev` for the demo. Add namespaces only when you have created them intentionally in your local cluster.
