# MCP MariaDB Server

The MCP MariaDB Server provides a Model Context Protocol (MCP) interface for managing and querying MariaDB databases, supporting both standard SQL operations.

---

## Table of Contents

- [Overview](#overview)
- [Core Components](#core-components)
- [Available Tools](#available-tools)
- [Available Prompts](#available-prompts)
- [Configuration & Environment Variables](#configuration--environment-variables)
- [Setup](#setup)
- [Integration - Claude desktop/Cursor/Windsurf/VS Code](#integration---claude-desktopcursorwindsurfvs-code)
- [Logging](#logging)
- [Testing](#testing)
---

## Overview

The MCP MariaDB Server exposes a set of tools for interacting with MariaDB databases via a standardized protocol. It supports:
- Listing databases and tables
- Retrieving table schemas
- Executing safe, read-only SQL queries
- Query performance analysis with EXPLAIN
- Providing prompt templates for common database tasks

---

## Core Components

- **config.py**: Loads configuration from environment and `.env` files.
- **logger.py**: Configures logging for the MCP server.
- **main.py**: Entry point for running the MCP server.
- **server.py**: Main MCP server logic and tool definitions.
- **tests/**: Manual and automated test documentation and scripts.

---

## Available Tools

### Standard Database Tools

- **list_databases**
  - Lists all accessible databases.
  - Notice which database to use
  - Give some usage guide
  - Parameters: _None_

- **list_tables**
  - Lists all tables in a specified database.
  - Parameters: `database_name` (string, required)

- **get_table_schema**
  - Retrieves schema for a table (columns, types, keys, etc.).
  - Parameters: `database_name` (string, required), `table_name` (string, required)

- **execute_sql**
  - Executes a read-only SQL query (`SELECT`, `SHOW`, `DESCRIBE`).
  - Parameters: `sql_query` (string, required), `database_name` (string, optional), `parameters` (list, optional)
  - _Note: Enforces read-only mode if `MCP_READ_ONLY` is enabled._
  
- **create_database**
  - Creates a new database if it doesn't exist.
  - Parameters: `database_name` (string, required)

### Query Performance Analysis Tools

- **explain_query**
  - Executes EXPLAIN EXTENDED on a SQL query to show detailed execution plan with additional information.
  - Parameters: `sql_query` (string, required), `database_name` (string, required), `parameters` (list, optional)
  - _Note: Provides comprehensive analysis including filtered rows percentage and extra optimization details._

## Available Prompts

- **explain_table**
  - Provides a detailed explanation of a database table's structure, relationships, and usage.
  - Parameters: `table_name` (string, required)

- **query_tuning**
  - Analyzes a SQL query for performance optimization opportunities.
  - Parameters: `original_query` (string, required)

- **migration_code**
  - Generates SQL code for safely migrating a database table.
  - Parameters: `table_name` (string, required), `migration_description` (string, required)

---

## Configuration & Environment Variables

All configuration is via environment variables (typically set in a `.env` file):

| Variable               | Description                                            | Required | Default      |
|------------------------|--------------------------------------------------------|----------|--------------|
| `DB_HOST`              | MariaDB host address                                   | Yes      | `localhost`  |
| `DB_PORT`              | MariaDB port                                           | No       | `3306`       |
| `DB_USER`              | MariaDB username                                       | Yes      |              |
| `DB_PASSWORD`          | MariaDB password                                       | Yes      |              |
| `DB_NAME`              | Default database (optional; can be set per query)      | No       |              |
| `MCP_READ_ONLY`        | Enforce read-only SQL mode (`true`/`false`)            | No       | `true`       |
| `MCP_MAX_POOL_SIZE`    | Max DB connection pool size                            | No       | `10`         |
| `MCP_AUTH_ENABLED`      | Enable MCP authentication (`true`/`false`)            | No       | `false`      |
| `ENCRYPTION_KEY`       | Key for encrypting user IDs (32 bytes)                  | No       |              |
| `SIGNING_KEY`          | Key for signing tokens (required if `MCP_AUTH_ENABLED=true`) | No       |              |
| `API_KEYS`          | JSON array of API keys for authentication (required if `MCP_AUTH_ENABLED=true`) | No       | `[]`         |

#### Example `.env` file

```dotenv
DB_HOST=localhost
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_PORT=3306
DB_NAME=your_default_database

MCP_READ_ONLY=true
MCP_MAX_POOL_SIZE=10

MCP_AUTH_ENABLED=true
ENCRYPTION_KEY=EmL8QakI4j4W...
SIGNING_KEY=key...
API_KEYS=["WSgFMWo_0_ThMDQ....","JTFtQBTFE825iVbohnR...."]
```

---

# Setup

## If you are not using Docker for MariaDB.(Installed on your local machine or remote server)

### Build the MCP server
```bash
docker build -t mcp-server .
```

### Run the MCP server container
```bash
docker run -d \
  --name mcp-server \
  -e DB_HOST={mariadb-hostname-or-ip} \
  -e DB_USER={mariadb-username} \
  -e DB_PASSWORD={mariadb-password} \
  -e DB_PORT=3306 \
  -e DB_NAME={mariadb-database-name} \
  -e MCP_READ_ONLY=true \
  -e MCP_MAX_POOL_SIZE=10 \
  -e MCP_AUTH_ENABLED=true \
  -e ENCRYPTION_KEY={your-32-byte-encryption-key} \
  -e SIGNING_KEY={your-signing-key} \
  -e API_KEYS='["{your-api-key-1}","{your-api-key-2}"]' \
  -p 9001:9001 \
  mcp-server
```

## If you using MariaDB with Docker

### Create network for MariaDB and MCP server connection
```bash
docker network create mariadb-mcp-network
docker network connect mariadb-mcp-network {mariadb-container-name}
```

### Build the Docker image for the MCP server
```bash
docker build -t mcp-server .
```

### Run the MCP server container
```bash
docker run -d \
  --name mcp-server \
  --network mariadb-mcp-network \
  -e DB_HOST={mariadb-container-name} \
  -e DB_USER={mariadb-username} \
  -e DB_PASSWORD={mariadb-password} \
  -e DB_PORT=3306 \
  -e DB_NAME={mariadb-database-name} \
  -e MCP_READ_ONLY=true \
  -e MCP_MAX_POOL_SIZE=10 \
  -e MCP_AUTH_ENABLED=true \
  -e ENCRYPTION_KEY={your-32-byte-encryption-key} \
  -e SIGNING_KEY={your-signing-key} \
  -e API_KEYS='["{your-api-key-1}","{your-api-key-2}"]' \
  -p 9001:9001 \
  mcp-server
```
---

## Running MCP Server Without Docker
If you prefer to run the MCP server without Docker, you can do so by following these steps:

1. Setup`.env` (Refer to the example above):
   - Create a `.env` file in the `src/` directory with your MariaDB connection details.
   - Ensure you have the required environment variables set.
2. Install dependencies:
  ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install uv
    uv pip compile pyproject.toml -o uv.lock
    uv pip sync uv.lock
  ```
3. Run the MCP server:
   ```bash
   python src/main.py
   ```

---

## Integration - Claude desktop/Cursor/Windsurf/VS Code
### VS Code -> `.vscode/mcp.json`
```json
{
  "servers": {
    "mariadb-mcp-server": {
      "url": "http://localhost:9001/sse/",
      "type": "sse",
      "headers": {
        "Authorization": "Bearer {your-api-key}"
      }
    }
  }
}
```
### Cursor -> `~/.cursor/mcp.json`
```json
{
  "servers": {
    "mariadb-mcp-server": {
      "url": "http://localhost:9001/sse/",
      "type": "sse",
      "headers": {
        "Authorization": "Bearer {your-api-key}"
      }
    }
  }
}
```

### Claude Code
```
claude mcp add --transport sse mariadb-mcp-server  http://localhost:9001/sse/
```
---

## Logging

- Logs are written to `logs/mcp_server.log` by default.
- Log messages include tool calls, configuration issues, embedding errors, and client requests.
- Log level and output can be adjusted in the code (see `config.py` and logger setup).

---

## Testing

- Tests are located in the `src/tests/` directory.
- See `src/tests/README.md` for an overview.
- Tests cover both standard SQL and vector/embedding tool operations.