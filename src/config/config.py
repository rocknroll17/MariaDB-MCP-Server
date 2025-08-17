import os
from dotenv import load_dotenv
import json
from typing import List
from logger.logger import Logger

logger = Logger.getLogger()
# Load environment variables from .env file
load_dotenv()

# --- Database Configuration ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# --- Authentication Configuration ---
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")  # 32 bytes key for AES-256
SIGNING_KEY = os.getenv("SIGNING_KEY")        # HMAC signing key
MCP_AUTH_ENABLED = os.getenv("MCP_AUTH_ENABLED", "false").lower() == "true"

# --- API 키 관리 (간단하게!) ---
def load_api_keys() -> List[str]:
    """API 키들을 JSON에서 읽어서 리스트로 반환"""
    try:
        keys_json = os.getenv("API_KEYS", "[]")
        keys_json = keys_json.replace('\n', '').replace('\r', '')  # 줄바꿈 제거
        return json.loads(keys_json)
    except:
        return []

# API 키 리스트
API_KEYS = load_api_keys()

# --- MCP Server Configuration ---
# Read-only mode
MCP_READ_ONLY = os.getenv("MCP_READ_ONLY", "true").lower() == "true"
MCP_MAX_POOL_SIZE = int(os.getenv("MCP_MAX_POOL_SIZE", 10))

# --- Validation ---
if not all([DB_USER, DB_PASSWORD]):
    logger.error("Database credentials (DB_USER, DB_PASSWORD) not found in environment variables or .env file.")

# Validate authentication keys if auth is enabled
if MCP_AUTH_ENABLED:
    if not ENCRYPTION_KEY or len(ENCRYPTION_KEY.encode()) != 32:
        logger.error("ENCRYPTION_KEY must be exactly 32 bytes when MCP_AUTH_ENABLED=true")
    if not SIGNING_KEY:
        logger.error("SIGNING_KEY is required when MCP_AUTH_ENABLED=true")
    if len(API_KEYS) == 0:
        logger.error("API_KEYS is required when MCP_AUTH_ENABLED=true")

logger.info(f"Read-only mode: {MCP_READ_ONLY}")
logger.info(f"Authentication enabled: {MCP_AUTH_ENABLED}")