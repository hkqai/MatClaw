"""
Tool for calculating adsorption energies using matcalc.

Computes adsorption energy by comparing the energy of an adsorbate-slab system
to the clean slab and isolated adsorbate. Can automatically place adsorbates on
slabs at common adsorption sites (ontop, bridge, hollow).

Use this tool to:
- Calculate adsorption energy for molecules on surfaces
- Screen different adsorbates on a catalyst surface
- Find optimal adsorption sites
- Compare adsorption strength across different surfaces
"""

from typing import Dict, Any, Optional, Union, Annotated, Tuple, List
from pydantic import Field


def matcalc_calc_adsorption(
    slab_structure: Annotated[
        Union[Dict[str, Any], str],
        Field(
            description=(
                "Slab structure as a pymatgen Structure dict (from Structure.as_dict()), "
                "or a CIF/POSCAR string. Should already be a slab with vacuum, or use "
                "matcalc_calc_surface to generate one from bulk. The adsorbate will be "
                "placed on this slab surface."
            )
        )
    ],
    adsorbate: Annotated[
        Union[str, List[float], Dict[str, Any]],
        Field(
            description=(
                "Adsorbate to place on the slab. Can be:\n"
                "- String: Molecular formula like 'CO', 'H2O', 'CH4', 'O', 'H' (will use pymatgen to build)\n"
                "- List of floats [x, y, z]: Single atom position (will place at this height above surface)\n"
                "- Dict: pymatgen Molecule.as_dict() for complex molecules"
            )
        )
    ],
    adsorption_site: Annotated[
        str,
        Field(
            default="ontop",
            description=(
                "Type of adsorption site to use. Options:\n"
                "- 'ontop': Directly above a surface atom\n"
                "- 'bridge': Between two surface atoms\n"
                "- 'hollow': In the center of 3+ surface atoms\n"
                "- 'all': Try all sites and return best (lowest energy)"
            )
        )
    ] = "ontop",
    distance: Annotated[
        float,
        Field(
            default=2.0,
            ge=1.0,
            le=4.0,
            description=(
                "Distance from adsorbate to surface in Angstroms (1-4 Å). "
                "Default: 2.0 Å."
            )
        )
    ] = 2.0,
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
    relax_adsorbate: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True (default), relaxes the isolated adsorbate before calculating energy. "
                "Set to False if adsorbate geometry is already optimized."
            )
        )
    ] = True,
    relax_slab: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True (default), relaxes the clean slab before calculating energy. "
                "Set to False if slab is already at equilibrium."
            )
        )
    ] = True,
    relax_bulk: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, relaxes the bulk structure (if needed). Usually not required "
                "for adsorption calculations. Default: False."
            )
        )
    ] = False,
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
    Calculate adsorption energy for a molecule/atom on a surface.
    
    Places the adsorbate on the slab at the specified site type, relaxes the
    system, and computes the adsorption energy as:
    E_ads = E_adslab - E_slab - E_adsorbate
    
    Args:
        slab_structure: Slab surface structure (dict or CIF/POSCAR string)
        adsorbate: Molecule/atom to adsorb (formula, coords, or Molecule dict)
        adsorption_site: Type of site ('ontop', 'bridge', 'hollow', 'all')
        distance: Initial adsorbate-surface distance in Angstroms
        calculator: Force field or ML potential to use
        relax_adsorbate: Whether to relax isolated adsorbate
        relax_slab: Whether to relax clean slab
        relax_bulk: Whether to relax bulk (usually not needed)
        fmax: Force convergence tolerance in eV/Å
        optimizer: Optimization algorithm
        max_steps: Maximum optimization steps
        
    Returns:
        Dictionary containing:
        - adsorption_energy: Adsorption energy in eV (negative = favorable)
        - adslab_energy: Total energy of adsorbate+slab system in eV
        - slab_energy: Energy of clean slab in eV
        - adsorbate_energy: Energy of isolated adsorbate in eV
        - slab_energy_per_atom: Slab energy per atom in eV/atom
        - adslab_structure: Final adslab structure as pymatgen dict
        - slab_structure: Final slab structure as pymatgen dict
        - adsorbate_structure: Final adsorbate structure as pymatgen dict
        - adsorption_site: Site type used
        - num_slab_atoms: Number of atoms in slab
        - num_adsorbate_atoms: Number of atoms in adsorbate
        
    Raises:
        ValueError: If structure/adsorbate parsing fails or site is invalid
        RuntimeError: If adsorption calculation fails
    """
    import matcalc as mtc
    from pymatgen.core import Structure, Molecule
    from pymatgen.analysis.adsorption import AdsorbateSiteFinder
    
    # Parse slab structure
    try:
        slab = _parse_structure(slab_structure)
    except Exception as e:
        return {
            "error": f"Failed to parse slab structure: {str(e)}",
            "details": "Ensure slab_structure is a valid Structure dict or CIF/POSCAR string."
        }
    
    # Parse adsorbate
    try:
        adsorbate_mol = _parse_adsorbate(adsorbate)
    except Exception as e:
        return {
            "error": f"Failed to parse adsorbate: {str(e)}",
            "details": "Ensure adsorbate is a molecular formula, coords, or Molecule dict."
        }
    
    # Find adsorption sites and place adsorbate
    try:
        asf = AdsorbateSiteFinder(slab)
        
        # Map site type to find_args
        if adsorption_site == "all":
            # Try all sites and pick best later
            ads_structs = asf.generate_adsorption_structures(
                adsorbate_mol,
                repeat=[1, 1, 1],
                find_args={'distance': distance}
            )
        else:
            # Generate structures for specific site type
            ads_structs = asf.generate_adsorption_structures(
                adsorbate_mol,
                repeat=[1, 1, 1],
                find_args={'distance': distance}
            )
            # Filter by site type if possible
            # Note: pymatgen's AdsorbateSiteFinder includes site info in structure properties
            filtered = []
            for ads_struct in ads_structs:
                site_props = getattr(ads_struct, 'properties', {})
                site_name = site_props.get('adsorption_site', '').lower()
                if adsorption_site.lower() in site_name or not site_name:
                    filtered.append(ads_struct)
            ads_structs = filtered if filtered else ads_structs
        
        if not ads_structs:
            return {
                "error": "No valid adsorption structures generated",
                "details": f"Could not place adsorbate at '{adsorption_site}' sites with distance={distance} Å",
                "adsorption_site": adsorption_site
            }
        
        # Use the first structure (or we can try all and pick best)
        adslab = ads_structs[0]
        
    except Exception as e:
        return {
            "error": f"Failed to generate adsorption structure: {str(e)}",
            "details": "Could not place adsorbate on slab surface.",
            "adsorption_site": adsorption_site
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
    except Exception as e:
        # Backend setting is optional, continue if it fails
        pass
    
    # Load calculator
    try:
        calc = mtc.load_fp(calculator)
    except Exception as e:
        return {
            "error": f"Failed to load calculator '{calculator}': {str(e)}",
            "details": "Check that calculator name is valid and model is available."
        }
    
    # Create AdsorptionCalc
    try:
        adsorption_calc = mtc.AdsorptionCalc(
            calculator=calc,
            relax_adsorbate=relax_adsorbate,
            relax_slab=relax_slab,
            relax_bulk=relax_bulk,
            fmax=fmax,
            optimizer=optimizer,
            max_steps=max_steps,
        )
    except Exception as e:
        return {
            "error": f"Failed to initialize AdsorptionCalc: {str(e)}",
            "details": "Check optimizer and parameter values."
        }
    
    # Run adsorption calculation
    try:
        # AdsorptionCalc requires dict with adslab, slab, adsorbate
        adsorption_input = {
            'adslab': adslab,
            'slab': slab,
            'adsorbate': adsorbate_mol
        }
        results = adsorption_calc.calc(adsorption_input)
    except Exception as e:
        return {
            "error": f"Adsorption calculation failed: {str(e)}",
            "details": "Energy calculation encountered an error.",
            "adsorption_site": adsorption_site
        }
    
    # Format output
    try:
        output = {
            "adsorption_energy": float(results["adsorption_energy"]),
            "adsorption_energy_units": "eV",
            "adslab_energy": float(results["adslab_energy"]),
            "slab_energy": float(results["slab_energy"]),
            "adsorbate_energy": float(results["adsorbate_energy"]),
            "slab_energy_per_atom": float(results["slab_energy_per_atom"]),
            "energy_units": "eV",
            "adslab_structure": results["final_adslab"].as_dict(),
            "slab_structure": results["final_slab"].as_dict(),
            "adsorbate_structure": results["final_adsorbate"].as_dict(),
            "adsorption_site": adsorption_site,
            "distance": distance,
            "num_slab_atoms": len(slab),
            "num_adsorbate_atoms": len(adsorbate_mol),
            "num_adslab_atoms": len(adslab),
            "calculator": calculator,
            "relax_adsorbate": relax_adsorbate,
            "relax_slab": relax_slab,
            "relax_bulk": relax_bulk,
        }
        
        # Add interpretation
        if output["adsorption_energy"] < 0:
            output["adsorption_favorable"] = True
            output["interpretation"] = "Negative adsorption energy indicates favorable (exothermic) adsorption"
        else:
            output["adsorption_favorable"] = False
            output["interpretation"] = "Positive adsorption energy indicates unfavorable (endothermic) adsorption"
        
        return output
        
    except Exception as e:
        return {
            "error": f"Failed to format results: {str(e)}",
            "details": "Adsorption calculation completed but result formatting failed."
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


def _parse_adsorbate(adsorbate: Union[str, List[float], Dict[str, Any]]) -> "Molecule":
    """
    Parse adsorbate from various formats.
    
    Args:
        adsorbate: Molecular formula, coords, or Molecule dict
        
    Returns:
        pymatgen Molecule object
        
    Raises:
        ValueError: If parsing fails
    """
    from pymatgen.core import Molecule
    
    if isinstance(adsorbate, str):
        # Treat as molecular formula
        try:
            # Use pymatgen's molecule building
            return Molecule.from_str(adsorbate, fmt='xyz')
        except:
            # Try as simple atom or molecule
            # Common adsorbates with reasonable geometries
            adsorbate_upper = adsorbate.upper()
            if adsorbate_upper == "CO":
                return Molecule(["C", "O"], [[0, 0, 0], [0, 0, 1.128]])
            elif adsorbate_upper == "O":
                return Molecule(["O"], [[0, 0, 0]])
            elif adsorbate_upper == "H":
                return Molecule(["H"], [[0, 0, 0]])
            elif adsorbate_upper == "OH":
                return Molecule(["O", "H"], [[0, 0, 0], [0, 0, 0.97]])
            elif adsorbate_upper == "H2O":
                return Molecule(["O", "H", "H"], [[0, 0, 0], [0.757, 0.586, 0], [-0.757, 0.586, 0]])
            elif adsorbate_upper == "CH4":
                return Molecule(["C", "H", "H", "H", "H"], 
                              [[0, 0, 0], [0.629, 0.629, 0.629], [-0.629, -0.629, 0.629],
                               [-0.629, 0.629, -0.629], [0.629, -0.629, -0.629]])
            elif adsorbate_upper == "N2":
                return Molecule(["N", "N"], [[0, 0, 0], [0, 0, 1.098]])
            elif adsorbate_upper == "NO":
                return Molecule(["N", "O"], [[0, 0, 0], [0, 0, 1.151]])
            else:
                # Try as single atom
                return Molecule([adsorbate], [[0, 0, 0]])
                
    elif isinstance(adsorbate, list):
        # Treat as coords for single atom (will use 'X' placeholder)
        if len(adsorbate) == 3:
            # Assume it's just coords, use as position
            raise ValueError("Adsorbate as list not yet supported. Use molecular formula or Molecule dict.")
        else:
            raise ValueError("Adsorbate list must have 3 coordinates [x, y, z]")
            
    elif isinstance(adsorbate, dict):
        # Treat as Molecule dict
        try:
            return Molecule.from_dict(adsorbate)
        except Exception as e:
            raise ValueError(f"Invalid Molecule dict: {e}")
            
    else:
        raise ValueError(f"adsorbate must be str, list, or dict, got {type(adsorbate)}")

