from typing import List, Dict, Any, Optional
import asyncmy
from fastmcp import FastMCP
import logging

# Import configuration settings
from config import (
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME,
    MCP_READ_ONLY, MCP_MAX_POOL_SIZE
)
logger = logging.getLogger(__name__)

from asyncmy.errors import Error as AsyncMyError

# --- MariaDB MCP Server Class ---
class MariaDBServer:
    """
    MCP Server exposing tools to interact with a MariaDB database.
    Manages the database connection pool.
    """
    def __init__(self, server_name="MariaDB_Server", autocommit=True):
        self.mcp = FastMCP(server_name)
        self.pool: Optional[asyncmy.Pool] = None
        self.autocommit=autocommit
        self.is_read_only = MCP_READ_ONLY
        logger.info(f"Initializing {server_name}...")
        if self.is_read_only:
            logger.warning("Server running in READ-ONLY mode. Write operations are disabled.")

    async def initialize_pool(self):
        """Initializes the asyncmy connection pool within the running event loop."""
        if not all([DB_USER, DB_PASSWORD]):
             logger.error("Cannot initialize pool due to missing database credentials.")
             raise ConnectionError("Missing database credentials for pool initialization.")

        if self.pool is not None:
            logger.info("Connection pool already initialized.")
            return

        try:
            logger.info(f"Creating connection pool for {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME} (max size: {MCP_MAX_POOL_SIZE})")
            self.pool = await asyncmy.create_pool(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                db=DB_NAME,
                minsize=1,
                maxsize=MCP_MAX_POOL_SIZE,
                autocommit=self.autocommit,
                pool_recycle=3600
            )
            logger.info("Connection pool initialized successfully.")
        except AsyncMyError as e:
            logger.error(f"Failed to initialize database connection pool: {e}", exc_info=True)
            self.pool = None
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during pool initialization: {e}", exc_info=True)
            self.pool = None
            raise

    async def close_pool(self):
        """Closes the connection pool gracefully."""
        if self.pool:
            logger.info("Closing database connection pool...")
            try:
                self.pool.close()
                await self.pool.wait_closed()
                logger.info("Database connection pool closed.")
            except Exception as e:
                logger.error(f"Error closing connection pool: {e}", exc_info=True)
            finally:
                self.pool = None

    async def _execute_query(self, sql: str, params: Optional[tuple] = None, database: Optional[str] = None) -> List[Dict[str, Any]]:
        """Helper function to execute SELECT queries using the pool."""
        if self.pool is None:
            logger.error("Connection pool is not initialized.")
            raise RuntimeError("Database connection pool not available.")

        allowed_prefixes = ('SELECT', 'SHOW', 'DESC', 'DESCRIBE', 'USE', 'EXPLAIN')
        query_upper = sql.strip().upper()
        is_allowed_read_query = any(query_upper.startswith(prefix) for prefix in allowed_prefixes)

        if self.is_read_only and not is_allowed_read_query:
             logger.warning(f"Blocked potentially non-read-only query in read-only mode: {sql[:100]}...")
             raise PermissionError("Operation forbidden: Server is in read-only mode.")

        logger.info(f"Executing query (DB: {database or DB_NAME}): {sql[:100]}...")
        if params:
            logger.debug(f"Parameters: {params}")

        conn = None
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(cursor=asyncmy.cursors.DictCursor) as cursor:
                    current_db_query = "SELECT DATABASE()"
                    await cursor.execute(current_db_query)
                    current_db_result = await cursor.fetchone()
                    current_db_name = current_db_result.get('DATABASE()') if current_db_result else None
                    pool_db_name = DB_NAME
                    actual_current_db = current_db_name or pool_db_name

                    if database and database != actual_current_db:
                        logger.info(f"Switching database context from '{actual_current_db}' to '{database}'")
                        await cursor.execute(f"USE `{database}`")

                    await cursor.execute(sql, params or ())
                    results = await cursor.fetchall()
                    logger.info(f"Query executed successfully, {len(results)} rows returned.")
                    return results if results else []
        except AsyncMyError as e:
            conn_state = f"Connection: {'acquired' if conn else 'not acquired'}"
            logger.error(f"Database error executing query ({conn_state}): {e}", exc_info=True)
            # Check for specific connection-related errors if possible
            raise RuntimeError(f"Database error: {e}") from e
        except PermissionError as e:
             logger.warning(f"Permission denied: {e}")
             raise e
        except Exception as e:
            # Catch potential loop closed errors here too, although ideally fixed by structure change
            if isinstance(e, RuntimeError) and 'Event loop is closed' in str(e):
                 logger.critical("Detected closed event loop during query execution!", exc_info=True)
                 # This indicates a fundamental problem with loop management still exists
                 raise RuntimeError("Event loop closed unexpectedly during query.") from e
            conn_state = f"Connection: {'acquired' if conn else 'not acquired'}"
            logger.error(f"Unexpected error during query execution ({conn_state}): {e}", exc_info=True)
            raise RuntimeError(f"An unexpected error occurred: {e}") from e
            
    async def _database_exists(self, database_name: str) -> bool:
        """Checks if a database exists."""
        if not database_name or not database_name.isidentifier():
            logger.warning(f"_database_exists called with invalid database_name: {database_name}")
            return False 

        sql = "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = %s"
        try:
            results = await self._execute_query(sql, params=(database_name,), database='information_schema')
            return len(results) > 0
        except Exception as e:
            logger.error(f"Error checking if database '{database_name}' exists: {e}", exc_info=True)
            return False
        
    async def _table_exists(self, database_name: str, table_name: str) -> bool:
        """Checks if a table exists in the given database."""
        if not database_name or not database_name.isidentifier() or \
           not table_name or not table_name.isidentifier():
            logger.warning(f"_table_exists called with invalid names: db='{database_name}', table='{table_name}'")
            return False

        sql = "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s"
        try:
            results = await self._execute_query(sql, params=(database_name, table_name), database='information_schema')
            return len(results) > 0
        except Exception as e:
            logger.error(f"Error checking if table '{database_name}.{table_name}' exists: {e}", exc_info=True)
            return False

    
    # --- MCP Tool Definitions ---

    async def list_databases(self) -> List[str]:
        """Lists all accessible databases on the connected MariaDB server."""
        logger.info("TOOL START: list_databases called.")
        sql = "SHOW DATABASES"
        try:
            results = await self._execute_query(sql)
            db_list = [row['Database'] for row in results if 'Database' in row]
            logger.info(f"TOOL END: list_databases completed. Databases found: {len(db_list)}.")
            return db_list
        except Exception as e:
            logger.error(f"TOOL ERROR: list_databases failed: {e}", exc_info=True)
            raise

    async def list_tables(self, database_name: str) -> List[str]:
        """Lists all tables within the specified database."""
        logger.info(f"TOOL START: list_tables called. database_name={database_name}")
        if not database_name or not database_name.isidentifier():
            logger.warning(f"TOOL WARNING: list_tables called with invalid database_name: {database_name}")
            raise ValueError(f"Invalid database name provided: {database_name}")
        sql = "SHOW TABLES"
        try:
            results = await self._execute_query(sql, database=database_name)
            table_list = [list(row.values())[0] for row in results if row]
            logger.info(f"TOOL END: list_tables completed. Tables found: {len(table_list)}.")
            return table_list
        except Exception as e:
            logger.error(f"TOOL ERROR: list_tables failed for database_name={database_name}: {e}", exc_info=True)
            raise

    async def get_table_schema(self, database_name: str, table_name: str) -> Dict[str, Any]:
        """
        Retrieves the schema (column names, types, nullability, keys, default values)
        for a specific table in a database.
        """
        logger.info(f"TOOL START: get_table_schema called. database_name={database_name}, table_name={table_name}")
        if not database_name or not database_name.isidentifier():
            logger.warning(f"TOOL WARNING: get_table_schema called with invalid database_name: {database_name}")
            raise ValueError(f"Invalid database name provided: {database_name}")
        if not table_name or not table_name.isidentifier():
            logger.warning(f"TOOL WARNING: get_table_schema called with invalid table_name: {table_name}")
            raise ValueError(f"Invalid table name provided: {table_name}")

        sql = f"DESCRIBE `{database_name}`.`{table_name}`"
        try:
            schema_results = await self._execute_query(sql)
            schema_info = {}
            if not schema_results:
                exists_sql = "SELECT COUNT(*) as count FROM information_schema.tables WHERE table_schema = %s AND table_name = %s"
                exists_result = await self._execute_query(exists_sql, params=(database_name, table_name))
                if not exists_result or exists_result[0]['count'] == 0:
                    logger.warning(f"TOOL WARNING: Table '{database_name}'.'{table_name}' not found or inaccessible.")
                    raise FileNotFoundError(f"Table '{database_name}'.'{table_name}' not found or inaccessible.")
                else:
                    logger.warning(f"Could not describe table '{database_name}'.'{table_name}'. It might be a view or lack permissions.")

            for row in schema_results:
                col_name = row.get('Field')
                if col_name:
                    schema_info[col_name] = {
                        'type': row.get('Type'),
                        'nullable': row.get('Null', '').upper() == 'YES',
                        'key': row.get('Key'),
                        'default': row.get('Default'),
                        'extra': row.get('Extra')
                    }
            logger.info(f"TOOL END: get_table_schema completed. Columns found: {len(schema_info)}. Keys: {list(schema_info.keys())}")
            return schema_info
        except FileNotFoundError as e:
            logger.warning(f"TOOL WARNING: get_table_schema table not found: {e}")
            raise e
        except Exception as e:
            logger.error(f"TOOL ERROR: get_table_schema failed for database_name={database_name}, table_name={table_name}: {e}", exc_info=True)
            raise RuntimeError(f"Could not retrieve schema for table '{database_name}.{table_name}'.")

    async def execute_sql(self, sql_query: str, database_name: str, parameters: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """
        Executes a read-only SQL query (primarily SELECT, SHOW, DESCRIBE) against a specified database
        and returns the results. Uses parameterized queries for safety.
        Example `parameters`: ["value1", 123] corresponding to %s placeholders in `sql_query`.
        """
        logger.info(f"TOOL START: execute_sql called. database_name={database_name}, sql_query={sql_query[:100]}, parameters={parameters}")
        if database_name and not database_name.isidentifier():
            logger.warning(f"TOOL WARNING: execute_sql called with invalid database_name: {database_name}")
            raise ValueError(f"Invalid database name provided: {database_name}")
        param_tuple = tuple(parameters) if parameters is not None else None
        try:
            results = await self._execute_query(sql_query, params=param_tuple, database=database_name)
            logger.info(f"TOOL END: execute_sql completed. Rows returned: {len(results)}.")
            return results
        except Exception as e:
            logger.error(f"TOOL ERROR: execute_sql failed for database_name={database_name}, sql_query={sql_query[:100]}, parameters={parameters}: {e}", exc_info=True)
            raise
            
    async def explain_query(self, sql_query: str, database_name: str, parameters: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """
        Executes EXPLAIN on a SQL query to show the execution plan.
        This helps analyze query performance and optimization opportunities.
        Example `parameters`: ["value1", 123] corresponding to %s placeholders in `sql_query`.
        """
        logger.info(f"TOOL START: explain_query called. database_name={database_name}, sql_query={sql_query[:100]}, parameters={parameters}")
        if database_name and not database_name.isidentifier():
            logger.warning(f"TOOL WARNING: explain_query called with invalid database_name: {database_name}")
            raise ValueError(f"Invalid database name provided: {database_name}")
        
        # EXPLAIN 키워드를 쿼리 앞에 추가
        explain_sql = f"EXPLAIN {sql_query.strip()}"
        param_tuple = tuple(parameters) if parameters is not None else None
        
        try:
            results = await self._execute_query(explain_sql, params=param_tuple, database=database_name)
            logger.info(f"TOOL END: explain_query completed. Execution plan rows returned: {len(results)}.")
            return results
        except Exception as e:
            logger.error(f"TOOL ERROR: explain_query failed for database_name={database_name}, sql_query={sql_query[:100]}, parameters={parameters}: {e}", exc_info=True)
            raise

    async def explain_query_extended(self, sql_query: str, database_name: str, parameters: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """
        Executes EXPLAIN EXTENDED on a SQL query to show detailed execution plan with additional information.
        This provides more comprehensive analysis including filtered rows percentage and extra information.
        Example `parameters`: ["value1", 123] corresponding to %s placeholders in `sql_query`.
        """
        logger.info(f"TOOL START: explain_query_extended called. database_name={database_name}, sql_query={sql_query[:100]}, parameters={parameters}")
        if database_name and not database_name.isidentifier():
            logger.warning(f"TOOL WARNING: explain_query_extended called with invalid database_name: {database_name}")
            raise ValueError(f"Invalid database name provided: {database_name}")
        
        # EXPLAIN EXTENDED 키워드를 쿼리 앞에 추가
        explain_sql = f"EXPLAIN EXTENDED {sql_query.strip()}"
        param_tuple = tuple(parameters) if parameters is not None else None
        
        try:
            results = await self._execute_query(explain_sql, params=param_tuple, database=database_name)
            logger.info(f"TOOL END: explain_query_extended completed. Extended execution plan rows returned: {len(results)}.")
            return results
        except Exception as e:
            logger.error(f"TOOL ERROR: explain_query_extended failed for database_name={database_name}, sql_query={sql_query[:100]}, parameters={parameters}: {e}", exc_info=True)
            raise

    async def create_database(self, database_name: str) -> Dict[str, Any]:
        """
        Creates a new database if it doesn't exist.
        """
        logger.info(f"TOOL START: create_database called for database: '{database_name}'")
        if not database_name or not database_name.isidentifier():
            logger.error(f"Invalid database_name for creation: '{database_name}'. Must be a valid identifier.")
            raise ValueError(f"Invalid database_name for creation: '{database_name}'. Must be a valid identifier.")

        # Check existence first to provide a clear message, though CREATE DATABASE IF NOT EXISTS is idempotent
        if await self._database_exists(database_name):
            message = f"Database '{database_name}' already exists."
            logger.info(f"TOOL END: create_database. {message}")
            return {"status": "exists", "message": message, "database_name": database_name}

        sql = f"CREATE DATABASE IF NOT EXISTS `{database_name}`;"

        try:
            await self._execute_query(sql, database=None)

            message = f"Database '{database_name}' created successfully."
            logger.info(f"TOOL END: create_database. {message}")
            return {"status": "success", "message": message, "database_name": database_name}
        except Exception as e:
            error_message = f"Failed to create database '{database_name}'."
            logger.error(f"TOOL ERROR: create_database. {error_message} Error: {e}", exc_info=True)
            raise RuntimeError(f"{error_message} Reason: {str(e)}")

    async def get_usage_guide(self) -> Dict[str, Any]:
        """
        Provides comprehensive usage guide for all available MCP tools.
        This helps LLMs understand how to properly use each tool with examples and best practices.
        """
        logger.info("TOOL START: get_usage_guide called.")
        
        usage_guide = {
            "server_info": {
                "name": "MariaDB MCP Server",
                "description": "MCP Server exposing tools to interact with a MariaDB database. Manages the database connection pool.",
                "read_only_mode": self.is_read_only,
                "pool_max_size": MCP_MAX_POOL_SIZE,
                "database_info": {
                    "host": DB_HOST,
                    "port": DB_PORT,
                    "user": DB_USER,
                    "default_database": DB_NAME
                }
            },
            "available_tools": {
                "list_databases": {
                    "description": "Lists all accessible databases on the connected MariaDB server.",
                    "parameters": "None required",
                    "returns": "List[str] - Array of database names",
                    "example_usage": "Use this first to see what databases are available",
                    "best_practices": [
                        "Call this before working with specific databases",
                        "No parameters needed - just call the function"
                    ]
                },
                "list_tables": {
                    "description": "Lists all tables within the specified database.",
                    "parameters": {
                        "database_name": "str - Name of the database (must be valid identifier)"
                    },
                    "returns": "List[str] - Array of table names in the database",
                    "example_usage": "list_tables('database_name') to see all tables in database_name database",
                    "validation": "Database name must be a valid SQL identifier",
                    "best_practices": [
                        "Always validate database exists first using list_databases",
                        "Use exact database name from list_databases result"
                    ]
                },
                "get_table_schema": {
                    "description": "Retrieves the schema (column names, types, nullability, keys, default values) for a specific table in a database.",
                    "parameters": {
                        "database_name": "str - Name of the database (must be valid identifier)",
                        "table_name": "str - Name of the table (must be valid identifier)"
                    },
                    "returns": "Dict[str, Any] - Schema information with column details",
                    "schema_structure": {
                        "column_name": {
                            "type": "SQL data type (e.g., 'varchar(255)', 'bigint(20)')",
                            "nullable": "boolean - True if column accepts NULL",
                            "key": "Key type ('PRI', 'UNI', 'MUL', '')",
                            "default": "Default value or null",
                            "extra": "Extra information (e.g., 'auto_increment')"
                        }
                    },
                    "example_usage": "get_table_schema('database_name', 'table_name') to understand table_name table structure",
                    "best_practices": [
                        "Use this before writing complex queries to understand table structure",
                        "Check nullable and key information for JOIN conditions",
                        "Validate both database and table names are valid identifiers"
                    ]
                },
                "get_table_schema_enhanced": {
                    "description": "Retrieves enhanced table schema with foreign key information including referenced tables and relationships.",
                    "parameters": {
                        "database_name": "str - Name of the database (must be valid identifier)",
                        "table_name": "str - Name of the table (must be valid identifier)"
                    },
                    "returns": "Dict[str, Any] - Enhanced schema with foreign key details",
                    "enhanced_structure": {
                        "table_info": "Metadata about the table (name, column count, FK count)",
                        "columns": {
                            "column_name": {
                                "type": "SQL data type",
                                "nullable": "boolean",
                                "key": "Key type",
                                "default": "Default value",
                                "extra": "Extra info",
                                "foreign_key": {
                                    "constraint_name": "FK constraint name",
                                    "referenced_database": "Target database",
                                    "referenced_table": "Target table",
                                    "referenced_column": "Target column",
                                    "on_update": "Update rule (CASCADE, RESTRICT, etc.)",
                                    "on_delete": "Delete rule (CASCADE, RESTRICT, etc.)",
                                    "full_reference": "Complete reference path"
                                }
                            }
                        },
                        "foreign_keys_summary": "List of all foreign key relationships"
                    },
                    "example_usage": "get_table_schema_enhanced('database_name', 'table_name') to see foreign key relationships",
                    "best_practices": [
                        "Use when you need to understand table relationships for complex JOINs",
                        "Helpful for database schema documentation and analysis",
                        "Use basic get_table_schema for simple column information to avoid overhead"
                    ]
                },
                "execute_sql": {
                    "description": "Executes a read-only SQL query (primarily SELECT, SHOW, DESCRIBE) against a specified database and returns the results. Uses parameterized queries for safety.",
                    "parameters": {
                        "sql_query": "str - The SQL query to execute",
                        "database_name": "str - Target database name",
                        "parameters": "Optional[List[Any]] - Parameters for prepared statements (corresponding to %s placeholders in `sql_query`)"
                    },
                    "returns": "List[Dict[str, Any]] - Query results as list of dictionaries",
                    "allowed_operations": [
                        "SELECT - Data retrieval queries",
                        "SHOW - Database/table information",
                        "DESCRIBE/DESC - Table structure",
                        "USE - Database context switching"
                    ],
                    "read_only_restrictions": "Server blocks non-read operations when MCP_READ_ONLY=true",
                    "parameterized_queries": {
                        "description": "Use %s placeholders for safe parameter binding",
                        "example": "SELECT * FROM users WHERE id = %s AND status = %s",
                        "parameters_example": "[123, 'active']"
                    },
                    "example_usage": "execute_sql('SELECT COUNT(*) FROM table_name', 'database_name')",
                    "best_practices": [
                        "Always use parameterized queries for user input to prevent SQL injection",
                        "Use LIMIT clauses for large datasets to avoid memory issues",
                        "Switch database context appropriately using database_name parameter"
                    ]
                },
                "explain_query": {
                    "description": "Executes EXPLAIN on a SQL query to show the execution plan. This helps analyze query performance and optimization opportunities.",
                    "parameters": {
                        "sql_query": "str - The SQL query to analyze (without EXPLAIN prefix)",
                        "database_name": "str - Target database name",
                        "parameters": "Optional[List[Any]] - Parameters for prepared statements"
                    },
                    "returns": "List[Dict[str, Any]] - Execution plan details",
                    "execution_plan_fields": [
                        "id - Select identifier",
                        "select_type - Type of SELECT",
                        "table - Table being accessed",
                        "type - Join type",
                        "possible_keys - Possible indexes to use",
                        "key - Actual index used",
                        "key_len - Length of key used",
                        "ref - Columns compared to index",
                        "rows - Estimated rows examined",
                        "Extra - Additional information"
                    ],
                    "example_usage": "explain_query('SELECT * FROM table_name WHERE id = %s', 'database_name', [123])",
                    "best_practices": [
                        "Use for performance analysis of complex queries",
                        "Look for table scans (type='ALL') that might need optimization",
                        "Check if proper indexes are being used"
                    ]
                },
                "explain_query_extended": {
                    "description": "Executes EXPLAIN EXTENDED on a SQL query to show detailed execution plan with additional information. This provides more comprehensive analysis including filtered rows percentage and extra information.",
                    "parameters": {
                        "sql_query": "str - The SQL query to analyze (without EXPLAIN EXTENDED prefix)",
                        "database_name": "str - Target database name", 
                        "parameters": "Optional[List[Any]] - Parameters for prepared statements"
                    },
                    "returns": "List[Dict[str, Any]] - Extended execution plan with additional details",
                    "additional_fields": [
                        "filtered - Percentage of rows filtered by condition",
                        "More detailed Extra information"
                    ],
                    "example_usage": "explain_query_extended('SELECT * FROM table1 t JOIN table2 tt ON t.id = tt.company_id', 'database_name')",
                    "best_practices": [
                        "Use for deep performance analysis",
                        "Compare with regular EXPLAIN to see additional insights",
                        "Focus on filtered percentage for WHERE clause optimization"
                    ]
                },
                "create_database": {
                    "description": "Creates a new database if it doesn't exist.",
                    "parameters": {
                        "database_name": "str - Name of database to create (must be valid identifier)"
                    },
                    "returns": "Dict[str, Any] - Operation result with status and message",
                    "return_structure": {
                        "status": "'success' or 'exists'",
                        "message": "Human readable result message",
                        "database_name": "The database name that was processed"
                    },
                    "validation": "Database name must be a valid SQL identifier",
                    "read_only_restriction": "This operation is blocked when MCP_READ_ONLY=true",
                    "example_usage": "create_database('test_db')",
                    "best_practices": [
                        "Check if database exists first using list_databases",
                        "Use valid SQL identifier names only",
                        "Consider read-only mode restrictions"
                    ]
                }
            },
            "general_best_practices": [
                "Always check database connection status before executing queries",
                "Use parameterized queries to prevent SQL injection",
                "Consider using LIMIT clauses for large result sets",
                "Check table schemas before writing complex JOINs",
                "Use EXPLAIN tools for query performance optimization",
                "Respect read-only mode restrictions when enabled",
                "Handle exceptions gracefully in your code"
            ],
            "common_workflows": {
                "database_exploration": [
                    "1. Call list_databases() to see available databases",
                    "2. Call list_tables(database_name) for target database", 
                    "3. Call get_table_schema(database_name, table_name) for tables of interest",
                    "4. Execute queries based on discovered schema"
                ],
                "query_optimization": [
                    "1. Write initial query using execute_sql()",
                    "2. Analyze performance with explain_query()",
                    "3. For deeper analysis, use explain_query_extended()",
                    "4. Optimize based on execution plan findings",
                    "5. Re-test with explain tools to verify improvements"
                ],
                "data_analysis": [
                    "1. Explore schema with get_table_schema()",
                    "2. Start with simple COUNT queries to understand data volume",
                    "3. Build complex analytical queries step by step",
                    "4. Use parameterized queries for filtering",
                    "5. Apply LIMIT for large datasets"
                ]
            },
            "error_handling": {
                "common_errors": {
                    "permission_error": "Server is in read-only mode - only SELECT/SHOW/DESCRIBE allowed",
                    "value_error": "Invalid database or table name provided",
                    "runtime_error": "Database connection or query execution failed",
                    "file_not_found_error": "Specified table does not exist"
                },
                "troubleshooting": [
                    "Check connection pool status",
                    "Verify database and table names are valid identifiers",
                    "Ensure queries are read-only when MCP_READ_ONLY=true",
                    "Use proper parameter binding for complex queries"
                ]
            }
        }
        
        logger.info("TOOL END: get_usage_guide completed.")
        return usage_guide

    async def get_table_schema_enhanced(self, database_name: str, table_name: str) -> Dict[str, Any]:
        """
        Retrieves enhanced table schema with foreign key information.
        Includes all basic schema info plus foreign key relationships and referenced tables.
        """
        logger.info(f"TOOL START: get_table_schema_enhanced called. database_name={database_name}, table_name={table_name}")
        if not database_name or not database_name.isidentifier():
            logger.warning(f"TOOL WARNING: get_table_schema_enhanced called with invalid database_name: {database_name}")
            raise ValueError(f"Invalid database name provided: {database_name}")
        if not table_name or not table_name.isidentifier():
            logger.warning(f"TOOL WARNING: get_table_schema_enhanced called with invalid table_name: {table_name}")
            raise ValueError(f"Invalid table name provided: {table_name}")

        try:
            # 1. 기본 스키마 정보 가져오기
            basic_schema = await self.get_table_schema(database_name, table_name)
            
            # 2. 외래키 정보 조회
            fk_sql = """
            SELECT 
                kcu.COLUMN_NAME as column_name,
                kcu.CONSTRAINT_NAME as constraint_name,
                kcu.REFERENCED_TABLE_SCHEMA as referenced_database,
                kcu.REFERENCED_TABLE_NAME as referenced_table,
                kcu.REFERENCED_COLUMN_NAME as referenced_column,
                rc.UPDATE_RULE as on_update,
                rc.DELETE_RULE as on_delete
            FROM information_schema.KEY_COLUMN_USAGE kcu
            LEFT JOIN information_schema.REFERENTIAL_CONSTRAINTS rc
                ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
                AND kcu.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA
            WHERE kcu.TABLE_SCHEMA = %s 
              AND kcu.TABLE_NAME = %s 
              AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
            ORDER BY kcu.ORDINAL_POSITION
            """
            
            fk_results = await self._execute_query(fk_sql, params=(database_name, table_name))
            
            # 3. 기본 스키마에 외래키 정보 추가
            enhanced_schema = {}
            for col_name, col_info in basic_schema.items():
                enhanced_schema[col_name] = col_info.copy()
                enhanced_schema[col_name]['foreign_key'] = None
            
            # 4. 외래키 정보를 해당 컬럼에 추가
            for fk_row in fk_results:
                column_name = fk_row['column_name']
                if column_name in enhanced_schema:
                    enhanced_schema[column_name]['foreign_key'] = {
                        'constraint_name': fk_row['constraint_name'],
                        'referenced_database': fk_row['referenced_database'],
                        'referenced_table': fk_row['referenced_table'],
                        'referenced_column': fk_row['referenced_column'],
                        'on_update': fk_row['on_update'],
                        'on_delete': fk_row['on_delete'],
                        'full_reference': f"{fk_row['referenced_database']}.{fk_row['referenced_table']}.{fk_row['referenced_column']}"
                    }
            
            # 5. 메타데이터 추가
            result = {
                'table_info': {
                    'database_name': database_name,
                    'table_name': table_name,
                    'total_columns': len(enhanced_schema),
                    'foreign_key_count': len(fk_results)
                },
                'columns': enhanced_schema,
                'foreign_keys_summary': [
                    {
                        'column': fk['column_name'],
                        'references': f"{fk['referenced_database']}.{fk['referenced_table']}.{fk['referenced_column']}",
                        'constraint': fk['constraint_name']
                    }
                    for fk in fk_results
                ]
            }
            
            logger.info(f"TOOL END: get_table_schema_enhanced completed. Columns: {len(enhanced_schema)}, Foreign keys: {len(fk_results)}")
            return result
            
        except Exception as e:
            logger.error(f"TOOL ERROR: get_table_schema_enhanced failed for database_name={database_name}, table_name={table_name}: {e}", exc_info=True)
            raise RuntimeError(f"Could not retrieve enhanced schema for table '{database_name}.{table_name}': {str(e)}")

    # --- Tool Registration (Synchronous) ---
    def register_tools(self):
        logger.debug("register_tools: called")
        """Registers the class methods as MCP tools using the instance. This is synchronous."""
        if self.pool is None:
             logger.error("Cannot register tools: Database pool is not initialized.")
             raise RuntimeError("Database pool must be initialized before registering tools.")

        # 기존 함수 등록 → Tool 객체로 래핑해서 등록
        from fastmcp.tools.tool import Tool

        self.mcp.add_tool(self.list_databases)
        self.mcp.add_tool(self.list_tables)
        self.mcp.add_tool(self.get_table_schema)
        self.mcp.add_tool(self.get_table_schema_enhanced)
        self.mcp.add_tool(self.execute_sql)
        self.mcp.add_tool(self.explain_query)
        self.mcp.add_tool(self.explain_query_extended)
        self.mcp.add_tool(self.get_usage_guide)
        self.mcp.add_tool(self.create_database)
        logger.info("Registered MCP tools explicitly.")
        logger.debug("register_tools: completed")

    # --- Async Main Server Logic ---
    async def run_async_server(self, transport="stdio", host="127.0.0.1", port=9001):
        logger.debug("run_async_server: start")
        """
        Initializes pool, registers tools, and runs the appropriate async MCP listener.
        This method should be the target for anyio.run().
        """
        try:
            # 1. Initialize pool within the anyio-managed loop
            await self.initialize_pool()

            # 2. Register tools (synchronous part, but called from async context)
            self.register_tools()

            # 3. Prepare transport arguments
            transport_kwargs = {}
            if transport == "sse":
                transport_kwargs = {"host": host, "port": port}
                logger.info(f"Starting MCP server via {transport} on {host}:{port}...")
            elif transport == "stdio":
                 logger.info(f"Starting MCP server via {transport}...")
            else:
                 logger.error(f"Unsupported transport type: {transport}")
                 return 

            logger.debug("run_async_server: before MCP run_async")
            # 4. Run the appropriate async listener from FastMCP
            await self.mcp.run_async(transport=transport, **transport_kwargs)
            logger.debug("run_async_server: after MCP run_async")

        except (ConnectionError, AsyncMyError, RuntimeError) as e:
            logger.critical(f"Server setup failed: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.critical(f"Server execution failed with an unexpected error: {e}", exc_info=True)
            raise
        finally:
            await self.close_pool()