import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.agent.state import TaskPlan, ExecutionResult, ReflectorDecision
from backend.agent.nodes.reflector import route_after_reflector


# ── route_after_reflector ──────────────────────────────────────────────────

def _make_state(outcome: str, retry_count: int, max_retries: int = 3) -> dict:
    decision = ReflectorDecision(outcome=outcome, reasoning="test").model_dump()
    return {
        "reflector_decision": decision,
        "retry_count": retry_count,
    }


def test_route_success():
    state = _make_state("success", retry_count=1)
    assert route_after_reflector(state) == "end_success"


def test_route_retryable_under_limit():
    state = _make_state("retryable_failure", retry_count=1)
    assert route_after_reflector(state) == "code_generator"


def test_route_hard_failure():
    state = _make_state("hard_failure", retry_count=1)
    assert route_after_reflector(state) == "end_failure"


def test_route_max_retries_exceeded():
    # retry_count > max_retries (3) should always be end_failure
    state = _make_state("retryable_failure", retry_count=4)
    assert route_after_reflector(state) == "end_failure"


def test_route_exactly_at_max_retries():
    # retry_count == max_retries + 1 (4 > 3) → end_failure
    state = _make_state("retryable_failure", retry_count=4)
    assert route_after_reflector(state) == "end_failure"


# ── code_generator strip_fences ───────────────────────────────────────────

def test_strip_fences():
    from backend.agent.nodes.code_generator import _strip_fences
    assert _strip_fences("```python\nprint(1)\n```") == "print(1)"
    assert _strip_fences("```\nprint(1)\n```") == "print(1)"
    assert _strip_fences("print(1)") == "print(1)"


# ── executor fast-path (no docker needed) ─────────────────────────────────

@pytest.mark.asyncio
async def test_executor_fast_path_no_code():
    from backend.agent.nodes.executor import run_executor

    state = {
        "task_id": "t1",
        "session_id": "s1",
        "task": "test",
        "generated_code": None,
        "error_trace": "Syntax error at line 1",
        "retry_count": 0,
    }

    result = await run_executor(state)
    er = ExecutionResult.model_validate(result["execution_result"])
    assert er.exit_code == 1
    assert "Syntax error" in er.stderr
    assert er.timed_out is False
