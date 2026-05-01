from langgraph.graph import StateGraph, END

from backend.agent.state import GraphState
from backend.agent.nodes.planner import run_planner
from backend.agent.nodes.code_generator import run_code_generator
from backend.agent.nodes.executor import run_executor
from backend.agent.nodes.reflector import run_reflector, route_after_reflector


def build_graph():
    builder = StateGraph(GraphState)

    builder.add_node("planner", run_planner)
    builder.add_node("code_generator", run_code_generator)
    builder.add_node("executor", run_executor)
    builder.add_node("reflector", run_reflector)

    builder.set_entry_point("planner")
    builder.add_edge("planner", "code_generator")
    builder.add_edge("code_generator", "executor")
    builder.add_edge("executor", "reflector")

    builder.add_conditional_edges(
        "reflector",
        route_after_reflector,
        {
            "code_generator": "code_generator",
            "end_success": END,
            "end_failure": END,
        },
    )

    return builder.compile()


agent_graph = build_graph()
