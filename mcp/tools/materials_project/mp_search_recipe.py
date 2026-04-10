"""
Tool for searching synthesis recipes from Materials Project Synthesis Explorer.
Retrieves literature-derived synthesis procedures for inorganic materials.
Requires MP_API_KEY environment variable with your Materials Project API key.
"""

from typing import List, Dict, Any, Optional, Annotated
from pydantic import Field
from mp_api.client import MPRester
import os
import re
from utils.literature_utils import get_paper_metadata_from_doi


def mp_search_recipe(
    target_formula: Annotated[
        Optional[str | List[str]],
        Field(
            default=None,
            description="Target material formula(s) to find synthesis recipes for. "
            "Can be a single formula (e.g., 'LiFePO4') or list of formulas (e.g., ['LiCoO2', 'LiMn2O4']). "
            "Use reduced formulas without charge."
        )
    ] = None,
    precursor_formulas: Annotated[
        Optional[str | List[str]],
        Field(
            default=None,
            description="Search by precursor/starting material formula(s). "
            "Examples: 'Li2CO3', 'Fe2O3', or ['Li2CO3', 'FePO4']. "
            "Finds recipes that use these specific precursors."
        )
    ] = None,
    elements: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description="Filter recipes by required elements in target product. "
            "Examples: ['Li', 'Fe', 'P', 'O'] for lithium iron phosphate compounds. "
            "Use element symbols."
        )
    ] = None,
    keywords: Annotated[
        Optional[str | List[str]],
        Field(
            default=None,
            description="Search by synthesis method keywords or conditions. "
            "Examples: 'solid-state', 'hydrothermal', 'sol-gel', 'ball-milled', "
            "'calcination', 'microwave', 'high-temperature', 'ambient', 'impurities'. "
            "Can be single keyword or list."
        )
    ] = None,
    synthesis_type: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Filter by reaction/synthesis type. "
            "Common types: 'solid_state', 'solution', 'hydrothermal', 'solvothermal', "
            "'sol_gel', 'combustion', 'precipitation', 'coprecipitation', 'melting'."
        )
    ] = None,
    temperature_min: Annotated[
        Optional[float],
        Field(
            default=None,
            ge=0,
            description="Minimum synthesis temperature in Celsius. "
            "Examples: 600 for high-temperature solid-state, 150 for hydrothermal."
        )
    ] = None,
    temperature_max: Annotated[
        Optional[float],
        Field(
            default=None,
            ge=0,
            description="Maximum synthesis temperature in Celsius. "
            "Use to find low-temperature synthesis routes."
        )
    ] = None,
    heating_time_min: Annotated[
        Optional[float],
        Field(
            default=None,
            ge=0,
            description="Minimum heating/reaction time in hours. "
            "Use to find synthesis protocols with minimum required heating duration (e.g., heating_time_min=2 for > 2 hours)."
        )
    ] = None,
    heating_time_max: Annotated[
        Optional[float],
        Field(
            default=None,
            ge=0,
            description="Maximum heating/reaction time in hours. "
            "Use to find fast synthesis protocols (e.g., heating_time_max=2 for < 2 hours)."
        )
    ] = None,
    year_min: Annotated[
        Optional[int],
        Field(
            default=None,
            ge=1900,
            le=2030,
            description="Filter by publication year (minimum). "
            "Examples: 2020 for recent recipes, 2015 for last decade."
        )
    ] = None,
    doi: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Filter by specific DOI (Digital Object Identifier) of publication. "
            "Example: '10.1021/jacs.5b00620'"
        )
    ] = None,
    limit: Annotated[
        int,
        Field(
            default=10,
            ge=1,
            le=30,
            description="Maximum number of synthesis recipes to return (1-30). "
            "Use smaller values where possible to reduce query time. Default: 10."
        )
    ] = 10,
    fields: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description="Specific fields to return in recipe data. "
            "Available fields: 'target', 'precursors', 'operations', 'conditions', "
            "'temperature', 'time', 'atmosphere', 'product_characterization', "
            "'doi', 'citation', 'year'. "
            "If None, returns all available fields."
        )
    ] = None,
    format_routes: Annotated[
        bool,
        Field(
            default=False,
            description="If True, automatically converts MP recipes to standardized synthesis routes. "
            "Requires target_formula to be provided (uses first formula if list)."
        )
    ] = False
) -> Dict[str, Any]:
    """
    Search Materials Project Synthesis Explorer for experimental synthesis recipes.
    
    Retrieves real-world, literature-derived synthesis procedures for inorganic/solid-state
    materials extracted from research papers. Each recipe includes target materials,
    precursors, reaction conditions, temperatures, times, and literature citations.
    
    Routes from this tool have high confidence because they are based on actual published 
    experimental procedures.
    
    Use this tool to:
        - Find proven synthesis routes for specific materials
        - Discover alternative synthesis methods from literature
        - Identify required precursors and conditions
        - Access original research papers via DOI
        - Compare synthesis approaches from different sources
    
    Search Strategies:
        1. By target material: target_formula="LiFePO4"
        2. By precursors: precursor_formulas=["Li2CO3", "FeC2O4"]
        3. By elements: elements=["Li", "Co", "O"] 
        4. By method: keywords="hydrothermal", temperature_max=200
        5. By recent literature: year_min=2020
        6. Fast synthesis: heating_time_max=5, temperature_max=800
    
    Common Applications:
        - Battery material synthesis (LiCoO2, LiFePO4, etc.)
        - Catalyst preparation
        - Ceramic processing
        - Novel material exploration
        - Process optimization
    
    Examples:
        Find LiFePO4 synthesis routes:
            target_formula="LiFePO4", limit=10
        
        Find low-temperature hydrothermal methods:
            keywords="hydrothermal", temperature_max=250
        
        Find recent solid-state recipes:
            keywords="solid-state", year_min=2018
        
        Find recipes using specific precursor:
            precursor_formulas="Li2CO3"
    
    Args:
        target_formula: Target material formula(s) to synthesize
        precursor_formulas: Starting material/precursor formula(s)
        elements: Required elements in target product
        keywords: Synthesis method keywords or conditions
        synthesis_type: Type of synthesis reaction
        temperature_min: Minimum synthesis temperature (°C)
        temperature_max: Maximum synthesis temperature (°C)
        heating_time_min: Minimum heating time (hours)
        heating_time_max: Maximum heating time (hours)
        year_min: Minimum publication year
        doi: Specific publication DOI
        limit: Maximum number of recipes to return (1-30)
        fields: Specific data fields to return
        format_routes: If True, converts recipes to standardized route format (uses target_formula)
    
    Returns:
        Dictionary containing:
            - success: Boolean indicating if search succeeded
            - query: Original search parameters used
            - count: Number of recipes found
            - recipes: List of synthesis recipe dictionaries, each containing:
                - target: Target material(s) produced
                - target_formula: Chemical formula of target
                - precursors: List of starting materials/precursors
                - operations: Synthesis steps/procedures
                - conditions: Reaction conditions (temperature, time, atmosphere, etc.)
                - temperature_celsius: Synthesis temperature
                - heating_time_hours: Heating/reaction duration
                - atmosphere: Reaction atmosphere (air, N2, vacuum, etc.)
                - product_info: Characterization/purity information
                - doi: Publication DOI
                - citation: Full citation
                - year: Publication year
                - recipe_id: Unique identifier
            - warnings: List of any warnings or notes
            - error: Error message if search failed
    """
    try:
        # Get API key from environment variable
        api_key = os.getenv("MP_API_KEY")
        if not api_key:
            error_msg = "MP_API_KEY environment variable not set. Get your API key from https://materialsproject.org/api"
            return {
                "success": False,
                "query": {},
                "count": 0,
                "recipes": [],
                "error": error_msg
            }
        
        # Normalize inputs
        if isinstance(target_formula, str):
            target_formula = [target_formula]
        if isinstance(precursor_formulas, str):
            precursor_formulas = [precursor_formulas]
        if isinstance(keywords, str):
            keywords = [keywords]
        
        # Build query parameters
        query_params = {}
        
        if target_formula:
            query_params["target_formula"] = target_formula
        if precursor_formulas:
            query_params["precursor_formulas"] = precursor_formulas
        if elements:
            query_params["elements"] = elements
        if keywords:
            query_params["keywords"] = keywords
        if synthesis_type:
            query_params["synthesis_type"] = synthesis_type
        if temperature_min is not None:
            query_params["temperature_min"] = temperature_min
        if temperature_max is not None:
            query_params["temperature_max"] = temperature_max
        if heating_time_min is not None:
            query_params["heating_time_min"] = heating_time_min
        if heating_time_max is not None:
            query_params["heating_time_max"] = heating_time_max
        if year_min is not None:
            query_params["year_min"] = year_min
        if doi:
            query_params["doi"] = doi
        
        if not query_params:
            return {
                "success": False,
                "query": {},
                "count": 0,
                "recipes": [],
                "error": "At least one search criterion must be provided (target_formula, precursor_formulas, elements, keywords, etc.)"
            }
        
        # Initialize Materials Project API client
        with MPRester(api_key) as mpr:
            try:
                if mpr.materials and hasattr(mpr.materials, 'synthesis'):

                    search_kwargs = {}
                    # target_formula: accepts single string only
                    if target_formula:
                        search_kwargs['target_formula'] = target_formula[0] if isinstance(target_formula, list) else target_formula
                    
                    # precursor_formula: accepts single string only
                    if precursor_formulas:
                        search_kwargs['precursor_formula'] = precursor_formulas[0] if isinstance(precursor_formulas, list) else precursor_formulas
                    
                    # keywords: accepts list[str]
                    if keywords:
                        if isinstance(keywords, str):
                            search_kwargs['keywords'] = [keywords]
                        else:
                            search_kwargs['keywords'] = keywords
                    
                    # synthesis_type parameter
                    if synthesis_type:
                        search_kwargs['synthesis_type'] = [synthesis_type]
                    
                    # Temperature parameters need condition_heating_ prefix
                    if temperature_min is not None:
                        search_kwargs['condition_heating_temperature_min'] = temperature_min
                    
                    if temperature_max is not None:
                        search_kwargs['condition_heating_temperature_max'] = temperature_max
                    
                    # Time parameters need condition_heating_ prefix
                    if heating_time_min is not None:
                        search_kwargs['condition_heating_time_min'] = heating_time_min
                    
                    if heating_time_max is not None:
                        search_kwargs['condition_heating_time_max'] = heating_time_max
                    
                    results = mpr.materials.synthesis.search(**search_kwargs, num_chunks=limit)
                    
                else:
                    return {
                        "success": False,
                        "query": query_params,
                        "count": 0,
                        "recipes": [],
                        "error": "Synthesis recipe search is not available in the current Materials Project API version. "
                                "This feature may require MP API v0.38.0+ or special access. "
                                "Available endpoints: " + str([attr for attr in dir(mpr) if not attr.startswith('_')][:20]),
                        "help": "The Materials Project Synthesis Explorer may require special API access. "
                               "Contact Materials Project support or check https://docs.materialsproject.org/"
                    }
                
                if not isinstance(results, list):
                    results = list(results)
                
                # Process and format results
                recipes = []
                for i, result in enumerate(results[:limit]):
                    recipe = {}
                    
                    # Extract standard fields
                    if hasattr(result, 'dict'):
                        result_dict = result.dict()
                    elif isinstance(result, dict):
                        result_dict = result
                    else:
                        result_dict = vars(result)
                    
                    # Map fields to standardized output
                    recipe['recipe_id'] = result_dict.get('synthesis_id') or result_dict.get('id') or f"recipe_{i+1}"
                    
                    # Target information
                    recipe['target'] = result_dict.get('target')
                    target_obj = result_dict.get('target', {})
                    if target_obj:
                        recipe['target_formula'] = target_obj.get('material_formula')
                    else:
                        recipe['target_formula'] = None
                    
                    # Precursors
                    recipe['precursors'] = result_dict.get('precursors') or []
                    
                    # Synthesis steps/operations
                    recipe['operations'] = result_dict.get('operations') or []
                    
                    # Extract temperature and time from operations
                    temp_celsius = None
                    time_hours = None
                    atmosphere = None
                    
                    operations = recipe['operations']
                    if operations and isinstance(operations, list):
                        for op in operations:
                            if isinstance(op, dict):
                                conditions = op.get('conditions', {})
                                
                                # Extract temperature from heating operations
                                if 'heating_temperature' in conditions:
                                    temp_list = conditions['heating_temperature']
                                    if temp_list and isinstance(temp_list, list):
                                        for temp_data in temp_list:
                                            if isinstance(temp_data, dict):
                                                temp_val = temp_data.get('min_value') or temp_data.get('max_value')
                                                if temp_val and temp_val > (temp_celsius or 0):
                                                    temp_celsius = temp_val
                                
                                # Extract heating time
                                if 'heating_time' in conditions:
                                    time_list = conditions['heating_time']
                                    if time_list and isinstance(time_list, list):
                                        for time_data in time_list:
                                            if isinstance(time_data, dict):
                                                time_val = time_data.get('min_value') or time_data.get('max_value')
                                                time_unit = time_data.get('units', 'hours')
                                                if time_val:
                                                    # Convert to hours
                                                    if time_unit in ['h', 'hours', 'hour']:
                                                        time_hours = (time_hours or 0) + time_val
                                                    elif time_unit in ['day', 'days']:
                                                        time_hours = (time_hours or 0) + (time_val * 24)
                                                    elif time_unit in ['min', 'minutes', 'minute']:
                                                        time_hours = (time_hours or 0) + (time_val / 60)
                                
                                # Extract atmosphere
                                if 'heating_atmosphere' in conditions:
                                    atm_list = conditions['heating_atmosphere']
                                    if atm_list and isinstance(atm_list, list) and len(atm_list) > 0:
                                        atmosphere = atm_list[0]
                    
                    # Conditions
                    recipe['conditions'] = {}
                    recipe['temperature_celsius'] = temp_celsius
                    recipe['heating_time_hours'] = time_hours
                    recipe['atmosphere'] = atmosphere or 'not specified'
                    
                    # Publication information
                    recipe['product_info'] = result_dict.get('paragraph_string')
                    recipe['doi'] = result_dict.get('doi')
                    recipe['citation'] = result_dict.get('citation') or result_dict.get('reference')
                    
                    # Extract year from DOI if not directly available
                    year = result_dict.get('year') or result_dict.get('publication_year')
                    if not year and recipe['doi']:
                        # Try extracting year from DOI pattern first
                        # Examples: 10.1016/j.matlet.2012.04.115 -> 2012
                        year_match = re.search(r'[./\-](19\d{2}|20\d{2})(?=[./\-])', recipe['doi'])
                        if year_match:
                            year = int(year_match.group(1))
                        
                        # If pattern matching failed, try CrossRef API as fallback
                        if not year and get_paper_metadata_from_doi is not None:
                            try:
                                doi_metadata = get_paper_metadata_from_doi(recipe['doi'])
                                if doi_metadata and doi_metadata.get('year'):
                                    year = doi_metadata['year']
                            except Exception:
                                # Silently fail - year will remain None
                                pass
                    recipe['year'] = year
                    
                    # Additional fields
                    recipe['synthesis_type'] = result_dict.get('synthesis_type')
                    
                    if fields:
                        recipe = {k: v for k, v in recipe.items() if k in fields or k == 'recipe_id'}
                    
                    recipes.append(recipe)
                
                # Track counts for accurate warnings
                total_before_filtering = len(recipes)
                
                # Apply client-side filtering (MP API doesn't always filter correctly)
                filtered_recipes = recipes

                # Filter by year_min if specified
                # Only filter out recipes with known years that are too old
                # Keep recipes where year cannot be determined
                if year_min is not None:
                    filtered_recipes = [
                        r for r in filtered_recipes 
                        if r.get('year') is None or r['year'] >= year_min
                    ]
                
                # Use filtered recipes
                recipes = filtered_recipes
                num_filtered_out = total_before_filtering - len(recipes)
                
                warnings = []
                if len(results) > limit:
                    warnings.append(f"Found {len(results)} total results in database, but limited to {limit}. Increase 'limit' parameter to see more.")
                
                if num_filtered_out > 0:
                    warnings.append(f"Filtered out {num_filtered_out} recipe(s) that didn't match client-side filtering criteria (e.g., year constraints).")
                
                if len(recipes) == 0:
                    if num_filtered_out > 0:
                        warnings.append("All recipes were filtered out. Try broadening your search criteria (e.g., lower year_min).")
                    else:
                        warnings.append("No synthesis recipes found matching the search criteria. Try broadening your search or using different keywords.")
                
                # Build base result
                base_result = {
                    "success": True,
                    "query": query_params,
                    "count": len(recipes),
                    "recipes": recipes,
                    "warnings": warnings if warnings else None,
                    "message": f"Found {len(recipes)} synthesis recipe(s) matching search criteria"
                }
                
                # Apply route formatting if requested
                if format_routes:
                    # Auto-infer target_composition from target_formula
                    if not target_formula:
                        return {
                            "success": False,
                            "query": query_params,
                            "count": len(recipes),
                            "recipes": recipes,
                            "error": "target_formula must be provided when format_routes=True"
                        }
                    
                    # Use first formula if list, otherwise use the string
                    target_composition = target_formula[0] if isinstance(target_formula, list) else target_formula
                    
                    routes = []
                    filtered_count = 0
                    conversion_warnings = []
                    
                    
                    for idx, recipe in enumerate(recipes, 1):
                        try:
                            # Extract basic information
                            temperature = recipe.get("temperature_celsius")
                            time_hours = recipe.get("heating_time_hours")
                            
                            # Extract precursors
                            precursors_data = recipe.get("precursors", [])
                            precursors = _extract_precursors(precursors_data)
                            
                            # Extract synthesis steps
                            operations = recipe.get("operations")
                            steps = _extract_steps(operations, temperature, time_hours)
                            
                            # Determine synthesis method
                            method = _infer_synthesis_method(recipe)
                            
                            # Calculate scores
                            confidence = 0.90  # Literature routes have high confidence
                            feasibility = _calculate_feasibility_score(
                                temperature or 800,
                                time_hours or 12,
                                temperature_max or float('inf'),
                                heating_time_max or float('inf')
                            )
                            
                            # Build standardized route
                            route = {
                                "route_id": idx,
                                "source": "literature",
                                "method": method,
                                "confidence": confidence,
                                "feasibility_score": feasibility,
                                "precursors": precursors,
                                "steps": steps,
                                "temperature_range": f"{temperature}°C" if temperature else "See steps",
                                "total_time_estimate": f"~{time_hours:.1f} hours" if time_hours else "See steps",
                                "atmosphere_required": recipe.get("atmosphere") or "not specified",
                                "basis": "Literature-derived from Materials Project",
                                "citation": recipe.get("citation"),
                                "doi": recipe.get("doi"),
                                "year": recipe.get("year"),
                                "recipe_id": recipe.get("recipe_id")
                            }
                            
                            routes.append(route)
                            
                        except Exception as e:
                            conversion_warnings.append(f"Failed to convert recipe {idx}: {str(e)}")
                            continue
                    
                    # Return formatted routes
                    if not routes:
                        return {
                            "success": False,
                            "target_composition": target_composition,
                            "n_routes": 0,
                            "routes": [],
                            "filtered_count": filtered_count,
                            "error": "No recipes could be converted. Check constraints or recipe format.",
                            "warnings": conversion_warnings + (warnings or [])
                        }
                    
                    return {
                        "success": True,
                        "target_composition": target_composition,
                        "n_routes": len(routes),
                        "routes": routes,
                        "filtered_count": filtered_count,
                        "original_count": len(recipes),
                        "warnings": (conversion_warnings + (warnings or [])) if conversion_warnings or warnings else None,
                        "message": f"Successfully converted {len(routes)} recipe(s) to standardized routes"
                    }
                
                return base_result
                
            except AttributeError as e:
                return {
                    "success": False,
                    "query": query_params,
                    "count": 0,
                    "recipes": [],
                    "error": f"Synthesis recipe endpoint not available: {str(e)}. "
                            "This may require MP API version 0.38.0+ or special access permissions.",
                    "help": "Check Materials Project API documentation or contact support for synthesis data access."
                }
                
    except Exception as e:
        return {
            "success": False,
            "query": query_params if 'query_params' in locals() else {},
            "count": 0,
            "recipes": [],
            "error": f"Unexpected error searching synthesis recipes: {str(e)}"
        }



def _extract_precursors(precursors_data: Any) -> List[Dict[str, Any]]:
    """Extract and standardize precursor information."""
    precursors = []
    
    if not precursors_data:
        return precursors
    
    if isinstance(precursors_data, list):
        for prec in precursors_data:
            if isinstance(prec, dict):
                # Handle MP format (material_formula, material_string, etc.)
                compound = (
                    prec.get("material_formula") or 
                    prec.get("formula") or 
                    prec.get("name") or 
                    prec.get("material_string") or 
                    str(prec)
                )
                
                precursors.append({
                    "compound": compound,
                    "amount": prec.get("amount"),
                    "form": prec.get("form") or prec.get("material_name") or "unspecified",
                    "purity": prec.get("purity")
                })
            elif isinstance(prec, str):
                precursors.append({
                    "compound": prec,
                    "amount": None,
                    "form": "unspecified",
                    "purity": None
                })
            else:
                precursors.append({
                    "compound": str(prec),
                    "amount": None,
                    "form": "unspecified",
                    "purity": None
                })
    
    return precursors


def _extract_steps(operations: Any, temperature: Optional[float], time_hours: Optional[float]) -> List[Dict[str, Any]]:
    """Extract and standardize synthesis steps from operations."""
    steps = []
    
    if operations:
        if isinstance(operations, str):
            # Parse string description into steps
            steps = _parse_operations_string(operations, temperature, time_hours)
        elif isinstance(operations, list):
            # List of operation dictionaries (MP format)
            for i, op in enumerate(operations, 1):
                if isinstance(op, dict):
                    # Extract conditions from MP format
                    conditions = op.get("conditions", {})
                    
                    # Get temperature from conditions or top level
                    temp_data = conditions.get("heating_temperature", [])
                    temp_c = None
                    if temp_data and isinstance(temp_data, list) and len(temp_data) > 0:
                        temp_info = temp_data[0]
                        if isinstance(temp_info, dict):
                            temp_c = temp_info.get("min_value") or temp_info.get("values", [None])[0]
                    
                    # Get time from conditions
                    time_data = conditions.get("heating_time", [])
                    duration = None
                    if time_data and isinstance(time_data, list) and len(time_data) > 0:
                        time_info = time_data[0]
                        if isinstance(time_info, dict):
                            duration = time_info.get("min_value") or time_info.get("values", [None])[0]
                            time_unit = time_info.get("units", "h")
                            # Convert days to hours if needed
                            if duration and time_unit == "day":
                                duration = duration * 24
                    
                    # Get atmosphere
                    atmosphere = conditions.get("heating_atmosphere", [])
                    if atmosphere and isinstance(atmosphere, list) and len(atmosphere) > 0:
                        atmosphere = atmosphere[0]
                    else:
                        atmosphere = None
                    
                    # Build step description
                    action = op.get("type", "process")
                    token = op.get("token", "")
                    
                    desc_parts = [token] if token else []
                    if temp_c:
                        desc_parts.append(f"at {temp_c}°C")
                    if duration:
                        unit = "h" if time_unit != "day" else "h"
                        desc_parts.append(f"for {duration} {unit}")
                    if atmosphere:
                        desc_parts.append(f"in {atmosphere}")
                    
                    description = " ".join(desc_parts) if desc_parts else str(op)
                    
                    steps.append({
                        "step": i,
                        "action": action,
                        "description": description,
                        "temperature_c": temp_c,
                        "duration": duration,
                        "atmosphere": atmosphere,
                        "conditions": conditions if conditions else None
                    })
                else:
                    steps.append({
                        "step": i,
                        "action": "process",
                        "description": str(op)
                    })
        else:
            # Single operation
            steps = [{
                "step": 1,
                "action": "synthesis",
                "description": str(operations)
            }]
    
    # If no detailed operations, create generic step
    if not steps:
        steps = [{
            "step": 1,
            "action": "synthesis",
            "description": f"Synthesis at {temperature}°C for {time_hours} hours" if temperature and time_hours else "Follow synthesis procedure",
            "temperature_c": temperature,
            "duration_h": time_hours
        }]
    
    return steps


def _parse_operations_string(operations: str, temperature: Optional[float], time_hours: Optional[float]) -> List[Dict[str, Any]]:
    """Parse operations text into structured steps."""
    import re
    
    steps = []
    
    # Split by common delimiters
    sentences = operations.replace(". ", ".\n").replace("; ", ";\n").split("\n")
    
    for i, sentence in enumerate(sentences, 1):
        sentence = sentence.strip()
        if not sentence:
            continue
        
        step = {
            "step": i,
            "action": "process",
            "description": sentence
        }
        
        # Try to extract temperature from text
        if "°C" in sentence or "celsius" in sentence.lower():
            temp_match = re.search(r'(\d+)\s*°?C', sentence)
            if temp_match:
                step["temperature_c"] = float(temp_match.group(1))
        
        # Try to extract time from text
        if "hour" in sentence.lower() or "hr" in sentence.lower():
            time_match = re.search(r'(\d+\.?\d*)\s*(hour|hr|h)', sentence.lower())
            if time_match:
                step["duration_h"] = float(time_match.group(1))
        
        steps.append(step)
    
    # If no steps extracted, create one
    if not steps:
        steps = [{
            "step": 1,
            "action": "synthesis",
            "description": operations,
            "temperature_c": temperature,
            "duration_h": time_hours
        }]
    
    return steps


def _infer_synthesis_method(recipe: Dict[str, Any]) -> str:
    """Infer synthesis method from recipe metadata."""
    
    # Check atmosphere and conditions
    atmosphere = str(recipe.get("atmosphere", "")).lower()
    conditions = str(recipe.get("conditions", "")).lower()
    operations = str(recipe.get("operations", "")).lower()
    
    # Look for method indicators
    all_text = f"{atmosphere} {conditions} {operations}"
    
    if "hydrothermal" in all_text or "autoclave" in all_text:
        return "hydrothermal"
    elif "solution" in all_text or "precipitation" in all_text:
        return "solution"
    elif "sol-gel" in all_text or "sol_gel" in all_text:
        return "sol_gel"
    elif "combustion" in all_text:
        return "combustion"
    elif "melt" in all_text:
        return "melting"
    else:
        return "solid_state"  # Default


def _calculate_feasibility_score(
    temperature: float,
    time_hours: float,
    max_temp: float,
    max_time: float
) -> float:
    """Calculate feasibility score for a literature route."""
    
    score = 1.0
    
    # Penalize if approaching limits
    if temperature > max_temp * 0.9:
        score -= 0.15
    if time_hours > max_time * 0.9:
        score -= 0.15
    
    # Literature routes get bonus for being proven
    score += 0.10  # Proven in literature
    
    # Clamp to [0, 1]
    return max(0.0, min(1.0, score))
