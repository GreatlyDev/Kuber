import json
from typing import Protocol

from devassist_core.schemas import ExecutionRun, RunEvent


def run_state_key(run_id: str) -> str:
    return f"devassist:runs:{run_id}"


def run_events_key(run_id: str) -> str:
    return f"{run_state_key(run_id)}:events"


class RedisClient(Protocol):
    def hset(self, name: str, mapping: dict[str, str]) -> object: ...

    def hgetall(self, name: str) -> dict[object, object]: ...

    def xadd(self, name: str, fields: dict[str, str]) -> object: ...

    def xrange(self, name: str) -> list[tuple[object, dict[object, object]]]: ...


class RedisRunStore:
    def __init__(self, redis: RedisClient):
        self.redis = redis

    def save_run(self, run: ExecutionRun) -> None:
        self.redis.hset(run.redis_state_key, mapping=_model_to_hash(run))

    def get_run(self, run_id: str) -> ExecutionRun | None:
        raw = self.redis.hgetall(run_state_key(run_id))
        if not raw:
            return None
        return ExecutionRun.model_validate(_hash_to_model_data(raw))

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
