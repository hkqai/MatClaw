"""
Synthesis route generation tool for materials synthesis planning.

Generates feasible synthesis routes for inorganic materials based on:
- Composition and structure
- Known synthesis methods (solid-state, hydrothermal, sol-gel)
- Literature-based precursor data from Materials Project
- Temperature/time heuristics

This tool queries Materials Project for actual precursors used in literature
synthesis recipes and uses template-based generation for process parameters.
Requires MP_API_KEY environment variable.
"""

from typing import Dict, Any, List, Optional, Annotated, Tuple
from pydantic import Field
import os
from mp_api.client import MPRester


def template_route_generator(
    target_material: Annotated[
        Dict[str, Any],
        Field(
            description=(
                "Target material to synthesize. Must contain:\n"
                "- 'composition': Chemical formula string (e.g., 'LiCoO2')\n"
                "- 'structure': Optional pymatgen Structure dict\n"
                "Example: {'composition': 'LiCoO2', 'structure': {...}}"
            )
        )
    ],
    synthesis_method: Annotated[
        str,
        Field(
            default="auto",
            description=(
                "Synthesis method to use:\n"
                "- 'solid_state': High-temperature solid-state reaction\n"
                "- 'hydrothermal': Low-temperature solution synthesis\n"
                "- 'sol_gel': Molecular-level mixing via gel chemistry\n"
                "- 'auto': Automatically select based on composition\n"
                "Default: 'auto'"
            )
        )
    ] = "auto",
    constraints: Annotated[
        Optional[Dict[str, Any]],
        Field(
            default=None,
            description=(
                "Optional constraints:\n"
                "- 'max_temperature': Maximum temperature in °C\n"
                "- 'max_time': Maximum total time in hours\n"
                "- 'exclude_precursors': List of precursor forms to avoid (e.g., ['nitrate', 'chloride'])\n"
                "- 'prefer_precursors': List of preferred precursor forms\n"
                "Example: {'max_temperature': 1000, 'exclude_precursors': ['nitrate']}"
            )
        )
    ] = None,
) -> Dict[str, Any]:
    """
    Generate template synthesis routes for inorganic materials using Materials Project precursor data.
    
    Queries Materials Project for literature-based precursors, then applies template-based
    process generation (temperature, time, atmosphere) using materials chemistry heuristics.
    
    Requires MP_API_KEY environment variable to be set.
    
    Returns
    -------
    {
        "success": bool,
        "target_composition": str,
        "routes": List[Dict],  # Ranked synthesis routes
        "warnings": List[str],
        "error": Optional[str]
    }
    
    Each route contains:
        - method: Synthesis method used
        - source: "template_with_mp_precursors"
        - confidence: Estimated feasibility (0-1)
        - precursors: List of starting materials with amounts (from MP literature data)
        - steps: Sequential synthesis steps with parameters
        - total_time_estimate: Estimated total synthesis time
        - feasibility_score: Overall feasibility assessment
    """
    
    # Validate input
    if not target_material or "composition" not in target_material:
        return {
            "success": False,
            "error": "target_material must contain 'composition' field."
        }
    
    composition_str = target_material["composition"]
    
    try:
        from pymatgen.core import Composition
    except ImportError:
        return {
            "success": False,
            "error": "pymatgen not available. Install with: pip install pymatgen"
        }
    
    # Parse composition
    try:
        composition = Composition(composition_str)
    except Exception as e:
        return {
            "success": False,
            "error": f"Invalid composition '{composition_str}': {str(e)}"
        }
    
    # Apply constraints
    if constraints is None:
        constraints = {}
    
    max_temp = constraints.get("max_temperature", 1400)
    max_time = constraints.get("max_time", 48)
    exclude_forms = constraints.get("exclude_precursors", [])
    prefer_forms = constraints.get("prefer_precursors", [])
    
    # Determine synthesis method
    if synthesis_method == "auto":
        method = _select_synthesis_method(composition)
    else:
        method = synthesis_method
    
    if method not in ["solid_state", "hydrothermal", "sol_gel"]:
        return {
            "success": False,
            "error": f"Unknown synthesis method: {method}. Use 'solid_state', 'hydrothermal', 'sol_gel', or 'auto'."
        }
    
    # Generate routes
    routes = []
    warnings = []
    
    try:
        # Select precursors
        precursors_result = _select_precursors(
            composition,
            composition_str,
            method,
            exclude_forms,
            prefer_forms
        )
        
        if not precursors_result["success"]:
            return {
                "success": False,
                "target_composition": composition_str,
                "error": precursors_result["error"],
                "warnings": precursors_result.get("warnings", [])
            }
        
        precursor_sets = precursors_result["precursor_sets"]
        warnings.extend(precursors_result.get("warnings", []))
        
        # Generate route for each precursor set
        for idx, precursor_set in enumerate(precursor_sets, 1):
            if method == "solid_state":
                route = _generate_solid_state_route(
                    composition,
                    precursor_set,
                    max_temp,
                    max_time
                )
            elif method == "hydrothermal":
                route = _generate_hydrothermal_route(
                    composition,
                    precursor_set,
                    max_temp,
                    max_time
                )
            elif method == "sol_gel":
                route = _generate_solgel_route(
                    composition,
                    precursor_set,
                    max_temp,
                    max_time
                )
            
            route["route_id"] = idx
            route["source"] = "template_with_mp_precursors"
            routes.append(route)
            
    except Exception as e:
        return {
            "success": False,
            "target_composition": composition_str,
            "error": f"Error generating routes: {str(e)}",
            "warnings": warnings
        }
    
    # Rank routes by feasibility
    routes.sort(key=lambda r: r["feasibility_score"], reverse=True)
    
    return {
        "success": True,
        "target_composition": composition_str,
        "n_routes": len(routes),
        "routes": routes,
        "warnings": warnings if warnings else None,
    }


def _select_synthesis_method(composition: Any) -> str:
    """Select appropriate synthesis method based on composition."""
    # Simple heuristics for method selection
    
    # Check for elements that prefer hydrothermal
    hydrothermal_indicators = {"F", "P", "V", "Mo", "W"}
    if any(elem.symbol in hydrothermal_indicators for elem in composition.elements):
        return "hydrothermal"
    
    # Check for multi-cation oxides that benefit from sol-gel homogeneity
    # Sol-gel is excellent for complex oxides with 3+ cations
    n_cations = len([e for e in composition.elements if e.symbol != "O"])
    if n_cations >= 3:
        # Multi-cation systems benefit from molecular-level mixing
        return "sol_gel"
    
    # Default to solid-state for simple oxides
    return "solid_state"


def _query_mp_precursors(target_formula: str) -> Dict[str, Any]:
    """Query Materials Project for precursors used in literature synthesis of target material."""
    
    # Get API key
    api_key = os.getenv("MP_API_KEY")
    if not api_key:
        return {
            "success": False,
            "error": "MP_API_KEY environment variable not set. Get your API key from https://materialsproject.org/api"
        }
    
    try:
        from pymatgen.core import Composition
        
        # Query MP for synthesis recipes
        with MPRester(api_key) as mpr:
            results = mpr.synthesis.search(
                target_formula=[target_formula],
                num_chunks=1,
                chunk_size=100
            )
        
        if not results:
            return {
                "success": False,
                "error": f"No synthesis recipes found in Materials Project for {target_formula}"
            }
        
        # Extract precursors and build element-based database
        element_precursors = {}
        precursor_counts = {}  # Track frequency
        
        for recipe in results:
            if not hasattr(recipe, 'precursors_formula_s'):
                continue
            
            for precursor_formula in recipe.precursors_formula_s:
                # Parse precursor to get elements
                try:
                    prec_comp = Composition(precursor_formula)
                    
                    # Track this precursor
                    if precursor_formula not in precursor_counts:
                        precursor_counts[precursor_formula] = 0
                    precursor_counts[precursor_formula] += 1
                    
                    # Map precursor to each element it contains
                    for elem in prec_comp.elements:
                        elem_symbol = str(elem)
                        if elem_symbol not in element_precursors:
                            element_precursors[elem_symbol] = {}
                        if precursor_formula not in element_precursors[elem_symbol]:
                            element_precursors[elem_symbol][precursor_formula] = 0
                        element_precursors[elem_symbol][precursor_formula] += 1
                except:
                    continue
        
        # Convert to PRECURSOR_DATABASE format
        precursor_database = {}
        for elem_symbol, precursor_dict in element_precursors.items():
            # Sort by frequency
            sorted_precursors = sorted(
                precursor_dict.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            precursor_list = []
            for precursor_formula, count in sorted_precursors:
                # Determine form from formula
                form = _determine_precursor_form(precursor_formula)
                
                precursor_list.append({
                    "compound": precursor_formula,
                    "form": form,
                    "common": count >= 2,  # Common if used 2+ times
                    "purity": "99%",  # Default
                    "frequency": count
                })
            
            precursor_database[elem_symbol] = precursor_list
        
        return {
            "success": True,
            "precursor_database": precursor_database,
            "total_recipes": len(results)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error querying Materials Project: {str(e)}"
        }


def _determine_precursor_form(formula: str) -> str:
    """Determine the chemical form/type of a precursor from its formula."""
    formula_upper = formula.upper()
    
    if "CO3" in formula_upper or "CO)3" in formula_upper:
        return "carbonate"
    elif "NO3" in formula_upper or "NO)3" in formula_upper:
        return "nitrate"
    elif "(OH)" in formula_upper or "HO" in formula and "H" in formula:
        return "hydroxide"
    elif "CL" in formula_upper:
        return "chloride"
    elif "PO4" in formula_upper or "PO)4" in formula_upper:
        return "phosphate"
    elif "SO4" in formula_upper:
        return "sulfate"
    elif formula.endswith("O") or "O2" in formula or "O3" in formula or "O4" in formula:
        return "oxide"
    else:
        return "other"


def _select_precursors(
    composition: Any,
    composition_str: str,
    method: str,
    exclude_forms: List[str],
    prefer_forms: List[str]
) -> Dict[str, Any]:
    """Select appropriate precursors for each element using Materials Project data."""
    
    precursor_sets = []
    warnings = []
    
    # Query MP for precursors
    mp_result = _query_mp_precursors(composition_str)
    
    if not mp_result["success"]:
        return {
            "success": False,
            "error": mp_result["error"],
            "warnings": warnings
        }
    
    PRECURSOR_DATABASE = mp_result["precursor_database"]
    warnings.append(f"Using {mp_result['total_recipes']} recipes from Materials Project")
    
    # Get element:amount mapping
    elem_amounts = composition.get_el_amt_dict()
    
    # Select precursors for each element
    element_precursor_options = {}
    
    for elem_symbol, amount in elem_amounts.items():
        if elem_symbol == "O":
            # Oxygen typically comes from air or is already in precursors
            continue
        
        if elem_symbol not in PRECURSOR_DATABASE:
            return {
                "success": False,
                "error": f"No precursors available for element: {elem_symbol} in Materials Project data for {composition_str}",
                "warnings": warnings
            }
        
        available_precursors = PRECURSOR_DATABASE[elem_symbol]
        
        if not available_precursors:
            warnings.append(f"Element {elem_symbol} has no common precursors in Materials Project data")
            continue
        
        # Filter precursors based on constraints
        filtered = []
        for prec in available_precursors:
            if prec["form"] in exclude_forms:
                continue
            filtered.append(prec)
        
        if not filtered:
            filtered = available_precursors  # Use all if filtering removes everything
        
        # Prefer certain forms if specified
        if prefer_forms:
            preferred = [p for p in filtered if p["form"] in prefer_forms]
            if preferred:
                filtered = preferred
        
        # For solid-state, prefer oxides and carbonates
        if method == "solid_state":
            pref = [p for p in filtered if p["form"] in ["oxide", "carbonate"]]
            if pref:
                filtered = pref
        
        # For hydrothermal, prefer nitrates and chlorides
        elif method == "hydrothermal":
            pref = [p for p in filtered if p["form"] in ["nitrate", "chloride"]]
            if pref:
                filtered = pref
        
        element_precursor_options[elem_symbol] = filtered
    
    # Generate precursor set (take first option for each element for MVP)
    precursor_set = {}
    for elem_symbol, options in element_precursor_options.items():
        if options:
            precursor_set[elem_symbol] = options[0]  # Pick most common/preferred
    
    # Calculate stoichiometry
    precursor_set_with_amounts = []
    for elem_symbol, precursor in precursor_set.items():
        target_amount = elem_amounts[elem_symbol]
        
        # Calculate molar ratio (simplified - assumes direct conversion)
        molar_ratio = _calculate_precursor_amount(
            precursor["compound"],
            elem_symbol,
            target_amount
        )
        
        precursor_set_with_amounts.append({
            "element": elem_symbol,
            "compound": precursor["compound"],
            "form": precursor["form"],
            "purity": precursor["purity"],
            "formula_amount": molar_ratio,
            "target_element_amount": target_amount
        })
    
    precursor_sets.append(precursor_set_with_amounts)
    
    return {
        "success": True,
        "precursor_sets": precursor_sets,
        "warnings": warnings
    }


def _calculate_precursor_amount(compound: str, target_element: str, target_amount: float) -> float:
    """Calculate required amount of precursor compound."""
    try:
        from pymatgen.core import Composition
        
        precursor_comp = Composition(compound)
        elem_in_precursor = precursor_comp.get_el_amt_dict().get(target_element, 0)
        
        if elem_in_precursor == 0:
            return target_amount  # Fallback
        
        # Molar ratio to provide target amount of element
        return target_amount / elem_in_precursor
    except:
        return target_amount  # Fallback


def _generate_solid_state_route(
    composition: Any,
    precursors: List[Dict],
    max_temp: float,
    max_time: float
) -> Dict[str, Any]:
    """Generate solid-state synthesis route."""
    
    # Estimate calcination temperature based on composition
    calc_temp = _estimate_calcination_temperature(composition, max_temp)
    
    # Estimate time based on complexity, accounting for all process steps
    n_elements = len(composition.elements)
    grinding_time = 0.5  # 30 min
    ramp_time = calc_temp / 5 / 60  # hours at 5°C/min
    cool_time = 4  # hours
    fixed_times = grinding_time + ramp_time + cool_time
    
    # Calculate available time for calcination hold
    available_hold_time = max_time - fixed_times
    
    # Desired hold time based on complexity
    desired_hold_time = 12 + (n_elements - 2) * 4
    
    # Use the minimum of desired and available
    calc_time = max(1, min(desired_hold_time, available_hold_time))  # At least 1 hour
    
    steps = [
        {
            "step": 1,
            "action": "mix_and_grind",
            "description": "Thoroughly mix precursors in stoichiometric ratio using mortar and pestle",
            "duration": "30 min",
            "equipment": "mortar_and_pestle",
            "notes": "Grind until homogeneous powder is obtained"
        },
        {
            "step": 2,
            "action": "pelletize",
            "description": "Press mixed powder into pellet",
            "pressure": "5-10 tons",
            "equipment": "hydraulic_press",
            "notes": "Optional: improves reaction kinetics"
        },
        {
            "step": 3,
            "action": "calcine",
            "description": f"Heat to {calc_temp}°C in furnace",
            "temperature_c": calc_temp,
            "ramp_rate": "5°C/min",
            "hold_time_h": calc_time,
            "atmosphere": "air",
            "equipment": "box_furnace",
            "notes": f"Ramp: {calc_temp/5:.0f} min, Hold: {calc_time} h"
        },
        {
            "step": 4,
            "action": "cool",
            "description": "Cool to room temperature",
            "rate": "furnace_cool",
            "duration_h": 4,
            "notes": "Natural cooling rate ~50°C/h"
        }
    ]
    
    total_time = grinding_time + ramp_time + calc_time + cool_time
    
    # Calculate feasibility score
    feasibility = _calculate_feasibility(
        "solid_state",
        precursors,
        calc_temp,
        max_temp,
        total_time,
        max_time
    )
    
    return {
        "method": "solid_state",
        "confidence": 0.75,  # Base confidence for solid-state
        "precursors": precursors,
        "steps": steps,
        "total_time_estimate": f"~{total_time:.0f} hours",
        "feasibility_score": feasibility,
        "basis": "Template-based solid-state synthesis for ceramic oxides",
        "temperature_range": f"{calc_temp}°C (high temperature)",
        "atmosphere_required": "Air (oxidizing)"
    }


def _generate_solgel_route(
    composition: Any,
    precursors: List[Dict],
    max_temp: float,
    max_time: float
) -> Dict[str, Any]:
    """Generate sol-gel synthesis route."""
    
    # Estimate temperatures based on composition
    decomp_temp, calc_temp = _estimate_solgel_temperatures(composition, max_temp)
    
    # Time estimates based on composition complexity
    n_elements = len(composition.elements)
    gel_formation_time = 4 + (n_elements - 3) * 1  # More complex = longer gelation
    drying_time = 12  # Standard drying time
    decomp_time = 2  # Standard decomposition time
    calc_time = 4 + (n_elements - 2) * 1  # More complex = longer calcination
    
    # Ensure calc_time fits within max_time
    available_time = max_time - (gel_formation_time + drying_time + decomp_time + 3)
    calc_time = max(2, min(calc_time, available_time))
    
    steps = [
        {
            "step": 1,
            "action": "prepare_solution",
            "description": "Dissolve metal precursors (nitrates preferred) in deionized water or ethanol",
            "solvent": "H2O or EtOH",
            "stirring": "magnetic stirrer",
            "temperature_c": 60,
            "equipment": "beaker",
            "notes": "Use nitrates or alkoxides for sol-gel; heat gently to aid dissolution"
        },
        {
            "step": 2,
            "action": "add_chelating_agent",
            "description": "Add citric acid or EDTA as chelating/gelling agent",
            "agent": "citric acid",
            "molar_ratio": "1:1 to 2:1 (agent:metal ions)",
            "notes": "Chelating agent promotes molecular-level mixing and gel formation"
        },
        {
            "step": 3,
            "action": "evaporate_and_gel",
            "description": "Heat at 80-100°C with stirring to evaporate solvent and form gel",
            "temperature_c": 90,
            "duration_h": gel_formation_time,
            "equipment": "hotplate",
            "notes": "Solution becomes viscous gel; continue heating until gel forms"
        },
        {
            "step": 4,
            "action": "dry_gel",
            "description": "Dry gel at 120-150°C to remove residual solvent",
            "temperature_c": 120,
            "duration_h": drying_time,
            "equipment": "oven",
            "notes": "Forms porous xerogel; avoid cracking by slow heating"
        },
        {
            "step": 5,
            "action": "decompose",
            "description": f"Heat to {decomp_temp}°C to decompose organic components",
            "temperature_c": decomp_temp,
            "ramp_rate": "2-5°C/min",
            "hold_time_h": decomp_time,
            "atmosphere": "air",
            "equipment": "furnace",
            "notes": "Burns off organic chelating agents, forms amorphous oxide precursor"
        },
        {
            "step": 6,
            "action": "calcine",
            "description": f"Final calcination at {calc_temp}°C to crystallize product",
            "temperature_c": calc_temp,
            "ramp_rate": "5°C/min",
            "hold_time_h": calc_time,
            "atmosphere": "air",
            "equipment": "furnace",
            "notes": f"Crystallizes final phase; lower temp than solid-state ({calc_temp}°C vs 900-1200°C)"
        },
        {
            "step": 7,
            "action": "cool",
            "description": "Cool to room temperature",
            "rate": "furnace_cool",
            "duration_h": 3
        }
    ]
    
    total_time = gel_formation_time + drying_time + decomp_time + calc_time + 3
    
    feasibility = _calculate_feasibility(
        "sol_gel",
        precursors,
        calc_temp,
        max_temp,
        total_time,
        max_time
    )
    
    return {
        "method": "sol_gel",
        "confidence": 0.70,
        "precursors": precursors,
        "steps": steps,
        "total_time_estimate": f"~{total_time:.0f} hours",
        "feasibility_score": feasibility,
        "basis": "Template-based sol-gel synthesis for homogeneous mixed oxides",
        "temperature_range": f"{decomp_temp}-{calc_temp}°C (moderate temperature)",
        "atmosphere_required": "Air",
        "advantages": "Molecular-level mixing, lower calcination temperature, fine particle size"
    }


def _generate_hydrothermal_route(
    composition: Any,
    precursors: List[Dict],
    max_temp: float,
    max_time: float
) -> Dict[str, Any]:
    """Generate hydrothermal synthesis route."""
    
    # Estimate temperature based on composition
    hydro_temp = _estimate_hydrothermal_temperature(composition, max_temp)
    
    # Time estimates based on composition complexity
    n_elements = len(composition.elements)
    base_time = 24
    # More complex compositions need longer crystallization
    adjusted_time = base_time + (n_elements - 2) * 4
    hydro_time = min(adjusted_time, max_time - 15)  # Reserve time for cooling + drying
    
    steps = [
        {
            "step": 1,
            "action": "prepare_solution",
            "description": "Dissolve precursors in deionized water",
            "solvent": "H2O",
            "volume": "50-100 mL",
            "equipment": "beaker",
            "notes": "Stir until fully dissolved, adjust pH if needed"
        },
        {
            "step": 2,
            "action": "transfer_autoclave",
            "description": "Transfer solution to Teflon-lined autoclave",
            "fill_ratio": "50-80%",
            "equipment": "autoclave",
            "notes": "Do not overfill to prevent pressure buildup"
        },
        {
            "step": 3,
            "action": "hydrothermal_treatment",
            "description": f"Heat autoclave to {hydro_temp}°C",
            "temperature_c": hydro_temp,
            "duration_h": hydro_time,
            "pressure": "autogenous",
            "equipment": "oven",
            "notes": f"Sealed system, pressure self-generates"
        },
        {
            "step": 4,
            "action": "cool",
            "description": "Cool autoclave to room temperature",
            "rate": "natural",
            "duration_h": 2
        },
        {
            "step": 5,
            "action": "wash_and_dry",
            "description": "Filter, wash with water and ethanol, dry at 80°C",
            "washing": "H2O + EtOH",
            "drying_temp_c": 80,
            "drying_time_h": 12,
            "notes": "Wash until neutral pH"
        }
    ]
    
    total_time = 1 + hydro_time + 2 + 12  # prep + hydrothermal + cool + dry
    
    feasibility = _calculate_feasibility(
        "hydrothermal",
        precursors,
        hydro_temp,
        max_temp,
        total_time,
        max_time
    )
    
    return {
        "method": "hydrothermal",
        "confidence": 0.70,  # Slightly lower base confidence
        "precursors": precursors,
        "steps": steps,
        "total_time_estimate": f"~{total_time:.0f} hours",
        "feasibility_score": feasibility,
        "basis": "Template-based hydrothermal synthesis",
        "temperature_range": f"{hydro_temp}°C (low temperature)",
        "atmosphere_required": "Sealed autoclave (autogenous pressure)"
    }


def _estimate_calcination_temperature(composition: Any, max_temp: float) -> float:
    """Estimate appropriate calcination temperature for solid-state synthesis."""
    
    # Base temperature for simple oxides
    base_temp = 800
    
    # Adjust based on composition complexity
    n_elements = len(composition.elements)
    
    # More elements typically need higher temperature for thorough mixing
    temp = base_temp + (n_elements - 2) * 50
    
    # Check for elements that need higher temperatures
    high_temp_elements = {"Si", "Ti", "Zr", "Al", "Mg"}
    if any(elem.symbol in high_temp_elements for elem in composition.elements):
        temp += 100
    
    # Check for elements that need lower temperatures
    low_temp_elements = {"Li", "Na", "K"}
    if any(elem.symbol in low_temp_elements for elem in composition.elements):
        temp -= 100
    
    # Clamp to reasonable range
    temp = max(600, min(temp, max_temp, 1200))
    
    # Round to nearest 50
    return round(temp / 50) * 50


def _estimate_solgel_temperatures(composition: Any, max_temp: float) -> Tuple[float, float]:
    """Estimate decomposition and calcination temperatures for sol-gel synthesis."""
    
    # Base temperatures for sol-gel
    decomp_temp = 400  # Organic decomposition
    calc_temp = 650    # Crystallization
    
    # Adjust based on composition
    # Rare earth oxides need higher calcination temperatures
    rare_earths = {"La", "Ce", "Pr", "Nd", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu", "Y"}
    if any(elem.symbol in rare_earths for elem in composition.elements):
        calc_temp += 100
    
    # Refractory elements need higher temperatures
    refractory_elements = {"Si", "Ti", "Zr", "Al"}
    if any(elem.symbol in refractory_elements for elem in composition.elements):
        calc_temp += 100
        decomp_temp += 50
    
    # Alkali metals need lower temperatures to prevent volatilization
    alkali_elements = {"Li", "Na", "K"}
    if any(elem.symbol in alkali_elements for elem in composition.elements):
        calc_temp -= 100
        decomp_temp -= 50
    
    # Adjust for composition complexity
    n_elements = len(composition.elements)
    if n_elements >= 4:
        calc_temp += 50  # Complex compositions need slightly higher temp
    
    # Clamp to reasonable ranges
    decomp_temp = max(300, min(decomp_temp, 500))
    calc_temp = max(500, min(calc_temp, max_temp, 900))
    
    # Round to nearest 50
    decomp_temp = round(decomp_temp / 50) * 50
    calc_temp = round(calc_temp / 50) * 50
    
    return decomp_temp, calc_temp


def _estimate_hydrothermal_temperature(composition: Any, max_temp: float) -> float:
    """Estimate hydrothermal reaction temperature based on composition."""
    
    # Base temperature for hydrothermal synthesis
    base_temp = 180
    
    # Phosphates typically synthesize at lower temperatures
    if any(elem.symbol == "P" for elem in composition.elements):
        base_temp = 160
    
    # Fluorides prefer lower temperatures
    elif any(elem.symbol == "F" for elem in composition.elements):
        base_temp = 140
    
    # Vanadates, molybdates, tungstates need higher temperatures
    high_temp_anions = {"V", "Mo", "W"}
    if any(elem.symbol in high_temp_anions for elem in composition.elements):
        base_temp = 210
    
    # Transition metals generally work well at moderate temperatures
    transition_metals = {"Ti", "Zr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn"}
    if any(elem.symbol in transition_metals for elem in composition.elements):
        base_temp = 180
    
    # Complex compositions may benefit from slightly higher temperature
    n_elements = len(composition.elements)
    if n_elements >= 4:
        base_temp += 20
    
    # Clamp to hydrothermal range and respect max_temp
    temp = max(120, min(base_temp, max_temp, 250))
    
    # Round to nearest 10
    return round(temp / 10) * 10


def _calculate_feasibility(
    method: str,
    precursors: List[Dict],
    temperature: float,
    max_temp: float,
    time: float,
    max_time: float
) -> float:
    """Calculate feasibility score for a synthesis route."""
    
    score = 1.0
    
    # Penalize if approaching temperature limits
    if temperature > max_temp * 0.9:
        score -= 0.2
    
    # Penalize if approaching time limits
    if time > max_time * 0.9:
        score -= 0.2
    
    # Reward common precursors
    common_count = sum(1 for p in precursors if p.get("form") in ["oxide", "carbonate", "nitrate"])
    score += 0.05 * common_count
    
    # Penalize for low availability precursors
    # (future: could integrate cost/availability data)
    
    # Clamp to [0, 1]
    return max(0.0, min(1.0, score))
