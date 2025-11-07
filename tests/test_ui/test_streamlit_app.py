
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os



@pytest.fixture
@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.asyncio
"""Tests for streamlit app."""
from src.apps.base_app import AgentState
def mock_env():
    """Mock environment variables."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}):
        yield


@pytest.fixture
def mock_llm(mock_env):
    """Mock LLM calls."""

async def test_streamlit_app_initialization(mock_env):
    """Test streamlit app initializes correctly."""


@pytest.mark.asyncio
async def test_singleton_instance(mock_env):
    """Test that streamlit_app singleton exists."""
    app = get_streamlit_app()
    assert app is not None

