from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from backend.agent.state import GraphState, TaskPlan
from backend.agent.prompts.planner_prompt import PLANNER_SYSTEM, build_planner_prompt
from backend.config import settings
from backend.memory import redis_store


_llm = ChatAnthropic(
    model=settings.claude_model,
    api_key=settings.anthropic_api_key,
).with_structured_output(TaskPlan)


async def run_planner(state: GraphState) -> dict:
    session_id = state["session_id"]
    task = state["task"]

    redis = await redis_store.get_redis_client()
    memory = await redis_store.get_session_memory(redis, session_id)

    memory_context: str | None = None
    if memory and (memory.last_successful_code or memory.last_error):
        parts = []
        if memory.last_successful_code:
            parts.append(f"Last successful code:\n{memory.last_successful_code}")
        if memory.last_error:
            parts.append(f"Last error:\n{memory.last_error}")
        memory_context = "\n\n".join(parts)

    messages = [
        SystemMessage(content=PLANNER_SYSTEM),
        HumanMessage(content=build_planner_prompt(task, memory_context)),
    ]

    task_plan: TaskPlan = await _llm.ainvoke(messages)

    await redis_store.publish_progress(
        redis,
        state["task_id"],
        "node_complete",
        {"node": "planner", "task_plan": task_plan.model_dump(), "retry_count": state.get("retry_count", 0)},
    )

    return {
        "task_plan": task_plan.model_dump(),
        "memory_context": memory_context,
    }
