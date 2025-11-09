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
    
    # Zillow.com API (NEW - primary API for property search)
    zillow_com_api_base_url: str = "https://zillow-com1.p.rapidapi.com"
    zillow_com_api_host: str = "zillow-com1.p.rapidapi.com"

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
        Check Streamlit secrets and override values when available.
        Priority: Streamlit secrets > Environment variables > Defaults
        This runs after Pydantic BaseSettings loads from environment variables.
        """
        # Only check Streamlit secrets if we're in a Streamlit context
        if not STREAMLIT_AVAILABLE or st is None:
            return self
        
        try:
            if hasattr(st, 'secrets'):
                # Try to access secrets - Streamlit secrets work like a dict
                # Access secrets directly using getattr or dict access
                secrets_to_check = [
                    ('ANTHROPIC_API_KEY', 'anthropic_api_key', str),
                    ('ANTHROPIC_MODEL', 'anthropic_model', str),
                    ('RAPIDAPI_KEY', 'rapidapi_key', str),
                    ('ZILLOW_API_BASE_URL', 'zillow_api_base_url', str),
                    ('ZILLOW_API_HOST', 'zillow_api_host', str),
                    ('ZILLOW_MARKET_API_BASE_URL', 'zillow_market_api_base_url', str),
                    ('ZILLOW_MARKET_API_HOST', 'zillow_market_api_host', str),
                    ('ZILLOW_COM_API_BASE_URL', 'zillow_com_api_base_url', str),
                    ('ZILLOW_COM_API_HOST', 'zillow_com_api_host', str),
                    ('MCP_SERVER_HOST', 'mcp_server_host', str),
                    ('LOG_LEVEL', 'log_level', str),
                    ('MCP_SERVER_PORT_REAL_ESTATE', 'mcp_server_port_real_estate', int),
                    ('MCP_SERVER_PORT_MARKET_ANALYSIS', 'mcp_server_port_market_analysis', int),
                    ('MCP_SERVER_PORT_USER_CONTEXT', 'mcp_server_port_user_context', int),
                    ('STREAMLIT_SERVER_PORT', 'streamlit_server_port', int),
                    ('ENABLE_DEBUG_MODE', 'enable_debug_mode', lambda x: str(x).lower() == "true"),
                ]
                
                for secret_key, field_name, converter in secrets_to_check:
                    try:
                        # Try multiple ways to access secrets
                        secret_value = None
                        
                        # Method 1: Dict-style access
                        try:
                            if hasattr(st.secrets, '__contains__') and secret_key in st.secrets:
                                secret_value = st.secrets[secret_key]
                        except (TypeError, KeyError, AttributeError):
                            pass
                        
                        # Method 2: Attribute access (st.secrets.ANTHROPIC_API_KEY)
                        if secret_value is None:
                            try:
                                if hasattr(st.secrets, secret_key):
                                    secret_value = getattr(st.secrets, secret_key)
                            except (AttributeError, Exception):
                                pass
                        
                        # Method 3: Try get() method if available
                        if secret_value is None:
                            try:
                                if hasattr(st.secrets, 'get'):
                                    secret_value = st.secrets.get(secret_key)
                            except (Exception):
                                pass
                        
                        # If we found a secret value, apply it
                        if secret_value is not None and secret_value != "":
                            try:
                                if converter == str:
                                    setattr(self, field_name, str(secret_value))
                                elif converter == int:
                                    setattr(self, field_name, int(secret_value))
                                else:
                                    # For boolean converter (lambda)
                                    setattr(self, field_name, converter(secret_value))
                            except (ValueError, TypeError, Exception):
                                # Skip if conversion fails
                                pass
                                
                    except (AttributeError, Exception):
                        # Skip this secret if access fails
                        continue
                    
        except (AttributeError, RuntimeError, Exception):
            # If Streamlit secrets are not available, that's okay - use env vars/defaults
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

