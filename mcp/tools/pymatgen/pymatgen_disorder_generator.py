"""
Tool for adding configurational disorder (mixed site occupancies) to ordered structures.

This tool converts fully ordered crystal structures into disordered structures with partial
site occupancies, which is essential for modeling solid solutions, high-entropy materials,
and doped systems. The disordered output structures can be used as input for SQS generation
or systematic enumeration.

Typical workflow:
    1. Get ordered structure from Materials Project or prototype
    2. Add disorder with this tool
    3. Generate SQS with pymatgen_sqs_generator or enumerate with pymatgen_enumeration_generator

Examples:
    - Solid solutions: (Li,Na)CoO₂, Al_xGa_{1-x}N
    - High-entropy materials: (Mg,Co,Ni,Cu,Zn)O
    - Doped semiconductors: Si_{1-x}Ge_x
    - Mixed anion systems: Li₂O_{1-x}F_x
"""

from typing import Dict, Any, Optional, List, Union, Annotated
from pydantic import Field


def pymatgen_disorder_generator(
    input_structures: Annotated[
        Union[Dict[str, Any], List[Dict[str, Any]], str, List[str]],
        Field(
            description=(
                "Input structure(s) to add disorder to. Must be fully ordered structures. "
                "Can be: single Structure dict (from Structure.as_dict()), "
                "list of Structure dicts, CIF string, or list of CIF strings. "
                "Structures with existing partial occupancies will be rejected unless "
                "allow_existing_disorder=True."
            )
        )
    ],
    site_substitutions: Annotated[
        Dict[str, Dict[str, float]],
        Field(
            description=(
                "Mapping of elements to their disordered occupancies. "
                "Format: {element: {species1: fraction1, species2: fraction2, ...}}. "
                "Examples: "
                "- {'Co': {'Ni': 0.333, 'Mn': 0.333, 'Co': 0.334}} — NMC ternary mixing. "
                "- {'O': {'O': 0.5, 'F': 0.5}} — mixed anion on O sites. "
                "Fractions for each element must sum to 1.0 (±0.01 tolerance). "
                "Use the element's symbol (not oxidation state decorated, e.g., 'Fe' not 'Fe2+')."
            )
        )
    ],
    site_selector: Annotated[
        str,
        Field(
            default="all_equivalent",
            description=(
                "Strategy for selecting which sites receive disorder. Options: "
                "'all_equivalent' (default): Apply disorder to ALL symmetry-equivalent sites of the element. "
                "  Recommended for symmetric disorder modeling. "
                "'wyckoff_X': Apply to specific Wyckoff position (e.g., 'wyckoff_4a', 'wyckoff_16d'). "
                "  Requires spacegroup analysis. "
                "'first_site': Apply to only the first occurrence (breaks symmetry, use with caution). "
                "'all_individually': Apply to each site independently (creates maximum disorder). "
                "Default: 'all_equivalent'."
            )
        )
    ] = "all_equivalent",
    validate_charge_neutrality: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True (default), attempts to validate that the disordered structure "
                "maintains overall charge neutrality using BVAnalyzer. Issues a warning "
                "if charge imbalance is detected, but does not reject the structure. "
                "Set to False to skip validation (faster, but risky for ionic materials)."
            )
        )
    ] = True,
    allow_existing_disorder: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If False (default), input structures with existing partial occupancies "
                "are rejected with an error. If True, allows adding disorder on top of "
                "existing disorder (advanced use case). Default: False."
            )
        )
    ] = False,
    composition_tolerance: Annotated[
        float,
        Field(
            default=0.01,
            ge=0.001,
            le=0.1,
            description=(
                "Tolerance for validating that site_substitutions fractions sum to 1.0 "
                "(0.001–0.1). If abs(sum - 1.0) > tolerance, an error is raised. "
                "Default: 0.01 (1%)."
            )
        )
    ] = 0.01,
    symmetry_precision: Annotated[
        float,
        Field(
            default=0.1,
            ge=0.01,
            le=1.0,
            description=(
                "Symmetry tolerance in Angstroms for identifying equivalent sites (0.01–1.0). "
                "Used when site_selector='all_equivalent'. Higher values group more sites "
                "as equivalent. Default: 0.1 Å."
            )
        )
    ] = 0.1,
    output_format: Annotated[
        str,
        Field(
            default="dict",
            description=(
                "Output format for disordered structures. "
                "'dict': pymatgen Structure.as_dict() (default, recommended for tool chaining). "
                "'poscar': VASP POSCAR string (NOTE: partial occupancies may not be standard). "
                "'cif': CIF string (properly encodes partial occupancies). "
                "'json': JSON-serialized Structure dict string. "
                "Default: 'dict'."
            )
        )
    ] = "dict"
) -> Dict[str, Any]:
    """
    Add configurational disorder (mixed site occupancies) to ordered crystal structures.

    This tool is the inverse of pymatgen_enumeration_generator: it creates disordered
    structures FROM ordered ones, enabling solid solution and high-entropy material modeling.

    Algorithm
    ---------
    1. Parse and validate input structures (must be fully ordered).
    2. Validate site_substitutions (fractions sum to 1.0 per element).
    3. Identify target sites based on site_selector strategy.
    4. Replace each target site with a mixed-occupancy site.
    5. Optionally validate charge neutrality.
    6. Return disordered structure(s) in requested format.

    Workflow Integration
    -------------------
    Disordered structures from this tool are suitable for:
      - pymatgen_sqs_generator: Generate Special Quasirandom Structures
      - pymatgen_enumeration_generator: Systematically enumerate all orderings
      - External tools: Virtual Crystal Approximation (VCA), CPA

    Returns
    -------
    dict:
        success            (bool)   True if generation succeeded
        count              (int)    Number of disordered structures generated
        structures         (list)   Disordered structures in requested output_format
        metadata           (list)   Per-structure information including:
            - formula: Chemical formula with disorder notation
            - original_formula: Formula before disorder
            - disorder_applied: Details of which sites were modified
            - charge_neutral: Whether structure is charge-neutral (if validated)
            - n_sites: Total number of sites
            - volume: Cell volume in ų
        input_info         (dict)   Summary of input structures
        substitution_rules (dict)   Parsed site_substitutions for reference
        warnings           (list)   Any non-fatal issues encountered
        error              (str)    Error message if success=False
    """
    try:
        from pymatgen.core import Structure, Composition, Species
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
        from pymatgen.analysis.bond_valence import BVAnalyzer
        from pymatgen.io.vasp import Poscar
        from pymatgen.io.cif import CifWriter
        import json
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import pymatgen: {str(e)}. Install with: pip install pymatgen"
        }

    # Validate output_format
    valid_formats = {"dict", "poscar", "cif", "json"}
    if output_format not in valid_formats:
        return {
            "success": False,
            "error": f"Invalid output_format: '{output_format}'. Must be one of {sorted(valid_formats)}."
        }

    # Validate site_selector
    valid_selectors = {"all_equivalent", "first_site", "all_individually"}
    if not (site_selector in valid_selectors or site_selector.startswith("wyckoff_")):
        return {
            "success": False,
            "error": (
                f"Invalid site_selector: '{site_selector}'. "
                f"Must be one of {sorted(valid_selectors)} or 'wyckoff_X' (e.g., 'wyckoff_4a')."
            )
        }

    # Parse input structures
    if isinstance(input_structures, (dict, str)):
        raw_list = [input_structures]
    elif isinstance(input_structures, list):
        raw_list = input_structures
    else:
        return {
            "success": False,
            "error": f"Invalid input_structures type: {type(input_structures).__name__}"
        }

    structures = []
    for i, item in enumerate(raw_list):
        try:
            if isinstance(item, dict):
                struct = Structure.from_dict(item)
            elif isinstance(item, str):
                struct = Structure.from_str(item, fmt="cif")
            else:
                return {
                    "success": False,
                    "error": f"Input structure {i} must be dict or CIF string, got {type(item).__name__}"
                }
            
            # Check for existing disorder
            has_disorder = any(len(site.species.keys()) > 1 for site in struct)
            if has_disorder and not allow_existing_disorder:
                return {
                    "success": False,
                    "error": (
                        f"Input structure {i} ({struct.composition.reduced_formula}) already has "
                        "partial site occupancies. Set allow_existing_disorder=True to proceed, "
                        "or use an ordered structure as input."
                    )
                }
            
            structures.append(struct)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to parse input structure {i}: {str(e)}"
            }

    if not structures:
        return {"success": False, "error": "No valid input structures provided."}

    # Validate site_substitutions
    if not site_substitutions or not isinstance(site_substitutions, dict):
        return {
            "success": False,
            "error": "site_substitutions must be a non-empty dictionary"
        }

    # Validate fractions sum to 1.0 for each element
    for element, species_fractions in site_substitutions.items():
        if not isinstance(species_fractions, dict):
            return {
                "success": False,
                "error": f"site_substitutions['{element}'] must be a dict of species:fraction pairs"
            }
        
        fraction_sum = sum(species_fractions.values())
        if abs(fraction_sum - 1.0) > composition_tolerance:
            return {
                "success": False,
                "error": (
                    f"Fractions for element '{element}' sum to {fraction_sum:.4f}, "
                    f"but must sum to 1.0 (±{composition_tolerance}). "
                    f"Provided: {species_fractions}"
                )
            }
        
        # Validate all fractions are positive
        for species, frac in species_fractions.items():
            if frac < 0:
                return {
                    "success": False,
                    "error": f"Negative fraction {frac} for species '{species}' in element '{element}'"
                }

    # Helper function to get Wyckoff positions
    def get_wyckoff_positions(struct: Structure, symprec: float) -> List[str]:
        """Get Wyckoff labels for each site in the structure."""
        try:
            sga = SpacegroupAnalyzer(struct, symprec=symprec)
            symmetrized = sga.get_symmetrized_structure()
            # Create mapping: site_index → wyckoff_letter
            wyckoff_labels = []
            for equiv_sites in symmetrized.equivalent_sites:
                wyckoff_label = symmetrized.wyckoff_symbols[len(wyckoff_labels)]
                for _ in equiv_sites:
                    wyckoff_labels.append(wyckoff_label)
            return wyckoff_labels
        except Exception as e:
            return ["unknown"] * len(struct)

    # Helper function to get symmetry-equivalent sites
    def get_equivalent_site_indices(struct: Structure, element: str, symprec: float) -> List[List[int]]:
        """Group site indices by symmetry equivalence for a given element."""
        try:
            sga = SpacegroupAnalyzer(struct, symprec=symprec)
            symmetrized = sga.get_symmetrized_structure()
            
            element_groups = []
            for equiv_sites in symmetrized.equivalent_sites:
                indices = []
                for site in equiv_sites:
                    # Find this site's index in the original structure
                    for i, orig_site in enumerate(struct):
                        if (orig_site.specie.symbol == element and
                            site.distance(orig_site) < 0.01):
                            indices.append(i)
                            break
                if indices:
                    element_groups.append(indices)
            
            return element_groups if element_groups else [[i for i, s in enumerate(struct) if s.specie.symbol == element]]
        except Exception:
            # Fallback: treat all sites of this element as one group
            return [[i for i, s in enumerate(struct) if s.specie.symbol == element]]

    # Main generation loop
    generated_structures = []
    metadata_list = []
    warnings = []

    for struct_idx, struct in enumerate(structures):
        struct_label = struct.composition.reduced_formula
        original_formula = struct.composition.formula
        
        # Create a mutable copy
        disordered_struct = struct.copy()
        disorder_applied = {}

        # Apply disorder for each element in site_substitutions
        for element, species_fractions in site_substitutions.items():
            # Find sites of this element
            element_indices = [i for i, site in enumerate(struct) if site.specie.symbol == element]
            
            if not element_indices:
                warnings.append(
                    f"Structure {struct_label}: no '{element}' sites found for disorder. Skipping element."
                )
                continue

            # Determine which sites to modify based on site_selector
            if site_selector == "all_equivalent":
                # Group by symmetry, apply to all groups
                equiv_groups = get_equivalent_site_indices(struct, element, symmetry_precision)
                target_indices = [idx for group in equiv_groups for idx in group]
            
            elif site_selector == "first_site":
                # Only the first site of this element
                target_indices = [element_indices[0]]
                warnings.append(
                    f"Structure {struct_label}: site_selector='first_site' breaks symmetry. "
                    "Use only for testing or when symmetry breaking is intentional."
                )
            
            elif site_selector == "all_individually":
                # All sites independently
                target_indices = element_indices
            
            elif site_selector.startswith("wyckoff_"):
                # Specific Wyckoff position
                target_wyckoff = site_selector.replace("wyckoff_", "")
                wyckoff_labels = get_wyckoff_positions(struct, symmetry_precision)
                target_indices = [
                    i for i in element_indices 
                    if wyckoff_labels[i] == target_wyckoff
                ]
                if not target_indices:
                    warnings.append(
                        f"Structure {struct_label}: no '{element}' sites found at Wyckoff position "
                        f"'{target_wyckoff}'. Available: {set(wyckoff_labels[i] for i in element_indices)}"
                    )
                    continue
            else:
                # Should not reach here due to earlier validation
                target_indices = element_indices

            # Apply disorder to target sites
            for site_idx in target_indices:
                # Create mixed species dictionary
                mixed_species = {Species(sp): frac for sp, frac in species_fractions.items()}
                
                # Replace site with disordered composition
                disordered_struct.replace(site_idx, mixed_species, properties=struct[site_idx].properties)
            
            # Record what was done
            disorder_applied[element] = {
                "species_fractions": species_fractions,
                "n_sites_modified": len(target_indices),
                "total_element_sites": len(element_indices),
                "site_indices": target_indices
            }

        # Charge neutrality check
        charge_neutral = None
        if validate_charge_neutrality:
            try:
                bva = BVAnalyzer()
                # Test on a copy to avoid modifying our structure
                test_struct = disordered_struct.copy()
                test_struct_oxi = bva.get_oxi_state_decorated_structure(test_struct)
                
                # Calculate total charge using oxidation states
                total_charge = 0.0
                for site in test_struct_oxi:
                    for species, occupancy in site.species.items():
                        if hasattr(species, 'oxi_state'):
                            total_charge += float(species.oxi_state) * occupancy
                
                charge_neutral = abs(total_charge) < 0.01
                
                if not charge_neutral:
                    warnings.append(
                        f"Structure {struct_label}: disordered structure has net charge "
                        f"{total_charge:+.3f}. Consider adjusting site_substitutions for charge balance."
                    )
            except Exception as e:
                warnings.append(
                    f"Structure {struct_label}: could not validate charge neutrality ({type(e).__name__}). "
                    "Proceeding without validation."
                )
                charge_neutral = None

        # Format output
        try:
            if output_format == "dict":
                output_struct = disordered_struct.as_dict()
            elif output_format == "poscar":
                poscar = Poscar(disordered_struct)
                output_struct = str(poscar)
            elif output_format == "cif":
                cif_writer = CifWriter(disordered_struct)
                output_struct = str(cif_writer)
            elif output_format == "json":
                output_struct = json.dumps(disordered_struct.as_dict())
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to format output for structure {struct_label}: {str(e)}"
            }

        generated_structures.append(output_struct)
        
        # Build metadata
        metadata = {
            "index": struct_idx + 1,
            "original_formula": original_formula,
            "formula": str(disordered_struct.composition),
            "reduced_formula": disordered_struct.composition.reduced_formula,
            "disorder_applied": disorder_applied,
            "charge_neutral": charge_neutral,
            "n_sites": len(disordered_struct),
            "volume": float(disordered_struct.volume),
            "lattice": {
                "a": float(disordered_struct.lattice.a),
                "b": float(disordered_struct.lattice.b),
                "c": float(disordered_struct.lattice.c),
                "alpha": float(disordered_struct.lattice.alpha),
                "beta": float(disordered_struct.lattice.beta),
                "gamma": float(disordered_struct.lattice.gamma)
            }
        }
        
        if output_format == "dict":
            metadata["structure_dict"] = output_struct
        
        metadata_list.append(metadata)

    # Build input_info summary
    input_info = {
        "n_input_structures": len(structures),
        "input_formulas": [s.composition.reduced_formula for s in structures]
    }

    # Build substitution_rules summary
    substitution_rules = {
        "site_selector": site_selector,
        "elements": list(site_substitutions.keys()),
        "substitutions": site_substitutions,
        "validate_charge_neutrality": validate_charge_neutrality
    }

    return {
        "success": True,
        "count": len(generated_structures),
        "structures": generated_structures,
        "metadata": metadata_list,
        "input_info": input_info,
        "substitution_rules": substitution_rules,
        "warnings": warnings if warnings else None,
        "message": (
            f"Successfully generated {len(generated_structures)} disordered structure(s). "
            f"Applied disorder to: {', '.join(site_substitutions.keys())}."
        )
    }
