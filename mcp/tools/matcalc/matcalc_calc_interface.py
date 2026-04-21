"""
Tool for calculating interface energies using matcalc.

Computes interface/grain boundary energy by comparing the energy of an interface
structure to the energies of the constituent bulk materials. Works for grain boundaries,
heterostructure interfaces, and other material junctions.

Use this tool to:
- Calculate grain boundary energies
- Evaluate heterostructure interface stability
- Compare different interface configurations
- Screen interface compositions for low-energy boundaries
"""

from typing import Dict, Any, Union, Annotated, Optional
from pydantic import Field
import matcalc as mtc
from pymatgen.core import Structure


def matcalc_calc_interface(
    interface_structure: Annotated[
        Union[Dict[str, Any], str],
        Field(
            description=(
                "Interface structure as a pymatgen Structure dict (from Structure.as_dict()), "
                "or a CIF/POSCAR string. This should be the combined structure with both "
                "materials at the interface."
            )
        )
    ],
    film_bulk: Annotated[
        Union[Dict[str, Any], str],
        Field(
            description=(
                "Film (top layer) bulk structure as a pymatgen Structure dict or CIF/POSCAR string. "
                "This is the bulk structure of one of the materials forming the interface, typically "
                "the film or deposited layer."
            )
        )
    ],
    substrate_bulk: Annotated[
        Union[Dict[str, Any], str],
        Field(
            description=(
                "Substrate (bottom layer) bulk structure as a pymatgen Structure dict or CIF/POSCAR string. "
                "This is the bulk structure of the other material forming the interface, typically "
                "the substrate or base material."
            )
        )
    ],
    calculator: Annotated[
        str,
        Field(
            default="CHGNet",
            description=(
                "Calculator/potential to use. Options:\n"
                "- 'CHGNet' or 'CHGNet-MatPES-PBE-2025.2.10-2.7M-PES' (default, requires DGL)\n"
                "- 'M3GNet' or 'M3GNet-MatPES-PBE-v2025.1-PES' (requires DGL)\n"
                "- 'TensorNet-MatPES-PBE-v2025.1-PES' or 'pbe' (uses PYG backend)\n"
                "- 'TensorNet-MatPES-r2SCAN-v2025.1-PES' or 'r2scan'\n"
                "Or any other matcalc-supported universal calculator."
            )
        )
    ] = "CHGNet",
    relax_bulk: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True (default), relaxes the bulk reference structures before calculating "
                "their energies. Set to False if bulk structures are already at equilibrium."
            )
        )
    ] = True,
    relax_interface: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True (default), relaxes the interface structure before energy calculation. "
                "Allows interface atoms to reach equilibrium configurations."
            )
        )
    ] = True,
    fmax: Annotated[
        float,
        Field(
            default=0.1,
            ge=0.01,
            le=1.0,
            description=(
                "Force convergence tolerance in eV/Å for structure relaxation (0.01-1.0). "
                "Lower values = more accurate but slower. Default: 0.1 eV/Å."
            )
        )
    ] = 0.1,
    optimizer: Annotated[
        str,
        Field(
            default="BFGS",
            description=(
                "Optimization algorithm for relaxation. Options:\n"
                "- 'BFGS' (default, Quasi-Newton method)\n"
                "- 'FIRE' (Fast Inertial Relaxation Engine)\n"
                "- 'LBFGS' (Limited-memory BFGS)\n"
                "- 'BFGSLineSearch' (BFGS with line search)"
            )
        )
    ] = "BFGS",
    max_steps: Annotated[
        int,
        Field(
            default=500,
            ge=10,
            le=2000,
            description=(
                "Maximum optimization steps (10-2000). Default: 500."
            )
        )
    ] = 500,
) -> Dict[str, Any]:
    """
    Calculate interface or grain boundary energy.
    
    Computes the interface energy by comparing the energy of the interface structure
    to the energies of the constituent bulk materials. The interface energy represents
    the excess energy per unit area due to the presence of the interface.
    
    Args:
        interface_structure: Combined structure with both materials at interface
        film_bulk: Bulk structure of the film/top material
        substrate_bulk: Bulk structure of the substrate/bottom material
        calculator: Force field or ML potential to use
        relax_bulk: Whether to relax bulk reference structures
        relax_interface: Whether to relax interface structure
        fmax: Force convergence tolerance in eV/Å
        optimizer: Optimization algorithm
        max_steps: Maximum optimization steps
        
    Returns:
        Dictionary containing:
        - interface_energy: Interface energy in eV/Å² (or J/m²)
        - interface_area: Interface area in Å²
        - interface_structure: Final interface structure as pymatgen dict
        - bulk_energy: Energy per atom of bulk reference
        - total_energy: Total energy of interface system
        - num_atoms: Number of atoms in interface structure
        
    Raises:
        ValueError: If structure parsing fails or calculator is invalid
        RuntimeError: If interface calculation fails
    """
    # Parse structures
    try:
        interface_struct = _parse_structure(interface_structure)
        film_struct = _parse_structure(film_bulk)
        substrate_struct = _parse_structure(substrate_bulk)
    except Exception as e:
        return {
            "error": f"Failed to parse structures: {str(e)}",
            "details": "Ensure all structures are valid Structure dicts or CIF/POSCAR strings."
        }
    
    # Set DGL backend for M3GNet/CHGNet
    _set_backend_if_needed(calculator)
    
    # Load calculator
    try:
        calc = mtc.load_fp(calculator)
    except Exception as e:
        return {
            "error": f"Failed to load calculator '{calculator}': {str(e)}",
            "details": "Check that calculator name is valid and model is available."
        }
    
    # Create InterfaceCalc
    try:
        interface_calc = mtc.InterfaceCalc(
            calculator=calc,
            relax_bulk=relax_bulk,
            relax_interface=relax_interface,
            fmax=fmax,
            optimizer=optimizer,
            max_steps=max_steps,
        )
    except Exception as e:
        return {
            "error": f"Failed to initialize InterfaceCalc: {str(e)}",
            "details": "Check optimizer and parameter values."
        }
    
    # Prepare input dict for InterfaceCalc
    input_dict = {
        "interface": interface_struct,
        "film_bulk": film_struct,
        "substrate_bulk": substrate_struct
    }
    
    # Run interface calculation
    try:
        results = interface_calc.calc(input_dict)
    except Exception as e:
        return {
            "error": f"Interface calculation failed: {str(e)}",
            "details": "Energy calculation encountered an error."
        }
    
    # Format output
    try:
        final_interface = results.get("final_interface", interface_struct)
        output = {
            "interface_energy": float(results.get("interface_energy", 0)),
            "interface_energy_units": results.get("interface_energy_units", "eV/Å²"),
            "interface_structure": final_interface.as_dict(),
            "calculator": calculator,
            "relax_bulk": relax_bulk,
            "relax_interface": relax_interface,
        }
        
        # Add optional fields if present
        if "interface_area" in results:
            output["interface_area"] = float(results["interface_area"])
            output["interface_area_units"] = "Å²"
        
        if "bulk_energy_per_atom" in results:
            output["bulk_energy_per_atom"] = float(results["bulk_energy_per_atom"])
            output["bulk_energy_units"] = "eV/atom"
        
        if "total_energy" in results:
            output["total_energy"] = float(results["total_energy"])
            output["total_energy_units"] = "eV"
        
        output["num_atoms"] = len(interface_struct)
        output["formula"] = str(interface_struct.composition.reduced_formula)
        
        # Add interpretation
        if "interface_energy" in output:
            if output["interface_energy"] < 0.1:
                output["stability"] = "Very stable interface (low energy)"
            elif output["interface_energy"] < 0.5:
                output["stability"] = "Stable interface"
            elif output["interface_energy"] < 1.0:
                output["stability"] = "Moderately stable interface"
            else:
                output["stability"] = "Less stable interface (high energy)"
        
        return output
        
    except Exception as e:
        return {
            "error": f"Failed to format results: {str(e)}",
            "details": "Interface calculation completed but result formatting failed.",
            "raw_results": {k: str(v) for k, v in results.items()}
        }


def _parse_structure(structure_input: Union[Dict[str, Any], str]) -> "Structure":
    """
    Parse structure from dict or string format.
    
    Args:
        structure_input: Structure as dict or CIF/POSCAR string
        
    Returns:
        pymatgen Structure object
        
    Raises:
        ValueError: If parsing fails
    """
    from pymatgen.core import Structure
    
    if isinstance(structure_input, dict):
        try:
            return Structure.from_dict(structure_input)
        except Exception as e:
            raise ValueError(f"Invalid Structure dict: {e}")
            
    elif isinstance(structure_input, str):
        # Try CIF first, then POSCAR
        for fmt in ['cif', 'poscar']:
            try:
                return Structure.from_str(structure_input, fmt=fmt)
            except:
                continue
        raise ValueError("Could not parse structure string as CIF or POSCAR")
        
    else:
        raise ValueError(f"structure_input must be dict or str, got {type(structure_input)}")


def _set_backend_if_needed(calculator: str) -> None:
    """
    Set DGL backend for M3GNet/CHGNet calculators.
    
    Args:
        calculator: Calculator name
    """
    # M3GNet and CHGNet require DGL backend, TensorNet uses PYG (default)
    if any(name in calculator.upper() for name in ['M3GNET', 'CHGNET']):
        try:
            import matgl
            matgl.set_backend('DGL')
        except ImportError:
            pass  # matgl may not be available, will fail later if needed
