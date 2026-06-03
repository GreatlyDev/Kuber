from datetime import UTC, datetime

from devassist_core.run_store import (
    RedisRunStore,
    run_events_key,
    run_index_key,
    run_state_key,
)
from devassist_core.schemas import ExecutionRun, RunEvent, RunStatus


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

    def xadd(self, name, fields):
        stream = self.streams.setdefault(name, [])
        event_id = f"{len(stream) + 1}-0"
        stream.append((event_id, dict(fields)))
        return event_id

    def xrange(self, name):
        return self.streams.get(name, [])

    def zadd(self, name, mapping):
        sorted_set = self.sorted_sets.setdefault(name, {})
        sorted_set.update(mapping)
        return len(mapping)

    def zrevrange(self, name, start, end):
        sorted_set = self.sorted_sets.get(name, {})
        items = sorted(
            sorted_set.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        if end == -1:
            selected = items[start:]
        else:
            selected = items[start : end + 1]
        return [member for member, _score in selected]


def test_run_state_key_is_deterministic():
    assert run_state_key("run-123") == "devassist:runs:run-123"


def test_run_events_key_is_deterministic():
    assert run_events_key("run-123") == "devassist:runs:run-123:events"


def test_run_index_key_is_deterministic():
    assert run_index_key() == "devassist:runs:index"


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


def test_saves_execution_run_to_recent_run_index():
    redis = FakeRedis()
    store = RedisRunStore(redis)
    run = ExecutionRun(
        run_id="run-123",
        plan_id="plan-123",
        status=RunStatus.QUEUED,
        redis_state_key=run_state_key("run-123"),
        created_at=datetime(2026, 5, 27, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 27, 12, 0, tzinfo=UTC),
    )

    store.save_run(run)

    assert redis.sorted_sets[run_index_key()] == {
        "run-123": datetime(2026, 5, 27, 12, 0, tzinfo=UTC).timestamp()
    }


def test_lists_recent_runs_newest_first():
    redis = FakeRedis()
    store = RedisRunStore(redis)
    older = ExecutionRun(
        run_id="run-older",
        plan_id="plan-older",
        status=RunStatus.SUCCEEDED,
        redis_state_key=run_state_key("run-older"),
        created_at=datetime(2026, 5, 27, 12, 0, tzinfo=UTC),
    )
    newer = ExecutionRun(
        run_id="run-newer",
        plan_id="plan-newer",
        status=RunStatus.FAILED,
        redis_state_key=run_state_key("run-newer"),
        created_at=datetime(2026, 5, 27, 12, 5, tzinfo=UTC),
    )

    store.save_run(older)
    store.save_run(newer)

    runs = store.list_runs()

    assert [run.run_id for run in runs] == ["run-newer", "run-older"]


def test_lists_recent_runs_with_status_filter_and_limit():
    redis = FakeRedis()
    store = RedisRunStore(redis)
    first = ExecutionRun(
        run_id="run-first",
        plan_id="plan-first",
        status=RunStatus.SUCCEEDED,
        redis_state_key=run_state_key("run-first"),
        created_at=datetime(2026, 5, 27, 12, 0, tzinfo=UTC),
    )
    second = ExecutionRun(
        run_id="run-second",
        plan_id="plan-second",
        status=RunStatus.FAILED,
        redis_state_key=run_state_key("run-second"),
        created_at=datetime(2026, 5, 27, 12, 5, tzinfo=UTC),
    )
    third = ExecutionRun(
        run_id="run-third",
        plan_id="plan-third",
        status=RunStatus.SUCCEEDED,
        redis_state_key=run_state_key("run-third"),
        created_at=datetime(2026, 5, 27, 12, 10, tzinfo=UTC),
    )

    store.save_run(first)
    store.save_run(second)
    store.save_run(third)

    runs = store.list_runs(status=RunStatus.SUCCEEDED, limit=1)

    assert [run.run_id for run in runs] == ["run-third"]


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
