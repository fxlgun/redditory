"""
Logging configuration module for the Redditory pipeline.
Sets up structured logging across all modules.
"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime

# Create logs directory if it doesn't exist
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

# Timestamp for log file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOGS_DIR / f"redditory_{timestamp}.log"


def setup_logger(name: str) -> logging.Logger:
    """
    Create and configure a logger for a specific module.
    
    Args:
        name: The name of the module (typically __name__)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Avoid duplicate handlers
    if logger.hasHandlers():
        return logger
    
    # Create formatter
    formatter = logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler (INFO level)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (DEBUG level - captures everything)
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=10_000_000,  # 10 MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


# Get a logger for the config module itself
logger = setup_logger(__name__)
logger.info(f"Logging initialized. Log file: {LOG_FILE}")
