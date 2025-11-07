#!/usr/bin/env python3
"""Test Anthropic API key directly."""

import os
import sys
from dotenv import load_dotenv
from anthropic import AsyncAnthropic
import asyncio

# Load .env
load_dotenv(override=True)

# Get API key
api_key = os.getenv("ANTHROPIC_API_KEY")

if not api_key:
    print("❌ ANTHROPIC_API_KEY not found!")
    sys.exit(1)

print("=" * 60)
print("ANTHROPIC API KEY TEST")
print("=" * 60)
print(f"Key length: {len(api_key)}")
print(f"Key starts with: {api_key[:10]}...")
print(f"Key ends with: ...{api_key[-10:]}")
print(f"Has whitespace/newlines: {api_key != api_key.strip()}")
print(f"Key stripped length: {len(api_key.strip())}")

# Check for common issues
if api_key != api_key.strip():
    print("\n⚠️  WARNING: Key has leading/trailing whitespace!")
    print("   Original length:", len(api_key))
    print("   Stripped length:", len(api_key.strip()))
    api_key = api_key.strip()

if not api_key.startswith("sk-ant-"):
    print("\n❌ ERROR: Key doesn't start with 'sk-ant-'")
    print(f"   Got: {api_key[:15]}...")
    sys.exit(1)

print("\n" + "-" * 60)
print("Testing API key with Anthropic...")
print("-" * 60)

async def test_api_key():
    """Test the API key with a simple request."""
    try:
        client = AsyncAnthropic(api_key=api_key)
        
        # Make a simple test request with Claude Haiku
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
        response = await client.messages.create(
            model=model,
            max_tokens=10,
            messages=[
                {"role": "user", "content": "Say 'test'"}
            ]
        )
        
        print("✅ API key is VALID!")
        print(f"   Response: {response.content[0].text}")
        return True
        
    except Exception as e:
        print(f"❌ API key test FAILED: {e}")
        if "401" in str(e) or "authentication" in str(e).lower():
            print("\n   This means the API key is INVALID or EXPIRED.")
            print("   Please check:")
            print("   1. The key in your .env file is correct")
            print("   2. The key hasn't expired")
            print("   3. The key has credits available")
            print("   4. There are no extra spaces or quotes in .env")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_api_key())
    print("\n" + "=" * 60)
    sys.exit(0 if result else 1)

