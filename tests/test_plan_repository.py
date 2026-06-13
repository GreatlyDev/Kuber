from datetime import UTC, datetime

import pytest

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


def test_lists_plans_by_status_with_limit():
    repository = InMemoryPlanRepository()
    repository.save(_plan())
    first_approved = repository.save(_plan())
    second_approved = repository.save(_plan())
    repository.approve(first_approved.plan_id, approved_by="great")
    repository.approve(second_approved.plan_id, approved_by="great")

    plans = repository.list(status=PlanStatus.APPROVED, limit=1)

    assert [plan.plan_id for plan in plans] == [first_approved.plan_id]


def test_approves_plan_with_named_approver():
    repository = InMemoryPlanRepository()
    plan = repository.save(_plan())

    approved = repository.approve(plan.plan_id, approved_by="great")

    assert approved.status is PlanStatus.APPROVED
    assert approved.approved_by == "great"


def test_approve_updates_plan_timestamp():
    decided_at = datetime(2026, 6, 8, 12, 30, tzinfo=UTC)
    repository = InMemoryPlanRepository(clock=lambda: decided_at)
    plan = repository.save(_plan())

    approved = repository.approve(plan.plan_id, approved_by="great")

    assert approved.updated_at == decided_at
    assert repository.get(plan.plan_id).updated_at == decided_at


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


def test_reject_updates_plan_timestamp():
    decided_at = datetime(2026, 6, 8, 13, 45, tzinfo=UTC)
    repository = InMemoryPlanRepository(clock=lambda: decided_at)
    plan = repository.save(_plan())

    rejected = repository.reject(plan.plan_id)

    assert rejected.updated_at == decided_at
    assert repository.get(plan.plan_id).updated_at == decided_at


def test_cannot_approve_rejected_plan():
    repository = InMemoryPlanRepository()
    plan = repository.save(_plan())
    repository.reject(plan.plan_id)

    with pytest.raises(ValueError, match="only draft ExecutionPlans can be approved"):
        repository.approve(plan.plan_id, approved_by="great")

    assert repository.get(plan.plan_id).status is PlanStatus.REJECTED


def test_cannot_reject_approved_plan():
    repository = InMemoryPlanRepository()
    plan = repository.save(_plan())
    repository.approve(plan.plan_id, approved_by="great")

    with pytest.raises(ValueError, match="only draft ExecutionPlans can be rejected"):
        repository.reject(plan.plan_id)

    assert repository.get(plan.plan_id).status is PlanStatus.APPROVED
