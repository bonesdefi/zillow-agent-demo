"""LangGraph workflow for multi-agent coordination."""

import logging
from typing import Literal
from dotenv import load_dotenv

# Load .env file to ensure environment variables are available
load_dotenv()

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
    try:
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
    except Exception as e:
        logger.error(f"Error converting to base state: {e}", exc_info=True)
        # Return minimal valid state
        return BaseAgentState(
            user_input=state.get("user_input", ""),
            conversation_history=state.get("conversation_history", []),
            search_criteria=None,
            properties=[],
            analyses={},
            recommendations=[],
            final_response="",
            errors=[f"State conversion error: {str(e)}"],
            needs_clarification=False,
            clarification_question=None,
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
    
    try:
        base_state = _convert_to_base_state(state)
        logger.info(f"Converted state - user_input: {base_state.user_input[:50] if base_state.user_input else 'None'}")
        
        search_agent = get_search_agent()
        logger.info("Calling SearchAgent.process()")
        result = await search_agent.process(base_state)
        logger.info(f"SearchAgent returned - properties: {len(result.properties)}, criteria: {result.search_criteria is not None}")
        
        updated_state = _convert_from_base_state(result, state)
        logger.info(f"Updated state - properties: {len(updated_state.get('properties', []))}, criteria: {updated_state.get('search_criteria') is not None}")
        return updated_state
    except Exception as e:
        logger.error(f"Error in understand_intent_node: {e}", exc_info=True)
        state["errors"] = state.get("errors", []) + [f"SearchAgent error: {str(e)}"]
        state["final_response"] = f"I encountered an error while processing your request: {str(e)}"
        return state


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
    
    try:
        base_state = _convert_to_base_state(state)
        logger.info(f"Analyzing {len(base_state.properties)} properties")
        
        analysis_agent = get_analysis_agent()
        result = await analysis_agent.process(base_state)
        logger.info(f"AnalysisAgent returned - analyses: {len(result.analyses)}")
        
        return _convert_from_base_state(result, state)
    except Exception as e:
        logger.error(f"Error in analyze_properties_node: {e}", exc_info=True)
        state["errors"] = state.get("errors", []) + [f"AnalysisAgent error: {str(e)}"]
        # Continue with existing state even if analysis fails
        return state


async def generate_recommendations_node(state: AgentState) -> AgentState:
    """
    Generate recommendations and final response.

    This node uses the AdvisorAgent to synthesize information.
    """
    logger.info("Workflow: Generating recommendations")
    
    try:
        base_state = _convert_to_base_state(state)
        logger.info(f"Generating recommendations for {len(base_state.properties)} properties")
        
        advisor_agent = get_advisor_agent()
        result = await advisor_agent.process(base_state)
        logger.info(f"AdvisorAgent returned - response length: {len(result.final_response)}, recommendations: {len(result.recommendations)}")
        
        updated_state = _convert_from_base_state(result, state)
        logger.info(f"Final state - final_response: {updated_state.get('final_response', '')[:100]}")
        return updated_state
    except Exception as e:
        logger.error(f"Error in generate_recommendations_node: {e}", exc_info=True)
        state["errors"] = state.get("errors", []) + [f"AdvisorAgent error: {str(e)}"]
        # Provide fallback response
        if not state.get("final_response"):
            state["final_response"] = (
                f"I found {len(state.get('properties', []))} properties, but encountered an error generating recommendations: {str(e)}"
            )
        return state


async def handle_clarification_node(state: AgentState) -> AgentState:
    """
    Handle clarification request.

    This node prepares the state for user clarification.
    """
    logger.info("Workflow: Handling clarification request")
    
    # Ensure clarification question is set
    clarification = state.get("clarification_question")
    if not clarification:
        clarification = "I need more information to help you. Could you please provide more details about what you're looking for?"
        state["clarification_question"] = clarification
    
    # Set final response to clarification question
    if not state.get("final_response"):
        state["final_response"] = clarification
    
    state["current_step"] = "clarification"
    logger.info(f"Clarification node - question: {clarification[:100]}")
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
    logger.info(f"Routing after search - properties found: {len(properties)}")
    
    if len(properties) == 0:
        logger.info("Workflow: No properties found, ending")
        # Only set final_response if it's not already set
        if not state.get("final_response"):
            state["final_response"] = (
                "I couldn't find any properties matching your criteria. "
                "Please try adjusting your search parameters."
            )
        return "end"
    
    logger.info(f"Routing to analyze - {len(properties)} properties to analyze")
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

