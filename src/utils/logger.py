"""Logging configuration"""

import logging
import sys
from pathlib import Path
from typing import Optional

import structlog


def setup_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Setup structured logging
    
    Args:
        name: Logger name
        
    Returns:
        Configured logger
    """
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer() if sys.stderr.isatty() else structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=logging.INFO,
    )
    
    # Create logger
    if name:
        logger = structlog.get_logger(name)
    else:
        logger = structlog.get_logger()
    
    return logger