from collections.abc import Callable, Collection
from datetime import UTC, datetime
from typing import Protocol

from kubernetes.client.exceptions import ApiException
from pydantic import BaseModel, ConfigDict

from devassist_core.policy import (
    DEFAULT_NAMESPACE_ALLOWLIST,
    PolicyDecision,
    validate_execution_plan,
)
from devassist_core.schemas import (
    DeploymentAction,
    DeploymentState,
    ExecutionPlan,
    PlanStep,
)


class AppsV1ApiClient(Protocol):
    def patch_namespaced_deployment(
        self, name: str, namespace: str, body: dict
    ) -> object: ...

    def patch_namespaced_deployment_scale(
        self, name: str, namespace: str, body: dict
    ) -> object: ...

    def read_namespaced_deployment(self, name: str, namespace: str) -> object: ...


class KubernetesExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    applied: bool
    policy: PolicyDecision
    deployment_state: DeploymentState | None = None
    messages: list[str]


class UnsupportedKubernetesActionError(Exception):
    pass


class KubernetesPlanExecutor:
    def __init__(
        self,
        apps_v1_api: AppsV1ApiClient,
        clock: Callable[[], datetime] | None = None,
        allowed_namespaces: Collection[str] | None = None,
    ):
        self.apps_v1_api = apps_v1_api
        self.clock = clock or (lambda: datetime.now(UTC))
        self.allowed_namespaces = tuple(allowed_namespaces or DEFAULT_NAMESPACE_ALLOWLIST)

    def execute(self, plan: ExecutionPlan) -> KubernetesExecutionResult:
        policy = validate_execution_plan(
            plan,
            allowed_namespaces=self.allowed_namespaces,
        )
        if not policy.allowed:
            return KubernetesExecutionResult(
                applied=False,
                policy=policy,
                deployment_state=None,
                messages=[],
            )

        messages: list[str] = []
        deployment_state: DeploymentState | None = None
        applied = False

        for step in plan.steps:
            if step.action is DeploymentAction.DEPLOY:
                self._deploy(step)
                applied = True
                messages.append(f"patched deployment {step.name} image")
            elif step.action is DeploymentAction.SCALE:
                self._scale(step)
                applied = True
                messages.append(
                    f"scaled deployment {step.name} to {step.params['replicas']} replicas"
                )
            elif step.action is DeploymentAction.STATUS:
                deployment_state = self._read_status(step, plan)
                if deployment_state is None:
                    messages.append(f"deployment {step.name} was not found")
            else:
                raise UnsupportedKubernetesActionError(step.action.value)

        return KubernetesExecutionResult(
            applied=applied,
            policy=policy,
            deployment_state=deployment_state,
            messages=messages,
        )

    def check_connection(self) -> bool:
        self.apps_v1_api.get_api_resources()
        return True

    def _deploy(self, step: PlanStep) -> None:
        image = step.params["image"]
        body = {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": step.name,
                                "image": image,
                            }
                        ]
                    }
                }
            }
        }
        self.apps_v1_api.patch_namespaced_deployment(
            name=step.name,
            namespace=step.namespace,
            body=body,
        )

    def _scale(self, step: PlanStep) -> None:
        body = {"spec": {"replicas": step.params["replicas"]}}
        self.apps_v1_api.patch_namespaced_deployment_scale(
            name=step.name,
            namespace=step.namespace,
            body=body,
        )

    def _read_status(
        self,
        step: PlanStep,
        plan: ExecutionPlan,
    ) -> DeploymentState | None:
        try:
            deployment = self.apps_v1_api.read_namespaced_deployment(
                name=step.name,
                namespace=step.namespace,
            )
        except ApiException as exc:
            if exc.status == 404:
                return None
            raise
        containers = deployment.spec.template.spec.containers
        current_image = containers[0].image if containers else None
        return DeploymentState(
            app=step.name,
            namespace=step.namespace,
            desired_image=plan.intent.image,
            current_image=current_image,
            replicas=deployment.spec.replicas or 0,
            available_replicas=deployment.status.available_replicas or 0,
            observed_at=self.clock(),
        )
