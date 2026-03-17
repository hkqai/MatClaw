"""
Tool for searching synthesis recipes from Materials Project Synthesis Explorer.
Retrieves literature-derived synthesis procedures for inorganic materials.
Requires MP_API_KEY environment variable with your Materials Project API key.
"""

from typing import List, Dict, Any, Optional, Annotated
from pydantic import Field
from mp_api.client import MPRester
import os


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
    
    reaction_type: Annotated[
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
            le=100,
            description="Maximum number of synthesis recipes to return (1-100). Default: 10."
        )
    ] = 10,
    
    fields: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description="Specific fields to return in recipe data. "
            "Available fields: 'target', 'precursors', 'operations', 'conditions', "
            "'temperature', 'time', 'atmosphere', 'product_characterization', "
            "'doi', 'citation', 'year', 'authors'. "
            "If None, returns all available fields."
        )
    ] = None
) -> Dict[str, Any]:
    """
    Search Materials Project Synthesis Explorer for experimental synthesis recipes.
    
    Retrieves real-world, literature-derived synthesis procedures for inorganic/solid-state
    materials extracted from research papers. Each recipe includes target materials,
    precursors, reaction conditions, temperatures, times, and literature citations.
    
    Use this tool to:
        - Find proven synthesis routes for specific materials
        - Discover alternative synthesis methods
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
            target_formula="LiFePO4", limit=20
        
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
        reaction_type: Type of synthesis reaction
        temperature_min: Minimum synthesis temperature (°C)
        temperature_max: Maximum synthesis temperature (°C)
        heating_time_max: Maximum heating time (hours)
        year_min: Minimum publication year
        doi: Specific publication DOI
        limit: Maximum number of recipes to return (1-100)
        fields: Specific data fields to return
    
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
                - authors: Paper authors
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
        if reaction_type:
            query_params["reaction_type"] = reaction_type
        if temperature_min is not None:
            query_params["temperature_min"] = temperature_min
        if temperature_max is not None:
            query_params["temperature_max"] = temperature_max
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
                    synthesis_client = mpr.materials.synthesis

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
                    
                    # synthesis_type maps to reaction_type parameter
                    if reaction_type:
                        search_kwargs['synthesis_type'] = [reaction_type]
                    
                    # Temperature parameters need condition_heating_ prefix
                    if temperature_min is not None:
                        search_kwargs['condition_heating_temperature_min'] = temperature_min
                    
                    if temperature_max is not None:
                        search_kwargs['condition_heating_temperature_max'] = temperature_max
                    
                    # Time parameters need condition_heating_ prefix
                    if heating_time_max is not None:
                        search_kwargs['condition_heating_time_max'] = heating_time_max
                    
                    # Execute search
                    results = synthesis_client.search(**search_kwargs, num_chunks=limit)
                    
                elif hasattr(mpr, 'get_synthesis_recipes'):
                    # Alternative method name
                    results = mpr.get_synthesis_recipes(
                        formula=target_formula[0] if target_formula and len(target_formula) == 1 else None,
                        num_chunks=limit
                    )
                    
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
                    recipe['target'] = result_dict.get('target') or result_dict.get('product')
                    recipe['target_formula'] = result_dict.get('target_formula') or result_dict.get('formula')
                    
                    # Precursors
                    recipe['precursors'] = result_dict.get('precursors') or result_dict.get('starting_materials') or []
                    
                    # Synthesis steps/operations
                    recipe['operations'] = result_dict.get('operations') or result_dict.get('steps') or result_dict.get('procedure')
                    
                    # Conditions
                    conditions = result_dict.get('conditions') or {}
                    recipe['conditions'] = conditions
                    
                    recipe['temperature_celsius'] = (
                        conditions.get('temperature') or 
                        result_dict.get('temperature') or
                        result_dict.get('temp_celsius')
                    )
                    
                    recipe['heating_time_hours'] = (
                        conditions.get('heating_time') or
                        conditions.get('time') or
                        result_dict.get('time_hours') or
                        result_dict.get('duration')
                    )
                    
                    recipe['atmosphere'] = (
                        conditions.get('atmosphere') or
                        result_dict.get('atmosphere') or
                        'not specified'
                    )
                    
                    recipe['product_info'] = result_dict.get('product_characterization') or result_dict.get('notes')
                    recipe['doi'] = result_dict.get('doi')
                    recipe['citation'] = result_dict.get('citation') or result_dict.get('reference')
                    recipe['year'] = result_dict.get('year') or result_dict.get('publication_year')
                    recipe['authors'] = result_dict.get('authors')
                    
                    if fields:
                        recipe = {k: v for k, v in recipe.items() if k in fields or k == 'recipe_id'}
                    
                    recipes.append(recipe)
                
                warnings = []
                if len(results) > limit:
                    warnings.append(f"Found {len(results)} recipes but returning only {limit}. Increase 'limit' parameter to see more.")
                
                if len(recipes) == 0:
                    warnings.append("No synthesis recipes found matching the search criteria. Try broadening your search or using different keywords.")
                
                return {
                    "success": True,
                    "query": query_params,
                    "count": len(recipes),
                    "recipes": recipes,
                    "warnings": warnings if warnings else None,
                    "message": f"Found {len(recipes)} synthesis recipe(s) matching search criteria"
                }
                
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
