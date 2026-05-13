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
        self.logger.info(f"Processing user input: {state.user_input}")

        try:
            # Step 1: Extract search criteria from natural language
            self.logger.info("Step 1: Extracting search criteria")
            criteria = await self._extract_search_criteria(state.user_input)
            self.logger.info(f"Extracted criteria: {criteria}")

            # Check if we need clarification
            needs_clar = self._needs_clarification(criteria)
            self.logger.info(f"Needs clarification: {needs_clar}")
            if needs_clar:
                self.logger.info("Requesting clarification from user")
                return self._request_clarification(state, criteria)

            # Step 2: Search for properties using MCP server
            self.logger.info("Step 2: Searching for properties")
            properties = await self._search_properties(criteria)
            self.logger.info(f"Found {len(properties)} properties")

            # Step 3: Update state
            state.search_criteria = criteria
            state.properties = properties
            state.needs_clarification = False

            self._log_processing(f"Found {len(properties)} properties")
            return state

        except ValueError as e:
            # Handle API errors (rate limiting, network issues, etc.)
            error_msg = str(e)
            self.logger.error(f"Search API error: {error_msg}")
            # Set a user-friendly error message in the state
            state.errors.append(f"Search API error: {error_msg}")
            # Set final response to inform user about the issue
            state.final_response = (
                f"I encountered an issue while searching for properties: {error_msg} "
                "Please try again in a few minutes."
            )
            return state
        except Exception as e:
            import traceback
            self.logger.error(f"Error in SearchAgent.process: {e}", exc_info=True)
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return self._add_error(state, f"Search failed: {str(e)}")

    async def _extract_search_criteria(self, user_input: str) -> Dict[str, Any]:
        """
        Extract structured search criteria from natural language using tool_use.

        Uses Anthropic's tool_use API to force structured JSON output, which
        eliminates JSON parsing failures across all Claude model versions.

        Args:
            user_input: User's natural language query

        Returns:
            Dictionary with search criteria
        """
        extraction_tool = {
            "name": "extract_search_criteria",
            "description": (
                "Extract structured real estate search criteria from a user's "
                "natural language query. Only populate fields the user explicitly "
                "mentions or clearly implies."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City and state, or ZIP code (e.g. 'Las Vegas, NV' or '89101')"
                    },
                    "min_price": {"type": "integer", "description": "Minimum price in USD"},
                    "max_price": {"type": "integer", "description": "Maximum price in USD"},
                    "bedrooms": {"type": "integer", "description": "Number of bedrooms"},
                    "bathrooms": {"type": "number", "description": "Number of bathrooms"},
                    "property_type": {
                        "type": "string",
                        "enum": ["house", "condo", "townhouse", "apartment"]
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": (
                            "high = specific query with clear criteria; "
                            "medium = some details but ambiguous; "
                            "low = vague terms like 'affordable' or no location"
                        )
                    }
                },
                "required": ["confidence"]
            }
        }

        system_prompt = (
            "You are a real estate search assistant. Use the extract_search_criteria "
            "tool to parse the user's query into structured fields. Only include "
            "fields explicitly mentioned or clearly implied. Use confidence='low' "
            "for vague terms like 'affordable' or when location is missing."
        )

        self.logger.info("Calling LLM with tool_use for criteria extraction")
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                temperature=0.3,
                system=system_prompt,
                tools=[extraction_tool],
                tool_choice={"type": "tool", "name": "extract_search_criteria"},
                messages=[{"role": "user", "content": f"Extract search criteria from: '{user_input}'"}],
            )
        except Exception as e:
            self.logger.error(f"LLM tool_use call failed: {e}", exc_info=True)
            raise

        for block in response.content:
            if block.type == "tool_use":
                criteria = dict(block.input)
                self.logger.info(f"Extracted criteria via tool_use: {criteria}")
                return criteria

        self.logger.error("No tool_use block in LLM response — falling back to low confidence")
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
        self.logger.info(f"Search criteria: {criteria}")

        try:
            # Build search params
            self.logger.info("Building PropertySearchParams")
            params = PropertySearchParams(
                location=criteria["location"],
                min_price=criteria.get("min_price"),
                max_price=criteria.get("max_price"),
                bedrooms=criteria.get("bedrooms"),
                bathrooms=criteria.get("bathrooms"),
                property_type=criteria.get("property_type"),
            )
            self.logger.info(f"Search params: {params}")

            # Call MCP server implementation directly (bypasses MCP tool wrapper)
            self.logger.info("Calling search_properties_direct()")
            properties = await search_properties_direct(params)
            self.logger.info(f"Received {len(properties)} properties from MCP server")

            # Convert to dict format for state
            property_dicts = [p.model_dump() for p in properties]
            self.logger.info(f"Converted {len(property_dicts)} properties to dict format")
            return property_dicts

        except Exception as e:
            import traceback
            self.logger.error(f"MCP server call failed: {e}", exc_info=True)
            self.logger.error(f"Traceback: {traceback.format_exc()}")
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

