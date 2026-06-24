from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "tests.yml"


def _workflow():
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def test_ci_runs_python_tests():
    workflow = _workflow()
    python_job = workflow["jobs"]["python"]

    assert python_job["runs-on"] == "ubuntu-latest"
    assert any(
        step.get("run") == 'python -m pip install -e ".[dev]"'
        for step in python_job["steps"]
    )
    assert any(step.get("run") == "python -m pytest" for step in python_job["steps"])


def test_ci_runs_live_api_smoke_check():
    workflow = _workflow()
    python_job = workflow["jobs"]["python"]

    smoke_step = next(
        step
        for step in python_job["steps"]
        if step.get("name") == "Run API smoke check"
    )

    assert "python -m uvicorn devassist_api.main:app" in smoke_step["run"]
    assert "trap 'kill \"$API_PID\"' EXIT" in smoke_step["run"]
    assert "python scripts/smoke_check.py --base-url http://127.0.0.1:8000" in smoke_step[
        "run"
    ]
    assert "/runs" not in smoke_step["run"]
    assert "kubectl" not in smoke_step["run"].lower()


def test_ci_builds_api_container_without_pushing_registry_image():
    workflow = _workflow()
    container_job = workflow["jobs"]["container"]

    assert container_job["name"] == "Docker build"
    assert container_job["runs-on"] == "ubuntu-latest"
    assert any(
        step.get("uses") == "actions/checkout@v4"
        for step in container_job["steps"]
    )
    assert any(
        step.get("run") == "docker build -t devassist-api:ci ."
        for step in container_job["steps"]
    )
    assert "docker push" not in WORKFLOW_PATH.read_text(encoding="utf-8")
