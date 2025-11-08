"""Real Estate Data MCP Server.

This server provides tools for searching and retrieving real estate property data
from external APIs (Zillow via RapidAPI).
"""

import os
import asyncio
import time
from typing import List, Optional
from functools import lru_cache
from datetime import datetime, timedelta

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from src.utils.config import get_settings
from src.utils.logging import setup_logging

# Initialize logger
logger = setup_logging(__name__)

# Initialize MCP server
mcp = FastMCP("Real Estate Data Server")

# Get settings
settings = get_settings()

# Simple in-memory cache with TTL
_cache: dict = {}
_cache_ttl: dict = {}


def _get_cache_key(prefix: str, **kwargs) -> str:
    """Generate cache key from prefix and kwargs."""
    sorted_kwargs = sorted(kwargs.items())
    key_parts = [prefix] + [f"{k}:{v}" for k, v in sorted_kwargs]
    return "|".join(key_parts)


def _get_cached(key: str, ttl_seconds: int = 300) -> Optional[dict]:
    """Get value from cache if not expired."""
    if key in _cache:
        if key in _cache_ttl:
            if datetime.now() < _cache_ttl[key]:
                logger.debug(f"Cache hit for key: {key}")
                return _cache[key]
            else:
                # Expired, remove it
                del _cache[key]
                del _cache_ttl[key]
    return None


def _set_cache(key: str, value: dict, ttl_seconds: int = 300) -> None:
    """Set value in cache with TTL."""
    _cache[key] = value
    _cache_ttl[key] = datetime.now() + timedelta(seconds=ttl_seconds)
    logger.debug(f"Cached value for key: {key} with TTL: {ttl_seconds}s")


async def _make_api_request(
    url: str, params: dict, max_retries: int = 3, retry_delay: float = 1.0
) -> dict:
    """
    Make HTTP request with retry logic and exponential backoff.

    Args:
        url: API endpoint URL
        params: Request parameters
        max_retries: Maximum number of retry attempts
        retry_delay: Initial retry delay in seconds

    Returns:
        JSON response as dictionary

    Raises:
        httpx.HTTPError: If request fails after all retries
        ValueError: If API key is missing
    """
    if not settings.rapidapi_key:
        raise ValueError("RAPIDAPI_KEY not configured")

    headers = {
        "X-RapidAPI-Key": settings.rapidapi_key,
        "X-RapidAPI-Host": settings.zillow_api_host,
    }

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limited - wait longer
                wait_time = retry_delay * (2 ** attempt) * 2
                logger.warning(
                    f"Rate limited. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                    continue
            raise

        except httpx.RequestError as e:
            logger.error(f"Request error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                await asyncio.sleep(wait_time)
                continue
            raise

    raise httpx.HTTPError("Max retries exceeded")


# Pydantic Models
class PropertySearchParams(BaseModel):
    """Parameters for property search."""

    location: str = Field(..., description="City, state, or ZIP code")
    min_price: Optional[int] = Field(None, description="Minimum price in USD")
    max_price: Optional[int] = Field(None, description="Maximum price in USD")
    bedrooms: Optional[int] = Field(None, description="Number of bedrooms")
    bathrooms: Optional[float] = Field(None, description="Number of bathrooms")
    property_type: Optional[str] = Field(
        None, description="Type: house, condo, townhouse"
    )


class Property(BaseModel):
    """Property data model."""

    id: str
    address: str
    city: str
    state: str
    zip_code: str
    price: int
    bedrooms: int
    bathrooms: float
    square_feet: int
    property_type: str
    listing_url: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    year_built: Optional[int] = None
    lot_size: Optional[float] = None


# MCP Tools
@mcp.tool()
async def search_properties(params: PropertySearchParams) -> List[Property]:
    """
    Search for properties matching the given criteria.

    Args:
        params: Search parameters including location, price range, etc.

    Returns:
        List of Property objects matching the criteria

    Raises:
        ValueError: If search parameters are invalid
        httpx.HTTPError: If API request fails

    Example:
        >>> params = PropertySearchParams(
        ...     location="Austin, TX",
        ...     max_price=600000,
        ...     bedrooms=3
        ... )
        >>> properties = await search_properties(params)
        >>> len(properties)
        12
    """
    logger.info(f"Searching properties with params: {params}")

    # Validate location
    if not params.location or len(params.location.strip()) < 2:
        raise ValueError("Invalid location: must be at least 2 characters")

    # Check cache first
    cache_key = _get_cache_key("search", **params.model_dump())
    cached_result = _get_cached(cache_key, ttl_seconds=300)  # 5 minute TTL
    if cached_result:
        logger.info(f"Returning cached results for: {params.location}")
        return [Property(**p) for p in cached_result.get("properties", [])]

    try:
        # Validate API key is configured
        if not settings.rapidapi_key or settings.rapidapi_key == "your_rapidapi_key_here":
            logger.error(
                "RAPIDAPI_KEY not configured. Please set RAPIDAPI_KEY in .env file. "
                "Visit https://rapidapi.com/apidojo/api/zillow-com1 for API access."
            )
            raise ValueError(
                "RAPIDAPI_KEY not configured. Please set your RapidAPI key in .env file"
            )

        # Prepare API request parameters for Zillow API via RapidAPI
        # Use the /search endpoint which supports location-based search
        api_params = {
            "location": params.location,
            "home_status": "FOR_SALE",
            "sort": "DEFAULT",
            "listing_type": "BY_AGENT",
            "page": "1",
        }
        
        # Add optional filters if provided
        # Note: The API may support additional filters - check documentation
        # For now, we'll filter results after receiving them
        
        # Use the new API search endpoint
        # Try /search/byaddress first, fallback to /search if needed
        from urllib.parse import quote
        search_endpoint = quote("search/byaddress", safe="")
        url = f"{settings.zillow_api_base_url}/{search_endpoint}"
        logger.info(f"Calling Zillow API: {url} with params: {api_params}")
        
        response_data = None
        try:
            response_data = await _make_api_request(url, api_params)
            logger.info(f"API call successful, received response")
        except httpx.HTTPStatusError as e:
            # If /search/byaddress doesn't work (404), try the old /search endpoint
            if e.response.status_code == 404:
                logger.warning(f"Endpoint /search/byaddress not found (404), trying /search")
                url = f"{settings.zillow_api_base_url}/search"
                try:
                    response_data = await _make_api_request(url, api_params)
                    logger.info(f"API call successful with fallback endpoint /search")
                except Exception as fallback_error:
                    error_status = e.response.status_code
                    error_msg = str(fallback_error)
                    logger.error(f"API request failed with status {error_status}: {error_msg}")
                    return []
            else:
                error_status = e.response.status_code
                error_msg = str(e)
                logger.error(f"API request failed with status {error_status}: {error_msg}")
                return []
        except Exception as e:
            logger.error(f"Unexpected error calling Zillow API: {e}")
            return []

        # Parse real API response and convert to Property objects
        # The /search endpoint returns: {status: "OK", data: [...], ...}
        properties = []
        
        if not isinstance(response_data, dict):
            logger.warning(f"Unexpected response type: {type(response_data)}")
            return []
        
        # Check response status
        status = response_data.get("status", "")
        if status != "OK":
            logger.warning(f"API returned non-OK status: {status}")
            # Continue anyway in case data is still present
        
        # Extract properties from data array
        props_list = response_data.get("data", [])
        if not props_list:
            logger.warning(f"No properties found in API response data array")
            logger.debug(f"Response keys: {list(response_data.keys())}")
            return []
        
        logger.info(f"Found {len(props_list)} properties in API response")

        # Filter properties based on search criteria (since API doesn't support all filters)
        # Make filtering more flexible - allow some tolerance
        filtered_props = []
        sample_props = []  # For debugging
        
        for prop_data in props_list:
            # Sample first few properties for debugging
            if len(sample_props) < 3:
                sample_props.append({
                    "bedrooms": prop_data.get("bedrooms"),
                    "bathrooms": prop_data.get("bathrooms"),
                    "homeType": prop_data.get("homeType"),
                    "price": prop_data.get("price"),
                })
            
            # Apply filters if provided - be flexible
            # Bedrooms: allow ±1 bedroom flexibility (e.g., 3 bedrooms can match 2-4)
            if params.bedrooms:
                prop_bedrooms = prop_data.get("bedrooms")
                if prop_bedrooms is None:
                    # If bedrooms not in API response, skip this filter
                    pass
                elif abs(prop_bedrooms - params.bedrooms) > 1:
                    continue
            
            # Bathrooms: allow ±0.5 bathroom flexibility
            if params.bathrooms:
                prop_bathrooms = prop_data.get("bathrooms")
                if prop_bathrooms is None:
                    # If bathrooms not in API response, skip this filter
                    pass
                elif abs(prop_bathrooms - params.bathrooms) > 0.5:
                    continue
            
            # Price filters: strict
            if params.min_price and prop_data.get("price", 0) < params.min_price:
                continue
            if params.max_price and prop_data.get("price", 0) > params.max_price:
                continue
            
            # Property type: flexible matching
            if params.property_type:
                home_type = prop_data.get("homeType", "").upper()
                property_type_upper = params.property_type.upper()
                # Map property types
                type_mapping = {
                    "HOUSE": ["SINGLE_FAMILY", "MULTI_FAMILY"],
                    "CONDO": ["CONDO", "CONDOMINIUM"],
                    "TOWNHOUSE": ["TOWNHOUSE", "TOWN_HOUSE"],
                }
                allowed_types = type_mapping.get(property_type_upper, [property_type_upper])
                # Check if home_type matches any allowed type
                if home_type not in allowed_types:
                    # If no match, skip this property
                    continue
            
            filtered_props.append(prop_data)
        
        # Log sample properties for debugging
        if sample_props:
            logger.info(f"Sample properties from API: {sample_props[:2]}")
        logger.info(f"Filtered to {len(filtered_props)} properties matching criteria (from {len(props_list)} total)")
        
        # If no properties match filters but we have properties, return top results anyway
        # This helps with edge cases where filters might be too strict
        if len(filtered_props) == 0 and len(props_list) > 0:
            logger.warning(
                f"No properties matched exact filters. Returning top {min(10, len(props_list))} properties "
                f"without strict filtering to show available options."
            )
            # Return properties with relaxed filtering - only apply price filters
            for prop_data in props_list[:10]:
                if params.min_price and prop_data.get("price", 0) < params.min_price:
                    continue
                if params.max_price and prop_data.get("price", 0) > params.max_price:
                    continue
                filtered_props.append(prop_data)
        
        for prop_data in filtered_props[:20]:  # Limit to 20 results
            try:
                # Parse address - API returns address as string and also has separate fields
                address_str = prop_data.get("address", "")
                street_address = prop_data.get("streetAddress", "")
                city = prop_data.get("city", "")
                state = prop_data.get("state", "")
                zip_code = str(prop_data.get("zipcode", ""))
                
                # If address string exists but separate fields don't, parse from string
                if address_str and not street_address:
                    address_parts = address_str.split(",")
                    if len(address_parts) > 0:
                        street_address = address_parts[0].strip()
                    if len(address_parts) > 1:
                        city = address_parts[1].strip()
                    if len(address_parts) > 2:
                        state_zip = address_parts[2].strip().split()
                        if len(state_zip) > 0:
                            state = state_zip[0]
                        if len(state_zip) > 1:
                            zip_code = state_zip[1]

                # Extract price - API returns as number
                price = int(prop_data.get("price", 0))
                
                # Extract square feet - API uses livingArea
                square_feet = int(prop_data.get("livingArea", 0))
                
                # Extract property type - API uses homeType
                home_type = prop_data.get("homeType", "SINGLE_FAMILY")
                # Map to our property types
                property_type_map = {
                    "SINGLE_FAMILY": "house",
                    "CONDO": "condo",
                    "TOWNHOUSE": "townhouse",
                    "MULTI_FAMILY": "house",
                }
                property_type = property_type_map.get(home_type, "house")

                # Extract image URL - API uses imgSrc
                image_url = prop_data.get("imgSrc", "") or ""
                
                # Extract bedrooms and bathrooms
                bedrooms = int(prop_data.get("bedrooms", 0))
                bathrooms = float(prop_data.get("bathrooms", 0))

                # Extract listing URL - API uses detailUrl
                detail_url = prop_data.get("detailUrl", "")
                listing_url = detail_url or ""

                # Build Property object with all required fields
                zpid = prop_data.get("zpid")
                property_id = str(zpid) if zpid else f"prop_{len(properties)}"
                
                # Build full address
                address_parts = [p for p in [street_address, city, state, zip_code] if p]
                property_address = ", ".join(address_parts) if address_parts else address_str or "Address not available"
                
                property_obj = Property(
                    id=property_id,
                    address=property_address,
                    city=city or "",
                    state=state or "",
                    zip_code=zip_code,
                    price=price,
                    bedrooms=bedrooms,
                    bathrooms=bathrooms,
                    square_feet=square_feet,
                    property_type=property_type,
                    listing_url=listing_url,
                    description=prop_data.get("description") or prop_data.get("statusText") or "",
                    image_url=image_url,
                )
                properties.append(property_obj)
                logger.debug(f"Parsed property: {property_obj.id} - {property_obj.address}")

            except Exception as e:
                logger.warning(f"Error parsing property data: {e}. Raw data: {prop_data}")
                continue

        # Cache results
        _set_cache(
            cache_key, {"properties": [p.model_dump() for p in properties]}, ttl_seconds=300
        )

        logger.info(f"Found {len(properties)} properties for: {params.location}")
        return properties

    except httpx.HTTPError as e:
        logger.error(f"API request failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in search_properties: {e}")
        raise


def _generate_mock_properties(params: PropertySearchParams) -> List[Property]:
    """
    Generate mock property data for testing purposes only.
    
    This function is used exclusively in unit tests when mocking API responses.
    Production code should never use this function - it should raise an error
    if API keys are not configured.
    """
    base_price = params.max_price or 500000
    mock_properties = []

    for i in range(5):
        price = base_price - (i * 20000)
        if params.min_price and price < params.min_price:
            continue

        property_obj = Property(
            id=f"mock_prop_{i+1}",
            address=f"{100 + i} Main Street",
            city=params.location.split(",")[0].strip() if "," in params.location else "Austin",
            state=params.location.split(",")[1].strip() if "," in params.location else "TX",
            zip_code="78701",
            price=price,
            bedrooms=params.bedrooms or 3,
            bathrooms=params.bathrooms or 2.5,
            square_feet=1500 + (i * 200),
            property_type=params.property_type or "house",
            listing_url=f"https://example.com/property/{i+1}",
            description=f"Beautiful {params.property_type or 'house'} in {params.location}",
            image_url=f"https://example.com/images/prop_{i+1}.jpg",
            year_built=1990 + (i * 5),
            lot_size=0.25 + (i * 0.05),
        )
        mock_properties.append(property_obj)

    return mock_properties


@mcp.tool()
async def get_property_details(property_id: str) -> Property:
    """
    Get detailed information about a specific property.

    Args:
        property_id: Unique property identifier

    Returns:
        Property object with full details

    Raises:
        ValueError: If property_id is invalid
        httpx.HTTPError: If API request fails
    """
    logger.info(f"Getting property details for: {property_id}")

    if not property_id or not property_id.strip():
        raise ValueError("property_id is required")

    # Check cache
    cache_key = _get_cache_key("details", property_id=property_id)
    cached_result = _get_cached(cache_key, ttl_seconds=600)  # 10 minute TTL
    if cached_result:
        logger.info(f"Returning cached property details for: {property_id}")
        return Property(**cached_result)

    # Validate API key
    if not settings.rapidapi_key or settings.rapidapi_key == "your_rapidapi_key_here":
        logger.error("RAPIDAPI_KEY not configured")
        raise ValueError("RAPIDAPI_KEY not configured. Please set your RapidAPI key in .env file")

    try:
        # Call real Zillow API
        # Try property ID endpoint first
        url = f"{settings.zillow_api_base_url}/property-details-zpid"
        logger.info(f"Fetching property details from Zillow API for: {property_id}")
        
        try:
            response_data = await _make_api_request(url, {"zpid": property_id})
        except httpx.HTTPStatusError as e:
            # If zpid endpoint doesn't exist, try alternative endpoint
            if e.response.status_code == 404:
                logger.info("ZPID endpoint not available, trying alternative endpoint")
                alt_url = f"{settings.zillow_api_base_url}/property"
                response_data = await _make_api_request(alt_url, {"zpid": property_id})
            else:
                raise

        # Parse real API response with robust error handling
        address_data = response_data.get("address", {})
        if isinstance(address_data, str):
            address_parts = address_data.split(",")
            street_address = address_parts[0].strip() if address_parts else ""
            city = address_parts[1].strip() if len(address_parts) > 1 else ""
            state = address_parts[2].strip() if len(address_parts) > 2 else ""
            zip_code = ""
        else:
            street_address = address_data.get("streetAddress") or address_data.get("street", "") or ""
            city = address_data.get("city") or ""
            state = address_data.get("state") or ""
            zip_code = str(address_data.get("zipcode") or address_data.get("zipCode") or "")

        # Extract price
        price = 0
        price_value = response_data.get("price") or response_data.get("listPrice") or response_data.get("unformattedPrice")
        if price_value:
            if isinstance(price_value, (int, float)):
                price = int(price_value)
            elif isinstance(price_value, str):
                price_str = price_value.replace("$", "").replace(",", "").strip()
                try:
                    price = int(float(price_str))
                except ValueError:
                    logger.warning(f"Could not parse price: {price_value}")

        # Extract square feet
        square_feet = (
            response_data.get("livingArea")
            or response_data.get("sqft")
            or response_data.get("squareFeet")
            or 0
        )
        if isinstance(square_feet, str):
            try:
                square_feet = int(float(square_feet.replace(",", "")))
            except ValueError:
                square_feet = 0

        # Extract image URL
        image_url = (
            response_data.get("imgSrc")
            or response_data.get("imageUrl")
            or (response_data.get("photos", [{}])[0].get("url", "") if response_data.get("photos") else "")
        )

        # Extract listing URL
        listing_url = (
            response_data.get("hdpUrl")
            or response_data.get("url")
            or response_data.get("detailUrl")
            or ""
        )
        if listing_url and not listing_url.startswith("http"):
            listing_url = f"https://www.zillow.com{listing_url}"

        property_obj = Property(
            id=str(response_data.get("zpid") or property_id),
            address=street_address or "Address not available",
            city=city or "",
            state=state or "",
            zip_code=zip_code,
            price=price,
            bedrooms=int(response_data.get("bedrooms") or response_data.get("beds") or 0),
            bathrooms=float(response_data.get("bathrooms") or response_data.get("baths") or 0),
            square_feet=int(square_feet),
            property_type=(response_data.get("propertyType") or response_data.get("homeType") or "house").lower(),
            listing_url=listing_url,
            description=response_data.get("description") or response_data.get("statusText") or "",
            image_url=image_url,
            year_built=response_data.get("yearBuilt"),
            lot_size=response_data.get("lotSize") or response_data.get("lotSizeValue"),
        )

        # Cache result
        _set_cache(cache_key, property_obj.model_dump(), ttl_seconds=600)

        logger.info(f"Retrieved property details for: {property_id}")
        return property_obj

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise ValueError(f"Property not found: {property_id}")
        raise
    except httpx.HTTPError as e:
        logger.error(f"API request failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_property_details: {e}")
        raise


@mcp.tool()
async def get_property_photos(property_id: str) -> List[str]:
    """
    Retrieve property images and media.

    Args:
        property_id: Unique property identifier

    Returns:
        List of image URLs

    Raises:
        ValueError: If property_id is invalid
    """
    logger.info(f"Getting property photos for: {property_id}")

    if not property_id or not property_id.strip():
        raise ValueError("property_id is required")

    # Validate API key
    if not settings.rapidapi_key or settings.rapidapi_key == "your_rapidapi_key_here":
        logger.error("RAPIDAPI_KEY not configured")
        raise ValueError("RAPIDAPI_KEY not configured. Please set your RapidAPI key in .env file")

    try:
        # Get property details which includes image data
        property_details = await get_property_details(property_id)
        photos = []

        # Add main image if available
        if property_details.image_url:
            photos.append(property_details.image_url)

        # Try to get additional photos from API
        try:
            url = f"{settings.zillow_api_base_url}/property"
            response_data = await _make_api_request(url, {"zpid": property_id})
            
            # Extract all photos from response
            photos_list = response_data.get("photos", [])
            if isinstance(photos_list, list):
                for photo in photos_list:
                    if isinstance(photo, dict):
                        photo_url = photo.get("url") or photo.get("href") or photo.get("src")
                    elif isinstance(photo, str):
                        photo_url = photo
                    else:
                        continue
                    
                    if photo_url and photo_url not in photos:
                        photos.append(photo_url)
            
            # Also check for imageGallery
            gallery = response_data.get("imageGallery", [])
            if isinstance(gallery, list):
                for img in gallery:
                    img_url = img.get("url") if isinstance(img, dict) else img
                    if img_url and img_url not in photos:
                        photos.append(img_url)
                        
        except Exception as e:
            logger.warning(f"Could not fetch additional photos: {e}")

        return photos if photos else []

    except Exception as e:
        logger.error(f"Error getting property photos: {e}")
        raise


@mcp.tool()
async def get_similar_properties(
    property_id: str, limit: int = 10
) -> List[Property]:
    """
    Find comparable properties.

    Args:
        property_id: Reference property identifier
        limit: Maximum number of results (default: 10)

    Returns:
        List of similar Property objects

    Raises:
        ValueError: If property_id is invalid
    """
    logger.info(f"Finding similar properties to: {property_id} (limit: {limit})")

    if not property_id or not property_id.strip():
        raise ValueError("property_id is required")

    if limit < 1 or limit > 50:
        raise ValueError("limit must be between 1 and 50")

    try:
        # Get reference property details
        reference_property = await get_property_details(property_id)

        # Search for similar properties in the same area
        search_params = PropertySearchParams(
            location=f"{reference_property.city}, {reference_property.state}",
            min_price=int(reference_property.price * 0.8),
            max_price=int(reference_property.price * 1.2),
            bedrooms=reference_property.bedrooms,
            property_type=reference_property.property_type,
        )

        similar_properties = await search_properties(search_params)

        # Filter out the reference property and limit results
        filtered = [
            p for p in similar_properties if p.id != property_id
        ][:limit]

        logger.info(f"Found {len(filtered)} similar properties")
        return filtered

    except Exception as e:
        logger.error(f"Error finding similar properties: {e}")
        raise


# Server entry point
if __name__ == "__main__":
    import uvicorn

    port = settings.mcp_server_port_real_estate
    logger.info(f"Starting Real Estate MCP Server on port {port}")
    uvicorn.run(mcp.app, host=settings.mcp_server_host, port=port)

