from typing import Optional
from backend.agent.state import TaskPlan

CODE_GEN_SYSTEM = """\
You are an expert Python 3.11 code writer for a sandboxed execution environment.

Rules:
- Output ONLY raw Python code. No markdown fences, no explanations, no prose.
- The code must print its final result to stdout using print().
- Available modules: math, json, re, collections, itertools, datetime, string, random.
- Any other import will raise ImportError at runtime — do not use them.
- Do not use open(), os, sys, subprocess, socket, or any I/O besides print().
- The code must be self-contained and terminate within 10 seconds.\
"""


def build_code_gen_prompt(
    task_plan: TaskPlan,
    memory_context: Optional[str],
    suggested_fix: Optional[str],
    retry_count: int,
) -> str:
    plan_text = (
        f"Objective: {task_plan.objective}\n"
        f"Steps:\n" + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(task_plan.steps)) + "\n"
        f"Success criteria: {task_plan.success_criteria}\n"
        f"Expected output type: {task_plan.expected_output_type}"
    )

    parts = [f"Task plan:\n{plan_text}"]

    if memory_context:
        parts.append(f"Prior session context:\n{memory_context}")

    if retry_count > 0 and suggested_fix:
        parts.append(
            f"Previous attempt failed. Suggested fix:\n{suggested_fix}\n"
            "Write corrected code that addresses this fix."
        )
    elif retry_count > 0:
        parts.append("Previous attempt failed. Write corrected code.")

    parts.append("Write the Python code now:")
    return "\n\n".join(parts)
