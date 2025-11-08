"""Market Analysis MCP Server.

This server provides tools for analyzing real estate market data including
neighborhood statistics, school ratings, market trends, affordability calculations,
and comparable sales data.
"""

import asyncio
import math
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from urllib.parse import quote

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


# MCP Tools
@mcp.tool()
async def get_neighborhood_stats(location: str) -> NeighborhoodStats:
    """
    Get demographics, crime, and walkability scores for a location.

    Args:
        location: City, state, or ZIP code

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

    # Check cache (24 hour TTL for neighborhood data)
    cache_key = _get_cache_key("neighborhood_stats", location=location)
    cached_result = _get_cached(cache_key, ttl_seconds=86400)
    if cached_result:
        logger.info(f"Returning cached neighborhood stats for: {location}")
        return NeighborhoodStats(**cached_result)

    try:
        # Validate API key
        if not settings.rapidapi_key or settings.rapidapi_key == "your_rapidapi_key_here":
            raise ValueError("RAPIDAPI_KEY not configured. Please set your RapidAPI key in .env file")

        # Call Zillow API for neighborhood data
        # Use the new API endpoint: /By Property Address (Property Info - Advanced)
        endpoint = quote("By Property Address", safe="")
        url = f"{settings.zillow_api_base_url}/{endpoint}"
        params = {"address": location}

        response_data = await _make_api_request(url, params)

        # Log response structure for debugging
        logger.info(f"API response keys for neighborhood stats: {list(response_data.keys())[:20]}")
        logger.debug(f"Full API response structure (first 500 chars): {str(response_data)[:500]}")

        # Extract neighborhood data from response
        # Note: Actual API response structure may vary - this handles common patterns
        # Try multiple possible response structures
        demographics_data = {}
        if "demographics" in response_data:
            demographics_data = response_data["demographics"] if isinstance(response_data["demographics"], dict) else {}
        elif "data" in response_data and isinstance(response_data["data"], dict):
            demographics_data = response_data["data"].get("demographics", {})
        elif "property" in response_data and isinstance(response_data["property"], dict):
            demographics_data = response_data["property"].get("demographics", {})

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
            or 50.0
        )
        
        walkability_score = (
            response_data.get("walkScore")
            or response_data.get("walk_score")
            or response_data.get("walkability")
            or (response_data.get("data", {}).get("walkScore") if isinstance(response_data.get("data"), dict) else None)
            or (response_data.get("property", {}).get("walkScore") if isinstance(response_data.get("property"), dict) else None)
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
        logger.error(f"Unexpected error in get_neighborhood_stats: {e}")
        raise


@mcp.tool()
async def get_school_ratings(location: str, radius: int = 5) -> List[SchoolRating]:
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

    # Check cache (24 hour TTL for school data)
    cache_key = _get_cache_key("school_ratings", location=location, radius=radius)
    cached_result = _get_cached(cache_key, ttl_seconds=86400)
    if cached_result:
        logger.info(f"Returning cached school ratings for: {location}")
        return [SchoolRating(**s) for s in cached_result.get("schools", [])]

    try:
        # Validate API key
        if not settings.rapidapi_key or settings.rapidapi_key == "your_rapidapi_key_here":
            raise ValueError("RAPIDAPI_KEY not configured. Please set your RapidAPI key in .env file")

        # Call Zillow API for school data
        # Use the new API endpoint: /By Property Address (Property Info - Advanced)
        # School data should be in the property details response
        endpoint = quote("By Property Address", safe="")
        url = f"{settings.zillow_api_base_url}/{endpoint}"
        params = {"address": location}

        response_data = await _make_api_request(url, params)

        # Extract school data from response - try multiple possible locations
        # The API might return schools in different nested structures
        schools_list = []
        
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
                school_name = school_data.get("name") or school_data.get("schoolName") or "Unknown"
                school_type = (
                    school_data.get("type")
                    or school_data.get("schoolType")
                    or school_data.get("level")
                    or "elementary"
                ).lower()

                # Extract rating (0-10 scale expected)
                rating = school_data.get("rating") or school_data.get("score") or 0
                # Keep rating as-is (0-10 scale) since SchoolRating model accepts 0-10
                # No conversion needed

                distance = school_data.get("distance") or school_data.get("distanceMiles") or 0

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
        logger.error(f"Unexpected error in get_school_ratings: {e}")
        raise


@mcp.tool()
async def get_market_trends(location: str, timeframe: str = "1y") -> MarketTrends:
    """
    Get price trends and market velocity.

    Args:
        location: City, state, or ZIP code
        timeframe: Timeframe for trends - "1m", "3m", "6m", or "1y" (default: "1y")

    Returns:
        MarketTrends object with price trends and market velocity

    Raises:
        ValueError: If location is invalid or timeframe is invalid
        httpx.HTTPError: If API request fails

    Example:
        >>> trends = await get_market_trends("Austin, TX", timeframe="6m")
        >>> trends.price_change_percent
        5.2
        >>> trends.sales_velocity
        45.3
    """
    logger.info(f"Getting market trends for: {location} (timeframe: {timeframe})")

    if not location or len(location.strip()) < 2:
        raise ValueError("Invalid location: must be at least 2 characters")

    valid_timeframes = ["1m", "3m", "6m", "1y"]
    if timeframe not in valid_timeframes:
        raise ValueError(f"Invalid timeframe. Must be one of: {', '.join(valid_timeframes)}")

    # Check cache (1 hour TTL for market trends)
    cache_key = _get_cache_key("market_trends", location=location, timeframe=timeframe)
    cached_result = _get_cached(cache_key, ttl_seconds=3600)
    if cached_result:
        logger.info(f"Returning cached market trends for: {location}")
        return MarketTrends(**cached_result)

    try:
        # Validate API key
        if not settings.rapidapi_key or settings.rapidapi_key == "your_rapidapi_key_here":
            raise ValueError("RAPIDAPI_KEY not configured. Please set your RapidAPI key in .env file")

        # Call Zillow API for market data
        # Use the housing_market endpoint for market trends
        # First get property details to extract location/ZIP for market data
        endpoint = quote("By Property Address", safe="")
        url = f"{settings.zillow_api_base_url}/{endpoint}"
        params = {"address": location}
        
        # Get property details first to extract location info
        property_response = await _make_api_request(url, params)
        
        # Extract ZIP code or location for market data
        zip_code = (
            property_response.get("zipcode")
            or property_response.get("zipCode")
            or (property_response.get("address", {}).get("zipcode") if isinstance(property_response.get("address"), dict) else None)
            or location.split(",")[-1].strip() if "," in location else None
        )
        
        # Now get market trends using housing_market endpoint
        market_url = f"{settings.zillow_api_base_url}/housing_market"
        market_params = {"zip": zip_code} if zip_code else {"address": location}
        
        response_data = await _make_api_request(market_url, market_params)

        # Log response structure for debugging
        logger.info(f"API response keys for market trends: {list(response_data.keys())[:20]}")

        # Extract market data from response - try multiple possible locations
        # Check top level, data.*, property.*
        median_price = (
            response_data.get("price")
            or response_data.get("medianPrice")
            or response_data.get("zestimate")
            or (response_data.get("data", {}).get("price") if isinstance(response_data.get("data"), dict) else None)
            or (response_data.get("property", {}).get("price") if isinstance(response_data.get("property"), dict) else None)
            or 0
        )
        
        price_per_sqft = (
            response_data.get("pricePerSqft")
            or response_data.get("pricePerSquareFoot")
            or response_data.get("price_per_sqft")
            or (response_data.get("data", {}).get("pricePerSqft") if isinstance(response_data.get("data"), dict) else None)
            or 0
        )

        # Calculate trends from API response data
        # Trends are calculated from available Zillow API data
        price_change_percent = (
            response_data.get("priceChangePercent")
            or response_data.get("price_change_percent")
            or (response_data.get("data", {}).get("priceChangePercent") if isinstance(response_data.get("data"), dict) else None)
            or 0
        )
        
        days_on_market = (
            response_data.get("daysOnMarket")
            or response_data.get("daysOnZillow")
            or response_data.get("days_on_market")
            or (response_data.get("data", {}).get("daysOnMarket") if isinstance(response_data.get("data"), dict) else None)
            or 30
        )
        
        inventory_count = (
            response_data.get("inventoryCount")
            or response_data.get("inventory_count")
            or (response_data.get("data", {}).get("inventoryCount") if isinstance(response_data.get("data"), dict) else None)
            or 0
        )

        # Calculate sales velocity (properties sold per month)
        # This is an estimate based on available data
        sales_velocity = response_data.get("salesVelocity") or (inventory_count / max(days_on_market / 30, 1))

        # Determine trend direction
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

        # Cache result
        _set_cache(cache_key, trends.model_dump(), ttl_seconds=3600)

        logger.info(f"Retrieved market trends for: {location}")
        return trends

    except httpx.HTTPStatusError as e:
        # Handle 400 Bad Request (endpoint requires specific address, not city/state)
        if e.response.status_code == 400:
            logger.warning(
                f"API returned 400 for location '{location}'. "
                f"Endpoint requires specific address. Returning estimated market trends."
            )
            # Return default/estimated trends when API doesn't support city-level queries
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
            # Cache the default result
            _set_cache(cache_key, trends.model_dump(), ttl_seconds=3600)
            return trends
        logger.error(f"API request failed: {e}")
        raise
    except httpx.HTTPError as e:
        logger.error(f"API request failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_market_trends: {e}")
        raise


@mcp.tool()
async def calculate_affordability(
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


@mcp.tool()
async def get_comparable_sales(
    location: str, property_type: Optional[str] = None
) -> List[ComparableSale]:
    """
    Get recent comparable sales data.

    Args:
        location: City, state, or ZIP code
        property_type: Optional property type filter (house, condo, townhouse)

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

    # Check cache (1 hour TTL for comparable sales)
    cache_key = _get_cache_key("comparable_sales", location=location, property_type=property_type or "all")
    cached_result = _get_cached(cache_key, ttl_seconds=3600)
    if cached_result:
        logger.info(f"Returning cached comparable sales for: {location}")
        return [ComparableSale(**s) for s in cached_result.get("sales", [])]

    try:
        # Validate API key
        if not settings.rapidapi_key or settings.rapidapi_key == "your_rapidapi_key_here":
            raise ValueError("RAPIDAPI_KEY not configured. Please set your RapidAPI key in .env file")

        # Call Zillow API for comparable sales
        # Use the comparable_homes endpoint
        url = f"{settings.zillow_api_base_url}/comparable_homes"
        params = {"address": location}

        response_data = await _make_api_request(url, params)

        # Log response structure for debugging
        logger.info(f"API response keys for comparable sales: {list(response_data.keys())[:20]}")

        # Extract comparable sales from response - try multiple possible locations
        # Note: Actual API may have different structure for comparable sales
        comps_list = []
        
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
                address = comp_data.get("address") or comp_data.get("streetAddress") or "Address not available"
                sale_price = comp_data.get("price") or comp_data.get("salePrice") or 0
                sale_date = comp_data.get("saleDate") or comp_data.get("date") or ""
                square_feet = comp_data.get("squareFeet") or comp_data.get("sqft") or comp_data.get("livingArea") or 0
                bedrooms = comp_data.get("bedrooms") or comp_data.get("beds") or 0
                bathrooms = comp_data.get("bathrooms") or comp_data.get("baths") or 0
                comp_property_type = (comp_data.get("propertyType") or comp_data.get("type") or "house").lower()
                distance = comp_data.get("distance") or comp_data.get("distanceMiles") or 0

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
        logger.error(f"Unexpected error in get_comparable_sales: {e}")
        raise


# Server entry point
if __name__ == "__main__":
    import uvicorn

    port = settings.mcp_server_port_market_analysis
    logger.info(f"Starting Market Analysis MCP Server on port {port}")
    uvicorn.run(mcp.app, host=settings.mcp_server_host, port=port)

