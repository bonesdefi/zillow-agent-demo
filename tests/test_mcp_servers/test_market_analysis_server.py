"""Tests for Market Analysis MCP Server."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from src.mcp_servers.market_analysis_server import (
    get_neighborhood_stats,
    get_school_ratings,
    get_market_trends,
    calculate_affordability,
    get_comparable_sales,
    NeighborhoodStats,
    SchoolRating,
    MarketTrends,
    AffordabilityAnalysis,
    ComparableSale,
)


@pytest.mark.asyncio
async def test_get_neighborhood_stats_success():
    """Test successful neighborhood stats retrieval."""
    location = "Austin, TX"

    with patch("src.mcp_servers.market_analysis_server.settings") as mock_settings:
        mock_settings.rapidapi_key = "test_key"
        mock_settings.zillow_api_base_url = "https://test.api.com"
        mock_settings.zillow_api_host = "test.api.com"

        with patch("src.mcp_servers.market_analysis_server._make_api_request") as mock_api:
            mock_api.return_value = {
                "demographics": {
                    "population": 1000000,
                    "medianAge": 35.5,
                    "medianIncome": 75000,
                    "householdSize": 2.5,
                },
                "crimeScore": 25.5,
                "walkScore": 78.2,
            }

            result = await get_neighborhood_stats(location)

            assert isinstance(result, NeighborhoodStats)
            assert result.crime_score == 25.5
            assert result.walkability_score == 78.2
            assert result.overall_score > 0
            assert "population" in result.demographics


@pytest.mark.asyncio
async def test_get_neighborhood_stats_invalid_location():
    """Test error handling for invalid location."""
    with pytest.raises(ValueError, match="Invalid location"):
        await get_neighborhood_stats("")


@pytest.mark.asyncio
async def test_get_neighborhood_stats_api_failure():
    """Test handling of API failures."""
    with patch("src.mcp_servers.market_analysis_server.settings") as mock_settings:
        mock_settings.rapidapi_key = "test_key"
        mock_settings.zillow_api_base_url = "https://test.api.com"
        mock_settings.zillow_api_host = "test.api.com"

        with patch("src.mcp_servers.market_analysis_server._make_api_request") as mock_api:
            mock_api.side_effect = httpx.HTTPError("API unavailable")

            with pytest.raises(httpx.HTTPError):
                await get_neighborhood_stats("Austin, TX")


@pytest.mark.asyncio
async def test_get_school_ratings_success():
    """Test successful school ratings retrieval."""
    location = "Austin, TX"
    radius = 5

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
                        "address": "123 School St",
                        "grades": "K-5",
                    },
                    {
                        "name": "Austin High",
                        "type": "high",
                        "rating": 9.0,
                        "distance": 1.2,
                    },
                ]
            }

            result = await get_school_ratings(location, radius)

            assert isinstance(result, list)
            assert len(result) > 0
            assert all(isinstance(s, SchoolRating) for s in result)
            assert result[0].name == "Austin Elementary"
            assert result[0].rating == 8.5


@pytest.mark.asyncio
async def test_get_school_ratings_invalid_radius():
    """Test error handling for invalid radius."""
    with pytest.raises(ValueError, match="Radius must be between"):
        await get_school_ratings("Austin, TX", radius=0)

    with pytest.raises(ValueError, match="Radius must be between"):
        await get_school_ratings("Austin, TX", radius=30)


@pytest.mark.asyncio
async def test_get_market_trends_success():
    """Test successful market trends retrieval."""
    location = "Austin, TX"
    timeframe = "6m"

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
                "salesVelocity": 45.3,
            }

            result = await get_market_trends(location, timeframe)

            assert isinstance(result, MarketTrends)
            assert result.location == location
            assert result.timeframe == timeframe
            assert result.median_price == 500000
            assert result.price_change_percent == 5.2
            assert result.trend_direction in ["up", "down", "stable"]


@pytest.mark.asyncio
async def test_get_market_trends_invalid_timeframe():
    """Test error handling for invalid timeframe."""
    with pytest.raises(ValueError, match="Invalid timeframe"):
        await get_market_trends("Austin, TX", timeframe="2y")


@pytest.mark.asyncio
async def test_calculate_affordability_affordable():
    """Test affordability calculation for affordable property."""
    price = 500000
    annual_income = 120000
    down_payment = 100000

    result = await calculate_affordability(price, annual_income, down_payment)

    assert isinstance(result, AffordabilityAnalysis)
    assert result.affordable is True
    assert result.monthly_payment > 0
    assert result.down_payment == down_payment
    assert result.loan_amount == price - down_payment
    assert result.debt_to_income_ratio > 0
    assert result.debt_to_income_ratio <= 100
    assert "recommendation" in result.recommendation.lower()


@pytest.mark.asyncio
async def test_calculate_affordability_not_affordable():
    """Test affordability calculation for unaffordable property."""
    price = 2000000
    annual_income = 50000

    result = await calculate_affordability(price, annual_income)

    assert isinstance(result, AffordabilityAnalysis)
    assert result.affordable is False
    assert result.monthly_payment > 0
    assert "not affordable" in result.recommendation.lower() or "exceeds" in result.recommendation.lower()


@pytest.mark.asyncio
async def test_calculate_affordability_invalid_inputs():
    """Test error handling for invalid inputs."""
    with pytest.raises(ValueError, match="Price must be greater than 0"):
        await calculate_affordability(0, 100000)

    with pytest.raises(ValueError, match="Annual income must be greater than 0"):
        await calculate_affordability(500000, 0)

    with pytest.raises(ValueError, match="Down payment cannot exceed"):
        await calculate_affordability(500000, 100000, down_payment=600000)


@pytest.mark.asyncio
async def test_calculate_affordability_default_down_payment():
    """Test affordability calculation with default 20% down payment."""
    price = 500000
    annual_income = 120000

    result = await calculate_affordability(price, annual_income)

    assert result.down_payment == int(price * 0.20)
    assert result.loan_amount == price - result.down_payment


@pytest.mark.asyncio
async def test_get_comparable_sales_success():
    """Test successful comparable sales retrieval."""
    location = "Austin, TX"
    property_type = "house"

    with patch("src.mcp_servers.market_analysis_server.settings") as mock_settings:
        mock_settings.rapidapi_key = "test_key"
        mock_settings.zillow_api_base_url = "https://test.api.com"
        mock_settings.zillow_api_host = "test.api.com"

        with patch("src.mcp_servers.market_analysis_server._make_api_request") as mock_api:
            mock_api.return_value = {
                "comps": [
                    {
                        "address": "123 Main St",
                        "price": 525000,
                        "saleDate": "2024-01-15",
                        "squareFeet": 2000,
                        "bedrooms": 3,
                        "bathrooms": 2.5,
                        "propertyType": "house",
                        "distance": 0.3,
                    },
                    {
                        "address": "456 Oak Ave",
                        "price": 510000,
                        "saleDate": "2024-01-10",
                        "squareFeet": 1900,
                        "bedrooms": 3,
                        "bathrooms": 2,
                        "propertyType": "house",
                        "distance": 0.5,
                    },
                ]
            }

            result = await get_comparable_sales(location, property_type)

            assert isinstance(result, list)
            assert len(result) > 0
            assert all(isinstance(s, ComparableSale) for s in result)
            assert all(s.property_type == "house" for s in result)
            assert result[0].sale_price == 525000


@pytest.mark.asyncio
async def test_get_comparable_sales_invalid_location():
    """Test error handling for invalid location."""
    with pytest.raises(ValueError, match="Invalid location"):
        await get_comparable_sales("")


@pytest.mark.asyncio
async def test_get_comparable_sales_caching():
    """Test that comparable sales are cached."""
    location = "Austin, TX"

    with patch("src.mcp_servers.market_analysis_server.settings") as mock_settings:
        mock_settings.rapidapi_key = "test_key"
        mock_settings.zillow_api_base_url = "https://test.api.com"
        mock_settings.zillow_api_host = "test.api.com"

        with patch("src.mcp_servers.market_analysis_server._make_api_request") as mock_api:
            mock_api.return_value = {"comps": []}

            # First call
            result1 = await get_comparable_sales(location)

            # Second call should use cache
            result2 = await get_comparable_sales(location)

            # Should only call API once
            assert mock_api.call_count == 1
            assert len(result1) == len(result2)

