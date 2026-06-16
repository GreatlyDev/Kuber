from __future__ import annotations

from datetime import UTC, datetime

from devassist_core.schemas import ExecutionPlan, PlanStatus


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
