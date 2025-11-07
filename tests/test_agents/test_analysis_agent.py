"""Tests for analysis agent."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os

from src.agents.analysis_agent import AnalysisAgent, get_analysis_agent
from src.agents.base_agent import AgentState


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}):
        yield


@pytest.fixture
def mock_llm(mock_env):
    """Mock LLM calls."""
    with patch.object(AnalysisAgent, "_call_llm") as mock:
        yield mock


@pytest.fixture
def mock_mcp_calls(mock_env):
    """Mock all MCP server calls."""
    with patch("src.agents.analysis_agent.get_neighborhood_stats") as mock_neighborhood, patch(
        "src.agents.analysis_agent.get_school_ratings"
    ) as mock_schools, patch(
        "src.agents.analysis_agent.get_market_trends"
    ) as mock_trends, patch(
        "src.agents.analysis_agent.calculate_affordability"
    ) as mock_afford:

        # Setup default returns
        mock_neighborhood.return_value = MagicMock()
        mock_neighborhood.return_value.model_dump.return_value = {
            "walkability_score": 75,
            "crime_rate": "low",
        }

        mock_schools.return_value = [
            MagicMock(model_dump=lambda: {"name": "Test School", "rating": 8.0})
        ]

        mock_trends.return_value = MagicMock()
        mock_trends.return_value.model_dump.return_value = {
            "trend": "stable",
            "median_price": 500000,
        }

        mock_afford.return_value = MagicMock()
        mock_afford.return_value.model_dump.return_value = {
            "affordable": True,
            "monthly_payment": 2500,
        }

        yield {
            "neighborhood": mock_neighborhood,
            "schools": mock_schools,
            "trends": mock_trends,
            "afford": mock_afford,
        }


@pytest.mark.asyncio
async def test_analysis_agent_initialization(mock_env):
    """Test analysis agent initializes correctly."""
    agent = AnalysisAgent()
    assert agent.name == "AnalysisAgent"


@pytest.mark.asyncio
async def test_process_no_properties(mock_env):
    """Test processing with no properties."""
    agent = AnalysisAgent()
    state = AgentState(user_input="test", properties=[])

    result = await agent.process(state)

    assert len(result.analyses) == 0


@pytest.mark.asyncio
async def test_analyze_property_complete(mock_llm, mock_mcp_calls):
    """Test complete property analysis."""
    agent = AnalysisAgent()

    # Mock LLM summary
    mock_llm.return_value = """
    {
        "pros": ["Great location", "Good schools"],
        "cons": ["Higher price"],
        "overall": "Solid choice"
    }
    """

    property_data = {
        "id": "123",
        "address": "123 Main St",
        "city": "Austin",
        "state": "TX",
        "price": 500000,
        "bedrooms": 3,
        "bathrooms": 2,
    }

    state = AgentState(user_input="test", search_criteria={"annual_income": 120000})

    analysis = await agent._analyze_property(property_data, state)

    assert analysis["property_id"] == "123"
    assert analysis["neighborhood"] is not None
    assert len(analysis["schools"]) > 0
    assert analysis["market_trends"] is not None
    assert analysis["affordability"] is not None
    assert "pros" in analysis["summary"]


@pytest.mark.asyncio
async def test_analyze_property_missing_income(mock_llm, mock_mcp_calls):
    """Test property analysis without income."""
    agent = AnalysisAgent()

    mock_llm.return_value = '{"pros": [], "cons": [], "overall": "test"}'

    property_data = {
        "id": "123",
        "address": "123 Main St",
        "city": "Austin",
        "state": "TX",
        "price": 500000,
    }

    state = AgentState(user_input="test")

    analysis = await agent._analyze_property(property_data, state)

    # Should not have affordability without income
    assert "affordability" not in analysis or analysis["affordability"] is None


@pytest.mark.asyncio
async def test_analyze_property_mcp_failure(mock_llm, mock_mcp_calls):
    """Test property analysis with MCP failures."""
    agent = AnalysisAgent()

    # Make MCP calls fail
    mock_mcp_calls["neighborhood"].side_effect = Exception("API Error")

    mock_llm.return_value = '{"pros": [], "cons": [], "overall": "test"}'

    property_data = {
        "id": "123",
        "address": "123 Main St",
        "city": "Austin",
        "state": "TX",
    }

    state = AgentState(user_input="test")

    # Should not raise, just log warning
    analysis = await agent._analyze_property(property_data, state)

    assert analysis["neighborhood"] is None


@pytest.mark.asyncio
async def test_process_multiple_properties(mock_llm, mock_mcp_calls):
    """Test processing multiple properties."""
    agent = AnalysisAgent()

    mock_llm.return_value = '{"pros": [], "cons": [], "overall": "test"}'

    state = AgentState(
        user_input="test",
        properties=[
            {"id": "1", "address": "123 Main", "city": "Austin", "state": "TX"},
            {"id": "2", "address": "456 Oak", "city": "Austin", "state": "TX"},
            {"id": "3", "address": "789 Elm", "city": "Austin", "state": "TX"},
        ],
    )

    result = await agent.process(state)

    assert len(result.analyses) == 3
    assert "1" in result.analyses
    assert "2" in result.analyses
    assert "3" in result.analyses


@pytest.mark.asyncio
async def test_process_limits_to_five_properties(mock_llm, mock_mcp_calls):
    """Test that processing limits to 5 properties."""
    agent = AnalysisAgent()

    mock_llm.return_value = '{"pros": [], "cons": [], "overall": "test"}'

    # Create 10 properties
    properties = [
        {"id": str(i), "address": f"{i} St", "city": "Austin", "state": "TX"}
        for i in range(10)
    ]

    state = AgentState(user_input="test", properties=properties)

    result = await agent.process(state)

    # Should only analyze first 5
    assert len(result.analyses) == 5


@pytest.mark.asyncio
async def test_singleton_instance(mock_env):
    """Test that analysis_agent singleton exists."""
    agent = get_analysis_agent()
    assert agent is not None
    assert isinstance(agent, AnalysisAgent)

