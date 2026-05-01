import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import redis.asyncio as aioredis

from backend.dependencies import get_redis
from backend.memory import redis_store

router = APIRouter(prefix="/session", tags=["sessions"])


class CreateSessionResponse(BaseModel):
    session_id: str


@router.post("/", response_model=CreateSessionResponse)
async def create_session(redis: aioredis.Redis = Depends(get_redis)):
    session_id = str(uuid.uuid4())
    await redis_store.create_session_memory(redis, session_id)
    return CreateSessionResponse(session_id=session_id)


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str, redis: aioredis.Redis = Depends(get_redis)
):
    memory = await redis_store.get_session_memory(redis, session_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Session not found")
    await redis_store.delete_session_memory(redis, session_id)
