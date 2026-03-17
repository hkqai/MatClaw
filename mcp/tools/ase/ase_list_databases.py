"""
Tool for discovering and listing ASE database files.
Scans directories for .db files, validates them as ASE databases,
and returns metadata including size, entry count, and timestamps.
"""

from typing import Dict, Any, List, Optional, Annotated
from pydantic import Field
import os
import glob


def ase_list_databases(
    search_dirs: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description="List of directories to search for database files. "
            "Examples: ['./data', './databases', './campaigns']. "
            "If None, searches current directory and common subdirectories. "
            "Paths can be absolute or relative to workspace."
        )
    ] = None,
    
    pattern: Annotated[
        str,
        Field(
            default="*.db",
            description="Filename pattern to match (glob syntax). "
            "Examples: '*.db' (all .db files), 'campaign_*.db', 'test_*.db', '*_2026.db'. "
            "Use wildcards: * (any chars), ? (single char), [abc] (char set)."
        )
    ] = "*.db",
    
    recursive: Annotated[
        bool,
        Field(
            default=False,
            description="If True, searches subdirectories recursively. "
            "If False, only searches specified directories (not subdirectories)."
        )
    ] = False,
    
    validate: Annotated[
        bool,
        Field(
            default=True,
            description="If True, validates each file is a valid ASE database by attempting connection. "
            "If False, returns all matching .db files without validation (faster but may include non-ASE files)."
        )
    ] = True,
    
    include_summary: Annotated[
        bool,
        Field(
            default=True,
            description="If True, includes summary statistics (entry count, formulas). "
            "If False, returns only basic file metadata (faster for large databases)."
        )
    ] = True
) -> Dict[str, Any]:
    """
    List and summarize ASE database files in specified directories.
    
    Scans directories for .db files, validates them as ASE databases, and returns
    metadata including file size, number of entries, creation/modification times,
    and optional summary statistics. Useful for discovering available databases
    at the start of a campaign or for database management.
    
    Returns:
        dict: Database listing including:
            - success (bool): Whether search completed successfully
            - count (int): Number of databases found
            - databases (list): List of database entries, each containing:
                - path (str): Full path to database file
                - filename (str): Database filename
                - size_bytes (int): File size in bytes
                - size_mb (float): File size in megabytes
                - created (float): Creation timestamp
                - modified (float): Last modified timestamp
                - valid (bool): Whether it's a valid ASE database
                - entry_count (int): Number of entries (if validated)
                - formulas (list): Unique chemical formulas (if include_summary)
                - error (str): Error message if validation failed
            - search_info (dict): Search parameters used
            - message (str): Status message
    """
    
    try:
        try:
            from ase.db import connect
        except ImportError:
            return {
                "success": False,
                "error": "ASE (Atomic Simulation Environment) is not installed. "
                        "Install it with: pip install ase"
            }
        
        # Set default search directories if not provided
        if search_dirs is None:
            search_dirs = [
                ".",
                "./data",
                "./databases",
                "./db",
                "./results"
            ]
        
        # Ensure search_dirs is a list
        if isinstance(search_dirs, str):
            search_dirs = [search_dirs]
        
        # Find all matching database files
        db_files = []
        
        for search_dir in search_dirs:
            expanded_dir = os.path.expanduser(search_dir)
            
            if not os.path.exists(expanded_dir):
                continue
            
            if not os.path.isdir(expanded_dir):
                continue
            
            # Build glob pattern
            if recursive:
                glob_pattern = os.path.join(expanded_dir, "**", pattern)
                matches = glob.glob(glob_pattern, recursive=True)
            else:
                glob_pattern = os.path.join(expanded_dir, pattern)
                matches = glob.glob(glob_pattern)
            
            # Add matches to list (convert to absolute paths)
            for match in matches:
                abs_path = os.path.abspath(match)
                if abs_path not in db_files and os.path.isfile(abs_path):
                    db_files.append(abs_path)
        
        # Process each database file
        databases = []
        
        for db_path in db_files:
            db_info = {
                "path": db_path,
                "filename": os.path.basename(db_path)
            }
            
            try:
                # Get file metadata
                stat = os.stat(db_path)
                db_info["size_bytes"] = stat.st_size
                db_info["size_mb"] = round(stat.st_size / (1024 * 1024), 2)
                db_info["created"] = stat.st_ctime
                db_info["modified"] = stat.st_mtime
                
                # Validate if requested
                if validate:
                    try:
                        # Try to connect to database
                        db = connect(db_path)
                        db_info["valid"] = True
                        
                        # Get entry count
                        try:
                            entry_count = db.count()
                            db_info["entry_count"] = entry_count
                        except:
                            db_info["entry_count"] = 0
                        
                        if include_summary and db_info.get("entry_count", 0) > 0:
                            try:
                                # Get unique formulas (limit to first 1000 entries for performance)
                                formulas = set()
                                for i, row in enumerate(db.select()):
                                    if i >= 1000:
                                        db_info["summary_limited"] = True
                                        break
                                    formulas.add(row.formula)
                                
                                db_info["formulas"] = sorted(list(formulas))
                                db_info["unique_formulas"] = len(formulas)
                                
                                # Get metadata keys from first entry
                                try:
                                    first_row = next(db.select())
                                    if hasattr(first_row, 'key_value_pairs') and first_row.key_value_pairs:
                                        db_info["metadata_keys"] = list(first_row.key_value_pairs.keys())
                                except StopIteration:
                                    pass
                                
                            except Exception as e:
                                db_info["summary_error"] = f"Failed to generate summary: {str(e)}"
                        
                        # Close connection
                        try:
                            if hasattr(db, '_con') and hasattr(db._con, 'close'):
                                db._con.close()
                        except:
                            pass
                        
                    except Exception as e:
                        db_info["valid"] = False
                        db_info["validation_error"] = str(e)
                else:
                    db_info["valid"] = "not_validated"
                
                databases.append(db_info)
                
            except PermissionError:
                db_info["valid"] = False
                db_info["error"] = "Permission denied"
                databases.append(db_info)
                
            except Exception as e:
                db_info["valid"] = False
                db_info["error"] = str(e)
                databases.append(db_info)
        
        databases.sort(key=lambda x: x["path"])
        
        search_info = {
            "search_dirs": search_dirs,
            "pattern": pattern,
            "recursive": recursive,
            "validated": validate
        }
        
        total_size_mb = sum(db.get("size_mb", 0) for db in databases)
        total_entries = sum(db.get("entry_count", 0) for db in databases if db.get("valid") == True)
        valid_count = sum(1 for db in databases if db.get("valid") == True)
        
        return {
            "success": True,
            "count": len(databases),
            "valid_count": valid_count,
            "total_size_mb": round(total_size_mb, 2),
            "total_entries": total_entries,
            "databases": databases,
            "search_info": search_info,
            "message": f"Found {len(databases)} database file(s), {valid_count} valid ASE database(s)"
        }
        
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import required module: {str(e)}. "
                    "Make sure ASE is installed: pip install ase"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error listing databases: {str(e)}",
            "error_type": type(e).__name__
        }
