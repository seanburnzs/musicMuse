"""
Live Scrobbler service package.
"""
import logging
from logging.handlers import RotatingFileHandler
import os

# Configure logging
def setup_logging(log_level=None):
    """
    Set up logging for the application.
    
    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO")
    
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(numeric_level)
    
    # Clear existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # Create file handler
    file_handler = RotatingFileHandler(
        os.path.join(logs_dir, "live_scrobbler.log"),
        maxBytes=10485760,  # 10 MB
        backupCount=10
    )
    file_handler.setLevel(numeric_level)
    file_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    # Set up specific loggers
    for logger_name in ["spotipy", "urllib3", "requests"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    logger.info(f"Logging configured with level {log_level}")

# Set up logging when the package is imported
setup_logging() 