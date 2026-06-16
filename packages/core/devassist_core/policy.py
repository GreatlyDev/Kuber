from collections.abc import Collection

from devassist_core.schemas import (
    DeploymentAction,
    ExecutionPlan,
    PlanStatus,
    PolicyDecision,
)

DEFAULT_NAMESPACE_ALLOWLIST = frozenset({"default", "dev", "local", "staging"})
LOCAL_NAMESPACE_ALLOWLIST = DEFAULT_NAMESPACE_ALLOWLIST
READ_ONLY_ACTIONS = frozenset({DeploymentAction.STATUS})
SUPPORTED_KUBERNETES_ACTIONS = frozenset(
    {
        DeploymentAction.DEPLOY,
        DeploymentAction.SCALE,
        DeploymentAction.STATUS,
    }
)


def validate_execution_plan(
    plan: ExecutionPlan,
    *,
    allowed_namespaces: Collection[str] | None = None,
) -> PolicyDecision:
    namespace_allowlist = frozenset(allowed_namespaces or DEFAULT_NAMESPACE_ALLOWLIST)
    reasons: list[str] = []
    mutating_steps = [step for step in plan.steps if step.action not in READ_ONLY_ACTIONS]

    if plan.status is PlanStatus.REJECTED:
        reasons.append("rejected ExecutionPlans cannot be run")

    if mutating_steps and not plan.approved and plan.status is not PlanStatus.REJECTED:
        reasons.append("mutating Kubernetes actions require an approved ExecutionPlan")

    for step in plan.steps:
        if step.action not in SUPPORTED_KUBERNETES_ACTIONS:
            reasons.append(
                f"action '{step.action.value}' is not supported by the MVP Kubernetes executor"
            )
        if step.namespace not in namespace_allowlist:
            reasons.append(
                f"namespace '{step.namespace}' is outside the configured namespace allowlist"
            )

    return PolicyDecision(allowed=not reasons, reasons=reasons)
