"""
Molecular Dynamics (MD) simulation tool using matcalc MDCalc.

This tool performs MD simulations on structures using universal ML potentials
to calculate thermodynamic properties, sample phase space, and study dynamics.
"""

from typing import Any

import numpy as np
from pymatgen.core import Structure


def matcalc_calc_md(
    structure_input: str | dict[str, Any],
    calculator: str = "TensorNet-MatPES-PBE",
    ensemble: str = "nvt",
    temperature: float = 300.0,
    timestep: float = 1.0,
    steps: int = 100,
    pressure: float | None = None,
    relax_structure: bool = True,
    fmax: float = 0.1,
    optimizer: str = "FIRE",
    trajfile: str | None = None,
    logfile: str | None = None,
    loginterval: int = 1,
    taut: float | None = None,
    taup: float | None = None,
    friction: float = 0.001,
    relax_calc_kwargs: dict[str, Any] | None = None,
    **kwargs,
) -> dict[str, Any]:
    """
    Run molecular dynamics simulation using matcalc.
    
    Performs MD simulation in various ensembles (NVE, NVT, NPT, etc.) using
    universal ML potentials. Optionally relaxes the structure before MD.
    
    Args:
        structure_input: Structure as CIF string, POSCAR string, dict, or pymatgen Structure.
            Can be:
            - CIF format string (must start with 'data_' or contain '_cell_')
            - POSCAR format string
            - Dictionary with structure data
            - Pymatgen Structure object
            
        calculator: Name of the ML potential calculator to use.
            Options: "TensorNet-MatPES-PBE", "r2SCAN", "M3GNet", "CHGNet"
            Default: "TensorNet-MatPES-PBE"
            
        ensemble: MD ensemble for simulation.
            Options: "nvt" (canonical), "nve" (microcanonical), "npt" (isothermal-isobaric),
                     "nvt-nh" (Nose-Hoover), "npt-nh" (NPT Nose-Hoover), "langevin", 
                     "nvt-andersen", "nvt-berendsen", "npt-berendsen"
            Default: "nvt"
            
        temperature: Temperature in Kelvin for the simulation.
            Default: 300.0
            
        timestep: Time step for MD integration in femtoseconds (fs).
            Default: 1.0 fs
            
        steps: Number of MD steps to run.
            Default: 100
            
        pressure: Pressure in GPa for NPT ensemble. Only used if ensemble contains "npt".
            Default: None (converts to ~0 GPa internally if NPT is used)
            
        relax_structure: Whether to relax the structure before MD.
            Recommended: True (ensures structure is at equilibrium)
            Default: True
            
        fmax: Force convergence criterion for structure relaxation (eV/Angstrom).
            Only used if relax_structure=True.
            Default: 0.1
            
        optimizer: Optimizer for structure relaxation.
            Options: "FIRE", "BFGS", "LBFGS", "BFGSLineSearch"
            Default: "FIRE"
            
        trajfile: Path to save trajectory file (e.g., "trajectory.traj").
            If None, trajectory is not saved to file.
            Default: None
            
        logfile: Path to save MD log file (e.g., "md.log").
            If None, log is not saved to file.
            Default: None
            
        loginterval: Interval (in steps) for logging MD information.
            Default: 1 (log every step)
            
        taut: Time constant for Berendsen/Nose-Hoover thermostat in fs.
            If None, uses ensemble-specific defaults.
            Default: None
            
        taup: Time constant for Berendsen/Nose-Hoover barostat in fs.
            If None, uses ensemble-specific defaults.
            Default: None
            
        friction: Friction coefficient for Langevin dynamics (fs^-1).
            Default: 0.001
            
        relax_calc_kwargs: Additional keyword arguments for relaxation calculator.
            Default: None
            
        **kwargs: Additional keyword arguments for MDCalc.
            
    Returns:
        Dictionary containing:
        {
            "success": bool,
            "energy": float,  # Final energy in eV
            "structure": dict,  # Final structure as pymatgen Structure dict
            "relaxed": bool,  # Whether structure was relaxed
            
            # MD information
            "ensemble": str,
            "temperature": float,  # K
            "pressure": float | None,  # GPa
            "steps": int,
            "timestep": float,  # fs
            "total_time": float,  # Total simulation time in ps
            
            # Calculator info
            "calculator": str,
            
            # Units reference
            "units": {
                "energy": "eV",
                "temperature": "K",
                "pressure": "GPa",
                "timestep": "fs",
                "time": "ps",
                "force": "eV/Angstrom"
            }
        }
    
    Raises:
        ValueError: If structure_input cannot be parsed
        RuntimeError: If MD simulation fails
    
    Example:
        >>> result = matcalc_calc_md(
        ...     structure_input=cif_string,
        ...     calculator="M3GNet",
        ...     ensemble="nvt",
        ...     temperature=300.0,
        ...     steps=1000,
        ...     timestep=1.0
        ... )
        >>> print(f"Final energy: {result['energy']:.4f} eV")
        >>> print(f"Simulation time: {result['total_time']:.2f} ps")
    
    Notes:
        - MD simulations are computationally expensive; start with small step counts
        - Structure relaxation is recommended before MD to avoid numerical instabilities
        - Timestep should be chosen based on system dynamics (typically 0.5-2.0 fs)
        - For production runs, use larger step counts (10000+) and save trajectories
        - NPT ensemble requires pressure parameter
        - Trajectory files can be large; use loginterval > 1 for long simulations
    """
    try:
        from matcalc import MDCalc
        import matcalc as mtc
    except ImportError as err:
        return {
            "success": False,
            "error": f"Failed to import matcalc: {err}. Please install with: pip install matcalc",
        }

    # Parse structure
    try:
        structure = _parse_structure(structure_input)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse structure: {e}",
        }

    # Set appropriate backend based on calculator type
    try:
        import matgl
        # M3GNet and CHGNet models require DGL backend
        if any(model in calculator.upper() for model in ["M3GNET", "CHGNET"]):
            matgl.set_backend('DGL')
        else:
            # TensorNet and other models use PYG (default)
            matgl.set_backend('PYG')
    except Exception:
        pass  # Backend setting is optional

    # Load calculator
    try:
        calc = mtc.load_fp(calculator)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load calculator '{calculator}': {e}",
        }

    # Set up MDCalc
    try:
        md_calc = MDCalc(
            calculator=calc,
            ensemble=ensemble,
            temperature=temperature,
            timestep=timestep,
            steps=steps,
            pressure=pressure,
            relax_structure=relax_structure,
            fmax=fmax,
            optimizer=optimizer,
            trajfile=trajfile,
            logfile=logfile,
            loginterval=loginterval,
            taut=taut,
            taup=taup,
            friction=friction,
            relax_calc_kwargs=relax_calc_kwargs,
            **kwargs,
        )
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to initialize MDCalc: {e}",
        }

    # Run MD simulation
    try:
        result = md_calc.calc(structure)
    except Exception as e:
        return {
            "success": False,
            "error": f"MD simulation failed: {e}",
        }

    # Extract results
    final_energy = result.get("energy", 0.0)
    final_structure = result.get("final_structure", structure)
    
    # Calculate total simulation time in ps
    total_time_ps = (steps * timestep) / 1000.0  # Convert fs to ps

    # Return formatted result
    return {
        "success": True,
        "energy": float(final_energy),
        "structure": final_structure.as_dict() if hasattr(final_structure, 'as_dict') else final_structure,
        "relaxed": relax_structure,
        "ensemble": ensemble,
        "temperature": float(temperature),
        "pressure": float(pressure) if pressure is not None else None,
        "steps": int(steps),
        "timestep": float(timestep),
        "total_time": float(total_time_ps),
        "calculator": calculator,
        "units": {
            "energy": "eV",
            "temperature": "K",
            "pressure": "GPa",
            "timestep": "fs",
            "time": "ps",
            "force": "eV/Angstrom"
        }
    }


def _parse_structure(structure_input: str | dict[str, Any]) -> Structure:
    """
    Parse structure from various input formats.
    
    Args:
        structure_input: Structure as string (CIF/POSCAR) or dict
        
    Returns:
        Pymatgen Structure object
    """
    # If already a Structure object, return it
    if isinstance(structure_input, Structure):
        return structure_input
    
    # If dict, try to load as Structure
    if isinstance(structure_input, dict):
        try:
            return Structure.from_dict(structure_input)
        except Exception:
            raise ValueError("Invalid structure dictionary format")
    
    # If string, try to parse as CIF or POSCAR
    if isinstance(structure_input, str):
        # Try CIF first (check for common CIF patterns)
        if structure_input.strip().startswith('data_') or '_cell_' in structure_input:
            try:
                return Structure.from_str(structure_input, fmt='cif')
            except Exception:
                raise ValueError("Failed to parse structure as CIF format")
        
        # Try POSCAR format
        try:
            return Structure.from_str(structure_input, fmt='poscar')
        except Exception:
            raise ValueError("Failed to parse structure as POSCAR format")
    
    raise ValueError(f"Unsupported structure input type: {type(structure_input)}")


def _format_array(arr) -> list[float]:
    """Convert numpy array to list of floats for JSON serialization."""
    if isinstance(arr, np.ndarray):
        return arr.tolist()
    elif isinstance(arr, (list, tuple)):
        return [float(x) for x in arr]
    else:
        return [float(arr)]
