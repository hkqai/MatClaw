"""
Tool for calculating formation and cohesive energies using matcalc.

Computes formation energy (relative to elemental references) and cohesive energy
(relative to isolated atoms) for crystal structures, useful for thermodynamic
stability analysis and materials screening.

Use this tool to:
- Calculate formation energy per atom
- Calculate cohesive energy per atom
- Assess thermodynamic stability of compounds
- Compare stability across different compositions
"""

from typing import Dict, Any, Optional, Union, Annotated
from pydantic import Field


def matcalc_calc_energetics(
    structure_input: Annotated[
        Union[Dict[str, Any], str],
        Field(
            description=(
                "Structure to calculate energetics for as a pymatgen Structure dict "
                "(from Structure.as_dict()), or a CIF/POSCAR string. Can be output from "
                "matgl_relax_structure or any pymatgen tool."
            )
        )
    ],
    calculator: Annotated[
        str,
        Field(
            default="M3GNet",
            description=(
                "Calculator/potential to use. Options:\n"
                "- 'M3GNet' or 'M3GNet-MatPES-PBE-v2025.1-PES' (default, good for energetics)\n"
                "- 'CHGNet' or 'CHGNet-MatPES-PBE-2025.2.10-2.7M-PES'\n"
                "- 'TensorNet-MatPES-PBE-v2025.1-PES' or 'pbe'\n"
                "- 'TensorNet-MatPES-r2SCAN-v2025.1-PES' or 'r2scan'\n"
                "Or any other matcalc-supported universal calculator."
            )
        )
    ] = "M3GNet",
    elemental_refs: Annotated[
        str,
        Field(
            default="MatPES-PBE",
            description=(
                "Elemental reference data for formation energy. Options:\n"
                "- 'MatPES-PBE' (default, matches MatPES potentials)\n"
                "- 'MatPES-r2SCAN' (for r2SCAN-based calculations)\n"
                "- 'MP-PBE' (Materials Project PBE references)\n"
                "References must be compatible with calculator functional."
            )
        )
    ] = "MatPES-PBE",
    relax_structure: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True (default), relaxes the structure before energy calculation. "
                "Set to False if structure is already at equilibrium."
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
    use_gs_reference: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "Use DFT ground state data for formation energy reference. "
                "When True, compares to experimental/DFT ground states instead of "
                "elemental references. Default: False."
            )
        )
    ] = False,
) -> Dict[str, Any]:
    """
    Calculate formation and cohesive energies using matcalc.
    
    Computes thermodynamic properties by relaxing the structure and calculating
    energies relative to elemental references (formation energy) and isolated
    atoms (cohesive energy). Essential for stability analysis and phase diagram
    construction.
    
    Formation Energy: Energy to form compound from constituent elements in their
    standard states. Negative values indicate thermodynamically stable compounds.
    
    Cohesive Energy: Energy to form compound from isolated atoms. Negative values
    indicate energy is released when bonding (more stable than isolated atoms).
    
    Typical Use Cases:
        **Basic energetics calculation:**
        matcalc_calc_energetics(structure)
        
        **Already relaxed structure:**
        matcalc_calc_energetics(structure, relax_structure=False)
        
        **High accuracy calculation:**
        matcalc_calc_energetics(structure, fmax=0.01, calculator="r2scan",
                               elemental_refs="MatPES-r2SCAN")
        
        **Fast screening:**
        matcalc_calc_energetics(structure, fmax=0.3, relax_structure=False)
    
    Reference Data Notes:
        - MatPES-PBE: Use with M3GNet, CHGNet, TensorNet-PBE calculators
        - MatPES-r2SCAN: Use with TensorNet-r2SCAN calculator
        - MP-PBE: Materials Project PBE references (legacy)
        - Cohesive energy always uses DFT atomic energies as reference
    
    Args:
        structure_input: Structure to analyze (pymatgen dict, CIF, or POSCAR string)
        calculator: ML potential or calculator name
        elemental_refs: Reference data for formation energy calculations
        relax_structure: Whether to relax structure before energy calculation
        fmax: Force convergence tolerance for relaxations (eV/Å)
        optimizer: Optimization algorithm
        use_gs_reference: Use DFT ground state references for formation energy
    
    Returns:
        Dictionary containing:
            success                         (bool)      Whether calculation completed successfully
            formation_energy_per_atom_eV    (float)     Formation energy per atom (eV/atom)
            cohesive_energy_per_atom_eV     (float)     Cohesive energy per atom (always positive)
            total_energy_eV                 (float)     Total energy of structure (eV)
            energy_per_atom_eV              (float)     Total energy per atom (eV/atom)
            num_atoms                       (int)       Number of atoms in structure
            structure                       (dict)      Input structure (pymatgen dict)
            final_structure                 (dict)      Relaxed structure if relax_structure=True
            relaxed                         (bool)      Whether structure was relaxed
            formation_stable                (bool)      True if formation energy < 0 (stable)
            calculation_time_seconds        (float)     Total calculation time
            parameters                      (dict)      All calculation parameters used
            units                           (dict)      Units for all quantities
            error                           (str)       Error message if calculation failed
    """
    import time
    start_time = time.time()
    
    try:
        from pymatgen.core import Structure
        from pymatgen.io.cif import CifParser
        from pymatgen.io.vasp import Poscar
        import matcalc as mtc
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import required libraries: {e}. "
                    f"Install with: pip install matcalc pymatgen"
        }
    
    # Parse structure
    try:
        structure = _parse_structure(structure_input)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse structure: {e}",
        }
    
    initial_structure_dict = structure.as_dict()
    
    # Set appropriate backend based on calculator type
    try:
        import matgl
        if any(model in calculator.upper() for model in ["M3GNET", "CHGNET"]):
            matgl.set_backend('DGL')
        else:
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
    
    # Initialize EnergeticsCalc
    try:
        energetics_calc = mtc.EnergeticsCalc(
            calculator=calc,
            elemental_refs=elemental_refs,
            fmax=fmax,
            optimizer=optimizer,
            use_gs_reference=use_gs_reference,
            relax_structure=relax_structure,
        )
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to initialize EnergeticsCalc: {e}",
        }
    
    # Run energetics calculation
    try:
        results = energetics_calc.calc(structure)
    except Exception as e:
        return {
            "success": False,
            "error": f"Energetics calculation failed: {e}. "
                    f"Check that elemental references are compatible with calculator.",
        }
    
    # Extract results
    try:
        # Handle None values from results
        formation_energy_raw = results.get("formation_energy_per_atom")
        cohesive_energy_raw = results.get("cohesive_energy_per_atom")
        
        if formation_energy_raw is None or cohesive_energy_raw is None:
            return {
                "success": False,
                "error": f"Energetics calculation returned None values. "
                        f"This may occur with '{elemental_refs}' references when used with machine learning force fields. "
                        f"Consider using 'MatPES-PBE' or 'MatPES-r2SCAN' with ML force fields.",
            }
        
        formation_energy_per_atom = float(formation_energy_raw)
        cohesive_energy_per_atom = float(cohesive_energy_raw)
        
        # Get final structure
        final_structure = results.get("final_structure")
        if final_structure is not None:
            final_structure_dict = final_structure.as_dict()
        else:
            final_structure_dict = initial_structure_dict
        
        # Calculate additional properties
        num_atoms = len(structure)
        
        # Get total energy if available, or calculate from formation energy
        if "energy" in results:
            total_energy = float(results["energy"])
        else:
            # Estimate from formation energy (not exact without elemental refs)
            total_energy = formation_energy_per_atom * num_atoms
        
        energy_per_atom = total_energy / num_atoms
        formation_stable = formation_energy_per_atom < 0
        
        calculation_time = time.time() - start_time
        
        return {
            "success": True,
            "formation_energy_per_atom_eV": formation_energy_per_atom,
            "cohesive_energy_per_atom_eV": cohesive_energy_per_atom,
            "total_energy_eV": total_energy,
            "energy_per_atom_eV": energy_per_atom,
            "num_atoms": int(num_atoms),
            "structure": initial_structure_dict,
            "final_structure": final_structure_dict,
            "relaxed": relax_structure,
            "formation_stable": formation_stable,
            "calculation_time_seconds": float(calculation_time),
            "parameters": {
                "calculator": calculator,
                "elemental_refs": elemental_refs,
                "relax_structure": relax_structure,
                "fmax": fmax,
                "optimizer": optimizer,
                "use_gs_reference": use_gs_reference,
            },
            "units": {
                "formation_energy": "eV/atom",
                "cohesive_energy": "eV/atom",
                "total_energy": "eV",
                "energy": "eV/atom",
                "force": "eV/Angstrom",
            },
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to extract energetics results: {e}",
        }


def _parse_structure(structure_input: Union[Dict[str, Any], str]) -> Any:
    """
    Parse structure input into pymatgen Structure object.
    
    Args:
        structure_input: Structure as dict, CIF string, or POSCAR string
    
    Returns:
        pymatgen Structure object
    """
    from pymatgen.core import Structure
    
    if isinstance(structure_input, Structure):
        return structure_input
    elif isinstance(structure_input, dict):
        try:
            return Structure.from_dict(structure_input)
        except Exception:
            raise ValueError("Invalid structure dictionary format")
    elif isinstance(structure_input, str):
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
    else:
        raise ValueError(f"Unsupported structure type: {type(structure_input)}")
