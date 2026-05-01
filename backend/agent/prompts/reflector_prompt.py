from typing import Optional
from backend.agent.state import TaskPlan, ExecutionResult

REFLECTOR_SYSTEM = """\
You are a code execution evaluator. Given a task plan, generated code, and execution result, \
determine the outcome.

Outcome definitions:
- "success": The code ran without errors and stdout matches the task's success criteria.
- "retryable_failure": The code has a fixable bug — wrong logic, runtime error, wrong output \
format, or missing print(). Provide a concrete suggested_fix.
- "hard_failure": The task is fundamentally impossible given the sandbox constraints, the code \
produced the same wrong output multiple times, or a timeout/OOM occurred.

Respond with a ReflectorDecision JSON object.\
"""


def build_reflector_prompt(
    task: str,
    task_plan: TaskPlan,
    generated_code: Optional[str],
    execution_result: ExecutionResult,
    retry_count: int,
) -> str:
    code_section = generated_code or "(no code was generated — syntax error before execution)"
    return (
        f"Original task: {task}\n\n"
        f"Success criteria: {task_plan.success_criteria}\n\n"
        f"Generated code:\n```python\n{code_section}\n```\n\n"
        f"Execution result:\n"
        f"  exit_code: {execution_result.exit_code}\n"
        f"  timed_out: {execution_result.timed_out}\n"
        f"  stdout: {execution_result.stdout!r}\n"
        f"  stderr: {execution_result.stderr!r}\n\n"
        f"Retry attempt: {retry_count}\n\n"
        "Evaluate and return a ReflectorDecision."
    )
