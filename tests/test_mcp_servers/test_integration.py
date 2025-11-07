"""Integration tests for MCP servers working together."""

import pytest
from unittest.mock import patch, AsyncMock

from src.mcp_servers.real_estate_server import (
    search_properties,
    get_property_details,
    PropertySearchParams,
    Property,
)
from src.mcp_servers.market_analysis_server import (
    get_neighborhood_stats,
    get_school_ratings,
    get_market_trends,
    calculate_affordability,
)
from src.mcp_servers.user_context_server import (
    store_user_preferences,
    get_user_preferences,
    add_conversation_message,
    get_conversation_history,
    track_viewed_property,
    get_viewed_properties,
)


@pytest.mark.asyncio
async def test_full_search_workflow():
    """Test complete workflow across all MCP servers."""
    user_id = "integration_test_user"
    location = "Austin, TX"

    # 1. Store user preferences
    preferences = {
        "location": location,
        "max_price": 600000,
        "bedrooms": 3,
        "must_haves": ["garage", "yard"],
    }
    prefs_result = await store_user_preferences(user_id, preferences)
    assert prefs_result.status == "success"

    # 2. Retrieve preferences
    stored_prefs = await get_user_preferences(user_id)
    assert stored_prefs["location"] == location
    assert stored_prefs["max_price"] == 600000

    # 3. Search properties using preferences
    with patch("src.mcp_servers.real_estate_server.settings") as mock_settings:
        mock_settings.rapidapi_key = "test_key"
        mock_settings.zillow_api_base_url = "https://test.api.com"
        mock_settings.zillow_api_host = "test.api.com"

        with patch("src.mcp_servers.real_estate_server._make_api_request") as mock_api:
            mock_api.return_value = {
                "props": [
                    {
                        "zpid": "prop_1",
                        "address": {"streetAddress": "123 Main St", "city": "Austin", "state": "TX", "zipcode": "78701"},
                        "price": 550000,
                        "bedrooms": 3,
                        "bathrooms": 2.5,
                        "livingArea": 2000,
                        "propertyType": "house",
                        "hdpUrl": "https://zillow.com/prop/1",
                        "description": "Beautiful home",
                        "imgSrc": "https://example.com/img1.jpg",
                    }
                ]
            }

            search_params = PropertySearchParams(
                location=stored_prefs["location"],
                max_price=stored_prefs["max_price"],
                bedrooms=stored_prefs["bedrooms"],
            )

            properties = await search_properties(search_params)
            assert len(properties) > 0
            property_id = properties[0].id

    # 4. Track viewed property
    view_result = await track_viewed_property(user_id, property_id, action="viewed")
    assert view_result.status == "success"

    # 5. Analyze neighborhood for top result
    with patch("src.mcp_servers.market_analysis_server.settings") as mock_settings:
        mock_settings.rapidapi_key = "test_key"
        mock_settings.zillow_api_base_url = "https://test.api.com"
        mock_settings.zillow_api_host = "test.api.com"

        with patch("src.mcp_servers.market_analysis_server._make_api_request") as mock_api:
            mock_api.return_value = {
                "demographics": {"population": 1000000, "medianAge": 35.5, "medianIncome": 75000},
                "crimeScore": 25.5,
                "walkScore": 78.2,
            }

            neighborhood_stats = await get_neighborhood_stats(location)
            assert neighborhood_stats.crime_score > 0
            assert neighborhood_stats.walkability_score > 0

    # 6. Get school ratings
    with patch("src.mcp_servers.market_analysis_server.settings") as mock_settings:
        mock_settings.rapidapi_key = "test_key"
        mock_settings.zillow_api_base_url = "https://test.api.com"
        mock_settings.zillow_api_host = "test.api.com"

        with patch("src.mcp_servers.market_analysis_server._make_api_request") as mock_api:
            mock_api.return_value = {
                "schools": [
                    {
                        "name": "Austin Elementary",
                        "type": "elementary",
                        "rating": 8.5,
                        "distance": 0.5,
                    }
                ]
            }

            schools = await get_school_ratings(location, radius=5)
            assert len(schools) > 0

    # 7. Calculate affordability
    property_price = properties[0].price
    annual_income = 120000
    affordability = await calculate_affordability(property_price, annual_income)
    assert affordability.monthly_payment > 0
    assert affordability.debt_to_income_ratio > 0

    # 8. Add conversation message
    conv_result = await add_conversation_message(
        user_id, "user", f"Found {len(properties)} properties in {location}"
    )
    assert conv_result.status == "success"

    # 9. Verify all data flows correctly
    viewed_props = await get_viewed_properties(user_id)
    assert len(viewed_props) > 0
    assert viewed_props[0]["property_id"] == property_id

    # Verify preferences persisted
    final_prefs = await get_user_preferences(user_id)
    assert final_prefs["location"] == location


@pytest.mark.asyncio
async def test_property_analysis_workflow():
    """Test property analysis workflow using multiple MCP servers."""
    property_id = "test_prop_analysis"
    location = "Austin, TX"

    # 1. Get property details
    with patch("src.mcp_servers.real_estate_server.settings") as mock_settings:
        mock_settings.rapidapi_key = "test_key"
        mock_settings.zillow_api_base_url = "https://test.api.com"
        mock_settings.zillow_api_host = "test.api.com"

        with patch("src.mcp_servers.real_estate_server._make_api_request") as mock_api:
            mock_api.return_value = {
                "zpid": property_id,
                "address": {"streetAddress": "123 Main St", "city": "Austin", "state": "TX", "zipcode": "78701"},
                "price": 500000,
                "bedrooms": 3,
                "bathrooms": 2.5,
                "livingArea": 2000,
                "propertyType": "house",
                "hdpUrl": "https://zillow.com/prop/1",
            }

            property_details = await get_property_details(property_id)
            assert property_details.price == 500000

    # 2. Analyze neighborhood
    with patch("src.mcp_servers.market_analysis_server.settings") as mock_settings:
        mock_settings.rapidapi_key = "test_key"
        mock_settings.zillow_api_base_url = "https://test.api.com"
        mock_settings.zillow_api_host = "test.api.com"

        with patch("src.mcp_servers.market_analysis_server._make_api_request") as mock_api:
            mock_api.return_value = {
                "demographics": {"population": 1000000},
                "crimeScore": 25.5,
                "walkScore": 78.2,
            }

            stats = await get_neighborhood_stats(location)
            assert stats.overall_score > 0

    # 3. Get market trends
    with patch("src.mcp_servers.market_analysis_server.settings") as mock_settings:
        mock_settings.rapidapi_key = "test_key"
        mock_settings.zillow_api_base_url = "https://test.api.com"
        mock_settings.zillow_api_host = "test.api.com"

        with patch("src.mcp_servers.market_analysis_server._make_api_request") as mock_api:
            mock_api.return_value = {
                "price": 500000,
                "pricePerSqft": 250,
                "priceChangePercent": 5.2,
                "daysOnMarket": 25,
                "inventoryCount": 150,
            }

            trends = await get_market_trends(location, timeframe="6m")
            assert trends.median_price > 0
            assert trends.sales_velocity > 0

    # 4. Calculate affordability
    affordability = await calculate_affordability(property_details.price, 120000)
    assert affordability.affordable is True or affordability.affordable is False
    assert affordability.monthly_payment > 0


@pytest.mark.asyncio
async def test_user_context_persistence():
    """Test that user context persists across multiple operations."""
    user_id = "persistence_test_user"

    # Store preferences
    await store_user_preferences(user_id, {"location": "San Francisco, CA", "max_price": 1000000})

    # Add conversation
    await add_conversation_message(user_id, "user", "Looking for a condo")
    await add_conversation_message(user_id, "assistant", "I found 10 condos")

    # Track properties
    await track_viewed_property(user_id, "prop_1", "viewed")
    await track_viewed_property(user_id, "prop_2", "favorited")

    # Verify persistence
    prefs = await get_user_preferences(user_id)
    assert prefs["location"] == "San Francisco, CA"

    history = await get_conversation_history(user_id)
    assert len(history) == 2

    viewed = await get_viewed_properties(user_id)
    assert len(viewed) == 2
    assert viewed[0]["action"] == "favorited"  # Most recent

