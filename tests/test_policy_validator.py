from devassist_core.policy import PolicyDecision, validate_execution_plan
from devassist_core.schemas import DeploymentAction, ExecutionPlan, PipelineIntent, PlanStatus, PlanStep


def _plan(status=PlanStatus.DRAFT, action=DeploymentAction.DEPLOY, namespace="dev"):
    intent = PipelineIntent(
        action=action,
        app="api",
        namespace=namespace,
        image="example/api:1.0.0" if action is DeploymentAction.DEPLOY else None,
    )
    return ExecutionPlan(
        intent=intent,
        summary=f"{action.value} api in {namespace}",
        status=status,
        approved_by="great" if status is PlanStatus.APPROVED else None,
        steps=[
            PlanStep(
                action=action,
                resource="deployment",
                namespace=namespace,
                name="api",
                params={"image": "example/api:1.0.0"} if action is DeploymentAction.DEPLOY else {},
            )
        ],
    )


def test_policy_rejects_mutating_plan_without_approval():
    decision = validate_execution_plan(_plan())

    assert decision == PolicyDecision(
        allowed=False,
        reasons=["mutating Kubernetes actions require an approved ExecutionPlan"],
    )


def test_policy_allows_approved_mutating_plan():
    decision = validate_execution_plan(_plan(status=PlanStatus.APPROVED))

    assert decision.allowed is True
    assert decision.reasons == []


def test_policy_rejects_non_local_namespace():
    decision = validate_execution_plan(_plan(status=PlanStatus.APPROVED, namespace="prod"))

    assert decision.allowed is False
    assert "namespace 'prod' is outside the local MVP allowlist" in decision.reasons


def test_policy_allows_read_only_status_without_approval():
    decision = validate_execution_plan(
        _plan(status=PlanStatus.DRAFT, action=DeploymentAction.STATUS)
    )

    assert decision.allowed is True
    assert decision.reasons == []
