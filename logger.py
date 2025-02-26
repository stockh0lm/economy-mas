import logging

def setup_logger():
    # Konfiguration des Loggers
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename='simulation.log',
        filemode='w'
    )
    return logging.getLogger()

def log(message, level="DEBUG"):
    if level.upper() == "INFO":
        logging.info(message)
    elif level.upper() == "WARNING":
        logging.warning(message)
    elif level.upper() == "ERROR":
        logging.error(message)
    else:
        logging.debug(message)
