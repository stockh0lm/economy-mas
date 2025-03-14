# logger.py
import logging
from typing import Literal, Optional
from config import CONFIG

# Logger level types
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

def setup_logger(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    log_format: Optional[str] = None,
    file_mode: Literal["w", "a"] = "w"
) -> logging.Logger:
    """
    Configure and return a logger instance based on configuration parameters.

    Args:
        level: Logging level (defaults to CONFIG or DEBUG)
        log_file: Log file path (defaults to CONFIG or 'simulation.log')
        log_format: Log message format (defaults to CONFIG or standard format)
        file_mode: File writing mode - 'w' for overwrite, 'a' for append

    Returns:
        Configured logging.Logger instance
    """
    # Get configuration from CONFIG with defaults
    config_level = level or CONFIG.get("logging_level", "DEBUG")
    config_file = log_file or CONFIG.get("log_file", "simulation.log")
    config_format = log_format or CONFIG.get(
        "log_format",
        "%(asctime)s - %(levelname)s - %(message)s"
    )

    # Convert string level to logging constant
    level_map: dict[str, int] = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }

    numeric_level = level_map.get(config_level.upper(), logging.DEBUG)

    # Configure the logger
    logging.basicConfig(
        level=numeric_level,
        format=config_format,
        filename=config_file,
        filemode=file_mode
    )

    return logging.getLogger()

def log(message: str, level: LogLevel = "DEBUG") -> None:
    """
    Log a message at the specified level.

    Args:
        message: The message to log
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    match level.upper():
        case "INFO":
            logging.info(message)
        case "WARNING":
            logging.warning(message)
        case "ERROR":
            logging.error(message)
        case "CRITICAL":
            logging.critical(message)
        case _:
            logging.debug(message)

# Initialize logger when module is imported
logger = setup_logger()