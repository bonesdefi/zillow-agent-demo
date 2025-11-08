#!/usr/bin/env python3
"""Test script to debug workflow issues."""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Load .env file first
load_dotenv(override=True)

# Add src to path
sys.path.insert(0, os.path.abspath('.'))

import logging

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

async def test_workflow():
    """Test the workflow with a simple query."""
    logger.info("=" * 60)
    logger.info("Testing workflow")
    logger.info("=" * 60)
    
    # Check environment variables
    logger.info("Checking environment variables...")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    rapidapi_key = os.getenv("RAPIDAPI_KEY")
    
    if anthropic_key:
        logger.info(f"✅ ANTHROPIC_API_KEY is set (length: {len(anthropic_key)})")
        logger.info(f"   Key starts with: {anthropic_key[:10]}...")
    else:
        logger.error("❌ ANTHROPIC_API_KEY is NOT set")
        return False
    
    if rapidapi_key:
        logger.info(f"✅ RAPIDAPI_KEY is set (length: {len(rapidapi_key)})")
        logger.info(f"   Key starts with: {rapidapi_key[:10]}...")
    else:
        logger.error("❌ RAPIDAPI_KEY is NOT set")
        return False
    
    logger.info("")
    logger.info("Creating workflow...")
    try:
        from src.graph.workflow import create_workflow
        workflow = create_workflow()
        logger.info("✅ Workflow created successfully")
    except Exception as e:
        logger.error(f"❌ Failed to create workflow: {e}", exc_info=True)
        return False
    
    logger.info("")
    logger.info("Testing with query: 'houses in las vegas under $600k'")
    
    from src.graph.state import AgentState
    
    initial_state: AgentState = {
        "messages": [],
        "user_input": "houses in las vegas under $600k",
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
    
    try:
        logger.info("Invoking workflow...")
        result = await workflow.ainvoke(initial_state)
        logger.info("✅ Workflow completed")
        logger.info("")
        logger.info("Results:")
        logger.info(f"  - Final response: {result.get('final_response', 'None')[:200]}")
        logger.info(f"  - Search criteria: {result.get('search_criteria')}")
        logger.info(f"  - Properties found: {len(result.get('properties', []))}")
        logger.info(f"  - Errors: {result.get('errors', [])}")
        logger.info(f"  - Needs clarification: {result.get('needs_clarification', False)}")
        
        if result.get('properties'):
            logger.info("")
            logger.info(f"First property: {result['properties'][0]}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Workflow failed: {e}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_workflow())
    sys.exit(0 if success else 1)

