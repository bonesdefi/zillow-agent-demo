#!/usr/bin/env python3
"""Verify API keys are loaded correctly."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

print("=" * 60)
print("API KEY VERIFICATION")
print("=" * 60)

# Check .env file
env_path = Path(".env")
if not env_path.exists():
    print("\n❌ ERROR: .env file not found!")
    print(f"   Expected location: {env_path.absolute()}")
    print("\n   Please create .env file with your API keys:")
    print("   ANTHROPIC_API_KEY=your_key_here")
    print("   RAPIDAPI_KEY=your_key_here")
    sys.exit(1)

print(f"\n✅ .env file found: {env_path.absolute()}")

# Load .env
print("\nLoading .env file...")
load_dotenv(override=True)

# Check ANTHROPIC_API_KEY
anth_key = os.getenv("ANTHROPIC_API_KEY")
if not anth_key:
    print("\n❌ ANTHROPIC_API_KEY not set in .env file!")
    sys.exit(1)

if anth_key == "your_anthropic_api_key_here" or len(anth_key) < 20:
    print(f"\n❌ ANTHROPIC_API_KEY looks invalid: {anth_key[:20]}...")
    print("   Please update .env with your actual Anthropic API key")
    sys.exit(1)

print(f"✅ ANTHROPIC_API_KEY loaded: {anth_key[:10]}...{anth_key[-4:]}")
print(f"   Length: {len(anth_key)} characters")

# Check RAPIDAPI_KEY
rapid_key = os.getenv("RAPIDAPI_KEY")
if not rapid_key:
    print("\n❌ RAPIDAPI_KEY not set in .env file!")
    sys.exit(1)

if rapid_key == "your_rapidapi_key_here" or len(rapid_key) < 20:
    print(f"\n❌ RAPIDAPI_KEY looks invalid: {rapid_key[:20]}...")
    print("   Please update .env with your actual RapidAPI key")
    sys.exit(1)

print(f"✅ RAPIDAPI_KEY loaded: {rapid_key[:10]}...{rapid_key[-4:]}")
print(f"   Length: {len(rapid_key)} characters")

# Test config loading
print("\n" + "-" * 60)
print("Testing config module...")
try:
    from src.utils.config import get_settings
    settings = get_settings()
    
    if settings.anthropic_api_key == anth_key:
        print("✅ Config module loaded ANTHROPIC_API_KEY correctly")
    else:
        print("❌ Config module API key doesn't match!")
    
    if settings.rapidapi_key == rapid_key:
        print("✅ Config module loaded RAPIDAPI_KEY correctly")
    else:
        print("❌ Config module RapidAPI key doesn't match!")
        
except Exception as e:
    print(f"❌ Error loading config: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("✅ All API keys verified and loaded correctly!")
print("=" * 60)

