from datetime import UTC, datetime

import pytest

from devassist_core.execution_runtime import ExecutionRuntime
from devassist_core.kubernetes_executor import KubernetesExecutionResult
from devassist_core.plan_builder import build_execution_plan
from devassist_core.policy import PolicyDecision
from devassist_core.run_service import PlanNotAllowedError
from devassist_core.run_store import RedisRunStore
from devassist_core.schemas import DeploymentAction, PipelineIntent, PlanStatus, RunStatus


class FakeRedis:
    def __init__(self):
        self.hashes = {}
        self.streams = {}
        self.sorted_sets = {}

    def hset(self, name, mapping):
        self.hashes[name] = dict(mapping)
        return len(mapping)

    def hgetall(self, name):
        return self.hashes.get(name, {})

    def ping(self):
        return True

    def xadd(self, name, fields):
        stream = self.streams.setdefault(name, [])
        stream_id = f"{len(stream) + 1}-0"
        stream.append((stream_id, dict(fields)))
        return stream_id

    def xrange(self, name):
        return self.streams.get(name, [])

    def zadd(self, name, mapping):
        sorted_set = self.sorted_sets.setdefault(name, {})
        sorted_set.update(mapping)
        return len(mapping)

    def zrevrange(self, name, start, end):
        return []


class FakeExecutor:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.executed_plan_ids = []
        self.connection_checks = 0

    def execute(self, plan):
        self.executed_plan_ids.append(plan.plan_id)
        if self.fail:
            raise RuntimeError("cluster unavailable")
        return KubernetesExecutionResult(
            applied=True,
            policy=PolicyDecision(allowed=True, reasons=[]),
            messages=["patched deployment api image"],
        )

    def check_connection(self):
        self.connection_checks += 1
        if self.fail:
            raise RuntimeError("cluster unavailable")
        return True


def _approved_plan(namespace="dev"):
    plan = build_execution_plan(
        PipelineIntent(
            action=DeploymentAction.DEPLOY,
            app="api",
            namespace=namespace,
            image="example/api:1.0.0",
        )
    )
    return plan.model_copy(update={"status": PlanStatus.APPROVED, "approved_by": "great"})


def test_runtime_records_running_and_succeeded_events():
    store = RedisRunStore(FakeRedis())
    executor = FakeExecutor()
    runtime = ExecutionRuntime(store=store, executor=executor)

    run = runtime.execute(_approved_plan())
    events = store.list_events(run.run_id)

    assert run.status is RunStatus.SUCCEEDED
    assert store.get_run(run.run_id) == run
    assert [event.event_type for event in events] == [
        "run.queued",
        "run.started",
        "run.succeeded",
    ]
    assert events[-1].payload == {"messages": ["patched deployment api image"]}


def test_runtime_updates_run_timestamp_on_status_transitions():
    store = RedisRunStore(FakeRedis())
    executor = FakeExecutor()
    ticks = iter(
        [
            datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
            datetime(2026, 6, 3, 12, 1, tzinfo=UTC),
        ]
    )
    runtime = ExecutionRuntime(
        store=store,
        executor=executor,
        clock=lambda: next(ticks),
    )

    run = runtime.execute(_approved_plan())
    stored_run = store.get_run(run.run_id)

    assert run.status is RunStatus.SUCCEEDED
    assert run.updated_at == datetime(2026, 6, 3, 12, 1, tzinfo=UTC)
    assert stored_run == run


def test_runtime_checks_redis_and_kubernetes_dependencies():
    store = RedisRunStore(FakeRedis())
    executor = FakeExecutor()
    runtime = ExecutionRuntime(store=store, executor=executor)

    dependencies = runtime.check_dependencies()

    assert dependencies == {"redis": "ok", "kubernetes": "ok"}
    assert executor.connection_checks == 1


def test_runtime_reports_unavailable_dependency_without_raising():
    store = RedisRunStore(FakeRedis())
    executor = FakeExecutor(fail=True)
    runtime = ExecutionRuntime(store=store, executor=executor)

    dependencies = runtime.check_dependencies()

    assert dependencies == {"redis": "ok", "kubernetes": "unavailable"}


def test_runtime_records_failed_event_and_reraises_error():
    redis = FakeRedis()
    store = RedisRunStore(redis)
    executor = FakeExecutor(fail=True)
    runtime = ExecutionRuntime(store=store, executor=executor)

    with pytest.raises(RuntimeError, match="cluster unavailable"):
        runtime.execute(_approved_plan())

    run_id = next(iter(redis.hashes)).removeprefix("devassist:runs:")
    run = store.get_run(run_id)
    events = store.list_events(run_id)

    assert run.status is RunStatus.FAILED
    assert [event.event_type for event in events] == [
        "run.queued",
        "run.started",
        "run.failed",
    ]
    assert events[-1].payload == {"error": "cluster unavailable"}


def test_runtime_rejects_plan_outside_allowed_namespaces_before_executor_call():
    redis = FakeRedis()
    store = RedisRunStore(redis)
    executor = FakeExecutor()
    runtime = ExecutionRuntime(
        store=store,
        executor=executor,
        allowed_namespaces=("dev",),
    )

    with pytest.raises(PlanNotAllowedError) as exc:
        runtime.execute(_approved_plan(namespace="staging"))

    assert exc.value.reasons == [
        "namespace 'staging' is outside the configured namespace allowlist"
    ]
    assert redis.hashes == {}
    assert executor.executed_plan_ids == []
