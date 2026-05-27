from devassist_core.plan_builder import build_execution_plan
from devassist_core.schemas import DeploymentAction, PipelineIntent, PlanStatus


def test_builds_deploy_plan_from_intent():
    intent = PipelineIntent(
        action=DeploymentAction.DEPLOY,
        app="api",
        namespace="dev",
        image="example/api:1.0.0",
    )

    plan = build_execution_plan(intent)

    assert plan.status is PlanStatus.DRAFT
    assert plan.requires_approval is True
    assert plan.summary == "Deploy api in namespace dev"
    assert len(plan.steps) == 1
    assert plan.steps[0].resource == "deployment"
    assert plan.steps[0].params == {"image": "example/api:1.0.0"}


def test_builds_scale_plan_from_intent():
    intent = PipelineIntent(
        action=DeploymentAction.SCALE,
        app="api",
        namespace="dev",
        replicas=3,
    )

    plan = build_execution_plan(intent)

    assert plan.summary == "Scale api in namespace dev to 3 replicas"
    assert plan.steps[0].params == {"replicas": 3}


def test_builds_read_only_status_plan_without_approval_requirement():
    intent = PipelineIntent(action=DeploymentAction.STATUS, app="api", namespace="dev")

    plan = build_execution_plan(intent)

    assert plan.requires_approval is False
    assert plan.steps[0].params == {}
