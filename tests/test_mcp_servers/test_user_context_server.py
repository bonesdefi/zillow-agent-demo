"""Tests for User Context MCP Server."""

import pytest
from datetime import datetime

from src.mcp_servers.user_context_server import (
    store_user_preferences,
    get_user_preferences,
    add_conversation_message,
    get_conversation_history,
    track_viewed_property,
    get_viewed_properties,
    StorageResponse,
    UserPreferences,
)


@pytest.mark.asyncio
async def test_store_user_preferences_success():
    """Test successful preference storage."""
    user_id = "test_user_123"
    preferences = {
        "location": "Austin, TX",
        "max_price": 600000,
        "bedrooms": 3,
        "must_haves": ["garage", "yard"],
    }

    result = await store_user_preferences(user_id, preferences)

    assert isinstance(result, StorageResponse)
    assert result.status == "success"
    assert "stored" in result.message.lower()


@pytest.mark.asyncio
async def test_store_user_preferences_invalid_user_id():
    """Test error handling for invalid user_id."""
    with pytest.raises(ValueError, match="user_id is required"):
        await store_user_preferences("", {"location": "Austin"})


@pytest.mark.asyncio
async def test_store_user_preferences_invalid_data():
    """Test error handling for invalid preference data."""
    with pytest.raises(ValueError):
        await store_user_preferences("user123", {"invalid_field": "invalid_value"})


@pytest.mark.asyncio
async def test_get_user_preferences_success():
    """Test successful preference retrieval."""
    user_id = "test_user_456"
    preferences = {
        "location": "San Francisco, CA",
        "min_price": 800000,
        "max_price": 1200000,
    }

    # Store preferences first
    await store_user_preferences(user_id, preferences)

    # Retrieve preferences
    result = await get_user_preferences(user_id)

    assert isinstance(result, dict)
    assert result["location"] == "San Francisco, CA"
    assert result["max_price"] == 1200000


@pytest.mark.asyncio
async def test_get_user_preferences_not_found():
    """Test retrieval when preferences don't exist."""
    user_id = "nonexistent_user"

    result = await get_user_preferences(user_id)

    assert isinstance(result, dict)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_add_conversation_message_success():
    """Test successful conversation message storage."""
    user_id = "test_user_789"
    role = "user"
    content = "Find me a house in Austin"

    result = await add_conversation_message(user_id, role, content)

    assert isinstance(result, StorageResponse)
    assert result.status == "success"
    assert "stored" in result.message.lower()


@pytest.mark.asyncio
async def test_add_conversation_message_invalid_role():
    """Test error handling for invalid role."""
    with pytest.raises(ValueError, match="role must be"):
        await add_conversation_message("user123", "invalid_role", "message")


@pytest.mark.asyncio
async def test_add_conversation_message_empty_content():
    """Test error handling for empty content."""
    with pytest.raises(ValueError, match="content is required"):
        await add_conversation_message("user123", "user", "")


@pytest.mark.asyncio
async def test_get_conversation_history_success():
    """Test successful conversation history retrieval."""
    user_id = "test_user_history"
    
    # Add multiple messages
    await add_conversation_message(user_id, "user", "Hello")
    await add_conversation_message(user_id, "assistant", "Hi! How can I help?")
    await add_conversation_message(user_id, "user", "Find houses in Austin")

    # Retrieve history
    history = await get_conversation_history(user_id)

    assert isinstance(history, list)
    assert len(history) == 3
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello"
    assert history[1]["role"] == "assistant"
    assert history[2]["role"] == "user"


@pytest.mark.asyncio
async def test_get_conversation_history_with_limit():
    """Test conversation history retrieval with limit."""
    user_id = "test_user_limit"
    
    # Add 5 messages
    for i in range(5):
        await add_conversation_message(user_id, "user", f"Message {i}")

    # Retrieve with limit
    history = await get_conversation_history(user_id, limit=3)

    assert len(history) == 3
    assert history[0]["content"] == "Message 2"  # Most recent first (last 3)


@pytest.mark.asyncio
async def test_get_conversation_history_invalid_limit():
    """Test error handling for invalid limit."""
    with pytest.raises(ValueError, match="limit must be between"):
        await get_conversation_history("user123", limit=0)

    with pytest.raises(ValueError, match="limit must be between"):
        await get_conversation_history("user123", limit=2000)


@pytest.mark.asyncio
async def test_track_viewed_property_success():
    """Test successful property view tracking."""
    user_id = "test_user_view"
    property_id = "prop_123"

    result = await track_viewed_property(user_id, property_id)

    assert isinstance(result, StorageResponse)
    assert result.status == "success"
    assert "tracked" in result.message.lower()


@pytest.mark.asyncio
async def test_track_viewed_property_with_action():
    """Test property tracking with custom action."""
    user_id = "test_user_action"
    property_id = "prop_456"
    action = "favorited"

    result = await track_viewed_property(user_id, property_id, action)

    assert result.status == "success"
    assert "favorited" in result.message.lower()


@pytest.mark.asyncio
async def test_track_viewed_property_invalid_inputs():
    """Test error handling for invalid inputs."""
    with pytest.raises(ValueError, match="user_id is required"):
        await track_viewed_property("", "prop123")

    with pytest.raises(ValueError, match="property_id is required"):
        await track_viewed_property("user123", "")


@pytest.mark.asyncio
async def test_get_viewed_properties_success():
    """Test successful viewed properties retrieval."""
    user_id = "test_user_viewed"
    
    # Track multiple properties
    await track_viewed_property(user_id, "prop_1", "viewed")
    await track_viewed_property(user_id, "prop_2", "favorited")
    await track_viewed_property(user_id, "prop_3", "viewed")

    # Retrieve viewed properties
    viewed = await get_viewed_properties(user_id)

    assert isinstance(viewed, list)
    assert len(viewed) == 3
    assert all("property_id" in v for v in viewed)
    assert all("timestamp" in v for v in viewed)
    assert all("action" in v for v in viewed)
    # Should be sorted by timestamp (most recent first)
    assert viewed[0]["property_id"] == "prop_3"


@pytest.mark.asyncio
async def test_get_viewed_properties_empty():
    """Test retrieval when no properties viewed."""
    user_id = "new_user"

    viewed = await get_viewed_properties(user_id)

    assert isinstance(viewed, list)
    assert len(viewed) == 0


@pytest.mark.asyncio
async def test_full_user_workflow():
    """Test complete user workflow across all functions."""
    user_id = "workflow_user"
    
    # 1. Store preferences
    prefs = {"location": "Austin, TX", "max_price": 600000, "bedrooms": 3}
    await store_user_preferences(user_id, prefs)
    
    # 2. Add conversation messages
    await add_conversation_message(user_id, "user", "Find me a house")
    await add_conversation_message(user_id, "assistant", "I found 5 houses")
    
    # 3. Track viewed properties
    await track_viewed_property(user_id, "prop_1", "viewed")
    await track_viewed_property(user_id, "prop_2", "favorited")
    
    # 4. Verify all data
    retrieved_prefs = await get_user_preferences(user_id)
    assert retrieved_prefs["location"] == "Austin, TX"
    
    history = await get_conversation_history(user_id)
    assert len(history) == 2
    
    viewed = await get_viewed_properties(user_id)
    assert len(viewed) == 2
    assert viewed[0]["action"] == "favorited"  # Most recent

