"""LangGraph state definition for multi-agent workflow."""

from typing import TypedDict, List, Optional, Dict, Any, Annotated
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    State for the multi-agent real estate assistant.

    This state is passed between agents in the LangGraph workflow.
    """

    # User interaction
    messages: Annotated[List[Dict[str, str]], add_messages]
    user_input: str

    # Search phase
    search_criteria: Optional[Dict[str, Any]]
    properties: List[Dict[str, Any]]

    # Analysis phase
    analyses: Dict[str, Dict[str, Any]]  # property_id -> analysis

    # Recommendation phase
    recommendations: List[Dict[str, Any]]
    final_response: str

    # Flow control
    current_step: str
    needs_clarification: bool
    clarification_question: Optional[str]

    # Error handling
    errors: List[str]

    # Context
    user_preferences: Optional[Dict[str, Any]]
    conversation_history: List[Dict[str, str]]

