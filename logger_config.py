import logging
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Create logger
logger = logging.getLogger("instagram_scraper")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# Console handler with formatting
console_handler = logging.StreamHandler()
console_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)

def get_logger(name: str) -> logging.Logger:
    """Get logger for a module"""
    return logging.getLogger(f"instagram_scraper.{name}")
