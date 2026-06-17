from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Protocol

from devassist_core.schemas import ExecutionPlan, PlanStatus


def plan_state_key(plan_id: str) -> str:
    return f"devassist:plans:{plan_id}"


def plan_index_key() -> str:
    return "devassist:plans:index"


class RedisPlanClient(Protocol):
    def hset(self, name: str, mapping: dict[str, str]) -> object: ...

    def hgetall(self, name: str) -> dict[object, object]: ...

    def zadd(self, name: str, mapping: dict[str, float]) -> object: ...

    def zrange(self, name: str, start: int, end: int) -> list[object]: ...


class InMemoryPlanRepository:
    def __init__(self, clock=None):
        self._plans: dict[str, ExecutionPlan] = {}
        self.clock = clock or (lambda: datetime.now(UTC))

    def save(self, plan: ExecutionPlan) -> ExecutionPlan:
        self._plans[plan.plan_id] = plan
        return plan

    def get(self, plan_id: str) -> ExecutionPlan | None:
        return self._plans.get(plan_id)

    def list(
        self,
        *,
        status: PlanStatus | None = None,
        limit: int | None = None,
    ) -> list[ExecutionPlan]:
        plans = []
        for plan in self._plans.values():
            if status is not None and plan.status is not status:
                continue
            plans.append(plan)
            if limit is not None and len(plans) >= limit:
                break
        return plans

    def list_pending_approvals(self, *, limit: int | None = None) -> list[ExecutionPlan]:
        plans = []
        for plan in self._plans.values():
            if plan.status is not PlanStatus.DRAFT:
                continue
            if not plan.requires_approval:
                continue
            plans.append(plan)
            if limit is not None and len(plans) >= limit:
                break
        return plans

    def approve(self, plan_id: str, approved_by: str) -> ExecutionPlan:
        approved_by = approved_by.strip()
        if not approved_by:
            raise ValueError("approved_by is required")

        plan = self._require_draft_plan(plan_id, transition="approved")
        approved = plan.model_copy(
            update={
                "status": PlanStatus.APPROVED,
                "approved_by": approved_by,
                "updated_at": self.clock(),
            }
        )
        self._plans[plan_id] = approved
        return approved

    def reject(self, plan_id: str) -> ExecutionPlan:
        plan = self._require_draft_plan(plan_id, transition="rejected")
        rejected = plan.model_copy(
            update={
                "status": PlanStatus.REJECTED,
                "approved_by": None,
                "updated_at": self.clock(),
            }
        )
        self._plans[plan_id] = rejected
        return rejected

    def clear(self) -> None:
        self._plans.clear()

    def _require_plan(self, plan_id: str) -> ExecutionPlan:
        plan = self.get(plan_id)
        if plan is None:
            raise KeyError(plan_id)
        return plan

    def _require_draft_plan(self, plan_id: str, *, transition: str) -> ExecutionPlan:
        plan = self._require_plan(plan_id)
        if plan.status is not PlanStatus.DRAFT:
            raise ValueError(f"only draft ExecutionPlans can be {transition}")
        return plan


class RedisPlanRepository:
    def __init__(self, redis: RedisPlanClient, clock=None):
        self.redis = redis
        self.clock = clock or (lambda: datetime.now(UTC))

    def save(self, plan: ExecutionPlan) -> ExecutionPlan:
        self.redis.hset(plan_state_key(plan.plan_id), mapping=_plan_to_hash(plan))
        self.redis.zadd(plan_index_key(), {plan.plan_id: plan.created_at.timestamp()})
        return plan

    def get(self, plan_id: str) -> ExecutionPlan | None:
        raw = self.redis.hgetall(plan_state_key(plan_id))
        if not raw:
            return None
        return ExecutionPlan.model_validate(_hash_to_plan_data(raw))

    def list(
        self,
        *,
        status: PlanStatus | None = None,
        limit: int | None = None,
    ) -> list[ExecutionPlan]:
        plan_ids = [
            _decode(plan_id)
            for plan_id in self.redis.zrange(plan_index_key(), 0, -1)
        ]
        plans = []
        for plan_id in plan_ids:
            plan = self.get(plan_id)
            if plan is None:
                continue
            if status is not None and plan.status is not status:
                continue
            plans.append(plan)
            if limit is not None and len(plans) >= limit:
                break
        return plans

    def list_pending_approvals(self, *, limit: int | None = None) -> list[ExecutionPlan]:
        plans = []
        for plan in self.list():
            if plan.status is not PlanStatus.DRAFT:
                continue
            if not plan.requires_approval:
                continue
            plans.append(plan)
            if limit is not None and len(plans) >= limit:
                break
        return plans

    def approve(self, plan_id: str, approved_by: str) -> ExecutionPlan:
        approved_by = approved_by.strip()
        if not approved_by:
            raise ValueError("approved_by is required")

        plan = self._require_draft_plan(plan_id, transition="approved")
        approved = plan.model_copy(
            update={
                "status": PlanStatus.APPROVED,
                "approved_by": approved_by,
                "updated_at": self.clock(),
            }
        )
        return self.save(approved)

    def reject(self, plan_id: str) -> ExecutionPlan:
        plan = self._require_draft_plan(plan_id, transition="rejected")
        rejected = plan.model_copy(
            update={
                "status": PlanStatus.REJECTED,
                "approved_by": None,
                "updated_at": self.clock(),
            }
        )
        return self.save(rejected)

    def _require_plan(self, plan_id: str) -> ExecutionPlan:
        plan = self.get(plan_id)
        if plan is None:
            raise KeyError(plan_id)
        return plan

    def _require_draft_plan(self, plan_id: str, *, transition: str) -> ExecutionPlan:
        plan = self._require_plan(plan_id)
        if plan.status is not PlanStatus.DRAFT:
            raise ValueError(f"only draft ExecutionPlans can be {transition}")
        return plan


def _plan_to_hash(plan: ExecutionPlan) -> dict[str, str]:
    data = plan.model_dump(mode="json", exclude={"approved"})
    return {key: json.dumps(value) for key, value in data.items()}


def _hash_to_plan_data(raw: dict[object, object]) -> dict[str, object]:
    return {_decode(key): json.loads(_decode(value)) for key, value in raw.items()}


def _decode(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)
