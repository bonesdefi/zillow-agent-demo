"""Logging configuration for the application."""

import logging
import sys
from typing import Optional
from src.utils.config import get_settings


def setup_logging(
    name: str, level: Optional[str] = None, format_string: Optional[str] = None
) -> logging.Logger:
    """
    Set up logging for a module.

    Args:
        name: Logger name (typically __name__)
        level: Log level (defaults to settings.log_level)
        format_string: Custom format string

    Returns:
        Configured logger instance
    """
    settings = get_settings()
    log_level = level or settings.log_level

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Avoid adding multiple handlers
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if format_string is None:
        format_string = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "%(funcName)s:%(lineno)d - %(message)s"
        )

    formatter = logging.Formatter(format_string)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger

