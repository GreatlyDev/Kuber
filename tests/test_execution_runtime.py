import pytest

from devassist_core.execution_runtime import ExecutionRuntime
from devassist_core.kubernetes_executor import KubernetesExecutionResult
from devassist_core.plan_builder import build_execution_plan
from devassist_core.policy import PolicyDecision
from devassist_core.run_store import RedisRunStore
from devassist_core.schemas import DeploymentAction, PipelineIntent, PlanStatus, RunStatus


class FakeRedis:
    def __init__(self):
        self.hashes = {}
        self.streams = {}

    def hset(self, name, mapping):
        self.hashes[name] = dict(mapping)
        return len(mapping)

    def hgetall(self, name):
        return self.hashes.get(name, {})

    def xadd(self, name, fields):
        stream = self.streams.setdefault(name, [])
        stream_id = f"{len(stream) + 1}-0"
        stream.append((stream_id, dict(fields)))
        return stream_id

    def xrange(self, name):
        return self.streams.get(name, [])


class FakeExecutor:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.executed_plan_ids = []

    def execute(self, plan):
        self.executed_plan_ids.append(plan.plan_id)
        if self.fail:
            raise RuntimeError("cluster unavailable")
        return KubernetesExecutionResult(
            applied=True,
            policy=PolicyDecision(allowed=True, reasons=[]),
            messages=["patched deployment api image"],
        )


def _approved_plan():
    plan = build_execution_plan(
        PipelineIntent(
            action=DeploymentAction.DEPLOY,
            app="api",
            namespace="dev",
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
