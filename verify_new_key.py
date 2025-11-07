#!/usr/bin/env python3
"""Verify the new API key is correctly set in .env"""

import os
import sys
from dotenv import load_dotenv
from anthropic import AsyncAnthropic
import asyncio

# Load .env
load_dotenv(override=True)

# Get API key
api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

print("=" * 60)
print("VERIFYING NEW API KEY")
print("=" * 60)

if not api_key:
    print("❌ ANTHROPIC_API_KEY not found in .env!")
    sys.exit(1)

print(f"✅ API key loaded from .env")
print(f"   Length: {len(api_key)}")
print(f"   Starts with: {api_key[:20]}...")
print(f"   Ends with: ...{api_key[-10:]}")
print()

# Check format
if not api_key.startswith("sk-ant-api03"):
    print("❌ Key doesn't start with 'sk-ant-api03'")
    sys.exit(1)

print("✅ Key format looks correct")
print()

# Test with Anthropic API
print("Testing API key with Anthropic...")
print("-" * 60)

async def test_key():
    try:
        # Use Claude Haiku model
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
        client = AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Say 'success'"}]
        )
        print("✅ API key is VALID and working!")
        print(f"   Response: {response.content[0].text}")
        return True
    except Exception as e:
        print(f"❌ API key test failed: {e}")
        if "401" in str(e) or "authentication" in str(e).lower():
            print("\n   The API key is being rejected by Anthropic.")
            print("   Please check:")
            print("   1. The key is correct in your .env file")
            print("   2. The key is active in Anthropic console")
            print("   3. The key has credits available")
        return False

result = asyncio.run(test_key())
print("=" * 60)
sys.exit(0 if result else 1)
