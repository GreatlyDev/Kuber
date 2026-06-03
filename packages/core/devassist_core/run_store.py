import json
from typing import Protocol

from devassist_core.schemas import ExecutionRun, RunEvent, RunStatus


def run_state_key(run_id: str) -> str:
    return f"devassist:runs:{run_id}"


def run_events_key(run_id: str) -> str:
    return f"{run_state_key(run_id)}:events"


def run_index_key() -> str:
    return "devassist:runs:index"


class RedisClient(Protocol):
    def hset(self, name: str, mapping: dict[str, str]) -> object: ...

    def hgetall(self, name: str) -> dict[object, object]: ...

    def xadd(self, name: str, fields: dict[str, str]) -> object: ...

    def xrange(self, name: str) -> list[tuple[object, dict[object, object]]]: ...

    def zadd(self, name: str, mapping: dict[str, float]) -> object: ...

    def zrevrange(self, name: str, start: int, end: int) -> list[object]: ...


class RedisRunStore:
    def __init__(self, redis: RedisClient):
        self.redis = redis

    def save_run(self, run: ExecutionRun) -> None:
        self.redis.hset(run.redis_state_key, mapping=_model_to_hash(run))
        self.redis.zadd(run_index_key(), {run.run_id: run.created_at.timestamp()})

    def get_run(self, run_id: str) -> ExecutionRun | None:
        raw = self.redis.hgetall(run_state_key(run_id))
        if not raw:
            return None
        return ExecutionRun.model_validate(_hash_to_model_data(raw))

    def list_runs(
        self,
        *,
        status: RunStatus | None = None,
        limit: int = 50,
    ) -> list[ExecutionRun]:
        run_ids = [
            _decode(run_id)
            for run_id in self.redis.zrevrange(run_index_key(), 0, -1)
        ]
        runs: list[ExecutionRun] = []
        for run_id in run_ids:
            run = self.get_run(run_id)
            if run is None:
                continue
            if status is not None and run.status is not status:
                continue
            runs.append(run)
            if len(runs) >= limit:
                break
        return runs

    def append_event(self, event: RunEvent) -> str:
        stream_id = self.redis.xadd(event.redis_stream_key, _model_to_hash(event))
        return _decode(stream_id)

    def list_events(self, run_id: str) -> list[RunEvent]:
        entries = self.redis.xrange(run_events_key(run_id))
        return [
            RunEvent.model_validate(_hash_to_model_data(fields))
            for _stream_id, fields in entries
        ]


def _model_to_hash(model: ExecutionRun | RunEvent) -> dict[str, str]:
    data = model.model_dump(mode="json")
    return {key: json.dumps(value) for key, value in data.items()}


def _hash_to_model_data(raw: dict[object, object]) -> dict[str, object]:
    return {_decode(key): json.loads(_decode(value)) for key, value in raw.items()}


def _decode(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)
