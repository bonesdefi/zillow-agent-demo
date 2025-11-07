"""User Context MCP Server.

This server provides tools for managing user preferences, conversation history,
and property viewing history. Uses in-memory storage for the application.
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from src.utils.config import get_settings
from src.utils.logging import setup_logging

# Initialize logger
logger = setup_logging(__name__)

# Initialize MCP server
mcp = FastMCP("User Context Server")

# Get settings
settings = get_settings()

# In-memory storage (dict-based)
# In production, this would be replaced with a database (Redis, PostgreSQL, etc.)
_user_preferences: Dict[str, Dict[str, Any]] = {}
_conversation_history: Dict[str, List[Dict[str, str]]] = defaultdict(list)
_viewed_properties: Dict[str, List[Dict[str, Any]]] = defaultdict(list)


# Pydantic Models
class UserPreferences(BaseModel):
    """User preferences data model."""

    location: Optional[str] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    property_type: Optional[str] = None
    must_haves: List[str] = Field(default_factory=list, description="List of must-have features")
    preferences_updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ConversationMessage(BaseModel):
    """Conversation message data model."""

    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class ViewedProperty(BaseModel):
    """Viewed property data model."""

    property_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    action: str = Field(default="viewed", description="Action type: viewed, favorited, etc.")


class StorageResponse(BaseModel):
    """Storage operation response model."""

    status: str = Field(..., description="Operation status: 'success' or 'error'")
    message: str = Field(..., description="Response message")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# MCP Tools
@mcp.tool()
async def store_user_preferences(user_id: str, preferences: Dict[str, Any]) -> StorageResponse:
    """
    Save user search preferences.

    Args:
        user_id: User identifier
        preferences: Preference dictionary containing:
            - location (str, optional)
            - min_price (int, optional)
            - max_price (int, optional)
            - bedrooms (int, optional)
            - bathrooms (float, optional)
            - property_type (str, optional)
            - must_haves (list, optional)

    Returns:
        StorageResponse with status and message

    Raises:
        ValueError: If user_id is invalid

    Example:
        >>> prefs = {
        ...     "location": "Austin, TX",
        ...     "max_price": 600000,
        ...     "bedrooms": 3
        ... }
        >>> result = await store_user_preferences("user123", prefs)
        >>> result.status
        'success'
    """
    logger.info(f"Storing preferences for user: {user_id}")

    if not user_id or not user_id.strip():
        raise ValueError("user_id is required and cannot be empty")

    try:
        # Validate and store preferences
        prefs_model = UserPreferences(**preferences)
        prefs_model.preferences_updated_at = datetime.now().isoformat()

        _user_preferences[user_id] = prefs_model.model_dump()

        logger.info(f"Successfully stored preferences for user: {user_id}")
        return StorageResponse(
            status="success",
            message=f"Preferences stored successfully for user {user_id}",
        )

    except Exception as e:
        logger.error(f"Error storing preferences: {e}")
        raise ValueError(f"Invalid preferences data: {e}")


@mcp.tool()
async def get_user_preferences(user_id: str) -> Dict[str, Any]:
    """
    Retrieve stored preferences.

    Args:
        user_id: User identifier

    Returns:
        User preferences dictionary, or empty dict if not found

    Raises:
        ValueError: If user_id is invalid

    Example:
        >>> prefs = await get_user_preferences("user123")
        >>> prefs.get("location")
        'Austin, TX'
    """
    logger.info(f"Retrieving preferences for user: {user_id}")

    if not user_id or not user_id.strip():
        raise ValueError("user_id is required and cannot be empty")

    preferences = _user_preferences.get(user_id, {})

    if preferences:
        logger.info(f"Found preferences for user: {user_id}")
    else:
        logger.info(f"No preferences found for user: {user_id}")

    return preferences


@mcp.tool()
async def add_conversation_message(
    user_id: str, role: str, content: str
) -> StorageResponse:
    """
    Store conversation history.

    Args:
        user_id: User identifier
        role: Message role - must be 'user' or 'assistant'
        content: Message content

    Returns:
        StorageResponse with status and message

    Raises:
        ValueError: If user_id, role, or content is invalid

    Example:
        >>> result = await add_conversation_message(
        ...     "user123", "user", "Find me a house in Austin"
        ... )
        >>> result.status
        'success'
    """
    logger.info(f"Adding conversation message for user: {user_id} (role: {role})")

    if not user_id or not user_id.strip():
        raise ValueError("user_id is required and cannot be empty")

    if role not in ["user", "assistant"]:
        raise ValueError("role must be 'user' or 'assistant'")

    if not content or not content.strip():
        raise ValueError("content is required and cannot be empty")

    try:
        message = ConversationMessage(role=role, content=content)
        _conversation_history[user_id].append(message.model_dump())

        logger.info(f"Successfully added message for user: {user_id}")
        return StorageResponse(
            status="success",
            message=f"Message stored successfully for user {user_id}",
        )

    except Exception as e:
        logger.error(f"Error storing conversation message: {e}")
        raise


@mcp.tool()
async def get_conversation_history(user_id: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
    """
    Retrieve conversation history.

    Args:
        user_id: User identifier
        limit: Optional maximum number of messages to return (most recent first)

    Returns:
        List of conversation messages, each with role, content, and timestamp

    Raises:
        ValueError: If user_id is invalid or limit is invalid

    Example:
        >>> history = await get_conversation_history("user123", limit=10)
        >>> len(history)
        10
        >>> history[0]["role"]
        'user'
    """
    logger.info(f"Retrieving conversation history for user: {user_id} (limit: {limit})")

    if not user_id or not user_id.strip():
        raise ValueError("user_id is required and cannot be empty")

    if limit is not None and (limit < 1 or limit > 1000):
        raise ValueError("limit must be between 1 and 1000")

    history = _conversation_history.get(user_id, [])

    # Return most recent messages first
    if limit:
        history = history[-limit:]

    logger.info(f"Retrieved {len(history)} messages for user: {user_id}")
    return history


@mcp.tool()
async def track_viewed_property(
    user_id: str, property_id: str, action: str = "viewed"
) -> StorageResponse:
    """
    Log properties user has viewed.

    Args:
        user_id: User identifier
        property_id: Property identifier
        action: Action type - "viewed", "favorited", "contacted", etc. (default: "viewed")

    Returns:
        StorageResponse with status and message

    Raises:
        ValueError: If user_id or property_id is invalid

    Example:
        >>> result = await track_viewed_property("user123", "prop456", action="favorited")
        >>> result.status
        'success'
    """
    logger.info(f"Tracking property view for user: {user_id}, property: {property_id}, action: {action}")

    if not user_id or not user_id.strip():
        raise ValueError("user_id is required and cannot be empty")

    if not property_id or not property_id.strip():
        raise ValueError("property_id is required and cannot be empty")

    try:
        viewed_prop = ViewedProperty(property_id=property_id, action=action)
        _viewed_properties[user_id].append(viewed_prop.model_dump())

        logger.info(f"Successfully tracked property view for user: {user_id}")
        return StorageResponse(
            status="success",
            message=f"Property {action} tracked successfully for user {user_id}",
        )

    except Exception as e:
        logger.error(f"Error tracking viewed property: {e}")
        raise


@mcp.tool()
async def get_viewed_properties(user_id: str) -> List[Dict[str, Any]]:
    """
    Get viewing history.

    Args:
        user_id: User identifier

    Returns:
        List of viewed properties, each with property_id, timestamp, and action

    Raises:
        ValueError: If user_id is invalid

    Example:
        >>> viewed = await get_viewed_properties("user123")
        >>> len(viewed)
        5
        >>> viewed[0]["property_id"]
        'prop456'
    """
    logger.info(f"Retrieving viewed properties for user: {user_id}")

    if not user_id or not user_id.strip():
        raise ValueError("user_id is required and cannot be empty")

    viewed = _viewed_properties.get(user_id, [])

    # Return most recent first
    viewed_sorted = sorted(viewed, key=lambda x: x.get("timestamp", ""), reverse=True)

    logger.info(f"Retrieved {len(viewed_sorted)} viewed properties for user: {user_id}")
    return viewed_sorted


# Server entry point
if __name__ == "__main__":
    import uvicorn

    port = settings.mcp_server_port_user_context
    logger.info(f"Starting User Context MCP Server on port {port}")
    uvicorn.run(mcp.app, host=settings.mcp_server_host, port=port)

