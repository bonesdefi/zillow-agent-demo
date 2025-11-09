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
    url: str, params: dict, max_retries: int = 3, retry_delay: float = 1.0, use_market_api: bool = False, use_zillow_com_api: bool = False
) -> dict:
    """
    Make HTTP request with retry logic and exponential backoff.

    Args:
        url: API endpoint URL
        params: Request parameters
        max_retries: Maximum number of retry attempts
        retry_delay: Initial retry delay in seconds
        use_market_api: If True, use zillow-working-api instead of real-time-zillow-data
        use_zillow_com_api: If True, use zillow-com1 API (new primary API)

    Returns:
        JSON response as dictionary

    Raises:
        httpx.HTTPError: If request fails after all retries
        ValueError: If API key is missing
    """
    if not settings.rapidapi_key:
        raise ValueError("RAPIDAPI_KEY not configured")

    # Choose API host based on flags
    if use_zillow_com_api:
        api_host = settings.zillow_com_api_host
    elif use_market_api:
        api_host = settings.zillow_market_api_host
    else:
        api_host = settings.zillow_api_host
    
    headers = {
        "X-RapidAPI-Key": settings.rapidapi_key,
        "X-RapidAPI-Host": api_host,
    }
    
    # Log request details for debugging (mask API key)
    logger.debug(f"Making API request to: {url}")
    logger.debug(f"API Host: {api_host}")
    logger.debug(f"Using Market API: {use_market_api}, Using Zillow.com API: {use_zillow_com_api}")
    logger.info(f"Request params: {params}")
    logger.info(f"Request headers: X-RapidAPI-Host={headers['X-RapidAPI-Host']}, X-RapidAPI-Key={headers['X-RapidAPI-Key'][:15]}...")

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers, params=params)
                logger.info(f"Response status: {response.status_code}")
                logger.info(f"Response headers: {dict(response.headers)}")
                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limited - check for Retry-After header, or use longer exponential backoff
                retry_after = e.response.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait_time = float(retry_after)
                        logger.info(f"API specified Retry-After: {wait_time}s")
                    except ValueError:
                        wait_time = 30.0  # Default to 30 seconds if header is invalid
                else:
                    # Longer exponential backoff for rate limits: 10s, 20s, 40s
                    wait_time = 10.0 * (2 ** attempt)
                
                logger.warning(
                    f"Rate limited. Waiting {wait_time:.1f}s before retry {attempt + 1}/{max_retries}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                    continue
                # If we've exhausted retries, raise the error
                logger.error(f"Rate limit persists after {max_retries} retries")
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


# Internal implementation (can be called directly by agents)
async def _search_properties_impl(params: PropertySearchParams) -> List[Property]:
    """
    Internal implementation of property search.

    This function contains the actual implementation and can be called directly
    by agents without going through the MCP tool wrapper.

    Args:
        params: Search parameters including location, price range, etc.

    Returns:
        List of Property objects matching the criteria

    Raises:
        ValueError: If search parameters are invalid
        httpx.HTTPError: If API request fails
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

        # Try multiple endpoints with fallback logic
        # Primary: real-time-zillow-data /search endpoint (returns multiple properties)
        # Fallbacks: alternative endpoints if primary fails
        
        # Prepare API request parameters for real-time-zillow-data /search endpoint
        api_params = {
            "location": params.location,
            "home_status": "FOR_SALE",
            "sort": "DEFAULT",
            "listing_type": "BY_AGENT",
            "page": "1",
        }
        
        # List of endpoints to try in order
        # NEW: zillow-com1.p.rapidapi.com API with /propertyExtendedSearch endpoint (PRIMARY)
        # This is the new paid API that supports location-based property search
        
        # Map property type to API format
        home_type_map = {
            "house": "Houses",
            "houses": "Houses",
            "condo": "Condos",
            "condos": "Condos",
            "townhouse": "Townhomes",
            "townhomes": "Townhomes",
        }
        api_home_type = home_type_map.get(params.property_type.lower() if params.property_type else "", "Houses")
        
        # Build search parameters for zillow-com1 API
        search_params = {
            "location": params.location,
            "status": "forSale",  # forSale, forRent, recentlySold
        }
        
        # Add optional filters
        if params.property_type:
            search_params["home_type"] = api_home_type
        if params.bedrooms:
            search_params["bedsMin"] = str(params.bedrooms)
        if params.bathrooms:
            search_params["bathsMin"] = str(int(params.bathrooms))
        if params.min_price:
            search_params["priceMin"] = str(params.min_price)
        if params.max_price:
            search_params["priceMax"] = str(params.max_price)
        
        endpoints_to_try = [
            # PRIMARY: zillow-com1 API /propertyExtendedSearch (supports location search)
            {
                "url": f"{settings.zillow_com_api_base_url}/propertyExtendedSearch",
                "params": search_params,
                "use_market_api": False,
                "use_zillow_com_api": True,
                "name": "zillow-com1 /propertyExtendedSearch"
            },
        ]
        
        response_data = None
        last_error = None
        
        # Try each endpoint until one works
        for endpoint_config in endpoints_to_try:
            url = endpoint_config["url"]
            endpoint_params = endpoint_config["params"]
            use_market_api = endpoint_config.get("use_market_api", False)
            use_zillow_com_api = endpoint_config.get("use_zillow_com_api", False)
            endpoint_name = endpoint_config["name"]
            
            
            logger.info(f"Trying endpoint: {endpoint_name} at {url}")
            logger.info(f"Request params: {endpoint_params}")
            logger.info(f"Using API key: {settings.rapidapi_key[:15]}... (length: {len(settings.rapidapi_key)})")
            
            # Log API configuration for debugging
            if use_zillow_com_api:
                logger.info(f"API Configuration - Using zillow-com1 API")
                logger.info(f"  Base URL: {settings.zillow_com_api_base_url}")
                logger.info(f"  Host: {settings.zillow_com_api_host}")
            elif use_market_api:
                logger.info(f"API Configuration - Using zillow-working-api")
                logger.info(f"  Base URL: {settings.zillow_market_api_base_url}")
                logger.info(f"  Host: {settings.zillow_market_api_host}")
            else:
                logger.info(f"API Configuration - Using real-time-zillow-data API")
                logger.info(f"  Base URL: {settings.zillow_api_base_url}")
                logger.info(f"  Host: {settings.zillow_api_host}")
            
            try:
                response_data = await _make_api_request(
                    url, 
                    endpoint_params, 
                    use_market_api=use_market_api,
                    use_zillow_com_api=use_zillow_com_api
                )
                logger.info(f"API call successful using {endpoint_name}, received response")
                break  # Success! Exit the loop
                
            except httpx.HTTPStatusError as e:
                error_status = e.response.status_code
                error_msg = str(e)
                last_error = e
                
                # Try to extract error details from response
                error_response_text = ""
                try:
                    error_response_text = e.response.text[:500] if e.response.text else ""
                    logger.warning(f"Endpoint {endpoint_name} failed with status {error_status}")
                    logger.warning(f"Response: {error_response_text}")
                except:
                    logger.warning(f"Endpoint {endpoint_name} failed with status {error_status}: {error_msg}")
                
                # For rate limiting (429), try next endpoint but log it
                if error_status == 429:
                    logger.warning(f"Rate limited on {endpoint_name}, trying next endpoint...")
                    continue
                # For 403/404, try next endpoint (endpoint might not exist or be accessible)
                elif error_status in (403, 404):
                    logger.warning(f"Endpoint {endpoint_name} returned {error_status} - endpoint may not exist or API key may not have access. Trying next endpoint...")
                    if error_response_text:
                        logger.info(f"Error response from {endpoint_name}: {error_response_text}")
                    continue
                # For authentication errors (401), don't try other endpoints
                elif error_status == 401:
                    raise ValueError(
                        "API authentication failed. Please check that your RAPIDAPI_KEY is correct and active. "
                        "The API key should be set in your .env file."
                    )
                # For server errors (5xx), try next endpoint
                elif error_status >= 500:
                    logger.warning(f"Server error on {endpoint_name}, trying next endpoint...")
                    continue
                # For other errors, continue to next endpoint
                else:
                    logger.warning(f"Unexpected error {error_status} on {endpoint_name}, trying next endpoint...")
                    continue
                    
            except httpx.RequestError as e:
                logger.warning(f"Network error on {endpoint_name}: {e}, trying next endpoint...")
                last_error = e
                continue
            except Exception as e:
                logger.warning(f"Unexpected error on {endpoint_name}: {e}, trying next endpoint...")
                last_error = e
                continue
        
        # If all endpoints failed, raise an error
        if response_data is None:
            error_details = []
            if last_error:
                if isinstance(last_error, httpx.HTTPStatusError):
                    error_details.append(f"Last error: HTTP {last_error.response.status_code}")
                    try:
                        error_body = last_error.response.json()
                        error_details.append(f"Response: {error_body}")
                    except:
                        error_details.append(f"Response text: {last_error.response.text[:200]}")
                else:
                    error_details.append(f"Last error: {str(last_error)}")
            
            # Check if the main issue is subscription-related
            subscription_issue = False
            if last_error and isinstance(last_error, httpx.HTTPStatusError):
                if last_error.response.status_code == 403:
                    try:
                        error_body = last_error.response.json()
                        if "not subscribed" in str(error_body).lower():
                            subscription_issue = True
                    except:
                        pass
            
            if subscription_issue:
                error_message = (
                    f"❌ API SUBSCRIPTION ISSUE DETECTED\n\n"
                    + f"The zillow-com1 API endpoint failed. The main issue is:\n"
                    + f"⚠️  You are NOT subscribed to the 'Zillow.com' API or API key is invalid\n\n"
                    + f"Error details:\n"
                    + "\n".join(error_details) + "\n\n"
                    + f"SOLUTION:\n"
                    + f"1. Go to RapidAPI Dashboard: https://rapidapi.com/developer/dashboard\n"
                    + f"2. Subscribe to 'Zillow.com' API (zillow-com1.p.rapidapi.com)\n"
                    + f"3. Verify your RAPIDAPI_KEY has access to the Zillow.com API\n"
                    + f"4. The '/propertyExtendedSearch' endpoint requires an active subscription\n"
                    + f"5. Verify ZILLOW_COM_API_BASE_URL and ZILLOW_COM_API_HOST are set in secrets\n\n"
                    + f"Endpoint tried:\n"
                    + "\n".join([f"  - {e['name']}" for e in endpoints_to_try])
                )
            else:
                error_message = (
                    f"❌ PROPERTY SEARCH FAILED\n\n"
                    + f"The zillow-com1 API endpoint failed to return results.\n\n"
                    + f"Error details:\n"
                    + "\n".join(error_details) + "\n\n"
                    + f"Endpoint tried:\n"
                    + f"- {', '.join([e['name'] for e in endpoints_to_try])}\n\n"
                    + "TROUBLESHOOTING:\n"
                    + "1. Check that your RAPIDAPI_KEY is correct and active\n"
                    + "2. Verify you have an active subscription to the 'Zillow.com' API (zillow-com1.p.rapidapi.com)\n"
                    + f"3. Check the API endpoint is accessible: {settings.zillow_com_api_base_url}/propertyExtendedSearch\n"
                    + "4. Verify ZILLOW_COM_API_BASE_URL and ZILLOW_COM_API_HOST are set in Streamlit secrets\n"
                    + "5. Check RapidAPI dashboard for available endpoints and quota status\n"
                    + "6. The endpoint may be rate-limited - wait a few minutes and try again"
                )
            logger.error(error_message)
            raise ValueError(error_message)

        # Parse real API response and convert to Property objects
        # Handle different API response formats:
        # 1. zillow-com1 /propertyExtendedSearch - returns properties array
        # 2. real-time-zillow-data /search - returns {data: array} or array
        # 3. Property details response with nearbyHomes array
        properties = []
        
        # Log full response structure for debugging
        logger.info(f"Response type: {type(response_data)}")
        if isinstance(response_data, dict):
            logger.info(f"Response keys: {list(response_data.keys())[:20]}")
            # Log all top-level keys and their types (but limit full response logging)
            for key, value in list(response_data.items())[:10]:
                if isinstance(value, (dict, list)):
                    value_str = f"{len(value)} items" if isinstance(value, list) else "dict"
                else:
                    value_str = str(value)[:200]
                logger.info(f"  {key}: {type(value)} - {value_str}")
        elif isinstance(response_data, list):
            logger.info(f"Response is a list with {len(response_data)} items")
        
        # Extract properties - handle different response structures
        props_list = []
        
        if isinstance(response_data, list):
            # Direct array response
            props_list = response_data
            logger.info("Response is a direct array")
        elif isinstance(response_data, dict):
            # Check if this is a single property object (has zpid, address, etc.)
            if "zpid" in response_data or "address" in response_data:
                # This is a single property, wrap it in a list
                logger.info("Response is a single property object, wrapping in list")
                props_list = [response_data]
            elif "data" in response_data:
                data = response_data.get("data", [])
                if isinstance(data, list):
                    props_list = data
                    logger.info(f"Found properties array in 'data' key with {len(props_list)} items")
                elif isinstance(data, dict) and ("zpid" in data or "address" in data):
                    # Single property in data key
                    props_list = [data]
                    logger.info("Found single property in 'data' key")
            elif "results" in response_data:
                results = response_data.get("results", [])
                if isinstance(results, list):
                    props_list = results
                    logger.info(f"Found properties array in 'results' key with {len(props_list)} items")
                elif isinstance(results, dict) and ("zpid" in results or "address" in results):
                    props_list = [results]
                    logger.info("Found single property in 'results' key")
            elif "properties" in response_data:
                props_list = response_data.get("properties", [])
                logger.info(f"Found properties in 'properties' key: {len(props_list) if isinstance(props_list, list) else 1}")
            elif "nearbyHomes" in response_data:
                # zillow-com1 API property details response includes nearbyHomes array
                nearby_homes = response_data.get("nearbyHomes", [])
                if isinstance(nearby_homes, list):
                    props_list = nearby_homes
                    logger.info(f"Found {len(props_list)} properties in 'nearbyHomes' key")
                else:
                    props_list = []
            elif "error" in response_data or "message" in response_data:
                # Error response
                error_msg = response_data.get("error") or response_data.get("message")
                logger.error(f"API returned error: {error_msg}")
                return []
            else:
                # Try to find any array in the response
                for key, value in response_data.items():
                    if isinstance(value, list) and len(value) > 0:
                        # Check if it looks like a property list
                        if isinstance(value[0], dict) and any(k in value[0] for k in ["address", "price", "zpid", "streetAddress"]):
                            props_list = value
                            logger.info(f"Found properties in response key: {key}")
                            break
                    elif isinstance(value, dict) and ("zpid" in value or "address" in value):
                        # Single property as a dict value
                        props_list = [value]
                        logger.info(f"Found single property in response key: {key}")
                        break
        else:
            logger.warning(f"Unexpected response type: {type(response_data)}")
            return []
        
        if not props_list:
            logger.warning(f"No properties found in API response")
            # Log a sample of the response for debugging (first 500 chars)
            response_sample = str(response_data)[:500] if response_data else "None"
            logger.info(f"Response sample: {response_sample}")
            return []
        
        logger.info(f"Found {len(props_list)} properties in API response")

        # Filter properties based on search criteria (since API doesn't support all filters)
        # Make filtering more flexible - allow some tolerance
        filtered_props = []
        sample_props = []  # For debugging
        
        for prop_data in props_list:
            # Sample first few properties for debugging - log all available fields
            if len(sample_props) < 2:
                # Log all keys in the first property to see what fields are available
                if len(sample_props) == 0:
                    logger.info(f"Sample property keys: {list(prop_data.keys())[:30]}")
                    logger.info(f"Sample property data: {dict(list(prop_data.items())[:10])}")
                sample_props.append({
                    "bedrooms": prop_data.get("bedrooms"),
                    "bathrooms": prop_data.get("bathrooms"),
                    "homeType": prop_data.get("homeType"),
                    "propertyType": prop_data.get("propertyType"),
                    "propertyTypeDimension": prop_data.get("propertyTypeDimension"),
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
            # Note: If propertyType is None, we trust the API's filtering (since we already filtered by home_type in the request)
            if params.property_type:
                # zillow-com1 API uses propertyType (not homeType) - check propertyType first
                home_type = prop_data.get("propertyType") or prop_data.get("homeType") or prop_data.get("home_type")
                if home_type is not None:
                    # Only filter if homeType is present
                    home_type = str(home_type).upper()
                    property_type_upper = params.property_type.upper()
                    # Map property types
                    type_mapping = {
                        "HOUSE": ["SINGLE_FAMILY", "MULTI_FAMILY", "HOUSE", "HOUSES"],
                        "CONDO": ["CONDO", "CONDOMINIUM", "CONDOS"],
                        "TOWNHOUSE": ["TOWNHOUSE", "TOWN_HOUSE", "TOWNHOUSES"],
                    }
                    allowed_types = type_mapping.get(property_type_upper, [property_type_upper])
                    # Check if home_type matches any allowed type
                    if home_type not in allowed_types:
                        # If no match, skip this property
                        continue
                # If homeType is None, trust the API's filtering (we already filtered by home_type in the request)
                # So we don't exclude properties with None homeType
            
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
                # Parse address - zillow-com1 API returns address as string: "Street, City, State ZIP"
                # Also check for nested address object or separate fields
                address_value = prop_data.get("address", "")
                street_address = ""
                city = ""
                state = ""
                zip_code = ""
                
                # Handle different address formats
                if isinstance(address_value, dict):
                    # Nested address object
                    street_address = address_value.get("streetAddress", "") or address_value.get("street", "") or ""
                    city = address_value.get("city", "") or ""
                    state = address_value.get("state", "") or ""
                    zip_code = str(address_value.get("zipcode", "") or address_value.get("zipCode", "") or "")
                elif isinstance(address_value, str) and address_value:
                    # String format: "2309 Aztec Ruin Way, Henderson, NV 89044"
                    address_parts = [part.strip() for part in address_value.split(",")]
                    if len(address_parts) > 0:
                        street_address = address_parts[0]
                    if len(address_parts) > 1:
                        city = address_parts[1]
                    if len(address_parts) > 2:
                        # Last part is "State ZIP" - split by space
                        state_zip = address_parts[2].split()
                        if len(state_zip) > 0:
                            state = state_zip[0]
                        if len(state_zip) > 1:
                            zip_code = state_zip[1]
                
                # Fallback to direct fields if address string parsing didn't work
                if not street_address:
                    street_address = prop_data.get("streetAddress", "") or ""
                if not city:
                    city = prop_data.get("city", "") or ""
                if not state:
                    state = prop_data.get("state", "") or ""
                if not zip_code:
                    zip_code = str(prop_data.get("zipcode", "") or prop_data.get("zipCode", "") or "")

                # Extract price - API returns as number
                price = int(prop_data.get("price", 0))
                
                # Extract square feet - API uses livingArea or livingAreaValue
                square_feet = int(prop_data.get("livingArea", 0) or prop_data.get("livingAreaValue", 0))
                
                # Extract property type - zillow-com1 API uses propertyType (not homeType)
                # Priority: propertyType > homeType > home_type > propertyTypeDimension
                home_type = (
                    prop_data.get("propertyType") or  # Primary field in zillow-com1 API
                    prop_data.get("homeType") or 
                    prop_data.get("home_type") or
                    prop_data.get("propertyTypeDimension")
                )
                
                # Map to our property types
                property_type_map = {
                    "SINGLE_FAMILY": "house",
                    "CONDO": "condo",
                    "TOWNHOUSE": "townhouse",
                    "MULTI_FAMILY": "house",
                    "HOUSE": "house",
                    "HOUSES": "house",
                    "CONDOS": "condo",
                    "TOWNHOUSES": "townhouse",
                }
                
                if home_type:
                    property_type = property_type_map.get(str(home_type).upper(), params.property_type or "house")
                else:
                    # If homeType is None, use the requested property type (API already filtered by home_type)
                    property_type = params.property_type or "house"

                # Extract image URL - API uses imgSrc or miniCardPhotos
                image_url = prop_data.get("imgSrc", "") or ""
                if not image_url:
                    # Try miniCardPhotos array
                    mini_photos = prop_data.get("miniCardPhotos", [])
                    if mini_photos and isinstance(mini_photos, list) and len(mini_photos) > 0:
                        photo = mini_photos[0]
                        if isinstance(photo, dict):
                            image_url = photo.get("url", "") or ""
                        elif isinstance(photo, str):
                            image_url = photo
                
                # Extract bedrooms and bathrooms
                bedrooms = int(prop_data.get("bedrooms", 0) or 0)
                bathrooms = float(prop_data.get("bathrooms", 0) or 0)

                # Extract listing URL - API uses hdpUrl or detailUrl
                listing_url = prop_data.get("hdpUrl", "") or prop_data.get("detailUrl", "") or ""
                # If hdpUrl is relative, prepend zillow.com domain
                if listing_url and listing_url.startswith("/"):
                    listing_url = f"https://www.zillow.com{listing_url}"

                # Build Property object with all required fields
                zpid = prop_data.get("zpid")
                property_id = str(zpid) if zpid else f"prop_{len(properties)}"
                
                # Build full address
                address_parts = [p for p in [street_address, city, state, zip_code] if p]
                property_address = ", ".join(address_parts) if address_parts else address_str or "Address not available"
                
                # Extract description
                description = (
                    prop_data.get("description") or 
                    prop_data.get("statusText") or 
                    prop_data.get("listingMetadata", {}).get("description", "") or 
                    ""
                )
                
                # Extract year built
                year_built = prop_data.get("yearBuilt")
                if year_built:
                    try:
                        year_built = int(year_built)
                    except (ValueError, TypeError):
                        year_built = None
                
                # Extract lot size
                lot_size = prop_data.get("lotSize") or prop_data.get("lotAreaValue")
                if lot_size:
                    try:
                        lot_size = float(lot_size)
                    except (ValueError, TypeError):
                        lot_size = None
                
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
                    description=description,
                    image_url=image_url,
                    year_built=year_built,
                    lot_size=lot_size,
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
        logger.error(f"Unexpected error in _search_properties_impl: {e}")
        raise


# MCP Tool wrapper (for MCP protocol)
@mcp.tool()
async def search_properties(params: PropertySearchParams) -> List[Property]:
    """
    Search for properties matching the given criteria.

    This is the MCP tool wrapper that calls the internal implementation.
    Agents should call search_properties_direct() directly to avoid the FunctionTool wrapper.

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
    return await _search_properties_impl(params)


# Export the internal implementation for direct use by agents
# This allows agents to call the function directly without going through MCP tool wrapper
async def search_properties_direct(params: PropertySearchParams) -> List[Property]:
    """
    Direct callable version of search_properties for use by agents.
    
    This function can be called directly by agents without the MCP tool wrapper.
    It bypasses the FunctionTool object created by @mcp.tool() decorator.
    """
    return await _search_properties_impl(params)


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
        # Try new zillow-com1 API first (primary), then fallback to zillow-working-api
        # zillow-com1 API /property endpoint
        url = f"{settings.zillow_com_api_base_url}/property"
        logger.info(f"Fetching property details from zillow-com1 API for ZPID: {property_id}")
        
        response_data = None
        try:
            # Use zillow-com1 API for property details
            response_data = await _make_api_request(url, {"zpid": property_id}, use_zillow_com_api=True)
            logger.info(f"Successfully fetched property details from zillow-com1 API")
        except httpx.HTTPStatusError as e:
            # Fallback to zillow-working-api if zillow-com1 fails
            if e.response.status_code in (403, 404):
                logger.info("zillow-com1 API endpoint not available, trying zillow-working-api")
                try:
                    url = f"{settings.zillow_market_api_base_url}/pro/byzpid"
                    response_data = await _make_api_request(url, {"zpid": property_id}, use_market_api=True)
                    # The response structure from /pro/byzpid is different - it's nested in propertyDetails
                    if "propertyDetails" in response_data:
                        response_data = response_data["propertyDetails"]
                except httpx.HTTPStatusError as e2:
                    # If zpid endpoint doesn't work, try fallback to real-time-zillow-data
                    if e2.response.status_code in (403, 404):
                        logger.info("zillow-working-api endpoint not available, trying fallback endpoint")
                        try:
                            fallback_url = f"{settings.zillow_api_base_url}/property-details-zpid"
                            response_data = await _make_api_request(fallback_url, {"zpid": property_id}, use_market_api=False)
                        except httpx.HTTPStatusError:
                            # Try one more alternative
                            alt_url = f"{settings.zillow_api_base_url}/property"
                            response_data = await _make_api_request(alt_url, {"zpid": property_id}, use_market_api=False)
                    else:
                        raise
            else:
                raise
        
        if not response_data:
            raise ValueError(f"Failed to fetch property details for ZPID: {property_id}")

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

