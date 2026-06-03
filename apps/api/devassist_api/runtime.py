import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from redis import Redis

from devassist_core.execution_runtime import ExecutionRuntime
from devassist_core.kubernetes_client import KubernetesConfigMode, build_apps_v1_api
from devassist_core.kubernetes_executor import KubernetesPlanExecutor
from devassist_core.policy import DEFAULT_NAMESPACE_ALLOWLIST
from devassist_core.run_store import RedisRunStore


@dataclass(frozen=True)
class RuntimeSettings:
    execution_enabled: bool = False
    redis_url: str = "redis://localhost:6379/0"
    kubernetes_config_mode: KubernetesConfigMode = KubernetesConfigMode.AUTO
    kubernetes_context: str | None = None
    allowed_namespaces: tuple[str, ...] = tuple(sorted(DEFAULT_NAMESPACE_ALLOWLIST))


def load_settings(environ: Mapping[str, str] | None = None) -> RuntimeSettings:
    environ = environ or os.environ
    return RuntimeSettings(
        execution_enabled=_parse_bool(
            environ.get("DEVASSIST_EXECUTION_ENABLED", "false")
        ),
        redis_url=environ.get("REDIS_URL", "redis://localhost:6379/0"),
        kubernetes_config_mode=KubernetesConfigMode(
            environ.get("KUBERNETES_CONFIG_MODE", KubernetesConfigMode.AUTO)
        ),
        kubernetes_context=environ.get("KUBERNETES_CONTEXT") or None,
        allowed_namespaces=_parse_csv(
            environ.get("DEVASSIST_ALLOWED_NAMESPACES"),
            default=tuple(sorted(DEFAULT_NAMESPACE_ALLOWLIST)),
        ),
    )


def build_execution_runtime(
    settings: RuntimeSettings,
    redis_module=Redis,
    apps_v1_api_builder: Callable[..., object] = build_apps_v1_api,
) -> ExecutionRuntime | None:
    if not settings.execution_enabled:
        return None

    redis_client = redis_module.from_url(settings.redis_url, decode_responses=True)
    apps_v1_api = apps_v1_api_builder(
        mode=settings.kubernetes_config_mode,
        context=settings.kubernetes_context,
    )
    return ExecutionRuntime(
        store=RedisRunStore(redis_client),
        executor=KubernetesPlanExecutor(
            apps_v1_api,
            allowed_namespaces=settings.allowed_namespaces,
        ),
        allowed_namespaces=settings.allowed_namespaces,
    )


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv(value: str | None, *, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None:
        return default
    parsed = tuple(item.strip() for item in value.split(",") if item.strip())
    return parsed or default
