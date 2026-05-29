import pytest

from devassist_core.plan_builder import build_execution_plan
from devassist_core.run_service import PlanNotAllowedError, queue_execution_run
from devassist_core.run_store import RedisRunStore, run_events_key, run_state_key
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


def _draft_plan():
    return build_execution_plan(
        PipelineIntent(
            action=DeploymentAction.DEPLOY,
            app="api",
            namespace="dev",
            image="example/api:1.0.0",
        )
    )


def test_draft_mutating_plan_cannot_be_queued():
    store = RedisRunStore(FakeRedis())

    with pytest.raises(PlanNotAllowedError) as exc:
        queue_execution_run(_draft_plan(), store)

    assert exc.value.reasons == [
        "mutating Kubernetes actions require an approved ExecutionPlan"
    ]


def test_approved_plan_is_queued_and_recorded_in_redis():
    store = RedisRunStore(FakeRedis())
    approved_plan = _draft_plan().model_copy(
        update={"status": PlanStatus.APPROVED, "approved_by": "great"}
    )

    run = queue_execution_run(approved_plan, store)
    loaded_run = store.get_run(run.run_id)
    events = store.list_events(run.run_id)

    assert run.status is RunStatus.QUEUED
    assert run.plan_id == approved_plan.plan_id
    assert run.redis_state_key == run_state_key(run.run_id)
    assert loaded_run == run
    assert len(events) == 1
    assert events[0].event_type == "run.queued"
    assert events[0].redis_stream_key == run_events_key(run.run_id)
    assert events[0].payload == {"plan_id": approved_plan.plan_id}
