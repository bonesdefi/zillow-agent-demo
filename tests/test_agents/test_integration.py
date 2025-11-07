"""Integration tests for complete agent workflows."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os

from src.agents.base_agent import AgentState
from src.agents.search_agent import get_search_agent
from src.agents.analysis_agent import get_analysis_agent
from src.agents.advisor_agent import get_advisor_agent


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}):
        yield


@pytest.fixture
def mock_llm(mock_env):
    """Mock LLM calls."""
    with patch("src.agents.search_agent.SearchAgent._call_llm") as mock_search_llm, patch(
        "src.agents.analysis_agent.AnalysisAgent._call_llm"
    ) as mock_analysis_llm, patch(
        "src.agents.advisor_agent.AdvisorAgent._call_llm"
    ) as mock_advisor_llm:

        # Default mock responses
        mock_search_llm.return_value = """
        {
            "location": "Austin, TX",
            "max_price": 600000,
            "bedrooms": 3,
            "confidence": "high"
        }
        """

        mock_analysis_llm.return_value = """
        {
            "pros": ["Great location", "Good schools"],
            "cons": ["Higher price"],
            "overall": "Solid choice"
        }
        """

        mock_advisor_llm.side_effect = [
            "This property is excellent.",
            "I found a great property for you!",
        ]

        yield {
            "search": mock_search_llm,
            "analysis": mock_analysis_llm,
            "advisor": mock_advisor_llm,
        }


@pytest.fixture
def mock_mcp_servers(mock_env):
    """Mock MCP server calls."""
    with patch("src.agents.search_agent.search_properties") as mock_search, patch(
        "src.agents.analysis_agent.get_neighborhood_stats"
    ) as mock_neighborhood, patch(
        "src.agents.analysis_agent.get_school_ratings"
    ) as mock_schools, patch(
        "src.agents.analysis_agent.get_market_trends"
    ) as mock_trends:

        # Mock property search
        mock_property = MagicMock()
        mock_property.model_dump.return_value = {
            "id": "123",
            "address": "123 Main St",
            "city": "Austin",
            "state": "TX",
            "price": 500000,
            "bedrooms": 3,
            "bathrooms": 2,
        }
        mock_search.return_value = [mock_property]

        # Mock analysis calls
        mock_neighborhood.return_value = MagicMock(
            model_dump=lambda: {"walkability_score": 75, "crime_rate": "low"}
        )
        mock_schools.return_value = [
            MagicMock(model_dump=lambda: {"name": "Test School", "rating": 8.5})
        ]
        mock_trends.return_value = MagicMock(
            model_dump=lambda: {"price_change_percent": 2.5, "median_price": 500000}
        )

        yield {
            "search": mock_search,
            "neighborhood": mock_neighborhood,
            "schools": mock_schools,
            "trends": mock_trends,
        }


@pytest.mark.asyncio
async def test_complete_workflow_search_to_advisor(mock_llm, mock_mcp_servers):
    """Test complete workflow from search to advisor."""
    # Step 1: Search
    search_state = AgentState(user_input="Find 3 bed house in Austin under 600k")
    search_result = await get_search_agent().process(search_state)

    assert search_result.needs_clarification is False
    assert search_result.search_criteria is not None
    assert len(search_result.properties) > 0

    # Step 2: Analysis
    analysis_result = await get_analysis_agent().process(search_result)

    assert len(analysis_result.analyses) > 0
    assert "123" in analysis_result.analyses

    # Step 3: Advisor
    advisor_result = await get_advisor_agent().process(analysis_result)

    assert len(advisor_result.recommendations) > 0
    assert len(advisor_result.final_response) > 0
    assert advisor_result.recommendations[0]["property_id"] == "123"


@pytest.mark.asyncio
async def test_workflow_with_clarification(mock_llm):
    """Test workflow when clarification is needed."""
    # Mock vague query
    mock_llm["search"].return_value = '{"confidence": "low"}'

    search_state = AgentState(user_input="Something affordable")
    search_result = await get_search_agent().process(search_state)

    assert search_result.needs_clarification is True
    assert search_result.clarification_question is not None
    assert len(search_result.properties) == 0


@pytest.mark.asyncio
async def test_workflow_no_properties_found(mock_llm, mock_mcp_servers):
    """Test workflow when no properties are found."""
    # Mock empty search results
    mock_mcp_servers["search"].return_value = []

    search_state = AgentState(
        user_input="Find 10 bed mansion in Antarctica under 100k"
    )
    search_result = await get_search_agent().process(search_state)

    # Should still have criteria but no properties
    assert search_result.search_criteria is not None
    assert len(search_result.properties) == 0

    # Analysis should handle empty properties gracefully
    analysis_result = await get_analysis_agent().process(search_result)
    assert len(analysis_result.analyses) == 0

    # Advisor should provide helpful message
    advisor_result = await get_advisor_agent().process(analysis_result)
    assert "couldn't find" in advisor_result.final_response.lower() or len(
        advisor_result.final_response
    ) > 0


@pytest.mark.asyncio
async def test_workflow_error_handling(mock_llm, mock_mcp_servers):
    """Test workflow handles errors gracefully."""
    # Make MCP search fail
    mock_mcp_servers["search"].side_effect = Exception("API Error")

    search_state = AgentState(user_input="Find houses in Austin")
    search_result = await get_search_agent().process(search_state)

    # Should have error in state
    assert len(search_result.errors) > 0
    assert "SearchAgent" in search_result.errors[0]

