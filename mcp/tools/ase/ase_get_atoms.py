"""
Tool for retrieving full Atoms objects from ASE database by row ID.
Used to fetch stored structures for reuse in subsequent calculations.
Returns serialized atoms with calculator results and metadata.
"""

from typing import Dict, Any, List, Union, Annotated
from pydantic import Field
import numpy as np


def ase_get_atoms(
    db_path: Annotated[
        str,
        Field(
            description="Path to the ASE database file (e.g., 'simulations.db', './data/results.db')."
        )
    ],
    row_ids: Annotated[
        Union[int, List[int]],
        Field(
            description="Database row ID(s) to retrieve. Can be a single integer or list of integers. "
            "Example: 42 or [1, 5, 10]. Get IDs from ase_query or ase_store_result."
        )
    ],
    include_results: Annotated[
        bool,
        Field(
            default=True,
            description="If True, includes calculator results (energy, forces, stress, etc.) in output. "
            "If False, returns only the atomic structure."
        )
    ] = True,
    include_metadata: Annotated[
        bool,
        Field(
            default=True,
            description="If True, includes all metadata key-value pairs in output. "
            "If False, returns only atoms and results."
        )
    ] = True,
    include_data: Annotated[
        bool,
        Field(
            default=False,
            description="If True, includes the data blob (large arrays, nested structures). "
            "If False (default), omits data blob to reduce output size."
        )
    ] = False
) -> Dict[str, Any]:
    """
    Retrieve full Atoms objects from ASE database by row ID.
    
    Fetches stored atomic structures with their calculator results and metadata,
    returning them in serialized form ready for reconstruction and reuse in
    subsequent calculations (geometry optimization, MD, phonons, etc.).
    
    Returns:
        dict: Retrieved atoms and information including:
            - success (bool): Whether retrieval was successful
            - count (int): Number of entries retrieved
            - atoms (list): List of atom entries, each containing:
                - id (int): Database row ID
                - formula (str): Chemical formula
                - atoms_dict (dict): Serialized Atoms object (from atoms.todict())
                - results (dict): Calculator results if available and requested
                - metadata (dict): Metadata key-value pairs if requested
                - data (dict): Data blob if requested
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
        
        if isinstance(row_ids, int):
            row_ids = [row_ids]
        elif not isinstance(row_ids, list):
            return {
                "success": False,
                "error": f"row_ids must be an integer or list of integers, got {type(row_ids).__name__}"
            }
        
        if not row_ids:
            return {
                "success": False,
                "error": "row_ids cannot be empty. Provide at least one row ID."
            }
        
        if not all(isinstance(rid, int) and rid > 0 for rid in row_ids):
            return {
                "success": False,
                "error": "All row_ids must be positive integers"
            }
        
        # Connect to database
        try:
            db = connect(db_path)
        except Exception as e:
            return {
                "success": False,
                "db_path": db_path,
                "error": f"Failed to connect to database: {str(e)}. "
                        "Ensure the database exists. Use ase_connect_or_create_db to create it."
            }
        
        # Retrieve entries
        atoms_list = []
        not_found = []
        
        for row_id in row_ids:
            try:
                row = db.get(id=row_id)
                try:
                    atoms = row.toatoms()
                    atoms_dict = atoms.todict()
                    atoms_dict = _serialize_arrays(atoms_dict)
                except Exception as e:
                    return {
                        "success": False,
                        "db_path": db_path,
                        "row_id": row_id,
                        "error": f"Failed to extract Atoms object from row {row_id}: {str(e)}"
                    }
                
                entry = {
                    "id": row.id,
                    "formula": row.formula,
                    "natoms": row.natoms,
                    "atoms_dict": atoms_dict
                }
                
                if include_results:
                    results = {}
                    
                    # Energy
                    if hasattr(row, 'energy') and row.energy is not None:
                        results['energy'] = float(row.energy)
                    
                    # Forces
                    if hasattr(row, 'forces') and row.forces is not None:
                        results['forces'] = row.forces.tolist() if hasattr(row.forces, 'tolist') else row.forces
                    
                    # Stress
                    if hasattr(row, 'stress') and row.stress is not None:
                        results['stress'] = row.stress.tolist() if hasattr(row.stress, 'tolist') else row.stress
                    
                    # Magnetic moments
                    if hasattr(row, 'magmoms') and row.magmoms is not None:
                        results['magmoms'] = row.magmoms.tolist() if hasattr(row.magmoms, 'tolist') else row.magmoms
                    
                    # Charges
                    if hasattr(row, 'charges') and row.charges is not None:
                        results['charges'] = row.charges.tolist() if hasattr(row.charges, 'tolist') else row.charges
                    
                    # Dipole
                    if hasattr(row, 'dipole') and row.dipole is not None:
                        results['dipole'] = row.dipole.tolist() if hasattr(row.dipole, 'tolist') else row.dipole
                    
                    # Max force
                    if hasattr(row, 'fmax') and row.fmax is not None:
                        results['fmax'] = float(row.fmax)
                    
                    # Max stress
                    if hasattr(row, 'smax') and row.smax is not None:
                        results['smax'] = float(row.smax)
                    
                    if results:
                        entry['results'] = results
                
                if include_metadata:
                    if hasattr(row, 'key_value_pairs') and row.key_value_pairs:
                        entry['metadata'] = dict(row.key_value_pairs)
                    
                    if hasattr(row, 'calculator') and row.calculator:
                        entry['calculator'] = row.calculator
                    
                    if hasattr(row, 'ctime'):
                        entry['ctime'] = row.ctime
                    
                    if hasattr(row, 'user'):
                        entry['user'] = row.user
                
                if include_data:
                    if hasattr(row, 'data') and row.data:
                        entry['data'] = row.data
                
                atoms_list.append(entry)
                
            except KeyError:
                not_found.append(row_id)
            except Exception as e:
                return {
                    "success": False,
                    "db_path": db_path,
                    "row_id": row_id,
                    "error": f"Error retrieving row {row_id}: {str(e)}",
                    "error_type": type(e).__name__
                }
        
        # Close database connection
        try:
            if hasattr(db, '_con') and hasattr(db._con, 'close'):
                db._con.close()
        except:
            pass
        
        # Check if any entries were found
        if not atoms_list and not_found:
            return {
                "success": False,
                "db_path": db_path,
                "requested_ids": row_ids,
                "not_found": not_found,
                "error": f"Row IDs not found in database: {not_found}"
            }
        
        result = {
            "success": True,
            "count": len(atoms_list),
            "atoms": atoms_list,
            "db_path": db_path,
            "message": f"Retrieved {len(atoms_list)} structure(s) from database"
        }
        
        if not_found:
            result["not_found"] = not_found
            result["warning"] = f"Some row IDs were not found: {not_found}"
        
        return result
        
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
            "error": f"Unexpected error retrieving atoms: {str(e)}",
            "error_type": type(e).__name__
        }


def _serialize_arrays(obj):
    """Recursively convert numpy arrays to lists for JSON serialization."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: _serialize_arrays(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_serialize_arrays(item) for item in obj]
    elif isinstance(obj, (np.integer, np.floating)):
        return float(obj)
    return obj