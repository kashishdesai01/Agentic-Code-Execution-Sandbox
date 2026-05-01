from typing import Optional, List, Literal
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
import uuid


class TaskPlan(BaseModel):
    objective: str
    inputs: List[str]
    steps: List[str]
    success_criteria: str
    expected_output_type: str  # "string", "number", "json", "list", "other"


class ExecutionResult(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    execution_time_ms: int


class ReflectorDecision(BaseModel):
    outcome: Literal["success", "retryable_failure", "hard_failure"]
    reasoning: str
    suggested_fix: Optional[str] = None


class AgentState(BaseModel):
    """Documentation model — mirrors GraphState for type safety within nodes."""
    session_id: str
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task: str
    task_plan: Optional[TaskPlan] = None
    generated_code: Optional[str] = None
    execution_result: Optional[ExecutionResult] = None
    reflector_decision: Optional[ReflectorDecision] = None
    error_trace: Optional[str] = None
    retry_count: int = 0
    memory_context: Optional[str] = None
    final_response: Optional[str] = None
    syntax_error_count: int = 0


class GraphState(TypedDict, total=False):
    """LangGraph state schema — TypedDict required by StateGraph."""
    session_id: str
    task_id: str
    task: str
    task_plan: Optional[dict]
    generated_code: Optional[str]
    execution_result: Optional[dict]
    reflector_decision: Optional[dict]
    error_trace: Optional[str]
    retry_count: int
    memory_context: Optional[str]
    final_response: Optional[str]
    syntax_error_count: int
