from fastapi import FastAPI

app = FastAPI(
    title="DevAssist API",
    version="0.1.0",
    description="Local MVP API for Kubernetes-native CI/CD orchestration.",
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, object]:
    return {
        "status": "ready",
        "dependencies": {
            "kubernetes": "not_configured",
            "redis": "not_configured",
        },
    }
