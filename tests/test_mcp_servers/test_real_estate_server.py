"""Tests for Real Estate Data MCP Server."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from src.mcp_servers.real_estate_server import (
    search_properties,
    get_property_details,
    get_property_photos,
    get_similar_properties,
    PropertySearchParams,
    Property,
    _generate_mock_properties,
)


@pytest.mark.asyncio
async def test_search_properties_basic():
    """Test basic property search functionality."""
    params = PropertySearchParams(
        location="Austin, TX",
        max_price=600000,
        bedrooms=3,
    )

    # Mock the API call with real API key
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

            results = await search_properties(params)

            assert isinstance(results, list)
            assert len(results) > 0
            assert all(isinstance(p, Property) for p in results)
            assert all(p.bedrooms == 3 for p in results)
            assert all(p.price <= 600000 for p in results)


@pytest.mark.asyncio
async def test_search_properties_missing_api_key():
    """Test error handling when API key is not configured."""
    params = PropertySearchParams(location="Austin, TX")

    with patch("src.mcp_servers.real_estate_server.settings") as mock_settings:
        mock_settings.rapidapi_key = None
        mock_settings.zillow_api_base_url = "https://test.api.com"
        mock_settings.zillow_api_host = "test.api.com"

        with pytest.raises(ValueError, match="RAPIDAPI_KEY not configured"):
            await search_properties(params)


@pytest.mark.asyncio
async def test_search_properties_invalid_location():
    """Test error handling for invalid location."""
    params = PropertySearchParams(
        location="",  # Empty location
        bedrooms=3,
    )

    with pytest.raises(ValueError, match="Invalid location"):
        await search_properties(params)


@pytest.mark.asyncio
async def test_search_properties_api_failure():
    """Test handling of API failures."""
    params = PropertySearchParams(location="Austin, TX")

    # Mock API failure
    with patch("src.mcp_servers.real_estate_server._make_api_request") as mock_api:
        mock_api.side_effect = httpx.HTTPError("API unavailable")

        with patch("src.mcp_servers.real_estate_server.settings") as mock_settings:
            mock_settings.rapidapi_key = "test_key"
            mock_settings.zillow_api_base_url = "https://test.api.com"

            with pytest.raises(httpx.HTTPError):
                await search_properties(params)


@pytest.mark.asyncio
async def test_get_property_details_success():
    """Test successful property details retrieval."""
    property_id = "test_property_123"

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
                "description": "Beautiful home",
                "imgSrc": "https://example.com/img1.jpg",
            }

            result = await get_property_details(property_id)

            assert isinstance(result, Property)
            assert result.id == property_id
            assert result.address is not None
            assert result.price > 0


@pytest.mark.asyncio
async def test_get_property_details_invalid_id():
    """Test error handling for invalid property ID."""
    with pytest.raises(ValueError, match="property_id is required"):
        await get_property_details("")


@pytest.mark.asyncio
async def test_get_property_details_not_found():
    """Test handling of property not found."""
    property_id = "nonexistent_property"

    with patch("src.mcp_servers.real_estate_server._make_api_request") as mock_api:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_api.side_effect = httpx.HTTPStatusError(
            "Not found", request=MagicMock(), response=mock_response
        )

        with patch("src.mcp_servers.real_estate_server.settings") as mock_settings:
            mock_settings.rapidapi_key = "test_key"
            mock_settings.zillow_api_base_url = "https://test.api.com"

            with pytest.raises(ValueError, match="Property not found"):
                await get_property_details(property_id)


@pytest.mark.asyncio
async def test_get_property_photos():
    """Test property photos retrieval."""
    property_id = "test_property_123"

    with patch("src.mcp_servers.real_estate_server.settings") as mock_settings:
        mock_settings.rapidapi_key = "test_key"
        mock_settings.zillow_api_base_url = "https://test.api.com"
        mock_settings.zillow_api_host = "test.api.com"

        with patch("src.mcp_servers.real_estate_server.get_property_details") as mock_details:
            mock_property = Property(
                id=property_id,
                address="123 Main St",
                city="Austin",
                state="TX",
                zip_code="78701",
                price=500000,
                bedrooms=3,
                bathrooms=2.5,
                square_feet=2000,
                property_type="house",
                listing_url="https://zillow.com/prop/1",
                image_url="https://example.com/img1.jpg",
            )
            mock_details.return_value = mock_property

            with patch("src.mcp_servers.real_estate_server._make_api_request") as mock_api:
                mock_api.return_value = {
                    "photos": [
                        {"url": "https://example.com/img1.jpg"},
                        {"url": "https://example.com/img2.jpg"},
                    ]
                }

                photos = await get_property_photos(property_id)

                assert isinstance(photos, list)
                assert len(photos) > 0
                assert all(isinstance(url, str) for url in photos)
                assert all(url.startswith("http") for url in photos)


@pytest.mark.asyncio
async def test_get_property_photos_invalid_id():
    """Test error handling for invalid property ID."""
    with pytest.raises(ValueError, match="property_id is required"):
        await get_property_photos("")


@pytest.mark.asyncio
async def test_get_similar_properties():
    """Test finding similar properties."""
    property_id = "test_property_123"

    with patch("src.mcp_servers.real_estate_server.settings") as mock_settings:
        mock_settings.rapidapi_key = "test_key"
        mock_settings.zillow_api_base_url = "https://test.api.com"
        mock_settings.zillow_api_host = "test.api.com"

        with patch("src.mcp_servers.real_estate_server.get_property_details") as mock_details:
            mock_property = Property(
                id=property_id,
                address="123 Main St",
                city="Austin",
                state="TX",
                zip_code="78701",
                price=500000,
                bedrooms=3,
                bathrooms=2.5,
                square_feet=2000,
                property_type="house",
                listing_url="https://zillow.com/prop/1",
            )
            mock_details.return_value = mock_property

            with patch("src.mcp_servers.real_estate_server.search_properties") as mock_search:
                mock_search.return_value = [
                    Property(
                        id="prop_2",
                        address="456 Oak Ave",
                        city="Austin",
                        state="TX",
                        zip_code="78701",
                        price=520000,
                        bedrooms=3,
                        bathrooms=2.5,
                        square_feet=2100,
                        property_type="house",
                        listing_url="https://zillow.com/prop/2",
                    )
                ]

                similar = await get_similar_properties(property_id, limit=5)

                assert isinstance(similar, list)
                assert len(similar) <= 5
                assert all(isinstance(p, Property) for p in similar)
                # Should not include the reference property
                assert all(p.id != property_id for p in similar)


@pytest.mark.asyncio
async def test_get_similar_properties_invalid_limit():
    """Test error handling for invalid limit."""
    with patch("src.mcp_servers.real_estate_server.settings") as mock_settings:
        mock_settings.rapidapi_key = "test_key"
        mock_settings.zillow_api_base_url = "https://test.api.com"
        mock_settings.zillow_api_host = "test.api.com"

        with patch("src.mcp_servers.real_estate_server.get_property_details") as mock_details:
            mock_property = Property(
                id="test_id",
                address="123 Main St",
                city="Austin",
                state="TX",
                zip_code="78701",
                price=500000,
                bedrooms=3,
                bathrooms=2.5,
                square_feet=2000,
                property_type="house",
                listing_url="https://zillow.com/prop/1",
            )
            mock_details.return_value = mock_property

            with pytest.raises(ValueError, match="limit must be between"):
                await get_similar_properties("test_id", limit=0)

            with pytest.raises(ValueError, match="limit must be between"):
                await get_similar_properties("test_id", limit=100)


def test_generate_mock_properties():
    """Test mock property generation."""
    params = PropertySearchParams(
        location="Austin, TX",
        max_price=600000,
        bedrooms=3,
    )

    mock_props = _generate_mock_properties(params)

    assert len(mock_props) > 0
    assert all(isinstance(p, Property) for p in mock_props)
    assert all(p.bedrooms == 3 for p in mock_props)
    assert all(p.price <= 600000 for p in mock_props)


@pytest.mark.asyncio
async def test_search_properties_caching():
    """Test that search results are cached."""
    params = PropertySearchParams(location="Austin, TX", max_price=600000)

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
                    }
                ]
            }

            # First call
            results1 = await search_properties(params)

            # Second call should use cache
            results2 = await search_properties(params)

            # Should only call API once due to caching
            assert mock_api.call_count == 1
            assert len(results1) == len(results2)
            assert results1[0].id == results2[0].id


@pytest.mark.asyncio
async def test_search_properties_with_all_filters():
    """Test search with all filters applied."""
    params = PropertySearchParams(
        location="Austin, TX",
        min_price=300000,
        max_price=600000,
        bedrooms=3,
        bathrooms=2.5,
        property_type="house",
    )

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
                        "price": 450000,
                        "bedrooms": 3,
                        "bathrooms": 2.5,
                        "livingArea": 2000,
                        "propertyType": "house",
                        "hdpUrl": "https://zillow.com/prop/1",
                    }
                ]
            }

            results = await search_properties(params)

            assert isinstance(results, list)
            assert all(isinstance(p, Property) for p in results)
            if results:
                assert all(p.price >= 300000 for p in results)
                assert all(p.price <= 600000 for p in results)

