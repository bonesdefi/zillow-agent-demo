#!/usr/bin/env python3
"""Debug script to test workflow execution."""

import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# Load .env file FIRST - this will load all environment variables
# Use override=True to ensure .env values take precedence over existing env vars
load_dotenv(override=True)

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
    if api_key == "test_key" or len(api_key) < 20:
        print(f"❌ WARNING: API key looks invalid: {api_key[:20]}...")
        print("   This might be a placeholder. Check your .env file.")
    else:
        print(f"✅ API key loaded: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else ''} (length: {len(api_key)})")
else:
    print("❌ WARNING: ANTHROPIC_API_KEY not found in environment!")
    print("   Make sure you have a .env file with ANTHROPIC_API_KEY set")

from src.graph.workflow import create_workflow
from src.graph.state import AgentState

async def test_workflow():
    """Test workflow execution."""
    print("=" * 60)
    print("WORKFLOW DEBUG TEST")
    print("=" * 60)
    
    # Create workflow
    print("\n1. Creating workflow...")
    try:
        workflow = create_workflow()
        print("✅ Workflow created successfully")
    except Exception as e:
        print(f"❌ Error creating workflow: {e}")
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
    
    # Execute workflow
    print("\n3. Executing workflow...")
    try:
        result = await workflow.ainvoke(test_state)
        print("✅ Workflow executed")
    except Exception as e:
        print(f"❌ Error executing workflow: {e}")
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
    print("DEBUG TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_workflow())

