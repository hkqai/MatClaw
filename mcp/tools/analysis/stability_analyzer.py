"""
Tool for analyzing thermodynamic stability of materials.

Assesses thermodynamic viability through:
- Formation energy calculations
- Energy above convex hull (using Materials Project data)
- Decomposition products prediction
- Phase stability assessment relative to competing phases

Uses Materials Project API and pymatgen's phase diagram analysis.
Critical for filtering out thermodynamically unstable candidates early in screening.
"""

from typing import Dict, Any, Optional, Union, Annotated
from pydantic import Field
import os


def stability_analyzer(
    input_structure: Annotated[
        Union[Dict[str, Any], str],
        Field(
            description=(
                "Structure or composition to analyze. Can be:\n"
                "- Pymatgen Structure dict (from Structure.as_dict())\n"
                "- Pymatgen Composition dict (from Composition.as_dict())\n"
                "- Composition string (e.g., 'Fe2O3', 'LiCoO2')\n"
                "- CIF/POSCAR string"
            )
        )
    ],
    energy_per_atom: Annotated[
        Optional[float],
        Field(
            default=None,
            description=(
                "Energy per atom (eV/atom) for the input structure.\n"
                "If provided, used for stability analysis. If None, attempts to retrieve\n"
                "from Materials Project database for known materials.\n"
                "Required for analyzing novel/hypothetical structures."
            )
        )
    ] = None,
    check_polymorphs: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True, checks for known polymorphs and their relative stability.\n"
                "Default: True"
            )
        )
    ] = True,
    include_metastable: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True, includes metastable phases in decomposition analysis.\n"
                "Metastable phases may be experimentally accessible.\n"
                "Default: True"
            )
        )
    ] = True,
    hull_tolerance: Annotated[
        float,
        Field(
            default=0.0,
            ge=0.0,
            le=0.5,
            description=(
                "Energy tolerance (eV/atom) for considering a phase stable.\n"
                "Phases within this tolerance above hull may be synthesizable.\n"
                "Typical values: 0.025-0.1 eV/atom. Default: 0.0 (only hull phases)"
            )
        )
    ] = 0.0,
    temperature: Annotated[
        float,
        Field(
            default=300.0,
            ge=0.0,
            le=3000.0,
            description=(
                "Temperature (K) for stability assessment.\n"
                "Currently uses 0K energies (DFT), but parameter reserved for future thermal corrections.\n"
                "Default: 300.0 K"
            )
        )
    ] = 300.0,
) -> Dict[str, Any]:
    """
    Analyze thermodynamic stability of a material.
    
    Computes stability metrics using Materials Project thermodynamic data and
    pymatgen's phase diagram analysis. Determines if a composition is stable,
    metastable, or unstable, and identifies decomposition pathways.
    
    Returns
    -------
    dict:
        success                 (bool)  Whether analysis succeeded.
        composition             (str)   Reduced composition formula.
        stability               (dict)  Stability metrics:
            is_stable               (bool)  True if on convex hull or within hull_tolerance.
            energy_above_hull       (float) Energy above hull (eV/atom). 0 if stable.
            formation_energy        (float) Formation energy per atom (eV/atom).
            stability_level         (str)   'stable', 'metastable', or 'unstable'.
            hull_distance           (float) Distance from hull (same as energy_above_hull).
        decomposition           (dict)  Decomposition analysis (if unstable):
            decomposition_products  (list)  Competing phases composition would decompose into.
            product_fractions       (dict)  Amount of each decomposition product.
            energy_released         (float) Energy released during decomposition (eV/atom).
        competing_phases        (list)  Other phases in the chemical system.
        polymorphs              (list)  Known polymorphs with same composition (if found).
        phase_diagram_info      (dict)  Phase diagram statistics:
            n_phases                (int)   Number of phases in system.
            n_stable_phases         (int)   Number of stable (hull) phases.
            dimensionality          (int)   Chemical space dimensionality.
        energy_info             (dict)  Energy information:
            energy_per_atom         (float) Input energy or retrieved energy (eV/atom).
            energy_source           (str)   Source of energy ('user_provided', 'materials_project', 'estimated').
            formation_energy        (float) Formation energy per atom (eV/atom).
        recommendations         (dict)  Synthesis recommendations:
            synthesizable           (bool)  Likely synthesizable based on hull distance.
            confidence              (str)   'high', 'medium', 'low'.
            notes                   (list)  Recommendations and warnings.
        metadata                (dict)  Analysis metadata:
            temperature             (float) Temperature used (K).
            hull_tolerance          (float) Hull tolerance used (eV/atom).
            mp_data_available       (bool)  Whether MP data was available.
        message                 (str)   Human-readable summary.
        warnings                (list)  Non-critical warnings (if any).
        error                   (str)   Error message (if failed).
    """
    
    try:
        from pymatgen.core import Composition, Structure
        from pymatgen.io.cif import CifParser
        from pymatgen.io.vasp import Poscar
        from pymatgen.entries.computed_entries import ComputedEntry
        from pymatgen.analysis.phase_diagram import PhaseDiagram
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import pymatgen: {e}. Install with: pip install pymatgen"
        }
    
    try:
        from mp_api.client import MPRester
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import mp-api: {e}. Install with: pip install mp-api"
        }
    
    # Get API key from environment variable only
    api_key = os.environ.get("MP_API_KEY")
    if not api_key:
        return {
            "success": False,
            "error": "Materials Project API key required. Set MP_API_KEY environment variable. Get your key at: https://next-gen.materialsproject.org/api"
        }
    
    # Parse input to get Composition
    try:
        composition = None
        
        if isinstance(input_structure, dict):
            # Check if it's a Structure dict or Composition dict
            if "@module" in input_structure:
                module = input_structure.get("@module", "")
                if "Structure" in module:
                    structure = Structure.from_dict(input_structure)
                    composition = structure.composition
                elif "Composition" in module:
                    composition = Composition.from_dict(input_structure)
                else:
                    try:
                        structure = Structure.from_dict(input_structure)
                        composition = structure.composition
                    except:
                        composition = Composition.from_dict(input_structure)
            else:
                structure = Structure.from_dict(input_structure)
                composition = structure.composition
                
        elif isinstance(input_structure, str):
            # Try to parse as formula first
            try:
                composition = Composition(input_structure)
            except:
                # Try CIF or POSCAR
                from io import StringIO
                if "data_" in input_structure or "_cell_length" in input_structure:
                    parser = CifParser(StringIO(input_structure))
                    structure = parser.get_structures()[0]
                    composition = structure.composition
                else:
                    poscar = Poscar.from_str(input_structure)
                    composition = poscar.structure.composition
        else:
            return {
                "success": False,
                "error": "input_structure must be a Structure dict, Composition dict, composition string, CIF, or POSCAR."
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse input: {e}"
        }
    
    if composition is None:
        return {
            "success": False,
            "error": "Could not extract composition from input"
        }
    
    # Get reduced composition
    reduced_formula = composition.reduced_formula
    elements = [str(el) for el in composition.elements]
    
    # Initialize results
    warnings = []
    mp_data_available = False
    energy_source = "not_available"
    
    # Query Materials Project
    try:
        with MPRester(api_key) as mpr:
            # Get all entries for the chemical system
            chemsys = "-".join(sorted(elements))
            
            # Get entries for phase diagram
            entries = mpr.get_entries_in_chemsys(elements)
            
            if not entries:
                return {
                    "success": False,
                    "error": f"No Materials Project data found for chemical system {chemsys}"
                }
            
            mp_data_available = True
            
            # Check if we have energy for input composition
            input_energy = energy_per_atom
            
            if input_energy is None:
                # Try to find matching composition in MP
                for entry in entries:
                    if entry.composition.reduced_formula == reduced_formula:
                        # Use lowest energy entry for this composition
                        e_per_atom = entry.energy_per_atom
                        if input_energy is None or e_per_atom < input_energy:
                            input_energy = e_per_atom
                            energy_source = "materials_project"
            else:
                energy_source = "user_provided"
            
            # Build phase diagram
            pd = PhaseDiagram(entries)
            
            # Create entry for input composition
            if input_energy is not None:
                # Create a ComputedEntry for analysis
                input_entry = ComputedEntry(composition, input_energy * composition.num_atoms)
            else:
                # No energy available - can only do limited analysis
                warnings.append(
                    f"No energy data available for {reduced_formula}. "
                    "Provide energy_per_atom parameter for complete stability analysis."
                )
                input_entry = None
            
            # Get decomposition and stability info
            if input_entry:
                decomp, e_above_hull = pd.get_decomp_and_e_above_hull(input_entry)
                decomp_dict = pd.get_decomposition(composition)
                
                # Formation energy
                formation_energy = pd.get_form_energy_per_atom(input_entry)
            else:
                decomp = None
                e_above_hull = None
                decomp_dict = pd.get_decomposition(composition)
                formation_energy = None
            
            # Get polymorphs (same composition, different structures)
            polymorphs = []
            if check_polymorphs:
                for entry in entries:
                    if entry.composition.reduced_formula == reduced_formula:
                        polymorphs.append({
                            "material_id": getattr(entry, "entry_id", "unknown"),
                            "energy_per_atom": round(entry.energy_per_atom, 6),
                            "formation_energy_per_atom": round(
                                pd.get_form_energy_per_atom(entry), 6
                            ),
                        })
                
                # Sort by energy
                polymorphs.sort(key=lambda x: x["energy_per_atom"])
            
            # Get competing phases (stable phases in system)
            competing_phases = []
            for entry in pd.stable_entries:
                if entry.composition.reduced_formula != reduced_formula:
                    competing_phases.append({
                        "formula": entry.composition.reduced_formula,
                        "energy_per_atom": round(entry.energy_per_atom, 6),
                    })
            
            # Determine stability level
            if e_above_hull is not None:
                if e_above_hull <= hull_tolerance:
                    stability_level = "stable"
                    is_stable = True
                elif e_above_hull <= 0.1:
                    stability_level = "metastable"
                    is_stable = False
                else:
                    stability_level = "unstable"
                    is_stable = False
            else:
                stability_level = "unknown"
                is_stable = False
            
            # Decomposition products
            decomposition_products = []
            product_fractions = {}
            if decomp_dict:
                for phase, fraction in decomp_dict.items():
                    formula = phase.composition.reduced_formula
                    decomposition_products.append(formula)
                    product_fractions[formula] = round(fraction, 6)
            
            # Build stability dict
            stability = {
                "is_stable": is_stable,
                "stability_level": stability_level,
            }
            
            if e_above_hull is not None:
                stability["energy_above_hull"] = round(e_above_hull, 6)
                stability["hull_distance"] = round(e_above_hull, 6)
            
            if formation_energy is not None:
                stability["formation_energy"] = round(formation_energy, 6)
            
            # Decomposition info
            decomposition_info = {}
            if decomposition_products:
                decomposition_info["decomposition_products"] = decomposition_products
                decomposition_info["product_fractions"] = product_fractions
                if e_above_hull is not None:
                    decomposition_info["energy_released"] = round(e_above_hull, 6)
            
            # Phase diagram info
            phase_diagram_info = {
                "n_phases": len(entries),
                "n_stable_phases": len(pd.stable_entries),
                "dimensionality": len(elements),
            }
            
            # Energy info
            energy_info = {}
            if input_energy is not None:
                energy_info["energy_per_atom"] = round(input_energy, 6)
            energy_info["energy_source"] = energy_source
            if formation_energy is not None:
                energy_info["formation_energy"] = round(formation_energy, 6)
            
            # Recommendations
            synthesizable = False
            confidence = "low"
            notes = []
            
            if e_above_hull is not None:
                if e_above_hull <= 0.025:
                    synthesizable = True
                    confidence = "high"
                    notes.append("Material is on or very close to convex hull - highly likely to be synthesizable.")
                elif e_above_hull <= 0.1:
                    synthesizable = True
                    confidence = "medium"
                    notes.append(
                        f"Material is {e_above_hull:.3f} eV/atom above hull - "
                        "may be synthesizable as metastable phase."
                    )
                elif e_above_hull <= 0.2:
                    synthesizable = False
                    confidence = "low"
                    notes.append(
                        f"Material is {e_above_hull:.3f} eV/atom above hull - "
                        "synthesis likely challenging but possibly accessible under specific conditions."
                    )
                else:
                    synthesizable = False
                    confidence = "low"
                    notes.append(
                        f"Material is {e_above_hull:.3f} eV/atom above hull - "
                        "thermodynamically unstable, synthesis highly unlikely."
                    )
                
                if decomposition_products:
                    notes.append(
                        f"Would decompose into: {', '.join(decomposition_products)}"
                    )
            else:
                notes.append("Energy data not available - stability assessment incomplete.")
            
            recommendations = {
                "synthesizable": synthesizable,
                "confidence": confidence,
                "notes": notes,
            }
            
            # Metadata
            metadata = {
                "temperature": temperature,
                "hull_tolerance": hull_tolerance,
                "mp_data_available": mp_data_available,
                "check_polymorphs": check_polymorphs,
                "include_metastable": include_metastable,
            }
            
            # Build result
            result = {
                "success": True,
                "composition": reduced_formula,
                "stability": stability,
                "energy_info": energy_info,
                "phase_diagram_info": phase_diagram_info,
                "recommendations": recommendations,
                "metadata": metadata,
                "message": f"{reduced_formula} is {stability_level} ({e_above_hull:.3f} eV/atom above hull)" if e_above_hull is not None else f"Stability analysis for {reduced_formula} (energy data incomplete)",
            }
            
            if decomposition_info:
                result["decomposition"] = decomposition_info
            
            if competing_phases:
                result["competing_phases"] = competing_phases[:10]  # Limit to 10
            
            if polymorphs:
                result["polymorphs"] = polymorphs[:5]  # Limit to 5
            
            if warnings:
                result["warnings"] = warnings
            
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Materials Project query failed: {e}"
        }
