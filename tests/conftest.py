"""Pytest configuration and shared fixtures."""

import pytest
from typing import Dict, Any


@pytest.fixture
def sample_property_data() -> Dict[str, Any]:
    """Sample property data for testing."""
    return {
        "id": "test_property_1",
        "address": "123 Main St",
        "city": "Austin",
        "state": "TX",
        "zip_code": "78701",
        "price": 500000,
        "bedrooms": 3,
        "bathrooms": 2.5,
        "square_feet": 2000,
        "property_type": "house",
        "listing_url": "https://example.com/property/1",
        "description": "Beautiful home in downtown Austin",
    }


@pytest.fixture
def sample_search_params() -> Dict[str, Any]:
    """Sample search parameters for testing."""
    return {
        "location": "Austin, TX",
        "min_price": None,
        "max_price": 600000,
        "bedrooms": 3,
        "bathrooms": None,
        "property_type": None,
    }

