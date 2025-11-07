"""Tests for base agent class."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os

from src.agents.base_agent import BaseAgent, AgentState, AgentError, AgentLLMError


# Create a concrete implementation for testing
class ConcreteTestAgent(BaseAgent):
    """Test implementation of BaseAgent."""

    async def process(self, state: AgentState) -> AgentState:
        """Test implementation."""
        self._log_processing("Processing test state")
        return state


@pytest.fixture
def mock_anthropic():
    """Mock Anthropic client."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}):
        yield


@pytest.mark.asyncio
async def test_base_agent_initialization(mock_anthropic):
    """Test base agent initializes correctly."""
    agent = ConcreteTestAgent(name="test_agent")

    assert agent.name == "test_agent"
    assert agent.model == "claude-3-haiku-20240307"  # Default model
    assert agent.client is not None
    assert agent.logger is not None


@pytest.mark.asyncio
async def test_base_agent_missing_api_key():
    """Test base agent raises error without API key."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            ConcreteTestAgent(name="test_agent")


@pytest.mark.asyncio
async def test_call_llm_success(mock_anthropic):
    """Test successful LLM call."""
    agent = ConcreteTestAgent(name="test_agent")

    # Mock the Anthropic client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Test response from LLM")]
    agent.client.messages.create = AsyncMock(return_value=mock_response)

    result = await agent._call_llm(
        system_prompt="You are a helpful assistant", user_message="Hello"
    )

    assert result == "Test response from LLM"
    agent.client.messages.create.assert_called_once()


@pytest.mark.asyncio
async def test_call_llm_failure(mock_anthropic):
    """Test LLM call handles errors."""
    agent = ConcreteTestAgent(name="test_agent")

    # Mock failure
    agent.client.messages.create = AsyncMock(side_effect=Exception("API Error"))

    with pytest.raises(Exception, match="API Error"):
        await agent._call_llm(system_prompt="Test", user_message="Test")


@pytest.mark.asyncio
async def test_add_error(mock_anthropic):
    """Test error addition to state."""
    agent = ConcreteTestAgent(name="test_agent")
    state = AgentState(user_input="test")

    updated_state = agent._add_error(state, "Test error")

    assert len(updated_state.errors) == 1
    assert "test_agent: Test error" in updated_state.errors


@pytest.mark.asyncio
async def test_process_abstract_method(mock_anthropic):
    """Test that process method is abstract."""
    agent = ConcreteTestAgent(name="test_agent")
    state = AgentState(user_input="test")

    # Should be implemented in TestAgent
    result = await agent.process(state)
    assert isinstance(result, AgentState)


@pytest.mark.asyncio
async def test_log_processing(mock_anthropic, caplog):
    """Test logging functionality."""
    import logging
    
    # Set logging level to INFO to capture the log message
    with caplog.at_level(logging.INFO):
        agent = ConcreteTestAgent(name="test_agent")
        agent._log_processing("Test message")
        
        assert "test_agent: Test message" in caplog.text

