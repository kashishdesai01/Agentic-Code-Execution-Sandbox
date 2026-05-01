from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from backend.agent.state import GraphState, TaskPlan, ExecutionResult, ReflectorDecision
from backend.agent.prompts.reflector_prompt import REFLECTOR_SYSTEM, build_reflector_prompt
from backend.config import settings
from backend.memory import redis_store
from backend.memory.redis_store import SessionMemory, TaskHistoryEntry
from datetime import datetime, timezone

_llm = ChatAnthropic(
    model=settings.claude_model,
    api_key=settings.anthropic_api_key,
).with_structured_output(ReflectorDecision)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run_reflector(state: GraphState) -> dict:
    task = state["task"]
    task_id = state["task_id"]
    session_id = state["session_id"]
    task_plan = TaskPlan.model_validate(state["task_plan"])
    execution_result = ExecutionResult.model_validate(state["execution_result"])
    generated_code = state.get("generated_code")
    retry_count = state.get("retry_count", 0)

    messages = [
        SystemMessage(content=REFLECTOR_SYSTEM),
        HumanMessage(
            content=build_reflector_prompt(
                task, task_plan, generated_code, execution_result, retry_count
            )
        ),
    ]

    decision: ReflectorDecision = await _llm.ainvoke(messages)
    new_retry_count = retry_count + 1

    final_response: str | None = None
    redis = await redis_store.get_redis_client()

    if decision.outcome == "success":
        final_response = (
            f"Task completed successfully.\n\nOutput:\n{execution_result.stdout.strip()}"
        )
        memory = await redis_store.get_session_memory(redis, session_id)
        if memory is None:
            now = _now_iso()
            memory = SessionMemory(session_id=session_id, created_at=now, updated_at=now)

        memory.last_successful_code = generated_code
        memory.last_error = None
        memory.task_history.append(
            TaskHistoryEntry(
                task_id=task_id,
                task=task,
                outcome="success",
                final_response=final_response,
                timestamp=_now_iso(),
            )
        )
        await redis_store.save_session_memory(redis, session_id, memory)

    elif new_retry_count > settings.max_retries or decision.outcome == "hard_failure":
        final_response = (
            f"Task failed after {retry_count} attempt(s).\n\n"
            f"Reason: {decision.reasoning}\n\n"
            f"Last stderr:\n{execution_result.stderr.strip() or '(empty)'}"
        )
        memory = await redis_store.get_session_memory(redis, session_id)
        if memory:
            memory.last_error = execution_result.stderr or decision.reasoning
            memory.task_history.append(
                TaskHistoryEntry(
                    task_id=task_id,
                    task=task,
                    outcome=decision.outcome,
                    final_response=final_response,
                    timestamp=_now_iso(),
                )
            )
            await redis_store.save_session_memory(redis, session_id, memory)

    await redis_store.publish_progress(
        redis,
        task_id,
        "node_complete",
        {
            "node": "reflector",
            "outcome": decision.outcome,
            "reasoning": decision.reasoning,
            "suggested_fix": decision.suggested_fix,
            "retry_count": new_retry_count,
        },
    )

    return {
        "reflector_decision": decision.model_dump(),
        "retry_count": new_retry_count,
        "final_response": final_response,
    }


def route_after_reflector(state: GraphState) -> str:
    decision = ReflectorDecision.model_validate(state["reflector_decision"])
    retry_count = state.get("retry_count", 0)

    if decision.outcome == "success":
        return "end_success"
    if retry_count > settings.max_retries or decision.outcome == "hard_failure":
        return "end_failure"
    if decision.outcome == "retryable_failure":
        return "code_generator"
    return "end_failure"
