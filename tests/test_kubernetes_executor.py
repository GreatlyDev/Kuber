from datetime import UTC, datetime

import pytest
from kubernetes.client.exceptions import ApiException

from devassist_core.kubernetes_executor import (
    KubernetesExecutionResult,
    KubernetesPlanExecutor,
    UnsupportedKubernetesActionError,
)
from devassist_core.plan_builder import build_execution_plan
from devassist_core.policy import PolicyDecision
from devassist_core.schemas import (
    DeploymentAction,
    DeploymentState,
    PipelineIntent,
    PlanStatus,
)


class FakeAppsV1Api:
    def __init__(self):
        self.patches = []
        self.scales = []
        self.deployments = {}
        self.missing_deployments = set()
        self.resource_checks = 0

    def patch_namespaced_deployment(self, name, namespace, body):
        self.patches.append({"name": name, "namespace": namespace, "body": body})
        return {"patched": True}

    def patch_namespaced_deployment_scale(self, name, namespace, body):
        self.scales.append({"name": name, "namespace": namespace, "body": body})
        return {"scaled": True}

    def read_namespaced_deployment(self, name, namespace):
        if (namespace, name) in self.missing_deployments:
            raise ApiException(status=404, reason="Not Found")
        return self.deployments[(namespace, name)]

    def get_api_resources(self):
        self.resource_checks += 1
        return {"resources": []}


class FakeDeployment:
    def __init__(self, image="example/api:1.0.0", replicas=2, available_replicas=1):
        self.spec = type("Spec", (), {})()
        self.spec.replicas = replicas
        self.spec.template = type("Template", (), {})()
        self.spec.template.spec = type("PodSpec", (), {})()
        self.spec.template.spec.containers = [type("Container", (), {"image": image})()]
        self.status = type("Status", (), {"available_replicas": available_replicas})()


def _plan(action=DeploymentAction.DEPLOY, status=PlanStatus.APPROVED, namespace="dev"):
    intent = PipelineIntent(
        action=action,
        app="api",
        namespace=namespace,
        image="example/api:1.0.0" if action is DeploymentAction.DEPLOY else None,
        replicas=3 if action is DeploymentAction.SCALE else None,
    )
    plan = build_execution_plan(intent)
    if status is PlanStatus.APPROVED:
        return plan.model_copy(update={"status": status, "approved_by": "great"})
    return plan


def test_draft_mutating_plan_never_calls_kubernetes_api():
    apps_api = FakeAppsV1Api()
    executor = KubernetesPlanExecutor(apps_api)

    result = executor.execute(_plan(status=PlanStatus.DRAFT))

    assert result == KubernetesExecutionResult(
        applied=False,
        policy=PolicyDecision(
            allowed=False,
            reasons=["mutating Kubernetes actions require an approved ExecutionPlan"],
        ),
        deployment_state=None,
        messages=[],
    )
    assert apps_api.patches == []


def test_approved_deploy_patches_deployment_image_with_kubernetes_client():
    apps_api = FakeAppsV1Api()
    executor = KubernetesPlanExecutor(apps_api)

    result = executor.execute(_plan())

    assert result.applied is True
    assert result.messages == ["patched deployment api image"]
    assert apps_api.patches == [
        {
            "name": "api",
            "namespace": "dev",
            "body": {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {"name": "api", "image": "example/api:1.0.0"}
                            ]
                        }
                    }
                }
            },
        }
    ]


def test_executor_connection_check_reads_apps_api_resources():
    apps_api = FakeAppsV1Api()
    executor = KubernetesPlanExecutor(apps_api)

    assert executor.check_connection() is True
    assert apps_api.resource_checks == 1


def test_executor_blocks_namespace_outside_configured_allowlist():
    apps_api = FakeAppsV1Api()
    executor = KubernetesPlanExecutor(apps_api, allowed_namespaces=("dev",))

    result = executor.execute(_plan(namespace="staging"))

    assert result.applied is False
    assert result.policy == PolicyDecision(
        allowed=False,
        reasons=["namespace 'staging' is outside the configured namespace allowlist"],
    )
    assert apps_api.patches == []


def test_approved_scale_patches_deployment_scale_with_kubernetes_client():
    apps_api = FakeAppsV1Api()
    executor = KubernetesPlanExecutor(apps_api)

    result = executor.execute(_plan(action=DeploymentAction.SCALE))

    assert result.applied is True
    assert result.messages == ["scaled deployment api to 3 replicas"]
    assert apps_api.scales == [
        {
            "name": "api",
            "namespace": "dev",
            "body": {"spec": {"replicas": 3}},
        }
    ]


def test_status_reads_deployment_state_without_approval():
    apps_api = FakeAppsV1Api()
    apps_api.deployments[("dev", "api")] = FakeDeployment()
    executor = KubernetesPlanExecutor(
        apps_api,
        clock=lambda: datetime(2026, 5, 29, tzinfo=UTC),
    )

    result = executor.execute(_plan(action=DeploymentAction.STATUS, status=PlanStatus.DRAFT))

    assert result.applied is False
    assert result.deployment_state == DeploymentState(
        app="api",
        namespace="dev",
        desired_image=None,
        current_image="example/api:1.0.0",
        replicas=2,
        available_replicas=1,
        observed_at=datetime(2026, 5, 29, tzinfo=UTC),
    )


def test_status_returns_no_state_when_deployment_is_missing():
    apps_api = FakeAppsV1Api()
    apps_api.missing_deployments.add(("dev", "api"))
    executor = KubernetesPlanExecutor(apps_api)

    result = executor.execute(_plan(action=DeploymentAction.STATUS, status=PlanStatus.DRAFT))

    assert result.applied is False
    assert result.policy == PolicyDecision(allowed=True, reasons=[])
    assert result.deployment_state is None
    assert result.messages == ["deployment api was not found"]


def test_unsupported_action_fails_before_kubernetes_call():
    apps_api = FakeAppsV1Api()
    executor = KubernetesPlanExecutor(apps_api)

    with pytest.raises(UnsupportedKubernetesActionError):
        executor.execute(_plan(action=DeploymentAction.RESTART))

    assert apps_api.patches == []
