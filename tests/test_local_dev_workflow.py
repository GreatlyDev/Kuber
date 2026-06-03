from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_local_dev_scripts_are_documented() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "local-kubernetes-runbook.md").read_text(
        encoding="utf-8"
    )

    assert "scripts/start-local-dev.ps1" in readme
    assert "scripts/stop-local-dev.ps1" in readme
    assert "scripts/start-local-dev.ps1" in runbook
    assert "scripts/stop-local-dev.ps1" in runbook


def test_env_example_documents_safe_local_defaults() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "DEVASSIST_EXECUTION_ENABLED=false" in env_example
    assert "REDIS_URL=redis://localhost:6379/0" in env_example
    assert "KUBERNETES_CONFIG_MODE=auto" in env_example
    assert "KUBERNETES_CONTEXT=" in env_example
    assert "DEVASSIST_ALLOWED_NAMESPACES=dev" in env_example


def test_start_local_dev_script_wires_expected_local_runtime() -> None:
    script = (ROOT / "scripts" / "start-local-dev.ps1").read_text(
        encoding="utf-8"
    )

    assert "DEVASSIST_EXECUTION_ENABLED" in script
    assert "REDIS_URL" in script
    assert "KUBERNETES_CONFIG_MODE" in script
    assert "KUBERNETES_CONTEXT" in script
    assert "DEVASSIST_ALLOWED_NAMESPACES" in script
    assert "apps/api" in script.replace("\\", "/")
    assert "packages/core" in script.replace("\\", "/")
    assert "devassist-redis" in script
    assert "uvicorn" in script
    assert "kubectl" not in script.lower()


def test_stop_local_dev_script_targets_only_local_redis_container() -> None:
    script = (ROOT / "scripts" / "stop-local-dev.ps1").read_text(
        encoding="utf-8"
    )

    assert "devassist-redis" in script
    assert "docker" in script.lower()
    assert "kubectl" not in script.lower()
