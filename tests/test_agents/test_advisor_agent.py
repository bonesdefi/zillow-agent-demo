"""Tests for advisor agent."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os

from src.agents.advisor_agent import AdvisorAgent, get_advisor_agent
from src.agents.base_agent import AgentState


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}):
        yield


@pytest.fixture
def mock_llm(mock_env):
    """Mock LLM calls."""
    with patch.object(AdvisorAgent, "_call_llm") as mock:
        yield mock


@pytest.mark.asyncio
async def test_advisor_agent_initialization(mock_env):
    """Test advisor agent initializes correctly."""
    agent = AdvisorAgent()
    assert agent.name == "AdvisorAgent"


@pytest.mark.asyncio
async def test_process_no_properties(mock_env):
    """Test processing with no properties."""
    agent = AdvisorAgent()
    state = AgentState(user_input="test", properties=[])

    result = await agent.process(state)

    assert result.final_response is not None
    assert "couldn't find" in result.final_response.lower() or "adjusting" in result.final_response.lower()


@pytest.mark.asyncio
async def test_calculate_score_basic(mock_env):
    """Test score calculation."""
    agent = AdvisorAgent()

    property_data = {
        "id": "123",
        "address": "123 Main St",
        "price": 500000,
        "bedrooms": 3,
        "bathrooms": 2,
    }

    analysis = {
        "affordability": {"affordable": True},
        "schools": [{"rating": 8.5}, {"rating": 9.0}],
        "neighborhood": {"walkability_score": 75, "crime_rate": "low"},
        "market_trends": {"price_change_percent": 2.5},
    }

    state = AgentState(
        user_input="test",
        search_criteria={"max_price": 600000, "bedrooms": 3},
    )

    score = agent._calculate_score(property_data, analysis, state)

    assert 0 <= score <= 100
    assert score > 50  # Should be above base score with good features


@pytest.mark.asyncio
async def test_calculate_score_over_budget(mock_env):
    """Test score calculation when over budget."""
    agent = AdvisorAgent()

    property_data = {"price": 700000}
    analysis = {}
    state = AgentState(
        user_input="test", search_criteria={"max_price": 600000}
    )

    score = agent._calculate_score(property_data, analysis, state)

    assert score < 50  # Should be penalized for being over budget


@pytest.mark.asyncio
async def test_extract_highlights(mock_env):
    """Test highlight extraction."""
    agent = AdvisorAgent()

    analysis = {
        "affordability": {"affordable": True},
        "schools": [{"rating": 8.5}, {"rating": 9.0}],
        "neighborhood": {"walkability_score": 75, "crime_rate": "low"},
        "market_trends": {"price_change_percent": 2.5},
    }

    highlights = agent._extract_highlights(analysis)

    assert len(highlights) > 0
    assert any("budget" in h.lower() for h in highlights)
    assert any("school" in h.lower() for h in highlights)


@pytest.mark.asyncio
async def test_generate_explanation(mock_llm):
    """Test explanation generation."""
    agent = AdvisorAgent()

    mock_llm.return_value = "This is a great property with excellent schools and a walkable neighborhood."

    property_data = {
        "address": "123 Main St",
        "price": 500000,
        "bedrooms": 3,
        "bathrooms": 2,
    }

    analysis = {"summary": {"pros": ["Great location"]}}
    state = AgentState(user_input="test")

    explanation = await agent._generate_explanation(
        property_data, analysis, 85.0, state
    )

    assert len(explanation) > 0
    assert "property" in explanation.lower() or "123 Main" in explanation


@pytest.mark.asyncio
async def test_generate_recommendation(mock_llm):
    """Test recommendation generation."""
    agent = AdvisorAgent()

    mock_llm.return_value = "This property is a great match for your needs."

    property_data = {
        "id": "123",
        "address": "123 Main St",
        "price": 500000,
        "bedrooms": 3,
        "bathrooms": 2,
    }

    analysis = {
        "affordability": {"affordable": True},
        "schools": [{"rating": 8.5}],
    }

    state = AgentState(
        user_input="test", search_criteria={"max_price": 600000}
    )

    recommendation = await agent._generate_recommendation(
        property_data, analysis, state
    )

    assert recommendation["property_id"] == "123"
    assert "score" in recommendation
    assert "explanation" in recommendation
    assert "highlights" in recommendation
    assert 0 <= recommendation["score"] <= 100


@pytest.mark.asyncio
async def test_process_complete_workflow(mock_llm):
    """Test complete advisor agent workflow."""
    agent = AdvisorAgent()

    # Mock LLM calls
    mock_llm.side_effect = [
        "This property is excellent.",
        "This property is good.",
        "I found 2 great properties for you.",
    ]

    state = AgentState(
        user_input="Find houses in Austin",
        properties=[
            {
                "id": "1",
                "address": "123 Main St",
                "price": 500000,
                "bedrooms": 3,
                "bathrooms": 2,
            },
            {
                "id": "2",
                "address": "456 Oak Ave",
                "price": 450000,
                "bedrooms": 2,
                "bathrooms": 1,
            },
        ],
        analyses={
            "1": {
                "affordability": {"affordable": True},
                "schools": [{"rating": 8.5}],
            },
            "2": {
                "affordability": {"affordable": True},
                "schools": [{"rating": 7.5}],
            },
        },
    )

    result = await agent.process(state)

    assert len(result.recommendations) == 2
    assert result.final_response is not None
    assert len(result.final_response) > 0
    # Recommendations should be sorted by score
    assert result.recommendations[0]["score"] >= result.recommendations[1]["score"]


@pytest.mark.asyncio
async def test_singleton_instance(mock_env):
    """Test that advisor_agent singleton exists."""
    agent = get_advisor_agent()
    assert agent is not None
    assert isinstance(agent, AdvisorAgent)

