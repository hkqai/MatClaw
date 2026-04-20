"""
Quasi-Harmonic Approximation (QHA) calculation tool using matcalc QHACalc.

This tool calculates temperature-dependent thermodynamic properties including
thermal expansion, Gibbs free energy, and heat capacity using the quasi-harmonic
approximation with universal ML potentials.
"""

from typing import Any

import numpy as np
from pymatgen.core import Structure


def matcalc_calc_qha(
    structure_input: str | dict[str, Any],
    calculator: str = "TensorNet-MatPES-PBE",
    t_min: float = 0.0,
    t_max: float = 1000.0,
    t_step: float = 10.0,
    scale_factors: list[float] | None = None,
    eos: str = "vinet",
    relax_structure: bool = True,
    fmax: float = 0.1,
    optimizer: str = "FIRE",
    relax_calc_kwargs: dict[str, Any] | None = None,
    phonon_calc_kwargs: dict[str, Any] | None = None,
    **kwargs,
) -> dict[str, Any]:
    """
    Calculate quasi-harmonic approximation (QHA) thermodynamic properties using matcalc.
    
    This tool uses QHACalc from matcalc to compute temperature-dependent properties
    including thermal expansion coefficient, Gibbs free energy, bulk modulus at
    constant pressure, heat capacity at constant pressure, and Grüneisen parameter.
    
    The QHA method calculates phonon properties at different volumes (defined by
    scale_factors), then determines how thermodynamic properties vary with temperature
    by accounting for volume changes.
    
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
            
        t_min: Minimum temperature (in Kelvin).
            Default: 0.0
            
        t_max: Maximum temperature (in Kelvin).
            Default: 1000.0
            
        t_step: Temperature step (in Kelvin).
            Default: 10.0
            
        scale_factors: List of volume scaling factors for QHA calculations.
            The structure will be scaled by these factors to sample different volumes.
            Default: [0.95, 0.96, 0.97, 0.98, 0.99, 1.0, 1.01, 1.02, 1.03, 1.04, 1.05]
            
        eos: Equation of state model for fitting.
            Options: "vinet", "murnaghan", "birch_murnaghan"
            Default: "vinet"
            
        relax_structure: Whether to relax the structure before QHA calculation.
            Recommended: True (ensures structure is at equilibrium)
            Default: True
            
        fmax: Force convergence criterion for structure relaxation (eV/Angstrom).
            Only used if relax_structure=True.
            Default: 0.1
            
        optimizer: Optimizer for structure relaxation.
            Options: "FIRE", "BFGS", "LBFGS", "BFGSLineSearch"
            Default: "FIRE"
            
        relax_calc_kwargs: Additional keyword arguments for RelaxCalc.
            Default: None
            
        phonon_calc_kwargs: Additional keyword arguments for PhononCalc used within QHA.
            Example: {"supercell_matrix": [[3, 0, 0], [0, 3, 0], [0, 0, 3]]}
            Default: None
            
        **kwargs: Additional arguments passed to matcalc QHACalc.
    
    Returns:
        Dictionary containing:
        {
            "success": bool,
            
            # Temperature-dependent properties
            "temperatures": [T1, T2, ...],  # K
            "thermal_expansion_coefficients": [α1, α2, ...],  # K^-1 (volumetric)
            "gibbs_free_energies": [G1, G2, ...],  # eV
            "bulk_modulus_P": [K1, K2, ...],  # GPa (at constant pressure)
            "heat_capacity_P": [Cp1, Cp2, ...],  # J/K/mol (at constant pressure)
            "gruneisen_parameters": [γ1, γ2, ...],  # dimensionless
            
            # Volume-energy data
            "scale_factors": [s1, s2, ...],  # dimensionless
            "volumes": [V1, V2, ...],  # Angstrom^3
            "electronic_energies": [E1, E2, ...],  # eV
            
            # Structure information
            "structure": dict,  # Pymatgen Structure as dict
            "relaxed": bool,    # Whether structure was relaxed
            
            # Calculator info
            "calculator": str,
            "eos_model": str,
            
            # Units reference
            "units": {
                "temperature": "K",
                "thermal_expansion": "K^-1",
                "gibbs_free_energy": "eV",
                "bulk_modulus": "GPa",
                "heat_capacity": "J/K/mol",
                "volume": "Angstrom^3",
                "energy": "eV"
            }
        }
    
    Raises:
        ValueError: If structure_input cannot be parsed
        RuntimeError: If QHA calculation fails
    
    Example:
        >>> result = matcalc_calc_qha(
        ...     structure_input=cif_string,
        ...     calculator="M3GNet",
        ...     t_max=500.0,
        ...     scale_factors=[0.97, 0.98, 0.99, 1.0, 1.01, 1.02, 1.03]
        ... )
        >>> print(f"Thermal expansion at 300K: {result['thermal_expansion_coefficients'][30]:.2e} K^-1")
        >>> print(f"Gibbs free energy at 300K: {result['gibbs_free_energies'][30]:.4f} eV")
    
    Notes:
        - QHA is more accurate than harmonic approximation for thermal expansion
        - Requires phonon calculations at multiple volumes (computationally expensive)
        - ML potentials make QHA calculations feasible for larger systems
        - Thermal expansion coefficient is volumetric (divide by 3 for linear)
        - For highly anharmonic systems, consider Phonon3 (anharmonic phonon methods)
        - Structure relaxation is strongly recommended before QHA
    """
    try:
        from matcalc import QHACalc
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

    # Set up scale factors if not provided
    if scale_factors is None:
        scale_factors = [0.95, 0.96, 0.97, 0.98, 0.99, 1.0, 1.01, 1.02, 1.03, 1.04, 1.05]

    # Set appropriate backend based on calculator type
    try:
        import matgl
        # M3GNet and CHGNet models require DGL backend
        if any(model in calculator.upper() for model in ["M3GNET", "CHGNET"]):
            matgl.set_backend('DGL')
        else:
            # TensorNet and other models use PYG (default)
            matgl.set_backend('PYG')
    except Exception as e:
        # Backend setting is optional, continue if it fails
        pass

    # Load calculator
    try:
        calc = mtc.load_fp(calculator)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load calculator '{calculator}': {e}",
        }

    # Set up QHACalc
    try:
        qha_calc = QHACalc(
            calculator=calc,
            t_min=t_min,
            t_max=t_max,
            t_step=t_step,
            scale_factors=scale_factors,
            eos=eos,
            relax_structure=relax_structure,
            fmax=fmax,
            optimizer=optimizer,
            relax_calc_kwargs=relax_calc_kwargs,
            phonon_calc_kwargs=phonon_calc_kwargs,
            **kwargs,
        )
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to initialize QHACalc: {e}",
        }

    # Run QHA calculation
    try:
        result = qha_calc.calc(structure)
    except Exception as e:
        return {
            "success": False,
            "error": f"QHA calculation failed: {e}",
        }

    # Extract results
    temperatures = result.get("temperatures", [])
    thermal_expansion = result.get("thermal_expansion_coefficients", [])
    gibbs_energies = result.get("gibbs_free_energies", [])
    bulk_modulus = result.get("bulk_modulus_P", [])
    heat_capacity = result.get("heat_capacity_P", [])
    gruneisen = result.get("gruneisen_parameters", [])
    
    # MatCalc QHA may return one fewer property value than temperature points
    # (typically excluding the last temperature). Align arrays to match.
    if len(thermal_expansion) > 0 and len(temperatures) > len(thermal_expansion):
        temperatures = temperatures[:len(thermal_expansion)]
    
    scale_factors_result = result.get("scale_factors", [])
    volumes = result.get("volumes", [])
    electronic_energies = result.get("electronic_energies", [])
    
    # Get final structure
    final_structure = result.get("final_structure", structure)
    
    return {
        "success": True,
        "temperatures": _format_array(temperatures, decimals=2),
        "thermal_expansion_coefficients": _format_array(thermal_expansion, decimals=6),
        "gibbs_free_energies": _format_array(gibbs_energies, decimals=6),
        "bulk_modulus_P": _format_array(bulk_modulus, decimals=4),
        "heat_capacity_P": _format_array(heat_capacity, decimals=4),
        "gruneisen_parameters": _format_array(gruneisen, decimals=4),
        "scale_factors": _format_array(scale_factors_result, decimals=4),
        "volumes": _format_array(volumes, decimals=4),
        "electronic_energies": _format_array(electronic_energies, decimals=6),
        "structure": final_structure.as_dict(),
        "relaxed": relax_structure,
        "calculator": calculator,
        "eos_model": eos,
        "units": {
            "temperature": "K",
            "thermal_expansion": "K^-1",
            "gibbs_free_energy": "eV",
            "bulk_modulus": "GPa",
            "heat_capacity": "J/K/mol",
            "volume": "Angstrom^3",
            "energy": "eV",
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


def _format_array(arr: list | np.ndarray, decimals: int = 4) -> list[float]:
    """Format array values for cleaner output."""
    if arr is None or len(arr) == 0:
        return []
    return [round(float(x), decimals) for x in arr]


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
    
    result = matcalc_calc_qha(
        structure_input=si_poscar,
        calculator="M3GNet",
        t_max=500.0,
        scale_factors=[0.98, 0.99, 1.0, 1.01, 1.02],
        relax_structure=False,
    )
    
    print("Success:", result.get("success"))
    if result.get("success"):
        temps = result.get("temperatures", [])
        if len(temps) > 30:
            idx_300k = 30
            print(f"Temperature at index {idx_300k}: {temps[idx_300k]} K")
            print(f"Thermal expansion at 300K: {result['thermal_expansion_coefficients'][idx_300k]:.2e} K^-1")
            print(f"Gibbs energy at 300K: {result['gibbs_free_energies'][idx_300k]:.4f} eV")
    else:
        print("Error:", result.get("error"))
