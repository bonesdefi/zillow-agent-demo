"""LangGraph workflow for multi-agent coordination."""

from src.graph.workflow import create_workflow, get_workflow
from src.graph.state import AgentState

# For backward compatibility
def __getattr__(name: str):
    if name == "workflow":
        return get_workflow()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["create_workflow", "get_workflow", "AgentState"]
