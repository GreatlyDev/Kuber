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
```

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

## Enable DevAssist Runtime

Copy `.env.example` to `.env` and set:

```text
DEVASSIST_EXECUTION_ENABLED=true
REDIS_URL=redis://localhost:6379/0
KUBERNETES_CONFIG_MODE=auto
KUBERNETES_CONTEXT=docker-desktop
DEVASSIST_ALLOWED_NAMESPACES=dev
```

If your current kubeconfig context already points at the right dev cluster, leave `KUBERNETES_CONTEXT` blank.

Start the API with those environment values loaded in your PowerShell session:

```powershell
$env:DEVASSIST_EXECUTION_ENABLED="true"
$env:REDIS_URL="redis://localhost:6379/0"
$env:KUBERNETES_CONFIG_MODE="auto"
$env:KUBERNETES_CONTEXT="docker-desktop"
$env:DEVASSIST_ALLOWED_NAMESPACES="dev"
$env:PYTHONPATH="$PWD\apps\api;$PWD\packages\core"
python -m uvicorn devassist_api.main:app --reload --port 8000
```

The `PYTHONPATH` line keeps Python pinned to this checkout. That is useful if you have worked from another local clone before.

In a second PowerShell window, run the local demo flow:

```powershell
python scripts/local_demo.py
```

The script calls DevAssist's API to create a plan, approve it, and run it. It does not call `kubectl`.

Before running a plan, you can preview the deterministic policy decision:

```powershell
curl http://localhost:8000/plans/<plan-id>/policy
```

When the runtime is enabled, this preview uses the same namespace allowlist that execution uses.

Use the printed run id to inspect the stored run and event timeline:

```powershell
curl "http://localhost:8000/runs?limit=10"
curl http://localhost:8000/runs/<run-id>
curl http://localhost:8000/runs/<run-id>/events
```

Filter recent runs by status when you want a quick history view:

```powershell
curl "http://localhost:8000/runs?status=succeeded&limit=10"
```

Inspect the deployment state through DevAssist's Kubernetes API-client path:

```powershell
curl http://localhost:8000/deployments/dev/api/state
```

After the run finishes, inspect Kubernetes manually:

```powershell
kubectl get deployment api -n dev
kubectl describe deployment api -n dev
```

## Safety Notes

- Use only a local/dev cluster for this MVP.
- Mutating actions still require an approved `ExecutionPlan`.
- DevAssist does not shell out to `kubectl`; manual `kubectl` commands are for setup and inspection only.
- Keep `DEVASSIST_EXECUTION_ENABLED=false` unless Redis is running and your kubeconfig points at the intended dev cluster.
- Keep `DEVASSIST_ALLOWED_NAMESPACES=dev` for the demo. Add namespaces only when you have created them intentionally in your local cluster.
