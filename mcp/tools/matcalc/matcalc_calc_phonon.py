"""
Phonon calculation tool using matcalc PhononCalc.

This tool calculates phonon properties and thermodynamic quantities using 
universal ML potentials (e.g., TensorNet-MatPES-PBE, M3GNet, CHGNet).
"""

from typing import Any

import numpy as np
from pymatgen.core import Structure


def matcalc_calc_phonon(
    structure_input: str | dict[str, Any],
    calculator: str = "TensorNet-MatPES-PBE",
    atom_disp: float = 0.015,
    supercell_matrix: list[list[int]] | None = None,
    t_min: float = 0.0,
    t_max: float = 1000.0,
    t_step: float = 10.0,
    relax_structure: bool = True,
    fmax: float = 0.1,
    **kwargs,
) -> dict[str, Any]:
    """
    Calculate phonon properties and thermodynamic quantities using matcalc.
    
    This tool uses PhononCalc from matcalc to compute phonon dispersion,
    density of states, and temperature-dependent thermodynamic properties
    (free energy, entropy, heat capacity) using universal ML potentials.
    
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
            
        atom_disp: Atomic displacement distance for calculating force constants (in Angstroms).
            Smaller values increase accuracy but may be numerically less stable.
            Default: 0.015
            
        supercell_matrix: Supercell matrix for phonon calculations.
            Larger supercells give more accurate phonon results but are more expensive.
            Can be:
            - List of 3 integers: [a, b, c] for diagonal supercell
            - 3x3 matrix: [[a1,a2,a3], [b1,b2,b3], [c1,c2,c3]]
            Default: [[2, 0, 0], [0, 2, 0], [0, 0, 2]] (2×2×2 supercell)
            
        t_min: Minimum temperature for thermodynamic properties (in Kelvin).
            Default: 0.0
            
        t_max: Maximum temperature for thermodynamic properties (in Kelvin).
            Default: 1000.0
            
        t_step: Temperature step for thermodynamic properties (in Kelvin).
            Default: 10.0
            
        relax_structure: Whether to relax the structure before phonon calculation.
            Recommended: True (ensuring structure is at equilibrium improves accuracy)
            Default: True
            
        fmax: Force convergence criterion for structure relaxation (eV/Angstrom).
            Only used if relax_structure=True.
            Default: 0.1
            
        **kwargs: Additional arguments passed to matcalc PhononCalc or RelaxCalc.
    
    Returns:
        Dictionary containing:
        {
            "success": bool,
            
            # Thermal properties
            "thermal_properties": {
                "temperatures": [T1, T2, ...],  # K
                "free_energy": [F1, F2, ...],   # kJ/mol
                "entropy": [S1, S2, ...],        # J/K/mol
                "heat_capacity": [Cv1, Cv2, ...] # J/K/mol
            },
            
            # Phonon stability analysis
            "stability": {
                "is_stable": bool,  # True if no imaginary modes
                "num_imaginary_modes": int,
                "max_imaginary_frequency": float | None,  # THz
            },
            
            # Key phonon metrics
            "debye_temperature": float,  # K (from Debye model fit)
            
            # Structure information
            "structure": dict,  # Pymatgen Structure as dict
            "relaxed": bool,    # Whether structure was relaxed
            
            # Calculator info
            "calculator": str,
            
            # Units reference
            "units": {
                "temperature": "K",
                "free_energy": "kJ/mol",
                "entropy": "J/K/mol",
                "heat_capacity": "J/K/mol",
                "frequency": "THz",
                "debye_temperature": "K"
            }
        }
    
    Raises:
        ValueError: If structure_input cannot be parsed
        RuntimeError: If phonon calculation fails
    
    Example:
        >>> result = matcalc_calc_phonon(
        ...     structure_input=cif_string,
        ...     calculator="M3GNet",
        ...     supercell_matrix=[3, 3, 3],
        ...     t_max=500.0
        ... )
        >>> print(f"Debye temperature: {result['debye_temperature']:.1f} K")
        >>> print(f"Stable: {result['stability']['is_stable']}")
    
    Notes:
        - Phonon calculations require larger supercells for accurate results
        - ML potentials are fast but less accurate than DFT
        - Imaginary frequencies indicate structural instability
        - Thermodynamic properties are calculated from phonon DOS using harmonic approximation
        - For very accurate results, consider using DFT-based phonon calculations
        - Structure relaxation is recommended before phonon calculation
    """
    try:
        from matcalc import PhononCalc
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

    # Set up supercell matrix
    if supercell_matrix is None:
        supercell_matrix = [[2, 0, 0], [0, 2, 0], [0, 0, 2]]
    elif isinstance(supercell_matrix, list) and len(supercell_matrix) == 3 and isinstance(supercell_matrix[0], (int, float)):
        # Handle [a, b, c] format
        a, b, c = supercell_matrix
        supercell_matrix = [[a, 0, 0], [0, b, 0], [0, 0, c]]

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

    # Set up PhononCalc
    try:
        phonon_calc = PhononCalc(
            calculator=calc,
            atom_disp=atom_disp,
            supercell_matrix=supercell_matrix,
            t_min=t_min,
            t_max=t_max,
            t_step=t_step,
            relax_structure=relax_structure,
            fmax=fmax,
            **kwargs,
        )
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to initialize PhononCalc: {e}",
        }

    # Run phonon calculation
    try:
        result = phonon_calc.calc(structure)
    except Exception as e:
        return {
            "success": False,
            "error": f"Phonon calculation failed: {e}",
        }

    # Extract phonopy object and thermal properties
    phonon = result.get("phonon")
    thermal_props = result.get("thermal_properties", {})
    
    if phonon is None:
        return {
            "success": False,
            "error": "Phonon calculation did not return a phonopy object",
        }

    # Analyze phonon stability (check for imaginary modes)
    stability_info = _analyze_phonon_stability(phonon)
    
    # Calculate Debye temperature
    debye_temp = _calculate_debye_temperature(phonon)
    
    # Format thermal properties
    formatted_thermal = _format_thermal_properties(thermal_props)
    
    # Get final structure
    final_structure = result.get("final_structure", structure)
    
    return {
        "success": True,
        "thermal_properties": formatted_thermal,
        "stability": stability_info,
        "debye_temperature": debye_temp,
        "structure": final_structure.as_dict(),
        "relaxed": relax_structure,
        "calculator": calculator,
        "units": {
            "temperature": "K",
            "free_energy": "kJ/mol",
            "entropy": "J/K/mol",
            "heat_capacity": "J/K/mol",
            "frequency": "THz",
            "debye_temperature": "K",
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


def _analyze_phonon_stability(phonon) -> dict[str, Any]:
    """
    Analyze phonon for imaginary modes (negative frequencies).
    
    Imaginary phonon modes indicate structural instability.
    """
    try:
        # Get mesh frequencies
        mesh_dict = phonon.get_mesh_dict()
        frequencies = mesh_dict.get("frequencies")  # Shape: (num_qpoints, num_branches)
        
        if frequencies is None:
            return {
                "is_stable": None,
                "num_imaginary_modes": None,
                "max_imaginary_frequency": None,
                "note": "Could not extract frequencies from phonopy mesh"
            }
        
        frequencies = np.array(frequencies)  # THz
        
        # Negative frequencies indicate imaginary modes
        # Use small tolerance to avoid counting numerical noise
        tolerance = 0.1  # THz
        imaginary_freqs = frequencies[frequencies < -tolerance]
        
        num_imaginary = len(imaginary_freqs)
        max_imaginary = float(imaginary_freqs.min()) if num_imaginary > 0 else None
        
        return {
            "is_stable": num_imaginary == 0,
            "num_imaginary_modes": num_imaginary,
            "max_imaginary_frequency": max_imaginary,
        }
        
    except Exception as e:
        return {
            "is_stable": None,
            "num_imaginary_modes": None,
            "max_imaginary_frequency": None,
            "note": f"Failed to analyze stability: {e}"
        }


def _calculate_debye_temperature(phonon) -> float:
    """
    Calculate Debye temperature from phonon DOS.
    
    The Debye temperature is a characteristic temperature that represents
    the maximum phonon frequency in a simplified model.
    """
    try:
        # Get total DOS
        total_dos = phonon.get_total_dos()
        
        if total_dos is None:
            return None
        
        # Debye temperature can be estimated from phonopy
        # θ_D = ħω_D / k_B where ω_D is Debye frequency
        # Phonopy calculates this as part of thermal properties
        
        # Get thermal properties at lowest temperature
        thermal_props = phonon.get_thermal_properties_dict()
        
        # Alternatively, estimate from average frequency
        # For now, we'll use a simple approximation based on max frequency
        mesh_dict = phonon.get_mesh_dict()
        frequencies = np.array(mesh_dict.get("frequencies", []))  # THz
        
        if len(frequencies) == 0:
            return None
        
        # Remove imaginary (negative) frequencies
        real_freqs = frequencies[frequencies > 0]
        
        if len(real_freqs) == 0:
            return None
        
        # Debye cutoff frequency (use 90th percentile as approximation)
        freq_debye = np.percentile(real_freqs, 90)  # THz
        
        # Convert to Debye temperature
        # θ_D = (h * ν_D) / k_B
        # where h = 6.62607015e-34 J·s (Planck constant)
        #       k_B = 1.380649e-23 J/K (Boltzmann constant)
        #       ν_D in Hz
        
        h = 6.62607015e-34  # J·s
        k_B = 1.380649e-23  # J/K
        freq_debye_hz = freq_debye * 1e12  # THz to Hz
        
        debye_temp = (h * freq_debye_hz) / k_B  # K
        
        return round(float(debye_temp), 1)
        
    except Exception as e:
        return None


def _format_thermal_properties(thermal_props: dict[str, Any]) -> dict[str, Any]:
    """
    Format thermal properties for cleaner output.
    
    Rounds values and ensures consistent types.
    """
    formatted = {}
    
    if "temperatures" in thermal_props:
        formatted["temperatures"] = [round(float(t), 2) for t in thermal_props["temperatures"]]
    
    if "free_energy" in thermal_props:
        formatted["free_energy"] = [round(float(f), 4) for f in thermal_props["free_energy"]]
    
    if "entropy" in thermal_props:
        formatted["entropy"] = [round(float(s), 4) for s in thermal_props["entropy"]]
    
    if "heat_capacity" in thermal_props:
        formatted["heat_capacity"] = [round(float(cv), 4) for cv in thermal_props["heat_capacity"]]
    
    return formatted


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
    
    result = matcalc_calc_phonon(
        structure_input=si_poscar,
        calculator="M3GNet",
        supercell_matrix=[2, 2, 2],
        t_max=500.0,
        relax_structure=False,
    )
    
    print("Success:", result.get("success"))
    if result.get("success"):
        print(f"Debye temperature: {result.get('debye_temperature')} K")
        print(f"Stable: {result['stability']['is_stable']}")
        print(f"Number of temperatures: {len(result['thermal_properties']['temperatures'])}")
    else:
        print("Error:", result.get("error"))
