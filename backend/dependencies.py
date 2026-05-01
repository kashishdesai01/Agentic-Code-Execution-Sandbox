from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends

from backend.memory.redis_store import get_redis_client
from backend.services.task_runner import TaskRunner

_redis: aioredis.Redis | None = None


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    global _redis
    if _redis is None:
        _redis = await get_redis_client()
    return _redis


async def get_task_runner(
    redis: aioredis.Redis = Depends(get_redis),
) -> TaskRunner:
    return TaskRunner(redis)
