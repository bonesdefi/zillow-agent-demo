# API Documentation Documentation

## Overview

The system uses three custom API (Model Context Protocol) documentation to provide structured data access for the AI agents.

## Real Estate Data Server

**Port**: 8001

### Tools

#### `search_properties`

Search for properties matching given criteria.

**Parameters**:
- `location` (str): City, state, or ZIP code
- `min_price` (int, optional): Minimum price in USD
- `max_price` (int, optional): Maximum price in USD
- `bedrooms` (int, optional): Number of bedrooms
- `bathrooms` (float, optional): Number of bathrooms
- `property_type` (str, optional): Type (house, condo, townhouse)

**Returns**: List of Property objects

**Example**:
```python
params = PropertySearchParams(
    location="Austin, TX",
    max_price=600000,
    bedrooms=3
)
properties = await search_properties(params)
```

#### `get_property_details`

Get detailed information about a specific property.

**Parameters**:
- `property_id` (str): Unique property identifier

**Returns**: Property object with full details

#### `get_property_photos`

Retrieve property images and media.

**Parameters**:
- `property_id` (str): Unique property identifier

**Returns**: List of image URLs

#### `get_similar_properties`

Find comparable properties.

**Parameters**:
- `property_id` (str): Reference property identifier
- `limit` (int, optional): Maximum number of results (default: 10)

**Returns**: List of similar Property objects

## Market Analysis Server

**Port**: 8002

### Tools

#### `get_neighborhood_stats`

Get demographics, crime, and walkability scores.

**Parameters**:
- `location` (str): City, state, or ZIP code

**Returns**: Neighborhood statistics dictionary

#### `get_school_ratings`

Get school quality ratings for area.

**Parameters**:
- `location` (str): City, state, or ZIP code
- `radius` (int, optional): Search radius in miles (default: 5)

**Returns**: List of school ratings

#### `get_market_trends`

Get price trends and market velocity.

**Parameters**:
- `location` (str): City, state, or ZIP code
- `timeframe` (str, optional): Timeframe (1m, 3m, 6m, 1y)

**Returns**: Market trends data

#### `calculate_affordability`

Calculate affordability based on income.

**Parameters**:
- `price` (int): Property price
- `annual_income` (int): Annual household income
- `down_payment` (int, optional): Down payment amount

**Returns**: Affordability analysis

#### `get_comparable_sales`

Get recent comparable sales data.

**Parameters**:
- `location` (str): City, state, or ZIP code
- `property_type` (str, optional): Property type filter

**Returns**: List of comparable sales

## User Context Server

**Port**: 8003

### Tools

#### `store_user_preferences`

Save user search preferences.

**Parameters**:
- `user_id` (str): User identifier
- `preferences` (dict): Preference dictionary

**Returns**: Confirmation message

#### `get_user_preferences`

Retrieve stored preferences.

**Parameters**:
- `user_id` (str): User identifier

**Returns**: User preferences dictionary

#### `add_conversation_message`

Store conversation history.

**Parameters**:
- `user_id` (str): User identifier
- `role` (str): Message role (user/assistant)
- `content` (str): Message content

**Returns**: Confirmation message

#### `get_conversation_history`

Retrieve conversation.

**Parameters**:
- `user_id` (str): User identifier
- `limit` (int, optional): Maximum number of messages

**Returns**: List of conversation messages

#### `track_viewed_property`

Log properties user has viewed.

**Parameters**:
- `user_id` (str): User identifier
- `property_id` (str): Property identifier
- `action` (str, optional): Action type (viewed, favorited, etc.)

**Returns**: Confirmation message

#### `get_viewed_properties`

Get viewing history.

**Parameters**:
- `user_id` (str): User identifier

**Returns**: List of viewed properties

## Error Handling

All API documentation implement comprehensive error handling:

- **Validation Errors**: Invalid input parameters return 400 errors
- **API Errors**: External API failures are caught and logged
- **Rate Limiting**: 429 errors when rate limits are exceeded
- **Timeout Errors**: Request timeouts are handled gracefully

## Rate Limiting

- Real Estate API: 100 requests/minute
- Market Analysis API: 50 requests/minute
- User Context: No rate limiting (in-memory)

## Caching Strategy

- Property search results: 5 minute TTL
- Property details: 10 minute TTL
- Market trends: 1 hour TTL
- School ratings: 24 hour TTL

