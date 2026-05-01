"""
Integration tests for the full LangGraph graph with mocked LLM calls and executor.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.agent.state import TaskPlan, ExecutionResult, ReflectorDecision, GraphState


def _make_initial_state() -> GraphState:
    return {
        "session_id": "s1",
        "task_id": "t1",
        "task": "Print the sum of 1 to 10",
        "task_plan": None,
        "generated_code": None,
        "execution_result": None,
        "reflector_decision": None,
        "error_trace": None,
        "retry_count": 0,
        "memory_context": None,
        "final_response": None,
        "syntax_error_count": 0,
    }


@pytest.mark.asyncio
async def test_graph_success_path():
    """Full graph run with mocked LLM/executor — success on first attempt."""
    plan = TaskPlan(
        objective="Sum 1 to 10",
        inputs=[],
        steps=["Compute sum", "Print result"],
        success_criteria="stdout is '55'",
        expected_output_type="number",
    )
    exec_result = ExecutionResult(stdout="55\n", stderr="", exit_code=0, timed_out=False, execution_time_ms=50)
    decision = ReflectorDecision(outcome="success", reasoning="Correct output")

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.publish = AsyncMock(return_value=1)

    with patch("backend.memory.redis_store._redis_client", mock_redis), \
         patch("backend.agent.nodes.planner._llm") as mock_planner_llm, \
         patch("backend.agent.nodes.code_generator._llm") as mock_codegen_llm, \
         patch("backend.agent.nodes.reflector._llm") as mock_reflector_llm, \
         patch("backend.agent.nodes.executor.asyncio.create_subprocess_exec") as mock_proc:

        mock_planner_llm.ainvoke = AsyncMock(return_value=plan)
        mock_codegen_llm.ainvoke = AsyncMock(return_value=MagicMock(content="print(sum(range(1,11)))"))
        mock_reflector_llm.ainvoke = AsyncMock(return_value=decision)

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"55\n", b""))
        mock_process.returncode = 0
        mock_proc.return_value = mock_process

        from backend.agent.graph import agent_graph
        final_state = await agent_graph.ainvoke(_make_initial_state())

    assert final_state["final_response"] is not None
    assert "55" in final_state["final_response"]
    assert final_state["retry_count"] == 1


@pytest.mark.asyncio
async def test_graph_retry_then_success():
    """Graph retries once after a retryable_failure, then succeeds."""
    plan = TaskPlan(
        objective="Sum 1 to 10",
        inputs=[],
        steps=["step1"],
        success_criteria="stdout is '55'",
        expected_output_type="number",
    )
    fail_decision = ReflectorDecision(
        outcome="retryable_failure",
        reasoning="Wrong output",
        suggested_fix="Use sum(range(1,11))",
    )
    success_decision = ReflectorDecision(outcome="success", reasoning="Correct")

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.publish = AsyncMock(return_value=1)

    call_count = {"reflector": 0}

    async def mock_reflector(*args, **kwargs):
        call_count["reflector"] += 1
        return fail_decision if call_count["reflector"] == 1 else success_decision

    with patch("backend.memory.redis_store._redis_client", mock_redis), \
         patch("backend.agent.nodes.planner._llm") as mock_planner_llm, \
         patch("backend.agent.nodes.code_generator._llm") as mock_codegen_llm, \
         patch("backend.agent.nodes.reflector._llm") as mock_reflector_llm, \
         patch("backend.agent.nodes.executor.asyncio.create_subprocess_exec") as mock_proc:

        mock_planner_llm.ainvoke = AsyncMock(return_value=plan)
        mock_codegen_llm.ainvoke = AsyncMock(return_value=MagicMock(content="print(55)"))
        mock_reflector_llm.ainvoke = mock_reflector

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"55\n", b""))
        mock_process.returncode = 0
        mock_proc.return_value = mock_process

        from backend.agent.graph import agent_graph
        final_state = await agent_graph.ainvoke(_make_initial_state())

    assert call_count["reflector"] == 2
    assert final_state["retry_count"] == 2
    assert final_state["final_response"] is not None
