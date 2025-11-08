"""Search agent for property search and query parsing."""

import json
import logging
from typing import Any, Dict, Optional

from src.agents.base_agent import BaseAgent, AgentState, AgentMCPError
from src.mcp_servers.real_estate_server import search_properties_direct, PropertySearchParams


logger = logging.getLogger(__name__)


class SearchAgent(BaseAgent):
    """
    Agent responsible for understanding user search intent and finding properties.

    This agent:
    1. Parses natural language queries into structured search criteria
    2. Calls the Real Estate MCP server to find matching properties
    3. Handles ambiguous queries by requesting clarification
    4. Returns properties and search criteria in state
    """

    def __init__(self):
        """Initialize search agent."""
        super().__init__(name="SearchAgent")

    async def process(self, state: AgentState) -> AgentState:
        """
        Process user input to search for properties.

        Args:
            state: Current agent state with user_input

        Returns:
            Updated state with:
            - search_criteria: Extracted search parameters
            - properties: Found properties (if criteria is clear)
            - needs_clarification: True if more info needed
            - clarification_question: Question to ask user
        """
        self._log_processing("Starting property search")

        try:
            # Step 1: Extract search criteria from natural language
            criteria = await self._extract_search_criteria(state.user_input)

            # Check if we need clarification
            if self._needs_clarification(criteria):
                return self._request_clarification(state, criteria)

            # Step 2: Search for properties using MCP server
            properties = await self._search_properties(criteria)

            # Step 3: Update state
            state.search_criteria = criteria
            state.properties = properties
            state.needs_clarification = False

            self._log_processing(f"Found {len(properties)} properties")
            return state

        except Exception as e:
            return self._add_error(state, f"Search failed: {str(e)}")

    async def _extract_search_criteria(self, user_input: str) -> Dict[str, Any]:
        """
        Extract structured search criteria from natural language.

        Args:
            user_input: User's natural language query

        Returns:
            Dictionary with search criteria
        """
        system_prompt = """You are a real estate search assistant. Extract structured search criteria from user queries.

Output JSON with these fields (all optional):
{
    "location": "City, State or ZIP",
    "min_price": integer,
    "max_price": integer,
    "bedrooms": integer,
    "bathrooms": float,
    "property_type": "house|condo|townhouse|apartment",
    "confidence": "high|medium|low"
}

Rules:
- Only include fields mentioned or clearly implied
- Use null for missing information
- Set confidence based on query clarity
- For vague terms like "affordable", use confidence: "low"

Examples:
"3 bedroom house in Austin under 600k" →
{"location": "Austin, TX", "max_price": 600000, "bedrooms": 3, "property_type": "house", "confidence": "high"}

"Something affordable in the suburbs" →
{"confidence": "low"}"""

        user_message = f"Extract search criteria from: '{user_input}'"

        response = await self._call_llm(system_prompt, user_message, temperature=0.3)

        try:
            # Parse JSON response
            criteria = json.loads(response)
            self.logger.info(f"Extracted criteria: {criteria}")
            return criteria
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse LLM response as JSON: {response}")
            return {"confidence": "low"}

    def _needs_clarification(self, criteria: Dict[str, Any]) -> bool:
        """
        Check if criteria needs clarification.

        Args:
            criteria: Extracted search criteria

        Returns:
            True if clarification needed
        """
        # Need clarification if:
        # 1. Low confidence
        # 2. Missing critical info (location)
        # 3. Very few criteria provided

        if criteria.get("confidence") == "low":
            return True

        if not criteria.get("location"):
            return True

        # Count how many criteria we have
        meaningful_criteria = [
            k for k in criteria.keys() if k not in ["confidence"] and criteria[k] is not None
        ]

        if len(meaningful_criteria) < 1:
            return True

        return False

    def _request_clarification(
        self, state: AgentState, criteria: Dict[str, Any]
    ) -> AgentState:
        """
        Request clarification from user.

        Args:
            state: Current state
            criteria: Partially extracted criteria

        Returns:
            State with clarification request
        """
        self._log_processing("Requesting clarification")

        # Determine what's missing
        if not criteria.get("location"):
            question = "I'd be happy to help you search for properties! What location are you interested in?"
        elif criteria.get("confidence") == "low":
            question = (
                "I want to make sure I understand what you're looking for. "
                "Could you tell me more about: the location, your budget range, "
                "and how many bedrooms you need?"
            )
        else:
            question = "Could you provide more details about what you're looking for?"

        state.needs_clarification = True
        state.clarification_question = question
        state.search_criteria = criteria

        return state

    async def _search_properties(self, criteria: Dict[str, Any]) -> list[Dict[str, Any]]:
        """
        Search for properties using MCP server.

        Args:
            criteria: Search criteria

        Returns:
            List of properties

        Raises:
            AgentMCPError: If MCP server call fails
        """
        self._log_processing("Calling Real Estate MCP server")

        try:
            # Build search params
            params = PropertySearchParams(
                location=criteria["location"],
                min_price=criteria.get("min_price"),
                max_price=criteria.get("max_price"),
                bedrooms=criteria.get("bedrooms"),
                bathrooms=criteria.get("bathrooms"),
                property_type=criteria.get("property_type"),
            )

            # Call MCP server implementation directly (bypasses MCP tool wrapper)
            properties = await search_properties_direct(params)

            # Convert to dict format for state
            return [p.model_dump() for p in properties]

        except Exception as e:
            self.logger.error(f"MCP server call failed: {e}")
            raise AgentMCPError(f"Failed to search properties: {e}")


# Lazy singleton instance (created on first access)
_search_agent_instance = None


def get_search_agent() -> SearchAgent:
    """Get or create the search agent singleton instance."""
    global _search_agent_instance
    if _search_agent_instance is None:
        _search_agent_instance = SearchAgent()
    return _search_agent_instance


# For backward compatibility, create on first access
def __getattr__(name: str):
    if name == "search_agent":
        return get_search_agent()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

