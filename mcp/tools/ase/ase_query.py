"""
Tool for querying ASE databases to find existing calculations.
Searches by formula, tags, metadata, and property ranges.
Returns lightweight summaries without full atomic structures by default.
"""

from typing import Dict, Any, Optional, List, Literal, Annotated
from pydantic import Field
import numpy as np


def ase_query(
    db_path: Annotated[
        str,
        Field(
            description="Path to the ASE database file to query (e.g., 'simulations.db', './data/results.db')."
        )
    ],
    formula: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Chemical formula to search for (e.g., 'H2O', 'LiFePO4', 'Fe2O3'). "
            "Use with formula_mode to specify exact or reduced formula matching."
        )
    ] = None,
    formula_mode: Annotated[
        Literal["exact", "reduced"],
        Field(
            default="reduced",
            description="Formula matching mode. 'reduced': match by reduced formula (e.g., 'FeO' matches 'Fe2O2'). "
            "'exact': match exact formula including stoichiometry."
        )
    ] = "reduced",
    tags: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description="List of keyword tags to filter by. Returns entries containing ANY of these tags. "
            "Example: ['converged', 'optimized', 'cathode']. "
            "Note: Store tags in metadata using 'keywords' or 'labels' key to avoid conflicts with ASE's atom tags."
        )
    ] = None,
    energy_min: Annotated[
        Optional[float],
        Field(
            default=None,
            description="Minimum energy in eV. Filter results with energy >= this value."
        )
    ] = None,
    energy_max: Annotated[
        Optional[float],
        Field(
            default=None,
            description="Maximum energy in eV. Filter results with energy <= this value."
        )
    ] = None,
    property_filters: Annotated[
        Optional[Dict[str, Any]],
        Field(
            default=None,
            description="Dictionary of metadata key-value pairs to filter by. "
            "Examples: {'converged': True, 'method': 'DFT-PBE', 'campaign': 'opt_2026'}. "
            "For numeric ranges, use tuples: {'volume': (10, 50)} for 10 <= volume <= 50."
        )
    ] = None,
    calculator_name: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Filter by calculator name (e.g., 'vasp', 'gpaw', 'lammps', 'emt')."
        )
    ] = None,
    limit: Annotated[
        int,
        Field(
            default=100,
            ge=1,
            le=10000,
            description="Maximum number of results to return (1-10000). Default: 100."
        )
    ] = 100,
    sort_by: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Field to sort results by. Common options: 'energy', 'id', 'ctime', 'natoms', "
            "or any metadata key. If None, returns in database order."
        )
    ] = None,
    sort_order: Annotated[
        Literal["asc", "desc"],
        Field(
            default="asc",
            description="Sort order: 'asc' (ascending, lowest first) or 'desc' (descending, highest first)."
        )
    ] = "asc",
    include_atoms: Annotated[
        bool,
        Field(
            default=False,
            description="If True, includes full atoms_dict in results (large data). "
            "If False (default), returns only lightweight summaries. "
            "Set to True only when you need to reconstruct structures."
        )
    ] = False,
    unique_key: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Search for entry with specific unique_key. Returns at most one result."
        )
    ] = None
) -> Dict[str, Any]:
    """
    Query an ASE database for calculation results matching specified criteria.
    
    Returns lightweight summaries by default, suitable for checking if calculations
    already exist before running expensive simulations. Supports filtering by formula,
    properties, energy ranges, tags, and arbitrary metadata.
    
    Returns:
        dict: Query results including:
            - success (bool): Whether query executed successfully
            - count (int): Number of matching entries
            - results (list): List of matching entry summaries with:
                - id (int): Database row ID
                - formula (str): Chemical formula
                - natoms (int): Number of atoms
                - energy (float): Energy if available
                - ctime (float): Creation timestamp
                - user (str): User who created entry
                - calculator (str): Calculator name if available
                - metadata (dict): Selected metadata fields
                - atoms_dict (dict): Full Atoms dictionary (only if include_atoms=True)
            - query (dict): Query parameters used
            - message (str): Status message
            - error (str): Error message if failed
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
        
        try:
            db = connect(db_path)
        except Exception as e:
            return {
                "success": False,
                "db_path": db_path,
                "error": f"Failed to connect to database: {str(e)}. "
                        "Ensure the database exists. Use ase_connect_or_create_db to create it."
            }
        
        # Build query selection criteria
        selection_criteria = []
        selection_kwargs = {}
        
        if formula and formula_mode == "exact":
            selection_kwargs['formula'] = formula
        
        # Energy range filters
        if energy_min is not None:
            selection_criteria.append(f'energy>={energy_min}')
        if energy_max is not None:
            selection_criteria.append(f'energy<={energy_max}')
        
        # Calculator name filter
        if calculator_name:
            selection_kwargs['calculator'] = calculator_name
        
        # Unique key filter
        if unique_key:
            selection_kwargs['unique_key'] = unique_key
        
        # Property filters (metadata key-value pairs)
        if property_filters:
            for key, value in property_filters.items():
                if isinstance(value, tuple) and len(value) == 2:
                    # Range filter: (min, max)
                    min_val, max_val = value
                    selection_criteria.append(f'{key}>={min_val}')
                    selection_criteria.append(f'{key}<={max_val}')
                else:
                    # Exact match
                    selection_kwargs[key] = value
        
        # Execute query
        try:
            selection_str = ','.join(selection_criteria) if selection_criteria else None
            if selection_str:
                rows = db.select(selection_str, **selection_kwargs)
            else:
                rows = db.select(**selection_kwargs)
            rows = list(rows)
            
        except Exception as e:
            return {
                "success": False,
                "db_path": db_path,
                "error": f"Query failed: {str(e)}. Check your filter criteria syntax."
            }
        
        # Post-process results for additional filters
        filtered_rows = []
        for row in rows:
            if formula and formula_mode == "reduced":
                try:
                    from ase.formula import Formula
                    row_formula = Formula(row.formula)
                    query_formula = Formula(formula)
                    if row_formula.reduce()[0] != query_formula.reduce()[0]:
                        continue
                except:
                    if row.formula != formula:
                        continue
            
            # Tags filter
            if tags:
                row_tags = ''
                key_value_pairs = getattr(row, 'key_value_pairs', {})
                for tag_key in ['keywords', 'labels', 'tags']:
                    if tag_key in key_value_pairs:
                        row_tags = key_value_pairs[tag_key]
                        break
                
                if isinstance(row_tags, str):
                    row_tags_list = [t.strip() for t in row_tags.split(',') if t.strip()]
                elif isinstance(row_tags, list):
                    row_tags_list = row_tags
                else:
                    row_tags_list = []
                
                if not any(tag in row_tags_list for tag in tags):
                    continue
            
            filtered_rows.append(row)
        
        # Sort results
        if sort_by:
            reverse = (sort_order == "desc")
            try:
                # Try to sort by the specified field
                def get_sort_key(row):
                    if hasattr(row, sort_by):
                        value = getattr(row, sort_by)
                        if value is None:
                            return float('inf') if not reverse else float('-inf')
                        return value
                    if hasattr(row, 'key_value_pairs') and sort_by in row.key_value_pairs:
                        value = row.key_value_pairs[sort_by]
                        if value is None:
                            return float('inf') if not reverse else float('-inf')
                        return value
                    return float('inf') if not reverse else float('-inf')
                
                filtered_rows.sort(key=get_sort_key, reverse=reverse)
            except Exception as e:
                pass
        
        # Limit results
        filtered_rows = filtered_rows[:limit]
        
        # Format results
        results = []
        for row in filtered_rows:
            result = {
                'id': row.id,
                'formula': row.formula,
                'natoms': row.natoms,
            }
            
            # Add optional fields if they exist
            if hasattr(row, 'energy') and row.energy is not None:
                result['energy'] = float(row.energy)
            
            if hasattr(row, 'ctime'):
                result['ctime'] = row.ctime
            
            if hasattr(row, 'user'):
                result['user'] = row.user
            
            if hasattr(row, 'calculator') and row.calculator:
                result['calculator'] = row.calculator
            
            if hasattr(row, 'fmax') and row.fmax is not None:
                result['fmax'] = float(row.fmax)
            
            if hasattr(row, 'smax') and row.smax is not None:
                result['smax'] = float(row.smax)
            
            if hasattr(row, 'volume') and row.volume is not None:
                result['volume'] = float(row.volume)
            
            if hasattr(row, 'mass') and row.mass is not None:
                result['mass'] = float(row.mass)
            
            if hasattr(row, 'constrained_forces') and row.constrained_forces is not None:
                if isinstance(row.constrained_forces, np.ndarray):
                    result['constrained_forces'] = row.constrained_forces.tolist()
                else:
                    result['constrained_forces'] = row.constrained_forces
            
            if hasattr(row, 'key_value_pairs'):
                result['metadata'] = dict(row.key_value_pairs)
            else:
                result['metadata'] = {}
            
            if hasattr(row, 'data') and row.data:
                result['has_data'] = True
                result['data_keys'] = list(row.data.keys()) if isinstance(row.data, dict) else []
            
            if include_atoms:
                try:
                    atoms = row.toatoms()
                    result['atoms_dict'] = atoms.todict()
                except Exception as e:
                    result['atoms_error'] = f"Failed to extract atoms: {str(e)}"
            
            results.append(result)
        
        # Close database connection
        try:
            if hasattr(db, '_con') and hasattr(db._con, 'close'):
                db._con.close()
        except:
            pass
        
        # Build query summary
        query_summary = {
            'db_path': db_path,
            'formula': formula,
            'formula_mode': formula_mode if formula else None,
            'tags': tags,
            'energy_range': [energy_min, energy_max] if (energy_min is not None or energy_max is not None) else None,
            'property_filters': property_filters,
            'calculator': calculator_name,
            'unique_key': unique_key,
            'limit': limit,
            'sort_by': sort_by,
            'sort_order': sort_order if sort_by else None
        }
        
        return {
            "success": True,
            "count": len(results),
            "results": results,
            "query": query_summary,
            "message": f"Found {len(results)} matching entries in database"
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
            "db_path": db_path if 'db_path' in locals() else 'unknown',
            "error": f"Unexpected error querying database: {str(e)}",
            "error_type": type(e).__name__
        }
