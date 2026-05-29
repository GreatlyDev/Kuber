import pytest

from devassist_core.kubernetes_client import (
    KubernetesConfigMode,
    build_apps_v1_api,
)


class FakeConfig:
    def __init__(self, in_cluster_error=None):
        self.calls = []
        self.in_cluster_error = in_cluster_error

    def load_incluster_config(self):
        self.calls.append("in_cluster")
        if self.in_cluster_error:
            raise self.in_cluster_error

    def load_kube_config(self, context=None):
        self.calls.append(("kubeconfig", context))


class FakeClientModule:
    class AppsV1Api:
        def __init__(self):
            self.created = True


def test_builds_apps_v1_api_from_local_kubeconfig():
    config = FakeConfig()

    api = build_apps_v1_api(
        mode=KubernetesConfigMode.KUBECONFIG,
        context="docker-desktop",
        config_module=config,
        client_module=FakeClientModule,
    )

    assert api.created is True
    assert config.calls == [("kubeconfig", "docker-desktop")]


def test_builds_apps_v1_api_from_in_cluster_config():
    config = FakeConfig()

    api = build_apps_v1_api(
        mode=KubernetesConfigMode.IN_CLUSTER,
        config_module=config,
        client_module=FakeClientModule,
    )

    assert api.created is True
    assert config.calls == ["in_cluster"]


def test_auto_mode_falls_back_to_kubeconfig_when_not_in_cluster():
    config = FakeConfig(in_cluster_error=RuntimeError("not in cluster"))

    api = build_apps_v1_api(
        mode=KubernetesConfigMode.AUTO,
        config_module=config,
        client_module=FakeClientModule,
    )

    assert api.created is True
    assert config.calls == ["in_cluster", ("kubeconfig", None)]


def test_invalid_config_mode_is_rejected():
    with pytest.raises(ValueError, match="unsupported Kubernetes config mode"):
        build_apps_v1_api(
            mode="bad-mode",
            config_module=FakeConfig(),
            client_module=FakeClientModule,
        )
