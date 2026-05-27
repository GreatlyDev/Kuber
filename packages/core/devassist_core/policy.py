from pydantic import BaseModel, ConfigDict

from devassist_core.schemas import DeploymentAction, ExecutionPlan

LOCAL_NAMESPACE_ALLOWLIST = frozenset({"default", "dev", "local", "staging"})
READ_ONLY_ACTIONS = frozenset({DeploymentAction.STATUS})


class PolicyDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    reasons: list[str]


def validate_execution_plan(plan: ExecutionPlan) -> PolicyDecision:
    reasons: list[str] = []
    mutating_steps = [step for step in plan.steps if step.action not in READ_ONLY_ACTIONS]

    if mutating_steps and not plan.approved:
        reasons.append("mutating Kubernetes actions require an approved ExecutionPlan")

    for step in plan.steps:
        if step.namespace not in LOCAL_NAMESPACE_ALLOWLIST:
            reasons.append(
                f"namespace '{step.namespace}' is outside the local MVP allowlist"
            )

    return PolicyDecision(allowed=not reasons, reasons=reasons)
