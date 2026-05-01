import pytest
from backend.agent.state import TaskPlan, ExecutionResult, ReflectorDecision, AgentState, GraphState


def test_task_plan_round_trip():
    plan = TaskPlan(
        objective="Test",
        inputs=["x=1"],
        steps=["step1"],
        success_criteria="prints 1",
        expected_output_type="number",
    )
    dumped = plan.model_dump()
    restored = TaskPlan.model_validate(dumped)
    assert restored.objective == "Test"
    assert restored.inputs == ["x=1"]


def test_execution_result_round_trip():
    result = ExecutionResult(
        stdout="hello\n",
        stderr="",
        exit_code=0,
        timed_out=False,
        execution_time_ms=100,
    )
    dumped = result.model_dump()
    restored = ExecutionResult.model_validate(dumped)
    assert restored.exit_code == 0
    assert not restored.timed_out


def test_reflector_decision_outcome_values():
    for outcome in ("success", "retryable_failure", "hard_failure"):
        d = ReflectorDecision(outcome=outcome, reasoning="test")
        assert d.outcome == outcome

    with pytest.raises(Exception):
        ReflectorDecision(outcome="invalid_outcome", reasoning="x")


def test_reflector_decision_optional_suggested_fix():
    d = ReflectorDecision(outcome="success", reasoning="ok")
    assert d.suggested_fix is None

    d2 = ReflectorDecision(outcome="retryable_failure", reasoning="fix it", suggested_fix="use print()")
    assert d2.suggested_fix == "use print()"


def test_agent_state_defaults():
    state = AgentState(session_id="s1", task="do something")
    assert state.retry_count == 0
    assert state.syntax_error_count == 0
    assert state.task_plan is None
    assert state.final_response is None
    assert state.task_id is not None


def test_graph_state_is_typeddict():
    # GraphState is a TypedDict — verify it can be used as a dict
    state: GraphState = {
        "session_id": "s1",
        "task_id": "t1",
        "task": "test",
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
    assert state["session_id"] == "s1"
    assert state["retry_count"] == 0
