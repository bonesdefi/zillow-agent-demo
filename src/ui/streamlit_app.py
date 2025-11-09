"""
Streamlit UI for Real Estate AI Assistant.

This is the main entry point for the web application.
Provides a chat interface for interacting with the multi-agent system.

Version: 1.0.1 - Fixed FunctionTool callable issue
"""

import streamlit as st
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
import os
import sys
import logging
from dotenv import load_dotenv

# Load .env file first before any other imports
# Use override=True to ensure .env values take precedence
load_dotenv(override=True)

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.graph.workflow import create_workflow
from src.graph.state import AgentState

# Configure logging to show in terminal where Streamlit runs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Ensure logs go to stdout
    ]
)
logger = logging.getLogger(__name__)
# Set log level for all our modules
logging.getLogger("src").setLevel(logging.INFO)
logging.getLogger("agent").setLevel(logging.INFO)

# Page configuration
st.set_page_config(
    page_title="Real Estate AI Assistant",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    /* Main title styling */
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    
    /* Subtitle styling */
    .subtitle {
        font-size: 1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    
    /* Property card styling */
    .property-card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        background: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Agent activity styling */
    .agent-log {
        font-family: monospace;
        font-size: 0.85rem;
        padding: 0.5rem;
        background: #f8f9fa;
        border-left: 3px solid #1f77b4;
        margin: 0.5rem 0;
    }
    
    /* Status indicators */
    .status-active {
        color: #28a745;
        font-weight: bold;
    }
    
    .status-complete {
        color: #6c757d;
    }
    
    /* Search criteria box */
    .criteria-box {
        background: #e7f3ff;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "agent_logs" not in st.session_state:
        st.session_state.agent_logs = []
    
    if "search_criteria" not in st.session_state:
        st.session_state.search_criteria = None
    
    if "properties" not in st.session_state:
        st.session_state.properties = []
    
    if "analyses" not in st.session_state:
        st.session_state.analyses = {}
    
    if "workflow" not in st.session_state:
        st.session_state.workflow = None
    
    if "processing" not in st.session_state:
        st.session_state.processing = False


def add_agent_log(agent: str, action: str, data: Optional[Dict[str, Any]] = None):
    """Add agent activity log."""
    log_entry = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "agent": agent,
        "action": action,
        "data": data or {}
    }
    st.session_state.agent_logs.append(log_entry)
    
    # Keep only last 20 logs
    if len(st.session_state.agent_logs) > 20:
        st.session_state.agent_logs = st.session_state.agent_logs[-20:]


def display_agent_activity_sidebar():
    """Display agent activity monitor in sidebar."""
    with st.sidebar:
        st.markdown("### 🤖 Agent Activity")
        st.caption("Real-time agent coordination")
        
        if not st.session_state.agent_logs:
            st.info("Waiting for activity...")
        else:
            # Show logs in reverse order (newest first)
            for log in reversed(st.session_state.agent_logs[-10:]):
                with st.expander(
                    f"**{log['agent']}** - {log['timestamp']}",
                    expanded=False
                ):
                    st.text(log['action'])
                    if log['data']:
                        st.json(log['data'], expanded=False)
        
        st.divider()
        
        # Current search criteria
        if st.session_state.search_criteria:
            st.markdown("### 📊 Current Search")
            st.json(st.session_state.search_criteria, expanded=True)
        
        st.divider()
        
        # System status
        st.markdown("### 📈 System Status")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Messages", len(st.session_state.messages))
        with col2:
            st.metric("Properties", len(st.session_state.properties))


def display_property_card(property_data: Dict[str, Any], index: int):
    """
    Display a single property in card format.
    
    Args:
        property_data: Property information
        index: Property index for unique keys
    """
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col1:
            # Property image
            image_url = property_data.get("image_url")
            if image_url:
                try:
                    st.image(image_url, use_container_width=True)
                except Exception:
                    st.image("https://via.placeholder.com/300x200?text=No+Image", 
                            use_container_width=True)
            else:
                # Placeholder if no image
                st.image("https://via.placeholder.com/300x200?text=No+Image", 
                        use_container_width=True)
        
        with col2:
            # Property details
            st.subheader(property_data.get("address", "Address not available"))
            
            # Price
            price = property_data.get("price", 0)
            st.markdown(f"### ${price:,}")
            
            # Basic info
            bedrooms = property_data.get("bedrooms", "N/A")
            bathrooms = property_data.get("bathrooms", "N/A")
            sqft = property_data.get("square_feet", 0)
            
            info_text = f"{bedrooms} bed • {bathrooms} bath"
            if sqft:
                info_text += f" • {sqft:,} sqft"
            st.text(info_text)
            
            # Property type
            prop_type = property_data.get("property_type", "N/A")
            st.caption(f"Type: {prop_type}")
        
        with col3:
            # Link to listing
            listing_url = property_data.get("listing_url")
            if listing_url:
                st.markdown(f"[🔗 View on Zillow]({listing_url})")
        
        # Analysis results (if available)
        property_id = property_data.get("id")
        if property_id and property_id in st.session_state.analyses:
            analysis = st.session_state.analyses[property_id]
            
            with st.expander("📊 AI Analysis", expanded=False):
                # Summary
                if "summary" in analysis:
                    summary = analysis["summary"]
                    
                    if isinstance(summary, dict):
                        if "pros" in summary and summary["pros"]:
                            st.markdown("**✅ Pros:**")
                            for pro in summary["pros"]:
                                st.markdown(f"- {pro}")
                        
                        if "cons" in summary and summary["cons"]:
                            st.markdown("**⚠️ Cons:**")
                            for con in summary["cons"]:
                                st.markdown(f"- {con}")
                        
                        if "overall" in summary:
                            st.markdown(f"**Overall:** {summary['overall']}")
                
                # Detailed data tabs
                tab1, tab2 = st.tabs(["🏫 Schools", "📈 Market"])
                
                with tab1:
                    if analysis.get("schools"):
                        schools = analysis["schools"]
                        if isinstance(schools, list):
                            for school in schools:
                                if isinstance(school, dict):
                                    st.markdown(f"**{school.get('name', 'Unknown')}**")
                                    st.text(f"Rating: {school.get('rating', 'N/A')}/10")
                                    if 'distance_miles' in school:
                                        st.text(f"Distance: {school['distance_miles']} miles")
                                    st.divider()
                        else:
                            st.json(schools, expanded=True)
                    else:
                        st.info("School data not available")
                
                with tab2:
                    if analysis.get("market_trends"):
                        st.json(analysis["market_trends"], expanded=True)
                    else:
                        st.info("Market data not available")
        
        st.divider()


async def process_user_message(user_input: str):
    """
    Process user message through the workflow.
    
    Args:
        user_input: User's message
    """
    # Add user message to chat
    st.session_state.messages.append({
        "role": "user",
        "content": user_input,
        "timestamp": datetime.now()
    })
    
    # Initialize workflow if needed
    if not st.session_state.workflow:
        add_agent_log("System", "Initializing workflow")
        try:
            st.session_state.workflow = create_workflow()
            add_agent_log("System", "Workflow initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize workflow: {e}")
            add_agent_log("System", f"Workflow initialization failed: {str(e)}")
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"I encountered an error initializing the system: {str(e)}",
                "timestamp": datetime.now()
            })
            return
    
    # Create initial state (using LangGraph AgentState TypedDict)
    conversation_history = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in st.session_state.messages[:-1]  # Exclude current message
    ]
    
    initial_state: AgentState = {
        "messages": conversation_history,
        "user_input": user_input,
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
        "conversation_history": conversation_history,
    }
    
    try:
        # Process through workflow
        add_agent_log("Workflow", f"Processing: {user_input[:50]}...")
        logger.info(f"Invoking workflow with user_input: {user_input}")
        logger.info(f"Initial state keys: {list(initial_state.keys())}")
        
        # Add detailed logging before invoking
        import traceback
        try:
            result = await st.session_state.workflow.ainvoke(initial_state)
            logger.info("Workflow invocation completed successfully")
        except Exception as workflow_error:
            logger.error(f"Workflow invocation failed: {workflow_error}", exc_info=True)
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        
        logger.info(f"Workflow completed. Result type: {type(result)}")
        logger.info(f"Result keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
        logger.info(f"Final response: {result.get('final_response', 'None')[:100] if result.get('final_response') else 'None'}")
        logger.info(f"Search criteria: {result.get('search_criteria')}")
        logger.info(f"Properties count: {len(result.get('properties', []))}")
        logger.info(f"Errors: {result.get('errors', [])}")
        logger.info(f"Needs clarification: {result.get('needs_clarification', False)}")
        
        # Update session state (result is AgentState TypedDict)
        if result.get("search_criteria"):
            st.session_state.search_criteria = result["search_criteria"]
            add_agent_log("Search", "Criteria extracted", result["search_criteria"])
            logger.info(f"Updated search_criteria: {result['search_criteria']}")
        else:
            logger.warning("No search_criteria in result")
        
        if result.get("properties"):
            st.session_state.properties = result["properties"]
            add_agent_log("Search", f"Found {len(result['properties'])} properties")
            logger.info(f"Updated properties: {len(result['properties'])}")
        else:
            logger.warning("No properties in result")
        
        if result.get("analyses"):
            st.session_state.analyses = result["analyses"]
            add_agent_log("Analysis", f"Analyzed {len(result['analyses'])} properties")
        
        # Get final response
        final_response = result.get("final_response", "")
        
        # Handle errors
        if result.get("errors"):
            error_list = result["errors"]
            logger.error(f"Workflow errors: {error_list}")
            if not final_response:
                final_response = f"I encountered some errors: {', '.join(error_list[:3])}"
        
        # Handle clarification
        if result.get("needs_clarification") and result.get("clarification_question"):
            final_response = result["clarification_question"]
            add_agent_log("Workflow", "Clarification needed")
            logger.info("Clarification needed")
        elif not final_response:
            # Fallback response if nothing was generated
            if result.get("properties"):
                final_response = f"I found {len(result['properties'])} properties matching your criteria."
            else:
                final_response = "I processed your request, but couldn't find any properties. Please try adjusting your search criteria."
            logger.warning(f"No final_response generated, using fallback: {final_response}")
        
        # Add assistant response
        st.session_state.messages.append({
            "role": "assistant",
            "content": final_response,
            "timestamp": datetime.now()
        })
        
        add_agent_log("Workflow", "Completed successfully")
        logger.info(f"Added assistant response: {final_response[:100]}")
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"Error processing message: {e}", exc_info=True)
        logger.error(f"Full traceback: {error_traceback}")
        
        # More detailed error message
        error_message = f"I encountered an error: {str(e)}. Please try again."
        if hasattr(e, '__cause__') and e.__cause__:
            error_message += f" Cause: {str(e.__cause__)}"
        
        st.session_state.messages.append({
            "role": "assistant",
            "content": error_message,
            "timestamp": datetime.now()
        })
        add_agent_log("System", f"Error: {str(e)}", {
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": error_traceback[:500]  # First 500 chars of traceback
        })


def run_async(coro):
    """Run async function in Streamlit."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def main():
    """Main application entry point."""
    initialize_session_state()
    
    # Header
    st.markdown('<h1 class="main-title">🏠 Real Estate AI Assistant</h1>', 
                unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Multi-Agent System Demo • Built with LangGraph & MCP Servers</p>', 
                unsafe_allow_html=True)
    
    # Sidebar
    display_agent_activity_sidebar()
    
    # Main layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 💬 Conversation")
        
        # Chat container
        chat_container = st.container()
        with chat_container:
            # Display message history
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])
                    if "timestamp" in msg:
                        st.caption(msg["timestamp"].strftime("%I:%M %p"))
        
        # Chat input
        if not st.session_state.processing:
            user_input = st.chat_input("What are you looking for?")
            
            if user_input:
                st.session_state.processing = True
                
                # Display user message immediately
                with st.chat_message("user"):
                    st.write(user_input)
                
                # Process message
                with st.spinner("🤖 Agents are working..."):
                    try:
                        run_async(process_user_message(user_input))
                    except Exception as e:
                        logger.error(f"Error in main: {e}", exc_info=True)
                        st.error(f"An error occurred: {str(e)}")
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": f"I encountered an error: {str(e)}",
                            "timestamp": datetime.now()
                        })
                
                st.session_state.processing = False
                st.rerun()
        else:
            st.info("Processing your request...")
    
    with col2:
        st.markdown("### 🔍 Search Summary")
        
        if st.session_state.search_criteria:
            st.markdown('<div class="criteria-box">', unsafe_allow_html=True)
            
            criteria = st.session_state.search_criteria
            if criteria.get("location"):
                st.markdown(f"**📍 Location:** {criteria['location']}")
            if criteria.get("max_price"):
                st.markdown(f"**💰 Max Price:** ${criteria['max_price']:,}")
            if criteria.get("min_price"):
                st.markdown(f"**💰 Min Price:** ${criteria['min_price']:,}")
            if criteria.get("bedrooms"):
                st.markdown(f"**🛏️ Bedrooms:** {criteria['bedrooms']}")
            if criteria.get("bathrooms"):
                st.markdown(f"**🚿 Bathrooms:** {criteria['bathrooms']}")
            if criteria.get("property_type"):
                st.markdown(f"**🏡 Type:** {criteria['property_type']}")
            
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("Enter a search query to get started!")
        
        # Quick stats
        if st.session_state.properties:
            st.markdown("### 📊 Quick Stats")
            
            prices = [p.get("price", 0) for p in st.session_state.properties if p.get("price")]
            if prices:
                avg_price = sum(prices) / len(prices)
                min_price = min(prices)
                max_price = max(prices)
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("Avg Price", f"${avg_price:,.0f}")
                with col_b:
                    st.metric("Properties", len(prices))
                
                st.metric("Price Range", f"${min_price:,.0f} - ${max_price:,.0f}")
    
    # Property results section
    if st.session_state.properties:
        st.markdown("---")
        st.markdown("## 🏘️ Property Results")
        st.caption(f"Showing {len(st.session_state.properties)} properties")
        
        # Display properties
        for idx, prop in enumerate(st.session_state.properties[:10]):  # Limit to 10
            display_property_card(prop, idx)
    
    # Footer
    st.markdown("---")
    st.caption("Built with ❤️ using LangGraph, FastMCP, and Anthropic Claude")
    st.caption("Data powered by Zillow API • Portfolio project by Michael P.")


if __name__ == "__main__":
    main()
