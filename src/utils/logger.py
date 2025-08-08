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
    import os
    
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
    
    # Get log level from environment, default to INFO
    log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    
    # Configure handlers based on environment
    handlers = [logging.StreamHandler(sys.stderr)]
    
    # Only add file handler in debug mode and if path is specified
    debug_log_path = os.environ.get("DEBUG_LOG_PATH")
    if debug_log_path and log_level == logging.DEBUG:
        try:
            log_file = Path(debug_log_path)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(log_file, mode='a', encoding='utf-8'))
        except Exception as e:
            # If file handler fails, just use stderr
            sys.stderr.write(f"Warning: Could not create log file handler: {e}\n")
    
    # Configure standard logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=log_level,
        handlers=handlers
    )
    
    # Create logger
    if name:
        logger = structlog.get_logger(name)
    else:
        logger = structlog.get_logger()
    
    return logger