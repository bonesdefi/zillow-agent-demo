"""Analysis agent for property evaluation."""

import json
import logging
from typing import Any, Dict

from src.agents.base_agent import BaseAgent, AgentState, AgentMCPError
from src.mcp_servers.market_analysis_server import (
    get_neighborhood_stats,
    get_school_ratings,
    get_market_trends,
    calculate_affordability,
)


logger = logging.getLogger(__name__)


class AnalysisAgent(BaseAgent):
    """
    Agent responsible for analyzing properties.

    This agent:
    1. Takes properties from state
    2. Analyzes each using Market Analysis MCP server
    3. Gathers neighborhood data, schools, market trends
    4. Calculates affordability if income provided
    5. Returns detailed analysis in state
    """

    def __init__(self):
        """Initialize analysis agent."""
        super().__init__(name="AnalysisAgent")

    async def process(self, state: AgentState) -> AgentState:
        """
        Process properties to add analysis.

        Args:
            state: Current state with properties to analyze

        Returns:
            Updated state with analyses dictionary
        """
        self._log_processing(f"Starting analysis of {len(state.properties)} properties")

        if not state.properties:
            self._log_processing("No properties to analyze")
            return state

        try:
            analyses = {}

            # Analyze top properties (limit to 5 for performance)
            properties_to_analyze = state.properties[:5]

            for prop in properties_to_analyze:
                property_id = prop.get("id")
                if not property_id:
                    continue

                self._log_processing(f"Analyzing property {property_id}")

                analysis = await self._analyze_property(prop, state)
                analyses[property_id] = analysis

            state.analyses = analyses
            self._log_processing(f"Completed analysis of {len(analyses)} properties")

            return state

        except Exception as e:
            return self._add_error(state, f"Analysis failed: {str(e)}")

    async def _analyze_property(
        self, property_data: Dict[str, Any], state: AgentState
    ) -> Dict[str, Any]:
        """
        Analyze a single property.

        Args:
            property_data: Property information
            state: Current state (for user preferences)

        Returns:
            Dictionary with analysis results
        """
        analysis = {
            "property_id": property_data.get("id"),
            "address": property_data.get("address"),
        }

        # Use full property address for API calls (endpoint requires specific address, not city/state)
        # Fallback to city, state if address not available
        property_address = property_data.get("address", "")
        if property_address:
            location = property_address
        else:
            # Fallback to city, state if address not available
            location = f"{property_data.get('city')}, {property_data.get('state')}"
            self.logger.warning(f"Property address not available, using city/state: {location}")

        try:
            # Get neighborhood stats using full address
            neighborhood = await get_neighborhood_stats(location)
            analysis["neighborhood"] = neighborhood.model_dump()

        except Exception as e:
            self.logger.warning(f"Failed to get neighborhood stats: {e}")
            analysis["neighborhood"] = None

        try:
            # Get school ratings using full address
            schools = await get_school_ratings(location, radius=5)
            analysis["schools"] = [s.model_dump() for s in schools]

        except Exception as e:
            self.logger.warning(f"Failed to get school ratings: {e}")
            analysis["schools"] = []

        try:
            # Get market trends using full address
            trends = await get_market_trends(location)
            analysis["market_trends"] = trends.model_dump()

        except Exception as e:
            self.logger.warning(f"Failed to get market trends: {e}")
            analysis["market_trends"] = None

        # Calculate affordability if income provided
        user_prefs = state.search_criteria or {}
        annual_income = user_prefs.get("annual_income")

        if annual_income:
            try:
                price = property_data.get("price", 0)
                affordability = await calculate_affordability(price, annual_income)
                analysis["affordability"] = affordability.model_dump()

            except Exception as e:
                self.logger.warning(f"Failed to calculate affordability: {e}")
                analysis["affordability"] = None

        # Generate pros/cons summary using LLM
        summary = await self._generate_summary(property_data, analysis)
        analysis["summary"] = summary

        return analysis

    async def _generate_summary(
        self, property_data: Dict[str, Any], analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate pros/cons summary using LLM.

        Args:
            property_data: Property information
            analysis: Analysis results

        Returns:
            Dictionary with pros, cons, and overall assessment
        """
        system_prompt = """You are a real estate analyst. Generate a concise pros/cons analysis.

IMPORTANT: You MUST respond with ONLY valid JSON. Do not include any markdown formatting, code blocks, or explanatory text. Return ONLY the JSON object.

Required JSON format:
{
    "pros": ["list", "of", "positive", "aspects"],
    "cons": ["list", "of", "concerns"],
    "overall": "brief overall assessment"
}

Focus on: location, price, schools, market trends, neighborhood quality.

Return ONLY the JSON object, nothing else."""

        user_message = f"""
Property: {property_data.get('address')}
Price: ${property_data.get('price', 0):,}
Bedrooms: {property_data.get('bedrooms')}
Bathrooms: {property_data.get('bathrooms')}

Analysis:
- Neighborhood: {analysis.get('neighborhood')}
- Schools: {len(analysis.get('schools', []))} nearby
- Market Trends: {analysis.get('market_trends')}
"""

        try:
            response = await self._call_llm(system_prompt, user_message, temperature=0.5)
            
            # Clean up response - remove markdown code blocks if present
            cleaned_response = response.strip()
            
            # Remove markdown code blocks (```json ... ```)
            if cleaned_response.startswith("```"):
                # Find the start and end of the code block
                lines = cleaned_response.split("\n")
                # Remove first line (```json or ```)
                if lines[0].startswith("```"):
                    lines = lines[1:]
                # Remove last line if it's ```
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned_response = "\n".join(lines).strip()
            
            # Try to extract JSON from the response
            # Look for JSON object boundaries
            start_idx = cleaned_response.find("{")
            end_idx = cleaned_response.rfind("}")
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = cleaned_response[start_idx:end_idx + 1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    # Try parsing the entire cleaned response
                    pass
            
            # Try parsing the cleaned response directly
            return json.loads(cleaned_response)

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON from LLM response: {e}. Response: {response[:200]}")
            # Return a structured fallback with available analysis data
            pros = []
            cons = []
            overall = "Analysis completed but summary generation failed."
            
            # Try to extract some useful information from the analysis
            if analysis.get("neighborhood"):
                pros.append("Neighborhood data available")
            if analysis.get("market_trends"):
                pros.append("Market trends analyzed")
            if len(analysis.get("schools", [])) == 0:
                cons.append("School information unavailable")
            if not analysis.get("neighborhood") or not analysis.get("market_trends"):
                cons.append("Some analysis data incomplete")
            
            if not pros:
                pros.append("Property available")
            if not cons:
                cons.append("Limited analysis data")
                
            return {
                "pros": pros,
                "cons": cons,
                "overall": overall,
            }
        except Exception as e:
            self.logger.error(f"Failed to generate summary: {e}")
            return {
                "pros": ["Property available"],
                "cons": ["Analysis incomplete"],
                "overall": "Unable to generate full analysis",
            }


# Lazy singleton instance (created on first access)
_analysis_agent_instance = None


def get_analysis_agent() -> AnalysisAgent:
    """Get or create the analysis agent singleton instance."""
    global _analysis_agent_instance
    if _analysis_agent_instance is None:
        _analysis_agent_instance = AnalysisAgent()
    return _analysis_agent_instance


# For backward compatibility, create on first access
def __getattr__(name: str):
    if name == "analysis_agent":
        return get_analysis_agent()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

