from datetime import UTC, datetime

from devassist_core.run_store import RedisRunStore, run_events_key, run_state_key
from devassist_core.schemas import ExecutionRun, RunEvent, RunStatus


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
        event_id = f"{len(stream) + 1}-0"
        stream.append((event_id, dict(fields)))
        return event_id

    def xrange(self, name):
        return self.streams.get(name, [])


def test_run_state_key_is_deterministic():
    assert run_state_key("run-123") == "devassist:runs:run-123"


def test_run_events_key_is_deterministic():
    assert run_events_key("run-123") == "devassist:runs:run-123:events"


def test_saves_and_loads_execution_run_from_redis_hash():
    redis = FakeRedis()
    store = RedisRunStore(redis)
    run = ExecutionRun(
        run_id="run-123",
        plan_id="plan-123",
        status=RunStatus.QUEUED,
        redis_state_key=run_state_key("run-123"),
        created_at=datetime(2026, 5, 27, tzinfo=UTC),
        updated_at=datetime(2026, 5, 27, tzinfo=UTC),
    )

    store.save_run(run)
    loaded = store.get_run("run-123")

    assert loaded == run


def test_appends_and_loads_run_events_from_redis_stream():
    redis = FakeRedis()
    store = RedisRunStore(redis)
    event = RunEvent(
        event_id="evt-123",
        run_id="run-123",
        event_type="run.queued",
        message="Run queued",
        redis_stream_key=run_events_key("run-123"),
        payload={"plan_id": "plan-123"},
        created_at=datetime(2026, 5, 27, tzinfo=UTC),
    )

    stream_id = store.append_event(event)
    events = store.list_events("run-123")

    assert stream_id == "1-0"
    assert events == [event]
