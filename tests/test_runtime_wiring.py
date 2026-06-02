from devassist_api import main
from devassist_api.runtime import RuntimeSettings, build_execution_runtime, load_settings
from devassist_core.execution_runtime import ExecutionRuntime
from devassist_core.kubernetes_client import KubernetesConfigMode


class FakeRedisModule:
    urls = []

    @classmethod
    def from_url(cls, url, decode_responses=True):
        cls.urls.append({"url": url, "decode_responses": decode_responses})
        return {"redis_url": url}


class FakeAppsV1Api:
    pass


def fake_apps_v1_api_builder(mode, context):
    fake_apps_v1_api_builder.calls.append({"mode": mode, "context": context})
    return FakeAppsV1Api()


fake_apps_v1_api_builder.calls = []


def setup_function():
    FakeRedisModule.urls = []
    fake_apps_v1_api_builder.calls = []
    main.execution_runtime = None


def teardown_function():
    main.execution_runtime = None


def test_load_settings_defaults_to_execution_disabled():
    settings = load_settings({})

    assert settings == RuntimeSettings(
        execution_enabled=False,
        redis_url="redis://localhost:6379/0",
        kubernetes_config_mode=KubernetesConfigMode.AUTO,
        kubernetes_context=None,
    )


def test_load_settings_reads_explicit_runtime_config():
    settings = load_settings(
        {
            "DEVASSIST_EXECUTION_ENABLED": "true",
            "REDIS_URL": "redis://redis:6379/1",
            "KUBERNETES_CONFIG_MODE": "kubeconfig",
            "KUBERNETES_CONTEXT": "docker-desktop",
        }
    )

    assert settings.execution_enabled is True
    assert settings.redis_url == "redis://redis:6379/1"
    assert settings.kubernetes_config_mode is KubernetesConfigMode.KUBECONFIG
    assert settings.kubernetes_context == "docker-desktop"


def test_disabled_runtime_does_not_create_clients():
    runtime = build_execution_runtime(
        RuntimeSettings(execution_enabled=False),
        redis_module=FakeRedisModule,
        apps_v1_api_builder=fake_apps_v1_api_builder,
    )

    assert runtime is None
    assert FakeRedisModule.urls == []
    assert fake_apps_v1_api_builder.calls == []


def test_enabled_runtime_wires_redis_and_kubernetes_executor():
    settings = RuntimeSettings(
        execution_enabled=True,
        redis_url="redis://localhost:6379/2",
        kubernetes_config_mode=KubernetesConfigMode.KUBECONFIG,
        kubernetes_context="docker-desktop",
    )

    runtime = build_execution_runtime(
        settings,
        redis_module=FakeRedisModule,
        apps_v1_api_builder=fake_apps_v1_api_builder,
    )

    assert isinstance(runtime, ExecutionRuntime)
    assert FakeRedisModule.urls == [
        {"url": "redis://localhost:6379/2", "decode_responses": True}
    ]
    assert fake_apps_v1_api_builder.calls == [
        {
            "mode": KubernetesConfigMode.KUBECONFIG,
            "context": "docker-desktop",
        }
    ]


def test_configure_execution_runtime_leaves_runtime_disabled_by_default():
    main.configure_execution_runtime(settings=RuntimeSettings(execution_enabled=False))

    assert main.execution_runtime is None


def test_configure_execution_runtime_sets_runtime_when_enabled():
    main.configure_execution_runtime(
        settings=RuntimeSettings(execution_enabled=True),
        runtime_builder=lambda settings: "runtime",
    )

    assert main.execution_runtime == "runtime"
