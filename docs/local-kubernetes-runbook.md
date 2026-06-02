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

```powershell
docker run --rm -p 6379:6379 redis:7
```

## Enable DevAssist Runtime

Copy `.env.example` to `.env` and set:

```text
DEVASSIST_EXECUTION_ENABLED=true
REDIS_URL=redis://localhost:6379/0
KUBERNETES_CONFIG_MODE=auto
KUBERNETES_CONTEXT=docker-desktop
```

If your current kubeconfig context already points at the right dev cluster, leave `KUBERNETES_CONTEXT` blank.

Start the API with those environment values loaded in your PowerShell session:

```powershell
$env:DEVASSIST_EXECUTION_ENABLED="true"
$env:REDIS_URL="redis://localhost:6379/0"
$env:KUBERNETES_CONFIG_MODE="auto"
$env:KUBERNETES_CONTEXT="docker-desktop"
python -m uvicorn devassist_api.main:app --reload --port 8000
```

In a second PowerShell window, run the local demo flow:

```powershell
python scripts/local_demo.py
```

The script calls DevAssist's API to create a plan, approve it, and run it. It does not call `kubectl`.

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
