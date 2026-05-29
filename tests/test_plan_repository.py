from devassist_core.plan_builder import build_execution_plan
from devassist_core.plan_repository import InMemoryPlanRepository
from devassist_core.schemas import DeploymentAction, PipelineIntent, PlanStatus


def _plan():
    return build_execution_plan(
        PipelineIntent(
            action=DeploymentAction.DEPLOY,
            app="api",
            namespace="dev",
            image="example/api:1.0.0",
        )
    )


def test_saves_and_loads_plan():
    repository = InMemoryPlanRepository()
    plan = _plan()

    repository.save(plan)

    assert repository.get(plan.plan_id) == plan


def test_approves_plan_with_named_approver():
    repository = InMemoryPlanRepository()
    plan = repository.save(_plan())

    approved = repository.approve(plan.plan_id, approved_by="great")

    assert approved.status is PlanStatus.APPROVED
    assert approved.approved_by == "great"


def test_rejects_plan_without_approver_name():
    repository = InMemoryPlanRepository()
    plan = repository.save(_plan())

    try:
        repository.approve(plan.plan_id, approved_by="")
    except ValueError as exc:
        assert str(exc) == "approved_by is required"
    else:
        raise AssertionError("expected approval to fail")


def test_rejects_plan():
    repository = InMemoryPlanRepository()
    plan = repository.save(_plan())

    rejected = repository.reject(plan.plan_id)

    assert rejected.status is PlanStatus.REJECTED
    assert rejected.approved_by is None
