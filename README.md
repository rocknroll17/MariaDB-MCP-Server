# MCP MariaDB Server

The MCP MariaDB Server provides a Model Context Protocol (MCP) interface for managing and querying MariaDB databases, supporting both standard SQL operations.

---

## Table of Contents

- [Overview](#overview)
- [Core Components](#core-components)
- [Available Tools](#available-tools)
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
- Query performance analysis with EXPLAIN and EXPLAIN EXTENDED
- Comprehensive tool usage guide for LLM self-discovery

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
  - Executes EXPLAIN on a SQL query to show the execution plan for performance analysis.
  - Parameters: `sql_query` (string, required), `database_name` (string, required), `parameters` (list, optional)
  - _Note: Helps analyze query performance and optimization opportunities. Does not execute the actual query._

- **explain_query_extended**
  - Executes EXPLAIN EXTENDED on a SQL query to show detailed execution plan with additional information.
  - Parameters: `sql_query` (string, required), `database_name` (string, required), `parameters` (list, optional)
  - _Note: Provides comprehensive analysis including filtered rows percentage and extra optimization details._

### Tool Discovery & Usage Guide
**! Note: You have to give prompt to your LLM understand this tool**  
`EXAMPLE: "First of all. There is a get_usage_guide tool that helps you understand how to use MCP tools."`
- **get_usage_guide**
  - Provides comprehensive usage guide for all available MCP tools with examples and best practices.
  - Parameters: _None_

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

#### Example `.env` file

```dotenv
DB_HOST=localhost
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_PORT=3306
DB_NAME=your_default_database

MCP_READ_ONLY=true
MCP_MAX_POOL_SIZE=10
```

---

# Setup

## If you are not using Docker for MariaDB.(Installed on your local machine or remote server)

1. **Build the MCP server**
```bash
docker build -t mcp-server .
```

2. **Run the MCP server container**
```bash
docker run -d \
  --name mcp-server \
  -e DB_HOST= {host.docker.internal or your-mariadb-host-ip} \
  -e DB_USER={mariadb-username} \
  -e DB_PASSWORD={mariadb-password} \
  -e DB_PORT=3306 \
  -e DB_NAME={mariadb-database-name} \
  -e MCP_READ_ONLY=true \
  -e MCP_MAX_POOL_SIZE=10 \
  -p 9001:9001 \
  mcp-server
```

## If you using MariaDB with Docker

1. **Create network for MariaDB and MCP server connection**
```bash
docker network create mariadb-mcp-network
docker network connect mariadb-mcp-network {mariadb-container-name}
```

2. **Build the Docker image for the MCP server**
```bash
docker build -t mcp-server .
```

3. **Run the MCP server container**
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

## Integration - Cursor/VS Code/Claude Code
### VS Code -> `.vscode/settings.json`
### Cursor -> `~/.cursor/settings.json`
```json
{
  "mcp": {
    "server": {
      "url": "http://localhost:9001/sse",
      "type": "sse"
    }
  }
}
```
### Claude Code
```sh
claude mcp add --transport sse mcp-server http://localhost:9001/sse
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