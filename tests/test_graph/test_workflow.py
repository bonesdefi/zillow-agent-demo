"""Tests for LangGraph workflow."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os

from src.graph.workflow import (
    create_workflow,
    get_workflow,
    understand_intent_node,
    analyze_properties_node,
    generate_recommendations_node,
    route_after_intent,
    route_after_search,
)
from src.graph.state import AgentState


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}):
        yield


@pytest.fixture
def mock_agents(mock_env):
    """Mock all agents."""
    with patch("src.graph.workflow.get_search_agent") as mock_get_search, patch(
        "src.graph.workflow.get_analysis_agent"
    ) as mock_get_analysis, patch(
        "src.graph.workflow.get_advisor_agent"
    ) as mock_get_advisor:

        # Create mock agent instances
        mock_search_agent = MagicMock()
        mock_search_agent.process = AsyncMock()
        mock_get_search.return_value = mock_search_agent

        mock_analysis_agent = MagicMock()
        mock_analysis_agent.process = AsyncMock()
        mock_get_analysis.return_value = mock_analysis_agent

        mock_advisor_agent = MagicMock()
        mock_advisor_agent.process = AsyncMock()
        mock_get_advisor.return_value = mock_advisor_agent

        yield {
            "search": mock_search_agent,
            "analysis": mock_analysis_agent,
            "advisor": mock_advisor_agent,
        }


@pytest.mark.asyncio
async def test_workflow_creation(mock_env):
    """Test workflow can be created."""
    wf = create_workflow()
    assert wf is not None


@pytest.mark.asyncio
async def test_route_after_intent_clear_criteria(mock_env):
    """Test routing when criteria is clear."""
    state: AgentState = {
        "messages": [],
        "user_input": "test",
        "search_criteria": {"location": "Austin, TX"},
        "properties": [],
        "analyses": {},
        "recommendations": [],
        "final_response": "",
        "current_step": "start",
        "needs_clarification": False,
        "clarification_question": None,
        "errors": [],
        "user_preferences": None,
        "conversation_history": [],
    }

    result = route_after_intent(state)
    assert result == "search"


@pytest.mark.asyncio
async def test_route_after_intent_needs_clarification(mock_env):
    """Test routing when clarification needed."""
    state: AgentState = {
        "messages": [],
        "user_input": "test",
        "search_criteria": None,
        "properties": [],
        "analyses": {},
        "recommendations": [],
        "final_response": "",
        "current_step": "start",
        "needs_clarification": True,
        "clarification_question": "What location?",
        "errors": [],
        "user_preferences": None,
        "conversation_history": [],
    }

    result = route_after_intent(state)
    assert result == "clarify"


@pytest.mark.asyncio
async def test_route_after_search_with_properties(mock_env):
    """Test routing when properties found."""
    state: AgentState = {
        "messages": [],
        "user_input": "test",
        "search_criteria": {},
        "properties": [{"id": "1", "address": "123 Main"}],
        "analyses": {},
        "recommendations": [],
        "final_response": "",
        "current_step": "search",
        "needs_clarification": False,
        "clarification_question": None,
        "errors": [],
        "user_preferences": None,
        "conversation_history": [],
    }

    result = route_after_search(state)
    assert result == "analyze"


@pytest.mark.asyncio
async def test_route_after_search_no_properties(mock_env):
    """Test routing when no properties found."""
    state: AgentState = {
        "messages": [],
        "user_input": "test",
        "search_criteria": {},
        "properties": [],
        "analyses": {},
        "recommendations": [],
        "final_response": "",
        "current_step": "search",
        "needs_clarification": False,
        "clarification_question": None,
        "errors": [],
        "user_preferences": None,
        "conversation_history": [],
    }

    result = route_after_search(state)
    assert result == "end"
    assert "couldn't find" in state["final_response"].lower()


@pytest.mark.asyncio
async def test_understand_intent_node(mock_agents):
    """Test understand intent node."""
    # Mock search agent response
    from src.agents.base_agent import AgentState as BaseAgentState

    mock_result = BaseAgentState(
        user_input="Find houses in Austin",
        search_criteria={"location": "Austin, TX", "bedrooms": 3},
        properties=[{"id": "1", "address": "123 Main"}],
        needs_clarification=False,
    )

    mock_agents["search"].process.return_value = mock_result

    state: AgentState = {
        "messages": [],
        "user_input": "Find houses in Austin",
        "search_criteria": None,
        "properties": [],
        "analyses": {},
        "recommendations": [],
        "final_response": "",
        "current_step": "start",
        "needs_clarification": False,
        "clarification_question": None,
        "errors": [],
        "user_preferences": None,
        "conversation_history": [],
    }

    result = await understand_intent_node(state)

    assert result["search_criteria"] is not None
    assert len(result["properties"]) > 0
    assert result["needs_clarification"] is False


@pytest.mark.asyncio
async def test_analyze_properties_node(mock_agents):
    """Test analyze properties node."""
    from src.agents.base_agent import AgentState as BaseAgentState

    mock_result = BaseAgentState(
        user_input="test",
        properties=[{"id": "1"}],
        analyses={"1": {"neighborhood": {}, "schools": []}},
    )

    mock_agents["analysis"].process.return_value = mock_result

    state: AgentState = {
        "messages": [],
        "user_input": "test",
        "search_criteria": {},
        "properties": [{"id": "1", "address": "123 Main"}],
        "analyses": {},
        "recommendations": [],
        "final_response": "",
        "current_step": "analyze",
        "needs_clarification": False,
        "clarification_question": None,
        "errors": [],
        "user_preferences": None,
        "conversation_history": [],
    }

    result = await analyze_properties_node(state)

    assert len(result["analyses"]) > 0
    assert "1" in result["analyses"]


@pytest.mark.asyncio
async def test_generate_recommendations_node(mock_agents):
    """Test generate recommendations node."""
    from src.agents.base_agent import AgentState as BaseAgentState

    mock_result = BaseAgentState(
        user_input="test",
        properties=[{"id": "1"}],
        analyses={"1": {}},
        recommendations=[{"property_id": "1", "score": 85}],
        final_response="Here are my recommendations...",
    )

    mock_agents["advisor"].process.return_value = mock_result

    state: AgentState = {
        "messages": [],
        "user_input": "test",
        "search_criteria": {},
        "properties": [{"id": "1"}],
        "analyses": {"1": {}},
        "recommendations": [],
        "final_response": "",
        "current_step": "recommend",
        "needs_clarification": False,
        "clarification_question": None,
        "errors": [],
        "user_preferences": None,
        "conversation_history": [],
    }

    result = await generate_recommendations_node(state)

    assert len(result["recommendations"]) > 0
    assert len(result["final_response"]) > 0


@pytest.mark.asyncio
async def test_workflow_happy_path(mock_agents):
    """Test complete workflow with clear user intent."""
    from src.agents.base_agent import AgentState as BaseAgentState

    # Mock search agent
    mock_search_result = BaseAgentState(
        user_input="Find 3 bed house in Austin under 600k",
        search_criteria={"location": "Austin, TX", "bedrooms": 3, "max_price": 600000},
        properties=[{"id": "1", "address": "123 Main", "price": 500000}],
        needs_clarification=False,
    )
    mock_agents["search"].process.return_value = mock_search_result

    # Mock analysis agent - preserve properties from search
    mock_analysis_result = BaseAgentState(
        user_input="Find 3 bed house in Austin under 600k",
        search_criteria={"location": "Austin, TX", "bedrooms": 3, "max_price": 600000},
        properties=[{"id": "1", "address": "123 Main", "price": 500000}],
        analyses={"1": {"neighborhood": {}, "schools": []}},
        needs_clarification=False,
    )
    mock_agents["analysis"].process.return_value = mock_analysis_result

    # Mock advisor agent - preserve all previous state
    mock_advisor_result = BaseAgentState(
        user_input="Find 3 bed house in Austin under 600k",
        search_criteria={"location": "Austin, TX", "bedrooms": 3, "max_price": 600000},
        properties=[{"id": "1", "address": "123 Main", "price": 500000}],
        analyses={"1": {"neighborhood": {}, "schools": []}},
        recommendations=[{"property_id": "1", "score": 85}],
        final_response="I found a great property for you!",
        needs_clarification=False,
    )
    mock_agents["advisor"].process.return_value = mock_advisor_result

    initial_state: AgentState = {
        "messages": [],
        "user_input": "Find 3 bed house in Austin under 600k",
        "search_criteria": None,
        "properties": [],
        "analyses": {},
        "recommendations": [],
        "final_response": "",
        "current_step": "start",
        "needs_clarification": False,
        "clarification_question": None,
        "errors": [],
        "user_preferences": None,
        "conversation_history": [],
    }

    # Create workflow fresh for this test
    wf = create_workflow()
    result = await wf.ainvoke(initial_state)

    assert result["search_criteria"] is not None
    assert len(result["properties"]) > 0
    assert len(result["analyses"]) > 0
    assert len(result["recommendations"]) > 0
    assert len(result["final_response"]) > 0
    assert result["current_step"] == "completed"

