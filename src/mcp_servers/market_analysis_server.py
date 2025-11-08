"""Market Analysis MCP Server.

This server provides tools for analyzing real estate market data including
neighborhood statistics, school ratings, market trends, affordability calculations,
and comparable sales data.
"""

import asyncio
import math
import re
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from src.utils.config import get_settings
from src.utils.logging import setup_logging

# Initialize logger
logger = setup_logging(__name__)

# Initialize MCP server
mcp = FastMCP("Market Analysis Server")

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


def _get_cached(key: str, ttl_seconds: int = 3600) -> Optional[dict]:
    """Get value from cache if not expired."""
    if key in _cache:
        if key in _cache_ttl:
            if datetime.now() < _cache_ttl[key]:
                logger.debug(f"Cache hit for key: {key}")
                return _cache[key]
            else:
                del _cache[key]
                del _cache_ttl[key]
    return None


def _set_cache(key: str, value: dict, ttl_seconds: int = 3600) -> None:
    """Set value in cache with TTL."""
    _cache[key] = value
    _cache_ttl[key] = datetime.now() + timedelta(seconds=ttl_seconds)
    logger.debug(f"Cached value for key: {key} with TTL: {ttl_seconds}s")


async def _make_api_request(
    url: str, params: dict, max_retries: int = 3, retry_delay: float = 1.0, use_market_api: bool = False
) -> dict:
    """
    Make HTTP request with retry logic and exponential backoff.

    Args:
        url: API endpoint URL
        params: Request parameters
        max_retries: Maximum number of retry attempts
        retry_delay: Initial retry delay in seconds
        use_market_api: If True, use zillow_market_api_host instead of zillow_api_host

    Returns:
        JSON response as dictionary

    Raises:
        httpx.HTTPError: If request fails after all retries
        ValueError: If API key is missing
    """
    if not settings.rapidapi_key:
        raise ValueError("RAPIDAPI_KEY not configured")

    # Use market API host if specified
    api_host = settings.zillow_market_api_host if use_market_api else settings.zillow_api_host
    
    headers = {
        "X-RapidAPI-Key": settings.rapidapi_key,
        "X-RapidAPI-Host": api_host,
    }

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                response_json = response.json()
                
                # Log response structure for debugging (first call only to avoid spam)
                if not hasattr(_make_api_request, "_logged_once"):
                    logger.info(f"API response sample - keys: {list(response_json.keys())[:20] if isinstance(response_json, dict) else 'not a dict'}")
                    logger.debug(f"API response sample (first 1000 chars): {str(response_json)[:1000]}")
                    _make_api_request._logged_once = True
                
                return response_json

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
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
class NeighborhoodStats(BaseModel):
    """Neighborhood statistics data model."""

    demographics: Dict[str, Any]
    crime_score: float = Field(..., ge=0, le=100, description="Crime score 0-100")
    walkability_score: float = Field(..., ge=0, le=100, description="Walkability score 0-100")
    overall_score: float = Field(..., ge=0, le=100, description="Overall neighborhood score")


class SchoolRating(BaseModel):
    """School rating data model."""

    name: str
    type: str = Field(..., description="School type: elementary, middle, high")
    rating: float = Field(..., ge=0, le=10, description="School rating 0-10")
    distance_miles: float = Field(..., ge=0, description="Distance from location in miles")
    address: Optional[str] = None
    grades: Optional[str] = None


class MarketTrends(BaseModel):
    """Market trends data model."""

    location: str
    timeframe: str
    median_price: float
    price_change_percent: float
    days_on_market_avg: float
    inventory_count: int
    sales_velocity: float = Field(..., description="Properties sold per month")
    price_per_sqft: float
    trend_direction: str = Field(..., description="up, down, or stable")


class AffordabilityAnalysis(BaseModel):
    """Affordability analysis data model."""

    affordable: bool
    monthly_payment: float
    down_payment: float
    loan_amount: float
    monthly_principal_interest: float
    estimated_monthly_taxes: float
    estimated_monthly_insurance: float
    debt_to_income_ratio: float = Field(..., ge=0, le=100)
    recommendation: str


class ComparableSale(BaseModel):
    """Comparable sale data model."""

    address: str
    sale_price: int
    sale_date: str
    square_feet: int
    bedrooms: int
    bathrooms: float
    property_type: str
    distance_miles: float = Field(..., ge=0)


# Internal implementation (can be called directly by agents)
async def _get_neighborhood_stats_impl(location: str, zpid: Optional[str] = None) -> NeighborhoodStats:
    """
    Get demographics, crime, and walkability scores for a location.

    Args:
        location: City, state, or ZIP code
        zpid: Optional Zillow Property ID for better data from /pro/byzpid endpoint

    Returns:
        NeighborhoodStats object with demographics, crime score, walkability, and overall score

    Raises:
        ValueError: If location is invalid
        httpx.HTTPError: If API request fails

    Example:
        >>> stats = await get_neighborhood_stats("Austin, TX")
        >>> stats.crime_score
        25.5
        >>> stats.walkability_score
        78.2
    """
    logger.info(f"Getting neighborhood stats for: {location}")

    if not location or len(location.strip()) < 2:
        raise ValueError("Invalid location: must be at least 2 characters")

    # Check cache (24 hour TTL for neighborhood data) - include ZPID in cache key if provided
    cache_key = _get_cache_key("neighborhood_stats", location=location, zpid=zpid or "none")
    cached_result = _get_cached(cache_key, ttl_seconds=86400)
    if cached_result:
        logger.info(f"Returning cached neighborhood stats for: {location}")
        return NeighborhoodStats(**cached_result)

    try:
        # Validate API key
        if not settings.rapidapi_key or settings.rapidapi_key == "your_rapidapi_key_here":
            raise ValueError("RAPIDAPI_KEY not configured. Please set your RapidAPI key in .env file")

        response_data = None
        
        # If ZPID is available, use the new /pro/byzpid endpoint for rich data
        if zpid:
            try:
                logger.info(f"Using /pro/byzpid endpoint with ZPID: {zpid}")
                url = f"{settings.zillow_market_api_base_url}/pro/byzpid"
                params = {"zpid": zpid}
                response_data = await _make_api_request(url, params, use_market_api=True)
                
                # Parse rich property data from /pro/byzpid
                property_details = response_data.get("propertyDetails", {})
                parent_region = property_details.get("parentRegion", {})
                neighborhood_name = parent_region.get("name", "")
                
                # Extract neighborhood info
                # Note: /pro/byzpid doesn't have demographics, but we can get neighborhood name
                demographics = {
                    "population": 0,  # Not available in this endpoint
                    "median_age": 0,
                    "median_income": 0,
                    "household_size": 0,
                }
                
                # Try to get walkability/transit scores if available
                walkability_score = 50.0  # Default
                crime_score = 50.0  # Default
                
                # If we have neighborhood name, we can at least provide that context
                if neighborhood_name:
                    logger.info(f"Found neighborhood: {neighborhood_name}")
                
            except Exception as zpid_error:
                logger.warning(f"Failed to use /pro/byzpid endpoint: {zpid_error}. Falling back to address-based lookup.")
                response_data = None
        
        # Fallback to address-based endpoint if ZPID failed or not provided
        if not response_data:
            # Call Zillow API for neighborhood data
            # Use property-details-address endpoint (works with real-time-zillow-data API)
            url = f"{settings.zillow_api_base_url}/property-details-address"
            params = {"address": location}
            response_data = await _make_api_request(url, params)

        # Log response structure for debugging
        logger.info(f"API response keys for neighborhood stats: {list(response_data.keys())[:20]}")

        # Extract neighborhood data from response - try multiple possible structures
        demographics_data = {}
        if "demographics" in response_data:
            demographics_data = response_data["demographics"] if isinstance(response_data["demographics"], dict) else {}
        elif "data" in response_data and isinstance(response_data["data"], dict):
            demographics_data = response_data["data"].get("demographics", {})
        elif "property" in response_data and isinstance(response_data["property"], dict):
            demographics_data = response_data["property"].get("demographics", {})
        elif "propertyDetails" in response_data:
            # New endpoint structure
            property_details = response_data.get("propertyDetails", {})
            parent_region = property_details.get("parentRegion", {})
            if parent_region:
                # We have neighborhood name but not demographics
                pass

        # Only update demographics if we found data
        if demographics_data:
            demographics = {
                "population": demographics_data.get("population") or demographics_data.get("populationCount") or 0,
                "median_age": demographics_data.get("medianAge") or demographics_data.get("age") or 0,
                "median_income": demographics_data.get("medianIncome") or demographics_data.get("income") or 0,
                "household_size": demographics_data.get("householdSize") or demographics_data.get("household_size") or 0,
            }

        # Calculate scores from available data - try multiple locations
        crime_score = (
            response_data.get("crimeScore") 
            or response_data.get("crime_score")
            or (response_data.get("data", {}).get("crimeScore") if isinstance(response_data.get("data"), dict) else None)
            or (response_data.get("property", {}).get("crimeScore") if isinstance(response_data.get("property"), dict) else None)
            or (response_data.get("propertyDetails", {}).get("crimeScore") if isinstance(response_data.get("propertyDetails"), dict) else None)
            or 50.0
        )
        
        walkability_score = (
            response_data.get("walkScore")
            or response_data.get("walk_score")
            or response_data.get("walkability")
            or (response_data.get("data", {}).get("walkScore") if isinstance(response_data.get("data"), dict) else None)
            or (response_data.get("property", {}).get("walkScore") if isinstance(response_data.get("property"), dict) else None)
            or (response_data.get("propertyDetails", {}).get("walkScore") if isinstance(response_data.get("propertyDetails"), dict) else None)
            or 50.0
        )

        # Calculate overall score (weighted average)
        overall_score = (crime_score * 0.4 + walkability_score * 0.6)

        stats = NeighborhoodStats(
            demographics=demographics,
            crime_score=float(crime_score),
            walkability_score=float(walkability_score),
            overall_score=float(overall_score),
        )

        # Cache result
        _set_cache(cache_key, stats.model_dump(), ttl_seconds=86400)

        logger.info(f"Retrieved neighborhood stats for: {location}")
        return stats

    except httpx.HTTPStatusError as e:
        # Handle 400 Bad Request (endpoint requires specific address, not city/state)
        if e.response.status_code == 400:
            logger.warning(
                f"API returned 400 for location '{location}'. "
                f"Endpoint requires specific address. Returning estimated neighborhood stats."
            )
            # Return default/estimated stats when API doesn't support city-level queries
            stats = NeighborhoodStats(
                demographics={
                    "population": 0,
                    "median_age": 0,
                    "median_income": 0,
                    "household_size": 0,
                },
                crime_score=50.0,  # Neutral default
                walkability_score=50.0,  # Neutral default
                overall_score=50.0,
            )
            # Cache the default result to avoid repeated API calls
            _set_cache(cache_key, stats.model_dump(), ttl_seconds=86400)
            return stats
        logger.error(f"API request failed: {e}")
        raise
    except httpx.HTTPError as e:
        logger.error(f"API request failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in _get_neighborhood_stats_impl: {e}")
        raise


# MCP Tool wrapper (for MCP protocol)
@mcp.tool()
async def get_neighborhood_stats(location: str, zpid: Optional[str] = None) -> NeighborhoodStats:
    """MCP tool wrapper. Agents should use get_neighborhood_stats_direct() instead."""
    return await _get_neighborhood_stats_impl(location, zpid=zpid)


# Direct callable version for agents
async def get_neighborhood_stats_direct(location: str, zpid: Optional[str] = None) -> NeighborhoodStats:
    """Direct callable version for use by agents (bypasses MCP tool wrapper)."""
    return await _get_neighborhood_stats_impl(location, zpid=zpid)


# Internal implementation for school ratings
async def _get_school_ratings_impl(location: str, radius: int = 5, zpid: Optional[str] = None) -> List[SchoolRating]:
    """
    Get school quality ratings for area.

    Args:
        location: City, state, or ZIP code
        radius: Search radius in miles (default: 5)

    Returns:
        List of SchoolRating objects

    Raises:
        ValueError: If location is invalid or radius is out of range
        httpx.HTTPError: If API request fails

    Example:
        >>> schools = await get_school_ratings("Austin, TX", radius=5)
        >>> len(schools)
        12
        >>> schools[0].rating
        8.5
    """
    logger.info(f"Getting school ratings for: {location} (radius: {radius} miles)")

    if not location or len(location.strip()) < 2:
        raise ValueError("Invalid location: must be at least 2 characters")

    if radius < 1 or radius > 25:
        raise ValueError("Radius must be between 1 and 25 miles")

    # Check cache (24 hour TTL for school data) - include ZPID in cache key if provided
    cache_key = _get_cache_key("school_ratings", location=location, radius=radius, zpid=zpid or "none")
    cached_result = _get_cached(cache_key, ttl_seconds=86400)
    if cached_result:
        logger.info(f"Returning cached school ratings for: {location}")
        return [SchoolRating(**s) for s in cached_result.get("schools", [])]

    try:
        # Validate API key
        if not settings.rapidapi_key or settings.rapidapi_key == "your_rapidapi_key_here":
            raise ValueError("RAPIDAPI_KEY not configured. Please set your RapidAPI key in .env file")

        response_data = None
        schools_list = []
        
        # If ZPID is available, use the new /pro/byzpid endpoint for rich school data
        if zpid:
            try:
                logger.info(f"Using /pro/byzpid endpoint with ZPID: {zpid} for school ratings")
                url = f"{settings.zillow_market_api_base_url}/pro/byzpid"
                params = {"zpid": zpid}
                response_data = await _make_api_request(url, params, use_market_api=True)
                
                # Parse school data from /pro/byzpid - schools are at propertyDetails.schools
                property_details = response_data.get("propertyDetails", {})
                schools_list = property_details.get("schools", [])
                
                if schools_list:
                    logger.info(f"Found {len(schools_list)} schools from /pro/byzpid endpoint")
                
            except Exception as zpid_error:
                logger.warning(f"Failed to use /pro/byzpid endpoint: {zpid_error}. Falling back to address-based lookup.")
                response_data = None
        
        # Fallback to address-based endpoint if ZPID failed or not provided
        if not schools_list:
            # Call Zillow API for school data
            # Use property-details-address endpoint (works with real-time-zillow-data API)
            url = f"{settings.zillow_api_base_url}/property-details-address"
            params = {"address": location}
            response_data = await _make_api_request(url, params)

            # Extract school data from response - try multiple possible locations
            # The API might return schools in different nested structures
            
            # Try various possible keys and nested paths
            if "schools" in response_data:
                schools_list = response_data["schools"] if isinstance(response_data["schools"], list) else []
            elif "nearbySchools" in response_data:
                schools_list = response_data["nearbySchools"] if isinstance(response_data["nearbySchools"], list) else []
            elif "data" in response_data and isinstance(response_data["data"], dict):
                # Check if schools are nested under data
                schools_list = response_data["data"].get("schools", []) or response_data["data"].get("nearbySchools", []) or []
            elif "property" in response_data and isinstance(response_data["property"], dict):
                # Check if schools are nested under property
                schools_list = response_data["property"].get("schools", []) or response_data["property"].get("nearbySchools", []) or []
            elif "propertyDetails" in response_data:
                # New endpoint structure
                property_details = response_data.get("propertyDetails", {})
                schools_list = property_details.get("schools", [])
            
            # Log what we found for debugging
            if not schools_list:
                logger.info(f"No school data found in API response. Response keys: {list(response_data.keys())}")
                # Log a sample of the response structure for debugging
                if response_data:
                    sample_keys = list(response_data.keys())[:10]
                    logger.debug(f"Sample response structure - top-level keys: {sample_keys}")
                    # Try to find any list that might contain school data
                    for key, value in response_data.items():
                        if isinstance(value, list) and len(value) > 0:
                            logger.debug(f"Found list under key '{key}' with {len(value)} items. First item keys: {list(value[0].keys()) if isinstance(value[0], dict) else 'not a dict'}")
                            # Check if items look like school data
                            if isinstance(value[0], dict) and any(k in value[0] for k in ["name", "schoolName", "rating", "score", "type", "schoolType"]):
                                logger.info(f"Found potential school data under key '{key}'")
                                schools_list = value
                                break
                        elif isinstance(value, dict):
                            # Recursively check nested dictionaries
                            nested_keys = list(value.keys())[:10]
                            logger.debug(f"Found nested dict under key '{key}' with keys: {nested_keys}")
                            # Check if this dict has school-related keys
                            if any(k in value for k in ["schools", "nearbySchools", "school"]):
                                school_key = next((k for k in ["schools", "nearbySchools", "school"] if k in value), None)
                                if school_key and isinstance(value[school_key], list):
                                    logger.info(f"Found school data under nested key '{key}.{school_key}'")
                                    schools_list = value[school_key]
                                    break

        school_ratings = []
        for school_data in schools_list[:20]:  # Limit to 20 schools
            try:
                # Handle different response formats
                # /pro/byzpid uses: name, rating, level (Primary/Middle/High), distance, grades
                school_name = school_data.get("name") or school_data.get("schoolName") or "Unknown"
                
                # Map level to type - /pro/byzpid uses "level": "Primary", "Middle", "High"
                level = school_data.get("level", "").lower()
                if level in ["primary", "elementary"]:
                    school_type = "elementary"
                elif level in ["middle", "junior"]:
                    school_type = "middle"
                elif level in ["high", "senior"]:
                    school_type = "high"
                else:
                    # Fallback to other fields
                    school_type = (
                        school_data.get("type")
                        or school_data.get("schoolType")
                        or "elementary"
                    ).lower()

                # Extract rating (0-10 scale expected)
                # /pro/byzpid provides rating directly (e.g., 8 = 8/10)
                rating = school_data.get("rating") or school_data.get("score") or 0
                # Keep rating as-is (0-10 scale) since SchoolRating model accepts 0-10
                rating = float(rating) if rating else 0.0

                # Extract distance in miles
                distance = (
                    school_data.get("distance")
                    or school_data.get("distanceMiles")
                    or 0.0
                )
                distance = float(distance) if distance else 0.0
                
                # Extract grades (e.g., "PK-5")
                grades = school_data.get("grades") or ""
                
                # Extract address if available
                address = school_data.get("address") or ""

                school_rating = SchoolRating(
                    name=school_name,
                    type=school_type,
                    rating=float(rating),
                    distance_miles=float(distance),
                    address=school_data.get("address"),
                    grades=school_data.get("grades"),
                )
                school_ratings.append(school_rating)

            except Exception as e:
                logger.warning(f"Error parsing school data: {e}")
                continue

        # Sort by rating (highest first)
        school_ratings.sort(key=lambda x: x.rating, reverse=True)

        # Cache result
        _set_cache(cache_key, {"schools": [s.model_dump() for s in school_ratings]}, ttl_seconds=86400)

        logger.info(f"Retrieved {len(school_ratings)} school ratings for: {location}")
        return school_ratings

    except httpx.HTTPStatusError as e:
        # Handle 400 Bad Request (endpoint requires specific address, not city/state)
        if e.response.status_code == 400:
            logger.warning(
                f"API returned 400 for location '{location}'. "
                f"Endpoint requires specific address. Returning empty school ratings."
            )
            # Return empty list when API doesn't support city-level queries
            return []
        logger.error(f"API request failed: {e}")
        raise
    except httpx.HTTPError as e:
        logger.error(f"API request failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in _get_school_ratings_impl: {e}")
        raise


# MCP Tool wrapper (for MCP protocol)
@mcp.tool()
async def get_school_ratings(location: str, radius: int = 5, zpid: Optional[str] = None) -> List[SchoolRating]:
    """MCP tool wrapper. Agents should use get_school_ratings_direct() instead."""
    return await _get_school_ratings_impl(location, radius=radius, zpid=zpid)


# Direct callable version for agents
async def get_school_ratings_direct(location: str, radius: int = 5, zpid: Optional[str] = None) -> List[SchoolRating]:
    """Direct callable version for use by agents (bypasses MCP tool wrapper)."""
    return await _get_school_ratings_impl(location, radius=radius, zpid=zpid)


# Internal implementation for market trends
async def _get_market_trends_impl(location: str, timeframe: str = "1y", property_price: Optional[int] = None, property_sqft: Optional[int] = None) -> MarketTrends:
    """
    Get price trends and market velocity.

    Args:
        location: City, state, or ZIP code
        timeframe: Timeframe for trends - "1m", "3m", "6m", or "1y" (default: "1y")
        property_price: Optional property price for accurate price_per_sqft calculation
        property_sqft: Optional property square footage for accurate price_per_sqft calculation

    Returns:
        MarketTrends object with price trends and market velocity.
        Note: Market trends (median_price, price_change_percent, etc.) are city-level and
        will be the same for all properties in the same city. Only price_per_sqft is
        property-specific when property_price and property_sqft are provided.

    Raises:
        ValueError: If location is invalid or timeframe is invalid
        httpx.HTTPError: If API request fails

    Example:
        >>> trends = await get_market_trends("Austin, TX", timeframe="6m")
        >>> trends.price_change_percent
        5.2
        >>> trends.sales_velocity
        45.3
        >>> # With property-specific data for accurate price_per_sqft
        >>> trends = await get_market_trends("123 Main St, Austin, TX", property_price=500000, property_sqft=2000)
        >>> trends.price_per_sqft
        250.0
    """
    logger.info(f"Getting market trends for: {location} (timeframe: {timeframe})")

    if not location or len(location.strip()) < 2:
        raise ValueError("Invalid location: must be at least 2 characters")

    valid_timeframes = ["1m", "3m", "6m", "1y"]
    if timeframe not in valid_timeframes:
        raise ValueError(f"Invalid timeframe. Must be one of: {', '.join(valid_timeframes)}")

    # Check cache (1 hour TTL for market trends)
    # Note: Market trends (median_price, price_change_percent, etc.) are city-level and can be cached.
    # price_per_sqft is property-specific and should be recalculated from property data.
    # Extract city/state for cache key (market trends are city-level)
    cache_location = location
    if "," in location:
        parts = [p.strip() for p in location.split(",")]
        if len(parts) >= 2:
            # Extract city, state for cache key
            if len(parts) >= 3:
                cache_location = f"{parts[-3]}, {parts[-2]}"  # "city, state"
            else:
                cache_location = f"{parts[-2]}, {parts[-1]}"  # "city, state"
    
    cache_key = _get_cache_key("market_trends", location=cache_location, timeframe=timeframe)
    cached_result = _get_cached(cache_key, ttl_seconds=3600)
    if cached_result:
        logger.info(f"Returning cached city-level market trends for: {cache_location}")
        # Recalculate price_per_sqft if property-specific data was provided
        if property_price and property_sqft and property_sqft > 0:
            cached_result["price_per_sqft"] = float(property_price) / float(property_sqft)
        return MarketTrends(**cached_result)

    try:
        # Validate API key
        if not settings.rapidapi_key or settings.rapidapi_key == "your_rapidapi_key_here":
            raise ValueError("RAPIDAPI_KEY not configured. Please set your RapidAPI key in .env file")

        # Extract city/state from location (housing_market endpoint needs city/state, not full address)
        # Try to parse city, state from location string
        search_query = location
        if "," in location:
            # If it's a full address, try to extract city, state
            parts = [p.strip() for p in location.split(",")]
            if len(parts) >= 2:
                # Assume last two parts are state and zip, second-to-last might be city
                # Or just use the city, state part
                if len(parts) >= 3:
                    # Format: "street, city, state, zip"
                    search_query = f"{parts[-3]}, {parts[-2]}"
                else:
                    # Format: "city, state" or "street, city state"
                    search_query = f"{parts[-2]}, {parts[-1]}"
        
        # Use the new housing_market endpoint from zillow-working-api
        url = f"{settings.zillow_market_api_base_url}/housing_market"
        params = {
            "search_query": search_query,
            "home_type": "All_Homes",
            "exclude_rentalMarketTrends": "true",
            "exclude_neighborhoods_zhvi": "true",
        }
        
        logger.info(f"Calling housing_market API with search_query: {search_query}")
        response_data = await _make_api_request(url, params, use_market_api=True)

        # Log response structure for debugging
        logger.info(f"API response keys for market trends: {list(response_data.keys())[:20]}")

        # Parse the rich market data from housing_market endpoint
        market_overview = response_data.get("market_overview", {})
        market_analytics = response_data.get("market_analytics", {})
        
        # Extract median price and typical home value
        median_price = (
            market_overview.get("median_sale_price")
            or market_overview.get("median_list_price")
            or market_overview.get("typical_home_values")
            or 0
        )
        
        # Extract price change from description or calculate from zhviRange
        price_change_percent = 0.0
        description = market_overview.get("description", "")
        if description and ("down" in description.lower() or "up" in description.lower()):
            # Try to extract percentage from description (e.g., "down 6.8%")
            match = re.search(r'([+-]?\d+\.?\d*)%', description)
            if match:
                price_change_percent = float(match.group(1))
                # Make negative if description says "down"
                if "down" in description.lower() and price_change_percent > 0:
                    price_change_percent = -price_change_percent
        
        # Calculate price change from zhviRange if available (compare first and last values)
        zhvi_range = market_analytics.get("zhviRange", [])
        if len(zhvi_range) > 1:
            first_value = zhvi_range[-1].get("dataValue", 0)  # Oldest (last in array)
            last_value = zhvi_range[0].get("dataValue", 0)     # Newest (first in array)
            if first_value > 0:
                price_change_percent = ((last_value - first_value) / first_value) * 100
        
        # Extract days on market from market listing data
        mrkt_listing_latest = market_analytics.get("mrktListingLatest", {})
        days_on_market = (
            mrkt_listing_latest.get("medianDaysToPending")
            or market_overview.get("median_days_to_pending")
            or 30
        )
        
        # Extract inventory count
        inventory_count = (
            market_overview.get("for_sale_inventory")
            or mrkt_listing_latest.get("forSaleInventory")
            or 0
        )
        
        # Calculate sales velocity from sale-to-list ratio and inventory
        sale_to_list_ratio = market_overview.get("market_saletolist_ratio", 1.0)
        new_listings = market_overview.get("new_listings", 0)
        sales_velocity = new_listings * sale_to_list_ratio if new_listings > 0 else 0
        
        # Calculate price per sqft
        # If we have property-specific data, use that; otherwise use median price with typical home size
        if property_price and property_sqft and property_sqft > 0:
            # Use actual property price and square footage for accurate price_per_sqft
            price_per_sqft = float(property_price) / float(property_sqft)
        elif median_price > 0:
            # Fallback: estimate using median price and typical home size
            typical_sqft = 2000  # Typical home size for estimation
            price_per_sqft = float(median_price) / typical_sqft
        else:
            price_per_sqft = 0

        # Determine trend direction from price change
        if price_change_percent > 2:
            trend_direction = "up"
        elif price_change_percent < -2:
            trend_direction = "down"
        else:
            trend_direction = "stable"

        trends = MarketTrends(
            location=location,
            timeframe=timeframe,
            median_price=float(median_price),
            price_change_percent=float(price_change_percent),
            days_on_market_avg=float(days_on_market),
            inventory_count=int(inventory_count),
            sales_velocity=float(sales_velocity),
            price_per_sqft=float(price_per_sqft),
            trend_direction=trend_direction,
        )

        # Cache result (cache city-level data, but price_per_sqft is property-specific)
        # Use the same cache_location we extracted earlier for consistency
        # Store base trends with estimated price_per_sqft (or actual if no property data provided)
        _set_cache(cache_key, trends.model_dump(), ttl_seconds=3600)

        logger.info(f"Retrieved market trends for: {location}")
        return trends

    except httpx.HTTPStatusError as e:
        # Handle 400/404 errors - fallback to old endpoint or return estimated data
        if e.response.status_code in [400, 404]:
            logger.warning(
                f"API returned {e.response.status_code} for location '{location}'. "
                f"Trying fallback to property-details-address endpoint."
            )
            try:
                # Fallback to old endpoint with full address
                url = f"{settings.zillow_api_base_url}/property-details-address"
                params = {"address": location}
                response_data = await _make_api_request(url, params, use_market_api=False)
                
                # Extract basic data from property details
                median_price = response_data.get("price") or response_data.get("zestimate") or 0
                price_change_percent = response_data.get("priceChangePercent") or 0
                days_on_market = response_data.get("daysOnMarket") or 30
                
                trends = MarketTrends(
                    location=location,
                    timeframe=timeframe,
                    median_price=float(median_price),
                    price_change_percent=float(price_change_percent),
                    days_on_market_avg=float(days_on_market),
                    inventory_count=0,
                    sales_velocity=0.0,
                    price_per_sqft=float(median_price) / 2000 if median_price > 0 else 0,
                    trend_direction="stable" if abs(price_change_percent) < 2 else ("up" if price_change_percent > 0 else "down"),
                )
                _set_cache(cache_key, trends.model_dump(), ttl_seconds=3600)
                return trends
            except Exception as fallback_error:
                logger.warning(f"Fallback also failed: {fallback_error}. Returning estimated trends.")
                # Return default/estimated trends when both APIs fail
                trends = MarketTrends(
                    location=location,
                    timeframe=timeframe,
                    median_price=0.0,
                    price_change_percent=0.0,
                    days_on_market_avg=30.0,
                    inventory_count=0,
                    sales_velocity=0.0,
                    price_per_sqft=0.0,
                    trend_direction="stable",
                )
                _set_cache(cache_key, trends.model_dump(), ttl_seconds=3600)
                return trends
        logger.error(f"API request failed: {e}")
        raise
    except httpx.HTTPError as e:
        logger.error(f"API request failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in _get_market_trends_impl: {e}")
        raise


# MCP Tool wrapper (for MCP protocol)
@mcp.tool()
async def get_market_trends(location: str, timeframe: str = "1y", property_price: Optional[int] = None, property_sqft: Optional[int] = None) -> MarketTrends:
    """MCP tool wrapper. Agents should use get_market_trends_direct() instead."""
    return await _get_market_trends_impl(location, timeframe=timeframe, property_price=property_price, property_sqft=property_sqft)


# Direct callable version for agents
async def get_market_trends_direct(location: str, timeframe: str = "1y", property_price: Optional[int] = None, property_sqft: Optional[int] = None) -> MarketTrends:
    """Direct callable version for use by agents (bypasses MCP tool wrapper)."""
    return await _get_market_trends_impl(location, timeframe=timeframe, property_price=property_price, property_sqft=property_sqft)


# Internal implementation for affordability
async def _calculate_affordability_impl(
    price: int, annual_income: int, down_payment: Optional[int] = None
) -> AffordabilityAnalysis:
    """
    Calculate affordability based on income.

    Uses standard mortgage calculations:
    - 30-year fixed mortgage at current rates
    - Property taxes estimated at 1.2% of home value annually
    - Home insurance estimated at 0.35% of home value annually
    - Maximum debt-to-income ratio of 28% for housing costs

    Args:
        price: Property price in USD
        annual_income: Annual household income in USD
        down_payment: Down payment amount in USD (default: 20% of price)

    Returns:
        AffordabilityAnalysis object with detailed affordability breakdown

    Raises:
        ValueError: If price or income is invalid

    Example:
        >>> analysis = await calculate_affordability(500000, 120000, down_payment=100000)
        >>> analysis.affordable
        True
        >>> analysis.monthly_payment
        2845.50
    """
    logger.info(f"Calculating affordability for price: ${price:,}, income: ${annual_income:,}")

    if price <= 0:
        raise ValueError("Price must be greater than 0")
    if annual_income <= 0:
        raise ValueError("Annual income must be greater than 0")

    # Default down payment to 20% if not provided
    if down_payment is None:
        down_payment = int(price * 0.20)
    elif down_payment < 0:
        raise ValueError("Down payment cannot be negative")
    elif down_payment > price:
        raise ValueError("Down payment cannot exceed property price")

    # Mortgage calculation constants
    LOAN_TERM_YEARS = 30
    ANNUAL_INTEREST_RATE = 0.065  # 6.5% - current market rate estimate
    MONTHLY_INTEREST_RATE = ANNUAL_INTEREST_RATE / 12
    PROPERTY_TAX_RATE = 0.012  # 1.2% annually
    INSURANCE_RATE = 0.0035  # 0.35% annually
    MAX_DTI_RATIO = 0.28  # 28% of income for housing

    # Calculate loan amount
    loan_amount = price - down_payment

    # Calculate monthly principal and interest
    num_payments = LOAN_TERM_YEARS * 12
    if loan_amount > 0:
        monthly_pi = loan_amount * (
            MONTHLY_INTEREST_RATE * (1 + MONTHLY_INTEREST_RATE) ** num_payments
        ) / ((1 + MONTHLY_INTEREST_RATE) ** num_payments - 1)
    else:
        monthly_pi = 0

    # Calculate monthly property taxes
    annual_taxes = price * PROPERTY_TAX_RATE
    monthly_taxes = annual_taxes / 12

    # Calculate monthly insurance
    annual_insurance = price * INSURANCE_RATE
    monthly_insurance = annual_insurance / 12

    # Total monthly payment
    monthly_payment = monthly_pi + monthly_taxes + monthly_insurance

    # Calculate debt-to-income ratio
    monthly_income = annual_income / 12
    dti_ratio = (monthly_payment / monthly_income) * 100 if monthly_income > 0 else 0
    
    # Cap DTI ratio at 100% for Pydantic validation (even if calculation exceeds it)
    dti_ratio_capped = min(dti_ratio, 100.0)

    # Determine if affordable
    affordable = dti_ratio <= (MAX_DTI_RATIO * 100)

    # Generate recommendation
    if affordable:
        if dti_ratio < 20:
            recommendation = "Highly affordable. You have significant room in your budget."
        elif dti_ratio < 25:
            recommendation = "Affordable. This fits comfortably within your budget."
        else:
            recommendation = "Affordable but at the upper limit. Consider your other expenses."
    else:
        recommendation = (
            f"Not affordable. Monthly payment (${monthly_payment:,.2f}) exceeds "
            f"recommended {MAX_DTI_RATIO*100:.0f}% of income. Consider a lower-priced property "
            f"or increase your down payment."
        )

    analysis = AffordabilityAnalysis(
        affordable=affordable,
        monthly_payment=round(monthly_payment, 2),
        down_payment=down_payment,
        loan_amount=loan_amount,
        monthly_principal_interest=round(monthly_pi, 2),
        estimated_monthly_taxes=round(monthly_taxes, 2),
        estimated_monthly_insurance=round(monthly_insurance, 2),
        debt_to_income_ratio=round(dti_ratio_capped, 2),
        recommendation=recommendation,
    )

    logger.info(f"Affordability calculated: {'Affordable' if affordable else 'Not affordable'} (DTI: {dti_ratio:.2f}%)")
    return analysis


# MCP Tool wrapper (for MCP protocol)
@mcp.tool()
async def calculate_affordability(
    price: int, annual_income: int, down_payment: Optional[int] = None
) -> AffordabilityAnalysis:
    """MCP tool wrapper. Agents should use calculate_affordability_direct() instead."""
    return await _calculate_affordability_impl(price, annual_income, down_payment=down_payment)


# Direct callable version for agents
async def calculate_affordability_direct(
    price: int, annual_income: int, down_payment: Optional[int] = None
) -> AffordabilityAnalysis:
    """Direct callable version for use by agents (bypasses MCP tool wrapper)."""
    return await _calculate_affordability_impl(price, annual_income, down_payment=down_payment)


# Internal implementation for comparable sales
async def _get_comparable_sales_impl(
    location: str, property_type: Optional[str] = None, zpid: Optional[str] = None
) -> List[ComparableSale]:
    """
    Get recent comparable sales data.

    Args:
        location: City, state, or ZIP code
        property_type: Optional property type filter (house, condo, townhouse)
        zpid: Optional Zillow Property ID for better data from /pro/byzpid endpoint

    Returns:
        List of ComparableSale objects

    Raises:
        ValueError: If location is invalid
        httpx.HTTPError: If API request fails

    Example:
        >>> sales = await get_comparable_sales("Austin, TX", property_type="house")
        >>> len(sales)
        15
        >>> sales[0].sale_price
        525000
    """
    logger.info(f"Getting comparable sales for: {location} (type: {property_type or 'all'})")

    if not location or len(location.strip()) < 2:
        raise ValueError("Invalid location: must be at least 2 characters")

    # Check cache (1 hour TTL for comparable sales) - include ZPID in cache key if provided
    cache_key = _get_cache_key("comparable_sales", location=location, property_type=property_type or "all", zpid=zpid or "none")
    cached_result = _get_cached(cache_key, ttl_seconds=3600)
    if cached_result:
        logger.info(f"Returning cached comparable sales for: {location}")
        return [ComparableSale(**s) for s in cached_result.get("sales", [])]

    try:
        # Validate API key
        if not settings.rapidapi_key or settings.rapidapi_key == "your_rapidapi_key_here":
            raise ValueError("RAPIDAPI_KEY not configured. Please set your RapidAPI key in .env file")

        response_data = None
        comps_list = []
        
        # If ZPID is available, use the new /pro/byzpid endpoint for comparable sales
        if zpid:
            try:
                logger.info(f"Using /pro/byzpid endpoint with ZPID: {zpid} for comparable sales")
                url = f"{settings.zillow_market_api_base_url}/pro/byzpid"
                params = {"zpid": zpid}
                response_data = await _make_api_request(url, params, use_market_api=True)
                
                # Parse comparable sales from /pro/byzpid
                # Based on user's example: collections.modules[].propertyDetails where name="Similar homes"
                # First, check propertyDetails.collections structure
                property_details = response_data.get("propertyDetails", {})
                if isinstance(property_details, dict):
                    # Check if collections is nested under propertyDetails
                    collections = property_details.get("collections", {})
                else:
                    collections = {}
                
                # If not found, try top-level collections
                if not collections or not isinstance(collections, dict):
                    collections = response_data.get("collections", {})
                
                modules = collections.get("modules", []) if isinstance(collections, dict) else []
                
                # Log structure for debugging
                logger.info(f"Checking for comparable sales - collections type: {type(collections)}, modules count: {len(modules)}")
                
                # Find the "Similar homes" module - try different matching strategies
                for idx, module in enumerate(modules):
                    if not isinstance(module, dict):
                        continue
                    
                    module_name = module.get("name", "")
                    placement = module.get("placement", "")
                    logger.debug(f"Module {idx}: name='{module_name}', placement='{placement}', keys={list(module.keys())[:10]}")
                    
                    # Check for similar homes - be flexible with name matching
                    if "similar" in module_name.lower() or "comparable" in module_name.lower():
                        property_details_list = module.get("propertyDetails", [])
                        if property_details_list and isinstance(property_details_list, list) and len(property_details_list) > 0:
                            logger.info(f"Found {len(property_details_list)} similar homes from /pro/byzpid in module '{module_name}'")
                            comps_list = property_details_list
                            break
                    
                    # Also check if propertyDetails exists and looks like property data
                    if "propertyDetails" in module:
                        property_details_list = module.get("propertyDetails", [])
                        if property_details_list and isinstance(property_details_list, list) and len(property_details_list) > 0:
                            # Verify first item looks like a property
                            first_item = property_details_list[0]
                            if isinstance(first_item, dict):
                                # Check for property-like keys
                                if any(k in first_item for k in ["price", "address", "bedrooms", "zpid", "livingArea"]):
                                    logger.info(f"Found {len(property_details_list)} properties in module '{module_name}' (assuming comparables)")
                                    comps_list = property_details_list
                                    break
                
                # If still no comps, try checking all top-level keys for property arrays
                if not comps_list:
                    logger.warning(f"No comparable sales found in modules. Checking alternative structures...")
                    # Check if there's a nearbyHomes or similar key
                    for key in ["nearbyHomes", "similarHomes", "comparableHomes", "recentSales"]:
                        if key in response_data:
                            candidate_list = response_data[key]
                            if isinstance(candidate_list, list) and len(candidate_list) > 0:
                                logger.info(f"Found {len(candidate_list)} properties in '{key}' (using as comparables)")
                                comps_list = candidate_list
                                break
                
            except Exception as zpid_error:
                logger.warning(f"Failed to use /pro/byzpid endpoint: {zpid_error}. Falling back to address-based lookup.")
                response_data = None
        
        # Fallback to address-based endpoint if ZPID failed or not provided
        if not comps_list:
            # Call Zillow API for comparable sales
            # Use property-details-address endpoint (works with real-time-zillow-data API)
            url = f"{settings.zillow_api_base_url}/property-details-address"
            params = {"address": location}
            response_data = await _make_api_request(url, params)

            # Log response structure for debugging
            logger.info(f"API response keys for comparable sales: {list(response_data.keys())[:20]}")

            # Extract comparable sales from response - try multiple possible locations
            # Try top-level keys
            if "comps" in response_data and isinstance(response_data["comps"], list):
                comps_list = response_data["comps"]
            elif "comparableSales" in response_data and isinstance(response_data["comparableSales"], list):
                comps_list = response_data["comparableSales"]
            elif "recentSales" in response_data and isinstance(response_data["recentSales"], list):
                comps_list = response_data["recentSales"]
            # Try nested under data.*
            elif "data" in response_data and isinstance(response_data["data"], dict):
                comps_list = (
                    response_data["data"].get("comps", [])
                    or response_data["data"].get("comparableSales", [])
                    or response_data["data"].get("recentSales", [])
                    or []
                )
            # Try nested under property.*
            elif "property" in response_data and isinstance(response_data["property"], dict):
                comps_list = (
                    response_data["property"].get("comps", [])
                    or response_data["property"].get("comparableSales", [])
                    or response_data["property"].get("recentSales", [])
                    or []
                )

        comparable_sales = []
        for comp_data in comps_list[:20]:  # Limit to 20 comparable sales
            try:
                # Handle different response formats
                # /pro/byzpid format: address.streetAddress, price, bedrooms, bathrooms, livingArea, etc.
                address_obj = comp_data.get("address", {})
                if isinstance(address_obj, dict):
                    # /pro/byzpid format
                    street = address_obj.get("streetAddress", "")
                    city = address_obj.get("city", "")
                    state = address_obj.get("state", "")
                    zipcode = address_obj.get("zipcode", "")
                    address = f"{street}, {city}, {state} {zipcode}".strip()
                else:
                    # Fallback format
                    address = comp_data.get("address") or comp_data.get("streetAddress") or "Address not available"
                
                sale_price = comp_data.get("price") or comp_data.get("salePrice") or 0
                
                # /pro/byzpid doesn't have sale_date, but we can use price history if available
                sale_date = comp_data.get("saleDate") or comp_data.get("date") or comp_data.get("lastSoldDate") or ""
                
                # /pro/byzpid uses livingArea or livingAreaValue
                square_feet = (
                    comp_data.get("livingAreaValue")
                    or comp_data.get("livingArea")
                    or comp_data.get("squareFeet")
                    or comp_data.get("sqft")
                    or 0
                )
                bedrooms = comp_data.get("bedrooms") or comp_data.get("beds") or 0
                bathrooms = comp_data.get("bathrooms") or comp_data.get("baths") or 0
                
                # /pro/byzpid uses homeType (e.g., "SINGLE_FAMILY")
                home_type = comp_data.get("homeType", "").upper()
                if home_type == "SINGLE_FAMILY":
                    comp_property_type = "house"
                elif home_type == "CONDO":
                    comp_property_type = "condo"
                elif home_type == "TOWNHOUSE":
                    comp_property_type = "townhouse"
                else:
                    comp_property_type = (comp_data.get("propertyType") or comp_data.get("type") or "house").lower()
                
                # Distance not available in /pro/byzpid similar homes, use 0
                distance = comp_data.get("distance") or comp_data.get("distanceMiles") or 0.0

                # Filter by property type if specified
                if property_type and comp_property_type != property_type.lower():
                    continue

                sale = ComparableSale(
                    address=address,
                    sale_price=int(sale_price),
                    sale_date=str(sale_date),
                    square_feet=int(square_feet),
                    bedrooms=int(bedrooms),
                    bathrooms=float(bathrooms),
                    property_type=comp_property_type,
                    distance_miles=float(distance),
                )
                comparable_sales.append(sale)

            except Exception as e:
                logger.warning(f"Error parsing comparable sale data: {e}")
                continue

        # Sort by sale date (most recent first)
        comparable_sales.sort(key=lambda x: x.sale_date, reverse=True)

        # Cache result
        _set_cache(cache_key, {"sales": [s.model_dump() for s in comparable_sales]}, ttl_seconds=3600)

        logger.info(f"Retrieved {len(comparable_sales)} comparable sales for: {location}")
        return comparable_sales

    except httpx.HTTPStatusError as e:
        # Handle 400 Bad Request (endpoint requires specific address, not city/state)
        if e.response.status_code == 400:
            logger.warning(
                f"API returned 400 for location '{location}'. "
                f"Endpoint requires specific address. Returning empty comparable sales."
            )
            # Return empty list when API doesn't support city-level queries
            return []
        logger.error(f"API request failed: {e}")
        raise
    except httpx.HTTPError as e:
        logger.error(f"API request failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in _get_comparable_sales_impl: {e}")
        raise


# MCP Tool wrapper (for MCP protocol)
@mcp.tool()
async def get_comparable_sales(
    location: str, property_type: Optional[str] = None, zpid: Optional[str] = None
) -> List[ComparableSale]:
    """MCP tool wrapper. Agents should use get_comparable_sales_direct() instead."""
    return await _get_comparable_sales_impl(location, property_type=property_type, zpid=zpid)


# Direct callable version for agents
async def get_comparable_sales_direct(
    location: str, property_type: Optional[str] = None, zpid: Optional[str] = None
) -> List[ComparableSale]:
    """Direct callable version for use by agents (bypasses MCP tool wrapper)."""
    return await _get_comparable_sales_impl(location, property_type=property_type, zpid=zpid)


# Server entry point
if __name__ == "__main__":
    import uvicorn

    port = settings.mcp_server_port_market_analysis
    logger.info(f"Starting Market Analysis MCP Server on port {port}")
    uvicorn.run(mcp.app, host=settings.mcp_server_host, port=port)

