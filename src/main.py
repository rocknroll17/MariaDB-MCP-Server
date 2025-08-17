import logging
import argparse
import logging
import anyio
from functools import partial
from server import MariaDBServer
from service.key import *

logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description="MariaDB MCP Server")
subparsers = parser.add_subparsers(dest='mode', help='Available modes')

# Server mode subparser
server_parser = subparsers.add_parser('server', help='Run MCP server')
server_parser.add_argument('--transport', type=str, default='sse', choices=['stdio', 'sse'], help='MCP transport protocol (stdio or sse)')
server_parser.add_argument('--host', type=str, default='127.0.0.1', help='Host for SSE transport')
server_parser.add_argument('--port', type=int, default=9001, help='Port for SSE transport')

# API key generation mode subparser
api_key_parser = subparsers.add_parser('api_key', help='Generate API keys for users')
api_key_parser.add_argument('users', nargs='+', help='User names for API key generation')
api_key_parser.add_argument('--encrypt-key', type=str, required=True, help='Encryption key for API key generation')
api_key_parser.add_argument('--signing-key', type=str, required=True, help='Signing key for API key generation')

# Auth key generation mode subparser
auth_key_parser = subparsers.add_parser('auth_key', help='Generate authentication keys')

# Set default mode if no subcommand provided
parser.set_defaults(mode='server', transport='sse', host='127.0.0.1', port=9001)

args = parser.parse_args()

exit_code = 0

try:
    if args.mode == 'server':
        # 서버 모드에서만 MariaDBServer 인스턴스 생성
        server = MariaDBServer()
        # 2. Use anyio.run to manage the event loop and call the main async server logic
        anyio.run(
            partial(server.run_async_server, transport=args.transport, host=args.host, port=args.port)
        )
        logger.info("Server finished gracefully.")
    elif args.mode == 'api_key':
        # API 키 생성 모드
        # AuthService 인스턴스 생성
        ENCRYPTION_KEY = args.encrypt_key
        SIGNING_KEY = args.signing_key
        # auth = AuthService(encryption_key=ENCRYPTION_KEY, signing_key=SIGNING_KEY)
        
        for user in args.users:
            try:
                create_user_key(user, ENCRYPTION_KEY, SIGNING_KEY)
            except Exception as e:
                print(f"❌ {user}의 API 키 생성 실패: {e}")
    elif args.mode == 'auth_key':
        print(f"ENCRYPTION_KEY={generate_32_byte_string_key()}")
        print(f"SIGNING_KEY={generate_signing_key(64)}")

except KeyboardInterrupt:
        logger.info("Server execution interrupted by user.")
except Exception as e:
        logger.critical(f"Server failed to start or crashed: {e}", exc_info=True)
        exit_code = 1
finally:
    logger.info(f"Server exiting with code {exit_code}.")