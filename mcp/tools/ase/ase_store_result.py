"""
Tool for storing ASE calculation results to a database.
Archives successful simulation results with atoms, calculator results, and metadata.
The most frequently called tool in optimization loops to avoid recomputing results.
"""

from typing import Dict, Any, Optional, Annotated
from pydantic import Field


def ase_store_result(
    db_path: Annotated[
        str,
        Field(
            description="Path to the ASE database file (e.g., 'simulations.db', './data/results.db'). "
            "Must be an existing database or will be created if it doesn't exist."
        )
    ],
    
    atoms_dict: Annotated[
        Dict[str, Any],
        Field(
            description="Serialized ASE Atoms object as a dictionary. "
            "Obtain this by calling atoms.todict() on an Atoms object. "
            "Must contain 'numbers', 'positions', and 'cell' keys at minimum."
        )
    ],
    
    results: Annotated[
        Optional[Dict[str, Any]],
        Field(
            default=None,
            description="Calculator results to store with the structure. "
            "Common keys: 'energy' (float, eV), 'forces' (array, eV/Å), "
            "'stress' (array, eV/Å³), 'magmoms' (magnetic moments), 'charges', etc. "
            "These are automatically extracted from calculator if attached to atoms."
        )
    ] = None,
    
    key_value_pairs: Annotated[
        Optional[Dict[str, Any]],
        Field(
            default=None,
            description="Metadata to store with this entry. Examples: "
            "{'campaign_id': 'opt_2026_03', 'target_property': 'band_gap', "
            "'method': 'DFT-PBE', 'converged': True, 'doi': '10.1021/...', "
            "'tags': 'cathode,LiFePO4'}. All values must be JSON-serializable."
        )
    ] = None,
    
    unique_key: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional unique identifier for this entry. "
            "If provided and already exists in database, will update instead of creating new entry. "
            "Useful for avoiding duplicates (e.g., use formula + structure hash)."
        )
    ] = None,
    
    data: Annotated[
        Optional[Dict[str, Any]],
        Field(
            default=None,
            description="Additional arbitrary data to store (arrays, nested dicts, etc.). "
            "Stored as JSON blob. Use for large data that doesn't fit in key_value_pairs."
        )
    ] = None
) -> Dict[str, Any]:
    """
    Store an atomic structure and calculation results to an ASE database.
    
    This is the primary tool for archiving simulation results, preventing recomputation
    and enabling analysis of previous calculations. Stores structures, energies, forces,
    and arbitrary metadata in a queryable database.
    
    Returns:
        dict: Storage status and entry information including:
            - success (bool): Whether storage was successful
            - row_id (int): Unique database row ID for this entry
            - db_path (str): Database path used
            - formula (str): Chemical formula of stored structure
            - energy (float): Energy if available
            - n_atoms (int): Number of atoms
            - updated (bool): True if updated existing entry, False if new
            - message (str): Success message
            - error (str): Error message if failed
    """
    
    try:
        try:
            from ase import Atoms
            from ase.db import connect
        except ImportError:
            return {
                "success": False,
                "error": "ASE (Atomic Simulation Environment) is not installed. "
                        "Install it with: pip install ase"
            }
        
        if not isinstance(atoms_dict, dict):
            return {
                "success": False,
                "error": f"atoms_dict must be a dictionary, got {type(atoms_dict).__name__}"
            }
        
        required_keys = ['numbers']
        missing_keys = [k for k in required_keys if k not in atoms_dict]
        if missing_keys:
            return {
                "success": False,
                "error": f"atoms_dict missing required keys: {missing_keys}. "
                        "Ensure you used atoms.todict() to serialize the Atoms object."
            }
        
        # Reconstruct Atoms object from dictionary
        try:
            atoms = Atoms.fromdict(atoms_dict)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to reconstruct Atoms object from dictionary: {str(e)}. "
                        "Ensure atoms_dict was created with atoms.todict()."
            }
        
        # Attach calculator results to atoms if provided
        if results:
            try:
                # Create a SinglePointCalculator with the results
                from ase.calculators.singlepoint import SinglePointCalculator
                
                # Extract relevant properties
                calc_kwargs = {}
                if 'energy' in results:
                    calc_kwargs['energy'] = results['energy']
                if 'forces' in results:
                    calc_kwargs['forces'] = results['forces']
                if 'stress' in results:
                    calc_kwargs['stress'] = results['stress']
                if 'magmoms' in results:
                    calc_kwargs['magmoms'] = results['magmoms']
                if 'charges' in results:
                    calc_kwargs['charges'] = results['charges']
                if 'dipole' in results:
                    calc_kwargs['dipole'] = results['dipole']
                
                # Attach calculator to atoms
                calc = SinglePointCalculator(atoms, **calc_kwargs)
                atoms.calc = calc
                
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to attach calculator results to atoms: {str(e)}"
                }
        
        # Connect to database
        try:
            db = connect(db_path)
        except Exception as e:
            return {
                "success": False,
                "db_path": db_path,
                "error": f"Failed to connect to database: {str(e)}. "
                        "Use ase_connect_or_create_db tool to initialize the database first."
            }
        
        write_kwargs = {}
        if key_value_pairs:
            for key, value in key_value_pairs.items():
                if not key.replace('_', '').isalnum():
                    return {
                        "success": False,
                        "error": f"Invalid metadata key '{key}'. "
                                "Keys must be alphanumeric with underscores only."
                    }
                write_kwargs[key] = value
        
        if data:
            write_kwargs['data'] = data
        
        # Check for existing entry with unique_key
        updated = False
        existing_id = None
        if unique_key:
            try:
                existing = list(db.select(unique_key=unique_key))
                if existing:
                    existing_id = existing[0].id
                    updated = True
            except:
                pass
        
        # Store unique_key as a regular key-value pair
        if unique_key:
            write_kwargs['unique_key'] = unique_key
        
        # Write to database
        try:
            if updated and existing_id:
                db.update(existing_id, atoms, **write_kwargs)
                row_id = existing_id
            else:
                row_id = db.write(atoms, **write_kwargs)
        except Exception as e:
            return {
                "success": False,
                "db_path": db_path,
                "error": f"Failed to write to database: {str(e)}"
            }
        
        # Get stored entry information
        try:
            formula = atoms.get_chemical_formula()
            n_atoms = len(atoms)
            
            energy = None
            if atoms.calc is not None:
                try:
                    energy = atoms.get_potential_energy()
                except:
                    pass
            
        except Exception as e:
            formula = "unknown"
            n_atoms = 0
            energy = None
        
        # Close database connection
        try:
            if hasattr(db, '_con') and hasattr(db._con, 'close'):
                db._con.close()
        except:
            pass
        
        # Prepare success response
        result = {
            "success": True,
            "row_id": row_id,
            "db_path": db_path,
            "formula": formula,
            "n_atoms": n_atoms,
            "updated": updated,
            "message": f"{'Updated' if updated else 'Stored'} {formula} "
                      f"({n_atoms} atoms) in database with ID {row_id}"
        }
        
        if energy is not None:
            result["energy"] = energy
        
        if unique_key:
            result["unique_key"] = unique_key
        
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
            "error": f"Unexpected error storing result: {str(e)}",
            "error_type": type(e).__name__
        }
