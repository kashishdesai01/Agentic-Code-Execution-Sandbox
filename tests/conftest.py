import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from backend.agent.state import TaskPlan, ExecutionResult, ReflectorDecision


@pytest.fixture
def sample_task_plan() -> TaskPlan:
    return TaskPlan(
        objective="Compute the sum of 1 to 10",
        inputs=[],
        steps=["Use a loop or sum() to add integers 1 through 10", "Print the result"],
        success_criteria="stdout contains '55'",
        expected_output_type="number",
    )


@pytest.fixture
def sample_execution_result_success() -> ExecutionResult:
    return ExecutionResult(
        stdout="55\n",
        stderr="",
        exit_code=0,
        timed_out=False,
        execution_time_ms=120,
    )


@pytest.fixture
def sample_execution_result_failure() -> ExecutionResult:
    return ExecutionResult(
        stdout="",
        stderr="NameError: name 'x' is not defined",
        exit_code=1,
        timed_out=False,
        execution_time_ms=80,
    )


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.publish = AsyncMock(return_value=1)
    redis.ping = AsyncMock(return_value=True)
    return redis


@pytest_asyncio.fixture
async def test_client(mock_redis):
    with patch("backend.memory.redis_store.get_redis_client", return_value=AsyncMock(return_value=mock_redis)):
        with patch("backend.dependencies.get_redis", return_value=mock_redis):
            from backend.main import app
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                yield client
