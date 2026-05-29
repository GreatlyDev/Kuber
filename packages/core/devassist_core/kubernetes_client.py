from enum import StrEnum
from typing import Any

from kubernetes import client, config


class KubernetesConfigMode(StrEnum):
    AUTO = "auto"
    IN_CLUSTER = "in_cluster"
    KUBECONFIG = "kubeconfig"


def build_apps_v1_api(
    mode: KubernetesConfigMode | str = KubernetesConfigMode.AUTO,
    context: str | None = None,
    config_module: Any = config,
    client_module: Any = client,
):
    mode = _parse_mode(mode)

    if mode is KubernetesConfigMode.IN_CLUSTER:
        config_module.load_incluster_config()
    elif mode is KubernetesConfigMode.KUBECONFIG:
        config_module.load_kube_config(context=context)
    elif mode is KubernetesConfigMode.AUTO:
        try:
            config_module.load_incluster_config()
        except Exception:
            config_module.load_kube_config(context=context)
    else:
        raise ValueError(f"unsupported Kubernetes config mode: {mode}")

    return client_module.AppsV1Api()


def _parse_mode(mode: KubernetesConfigMode | str) -> KubernetesConfigMode:
    try:
        return KubernetesConfigMode(mode)
    except ValueError as exc:
        raise ValueError(f"unsupported Kubernetes config mode: {mode}") from exc
