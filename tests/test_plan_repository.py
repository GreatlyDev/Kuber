from datetime import UTC, datetime

import pytest

from devassist_core.plan_builder import build_execution_plan
from devassist_core.plan_repository import (
    InMemoryPlanRepository,
    RedisPlanRepository,
    plan_index_key,
    plan_state_key,
)
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


class FakeRedis:
    def __init__(self):
        self.hashes = {}
        self.sorted_sets = {}

    def hset(self, name, mapping):
        self.hashes[name] = dict(mapping)
        return len(mapping)

    def hgetall(self, name):
        return self.hashes.get(name, {})

    def zadd(self, name, mapping):
        sorted_set = self.sorted_sets.setdefault(name, {})
        sorted_set.update(mapping)
        return len(mapping)

    def zrange(self, name, start, end):
        sorted_set = self.sorted_sets.get(name, {})
        items = sorted(sorted_set.items(), key=lambda item: item[1])
        if end == -1:
            selected = items[start:]
        else:
            selected = items[start : end + 1]
        return [member for member, _score in selected]


def test_plan_state_key_is_deterministic():
    assert plan_state_key("plan-123") == "devassist:plans:plan-123"


def test_plan_index_key_is_deterministic():
    assert plan_index_key() == "devassist:plans:index"


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


def test_lists_pending_approval_plans_with_limit():
    repository = InMemoryPlanRepository()
    first_pending = repository.save(_plan())
    second_pending = repository.save(_plan())
    approved = repository.save(_plan())
    repository.approve(approved.plan_id, approved_by="great")

    plans = repository.list_pending_approvals(limit=1)

    assert [plan.plan_id for plan in plans] == [first_pending.plan_id]
    assert second_pending.plan_id not in [plan.plan_id for plan in plans]
    assert approved.plan_id not in [plan.plan_id for plan in plans]


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


def test_redis_repository_saves_and_loads_plan():
    redis = FakeRedis()
    repository = RedisPlanRepository(redis)
    plan = _plan()

    repository.save(plan)

    assert repository.get(plan.plan_id) == plan
    assert plan_state_key(plan.plan_id) in redis.hashes
    assert redis.sorted_sets[plan_index_key()] == {
        plan.plan_id: plan.created_at.timestamp()
    }


def test_redis_repository_lists_plans_by_status_with_limit():
    redis = FakeRedis()
    repository = RedisPlanRepository(redis)
    repository.save(_plan())
    first_approved = repository.save(_plan())
    second_approved = repository.save(_plan())
    repository.approve(first_approved.plan_id, approved_by="great")
    repository.approve(second_approved.plan_id, approved_by="great")

    plans = repository.list(status=PlanStatus.APPROVED, limit=1)

    assert [plan.plan_id for plan in plans] == [first_approved.plan_id]


def test_redis_repository_lists_pending_approval_plans_with_limit():
    redis = FakeRedis()
    repository = RedisPlanRepository(redis)
    first_pending = repository.save(_plan())
    second_pending = repository.save(_plan())
    approved = repository.save(_plan())
    repository.approve(approved.plan_id, approved_by="great")

    plans = repository.list_pending_approvals(limit=1)

    assert [plan.plan_id for plan in plans] == [first_pending.plan_id]
    assert second_pending.plan_id not in [plan.plan_id for plan in plans]
    assert approved.plan_id not in [plan.plan_id for plan in plans]


def test_redis_repository_approval_transitions_are_persisted():
    decided_at = datetime(2026, 6, 17, 9, 15, tzinfo=UTC)
    redis = FakeRedis()
    repository = RedisPlanRepository(redis, clock=lambda: decided_at)
    plan = repository.save(_plan())

    approved = repository.approve(plan.plan_id, approved_by=" great ")

    assert approved.status is PlanStatus.APPROVED
    assert approved.approved_by == "great"
    assert approved.updated_at == decided_at
    assert repository.get(plan.plan_id) == approved


def test_redis_repository_rejects_missing_plan():
    repository = RedisPlanRepository(FakeRedis())

    with pytest.raises(KeyError):
        repository.approve("plan-missing", approved_by="great")
