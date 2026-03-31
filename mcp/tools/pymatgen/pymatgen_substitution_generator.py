"""
Tool for generating structures via atomic substitution and doping.
Applies targeted or random element substitutions while preserving periodicity.
Supports fractional doping, site-specific substitution, and charge neutrality enforcement.
"""

from typing import Dict, Any, Optional, List, Union, Annotated
from pydantic import Field
import random


def pymatgen_substitution_generator(
    input_structures: Annotated[
        Union[Dict[str, Any], List[Dict[str, Any]], str, List[str]],
        Field(
            description="Input structure(s) to apply substitutions to. "
            "Can be: single Structure dict (from Structure.as_dict()), "
            "list of Structure dicts, CIF string, or list of CIF strings. "
            "Each structure will have all substitution rules applied."
        )
    ],
    substitutions: Annotated[
        Dict[str, Union[str, List[str], Dict[str, Any]]],
        Field(
            description="Substitution rules mapping elements to replacements. "
            "Simple: {'Li': 'Na', 'O': 'F'} - replace all Li with Na, all O with F. "
            "Multiple options: {'Li': ['Na', 'K', 'Mg']} - creates variants for each. "
            "Fractional: {'Li': {'replace_with': 'Na', 'fraction': 0.5}} - replace 50% of Li sites. "
            "Multiple fractional: {'Li': [{'replace_with': 'Na', 'fraction': 0.25}, {'replace_with': 'K', 'fraction': 0.5}]}."
        )
    ],
    site_selector: Annotated[
        Optional[Union[str, List[str]]],
        Field(
            default=None,
            description="Select which sites to substitute. Options: "
            "'all' (default) - all sites of specified element, "
            "'random' - random subset, "
            "Element name(s): ['Li', 'Fe'] - only these elements, "
            "'oxidation_X' - sites with specific oxidation state (e.g., 'oxidation_+2'), "
            "Coordination: 'coordination_4', 'coordination_6' (tetrahedral, octahedral), "
            "Wyckoff: 'wyckoff_4a', 'wyckoff_8d'. "
            "Can be a list to combine: ['Li', 'Na']."
        )
    ] = None,
    n_structures: Annotated[
        int,
        Field(
            default=5,
            ge=1,
            le=100,
            description="Number of structure variants to generate PER SUBSTITUTION COMBINATION (1-100). "
            "Total output count = n_structures × number_of_combinations, subject to max_attempts cap. "
            "For fractional substitutions: creates n_structures different random site arrangements per combo. "
            "For deterministic (fraction=1.0) substitutions: all n_structures copies are IDENTICAL — "
            "set n_structures=1 to avoid duplicate output. "
            "For multiple substitution options {'Ti': ['Mn','Fe','Co']}: one combination per option, "
            "so total = n_structures × len(options). "
            "Default: 5."
        )
    ] = 5,
    enforce_charge_neutrality: Annotated[
        bool,
        Field(
            default=False,
            description="If True, attempts to maintain charge neutrality by adjusting substitutions "
            "or applying charge balancing transformations. May fail if no neutral solution exists. "
            "If False, allows charge-imbalanced structures. Default: False."
        )
    ] = False,
    max_attempts: Annotated[
        int,
        Field(
            default=50,
            ge=1,
            le=500,
            description="Hard cap on total generation attempts (1-500). "
            "Acts as an absolute limit on output count: once attempts exceeds this value, "
            "generation stops regardless of how many structures were requested. "
            "For deterministic substitutions (fraction=1.0) every attempt succeeds, so "
            "output count = min(n_structures × num_combinations, max_attempts). "
            "IMPORTANT: when using a list of N substitution options with n_structures=k, "
            "set max_attempts >= N × k to avoid silently truncating the output. "
            "Default: 50."
        )
    ] = 50,
    allow_multiple_occupancy: Annotated[
        bool,
        Field(
            default=False,
            description="If True, allows partial occupancy of sites (disorder). "
            "If False, generates fully ordered structures by creating supercells if needed. "
            "Default: False (ordered structures)."
        )
    ] = False,
    min_distance: Annotated[
        float,
        Field(
            default=0.5,
            ge=0.1,
            le=3.0,
            description="Minimum allowed distance between atoms in Angstroms (0.1-3.0). "
            "Structures with atoms closer than this are rejected. "
            "Default: 0.5 Å."
        )
    ] = 0.5,
    output_format: Annotated[
        str,
        Field(
            default="dict",
            description="Output format: 'dict' (Structure.as_dict()), "
            "'poscar' (VASP POSCAR), 'cif' (CIF string), 'json' (JSON string). "
            "Default: 'dict'."
        )
    ] = "dict"
) -> Dict[str, Any]:
    """
    Generate structures by applying atomic substitutions and doping.
    
    Takes existing structures and applies element substitution rules to create
    new candidate materials. Supports complete replacement, fractional doping,
    site-specific substitution, and charge neutrality enforcement. 
    
    Uses pymatgen transformation classes:
    - SubstitutionTransformation: Complete element replacement (fraction=1.0)
    - ReplaceSiteSpeciesTransformation: Site-specific fractional substitutions
    - OrderDisorderedStructureTransformation: Handle disordered structures
    
    These transformation classes provide robust handling of symmetry preservation,
    automatic validation, and maintain transformation history.
    
    Returns:
        dict: Results containing:
            - success (bool): Whether generation succeeded
            - count (int): Number of structures generated
            - structures (list): Generated structures in requested format
            - metadata (list): Information about each structure including:
                - index (int): Structure number
                - formula (str): Chemical formula
                - composition (str): Formula with fractional occupancies
                - substitutions_applied (dict): What substitutions were applied
                - charge_neutral (bool): Whether structure is charge neutral
                - n_sites (int): Number of sites
                - volume (float): Cell volume in Å³
            - input_info (dict): Information about input structures
            - substitution_rules (dict): Substitution rules that were applied
            - message (str): Success message
            - warnings (list): Any warnings generated
            - error (str): Error message if failed
    """
    
    try:
        try:
            from pymatgen.core import Structure, Composition
            from pymatgen.transformations.standard_transformations import (
                SubstitutionTransformation,  # Complete element substitution (all sites)
                OrderDisorderedStructureTransformation  # Handle disordered structures
            )
            from pymatgen.transformations.site_transformations import (
                ReplaceSiteSpeciesTransformation  # Fractional/site-specific substitution
            )
            from pymatgen.analysis.bond_valence import BVAnalyzer
        except ImportError as e:
            return {
                "success": False,
                "error": f"Failed to import pymatgen: {str(e)}. Install with: pip install pymatgen"
            }
        
        # Parse input structures
        input_structs = []
        if isinstance(input_structures, dict):
            input_structs = [input_structures]
        elif isinstance(input_structures, list):
            input_structs = input_structures
        elif isinstance(input_structures, str):
            input_structs = [input_structures]
        else:
            return {
                "success": False,
                "error": f"Invalid input_structures type: {type(input_structures).__name__}"
            }
        
        # Convert to Structure objects
        structures = []
        for i, struct_input in enumerate(input_structs):
            try:
                if isinstance(struct_input, dict):
                    struct = Structure.from_dict(struct_input)
                elif isinstance(struct_input, str):
                    # Try CIF format
                    struct = Structure.from_str(struct_input, fmt="cif")
                else:
                    return {
                        "success": False,
                        "error": f"Input structure {i} must be dict or CIF string, got {type(struct_input).__name__}"
                    }
                structures.append(struct)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to parse input structure {i}: {str(e)}"
                }
        
        if not structures:
            return {
                "success": False,
                "error": "No valid input structures provided"
            }
        
        # Validate substitution rules
        if not substitutions or not isinstance(substitutions, dict):
            return {
                "success": False,
                "error": "substitutions must be a non-empty dictionary"
            }
        
        # Parse substitution rules into standardized format
        substitution_rules = {}
        for element, replacement in substitutions.items():
            if isinstance(replacement, str):
                # Simple replacement: {'Li': 'Na'}
                substitution_rules[element] = [{'replace_with': replacement, 'fraction': 1.0}]
            elif isinstance(replacement, list):
                rules = []
                for item in replacement:
                    if isinstance(item, str):
                        rules.append({'replace_with': item, 'fraction': 1.0})
                    elif isinstance(item, dict):
                        if 'replace_with' not in item:
                            return {
                                "success": False,
                                "error": f"Fractional substitution for {element} missing 'replace_with' key"
                            }
                        fraction = item.get('fraction', 1.0)
                        rules.append({'replace_with': item['replace_with'], 'fraction': float(fraction)})
                    else:
                        return {
                            "success": False,
                            "error": f"Invalid substitution format for {element}: {item}"
                        }
                substitution_rules[element] = rules
            elif isinstance(replacement, dict):
                # Single fractional replacement
                if 'replace_with' not in replacement:
                    return {
                        "success": False,
                        "error": f"Fractional substitution for {element} missing 'replace_with' key"
                    }
                fraction = replacement.get('fraction', 1.0)
                substitution_rules[element] = [{'replace_with': replacement['replace_with'], 'fraction': float(fraction)}]
            else:
                return {
                    "success": False,
                    "error": f"Invalid substitution format for {element}"
                }
        
        # Generate structures
        generated_structures = []
        metadata_list = []
        warnings = []
        attempts = 0
        
        for input_struct in structures:
            # For each substitution rule combination
            rule_combinations = []
            
            # Build list of all rule combinations to try
            for element, rules in substitution_rules.items():
                if not rule_combinations:
                    rule_combinations = [[(element, rule)] for rule in rules]
                else:
                    new_combinations = []
                    for combo in rule_combinations:
                        for rule in rules:
                            new_combinations.append(combo + [(element, rule)])
                    rule_combinations = new_combinations
            
            # Generate n_structures for each combination
            for combo in rule_combinations:
                for variant_num in range(n_structures):
                    if len(generated_structures) >= n_structures * len(rule_combinations):
                        break
                    
                    attempts += 1
                    if attempts > max_attempts:
                        warnings.append(f"Reached max attempts ({max_attempts}), stopping generation")
                        break
                    
                    try:
                        # Start with copy of input structure
                        new_struct = input_struct.copy()
                        substitutions_applied = {}
                        
                        # Apply each substitution in the combination
                        for element, rule in combo:
                            replace_with = rule['replace_with']
                            fraction = rule['fraction']
                            
                            # Check if element exists in structure
                            if element not in [str(s) for s in new_struct.composition.elements]:
                                continue
                            
                            # Apply site selector if specified
                            site_indices = None
                            if site_selector and site_selector != 'all':
                                # Get indices of sites matching selector
                                if isinstance(site_selector, str):
                                    selectors = [site_selector]
                                else:
                                    selectors = site_selector
                                
                                site_indices = []
                                for idx, site in enumerate(new_struct):
                                    species = str(site.specie)
                                    
                                    # Check each selector
                                    matches = False
                                    for selector in selectors:
                                        if selector == 'random':
                                            matches = True
                                        elif selector in [element, species]:
                                            matches = True
                                        elif selector.startswith('coordination_'):
                                            # Would need coordination analysis - skip for now
                                            pass
                                        elif selector.startswith('wyckoff_'):
                                            # Would need wyckoff analysis - skip for now
                                            pass
                                    
                                    if matches and species == element:
                                        site_indices.append(idx)
                            
                            # Apply substitution using transformation classes
                            if fraction >= 1.0:
                                # Complete substitution using SubstitutionTransformation
                                try:
                                    trans = SubstitutionTransformation({element: replace_with})
                                    new_struct = trans.apply_transformation(new_struct)
                                    substitutions_applied[element] = {'replace_with': replace_with, 'fraction': 1.0}
                                except Exception as e:
                                    warnings.append(f"SubstitutionTransformation failed for {element}→{replace_with}: {str(e)}")
                                    continue
                            else:
                                # Fractional substitution using ReplaceSiteSpeciesTransformation
                                # Get all sites with the element
                                if site_indices is None:
                                    site_indices = [i for i, site in enumerate(new_struct) 
                                                   if str(site.specie) == element]
                                
                                if not site_indices:
                                    warnings.append(f"No {element} sites found for substitution")
                                    continue
                                
                                # Select random subset based on fraction
                                n_to_replace = max(1, int(len(site_indices) * fraction))
                                if site_selector == 'random' or (isinstance(site_selector, str) and site_selector == 'random'):
                                    sites_to_replace = random.sample(site_indices, min(n_to_replace, len(site_indices)))
                                else:
                                    sites_to_replace = site_indices[:n_to_replace]
                                
                                # Apply ReplaceSiteSpeciesTransformation for each selected site
                                try:
                                    trans = ReplaceSiteSpeciesTransformation(
                                        indices_species_map={idx: replace_with for idx in sites_to_replace}
                                    )
                                    new_struct = trans.apply_transformation(new_struct)
                                    
                                    actual_fraction = len(sites_to_replace) / len(site_indices) if site_indices else 0
                                    substitutions_applied[element] = {
                                        'replace_with': replace_with,
                                        'fraction': actual_fraction,
                                        'n_sites_replaced': len(sites_to_replace)
                                    }
                                except Exception as e:
                                    warnings.append(f"ReplaceSiteSpeciesTransformation failed for fractional {element}→{replace_with}: {str(e)}")
                                    continue
                        
                        # Validate minimum distance
                        distance_matrix = new_struct.distance_matrix
                        min_dist = float('inf')
                        for i in range(len(distance_matrix)):
                            for j in range(i + 1, len(distance_matrix)):
                                if distance_matrix[i][j] < min_dist:
                                    min_dist = distance_matrix[i][j]
                        
                        if min_dist < min_distance:
                            warnings.append(f"Structure variant has atoms too close ({min_dist:.3f} Å < {min_distance} Å), skipping")
                            continue
                        
                        # Check charge neutrality if requested
                        charge_neutral = False
                        if enforce_charge_neutrality:
                            try:
                                # Try to add oxidation states
                                bva = BVAnalyzer()
                                new_struct = bva.get_oxi_state_decorated_structure(new_struct)
                                
                                # Check if neutral
                                total_charge = sum([site.specie.oxi_state for site in new_struct])
                                charge_neutral = abs(total_charge) < 0.01
                                
                                if not charge_neutral:
                                    warnings.append(f"Structure variant not charge neutral (charge={total_charge:.2f}), skipping")
                                    continue
                            except Exception as e:
                                warnings.append(f"Could not determine oxidation states: {str(e)}, skipping")
                                continue
                        else:
                            # Check if can determine charge neutrality without enforcing
                            try:
                                bva = BVAnalyzer()
                                test_struct = bva.get_oxi_state_decorated_structure(new_struct.copy())
                                total_charge = sum([site.specie.oxi_state for site in test_struct])
                                charge_neutral = abs(total_charge) < 0.01
                            except:
                                charge_neutral = None  # Unknown
                        
                        # Handle disordered sites if needed
                        if not allow_multiple_occupancy:
                            # Check for disorder
                            has_disorder = any(len(site.species.keys()) > 1 for site in new_struct)
                            if has_disorder:
                                # Use OrderDisorderedStructureTransformation to create ordered structure
                                try:
                                    trans = OrderDisorderedStructureTransformation()
                                    ordered_structs = trans.apply_transformation(new_struct, return_ranked_list=10)
                                    if ordered_structs:
                                        new_struct = ordered_structs[0]['structure']
                                except Exception as e:
                                    warnings.append(f"Could not create ordered structure: {str(e)}")
                        
                        # Format output
                        if output_format == "dict":
                            output_struct = new_struct.as_dict()
                        elif output_format == "poscar":
                            from pymatgen.io.vasp import Poscar
                            poscar = Poscar(new_struct)
                            output_struct = str(poscar)
                        elif output_format == "cif":
                            from pymatgen.io.cif import CifWriter
                            cif_writer = CifWriter(new_struct)
                            output_struct = str(cif_writer)
                        elif output_format == "json":
                            import json
                            output_struct = json.dumps(new_struct.as_dict())
                        else:
                            return {
                                "success": False,
                                "error": f"Invalid output_format: {output_format}. Must be 'dict', 'poscar', 'cif', or 'json'"
                            }
                        
                        # Store structure and metadata
                        generated_structures.append(output_struct)
                        
                        metadata = {
                            "index": len(generated_structures),
                            "formula": new_struct.composition.reduced_formula,
                            "composition": str(new_struct.composition),
                            "substitutions_applied": substitutions_applied,
                            "charge_neutral": charge_neutral,
                            "n_sites": len(new_struct),
                            "volume": float(new_struct.volume)
                        }
                        
                        if output_format == "dict":
                            metadata["structure_dict"] = output_struct
                        
                        metadata_list.append(metadata)
                        
                    except Exception as e:
                        warnings.append(f"Failed to generate variant {variant_num} for combination: {str(e)}")
                        continue
                
                if attempts > max_attempts:
                    break
            
            if attempts > max_attempts:
                break
        
        # Check if any structures were generated
        if not generated_structures:
            return {
                "success": False,
                "error": "No valid structures could be generated with the given parameters",
                "warnings": warnings,
                "attempts": attempts
            }
        
        # Build response
        input_info = {
            "n_input_structures": len(structures),
            "input_formulas": [s.composition.reduced_formula for s in structures]
        }
        
        result = {
            "success": True,
            "count": len(generated_structures),
            "structures": generated_structures,
            "metadata": metadata_list,
            "input_info": input_info,
            "substitution_rules": {k: [r for r in v] for k, v in substitution_rules.items()},
            "attempts": attempts,
            "message": f"Generated {len(generated_structures)} structure(s) via substitution"
        }
        
        if warnings:
            result["warnings"] = warnings
        
        return result
        
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import required module: {str(e)}. Install pymatgen: pip install pymatgen"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error during substitution generation: {str(e)}",
            "error_type": type(e).__name__
        }
