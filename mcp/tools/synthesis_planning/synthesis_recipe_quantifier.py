"""
Tool for calculating absolute masses/amounts for synthesis recipes.

Converts stoichiometric ratios from Materials Project recipes into concrete
quantities (grams) based on desired batch size. Essential for lab automation
and robotic synthesis systems.
"""

from typing import Dict, Any, List, Optional, Annotated
from pydantic import Field
import re


# Standard atomic masses (amu) for common elements in materials synthesis
ATOMIC_MASSES = {
    'H': 1.008, 'He': 4.003, 'Li': 6.941, 'Be': 9.012, 'B': 10.81,
    'C': 12.01, 'N': 14.01, 'O': 16.00, 'F': 19.00, 'Ne': 20.18,
    'Na': 22.99, 'Mg': 24.31, 'Al': 26.98, 'Si': 28.09, 'P': 30.97,
    'S': 32.07, 'Cl': 35.45, 'Ar': 39.95, 'K': 39.10, 'Ca': 40.08,
    'Sc': 44.96, 'Ti': 47.87, 'V': 50.94, 'Cr': 52.00, 'Mn': 54.94,
    'Fe': 55.85, 'Co': 58.93, 'Ni': 58.69, 'Cu': 63.55, 'Zn': 65.38,
    'Ga': 69.72, 'Ge': 72.63, 'As': 74.92, 'Se': 78.97, 'Br': 79.90,
    'Kr': 83.80, 'Rb': 85.47, 'Sr': 87.62, 'Y': 88.91, 'Zr': 91.22,
    'Nb': 92.91, 'Mo': 95.95, 'Tc': 98.00, 'Ru': 101.1, 'Rh': 102.9,
    'Pd': 106.4, 'Ag': 107.9, 'Cd': 112.4, 'In': 114.8, 'Sn': 118.7,
    'Sb': 121.8, 'Te': 127.6, 'I': 126.9, 'Xe': 131.3, 'Cs': 132.9,
    'Ba': 137.3, 'La': 138.9, 'Ce': 140.1, 'Pr': 140.9, 'Nd': 144.2,
    'Pm': 145.0, 'Sm': 150.4, 'Eu': 152.0, 'Gd': 157.3, 'Tb': 158.9,
    'Dy': 163.5, 'Ho': 164.9, 'Er': 167.3, 'Tm': 168.9, 'Yb': 173.1,
    'Lu': 175.0, 'Hf': 178.5, 'Ta': 180.9, 'W': 183.8, 'Re': 186.2,
    'Os': 190.2, 'Ir': 192.2, 'Pt': 195.1, 'Au': 197.0, 'Hg': 200.6,
    'Tl': 204.4, 'Pb': 207.2, 'Bi': 209.0, 'Po': 209.0, 'At': 210.0,
    'Rn': 222.0, 'Fr': 223.0, 'Ra': 226.0, 'Ac': 227.0, 'Th': 232.0,
    'Pa': 231.0, 'U': 238.0, 'Np': 237.0, 'Pu': 244.0, 'Am': 243.0,
    'Cm': 247.0, 'Bk': 247.0, 'Cf': 251.0, 'Es': 252.0, 'Fm': 257.0,
    'Md': 258.0, 'No': 259.0, 'Lr': 262.0
}


def calculate_molar_mass(formula: str) -> float:
    """
    Calculate molar mass of a chemical formula.
    
    Args:
        formula: Chemical formula (e.g., 'Li2CO3', 'Fe2O3', 'H2O')
    
    Returns:
        Molar mass in g/mol
    
    Raises:
        ValueError: If formula contains unknown elements or invalid format
    """
    # Parse chemical formula using regex
    # Matches element symbols (capital + optional lowercase) followed by optional number
    pattern = r'([A-Z][a-z]?)(\d*\.?\d*)'
    matches = re.findall(pattern, formula)
    
    if not matches:
        raise ValueError(f"Could not parse chemical formula: {formula}")
    
    molar_mass = 0.0
    for element, count in matches:
        if element not in ATOMIC_MASSES:
            raise ValueError(f"Unknown element: {element} in formula {formula}")
        
        # Default count is 1 if not specified
        count_val = float(count) if count else 1.0
        molar_mass += ATOMIC_MASSES[element] * count_val
    
    return molar_mass


def calculate_molar_mass_from_elements(elements: Dict[str, str]) -> float:
    """
    Calculate molar mass from element dictionary.
    
    Args:
        elements: Dictionary mapping element symbols to stoichiometric coefficients
                  Example: {"Li": "2", "C": "1", "O": "3"} for Li2CO3
    
    Returns:
        Molar mass in g/mol
    
    Raises:
        ValueError: If unknown elements encountered
    """
    molar_mass = 0.0
    for element, coeff_str in elements.items():
        if element not in ATOMIC_MASSES:
            raise ValueError(f"Unknown element: {element}")
        
        coeff = float(coeff_str)
        molar_mass += ATOMIC_MASSES[element] * coeff
    
    return molar_mass


def synthesis_recipe_quantifier(
    recipes: Annotated[
        Dict[str, Any] | List[Dict[str, Any]],
        Field(
            description="Single recipe or list of recipes from mp_search_recipe (format_routes=False). "
            "Each recipe must contain 'precursors' list and optionally 'targets' list."
        )
    ],
    target_batch_size_grams: Annotated[
        float,
        Field(
            default=10.0,
            gt=0,
            description="Desired batch size of final product in grams. "
            "Tool calculates precursor masses to produce this amount. "
            "Default: 10.0 grams. Typical range: 1-100g for lab synthesis."
        )
    ] = 10.0,
    target_formula: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Target product formula for mass calculations. "
            "If not provided, attempts to infer from recipe 'targets' field. "
            "Required if recipe doesn't have target information."
        )
    ] = None,
    excess_factor: Annotated[
        float,
        Field(
            default=1.0,
            gt=0,
            le=2.0,
            description="Multiply precursor masses by this factor to account for losses. "
            "Example: 1.1 = 10% excess, 1.2 = 20% excess. "
            "Default: 1.0 (no excess). Use 1.1-1.2 for typical lab synthesis."
        )
    ] = 1.0,
    yield_efficiency: Annotated[
        float,
        Field(
            default=1.0,
            gt=0,
            le=1.0,
            description="Expected yield efficiency (0-1). Adjusts batch size to account for losses. "
            "Example: 0.9 = 90% yield, 0.8 = 80% yield. "
            "Default: 1.0 (100% yield). Use 0.8-0.95 for typical reactions."
        )
    ] = 1.0
) -> Dict[str, Any]:
    """
    Calculate absolute masses for synthesis recipe precursors based on target batch size.
    
    Converts stoichiometric ratios from Materials Project into concrete quantities (grams)
    for lab automation and robotic synthesis. Essential first step for translating 
    abstract recipes into machine-executable procedures.
    
    The tool:
    1. Identifies target product and calculates molar mass
    2. Converts target batch size (grams) to moles
    3. Calculates stoichiometric moles needed for each precursor
    4. Converts precursor moles to grams using molar masses
    5. Applies excess factor and yield adjustments
    6. Adds 'mass_grams' field to each precursor in recipe
    
    Use this tool:
        - After mp_search_recipe to prepare for automation
        - Before parameter_completer and equipment_mapper
        - To scale recipes for different batch sizes
        - To calculate material costs and inventory needs
    
    Examples:
        Quantify single recipe for 10g target:
            recipes=recipe_dict, target_batch_size_grams=10.0
        
        Quantify with 20% excess for losses:
            recipes=recipe_dict, target_batch_size_grams=5.0, excess_factor=1.2
        
        Quantify assuming 90% yield:
            recipes=recipe_dict, target_batch_size_grams=20.0, yield_efficiency=0.9
        
        Batch process multiple recipes:
            recipes=[recipe1, recipe2, recipe3], target_batch_size_grams=10.0
    
    Args:
        recipes: Recipe(s) from mp_search_recipe (format_routes=False)
        target_batch_size_grams: Desired final product mass in grams
        target_formula: Target product formula (auto-detected if not provided)
        excess_factor: Multiplier for precursor masses (accounts for losses)
        yield_efficiency: Expected reaction yield (0-1, accounts for incomplete conversion)
    
    Returns:
        Dictionary containing:
            - success: Boolean indicating calculation success
            - recipes: Modified recipe(s) with mass_grams added to precursors
            - target_formula: Target product formula used
            - target_batch_size_grams: Batch size used
            - target_molar_mass: Calculated molar mass of target (g/mol)
            - total_precursor_mass_grams: Sum of all precursor masses
            - adjusted_batch_size: Batch size after yield adjustment
            - excess_applied: Excess factor applied
            - yield_efficiency: Yield efficiency used
            - warnings: List of any warnings or notes
            - error: Error message if calculation failed
    """
    try:
        # Normalize input to list
        if isinstance(recipes, dict):
            recipes_list = [recipes]
            single_input = True
        else:
            recipes_list = recipes
            single_input = False
        
        if not recipes_list:
            return {
                "success": False,
                "recipes": [],
                "error": "No recipes provided"
            }
        
        # Process each recipe
        quantified_recipes = []
        warnings = []
        
        for recipe_idx, recipe in enumerate(recipes_list):
            try:
                # Extract target formula
                recipe_target_formula = target_formula
                
                if not recipe_target_formula:
                    # Try to infer from recipe targets
                    targets = recipe.get('targets', [])
                    if targets and len(targets) > 0:
                        # Try multiple possible field names
                        target_0 = targets[0]
                        recipe_target_formula = (
                            target_0.get('material_formula') or 
                            target_0.get('formula') or 
                            target_0.get('composition')
                        )
                    
                    # If still not found, check top-level fields
                    if not recipe_target_formula:
                        recipe_target_formula = (
                            recipe.get('target_formula') or
                            recipe.get('target') or
                            recipe.get('product_formula')
                        )
                
                if not recipe_target_formula:
                    warnings.append(f"Recipe {recipe_idx + 1}: Could not determine target formula. Provide target_formula parameter.")
                    continue
                
                # Calculate target molar mass
                try:
                    target_molar_mass = calculate_molar_mass(recipe_target_formula)
                except ValueError as e:
                    warnings.append(f"Recipe {recipe_idx + 1}: {str(e)}")
                    continue
                
                # Adjust batch size for yield
                adjusted_batch_size = target_batch_size_grams / yield_efficiency
                
                # Calculate moles of target needed
                target_moles = adjusted_batch_size / target_molar_mass
                
                # Extract precursors
                precursors = recipe.get('precursors', [])
                if not precursors:
                    warnings.append(f"Recipe {recipe_idx + 1}: No precursors found")
                    continue
                
                # Calculate mass for each precursor
                total_precursor_mass = 0.0
                quantified_precursors = []
                
                for precursor in precursors:
                    try:
                        # Get stoichiometric amount (relative ratio)
                        stoich_amount_str = precursor.get('amount', '1')
                        stoich_amount = float(stoich_amount_str)
                        
                        # Get precursor formula and elements
                        precursor_formula = (
                            precursor.get('material_formula') or
                            precursor.get('formula') or
                            precursor.get('material')
                        )
                        
                        if not precursor_formula:
                            warnings.append(f"Recipe {recipe_idx + 1}: Precursor missing formula, skipping")
                            continue
                        
                        # Calculate precursor molar mass
                        # Try to use elements dict first, fall back to formula parsing
                        elements = precursor.get('elements', {})
                        if elements:
                            precursor_molar_mass = calculate_molar_mass_from_elements(elements)
                        else:
                            precursor_molar_mass = calculate_molar_mass(precursor_formula)
                        
                        # Calculate moles of precursor needed
                        # Stoichiometry: precursor_moles = target_moles * stoichiometric_ratio
                        precursor_moles = target_moles * stoich_amount
                        
                        # Calculate mass in grams
                        precursor_mass = precursor_moles * precursor_molar_mass * excess_factor
                        
                        # Add mass to precursor
                        quantified_precursor = precursor.copy()
                        quantified_precursor['mass_grams'] = round(precursor_mass, 4)
                        quantified_precursor['moles'] = round(precursor_moles, 6)
                        quantified_precursor['molar_mass_g_per_mol'] = round(precursor_molar_mass, 2)
                        quantified_precursor['stoichiometric_amount'] = stoich_amount
                        
                        quantified_precursors.append(quantified_precursor)
                        total_precursor_mass += precursor_mass
                        
                    except Exception as e:
                        warnings.append(f"Recipe {recipe_idx + 1}: Error calculating mass for precursor '{precursor.get('material_formula', 'unknown')}': {str(e)}")
                        continue
                
                # Build quantified recipe
                quantified_recipe = recipe.copy()
                quantified_recipe['precursors'] = quantified_precursors
                quantified_recipe['quantification_metadata'] = {
                    'target_formula': recipe_target_formula,
                    'target_molar_mass_g_per_mol': round(target_molar_mass, 2),
                    'target_batch_size_grams': target_batch_size_grams,
                    'adjusted_batch_size_grams': round(adjusted_batch_size, 4),
                    'target_moles': round(target_moles, 6),
                    'total_precursor_mass_grams': round(total_precursor_mass, 4),
                    'excess_factor': excess_factor,
                    'yield_efficiency': yield_efficiency
                }
                
                quantified_recipes.append(quantified_recipe)
                
            except Exception as e:
                warnings.append(f"Recipe {recipe_idx + 1}: Unexpected error: {str(e)}")
                continue
        
        if not quantified_recipes:
            return {
                "success": False,
                "recipes": [],
                "warnings": warnings,
                "error": "Could not quantify any recipes. Check warnings for details."
            }
        
        # Build result
        result = {
            "success": True,
            "recipes": quantified_recipes[0] if single_input else quantified_recipes,
            "count": len(quantified_recipes),
            "parameters_used": {
                "target_batch_size_grams": target_batch_size_grams,
                "excess_factor": excess_factor,
                "yield_efficiency": yield_efficiency
            },
            "warnings": warnings if warnings else None,
            "message": f"Successfully quantified {len(quantified_recipes)} recipe(s)"
        }
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "recipes": [],
            "error": f"Unexpected error quantifying recipes: {str(e)}"
        }


# Utility function for quick molar mass lookup
def get_element_mass(element: str) -> float:
    """
    Get atomic mass for a single element.
    
    Args:
        element: Element symbol (e.g., 'Fe', 'O', 'Li')
    
    Returns:
        Atomic mass in amu (g/mol)
    
    Raises:
        ValueError: If element not found
    """
    if element not in ATOMIC_MASSES:
        raise ValueError(f"Unknown element: {element}")
    return ATOMIC_MASSES[element]
