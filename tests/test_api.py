import pytest
import json
from unittest.mock import AsyncMock, patch

from backend.memory.redis_store import SessionMemory
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.mark.asyncio
async def test_health(test_client):
    response = await test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_create_session(test_client):
    memory = SessionMemory(session_id="s1", created_at=_now(), updated_at=_now())

    with patch("backend.api.sessions.redis_store.create_session_memory", AsyncMock(return_value=memory)):
        response = await test_client.post("/api/v1/session/")
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert len(data["session_id"]) > 0


@pytest.mark.asyncio
async def test_delete_session_not_found(test_client):
    with patch("backend.api.sessions.redis_store.get_session_memory", AsyncMock(return_value=None)):
        response = await test_client.delete("/api/v1/session/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_session_success(test_client):
    memory = SessionMemory(session_id="s1", created_at=_now(), updated_at=_now())
    with patch("backend.api.sessions.redis_store.get_session_memory", AsyncMock(return_value=memory)), \
         patch("backend.api.sessions.redis_store.delete_session_memory", AsyncMock()):
        response = await test_client.delete("/api/v1/session/s1")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_submit_task_session_not_found(test_client):
    with patch("backend.api.tasks.redis_store.get_session_memory", AsyncMock(return_value=None)):
        response = await test_client.post(
            "/api/v1/session/bad-session/run",
            json={"task": "do something"},
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_submit_task_returns_task_id(test_client):
    memory = SessionMemory(session_id="s1", created_at=_now(), updated_at=_now())
    with patch("backend.api.tasks.redis_store.get_session_memory", AsyncMock(return_value=memory)), \
         patch("backend.services.task_runner.TaskRunner.submit_task", AsyncMock(return_value="task-123")):
        response = await test_client.post(
            "/api/v1/session/s1/run",
            json={"task": "compute something"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["session_id"] == "s1"


@pytest.mark.asyncio
async def test_get_history_not_found(test_client):
    with patch("backend.api.tasks.redis_store.get_session_memory", AsyncMock(return_value=None)):
        response = await test_client.get("/api/v1/session/bad/history")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_history_empty(test_client):
    memory = SessionMemory(session_id="s1", created_at=_now(), updated_at=_now())
    with patch("backend.api.tasks.redis_store.get_session_memory", AsyncMock(return_value=memory)):
        response = await test_client.get("/api/v1/session/s1/history")
    assert response.status_code == 200
    data = response.json()
    assert data["task_history"] == []
    assert data["session_id"] == "s1"
