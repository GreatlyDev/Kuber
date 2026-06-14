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
