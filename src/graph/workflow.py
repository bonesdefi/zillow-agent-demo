"""LangGraph workflow for multi-agent coordination."""

import logging
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from src.graph.state import AgentState
from src.agents.search_agent import get_search_agent
from src.agents.analysis_agent import get_analysis_agent
from src.agents.advisor_agent import get_advisor_agent
from src.agents.base_agent import AgentState as BaseAgentState


logger = logging.getLogger(__name__)


def _convert_to_base_state(state: AgentState) -> BaseAgentState:
    """Convert LangGraph state to BaseAgentState."""
    return BaseAgentState(
        user_input=state.get("user_input", ""),
        conversation_history=state.get("conversation_history", []),
        search_criteria=state.get("search_criteria"),
        properties=state.get("properties", []),
        analyses=state.get("analyses", {}),
        recommendations=state.get("recommendations", []),
        final_response=state.get("final_response", ""),
        errors=state.get("errors", []),
        needs_clarification=state.get("needs_clarification", False),
        clarification_question=state.get("clarification_question"),
    )


def _convert_from_base_state(
    base_state: BaseAgentState, original_state: AgentState
) -> AgentState:
    """Convert BaseAgentState back to LangGraph state."""
    return {
        **original_state,
        "user_input": base_state.user_input,
        "conversation_history": base_state.conversation_history,
        "search_criteria": base_state.search_criteria,
        "properties": base_state.properties,
        "analyses": base_state.analyses,
        "recommendations": base_state.recommendations,
        "final_response": base_state.final_response,
        "errors": base_state.errors,
        "needs_clarification": base_state.needs_clarification,
        "clarification_question": base_state.clarification_question,
        "current_step": "completed",
    }


async def understand_intent_node(state: AgentState) -> AgentState:
    """
    Parse user input and extract search criteria.

    This node uses the SearchAgent to understand user intent.
    """
    logger.info("Workflow: Understanding user intent")

    base_state = _convert_to_base_state(state)
    search_agent = get_search_agent()
    result = await search_agent.process(base_state)
    return _convert_from_base_state(result, state)


async def search_properties_node(state: AgentState) -> AgentState:
    """
    Search for properties using extracted criteria.

    This node is actually handled by SearchAgent in understand_intent_node,
    but we keep it for clarity in the workflow graph.
    """
    logger.info("Workflow: Searching properties")
    # Properties are already set by SearchAgent
    return state


async def analyze_properties_node(state: AgentState) -> AgentState:
    """
    Analyze found properties using market data.

    This node uses the AnalysisAgent to gather detailed information.
    """
    logger.info("Workflow: Analyzing properties")

    base_state = _convert_to_base_state(state)
    analysis_agent = get_analysis_agent()
    result = await analysis_agent.process(base_state)
    return _convert_from_base_state(result, state)


async def generate_recommendations_node(state: AgentState) -> AgentState:
    """
    Generate recommendations and final response.

    This node uses the AdvisorAgent to synthesize information.
    """
    logger.info("Workflow: Generating recommendations")

    base_state = _convert_to_base_state(state)
    advisor_agent = get_advisor_agent()
    result = await advisor_agent.process(base_state)
    return _convert_from_base_state(result, state)


async def handle_clarification_node(state: AgentState) -> AgentState:
    """
    Handle clarification request.

    This node prepares the state for user clarification.
    """
    logger.info("Workflow: Handling clarification request")
    state["current_step"] = "clarification"
    return state


def route_after_intent(state: AgentState) -> Literal["search", "clarify"]:
    """
    Route after understanding user intent.

    Returns:
        "search" if criteria is clear, "clarify" if clarification needed
    """
    if state.get("needs_clarification", False):
        return "clarify"
    return "search"


def route_after_search(state: AgentState) -> Literal["analyze", "end"]:
    """
    Route after property search.

    Returns:
        "analyze" if properties found, "end" if no results
    """
    properties = state.get("properties", [])
    if len(properties) == 0:
        logger.info("Workflow: No properties found, ending")
        state["final_response"] = (
            "I couldn't find any properties matching your criteria. "
            "Please try adjusting your search parameters."
        )
        return "end"
    return "analyze"


def create_workflow() -> StateGraph:
    """
    Create the LangGraph workflow for multi-agent coordination.

    Returns:
        Compiled StateGraph ready to execute
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("understand_intent", understand_intent_node)
    workflow.add_node("search_properties", search_properties_node)
    workflow.add_node("analyze_properties", analyze_properties_node)
    workflow.add_node("generate_recommendations", generate_recommendations_node)
    workflow.add_node("handle_clarification", handle_clarification_node)

    # Set entry point
    workflow.set_entry_point("understand_intent")

    # Add conditional edges
    workflow.add_conditional_edges(
        "understand_intent",
        route_after_intent,
        {
            "search": "search_properties",
            "clarify": "handle_clarification",
        },
    )

    workflow.add_conditional_edges(
        "search_properties",
        route_after_search,
        {
            "analyze": "analyze_properties",
            "end": END,
        },
    )

    # Add sequential edges
    workflow.add_edge("analyze_properties", "generate_recommendations")
    workflow.add_edge("generate_recommendations", END)
    workflow.add_edge("handle_clarification", END)

    return workflow.compile()


# Lazy workflow instance (created on first access)
_workflow_instance = None


def get_workflow():
    """Get or create the workflow instance."""
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = create_workflow()
    return _workflow_instance


# For backward compatibility
workflow = None  # Will be set via __getattr__


def __getattr__(name: str):
    if name == "workflow":
        return get_workflow()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

