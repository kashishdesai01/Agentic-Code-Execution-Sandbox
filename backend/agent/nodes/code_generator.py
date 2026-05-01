import ast
import re
from typing import Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from backend.agent.state import GraphState, TaskPlan, ReflectorDecision
from backend.agent.prompts.code_generator_prompt import CODE_GEN_SYSTEM, build_code_gen_prompt
from backend.config import settings
from backend.memory import redis_store

_llm = ChatAnthropic(
    model=settings.claude_model,
    api_key=settings.anthropic_api_key,
)

_FENCE_RE = re.compile(r"^```(?:python)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)


def _strip_fences(text: str) -> str:
    m = _FENCE_RE.match(text.strip())
    return m.group(1).strip() if m else text.strip()


async def _generate(
    task_plan: TaskPlan,
    memory_context: Optional[str],
    suggested_fix: Optional[str],
    retry_count: int,
    extra_context: Optional[str] = None,
) -> str:
    prompt = build_code_gen_prompt(task_plan, memory_context, suggested_fix, retry_count)
    if extra_context:
        prompt = f"{extra_context}\n\n{prompt}"

    messages = [
        SystemMessage(content=CODE_GEN_SYSTEM),
        HumanMessage(content=prompt),
    ]
    response = await _llm.ainvoke(messages)
    return _strip_fences(response.content)


async def run_code_generator(state: GraphState) -> dict:
    task_plan = TaskPlan.model_validate(state["task_plan"])
    memory_context = state.get("memory_context")
    retry_count = state.get("retry_count", 0)
    syntax_error_count = state.get("syntax_error_count", 0)

    # On reflector-driven retry, use its suggested_fix
    suggested_fix: Optional[str] = None
    if retry_count > 0 and state.get("reflector_decision"):
        decision = ReflectorDecision.model_validate(state["reflector_decision"])
        suggested_fix = decision.suggested_fix

    code = await _generate(task_plan, memory_context, suggested_fix, retry_count)

    # Validate syntax — one internal retry allowed
    try:
        ast.parse(code)
    except SyntaxError as e:
        if syntax_error_count == 0:
            fix_context = f"Previous code had a syntax error: {e}\nFix it."
            code = await _generate(task_plan, memory_context, suggested_fix, retry_count, fix_context)
            try:
                ast.parse(code)
            except SyntaxError as e2:
                error_msg = f"Syntax error after two attempts: {e2}"
                return {
                    "generated_code": None,
                    "error_trace": error_msg,
                    "syntax_error_count": 2,
                }
            return {
                "generated_code": code,
                "error_trace": None,
                "syntax_error_count": 1,
            }
        else:
            return {
                "generated_code": None,
                "error_trace": f"Syntax error: {e}",
                "syntax_error_count": syntax_error_count + 1,
            }

    redis = await redis_store.get_redis_client()
    await redis_store.publish_progress(
        redis,
        state["task_id"],
        "node_complete",
        {
            "node": "code_generator",
            "code": code,
            "retry_count": retry_count,
        },
    )

    return {
        "generated_code": code,
        "error_trace": None,
        "syntax_error_count": 0,
    }
