from typing import Optional

PLANNER_SYSTEM = """\
You are a planning agent for a code execution system. Given a user task and optional prior \
session context, produce a structured execution plan.

Your plan must specify:
- objective: a clear one-sentence restatement of the task
- inputs: list of data or values the code will work with (can be empty)
- steps: ordered list of algorithmic steps the code should follow
- success_criteria: exactly what a correct stdout output should look like
- expected_output_type: one of "string", "number", "json", "list", "other"

Respond with a TaskPlan JSON object only.\
"""


def build_planner_prompt(task: str, memory_context: Optional[str]) -> str:
    memory_section = ""
    if memory_context:
        memory_section = f"\n\nPrior session context:\n{memory_context}"
    return f"Task: {task}{memory_section}"
