from devassist_core.schemas import ExecutionPlan, PlanStatus


class InMemoryPlanRepository:
    def __init__(self):
        self._plans: dict[str, ExecutionPlan] = {}

    def save(self, plan: ExecutionPlan) -> ExecutionPlan:
        self._plans[plan.plan_id] = plan
        return plan

    def get(self, plan_id: str) -> ExecutionPlan | None:
        return self._plans.get(plan_id)

    def list(self) -> list[ExecutionPlan]:
        return list(self._plans.values())

    def approve(self, plan_id: str, approved_by: str) -> ExecutionPlan:
        approved_by = approved_by.strip()
        if not approved_by:
            raise ValueError("approved_by is required")

        plan = self._require_plan(plan_id)
        approved = plan.model_copy(
            update={
                "status": PlanStatus.APPROVED,
                "approved_by": approved_by,
            }
        )
        self._plans[plan_id] = approved
        return approved

    def reject(self, plan_id: str) -> ExecutionPlan:
        plan = self._require_plan(plan_id)
        rejected = plan.model_copy(
            update={
                "status": PlanStatus.REJECTED,
                "approved_by": None,
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
