import functools
import inspect
from auth_decorator import get_current_user_id, get_current_client_ip, get_current_api_key
from logger.logger import Logger
from typing import List, Dict, Any, Optional

logger = Logger.getLogger()

def tool_start_logger(func):
    """
    Decorator that logs MCP tool execution with authentication context.
    
    Captures and logs user ID, IP address, API key preview, and function parameters
    for audit and debugging purposes. SQL queries are truncated for readability.
    
    Note: Must be applied after @auth_decorator.require_auth to access user context.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        func_name = func.__name__
        
        # Extract and format function parameters
        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        
        params_dict = dict(bound_args.arguments)
        if 'self' in params_dict:
            del params_dict['self']
        
        if params_dict:
            formatted_params = []
            for k, v in params_dict.items():
                # Truncate long SQL queries for readability
                if k == 'sql_query' and isinstance(v, str) and len(v) > 100:
                    formatted_params.append(f"{k}='{v[:100]}...'")
                else:
                    formatted_params.append(f"{k}='{v}'")
            params_str = ', '.join(formatted_params)
        else:
            params_str = "None"
        
        logger.info(f"TOOL: {func_name} | User: {get_current_user_id()} | IP: {get_current_client_ip()} | API_KEY: {get_current_api_key()[:25] + '...'} | Parameters: {params_str}")
        
        return await func(*args, **kwargs)
    
    return wrapper

def format_query_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Format query results for better readability.
    
    Converts:
    - bit(1) values: \u0001 -> True, \u0000 -> False
    - bytes objects to readable strings where appropriate
    
    Args:
        results: Raw query results from database
        
    Returns:
        Formatted results with improved readability
    """
    if not results:
        return results
    
    formatted_results = []
    for row in results:
        formatted_row = {}
        for key, value in row.items():
            # Handle bit(1) values - convert bytes to boolean
            if isinstance(value, bytes) and len(value) == 1:
                # Check if it's a bit field (0 or 1)
                if value == b'\x01':
                    formatted_row[key] = True
                elif value == b'\x00':
                    formatted_row[key] = False
                else:
                    # Keep as bytes if not a clear boolean value
                    formatted_row[key] = value
            # Handle other bytes objects (convert to string if possible)
            elif isinstance(value, bytes):
                try:
                    formatted_row[key] = value.decode('utf-8')
                except UnicodeDecodeError:
                    formatted_row[key] = value
            else:
                formatted_row[key] = value
        formatted_results.append(formatted_row)
    
    return formatted_results

def validate_sql_parameters(sql: str, params: Optional[tuple]) -> None:
    """
    Validate SQL parameters to provide helpful error messages.
    
    Args:
        sql: SQL query string
        params: Parameters tuple
        
    Raises:
        ValueError: With detailed error message for parameter mismatches
    """
    if params is None:
        params = ()
    
    # Count %s placeholders in SQL, but exclude %%s and other %% patterns
    # Use a more sophisticated approach to handle escaped % characters
    import re
    
    # Replace all %% (escaped %) with a temporary placeholder first
    temp_sql = sql.replace('%%', '__ESCAPED_PERCENT__')
    
    # Now count %s patterns that are actual placeholders
    placeholder_count = temp_sql.count('%s')
    param_count = len(params)
    
    if placeholder_count != param_count:
        # Create helpful error message
        error_msg = f"Parameter count mismatch: SQL query has {placeholder_count} placeholder(s) (%s) but {param_count} parameter(s) provided."
        
        if placeholder_count > param_count:
            error_msg += f"\n\nMissing {placeholder_count - param_count} parameter(s). "
            error_msg += "Make sure to provide values for all %s placeholders in your query."
        elif param_count > placeholder_count:
            error_msg += f"\n\nToo many parameters provided ({param_count - placeholder_count} extra). "
            error_msg += "Remove extra parameters or add more %s placeholders to your query."
        
        # Add helpful examples
        error_msg += "\n\nExamples:"
        error_msg += "\n- Correct: execute_sql(\"SELECT * FROM table WHERE id = %s\", \"mydb\", [123])"
        error_msg += "\n- Correct: execute_sql(\"SELECT * FROM table WHERE id = %s AND name = %s\", \"mydb\", [123, \"test\"])"
        error_msg += "\n- Incorrect: execute_sql(\"SELECT * FROM table WHERE id = %s\", \"mydb\", [123, \"extra\"])"
        
        # Check for common date function issues
        if '%%' in sql and '%s' in sql:
            error_msg += "\n\nNote: For date functions, use %% for date formatting and %s for parameters:"
            error_msg += "\n- DATE_FORMAT(date_col, '%%Y-%%m-%%d') WHERE id = %s"
        
        raise ValueError(error_msg)