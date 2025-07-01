import os
from dotenv import load_dotenv
import logging
logger = logging.getLogger(__name__)
# Load environment variables from .env file
load_dotenv()

#--- Logging Configuration ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE_PATH = os.getenv("LOG_FILE", "logs/mcp_server.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", 10 * 1024 * 1024))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 5))

# --- Database Configuration ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# --- MCP Server Configuration ---
# Read-only mode
MCP_READ_ONLY = os.getenv("MCP_READ_ONLY", "true").lower() == "true"
MCP_MAX_POOL_SIZE = int(os.getenv("MCP_MAX_POOL_SIZE", 10))

# --- Validation ---
if not all([DB_USER, DB_PASSWORD]):
    logger.error("Database credentials (DB_USER, DB_PASSWORD) not found in environment variables or .env file.")

logger.info(f"Read-only mode: {MCP_READ_ONLY}")
logger.info(f"Logging to console and to file: {LOG_FILE_PATH} (Level: {LOG_LEVEL}, MaxSize: {LOG_MAX_BYTES}B, Backups: {LOG_BACKUP_COUNT})")