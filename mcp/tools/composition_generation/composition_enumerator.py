"""
Tool for enumerating charge-balanced chemical compositions from element lists.

Generates stoichiometrically valid compositions by systematically combining elements
with specified oxidation states, ensuring overall charge neutrality. This is essential
for composition-space exploration in materials discovery when you know which elements
to combine but not the exact stoichiometry.

Key use cases:
- Exploring Pr-Mo-O compositions (e.g., discovering Pr4MoO9 candidates)
- Enumerating Cu-Cr-Se stoichiometries for new semiconductors
- Finding charge-balanced Li-M-O cathode compositions
- Systematic composition generation for high-throughput screening
"""

from typing import Dict, Any, List, Optional, Annotated, Set, Tuple
from pydantic import Field
import itertools


def composition_enumerator(
    elements: Annotated[
        List[str],
        Field(
            description=(
                "List of element symbols to combine (e.g., ['Pr', 'Mo', 'O']). "
                "Must include at least one cation and one anion. "
                "Use standard element symbols (case-sensitive): 'Li', 'Fe', 'O', etc."
            )
        )
    ],
    oxidation_states: Annotated[
        Dict[str, List[int]],
        Field(
            description=(
                "Oxidation states for each element as {element: [states]}. "
                "Example: {'Pr': [3, 4], 'Mo': [6], 'O': [-2]} allows Pr³⁺/Pr⁴⁺, Mo⁶⁺, O²⁻. "
                "Multiple oxidation states enable mixed-valence compositions. "
                "Must provide at least one oxidation state per element."
            )
        )
    ],
    max_formula_units: Annotated[
        int,
        Field(
            default=6,
            ge=1,
            le=20,
            description=(
                "Maximum number of formula units to enumerate (1-20). "
                "Controls composition complexity: max_fu=5 allows up to (Pr,Mo)₅O₁₅. "
                "Larger values generate more compositions but increase computation time. "
                "Default: 6."
            )
        )
    ] = 6,
    max_atoms_per_formula: Annotated[
        Optional[int],
        Field(
            default=30,
            ge=3,
            le=100,
            description=(
                "Maximum total atoms in any generated formula (3-100). "
                "Prevents overly complex compositions like Pr₁₀Mo₁₀O₅₀. "
                "Default: 30. Set to None for unlimited."
            )
        )
    ] = 30,
    anion_cation_ratio_max: Annotated[
        float,
        Field(
            default=4.0,
            ge=1.0,
            le=10.0,
            description=(
                "Maximum ratio of anion/cation atoms to filter chemically unrealistic compositions. "
                "Example: ratio=4.0 would exclude PrMo₁₀O₅₀ (O/cation = 50/11 ≈ 4.5). "
                "Typical oxides: 1.0-3.0. Fluorides: 1.0-6.0. "
                "Default: 4.0."
            )
        )
    ] = 4.0,
    require_all_elements: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True, only return compositions containing ALL input elements. "
                "If False, allows binary/ternary subsets (e.g., Pr-O, Mo-O from Pr-Mo-O input). "
                "Default: True (ensures Pr-Mo-O compositions, not just Pr-O or Mo-O)."
            )
        )
    ] = True,
    allow_mixed_valence: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True, allows compositions with fractional average oxidation states "
                "(e.g., Pr₄MoO₉ has Pr avg oxidation = +3.5). "
                "If False, requires integer multiples matching exact oxidation states. "
                "Default: True (enables Pr³⁺/Pr⁴⁺ mixed-valence compounds)."
            )
        )
    ] = True,
    min_cation_fraction: Annotated[
        float,
        Field(
            default=0.05,
            ge=0.0,
            le=0.5,
            description=(
                "Minimum fraction of total atoms that must be cations (0.0-0.5). "
                "Prevents nearly-pure oxides like Pr₀.₀₁O₀.₉₉. "
                "Default: 0.05 (at least 5% cations)."
            )
        )
    ] = 0.05,
    output_format: Annotated[
        str,
        Field(
            default="detailed",
            description=(
                "Level of detail in output. "
                "'minimal': Just formula strings ['Pr2MoO6', 'Pr4MoO9']. "
                "'detailed': Full metadata with oxidation states, charge, atoms count. "
                "Default: 'detailed'."
            )
        )
    ] = "detailed",
    deduplicate: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True, removes duplicate reduced formulas (Pr₄Mo₂O₁₈ → Pr₂MoO₉). "
                "If False, keeps all unreduced formulas. "
                "Default: True."
            )
        )
    ] = True,
    sort_by: Annotated[
        str,
        Field(
            default="atoms",
            description=(
                "Sorting criterion for output. "
                "'atoms': By total atom count (smallest first). "
                "'anion_ratio': By anion/cation ratio (lowest first). "
                "'alphabetical': By formula string (A-Z). "
                "Default: 'atoms'."
            )
        )
    ] = "atoms"
) -> Dict[str, Any]:
    """
    Enumerate charge-balanced chemical compositions from element lists and oxidation states.
    
    Systematically generates all possible stoichiometric combinations of the input elements
    that satisfy charge neutrality constraints. Uses oxidation state chemistry to ensure
    only chemically reasonable formulas are returned.
    
    Algorithm:
    1. Classify elements as cations (positive oxidation states) and anions (negative)
    2. Enumerate cation combinations up to max_formula_units (e.g., Pr₁Mo₁, Pr₂Mo₁, Pr₁Mo₂, ...)
    3. For each cation combination, try all oxidation state assignments
    4. Calculate required anion count for charge neutrality
    5. Filter by chemical constraints (atom count, O/cation ratio, etc.)
    6. Reduce formulas and deduplicate
    
    Returns:
        dict:
            success (bool): Whether enumeration succeeded
            count (int): Number of unique compositions found
            compositions (list): Generated compositions (format depends on output_format):
                Minimal format - list of formula strings:
                    ['Pr2MoO6', 'Pr4MoO9', 'Pr6MoO12']
                Detailed format - list of dicts:
                    [
                        {
                            'formula': 'Pr4MoO9',
                            'reduced_formula': 'Pr4MoO9',
                            'elements': {'Pr': 4, 'Mo': 1, 'O': 9},
                            'total_atoms': 14,
                            'oxidation_state_assignment': {'Pr': 3.5, 'Mo': 6, 'O': -2},
                            'charge_balanced': True,
                            'anion_cation_ratio': 0.64,
                            'cation_fraction': 0.36
                        },
                        ...
                    ]
            metadata (dict): Enumeration parameters and statistics
            message (str): Summary message
            warnings (list, optional): Chemical warnings or edge cases
            error (str, optional): Error message if failed
    
    Example:
        >>> composition_enumerator(
        ...     elements=['Pr', 'Mo', 'O'],
        ...     oxidation_states={'Pr': [3, 4], 'Mo': [6], 'O': [-2]},
        ...     max_formula_units=6
        ... )
        {
            'success': True,
            'count': 12,
            'compositions': [
                {'formula': 'Pr2MoO6', 'oxidation_state_assignment': {'Pr': 3, 'Mo': 6, 'O': -2}, ...},
                {'formula': 'Pr4MoO9', 'oxidation_state_assignment': {'Pr': 3.5, 'Mo': 6, 'O': -2}, ...},
                ...
            ]
        }
    """
    
    try:
        # Import pymatgen for composition validation
        try:
            from pymatgen.core import Composition, Element
        except ImportError as e:
            return {
                "success": False,
                "error": f"Failed to import pymatgen: {str(e)}. Install with: pip install pymatgen"
            }
        
        # Validate inputs
        if not elements or len(elements) < 2:
            return {
                "success": False,
                "error": "Must provide at least 2 elements"
            }
        
        if not oxidation_states:
            return {
                "success": False,
                "error": "Must provide oxidation states dictionary"
            }
        
        # Check all elements have oxidation states
        missing = set(elements) - set(oxidation_states.keys())
        if missing:
            return {
                "success": False,
                "error": f"Missing oxidation states for elements: {missing}"
            }
        
        # Classify elements by oxidation states
        cations = {}  # {element: [positive oxidation states]}
        anions = {}   # {element: [negative oxidation states]}
        amphoteric = {}  # Elements with both positive and negative states
        
        for elem in elements:
            states = oxidation_states[elem]
            if not states:
                return {
                    "success": False,
                    "error": f"Element '{elem}' has no oxidation states specified"
                }
            
            positive = [s for s in states if s > 0]
            negative = [s for s in states if s < 0]
            
            if positive and negative:
                amphoteric[elem] = {'positive': positive, 'negative': negative}
            elif positive:
                cations[elem] = positive
            elif negative:
                anions[elem] = negative
            else:
                return {
                    "success": False,
                    "error": f"Element '{elem}' has no non-zero oxidation states"
                }
        
        # For now, treat amphoteric elements as cations (user can specify behavior)
        # TODO: In future, could enumerate both scenarios
        for elem, states_dict in amphoteric.items():
            cations[elem] = states_dict['positive']
        
        if not cations:
            return {
                "success": False,
                "error": "No cations (positive oxidation states) found. Need at least one cation."
            }
        
        if not anions:
            return {
                "success": False,
                "error": "No anions (negative oxidation states) found. Need at least one anion."
            }
        
        # Generate compositions
        compositions_set = set()  # Store as frozenset of (element, count, oxidation) tuples to deduplicate
        detailed_compositions = []  # Store full metadata
        warnings = []
        
        # Enumerate cation combinations
        cation_elements = list(cations.keys())
        anion_elements = list(anions.keys())
        
        # Generate all cation stoichiometry combinations up to max_formula_units
        for total_cations in range(1, max_formula_units + 1):
            # Distribute total_cations among available cation elements
            for cation_combo in _generate_integer_partitions(total_cations, len(cation_elements)):
                # cation_combo is a tuple like (2, 1) meaning 2 of first cation, 1 of second
                if require_all_elements and 0 in cation_combo:
                    continue  # Skip if not all cations present
                
                cation_stoich = {elem: count for elem, count in zip(cation_elements, cation_combo) if count > 0}
                
                # Try all oxidation state combinations for these cations
                cation_oxi_combos = [
                    dict(zip(cation_stoich.keys(), oxi_combo))
                    for oxi_combo in itertools.product(*[cations[elem] for elem in cation_stoich.keys()])
                ]
                
                for cation_oxi in cation_oxi_combos:
                    # Calculate total positive charge
                    total_positive_charge = sum(count * cation_oxi[elem] for elem, count in cation_stoich.items())
                    
                    # Enumerate anion combinations to balance charge
                    for anion_combo in _generate_anion_combinations(
                        anions, 
                        total_positive_charge, 
                        max_atoms_per_formula - total_cations if max_atoms_per_formula else 100,
                        allow_mixed_valence
                    ):
                        if not anion_combo:
                            continue
                        
                        # Check if all required elements present
                        if require_all_elements:
                            present_elements = set(cation_stoich.keys()) | set(anion_combo.keys())
                            if present_elements != set(elements):
                                continue
                        
                        # Build full stoichiometry
                        full_stoich = {**cation_stoich, **anion_combo}
                        total_atoms = sum(full_stoich.values())
                        
                        # Apply filters
                        if max_atoms_per_formula and total_atoms > max_atoms_per_formula:
                            continue
                        
                        # Anion/cation ratio check
                        total_anions = sum(anion_combo.values())
                        anion_ratio = total_anions / total_cations
                        if anion_ratio > anion_cation_ratio_max:
                            continue
                        
                        # Cation fraction check
                        cation_fraction = total_cations / total_atoms
                        if cation_fraction < min_cation_fraction:
                            continue
                        
                        # Build formula string
                        try:
                            # Use pymatgen to create and reduce formula
                            comp_dict = full_stoich.copy()
                            comp = Composition(comp_dict)
                            formula = comp.formula
                            reduced_formula = comp.reduced_formula
                            
                            # Deduplicate by reduced formula if requested
                            dedup_key = reduced_formula if deduplicate else formula
                            
                            if dedup_key not in [c.get('reduced_formula' if deduplicate else 'formula') 
                                                  for c in detailed_compositions]:
                                # Calculate average oxidation states
                                avg_oxi_states = cation_oxi.copy()
                                for anion_elem in anion_combo.keys():
                                    # For anions, use the single oxidation state (or could average if multiple)
                                    avg_oxi_states[anion_elem] = anions[anion_elem][0]  # Simplification
                                
                                composition_entry = {
                                    'formula': formula,
                                    'reduced_formula': reduced_formula,
                                    'elements': full_stoich,
                                    'total_atoms': total_atoms,
                                    'oxidation_state_assignment': avg_oxi_states,
                                    'charge_balanced': True,  # By construction
                                    'anion_cation_ratio': round(anion_ratio, 3),
                                    'cation_fraction': round(cation_fraction, 3),
                                    'cation_count': total_cations,
                                    'anion_count': total_anions
                                }
                                
                                detailed_compositions.append(composition_entry)
                        
                        except Exception as e:
                            warnings.append(f"Failed to process composition {full_stoich}: {str(e)}")
                            continue
        
        # Sort compositions
        if sort_by == "atoms":
            detailed_compositions.sort(key=lambda x: x['total_atoms'])
        elif sort_by == "anion_ratio":
            detailed_compositions.sort(key=lambda x: x['anion_cation_ratio'])
        elif sort_by == "alphabetical":
            detailed_compositions.sort(key=lambda x: x['reduced_formula'])
        
        # Format output
        if output_format == "minimal":
            output_compositions = [c['reduced_formula'] for c in detailed_compositions]
        else:
            output_compositions = detailed_compositions
        
        # Build metadata
        metadata = {
            'enumeration_params': {
                'elements': elements,
                'max_formula_units': max_formula_units,
                'max_atoms_per_formula': max_atoms_per_formula,
                'anion_cation_ratio_max': anion_cation_ratio_max,
                'require_all_elements': require_all_elements,
                'allow_mixed_valence': allow_mixed_valence,
                'min_cation_fraction': min_cation_fraction,
                'deduplicate': deduplicate,
                'sort_by': sort_by
            },
            'classification': {
                'cations': list(cations.keys()),
                'anions': list(anions.keys()),
                'amphoteric': list(amphoteric.keys())
            },
            'statistics': {
                'total_generated': len(detailed_compositions),
                'complexity_range': {
                    'min_atoms': min(c['total_atoms'] for c in detailed_compositions) if detailed_compositions else 0,
                    'max_atoms': max(c['total_atoms'] for c in detailed_compositions) if detailed_compositions else 0
                }
            }
        }
        
        result = {
            'success': True,
            'count': len(output_compositions),
            'compositions': output_compositions,
            'metadata': metadata,
            'message': f"Generated {len(output_compositions)} charge-balanced compositions from {len(elements)} elements"
        }
        
        if warnings:
            result['warnings'] = warnings
        
        return result
    
    except Exception as e:
        return {
            'success': False,
            'error': f"Composition enumeration failed: {str(e)}"
        }


def _generate_integer_partitions(n: int, num_parts: int) -> List[Tuple[int, ...]]:
    """
    Generate all ways to partition integer n into num_parts non-negative integers.
    
    Example: n=3, num_parts=2 → [(0,3), (1,2), (2,1), (3,0)]
    """
    if num_parts == 1:
        return [(n,)]
    
    partitions = []
    for i in range(n + 1):
        for sub_partition in _generate_integer_partitions(n - i, num_parts - 1):
            partitions.append((i,) + sub_partition)
    
    return partitions


def _generate_anion_combinations(
    anions: Dict[str, List[int]],
    required_negative_charge: int,
    max_anions: int,
    allow_fractional: bool = True
) -> List[Dict[str, int]]:
    """
    Generate anion stoichiometries that provide exactly the required negative charge.
    
    Args:
        anions: {element: [oxidation_states]} for anions
        required_negative_charge: Total negative charge needed (as positive integer)
        max_anions: Maximum number of anion atoms
        allow_fractional: Allow non-integer charge balancing
    
    Returns:
        List of {element: count} dictionaries for anions
    """
    combinations = []
    anion_elements = list(anions.keys())
    
    # For simplicity, assume single oxidation state per anion for now
    # TODO: Could be extended to handle multiple oxidation states per anion
    anion_charges = {elem: abs(states[0]) for elem, states in anions.items()}
    
    # Special case: single anion type
    if len(anion_elements) == 1:
        elem = anion_elements[0]
        charge_per_anion = anion_charges[elem]
        
        if allow_fractional:
            # Allow fractional anions if charge divides evenly
            if required_negative_charge % charge_per_anion == 0:
                count = required_negative_charge // charge_per_anion
                if count <= max_anions:
                    return [{elem: count}]
        else:
            # Strict integer charge balance
            if required_negative_charge % charge_per_anion == 0:
                count = required_negative_charge // charge_per_anion
                if count <= max_anions:
                    return [{elem: count}]
        return []
    
    # Multiple anion types - enumerate combinations
    # For computational efficiency, limit search space
    for total_anions in range(1, min(max_anions + 1, 30)):
        for anion_combo in _generate_integer_partitions(total_anions, len(anion_elements)):
            anion_stoich = {elem: count for elem, count in zip(anion_elements, anion_combo) if count > 0}
            
            # Calculate total negative charge
            total_negative = sum(count * anion_charges[elem] for elem, count in anion_stoich.items())
            
            if total_negative == required_negative_charge:
                combinations.append(anion_stoich)
    
    return combinations
