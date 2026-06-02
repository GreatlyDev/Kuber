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

## Safety Notes

- Use only a local/dev cluster for this MVP.
- Mutating actions still require an approved `ExecutionPlan`.
- DevAssist does not shell out to `kubectl`; manual `kubectl` commands are for setup and inspection only.
- Keep `DEVASSIST_EXECUTION_ENABLED=false` unless Redis is running and your kubeconfig points at the intended dev cluster.
