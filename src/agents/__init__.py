"""AI agents for real estate assistance."""

from src.agents.base_agent import (
    BaseAgent,
    AgentState,
    AgentError,
    AgentLLMError,
    AgentMCPError,
)
from src.agents.search_agent import SearchAgent, get_search_agent
from src.agents.analysis_agent import AnalysisAgent, get_analysis_agent
from src.agents.advisor_agent import AdvisorAgent, get_advisor_agent

# Lazy singletons (for backward compatibility)
def __getattr__(name: str):
    if name == "search_agent":
        return get_search_agent()
    elif name == "analysis_agent":
        return get_analysis_agent()
    elif name == "advisor_agent":
        return get_advisor_agent()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "BaseAgent",
    "AgentState",
    "AgentError",
    "AgentLLMError",
    "AgentMCPError",
    "SearchAgent",
    "get_search_agent",
    "AnalysisAgent",
    "get_analysis_agent",
    "AdvisorAgent",
    "get_advisor_agent",
]

