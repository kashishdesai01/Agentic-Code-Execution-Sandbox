"""
Integration tests for the executor node. Requires Docker to be running
and the sandbox-image to be built. Skipped otherwise.
"""
import pytest
import subprocess
import shutil

from backend.agent.state import ExecutionResult
from backend.agent.nodes.executor import run_executor


def docker_available() -> bool:
    return shutil.which("docker") is not None


def sandbox_image_exists() -> bool:
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", "sandbox-image"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


skip_no_docker = pytest.mark.skipif(
    not docker_available() or not sandbox_image_exists(),
    reason="Docker or sandbox-image not available",
)


def _make_state(code: str, task_id: str = "test-task-1") -> dict:
    return {
        "task_id": task_id,
        "session_id": "s1",
        "task": "test",
        "generated_code": code,
        "error_trace": None,
        "retry_count": 0,
    }


@skip_no_docker
@pytest.mark.asyncio
async def test_executor_simple_print():
    state = _make_state("print('hello world')")
    result = await run_executor(state)
    er = ExecutionResult.model_validate(result["execution_result"])
    assert er.exit_code == 0
    assert "hello world" in er.stdout
    assert er.timed_out is False


@skip_no_docker
@pytest.mark.asyncio
async def test_executor_math_import():
    state = _make_state("import math\nprint(math.pi)")
    result = await run_executor(state)
    er = ExecutionResult.model_validate(result["execution_result"])
    assert er.exit_code == 0
    assert "3.14" in er.stdout


@skip_no_docker
@pytest.mark.asyncio
async def test_executor_blocked_import():
    state = _make_state("import requests\nprint('ok')")
    result = await run_executor(state)
    er = ExecutionResult.model_validate(result["execution_result"])
    assert er.exit_code != 0
    assert "blocked by sandbox policy" in er.stderr or "ImportError" in er.stderr


@skip_no_docker
@pytest.mark.asyncio
async def test_executor_timeout():
    state = _make_state("while True: pass", task_id="test-timeout")
    result = await run_executor(state)
    er = ExecutionResult.model_validate(result["execution_result"])
    assert er.timed_out is True
    assert er.exit_code == -1


@skip_no_docker
@pytest.mark.asyncio
async def test_executor_runtime_error():
    state = _make_state("print(1/0)")
    result = await run_executor(state)
    er = ExecutionResult.model_validate(result["execution_result"])
    assert er.exit_code != 0
    assert "ZeroDivisionError" in er.stderr
