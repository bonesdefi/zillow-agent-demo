"""Advisor agent for synthesizing recommendations."""

import json
import logging
from typing import Any, Dict, List

from src.agents.base_agent import BaseAgent, AgentState


logger = logging.getLogger(__name__)


class AdvisorAgent(BaseAgent):
    """
    Agent responsible for synthesizing information and providing recommendations.

    This agent:
    1. Takes analyzed properties from state
    2. Synthesizes information from Search and Analysis agents
    3. Generates personalized recommendations
    4. Provides natural language explanations
    5. Returns final response for user
    """

    def __init__(self):
        """Initialize advisor agent."""
        super().__init__(name="AdvisorAgent")

    async def process(self, state: AgentState) -> AgentState:
        """
        Process analyzed properties to generate recommendations.

        Args:
            state: Current state with properties and analyses

        Returns:
            Updated state with recommendations and final_response
        """
        self._log_processing("Starting recommendation generation")

        if not state.properties:
            state.final_response = "I couldn't find any properties matching your criteria. Could you try adjusting your search?"
            return state

        try:
            # Generate recommendations for each analyzed property
            recommendations = []
            for prop in state.properties:
                property_id = prop.get("id")
                if property_id and property_id in state.analyses:
                    recommendation = await self._generate_recommendation(
                        prop, state.analyses[property_id], state
                    )
                    recommendations.append(recommendation)

            # Sort recommendations by score (highest first)
            recommendations.sort(key=lambda x: x.get("score", 0), reverse=True)

            # Generate final natural language response
            final_response = await self._generate_final_response(
                state, recommendations
            )

            state.recommendations = recommendations
            state.final_response = final_response

            self._log_processing(f"Generated {len(recommendations)} recommendations")
            return state

        except Exception as e:
            return self._add_error(
                state, f"Recommendation generation failed: {str(e)}"
            )

    async def _generate_recommendation(
        self,
        property_data: Dict[str, Any],
        analysis: Dict[str, Any],
        state: AgentState,
    ) -> Dict[str, Any]:
        """
        Generate recommendation for a single property.

        Args:
            property_data: Property information
            analysis: Analysis results
            state: Current state

        Returns:
            Dictionary with recommendation details
        """
        recommendation = {
            "property_id": property_data.get("id"),
            "address": property_data.get("address"),
            "price": property_data.get("price"),
            "bedrooms": property_data.get("bedrooms"),
            "bathrooms": property_data.get("bathrooms"),
        }

        # Calculate recommendation score
        score = self._calculate_score(property_data, analysis, state)
        recommendation["score"] = score

        # Generate explanation using LLM
        explanation = await self._generate_explanation(
            property_data, analysis, score, state
        )
        recommendation["explanation"] = explanation

        # Add key highlights
        recommendation["highlights"] = self._extract_highlights(analysis)

        return recommendation

    def _calculate_score(
        self,
        property_data: Dict[str, Any],
        analysis: Dict[str, Any],
        state: AgentState,
    ) -> float:
        """
        Calculate recommendation score (0-100).

        Args:
            property_data: Property information
            analysis: Analysis results
            state: Current state

        Returns:
            Score from 0 to 100
        """
        score = 50.0  # Base score

        # Price match (if criteria specified)
        search_criteria = state.search_criteria or {}
        max_price = search_criteria.get("max_price")
        min_price = search_criteria.get("min_price")
        price = property_data.get("price", 0)

        if max_price and price <= max_price:
            score += 10
        if min_price and price >= min_price:
            score += 10
        if max_price and price > max_price * 1.1:  # 10% over budget
            score -= 15

        # Bedrooms match
        desired_bedrooms = search_criteria.get("bedrooms")
        bedrooms = property_data.get("bedrooms", 0)
        if desired_bedrooms and bedrooms >= desired_bedrooms:
            score += 10
        elif desired_bedrooms and bedrooms < desired_bedrooms:
            score -= 10

        # Affordability
        affordability = analysis.get("affordability")
        if affordability and affordability.get("affordable"):
            score += 15
        elif affordability and not affordability.get("affordable"):
            score -= 10

        # School quality
        schools = analysis.get("schools", [])
        if schools:
            avg_rating = sum(s.get("rating", 0) for s in schools) / len(schools)
            if avg_rating >= 8.0:
                score += 10
            elif avg_rating >= 7.0:
                score += 5

        # Market trends
        trends = analysis.get("market_trends")
        if trends:
            price_change = trends.get("price_change_percent", 0)
            if price_change > 0:
                score += 5  # Appreciating market

        # Clamp score between 0 and 100
        return max(0.0, min(100.0, score))

    async def _generate_explanation(
        self,
        property_data: Dict[str, Any],
        analysis: Dict[str, Any],
        score: float,
        state: AgentState,
    ) -> str:
        """
        Generate natural language explanation for recommendation.

        Args:
            property_data: Property information
            analysis: Analysis results
            score: Recommendation score
            state: Current state

        Returns:
            Explanation text
        """
        system_prompt = """You are a real estate advisor. Generate a concise, helpful explanation for why this property is recommended.

Be specific about:
- Price and value
- Location
- Schools (if available)
- Market trends
- Overall fit for the buyer

Keep it to 2-3 sentences. Be honest about any concerns."""

        user_message = f"""
Property: {property_data.get('address')}
Price: ${property_data.get('price', 0):,}
Bedrooms: {property_data.get('bedrooms')}
Bathrooms: {property_data.get('bathrooms')}

Recommendation Score: {score:.1f}/100

Analysis Summary:
{analysis.get('summary', {})}

Schools: {len(analysis.get('schools', []))} nearby
Market Trends: {analysis.get('market_trends', {})}
Affordability: {analysis.get('affordability', {})}
"""

        try:
            response = await self._call_llm(
                system_prompt, user_message, temperature=0.6, max_tokens=300
            )
            return response.strip()
        except Exception as e:
            self.logger.error(f"Failed to generate explanation: {e}")
            return f"This property at {property_data.get('address')} matches your criteria with a score of {score:.1f}/100."

    def _extract_highlights(self, analysis: Dict[str, Any]) -> List[str]:
        """
        Extract key highlights from analysis.

        Args:
            analysis: Analysis results

        Returns:
            List of highlight strings
        """
        highlights = []

        # Affordability
        affordability = analysis.get("affordability")
        if affordability and affordability.get("affordable"):
            highlights.append("✅ Within your budget")

        # Schools
        schools = analysis.get("schools", [])
        if schools:
            high_rated = [s for s in schools if s.get("rating", 0) >= 8.0]
            if high_rated:
                highlights.append(f"⭐ {len(high_rated)} highly-rated schools nearby")

        # Market trends
        trends = analysis.get("market_trends")
        if trends:
            price_change = trends.get("price_change_percent", 0)
            if price_change > 0:
                highlights.append("📈 Appreciating market")

        return highlights

    async def _generate_final_response(
        self, state: AgentState, recommendations: List[Dict[str, Any]]
    ) -> str:
        """
        Generate final natural language response for user.

        Args:
            state: Current state
            recommendations: List of recommendations

        Returns:
            Final response text
        """
        if not recommendations:
            return "I found some properties, but couldn't complete the analysis. Please try again."

        system_prompt = """You are a friendly real estate assistant. Generate a natural, conversational response summarizing property recommendations.

Structure:
1. Brief greeting and summary of what you found
2. Highlight top 2-3 properties with key points
3. Offer to provide more details or refine search

Be conversational, helpful, and specific. Mention prices, locations, and key features."""

        user_message = f"""
User Query: {state.user_input}

Found {len(state.properties)} properties matching criteria.

Top Recommendations:
{json.dumps(recommendations[:3], indent=2)}
"""

        try:
            response = await self._call_llm(
                system_prompt, user_message, temperature=0.7, max_tokens=500
            )
            return response.strip()
        except Exception as e:
            self.logger.error(f"Failed to generate final response: {e}")
            # Fallback response
            top_rec = recommendations[0] if recommendations else None
            if top_rec:
                return (
                    f"I found {len(recommendations)} properties that match your criteria. "
                    f"The top recommendation is {top_rec.get('address')} at ${top_rec.get('price', 0):,}. "
                    f"{top_rec.get('explanation', 'This property matches your search criteria.')}"
                )
            return f"I found {len(state.properties)} properties matching your criteria."


# Lazy singleton instance (created on first access)
_advisor_agent_instance = None


def get_advisor_agent() -> AdvisorAgent:
    """Get or create the advisor agent singleton instance."""
    global _advisor_agent_instance
    if _advisor_agent_instance is None:
        _advisor_agent_instance = AdvisorAgent()
    return _advisor_agent_instance


# For backward compatibility, create on first access
def __getattr__(name: str):
    if name == "advisor_agent":
        return get_advisor_agent()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
