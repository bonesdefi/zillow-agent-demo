#!/usr/bin/env python3
"""Check script to test env execution."""

import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# Load .env file FIRST - this will load all environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.abspath('.'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Verify API key is loaded
api_key = os.getenv("ANTHROPIC_API_KEY")
if api_key:
    print(f"✅ API key loaded: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else ''}")
else:
    print("❌ WARNING: ANTHROPIC_API_KEY not found in environment!")
    print("   Make sure you have a .env file with ANTHROPIC_API_KEY set")

from src.graph.env import create_env
from src.graph.state import AgentState

async def test_env():
    """Test env execution."""
    print("=" * 60)
    print("ENV CHECK TEST")
    print("=" * 60)
    
    # Create env
    print("\n1. Creating env...")
    try:
        env = create_env()
        print("✅ Env created successfully")
    except Exception as e:
        print(f"❌ Error creating env: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Create test state
    print("\n2. Creating test state...")
    test_state: AgentState = {
        "messages": [],
        "user_input": "Find a 3 bedroom 2 bath house in 89044 henderson nv",
        "search_criteria": None,
        "properties": [],
        "analyses": {},
        "recommendations": [],
        "final_response": "",
        "current_step": "start",
        "needs_clarification": False,
        "clarification_question": None,
        "errors": [],
        "user_preferences": None,
        "conversation_history": [],
    }
    print(f"✅ Test state created - user_input: {test_state['user_input']}")
    
    # Execute env
    print("\n3. Executing env...")
    try:
        result = await env.ainvoke(test_state)
        print("✅ Env executed")
    except Exception as e:
        print(f"❌ Error executing env: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Check results
    print("\n4. Checking results...")
    print(f"   Result type: {type(result)}")
    print(f"   Result keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
    print(f"   Final response: {result.get('final_response', 'None')[:200] if result.get('final_response') else 'None'}")
    print(f"   Search criteria: {result.get('search_criteria')}")
    print(f"   Properties count: {len(result.get('properties', []))}")
    print(f"   Analyses count: {len(result.get('analyses', {}))}")
    print(f"   Recommendations count: {len(result.get('recommendations', []))}")
    print(f"   Errors: {result.get('errors', [])}")
    print(f"   Needs clarification: {result.get('needs_clarification')}")
    
    # Detailed check
    if result.get("properties"):
        print(f"\n   First property: {result['properties'][0]}")
    else:
        print("\n   ⚠️  No properties found!")
    
    if result.get("final_response"):
        print(f"\n   ✅ Final response exists: {result['final_response'][:100]}")
    else:
        print("\n   ❌ No final response generated!")
    
    print("\n" + "=" * 60)
    print("CHECK TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_env())

