"""
Tool for calculating surface energies using matcalc.

Computes surface energy for crystal surfaces by comparing slab and bulk
energies. Can automatically generate slabs from bulk structures with specified
Miller indices, or accept pre-generated slab structures.

Use this tool to:
- Calculate surface energy for specific Miller indices
- Compare surface stability across different facets
- Estimate surface formation costs
- Screen materials for low-energy surfaces
"""

from typing import Dict, Any, Optional, Union, Annotated, Tuple
from pydantic import Field


def matcalc_calc_surface(
    structure_input: Annotated[
        Union[Dict[str, Any], str],
        Field(
            description=(
                "Bulk crystal structure as a pymatgen Structure dict (from Structure.as_dict()), "
                "or a CIF/POSCAR string. The tool will generate a slab from this bulk structure "
                "using the specified Miller indices. Can be output from matgl_relax_structure "
                "or any pymatgen tool."
            )
        )
    ],
    miller_index: Annotated[
        Tuple[int, int, int],
        Field(
            description=(
                "Miller indices (h,k,l) specifying the surface plane to generate. "
                "Common surfaces: (1,0,0), (1,1,0), (1,1,1). Example: (1,1,1) for "
                "the 111 surface of FCC crystals."
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
    min_slab_size: Annotated[
        float,
        Field(
            default=10.0,
            ge=5.0,
            le=30.0,
            description=(
                "Minimum thickness of the slab in Angstroms (5-30 Å). "
                "Larger slabs are more accurate but computationally expensive. "
                "Default: 10.0 Å."
            )
        )
    ] = 10.0,
    min_vacuum_size: Annotated[
        float,
        Field(
            default=10.0,
            ge=5.0,
            le=30.0,
            description=(
                "Minimum vacuum gap thickness in Angstroms (5-30 Å). "
                "Ensures surfaces don't interact across periodic boundaries. "
                "Default: 10.0 Å."
            )
        )
    ] = 10.0,
    relax_bulk: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, relaxes the bulk structure before calculating bulk energy. "
                "Set to False if bulk structure is already at equilibrium. "
                "Default: False."
            )
        )
    ] = False,
    relax_slab: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True (default), relaxes the slab structure before energy calculation. "
                "Allows surface atoms to reconstruct to their equilibrium positions."
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
            default="FIRE",
            description=(
                "Optimization algorithm for relaxation. Options:\n"
                "- 'FIRE' (default, Fast Inertial Relaxation Engine)\n"
                "- 'BFGS' (Quasi-Newton method)\n"
                "- 'LBFGS' (Limited-memory BFGS)\n"
                "- 'BFGSLineSearch' (BFGS with line search)"
            )
        )
    ] = "FIRE",
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
    Calculate surface energy for a specified crystallographic plane.
    
    Generates a slab from the bulk structure, computes energies for both bulk
    and slab configurations, and returns the surface energy in eV/Å².
    
    Args:
        structure_input: Bulk crystal structure (dict or CIF/POSCAR string)
        miller_index: Miller indices (h,k,l) for surface plane
        calculator: Force field or ML potential to use
        min_slab_size: Minimum slab thickness in Angstroms
        min_vacuum_size: Minimum vacuum gap in Angstroms
        relax_bulk: Whether to relax bulk structure
        relax_slab: Whether to relax slab structure
        fmax: Force convergence tolerance in eV/Å
        optimizer: Optimization algorithm
        max_steps: Maximum optimization steps
        
    Returns:
        Dictionary containing:
        - surface_energy: Surface energy in eV/Å²
        - bulk_energy_per_atom: Bulk energy per atom in eV
        - slab_energy: Total slab energy in eV
        - slab_structure: Pymatgen Structure dict of the slab
        - bulk_structure: Pymatgen Structure dict of the bulk
        - miller_index: Miller indices used
        - slab_formula: Chemical formula of slab
        - num_slab_atoms: Number of atoms in slab
        
    Raises:
        ValueError: If structure parsing fails or calculator is invalid
        RuntimeError: If surface calculation fails
    """
    import matcalc as mtc
    from pymatgen.core import Structure
    from pymatgen.core.surface import SlabGenerator
    
    # Parse structure
    try:
        bulk_structure = _parse_structure(structure_input)
    except Exception as e:
        return {
            "error": f"Failed to parse structure: {str(e)}",
            "details": "Ensure structure_input is a valid Structure dict or CIF/POSCAR string."
        }
    
    # Generate slab from bulk
    try:
        slabgen = SlabGenerator(
            initial_structure=bulk_structure,
            miller_index=miller_index,
            min_slab_size=min_slab_size,
            min_vacuum_size=min_vacuum_size,
            center_slab=True,
        )
        slab = slabgen.get_slab()
    except Exception as e:
        return {
            "error": f"Failed to generate slab: {str(e)}",
            "details": f"Could not create slab with Miller index {miller_index}.",
            "miller_index": miller_index
        }
    
    # Set appropriate backend based on calculator type
    try:
        import matgl
        # M3GNet and CHGNet models require DGL backend
        if any(name in calculator.upper() for name in ['M3GNET', 'CHGNET']):
            matgl.set_backend('DGL')
        else:
            matgl.set_backend('PYG')
    except Exception:
        pass
    
    # Load calculator
    try:
        calc = mtc.load_fp(calculator)
    except Exception as e:
        return {
            "error": f"Failed to load calculator '{calculator}': {str(e)}",
            "details": "Check that calculator name is valid and model is available."
        }
    
    # Create SurfaceCalc
    try:
        surface_calc = mtc.SurfaceCalc(
            calculator=calc,
            relax_bulk=relax_bulk,
            relax_slab=relax_slab,
            fmax=fmax,
            optimizer=optimizer,
            max_steps=max_steps,
        )
    except Exception as e:
        return {
            "error": f"Failed to initialize SurfaceCalc: {str(e)}",
            "details": "Check optimizer and parameter values."
        }
    
    # Run surface calculation
    try:
        # SurfaceCalc requires dict with both slab and bulk
        surface_input = {
            'slab': slab,
            'bulk': bulk_structure
        }
        results = surface_calc.calc(surface_input)
    except Exception as e:
        return {
            "error": f"Surface calculation failed: {str(e)}",
            "details": "Energy calculation encountered an error.",
            "miller_index": miller_index
        }
    
    # Format output
    try:
        output = {
            "surface_energy": float(results["surface_energy"]),
            "surface_energy_units": "eV/Å²",
            "bulk_energy_per_atom": float(results["bulk_energy_per_atom"]),
            "bulk_energy_units": "eV/atom",
            "slab_energy": float(results["slab_energy"]),
            "slab_energy_units": "eV",
            "slab_structure": results["final_slab"].as_dict(),
            "bulk_structure": results["final_bulk"].as_dict(),
            "miller_index": list(miller_index),
            "slab_formula": str(slab.composition.reduced_formula),
            "num_slab_atoms": len(slab),
            "calculator": calculator,
            "min_slab_size": min_slab_size,
            "min_vacuum_size": min_vacuum_size,
            "relax_bulk": relax_bulk,
            "relax_slab": relax_slab,
        }
        
        return output
        
    except Exception as e:
        return {
            "error": f"Failed to format results: {str(e)}",
            "details": "Surface calculation completed but result formatting failed."
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

