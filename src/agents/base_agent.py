"""Base agent class for all AI agents."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import os
from dotenv import load_dotenv

# Load .env file to ensure environment variables are available
load_dotenv(override=True)

from anthropic import AsyncAnthropic
from pydantic import BaseModel


class AgentState(BaseModel):
    """Represents the current state passed to agents."""

    user_input: str
    conversation_history: list[Dict[str, str]] = []
    search_criteria: Optional[Dict[str, Any]] = None
    properties: list[Dict[str, Any]] = []
    analyses: Dict[str, Dict[str, Any]] = {}
    recommendations: list[Dict[str, Any]] = []
    final_response: str = ""
    errors: list[str] = []
    needs_clarification: bool = False
    clarification_question: Optional[str] = None


class BaseAgent(ABC):
    """
    Base class for all AI agents in the multi-agent system.

    Provides common functionality:
    - LLM client initialization
    - Logging setup
    - Error handling patterns
    - MCP server communication

    All agents must implement the `process` method.
    """

    def __init__(self, name: str, model: Optional[str] = None):
        """
        Initialize base agent.

        Args:
            name: Agent name for logging and identification
            model: Claude model to use (defaults to ANTHROPIC_MODEL env var or claude-3-haiku-20240307)
        """
        self.name = name
        # Get model from parameter, environment variable, or default to Claude Haiku
        if model is None:
            # Default to Claude Haiku if not specified
            self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
        else:
            self.model = model
        self.logger = logging.getLogger(f"agent.{name}")

        # Initialize Anthropic client
        # Ensure .env is loaded (reload in case it wasn't loaded at import time)
        load_dotenv(override=True)  # override=True ensures .env takes precedence
        
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Please create a .env file in the project root with: ANTHROPIC_API_KEY=your_key"
            )
        
        # Strip whitespace (common issue with .env files)
        api_key = api_key.strip()
        
        # Verify key looks valid (Anthropic keys start with 'sk-ant-')
        if not api_key.startswith("sk-ant-"):
            self.logger.error(
                f"API key doesn't look like a valid Anthropic key (should start with 'sk-ant-'). "
                f"Got: {api_key[:20]}... (length: {len(api_key)})"
            )
            raise ValueError(
                f"Invalid API key format. Expected key starting with 'sk-ant-', got: {api_key[:20]}..."
            )
        
        # Log key info for debugging (masked)
        self.logger.info(
            f"Using API key: {api_key[:10]}...{api_key[-4:]} (length: {len(api_key)})"
        )

        self.client = AsyncAnthropic(api_key=api_key)

        self.logger.info(f"Initialized {name} agent with model {self.model}")

    @abstractmethod
    async def process(self, state: AgentState) -> AgentState:
        """
        Process the current state and return updated state.

        This is the main entry point for each agent. Agents receive
        the current state, perform their task, and return updated state.

        Args:
            state: Current agent state

        Returns:
            Updated agent state

        Raises:
            Exception: If processing fails
        """
        pass

    async def _call_llm(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """
        Call Claude LLM with error handling.

        Args:
            system_prompt: System instructions for the LLM
            user_message: User message to process
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens in response

        Returns:
            LLM response text

        Raises:
            Exception: If LLM call fails after retries
        """
        self.logger.info(f"{self.name}: Calling LLM")

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            # Extract text from response
            text = response.content[0].text
            self.logger.info(f"{self.name}: Received LLM response ({len(text)} chars)")
            return text

        except Exception as e:
            self.logger.error(f"{self.name}: LLM call failed: {e}")
            raise

    def _add_error(self, state: AgentState, error: str) -> AgentState:
        """
        Add error message to state.

        Args:
            state: Current state
            error: Error message

        Returns:
            Updated state with error
        """
        self.logger.warning(f"{self.name}: {error}")
        state.errors.append(f"{self.name}: {error}")
        return state

    def _log_processing(self, message: str) -> None:
        """
        Log processing step.

        Args:
            message: Message to log
        """
        self.logger.info(f"{self.name}: {message}")


class AgentError(Exception):
    """Base exception for agent errors."""

    pass


class AgentLLMError(AgentError):
    """Exception for LLM-related errors."""

    pass


class AgentMCPError(AgentError):
    """Exception for MCP server communication errors."""

    pass

