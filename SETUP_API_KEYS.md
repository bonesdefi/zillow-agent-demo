# API Keys Setup Guide

## Quick Setup

1. Create your `.env` file:
```bash
cp .env.example .env
```

2. Add your API keys to `.env`:

```bash
# Anthropic API Key (for Claude AI)
# Get from: https://console.anthropic.com/
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# RapidAPI Key (for Zillow data)
# Get from: https://rapidapi.com/marketplace/api/real-time-zillow-data
RAPIDAPI_KEY=your_rapidapi_key_here

# API Configuration
ZILLOW_API_BASE_URL=https://real-time-zillow-data.p.rapidapi.com
ZILLOW_API_HOST=real-time-zillow-data.p.rapidapi.com
```

3. Verify your setup:
```bash
# Check that .env is in .gitignore (it should be)
cat .gitignore | grep .env

# Test the configuration loads
python -c "from src.utils.config import get_settings; s = get_settings(); print(f'API keys configured: {bool(s.rapidapi_key and s.anthropic_api_key)}')"
```

## API Endpoints Used

The Real Estate MCP Server uses these endpoints from the Real-Time Zillow Data API:

- **Property Search**: `/property-details-address` (with `address` parameter)
- **Property Details**: `/property-details-zpid` (with `zpid` parameter)
- **Property Photos**: Extracted from property details response

## Testing the Integration

Once your API keys are configured, you can test the integration:

```python
import asyncio
from src.mcp_servers.real_estate_server import search_properties, PropertySearchParams

async def test():
    params = PropertySearchParams(
        location="1161 Natchez Dr College Station Texas 77845",
        max_price=500000
    )
    properties = await search_properties(params)
    print(f"Found {len(properties)} properties")
    for prop in properties:
        print(f"- {prop.address}, {prop.city}, {prop.state} - ${prop.price:,}")

asyncio.run(test())
```

## Security Notes

- ✅ `.env` is in `.gitignore` - your keys won't be committed
- ✅ Never commit API keys to git
- ✅ Use environment variables in production
- ✅ Rotate keys if they're ever exposed

