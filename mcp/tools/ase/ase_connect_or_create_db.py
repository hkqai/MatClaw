"""
Tool for initializing or connecting to an ASE (Atomic Simulation Environment) database.
Creates new database files or connects to existing ones for storing atomic structures and calculations.
Supports SQLite (default), PostgreSQL, and MySQL backends.
"""

from typing import Dict, Any, Optional, Literal, Annotated
from pydantic import Field
from pathlib import Path


def ase_connect_or_create_db(
    db_path: Annotated[
        str,
        Field(
            description="Path to the database file or connection string. "
            "For SQLite: 'simulations_campaign_2026.db' or './data/ase_results.db'. "
            "For PostgreSQL: 'postgresql://user:password@host:port/database'. "
            "For MySQL: 'mysql://user:password@host:port/database'."
        )
    ],
    
    backend: Annotated[
        Literal["sqlite", "postgresql", "mysql"],
        Field(
            default="sqlite",
            description="Database backend type. Options: 'sqlite' (default, file-based), "
            "'postgresql' (remote server), 'mysql' (remote server)."
        )
    ] = "sqlite",
    
    create_if_missing: Annotated[
        bool,
        Field(
            default=True,
            description="If True, creates a new database if the file/database doesn't exist. "
            "If False, returns an error if the database is not found."
        )
    ] = True,
    
    connect_timeout: Annotated[
        Optional[int],
        Field(
            default=30,
            ge=1,
            le=300,
            description="Connection timeout in seconds (1-300). Default: 30. "
            "Note: Primarily for remote databases (PostgreSQL/MySQL). "
            "SQLite (local files) typically don't use explicit timeouts."
        )
    ] = 30,
    
    append: Annotated[
        bool,
        Field(
            default=True,
            description="If True, opens database in append mode (read/write). "
            "If False, opens in read-only mode. "
            "Note: On Windows, rapid sequential access to the same database file "
            "may cause temporary locking conflicts. Allow brief delays between operations."
        )
    ] = True
) -> Dict[str, Any]:
    """
    Initialize or connect to an ASE database for storing atomic structures and calculations.
    
    This tool creates a new database or connects to an existing one, providing a persistent
    storage solution for atomic simulations throughout a campaign or session.
    
    Returns:
        dict: Connection status and database information including:
            - success (bool): Whether connection was established
            - db_path (str): Path or connection string used
            - backend (str): Database backend type
            - exists (bool): Whether database existed before this call
            - writable (bool): Whether database is writable
            - count (int): Number of entries in database (if accessible)
            - message (str): Success/status message
            - error (str): Error message if failed
    """
    
    try:
        # Import ASE database module
        try:
            from ase.db import connect
        except ImportError:
            return {
                "success": False,
                "error": "ASE (Atomic Simulation Environment) is not installed. "
                        "Install it with: pip install ase"
            }
        
        # Validate backend
        if backend not in ["sqlite", "postgresql", "mysql"]:
            return {
                "success": False,
                "error": f"Invalid backend '{backend}'. Must be 'sqlite', 'postgresql', or 'mysql'."
            }
        
        # Check if database exists (for SQLite)
        db_existed = False
        if backend == "sqlite":
            db_file = Path(db_path)
            db_existed = db_file.exists()
            
            # Create parent directories if needed
            if create_if_missing and not db_existed:
                db_file.parent.mkdir(parents=True, exist_ok=True)
            elif not create_if_missing and not db_existed:
                return {
                    "success": False,
                    "db_path": db_path,
                    "backend": backend,
                    "error": f"Database file '{db_path}' does not exist and create_if_missing=False"
                }
        else:
            db_existed = None  # Unknown until we try to connect
        
        # Build connection string
        if backend == "sqlite":
            connection_string = str(db_path)
        else:
            connection_string = db_path
            if not connection_string.startswith(f"{backend}://"):
                return {
                    "success": False,
                    "error": f"Invalid connection string for {backend}. "
                            f"Expected format: {backend}://user:password@host:port/database"
                }
        
        # Connect to database
        try:
            if backend == "sqlite":
                db = connect(connection_string, append=append)
            else:
                # For remote databases, timeout may be handled differently
                db = connect(connection_string, append=append)
        except Exception as conn_err:
            if not create_if_missing:
                return {
                    "success": False,
                    "db_path": db_path,
                    "backend": backend,
                    "error": f"Failed to connect to database: {str(conn_err)}"
                }
            else:
                # Retry connection (ASE should create file for SQLite)
                try:
                    db = connect(connection_string, append=append)
                except Exception as retry_err:
                    return {
                        "success": False,
                        "db_path": db_path,
                        "backend": backend,
                        "error": f"Failed to create/connect to database: {str(retry_err)}"
                    }
        
        # Get database information
        try:
            entry_count = db.count()
        except:
            entry_count = 0
        
        is_writable = append
        metadata = {}
        try:
            if hasattr(db, 'metadata'):
                metadata = db.metadata or {}
        except:
            pass
        
        result = {
            "success": True,
            "db_path": db_path,
            "backend": backend,
            "exists": db_existed if db_existed is not None else True,
            "writable": is_writable,
            "count": entry_count,
            "metadata": metadata if metadata else None,
            "message": f"Successfully connected to {'existing' if db_existed else 'new'} ASE database "
                      f"at '{db_path}' ({entry_count} entries)"
        }
        
        # Add connection details for remote databases
        if backend != "sqlite":
            result["connection_info"] = "Remote database connection established"
        
        # Store connection info in a global registry for other tools to use
        try:
            if not hasattr(ase_connect_or_create_db, '_db_registry'):
                ase_connect_or_create_db._db_registry = {}
            
            ase_connect_or_create_db._db_registry[db_path] = {
                "connection_string": connection_string,
                "backend": backend,
                "writable": is_writable
            }
        except:
            pass
        
        try:
            if hasattr(db, '_con') and hasattr(db._con, 'close'):
                db._con.close()
        except:
            pass
        
        return result
        
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import required module: {str(e)}. "
                    "Make sure ASE is installed: pip install ase"
        }
    
    except FileNotFoundError as e:
        return {
            "success": False,
            "db_path": db_path,
            "backend": backend,
            "error": f"Database file or path not found: {str(e)}"
        }
    
    except PermissionError as e:
        return {
            "success": False,
            "db_path": db_path,
            "backend": backend,
            "error": f"Permission denied accessing database: {str(e)}. "
                    "Check file/directory permissions."
        }
    
    except TimeoutError as e:
        return {
            "success": False,
            "db_path": db_path,
            "backend": backend,
            "error": f"Connection timeout after {connect_timeout} seconds: {str(e)}. "
                    "Try increasing connect_timeout or check network connection."
        }
    
    except Exception as e:
        return {
            "success": False,
            "db_path": db_path,
            "backend": backend,
            "error": f"Unexpected error connecting to database: {str(e)}",
            "error_type": type(e).__name__
        }
