from typing import List, Dict, Any, Optional
import asyncmy
import asyncio
from fastmcp import FastMCP
from fastmcp.tools import FunctionTool
from service import AuthService, get_current_user_id, get_current_client_ip, get_current_api_key
import logging
from asyncmy.errors import Error as AsyncMyError
from utils import tool_logger, format_query_results, validate_sql_parameters
from prompt import get_explain_table_prompt, get_query_tuning_prompt, get_migration_code_prompt
from config import (
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME,
    MCP_READ_ONLY, MCP_MAX_POOL_SIZE, ENCRYPTION_KEY, SIGNING_KEY
)

logger = logging.getLogger(__name__)

# Query execution timeout in seconds
QUERY_TIMEOUT_SECONDS = 30

class MariaDBServer:
    """
    MariaDB MCP Server implementation providing authenticated database operations.
    
    Features:
    - Connection pooling with configurable size limits
    - Read-only mode for production safety
    - Parameterized queries for SQL injection protection
    - Comprehensive error handling and audit logging
    - MCP tool registration for various database operations
    
    Usage:
        server = MariaDBServer()
        await server.run_async_server(transport="stdio")
    """
    
    def __init__(self, server_name="MariaDB_Server", autocommit=True):
        self.mcp = FastMCP(server_name)
        self.pool: Optional[asyncmy.Pool] = None
        self.autocommit = autocommit
        self.is_read_only = MCP_READ_ONLY
        self.auth = AuthService(
            encryption_key=ENCRYPTION_KEY,
            signing_key=SIGNING_KEY
        )
        
        logger.info(f"Initializing {server_name}...")
        if self.is_read_only:
            logger.warning("Server running in READ-ONLY mode. Write operations are disabled.")

    async def initialize_pool(self):
        """
        Initialize database connection pool with configured settings.
        
        Creates asyncmy pool with connection limits, recycling, and autocommit.
        Pool is required before registering MCP tools.
        
        Raises:
            ConnectionError: If database credentials are missing
            AsyncMyError: If database connection fails
        """
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
            logger.error(f"Failed to initialize database connection pool: {type(e).__name__}: {str(e)}")
            self.pool = None
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during pool initialization: {type(e).__name__}: {str(e)}")
            self.pool = None
            raise

    async def close_pool(self):
        """
        Gracefully close database connection pool.
        
        Called automatically during server shutdown to ensure clean resource cleanup.
        """
        if self.pool:
            logger.info("Closing database connection pool...")
            try:
                self.pool.close()
                await self.pool.wait_closed()
                logger.info("Database connection pool closed.")
            except Exception as e:
                logger.error(f"Error closing connection pool: {type(e).__name__}: {str(e)}")
            finally:
                self.pool = None

    async def _execute_query(self, sql: str, params: Optional[tuple] = None, database: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Execute SQL query with connection pooling and read-only enforcement.
        
        Internal method that handles:
        - Connection acquisition from pool
        - Database context switching if needed
        - Read-only mode validation
        - Query execution with parameterized binding
        - Parameter validation with helpful error messages
        - Result formatting for better readability
        
        Args:
            sql: SQL query to execute
            params: Optional tuple of parameters for prepared statements
            database: Target database name (switches context if different)
            
        Returns:
            List of result rows as dictionaries (with formatted values)
            
        Raises:
            RuntimeError: If pool unavailable or query execution fails
            PermissionError: If non-read query attempted in read-only mode
            ValueError: If parameter count doesn't match SQL placeholders
        """
        if self.pool is None:
            logger.error("Connection pool is not initialized.")
            raise RuntimeError("Database connection pool not available.")

        # Validate parameters before executing query
        try:
            validate_sql_parameters(sql, params)
        except ValueError as e:
            logger.warning(f"Parameter validation failed: {e}")
            raise e

        allowed_prefixes = ('SELECT', 'SHOW', 'DESC', 'DESCRIBE', 'USE', 'EXPLAIN')
        query_upper = sql.strip().upper()
        is_allowed_read_query = any(query_upper.startswith(prefix) for prefix in allowed_prefixes)

        if self.is_read_only and not is_allowed_read_query:
             logger.warning(f"Blocked potentially non-read-only query in read-only mode: {sql[:100]}...")
             raise PermissionError("Operation forbidden: Server is in read-only mode.")

        if params:
            logger.debug(f"Parameters: {params}")

        conn = None
        try:
            # Wrap the entire database operation in a timeout
            async def execute_with_connection():
                async with self.pool.acquire() as conn:
                    # Handle database switching if needed
                    if database:
                        async with conn.cursor() as switch_cursor:
                            await switch_cursor.execute(f"USE `{database}`")
                    
                    # Execute main query with fresh cursor
                    async with conn.cursor(cursor=asyncmy.cursors.DictCursor) as cursor:
                        await cursor.execute(sql, params or ())
                        results = await cursor.fetchall()
                        
                        # Format results for better readability
                        formatted_results = format_query_results(results if results else [])
                        return formatted_results
            
            # Execute with timeout
            return await asyncio.wait_for(execute_with_connection(), timeout=QUERY_TIMEOUT_SECONDS)
            
        except asyncio.TimeoutError:
            query_preview = sql[:100] + "..." if len(sql) > 100 else sql
            logger.warning(f"Query execution timeout after {QUERY_TIMEOUT_SECONDS} seconds. Query: {query_preview}")
            raise RuntimeError(
                f"Query execution timed out after {QUERY_TIMEOUT_SECONDS} seconds. "
                f"Consider adding WHERE clauses, LIMIT, or check with EXPLAIN tool for optimization."
            )
        except AsyncMyError as e:
            # Enhanced error message for common parameter issues
            error_str = str(e)
            if "not enough arguments for format string" in error_str.lower():
                raise RuntimeError(
                    f"Parameter binding error: {e}\n\n"
                    "This usually means:\n"
                    "1. Your SQL query has %s placeholders but no parameters were provided\n"
                    "2. The number of %s placeholders doesn't match the number of parameters\n"
                    "3. You're using % in date functions - use %% instead (e.g., DATE_FORMAT(date, '%%Y-%%m-%%d'))\n\n"
                    "Current query: " + sql[:200] + ("..." if len(sql) > 200 else "") + "\n"
                    f"Parameters provided: {params}"
                ) from e
            # Don't log here to avoid duplicate logging - let higher level handle it
            raise RuntimeError(f"Database error: {e}") from e
        except PermissionError as e:
             logger.warning(f"Permission denied: {e}")
             raise e
        except ValueError as e:
            # Re-raise parameter validation errors as-is
            raise e
        except Exception as e:
            if isinstance(e, RuntimeError) and 'Event loop is closed' in str(e):
                 logger.critical("Detected closed event loop during query execution!")
                 raise RuntimeError("Event loop closed unexpectedly during query.") from e
            raise RuntimeError(f"An unexpected error occurred: {e}") from e
            
    async def _database_exists(self, database_name: str) -> bool:
        """
        Check if database exists on the server.
        
        Args:
            database_name: Name to check (validates as SQL identifier)
            
        Returns:
            True if database exists and is accessible
        """
        if not database_name or not database_name.isidentifier():
            logger.warning(f"_database_exists called with invalid database_name: {database_name}")
            return False 

        sql = "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = %s"
        try:
            results = await self._execute_query(sql, params=(database_name,), database='information_schema')
            return len(results) > 0
        except Exception as e:
            logger.error(f"Error checking if database '{database_name}' exists: {type(e).__name__}: {str(e)}")
            return False
        
    async def _table_exists(self, database_name: str, table_name: str) -> bool:
        """
        Check if table exists in the specified database.
        
        Args:
            database_name: Database to check in
            table_name: Table name to verify
            
        Returns:
            True if table exists and is accessible
        """
        if not database_name or not database_name.isidentifier() or \
           not table_name or not table_name.isidentifier():
            logger.warning(f"_table_exists called with invalid names: db='{database_name}', table='{table_name}'")
            return False

        sql = "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s"
        try:
            results = await self._execute_query(sql, params=(database_name, table_name), database='information_schema')
            return len(results) > 0
        except Exception as e:
            logger.error(f"Error checking if table '{database_name}.{table_name}' exists: {type(e).__name__}: {str(e)}")
            return False

    # --- MCP Tool Methods ---
    # These methods are exposed as MCP tools and require authentication
    @AuthService.authorization()
    @tool_logger
    async def list_databases(self) -> Dict[str, Any]:
        """
        List all accessible databases on the MariaDB server.
        
        Returns:
            Dictionary containing list of database names and usage notice
        """
        # Add 0.2 second delay for concurrency testing
        print("before:", get_current_user_id(), get_current_client_ip())
        await asyncio.sleep(2)
        print("after:", get_current_user_id(), get_current_client_ip())
        sql = "SHOW DATABASES"
        try:
            results = await self._execute_query(sql)
            db_list = [row['Database'] for row in results if 'Database' in row]
            
            # Add environment-specific database usage notice
            data = {
                "databases": db_list,
                "usage_guide": {
                    "description": "MariaDB MCP Server - Core database tools",
                    "environment": f"Unless specifically mentioned otherwise, you should work in the '{DB_NAME}' database",
                    "tools": {
                        "execute_sql": "Execute queries with %s parameterization",
                        "get_table_schema": "Get table structure with columns/types/foreign keys",
                        "explain_query": "Analyze query performance and execution plan",
                        "list_tables": "List all tables in specified database"
                    },
                    "patterns": {
                        "basic": "SELECT * FROM table WHERE column = %s",
                        "joins": "SELECT t1.*, t2.name FROM table1 t1 JOIN table2 t2 ON t1.id = t2.ref_id"
                    },
                    "date_functions": {
                        "important": "날짜 함수에서 % 문자는 반드시 %% 로 이스케이프해야 합니다",
                        "examples": {
                            "correct": "DATE_FORMAT(date_col, '%%Y-%%m-%%d')",
                            "wrong": "DATE_FORMAT(date_col, '%Y-%m-%d')",
                            "functions": ["DATE_FORMAT", "TIME_FORMAT", "STR_TO_DATE"]
                        },
                        "reason": "Python 문자열 포매팅과 충돌을 방지하기 위해 % 문자를 %% 로 이스케이프 필요"
                    },
                    "reserved_words": {
                        "warning": "MySQL/MariaDB 예약어는 별칭(alias)으로 사용할 수 없습니다",
                        "common_issues": [
                            "current_time", "current_date", "current_timestamp",
                            "user", "database", "schema", "table", "index",
                            "key", "primary", "foreign", "unique", "null"
                        ],
                        "solutions": {
                            "good": "SELECT NOW() as now_time, CURDATE() as today_date",
                            "bad": "SELECT NOW() as current_time, CURDATE() as current_date"
                        },
                        "tip": "예약어와 충돌 시 '_time', '_date', '_value' 등의 접미사를 사용하세요"
                    }
                }
            }
            return data
        except Exception as e:
            logger.error(f"TOOL ERROR: list_databases | User: {get_current_user_id()} | IP: {get_current_client_ip()} | Error: {type(e).__name__}: {str(e)}")
            raise

    @AuthService.authorization()
    @tool_logger
    async def list_tables(self, database_name: str) -> List[str]:
        """
        List all tables in the specified database.
        
        Args:
            database_name: Target database (must be valid SQL identifier)
            
        Returns:
            List of table names in the database
        """
        if not database_name or not database_name.isidentifier():
            logger.warning(f"TOOL WARNING: list_tables | User: {get_current_user_id()} | IP: {get_current_client_ip()} | Invalid database_name: '{database_name}'")
            raise ValueError(f"Invalid database name provided: {database_name}")
        sql = "SHOW TABLES"
        try:
            results = await self._execute_query(sql, database=database_name)
            table_list = [list(row.values())[0] for row in results if row]
            return table_list
        except Exception as e:
            logger.error(f"TOOL ERROR: list_tables | User: {get_current_user_id()} | IP: {get_current_client_ip()} | database_name='{database_name}' | Error: {type(e).__name__}: {str(e)}")
            raise

    @AuthService.authorization()
    @tool_logger
    async def get_table_schema(self, database_name: str, table_name: str, include_foreign_keys: bool = True) -> Dict[str, Any]:
        """
        Get comprehensive table schema including column definitions, constraints, comments, and foreign key relationships.
        
        Args:
            database_name: Target database name
            table_name: Target table name
            include_foreign_keys: Whether to include foreign key relationship information (default: True)
            
        Returns:
            Dictionary with comprehensive table schema information:
            {
                'table_info': {
                    'database_name': str,
                    'table_name': str,
                    'table_comment': str or None,
                    'total_columns': int,
                    'foreign_key_count': int (only if include_foreign_keys=True)
                },
                'columns': {
                    'column_name': {
                        'type': 'SQL data type',
                        'nullable': bool,
                        'key': 'Key type (PRI/UNI/MUL)',
                        'default': 'Default value or None',
                        'extra': 'Additional info (auto_increment, etc.)',
                        'comment': 'Column comment if any',
                        'foreign_key': {...} or None (only if include_foreign_keys=True)
                    }
                },
                'foreign_keys_summary': [...] (only if include_foreign_keys=True)
            }
        """
        if not database_name or not database_name.isidentifier():
            logger.warning(f"TOOL WARNING: get_table_schema | User: {get_current_user_id()} | IP: {get_current_client_ip()} | Invalid database_name: '{database_name}'")
            raise ValueError(f"Invalid database name provided: {database_name}")
        if not table_name or not table_name.isidentifier():
            logger.warning(f"TOOL WARNING: get_table_schema | User: {get_current_user_id()} | IP: {get_current_client_ip()} | Invalid table_name: '{table_name}'")
            raise ValueError(f"Invalid table name provided: {table_name}")

        try:
            # Get basic schema using DESCRIBE
            describe_sql = f"DESCRIBE `{database_name}`.`{table_name}`"
            
            # Get detailed column information including comments from information_schema
            column_info_sql = """
            SELECT 
                COLUMN_NAME,
                COLUMN_COMMENT,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                DATA_TYPE,
                COLUMN_TYPE,
                EXTRA
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """
            
            # Get table comment
            table_comment_sql = """
            SELECT TABLE_COMMENT
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """
            
            # Execute basic queries
            schema_results = await self._execute_query(describe_sql)
            column_details = await self._execute_query(column_info_sql, params=(database_name, table_name))
            table_comment_result = await self._execute_query(table_comment_sql, params=(database_name, table_name))
            
            # Build basic schema info dictionary
            schema_info = {}
            
            # Create lookup dictionary for column comments and details
            column_lookup = {col['COLUMN_NAME']: col for col in column_details}
            
            if not schema_results:
                exists_sql = "SELECT COUNT(*) as count FROM information_schema.tables WHERE table_schema = %s AND table_name = %s"
                exists_result = await self._execute_query(exists_sql, params=(database_name, table_name))
                if not exists_result or exists_result[0]['count'] == 0:
                    logger.warning(f"TOOL WARNING: get_table_schema | User: {get_current_user_id()} | IP: {get_current_client_ip()} | Table '{database_name}'.'{table_name}' not found or inaccessible")
                    raise FileNotFoundError(f"Table '{database_name}'.'{table_name}' not found or inaccessible.")
                else:
                    logger.warning(f"TOOL WARNING: get_table_schema | User: {get_current_user_id()} | IP: {get_current_client_ip()} | Could not describe table '{database_name}'.'{table_name}' - might be a view or lack permissions")

            # Process DESCRIBE results with enhanced information
            for row in schema_results:
                col_name = row.get('Field')
                if col_name:
                    col_details = column_lookup.get(col_name, {})
                    schema_info[col_name] = {
                        'type': row.get('Type'),
                        'nullable': row.get('Null', '').upper() == 'YES',
                        'key': row.get('Key'),
                        'default': row.get('Default'),
                        'extra': row.get('Extra'),
                        'comment': col_details.get('COLUMN_COMMENT', '') or None
                    }
                    
                    # Initialize foreign_key field if requested
                    if include_foreign_keys:
                        schema_info[col_name]['foreign_key'] = None
            
            # Get table comment
            table_comment = table_comment_result[0].get('TABLE_COMMENT') if table_comment_result else None
            
            # Build result structure
            result = {
                'table_info': {
                    'database_name': database_name,
                    'table_name': table_name,
                    'table_comment': table_comment if table_comment else None,
                    'total_columns': len(schema_info)
                },
                'columns': schema_info
            }
            
            # Add foreign key information if requested
            if include_foreign_keys:
                # Query foreign key relationships from information_schema
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
                
                # Add foreign key details to matching columns
                for fk_row in fk_results:
                    column_name = fk_row['column_name']
                    if column_name in schema_info:
                        schema_info[column_name]['foreign_key'] = {
                            'constraint_name': fk_row['constraint_name'],
                            'referenced_database': fk_row['referenced_database'],
                            'referenced_table': fk_row['referenced_table'],
                            'referenced_column': fk_row['referenced_column'],
                            'on_update': fk_row['on_update'],
                            'on_delete': fk_row['on_delete'],
                            'full_reference': f"{fk_row['referenced_database']}.{fk_row['referenced_table']}.{fk_row['referenced_column']}"
                        }
                
                # Add foreign key summary and count to result
                result['table_info']['foreign_key_count'] = len(fk_results)
                result['foreign_keys_summary'] = [
                    {
                        'column': fk['column_name'],
                        'references': f"{fk['referenced_database']}.{fk['referenced_table']}.{fk['referenced_column']}",
                        'constraint': fk['constraint_name']
                    }
                    for fk in fk_results
                ]
            
            return result
            
        except FileNotFoundError as e:
            logger.warning(f"TOOL WARNING: get_table_schema | User: {get_current_user_id()} | IP: {get_current_client_ip()} | Table not found: {e}")
            raise e
        except Exception as e:
            logger.error(f"TOOL ERROR: get_table_schema | User: {get_current_user_id()} | IP: {get_current_client_ip()} | database_name='{database_name}', table_name='{table_name}' | Error: {type(e).__name__}: {str(e)}")
            raise RuntimeError(f"Could not retrieve schema for table '{database_name}.{table_name}'.")

    @AuthService.authorization()
    @tool_logger
    async def execute_sql(self, sql_query: str, database_name: str, parameters: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute read-only SQL query with parameterized binding for safety.
        
        Args:
            sql_query: SQL query to execute (SELECT, SHOW, DESCRIBE, etc.)
            database_name: Target database context
            parameters: Optional list of values for %s placeholders in query
            
        Returns:
            List of result rows as dictionaries
            
        Example:
            await execute_sql(
                "SELECT * FROM users WHERE id = %s AND status = %s",
                "mydb", 
                [123, "active"]
            )
        """
        if database_name and not database_name.isidentifier():
            logger.warning(f"TOOL WARNING: execute_sql | User: {get_current_user_id()} | IP: {get_current_client_ip()} | Invalid database_name: '{database_name}'")
            raise ValueError(f"Invalid database name provided: {database_name}")
        param_tuple = tuple(parameters) if parameters is not None else None
        try:
            results = await self._execute_query(sql_query, params=param_tuple, database=database_name)
            return results
        except Exception as e:
            query_preview = sql_query[:100] + "..." if len(sql_query) > 100 else sql_query
            logger.error(f"TOOL ERROR: execute_sql | User: {get_current_user_id()} | IP: {get_current_client_ip()} | database_name='{database_name}' | sql_query='{query_preview}' | parameters={parameters} | Error: {type(e).__name__}: {str(e)}")
            raise
            
    @AuthService.authorization()
    @tool_logger
    async def explain_query(self, sql_query: str, database_name: str, parameters: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """
        Get detailed query execution plan with extended information.
        
        Provides more comprehensive analysis including
        filtered row percentages and detailed optimizer information.
        
        Args:
            sql_query: Query to analyze (without EXPLAIN EXTENDED prefix)
            database_name: Target database context
            parameters: Optional parameters for query placeholders
            
        Returns:
            Extended execution plan with additional optimization details
        """
        if database_name and not database_name.isidentifier():
            logger.warning(f"TOOL WARNING: explain_query_extended | User: {get_current_user_id()} | IP: {get_current_client_ip()} | Invalid database_name: '{database_name}'")
            raise ValueError(f"Invalid database name provided: {database_name}")
        
        # Prefix query with EXPLAIN EXTENDED for detailed analysis
        explain_sql = f"EXPLAIN EXTENDED {sql_query.strip()}"
        param_tuple = tuple(parameters) if parameters is not None else None
        
        try:
            results = await self._execute_query(explain_sql, params=param_tuple, database=database_name)
            return results
        except Exception as e:
            query_preview = sql_query[:100] + "..." if len(sql_query) > 100 else sql_query
            logger.error(f"TOOL ERROR: explain_query_extended | User: {get_current_user_id()} | IP: {get_current_client_ip()} | database_name='{database_name}' | sql_query='{query_preview}' | parameters={parameters} | Error: {type(e).__name__}: {str(e)}")
            raise

    @AuthService.authorization()
    @tool_logger
    async def create_database(self, database_name: str) -> Dict[str, Any]:
        """
        Create new database if it doesn't already exist.
        
        Note: Only available when server is not in read-only mode.
        
        Args:
            database_name: Name for new database (must be valid SQL identifier)
            
        Returns:
            Operation result with status ('success' or 'exists') and message
        """
        if not database_name or not database_name.isidentifier():
            logger.error(f"TOOL ERROR: create_database | User: {get_current_user_id()} | IP: {get_current_client_ip()} | Invalid database_name: '{database_name}' - must be a valid identifier")
            raise ValueError(f"Invalid database_name for creation: '{database_name}'. Must be a valid identifier.")

        # Check existence first for informative response message
        if await self._database_exists(database_name):
            message = f"Database '{database_name}' already exists."
            return {"status": "exists", "message": message, "database_name": database_name}

        sql = f"CREATE DATABASE IF NOT EXISTS `{database_name}`;"

        try:
            await self._execute_query(sql, database=None)
            return {"status": "success", "message": message, "database_name": database_name}
        except Exception as e:
            error_message = f"Failed to create database '{database_name}'."
            logger.error(f"TOOL ERROR: create_database | User: {get_current_user_id()} | IP: {get_current_client_ip()} | database_name='{database_name}' | Error: {type(e).__name__}: {str(e)}")
            raise RuntimeError(f"{error_message} Reason: {str(e)}")
        
    # --- MCP Prompt Methods ---
    # These methods are exposed as MCP prompts

    async def explain_table(
        self,
        table_name: str, 
    ) -> str:
        """
        테이블 구조 분석을 위한 프롬프트를 반환합니다.
        
        Args:
            table_name: 분석할 테이블명
            
        Returns:
            테이블 구조 분석 프롬프트
        """
        return get_explain_table_prompt(table_name)

    async def query_tuning(
        self,
        original_query: str,
    ) -> str:
        """
        쿼리 성능 분석을 위한 프롬프트를 반환합니다.
        
        Args:
            original_query: 분석할 원본 쿼리
            database_name: 데이터베이스명
            optimization_focus: 최적화 중점 영역
            
        Returns:
            쿼리 성능 분석 프롬프트
        """
        return get_query_tuning_prompt(original_query)
    
    async def migration_code(
            self,
            table_name: str,
            migration_description: str
    ) -> str:
        """
        데이터베이스 마이그레이션 가이드를 위한 프롬프트 템플릿을 반환합니다.
        변경 대상 컬럼과 ID만 선택적으로 백업하는 효율적인 마이그레이션 전략 제공
        
        Args:
            table_name: 마이그레이션할 테이블명
            migration_description: 마이그레이션 내용 설명
            
        Returns:
            데이터베이스 마이그레이션 가이드 프롬프트
        """
        return get_migration_code_prompt(table_name, migration_description)

    # --- Tool Registration ---
    
    def register_tools(self):
        """
        Register all MCP tool methods with the FastMCP server.
        
        Creates FunctionTool instances for each public method and adds them
        to the MCP server. Read-only mode affects which tools are registered.
        
        Note: Database pool must be initialized before calling this method.
        """
        if self.pool is None:
             logger.error("Cannot register tools: Database pool is not initialized.")
             raise RuntimeError("Database pool must be initialized before registering tools.")

        # Register core database operation tools
        self.mcp.add_tool(FunctionTool.from_function(self.list_databases, name="list_databases"))
        self.mcp.add_tool(FunctionTool.from_function(self.list_tables, name="list_tables"))
        self.mcp.add_tool(FunctionTool.from_function(self.get_table_schema, name="get_table_schema"))
        self.mcp.add_tool(FunctionTool.from_function(self.execute_sql, name="execute_sql"))
        self.mcp.add_tool(FunctionTool.from_function(self.explain_query, name="explain_query"))
        if not self.is_read_only:
            self.mcp.add_tool(FunctionTool.from_function(self.create_database, name="create_database"))

        # self.mcp.prompt()(self.generate_migration_guide)
        self.mcp.prompt()(self.query_tuning) 
        self.mcp.prompt()(self.explain_table)
        self.mcp.prompt()(self.migration_code)

        logger.info("Registered MCP tools using FunctionTool.from_function() and prompts using add_prompt().")
        logger.debug("register_tools: completed")

    # --- Async Main Server Logic ---
    async def run_async_server(self, transport="stdio", host="0.0.0.0", port=9001):
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
            logger.critical(f"Server setup failed: {type(e).__name__}: {str(e)}")
            raise
        except Exception as e:
            logger.critical(f"Server execution failed with an unexpected error: {type(e).__name__}: {str(e)}")
            raise
        finally:
            await self.close_pool()