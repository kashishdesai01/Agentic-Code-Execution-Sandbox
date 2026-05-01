from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

import redis.asyncio as aioredis

from backend.dependencies import get_redis, get_task_runner
from backend.memory import redis_store
from backend.services.task_runner import TaskRunner

router = APIRouter(prefix="/session/{session_id}", tags=["tasks"])


class SubmitTaskRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=4000)


class SubmitTaskResponse(BaseModel):
    task_id: str
    session_id: str


class HistoryEntry(BaseModel):
    task_id: str
    task: str
    outcome: str
    final_response: Optional[str]
    timestamp: str


class HistoryResponse(BaseModel):
    session_id: str
    task_history: List[HistoryEntry]


@router.post("/run", response_model=SubmitTaskResponse)
async def submit_task(
    session_id: str,
    body: SubmitTaskRequest,
    redis: aioredis.Redis = Depends(get_redis),
    runner: TaskRunner = Depends(get_task_runner),
):
    memory = await redis_store.get_session_memory(redis, session_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Session not found")

    task_id = await runner.submit_task(session_id, body.task)
    return SubmitTaskResponse(task_id=task_id, session_id=session_id)


@router.get("/result/{task_id}")
async def stream_result(
    session_id: str,
    task_id: str,
    runner: TaskRunner = Depends(get_task_runner),
):
    return EventSourceResponse(runner.stream_task_events(task_id))


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    session_id: str,
    redis: aioredis.Redis = Depends(get_redis),
):
    memory = await redis_store.get_session_memory(redis, session_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return HistoryResponse(
        session_id=session_id,
        task_history=[
            HistoryEntry(**entry.model_dump()) for entry in memory.task_history
        ],
    )
