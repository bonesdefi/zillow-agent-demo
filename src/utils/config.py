"""Configuration management for the application."""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache
from dotenv import load_dotenv

# Load .env file at module import
# Use override=True to ensure .env values take precedence
load_dotenv(override=True)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM API Keys
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")

    # Real Estate Data API
    rapidapi_key: str = os.getenv("RAPIDAPI_KEY", "")
    zillow_api_base_url: str = os.getenv(
        "ZILLOW_API_BASE_URL", "https://zillow-working-api.p.rapidapi.com"
    )
    zillow_api_host: str = os.getenv(
        "ZILLOW_API_HOST", "zillow-working-api.p.rapidapi.com"
    )

    # MCP Server Configuration
    mcp_server_host: str = os.getenv("MCP_SERVER_HOST", "localhost")
    mcp_server_port_real_estate: int = int(
        os.getenv("MCP_SERVER_PORT_REAL_ESTATE", "8001")
    )
    mcp_server_port_market_analysis: int = int(
        os.getenv("MCP_SERVER_PORT_MARKET_ANALYSIS", "8002")
    )
    mcp_server_port_user_context: int = int(
        os.getenv("MCP_SERVER_PORT_USER_CONTEXT", "8003")
    )

    # Application Configuration
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    enable_debug_mode: bool = os.getenv("ENABLE_DEBUG_MODE", "false").lower() == "true"

    # Streamlit Configuration
    streamlit_server_port: int = int(os.getenv("STREAMLIT_SERVER_PORT", "8501"))

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

