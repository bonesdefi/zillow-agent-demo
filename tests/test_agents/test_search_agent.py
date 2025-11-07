"""Tests for search agent."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os

from src.agents.search_agent import SearchAgent, get_search_agent
from src.agents.base_agent import AgentState


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}):
        yield


@pytest.fixture
def mock_llm(mock_env):
    """Mock LLM calls."""
    with patch.object(SearchAgent, "_call_llm") as mock:
        yield mock


@pytest.fixture
def mock_mcp_search(mock_env):
    """Mock MCP server search."""
    with patch("src.agents.search_agent.search_properties") as mock:
        yield mock


@pytest.mark.asyncio
async def test_search_agent_initialization(mock_env):
    """Test search agent initializes correctly."""
    agent = SearchAgent()
    assert agent.name == "SearchAgent"


@pytest.mark.asyncio
async def test_extract_criteria_clear_query(mock_llm):
    """Test extraction of clear search criteria."""
    agent = SearchAgent()

    # Mock LLM response
    mock_llm.return_value = """
    {
        "location": "Austin, TX",
        "max_price": 600000,
        "bedrooms": 3,
        "property_type": "house",
        "confidence": "high"
    }
    """

    criteria = await agent._extract_search_criteria("Find me a 3 bedroom house in Austin under 600k")

    assert criteria["location"] == "Austin, TX"
    assert criteria["max_price"] == 600000
    assert criteria["bedrooms"] == 3
    assert criteria["confidence"] == "high"


@pytest.mark.asyncio
async def test_extract_criteria_vague_query(mock_llm):
    """Test extraction of vague search criteria."""
    agent = SearchAgent()

    mock_llm.return_value = '{"confidence": "low"}'

    criteria = await agent._extract_search_criteria("Something affordable")

    assert criteria["confidence"] == "low"


@pytest.mark.asyncio
async def test_needs_clarification_missing_location(mock_env):
    """Test clarification needed when location missing."""
    agent = SearchAgent()

    criteria = {"bedrooms": 3, "confidence": "high"}

    assert agent._needs_clarification(criteria) is True


@pytest.mark.asyncio
async def test_needs_clarification_low_confidence(mock_env):
    """Test clarification needed for low confidence."""
    agent = SearchAgent()

    criteria = {"location": "Austin, TX", "confidence": "low"}

    assert agent._needs_clarification(criteria) is True


@pytest.mark.asyncio
async def test_needs_clarification_clear_criteria(mock_env):
    """Test no clarification needed for clear criteria."""
    agent = SearchAgent()

    criteria = {
        "location": "Austin, TX",
        "bedrooms": 3,
        "max_price": 600000,
        "confidence": "high",
    }

    assert agent._needs_clarification(criteria) is False


@pytest.mark.asyncio
async def test_request_clarification_missing_location(mock_env):
    """Test clarification request for missing location."""
    agent = SearchAgent()
    state = AgentState(user_input="3 bedrooms")

    criteria = {"bedrooms": 3, "confidence": "high"}
    result = agent._request_clarification(state, criteria)

    assert result.needs_clarification is True
    assert "location" in result.clarification_question.lower()


@pytest.mark.asyncio
async def test_search_properties_success(mock_env, mock_mcp_search):
    """Test successful property search."""
    agent = SearchAgent()

    # Mock MCP response
    mock_property = MagicMock()
    mock_property.model_dump.return_value = {
        "id": "123",
        "address": "123 Main St",
        "price": 500000,
        "bedrooms": 3,
    }
    mock_mcp_search.return_value = [mock_property]

    criteria = {"location": "Austin, TX", "bedrooms": 3, "max_price": 600000}

    properties = await agent._search_properties(criteria)

    assert len(properties) == 1
    assert properties[0]["address"] == "123 Main St"


@pytest.mark.asyncio
async def test_process_complete_workflow(mock_llm, mock_mcp_search):
    """Test complete search agent workflow."""
    agent = SearchAgent()

    # Mock LLM extraction
    mock_llm.return_value = """
    {
        "location": "Austin, TX",
        "max_price": 600000,
        "bedrooms": 3,
        "confidence": "high"
    }
    """

    # Mock MCP search
    mock_property = MagicMock()
    mock_property.model_dump.return_value = {
        "id": "123",
        "address": "123 Main St",
        "price": 500000,
    }
    mock_mcp_search.return_value = [mock_property]

    state = AgentState(user_input="Find 3 bed house in Austin under 600k")
    result = await agent.process(state)

    assert result.needs_clarification is False
    assert result.search_criteria is not None
    assert len(result.properties) == 1
    assert result.properties[0]["address"] == "123 Main St"


@pytest.mark.asyncio
async def test_process_needs_clarification(mock_llm):
    """Test process flow when clarification needed."""
    agent = SearchAgent()

    # Mock vague criteria
    mock_llm.return_value = '{"confidence": "low"}'

    state = AgentState(user_input="Something affordable")
    result = await agent.process(state)

    assert result.needs_clarification is True
    assert result.clarification_question is not None
    assert len(result.properties) == 0


@pytest.mark.asyncio
async def test_singleton_instance(mock_env):
    """Test that search_agent singleton exists."""
    agent = get_search_agent()
    assert agent is not None
    assert isinstance(agent, SearchAgent)

