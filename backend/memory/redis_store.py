import json
import hashlib
from typing import Optional, List
from datetime import datetime, timezone

import redis.asyncio as aioredis
from pydantic import BaseModel

from backend.config import settings


class TaskHistoryEntry(BaseModel):
    task_id: str
    task: str
    outcome: str  # "success" | "retryable_failure" | "hard_failure"
    final_response: Optional[str]
    timestamp: str


class SessionMemory(BaseModel):
    session_id: str
    task_history: List[TaskHistoryEntry] = []
    last_successful_code: Optional[str] = None
    last_error: Optional[str] = None
    created_at: str
    updated_at: str


SESSION_KEY_PREFIX = "session:"
TOOL_RESULT_KEY_PREFIX = "tool_result:"
TASK_KEY_PREFIX = "task:"
TASK_UPDATES_PREFIX = "task_updates:"
TOOL_RESULT_TTL = 86400  # 1 day

_redis_client: Optional[aioredis.Redis] = None


async def get_redis_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_url, encoding="utf-8", decode_responses=True
        )
    return _redis_client


def hash_task(task: str) -> str:
    return hashlib.sha256(task.encode()).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_session_memory(
    redis: aioredis.Redis, session_id: str
) -> Optional[SessionMemory]:
    raw = await redis.get(f"{SESSION_KEY_PREFIX}{session_id}")
    if raw is None:
        return None
    return SessionMemory.model_validate_json(raw)


async def save_session_memory(
    redis: aioredis.Redis, session_id: str, memory: SessionMemory
) -> None:
    memory.updated_at = _now_iso()
    await redis.set(
        f"{SESSION_KEY_PREFIX}{session_id}",
        memory.model_dump_json(),
        ex=settings.session_ttl_seconds,
    )


async def create_session_memory(
    redis: aioredis.Redis, session_id: str
) -> SessionMemory:
    now = _now_iso()
    memory = SessionMemory(session_id=session_id, created_at=now, updated_at=now)
    await save_session_memory(redis, session_id, memory)
    return memory


async def delete_session_memory(redis: aioredis.Redis, session_id: str) -> None:
    await redis.delete(f"{SESSION_KEY_PREFIX}{session_id}")


async def get_cached_result(
    redis: aioredis.Redis, task_hash: str
) -> Optional[dict]:
    raw = await redis.get(f"{TOOL_RESULT_KEY_PREFIX}{task_hash}")
    if raw is None:
        return None
    return json.loads(raw)


async def set_cached_result(
    redis: aioredis.Redis, task_hash: str, result: dict
) -> None:
    await redis.set(
        f"{TOOL_RESULT_KEY_PREFIX}{task_hash}",
        json.dumps(result),
        ex=TOOL_RESULT_TTL,
    )


async def set_task_status(
    redis: aioredis.Redis, task_id: str, status: dict
) -> None:
    await redis.set(f"{TASK_KEY_PREFIX}{task_id}", json.dumps(status), ex=3600)


async def get_task_status(
    redis: aioredis.Redis, task_id: str
) -> Optional[dict]:
    raw = await redis.get(f"{TASK_KEY_PREFIX}{task_id}")
    if raw is None:
        return None
    return json.loads(raw)


async def publish_progress(
    redis: aioredis.Redis, task_id: str, event: str, payload: dict
) -> None:
    message = json.dumps({"event": event, "task_id": task_id, "payload": payload})
    await redis.publish(f"{TASK_UPDATES_PREFIX}{task_id}", message)
