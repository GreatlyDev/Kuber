from collections.abc import Collection
from datetime import UTC, datetime
from typing import Protocol

from devassist_core.kubernetes_executor import KubernetesExecutionResult
from devassist_core.policy import (
    DEFAULT_NAMESPACE_ALLOWLIST,
    PolicyDecision,
    validate_execution_plan,
)
from devassist_core.run_service import queue_execution_run
from devassist_core.run_store import RedisRunStore, run_events_key
from devassist_core.schemas import ExecutionPlan, ExecutionRun, RunEvent, RunStatus


class PlanExecutor(Protocol):
    def execute(self, plan: ExecutionPlan) -> KubernetesExecutionResult: ...


class ExecutionRuntime:
    def __init__(
        self,
        store: RedisRunStore,
        executor: PlanExecutor,
        allowed_namespaces: Collection[str] | None = None,
        clock=None,
    ):
        self.store = store
        self.executor = executor
        self.allowed_namespaces = tuple(allowed_namespaces or DEFAULT_NAMESPACE_ALLOWLIST)
        self.clock = clock or (lambda: datetime.now(UTC))

    def validate(self, plan: ExecutionPlan) -> PolicyDecision:
        return validate_execution_plan(
            plan,
            allowed_namespaces=self.allowed_namespaces,
        )

    def check_dependencies(self) -> dict[str, str]:
        return {
            "redis": self._check_redis(),
            "kubernetes": self._check_kubernetes(),
        }

    def execute(self, plan: ExecutionPlan) -> ExecutionRun:
        run = queue_execution_run(
            plan,
            self.store,
            allowed_namespaces=self.allowed_namespaces,
        )
        running = self._transition(run, RunStatus.RUNNING)
        self._append_event(running, "run.started", "Run started")

        try:
            result = self.executor.execute(plan)
        except Exception as exc:
            failed = self._transition(running, RunStatus.FAILED)
            self._append_event(
                failed,
                "run.failed",
                "Run failed",
                payload={"error": str(exc)},
            )
            raise

        succeeded = self._transition(running, RunStatus.SUCCEEDED)
        self._append_event(
            succeeded,
            "run.succeeded",
            "Run succeeded",
            payload={"messages": result.messages},
        )
        return succeeded

    def _transition(self, run: ExecutionRun, status: RunStatus) -> ExecutionRun:
        updated = run.model_copy(
            update={
                "status": status,
                "updated_at": self.clock(),
            }
        )
        self.store.save_run(updated)
        return updated

    def _append_event(
        self,
        run: ExecutionRun,
        event_type: str,
        message: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        self.store.append_event(
            RunEvent(
                run_id=run.run_id,
                event_type=event_type,
                message=message,
                redis_stream_key=run_events_key(run.run_id),
                payload=payload or {},
            )
        )

    def _check_redis(self) -> str:
        try:
            return "ok" if self.store.ping() else "unavailable"
        except Exception:
            return "unavailable"

    def _check_kubernetes(self) -> str:
        check_connection = getattr(self.executor, "check_connection", None)
        if check_connection is None:
            return "configured"
        try:
            return "ok" if check_connection() else "unavailable"
        except Exception:
            return "unavailable"
