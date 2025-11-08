"""Configuration management for the application."""

import os
from typing import Optional, Any
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator
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
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-haiku-20240307"

    # Real Estate Data API (for property search and details)
    rapidapi_key: str = ""
    zillow_api_base_url: str = "https://real-time-zillow-data.p.rapidapi.com"
    zillow_api_host: str = "real-time-zillow-data.p.rapidapi.com"

    # Zillow Working API (for market analytics - housing_market endpoint)
    zillow_market_api_base_url: str = "https://zillow-working-api.p.rapidapi.com"
    zillow_market_api_host: str = "zillow-working-api.p.rapidapi.com"

    # MCP Server Configuration
    mcp_server_host: str = "localhost"
    mcp_server_port_real_estate: int = 8001
    mcp_server_port_market_analysis: int = 8002
    mcp_server_port_user_context: int = 8003

    # Application Configuration
    log_level: str = "INFO"
    enable_debug_mode: bool = False

    # Streamlit Configuration
    streamlit_server_port: int = 8501
    
    @model_validator(mode='after')
    def check_streamlit_secrets(self) -> 'Settings':
        """
        Check Streamlit secrets if environment variables are not set.
        This runs after Pydantic loads from environment variables.
        """
        # Only check Streamlit secrets if we're in a Streamlit context
        if not STREAMLIT_AVAILABLE or st is None:
            return self
        
        try:
            if hasattr(st, 'secrets'):
                # Update fields from Streamlit secrets if they're empty
                # Check each field and update from secrets if env var wasn't set
                secret_fields = {
                    'anthropic_api_key': 'ANTHROPIC_API_KEY',
                    'anthropic_model': 'ANTHROPIC_MODEL',
                    'rapidapi_key': 'RAPIDAPI_KEY',
                    'zillow_api_base_url': 'ZILLOW_API_BASE_URL',
                    'zillow_api_host': 'ZILLOW_API_HOST',
                    'zillow_market_api_base_url': 'ZILLOW_MARKET_API_BASE_URL',
                    'zillow_market_api_host': 'ZILLOW_MARKET_API_HOST',
                    'mcp_server_host': 'MCP_SERVER_HOST',
                    'log_level': 'LOG_LEVEL',
                }
                
                for field_name, secret_key in secret_fields.items():
                    # Only override if field is empty or default value
                    current_value = getattr(self, field_name, "")
                    if not current_value or current_value == "":
                        try:
                            # Try dict access first
                            if hasattr(st.secrets, '__getitem__'):
                                try:
                                    secret_value = st.secrets[secret_key]
                                    if secret_value:
                                        setattr(self, field_name, str(secret_value))
                                except (KeyError, TypeError):
                                    # Try attribute access
                                    if hasattr(st.secrets, secret_key):
                                        secret_value = getattr(st.secrets, secret_key)
                                        if secret_value:
                                            setattr(self, field_name, str(secret_value))
                        except (AttributeError, Exception):
                            pass
                
                # Handle integer fields
                if not self.mcp_server_port_real_estate or self.mcp_server_port_real_estate == 8001:
                    try:
                        port = _get_env_var("MCP_SERVER_PORT_REAL_ESTATE", "")
                        if port:
                            self.mcp_server_port_real_estate = int(port)
                    except (ValueError, Exception):
                        pass
                
                if not self.mcp_server_port_market_analysis or self.mcp_server_port_market_analysis == 8002:
                    try:
                        port = _get_env_var("MCP_SERVER_PORT_MARKET_ANALYSIS", "")
                        if port:
                            self.mcp_server_port_market_analysis = int(port)
                    except (ValueError, Exception):
                        pass
                
                if not self.mcp_server_port_user_context or self.mcp_server_port_user_context == 8003:
                    try:
                        port = _get_env_var("MCP_SERVER_PORT_USER_CONTEXT", "")
                        if port:
                            self.mcp_server_port_user_context = int(port)
                    except (ValueError, Exception):
                        pass
                
                if not self.streamlit_server_port or self.streamlit_server_port == 8501:
                    try:
                        port = _get_env_var("STREAMLIT_SERVER_PORT", "")
                        if port:
                            self.streamlit_server_port = int(port)
                    except (ValueError, Exception):
                        pass
                
                # Handle boolean field
                debug_mode = _get_env_var("ENABLE_DEBUG_MODE", "")
                if debug_mode:
                    self.enable_debug_mode = debug_mode.lower() == "true"
                    
        except (AttributeError, RuntimeError, Exception) as e:
            # If Streamlit secrets are not available, that's okay - we'll use env vars
            pass
        
        return self

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

