# Fixing API Key 401 Error

## Current Status

✅ API key is loading from .env file correctly  
✅ Key format looks correct (starts with `sk-ant-api`, 108 characters)  
❌ Still getting 401 Unauthorized errors from Anthropic API

## Possible Causes

1. **Whitespace in .env file** - Keys might have trailing spaces or newlines
2. **Invalid API key** - Key might be expired, revoked, or incorrect
3. **Wrong API key format** - Key might be for a different service
4. **Key needs activation** - New keys might need to be activated first

## Diagnostic Steps

### Step 1: Test API Key Directly

Run the test script:
```bash
python3 test_anthropic_key.py
```

This will:
- Check for whitespace issues
- Test the key directly with Anthropic API
- Show exactly what error you get

### Step 2: Check .env File Format

Make sure your `.env` file looks like this (NO quotes, NO spaces around =):

```bash
ANTHROPIC_API_KEY=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
RAPIDAPI_KEY=92fbc13ef2msh9f0570621ce0dfdp11d5d9jsnd051d5af23bf
```

**NOT like this:**
```bash
ANTHROPIC_API_KEY="sk-ant-api03-..."  # ❌ No quotes
ANTHROPIC_API_KEY = sk-ant-api03-...  # ❌ No spaces around =
ANTHROPIC_API_KEY=sk-ant-api03-...\n  # ❌ No newlines
```

### Step 3: Verify API Key is Valid

1. Go to https://console.anthropic.com/
2. Check your API keys
3. Make sure the key you're using:
   - Is active
   - Has credits available
   - Hasn't expired
   - Is for the correct organization

### Step 4: Test with curl

Test the API key directly:
```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: YOUR_KEY_HERE" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 10,
    "messages": [{"role": "user", "content": "test"}]
  }'
```

## Fix Applied

I've added:
1. ✅ Whitespace stripping in `base_agent.py`
2. ✅ Better error messages
3. ✅ API key validation
4. ✅ Test script to verify the key

## Next Steps

1. Run `python3 test_anthropic_key.py` to see the exact error
2. Check your Anthropic console to verify the key is valid
3. If the key is invalid, generate a new one and update `.env`
4. Make sure there are no quotes or spaces in your `.env` file

