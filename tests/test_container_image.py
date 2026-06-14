from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_api_dockerfile_runs_fastapi_with_execution_disabled_by_default():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.12-slim" in dockerfile
    assert "DEVASSIST_EXECUTION_ENABLED=false" in dockerfile
    assert "COPY apps ./apps" in dockerfile
    assert "COPY packages ./packages" in dockerfile
    assert 'CMD ["uvicorn", "devassist_api.main:app"' in dockerfile
    assert '"--host", "0.0.0.0"' in dockerfile
    assert '"--port", "8000"' in dockerfile
    assert "kubectl" not in dockerfile.lower()


def test_dockerignore_keeps_local_state_out_of_build_context():
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    for pattern in [
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".env",
        "*.log",
    ]:
        assert pattern in dockerignore
