from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = ROOT / "compose.yaml"


def _compose():
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def test_compose_defines_local_api_and_redis_services():
    compose = _compose()
    services = compose["services"]

    assert set(services) == {"api", "redis"}
    assert services["api"]["build"] == {"context": "."}
    assert services["api"]["image"] == "devassist-api:local"
    assert services["api"]["ports"] == ["8000:8000"]
    assert services["api"]["depends_on"] == ["redis"]
    assert services["redis"]["image"] == "redis:7"
    assert "ports" not in services["redis"]


def test_compose_uses_safe_local_runtime_defaults():
    compose = _compose()
    api = compose["services"]["api"]

    assert api["environment"] == {
        "DEVASSIST_EXECUTION_ENABLED": "false",
        "REDIS_URL": "redis://redis:6379/0",
        "KUBERNETES_CONFIG_MODE": "auto",
        "DEVASSIST_ALLOWED_NAMESPACES": "dev",
    }
    assert "volumes" not in api
    assert "env_file" not in api


def test_compose_adds_redis_healthcheck_without_shelling_to_kubectl():
    compose = _compose()
    redis = compose["services"]["redis"]

    assert redis["healthcheck"]["test"] == ["CMD", "redis-cli", "ping"]
    assert "kubectl" not in COMPOSE_PATH.read_text(encoding="utf-8").lower()
