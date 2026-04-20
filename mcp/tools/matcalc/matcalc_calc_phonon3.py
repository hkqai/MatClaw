"""
Thermal conductivity calculation tool using matcalc Phonon3Calc.

This tool calculates lattice thermal conductivity using third-order force constants
and the Boltzmann transport equation (BTE) within the relaxation time approximation (RTA).
Uses universal ML potentials (e.g., TensorNet-MatPES-PBE, M3GNet, CHGNet).
"""

from typing import Any
import numpy as np
from pymatgen.core import Structure


def matcalc_calc_phonon3(
    structure_input: str | dict[str, Any],
    calculator: str = "TensorNet-MatPES-PBE",
    fc2_supercell: list[list[int]] | None = None,
    fc3_supercell: list[list[int]] | None = None,
    mesh_numbers: list[int] | None = None,
    t_min: float = 0.0,
    t_max: float = 1000.0,
    t_step: float = 10.0,
    relax_structure: bool = True,
    fmax: float = 0.1,
    **kwargs,
) -> dict[str, Any]:
    """
    Calculate lattice thermal conductivity using third-order force constants.
    
    This tool uses Phonon3Calc from matcalc to compute thermal conductivity via
    the Boltzmann transport equation within the relaxation time approximation.
    Thermal conductivity arises from anharmonic phonon-phonon scattering captured
    by third-order force constants.
    
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
            
        fc2_supercell: Supercell matrix for second-order force constants (harmonic).
            Larger supercells give more accurate phonon properties.
            Can be:
            - List of 3 integers: [a, b, c] for diagonal supercell
            - 3x3 matrix: [[a1,a2,a3], [b1,b2,b3], [c1,c2,c3]]
            Default: [[2, 0, 0], [0, 2, 0], [0, 0, 2]] (2×2×2 supercell)
            
        fc3_supercell: Supercell matrix for third-order force constants (anharmonic).
            Should typically match or exceed fc2_supercell for consistency.
            Same format as fc2_supercell.
            Default: [[2, 0, 0], [0, 2, 0], [0, 0, 2]] (2×2×2 supercell)
            
        mesh_numbers: q-point mesh for thermal conductivity integration [nx, ny, nz].
            Denser mesh = more accurate but more expensive.
            Default: [20, 20, 20]
            
        t_min: Minimum temperature for thermal conductivity calculation (Kelvin).
            Default: 0.0
            
        t_max: Maximum temperature for thermal conductivity calculation (Kelvin).
            Default: 1000.0
            
        t_step: Temperature step (Kelvin).
            Default: 10.0
            
        relax_structure: Whether to relax the structure before calculation.
            Recommended: True (equilibrium structure needed for accurate force constants)
            Default: True
            
        fmax: Force convergence criterion for structure relaxation (eV/Angstrom).
            Only used if relax_structure=True.
            Default: 0.1
            
        **kwargs: Additional arguments:
            - disp_kwargs: dict for phonon3.generate_displacements()
            - thermal_conductivity_kwargs: dict for phonon3.run_thermal_conductivity()
            - optimizer: Relaxation optimizer (default: "FIRE")
            - write_phonon3: Path to save phono3py object
            - write_kappa: Whether to write kappa files
    
    Returns:
        Dictionary containing:
        {
            "success": bool,
            
            # Thermal conductivity results
            "thermal_conductivity": [...],  # W/m·K at each temperature (averaged over 3 directions)
            "temperatures": [...],          # K
            
            # Structure information
            "structure": dict,              # Input structure as pymatgen dict
            "relaxed": bool,                # Whether structure was relaxed
            
            # Calculator info
            "calculator": str,
            
            # Calculation parameters
            "parameters": {
                "fc2_supercell": list,
                "fc3_supercell": list,
                "mesh_numbers": list,
                ...
            },
            
            # Units reference
            "units": {
                "temperature": "K",
                "thermal_conductivity": "W/m·K"
            }
        }
    
    Raises:
        ValueError: If structure_input cannot be parsed
        RuntimeError: If phonon3 calculation fails
    
    Example:
        >>> result = matcalc_calc_phonon3(
        ...     structure_input=cif_string,
        ...     calculator="M3GNet",
        ...     fc3_supercell=[3, 3, 3],
        ...     mesh_numbers=[30, 30, 30],
        ...     t_max=500.0
        ... )
        >>> print(f"Thermal conductivity at 300K: {result['thermal_conductivity'][30]:.2f} W/m·K")
    
    Notes:
        - Thermal conductivity calculations are expensive (many force calculations required)
        - Larger supercells and denser meshes improve accuracy but increase cost
        - ML potentials are fast but less accurate than DFT
        - Structure must be at equilibrium for meaningful results
        - Thermal conductivity is averaged over x, y, z directions
        - Uses relaxation time approximation (RTA) - simplified but fast
        - For very accurate results, consider using DFT-based phono3py calculations
    """
    try:
        from matcalc import Phonon3Calc
        import matcalc as mtc
    except ImportError as err:
        return {
            "success": False,
            "error": f"Failed to import matcalc: {err}. Please install with: pip install matcalc",
        }
    
    # Workaround for phono3py 3.30.1+ compatibility
    # matcalc tries to access kappa_TOT_RTA but phono3py 3.30.1 uses just 'kappa'
    try:
        from phono3py.conductivity.rta_init import RTACalculator
        if not hasattr(RTACalculator, 'kappa_TOT_RTA'):
            # Add compatibility property
            @property
            def kappa_TOT_RTA(self):
                """Compatibility property for older matcalc versions."""
                return self.kappa
            RTACalculator.kappa_TOT_RTA = kappa_TOT_RTA
    except Exception:
        # If monkey-patch fails, continue anyway - might not be needed
        pass

    # Parse structure
    try:
        structure = _parse_structure(structure_input)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse structure: {e}",
        }

    # Set up supercell matrices
    if fc2_supercell is None:
        fc2_supercell = [[2, 0, 0], [0, 2, 0], [0, 0, 2]]
    elif isinstance(fc2_supercell, list) and len(fc2_supercell) == 3 and isinstance(fc2_supercell[0], (int, float)):
        # Handle [a, b, c] format
        a, b, c = fc2_supercell
        fc2_supercell = [[a, 0, 0], [0, b, 0], [0, 0, c]]
    
    if fc3_supercell is None:
        fc3_supercell = [[2, 0, 0], [0, 2, 0], [0, 0, 2]]
    elif isinstance(fc3_supercell, list) and len(fc3_supercell) == 3 and isinstance(fc3_supercell[0], (int, float)):
        # Handle [a, b, c] format
        a, b, c = fc3_supercell
        fc3_supercell = [[a, 0, 0], [0, b, 0], [0, 0, c]]
    
    if mesh_numbers is None:
        mesh_numbers = [20, 20, 20]

    # Load calculator
    try:
        calc = mtc.load_fp(calculator)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load calculator '{calculator}': {e}",
        }

    # Extract optional kwargs
    disp_kwargs = kwargs.pop("disp_kwargs", {})
    thermal_conductivity_kwargs = kwargs.pop("thermal_conductivity_kwargs", {})
    optimizer = kwargs.pop("optimizer", "FIRE")
    write_phonon3 = kwargs.pop("write_phonon3", False)
    write_kappa = kwargs.pop("write_kappa", False)
    relax_calc_kwargs = kwargs.pop("relax_calc_kwargs", None)

    # Set up Phonon3Calc
    try:
        phonon3_calc = Phonon3Calc(
            calculator=calc,
            fc2_supercell=fc2_supercell,
            fc3_supercell=fc3_supercell,
            mesh_numbers=mesh_numbers,
            t_min=t_min,
            t_max=t_max,
            t_step=t_step,
            relax_structure=relax_structure,
            fmax=fmax,
            optimizer=optimizer,
            disp_kwargs=disp_kwargs,
            thermal_conductivity_kwargs=thermal_conductivity_kwargs,
            write_phonon3=write_phonon3,
            write_kappa=write_kappa,
            relax_calc_kwargs=relax_calc_kwargs,
        )
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to initialize Phonon3Calc: {e}",
        }

    # Run thermal conductivity calculation
    try:
        result = phonon3_calc.calc(structure)
    except Exception as e:
        return {
            "success": False,
            "error": f"Phonon3 calculation failed: {e}",
        }

    # Extract results
    temperatures = result.get("temperatures")
    kappa = result.get("thermal_conductivity")
    
    if temperatures is None or kappa is None:
        return {
            "success": False,
            "error": "Phonon3 calculation did not return thermal conductivity data",
        }

    # Format thermal conductivity
    kappa_formatted = _format_thermal_conductivity(kappa, temperatures)
    
    # Get final structure
    final_structure = result.get("final_structure", structure)
    
    return {
        "success": True,
        "thermal_conductivity": kappa_formatted["kappa"],
        "temperatures": kappa_formatted["temperatures"],
        "structure": final_structure.as_dict(),
        "relaxed": relax_structure,
        "calculator": calculator,
        "parameters": {
            "fc2_supercell": fc2_supercell,
            "fc3_supercell": fc3_supercell,
            "mesh_numbers": list(mesh_numbers),
            "t_min": t_min,
            "t_max": t_max,
            "t_step": t_step,
            "fmax": fmax,
        },
        "units": {
            "temperature": "K",
            "thermal_conductivity": "W/m·K",
        },
    }


def _parse_structure(structure_input: str | dict[str, Any] | Structure) -> Structure:
    """Parse structure from various input formats."""
    if isinstance(structure_input, Structure):
        return structure_input
    
    if isinstance(structure_input, dict):
        try:
            return Structure.from_dict(structure_input)
        except Exception as e:
            raise ValueError(f"Could not parse structure from dict: {e}")
    
    if isinstance(structure_input, str):
        structure_input = structure_input.strip()
        
        # Try CIF format
        if "data_" in structure_input or "_cell_" in structure_input.lower():
            try:
                return Structure.from_str(structure_input, fmt="cif")
            except Exception as e:
                raise ValueError(f"Could not parse CIF format: {e}")
        
        # Try POSCAR format
        try:
            return Structure.from_str(structure_input, fmt="poscar")
        except Exception as e:
            raise ValueError(f"Could not parse POSCAR format: {e}")
    
    raise ValueError(f"Unsupported structure input type: {type(structure_input)}")


def _format_thermal_conductivity(kappa: np.ndarray, temperatures: np.ndarray) -> dict[str, Any]:
    """
    Format thermal conductivity for cleaner output.
    
    Handles NaN values and ensures consistent types.
    """
    # Convert to lists and round values
    temps = [round(float(t), 2) for t in temperatures]
    
    # Handle scalar or array kappa
    if np.isscalar(kappa) or kappa.size == 1:
        # Single value
        k_val = float(kappa)
        kappa_list = [round(k_val, 4) if not np.isnan(k_val) else None]
    else:
        # Array of values
        kappa_list = []
        for k in kappa.flat:
            k_float = float(k)
            kappa_list.append(round(k_float, 4) if not np.isnan(k_float) else None)
    
    return {
        "temperatures": temps,
        "kappa": kappa_list,
    }


# For testing
if __name__ == "__main__":
    # Simple test with Si structure
    si_poscar = """Si2
1.0
3.348920 0.000000 1.933487
1.116307 3.157372 1.933487
0.000000 0.000000 3.866975
Si
2
direct
0.875000 0.875000 0.875000 Si
0.125000 0.125000 0.125000 Si"""
    
    result = matcalc_calc_phonon3(
        structure_input=si_poscar,
        calculator="M3GNet",
        fc2_supercell=[2, 2, 2],
        fc3_supercell=[2, 2, 2],
        mesh_numbers=[10, 10, 10],  # Small mesh for testing
        t_max=300.0,
        t_step=100.0,
        relax_structure=False,
    )
    
    print("Success:", result.get("success"))
    if result.get("success"):
        print(f"Number of temperatures: {len(result.get('temperatures', []))}")
        kappa = result.get("thermal_conductivity", [])
        temps = result.get("temperatures", [])
        if len(kappa) > 0 and len(temps) > 0:
            for t, k in zip(temps, kappa):
                if k is not None:
                    print(f"  T = {t} K: κ = {k} W/m·K")
    else:
        print("Error:", result.get("error"))
