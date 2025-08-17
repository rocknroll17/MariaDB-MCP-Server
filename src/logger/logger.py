import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from config import LOG_LEVEL

# Get the root logger
root_logger = logging.getLogger()
root_logger.setLevel(LOG_LEVEL)

# Create formatter
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Remove existing handlers to avoid duplication if script is reloaded
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
root_logger.addHandler(console_handler)

# File Handler - Create logs directory and set 7-day rotation
logs_dir = Path(__file__).parent.parent.parent / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)
log_file = logs_dir / "server.log"

file_handler = RotatingFileHandler(
    log_file,
    maxBytes=10 * 1024 * 1024,  # 10MB per file
    backupCount=7  # Keep 7 backup files (7 days)
)
file_handler.setFormatter(log_formatter)
root_logger.addHandler(file_handler)

# The specific logger used in server.py and elsewhere will inherit this configuration.
logger = logging.getLogger(__name__)