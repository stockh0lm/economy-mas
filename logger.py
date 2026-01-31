# logger.py
import logging
from pathlib import Path
from typing import Literal

from config import CONFIG_MODEL

# Logger level types
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def setup_logger(
    level: str | None = None,
    log_file: str | None = None,
    log_format: str | None = None,
    file_mode: Literal["w", "a"] = "w",
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
    config_level = level or CONFIG_MODEL.logging_level
    config_file = log_file or CONFIG_MODEL.log_file
    config_format = log_format or CONFIG_MODEL.log_format

    # Ensure the log directory exists (fresh checkouts often miss /output).
    try:
        log_path = Path(config_file)
        if log_path.parent and str(log_path.parent) != ".":
            log_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        # If anything goes wrong, proceed and let logging raise a clear error.
        pass

    # Convert string level to logging constant
    level_map: dict[str, int] = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    numeric_level = level_map.get(config_level.upper(), logging.DEBUG)

    # Configure the logger
    logging.basicConfig(
        level=numeric_level, format=config_format, filename=config_file, filemode=file_mode
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


# Removed eager module-level initialization; call setup_logger() explicitly where needed.
