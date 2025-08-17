from logger.logger import Logger
Logger()
import argparse
import logging
import anyio
from functools import partial
from server import MariaDBServer

logger = Logger.getLogger()

parser = argparse.ArgumentParser(description="MariaDB MCP Server")
parser.add_argument('--transport', type=str, default='sse', choices=['stdio', 'sse'], help='MCP transport protocol (stdio or sse)')
parser.add_argument('--host', type=str, default='127.0.0.1', help='Host for SSE transport')
parser.add_argument('--port', type=int, default=9001, help='Port for SSE transport')
args = parser.parse_args()

# 1. Create the server instance
server = MariaDBServer()
exit_code = 0

try:
    # 2. Use anyio.run to manage the event loop and call the main async server logic
    anyio.run(
        partial(server.run_async_server, transport=args.transport, host=args.host, port=args.port)
    )
    logger.info("Server finished gracefully.")

except KeyboardInterrupt:
        logger.info("Server execution interrupted by user.")
except Exception as e:
        logger.critical(f"Server failed to start or crashed: {e}", exc_info=True)
        exit_code = 1
finally:
    logger.info(f"Server exiting with code {exit_code}.")