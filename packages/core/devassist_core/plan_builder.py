from devassist_core.schemas import (
    DeploymentAction,
    ExecutionPlan,
    PipelineIntent,
    PlanStep,
)


def build_execution_plan(intent: PipelineIntent) -> ExecutionPlan:
    if intent.action is DeploymentAction.DEPLOY:
        summary = f"Deploy {intent.app} in namespace {intent.namespace}"
        params = {"image": intent.image}
    elif intent.action is DeploymentAction.SCALE:
        summary = (
            f"Scale {intent.app} in namespace {intent.namespace} "
            f"to {intent.replicas} replicas"
        )
        params = {"replicas": intent.replicas}
    elif intent.action is DeploymentAction.RESTART:
        summary = f"Restart {intent.app} in namespace {intent.namespace}"
        params = {}
    elif intent.action is DeploymentAction.ROLLBACK:
        summary = f"Rollback {intent.app} in namespace {intent.namespace}"
        params = {}
    else:
        summary = f"Read status for {intent.app} in namespace {intent.namespace}"
        params = {}

    step = PlanStep(
        action=intent.action,
        resource="deployment",
        namespace=intent.namespace,
        name=intent.app,
        params={key: value for key, value in params.items() if value is not None},
    )

    return ExecutionPlan(
        intent=intent,
        summary=summary,
        steps=[step],
        requires_approval=intent.action is not DeploymentAction.STATUS,
    )
