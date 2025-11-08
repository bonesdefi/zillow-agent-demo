"""Configuration management for the application."""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache
from dotenv import load_dotenv

# Try to import streamlit for secrets management (for Streamlit Cloud deployment)
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False
    st = None

# Load .env file at module import (for local development)
# Use override=True to ensure .env values take precedence over system env vars
# Note: Streamlit Cloud uses st.secrets, not .env files
load_dotenv(override=True)


def _get_env_var(key: str, default: str = "") -> str:
    """
    Get environment variable with priority:
    1. Streamlit secrets (for Streamlit Cloud deployment)
    2. Environment variables (for local development)
    3. Default value
    
    Streamlit secrets are accessed as: st.secrets[key] or st.secrets.KEY_NAME
    """
    # First, try Streamlit secrets (for Streamlit Cloud deployment)
    if STREAMLIT_AVAILABLE and st is not None:
        try:
            # Check if we're in a Streamlit context and secrets are available
            if hasattr(st, 'secrets'):
                # Try accessing secrets as a dictionary first
                try:
                    # Streamlit secrets can be accessed like a dict
                    if key in st.secrets:
                        value = st.secrets[key]
                        if value:
                            return str(value)
                except (TypeError, KeyError, AttributeError):
                    # If dict access doesn't work, try attribute access
                    try:
                        # Some versions use attribute access: st.secrets.ANTHROPIC_API_KEY
                        if hasattr(st.secrets, key):
                            value = getattr(st.secrets, key)
                            if value:
                                return str(value)
                    except (AttributeError, Exception):
                        pass
        except (AttributeError, RuntimeError, Exception):
            # Not in Streamlit context, secrets not available, or runtime error
            # Continue to environment variables
            pass
    
    # Fall back to environment variables (for local development)
    return os.getenv(key, default)


class Settings(BaseSettings):
    """Application settings loaded from environment variables or Streamlit secrets."""

    # LLM API Keys
    anthropic_api_key: str = _get_env_var("ANTHROPIC_API_KEY", "")
    anthropic_model: str = _get_env_var("ANTHROPIC_MODEL", "claude-3-haiku-20240307")

    # Real Estate Data API (for property search and details)
    rapidapi_key: str = _get_env_var("RAPIDAPI_KEY", "")
    zillow_api_base_url: str = _get_env_var(
        "ZILLOW_API_BASE_URL", "https://real-time-zillow-data.p.rapidapi.com"
    )
    zillow_api_host: str = _get_env_var(
        "ZILLOW_API_HOST", "real-time-zillow-data.p.rapidapi.com"
    )

    # Zillow Working API (for market analytics - housing_market endpoint)
    zillow_market_api_base_url: str = _get_env_var(
        "ZILLOW_MARKET_API_BASE_URL", "https://zillow-working-api.p.rapidapi.com"
    )
    zillow_market_api_host: str = _get_env_var(
        "ZILLOW_MARKET_API_HOST", "zillow-working-api.p.rapidapi.com"
    )

    # MCP Server Configuration
    mcp_server_host: str = _get_env_var("MCP_SERVER_HOST", "localhost")
    mcp_server_port_real_estate: int = int(
        _get_env_var("MCP_SERVER_PORT_REAL_ESTATE", "8001")
    )
    mcp_server_port_market_analysis: int = int(
        _get_env_var("MCP_SERVER_PORT_MARKET_ANALYSIS", "8002")
    )
    mcp_server_port_user_context: int = int(
        _get_env_var("MCP_SERVER_PORT_USER_CONTEXT", "8003")
    )

    # Application Configuration
    log_level: str = _get_env_var("LOG_LEVEL", "INFO")
    enable_debug_mode: bool = _get_env_var("ENABLE_DEBUG_MODE", "false").lower() == "true"

    # Streamlit Configuration
    streamlit_server_port: int = int(_get_env_var("STREAMLIT_SERVER_PORT", "8501"))

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

