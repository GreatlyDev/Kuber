from collections.abc import Collection
from uuid import uuid4

from devassist_core.policy import validate_execution_plan
from devassist_core.run_store import RedisRunStore, run_events_key, run_state_key
from devassist_core.schemas import ExecutionPlan, ExecutionRun, RunEvent, RunStatus


class PlanNotAllowedError(Exception):
    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons))


def queue_execution_run(
    plan: ExecutionPlan,
    store: RedisRunStore,
    *,
    allowed_namespaces: Collection[str] | None = None,
) -> ExecutionRun:
    decision = validate_execution_plan(plan, allowed_namespaces=allowed_namespaces)
    if not decision.allowed:
        raise PlanNotAllowedError(decision.reasons)

    run_id = f"run-{uuid4().hex}"
    run = ExecutionRun(
        run_id=run_id,
        plan_id=plan.plan_id,
        status=RunStatus.QUEUED,
        redis_state_key=run_state_key(run_id),
    )
    event = RunEvent(
        run_id=run_id,
        event_type="run.queued",
        message="Run queued",
        redis_stream_key=run_events_key(run_id),
        payload={"plan_id": plan.plan_id},
    )

    store.save_run(run)
    store.append_event(event)
    return run
