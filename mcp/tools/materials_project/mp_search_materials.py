"""
Tool for searching Materials Project database for inorganic materials and crystals.
Requires MP_API_KEY environment variable with your Materials Project API key.
"""

from typing import List, Dict, Any, Optional, Literal, Annotated
from pydantic import Field
from mp_api.client import MPRester
import os


def mp_search_materials(
    formula: Annotated[
        Optional[str],
        Field(default=None, description="Chemical formula (e.g., 'LiFePO4', 'TiO2', 'Si'). Use reduced formula without charge.")
    ] = None,
    
    elements: Annotated[
        Optional[List[str]],
        Field(default=None, description="List of elements that must be present (e.g., ['Li', 'Fe', 'P', 'O']). Use element symbols.")
    ] = None,
    
    exclude_elements: Annotated[
        Optional[List[str]],
        Field(default=None, description="List of elements to exclude (e.g., ['Pb', 'Hg']). Use element symbols.")
    ] = None,
    
    chemsys: Annotated[
        Optional[str],
        Field(default=None, description="Chemical system as hyphen-separated elements (e.g., 'Li-Fe-P-O'). Alternative to 'elements'.")
    ] = None,
    
    band_gap_min: Annotated[
        Optional[float],
        Field(default=None, ge=0, description="Minimum band gap in eV (e.g., 0.5). Use for searching semiconductors/insulators.")
    ] = None,
    
    band_gap_max: Annotated[
        Optional[float],
        Field(default=None, ge=0, description="Maximum band gap in eV (e.g., 5.0). Use for searching semiconductors/insulators.")
    ] = None,
    
    crystal_system: Annotated[
        Optional[Literal["triclinic", "monoclinic", "orthorhombic", "tetragonal", "trigonal", "hexagonal", "cubic"]],
        Field(default=None, description="Crystal system to filter by. Options: triclinic, monoclinic, orthorhombic, tetragonal, trigonal, hexagonal, cubic.")
    ] = None,
    
    is_stable: Annotated[
        Optional[bool],
        Field(default=None, description="Filter by thermodynamic stability. True = only stable materials (energy_above_hull = 0).")
    ] = None,
    
    energy_above_hull_max: Annotated[
        Optional[float],
        Field(default=None, ge=0, description="Maximum energy above hull in eV/atom (e.g., 0.1). Lower = more stable. Use 0 for only stable materials.")
    ] = None,
    
    is_magnetic: Annotated[
        Optional[bool],
        Field(default=None, description="Filter by magnetic ordering. True = magnetic materials only.")
    ] = None,
    
    theoretical: Annotated[
        Optional[bool],
        Field(default=None, description="Include theoretical (predicted but not synthesized) materials. Default includes both.")
    ] = None,
    
    max_results: Annotated[
        int,
        Field(default=10, ge=1, le=100, description="Maximum number of results to return (1-100). Default: 10.")
    ] = 10
) -> Dict[str, Any]:
    """
    Search Materials Project database for inorganic materials and crystals.
    
    Returns materials with crystal structure, electronic properties, thermodynamic
    stability, and more. Use this for battery materials, catalysts, semiconductors,
    and other inorganic compounds.
    
    Search Methods:
        1. By exact formula: formula="LiFePO4"
        2. By required elements: elements=["Li", "Fe", "P", "O"]
        3. By chemical system: chemsys="Li-Fe-P-O"
        4. By properties: band_gap_min=1.0, band_gap_max=3.0
        5. By stability: is_stable=True or energy_above_hull_max=0.1
    
    Common Use Cases:
        - Find battery cathode materials: elements=["Li"], is_stable=True
        - Find semiconductors: band_gap_min=1.0, band_gap_max=3.0
        - Find magnetic materials: is_magnetic=True
        - Find specific compound: formula="Si"
        - Find materials in system: chemsys="Li-Fe-P-O"
    
    Args:
        formula: Exact chemical formula (e.g., "LiFePO4", "TiO2")
        elements: List of required elements (e.g., ["Li", "Fe", "P", "O"])
        exclude_elements: List of elements to exclude (e.g., ["Pb", "Hg"])
        chemsys: Chemical system as hyphen-separated elements (e.g., "Li-Fe-P-O")
        band_gap_min: Minimum band gap in eV
        band_gap_max: Maximum band gap in eV
        crystal_system: Crystal system (cubic, hexagonal, etc.)
        is_stable: Only thermodynamically stable materials (energy_above_hull = 0)
        energy_above_hull_max: Maximum energy above hull in eV/atom
        is_magnetic: Only magnetic materials
        theoretical: Include theoretical (not yet synthesized) materials
        max_results: Maximum number of results (1-100)
    
    Returns:
        Dictionary containing:
            - success: Boolean indicating if search succeeded
            - query: Original search parameters
            - count: Number of materials found
            - materials: List of material dictionaries with properties
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
                "materials": [],
                "error": error_msg
            }
        
        # Initialize Materials Project API client
        with MPRester(api_key) as mpr:
            
            # Build search criteria
            search_criteria = {}
            
            # Formula search
            if formula:
                search_criteria["formula"] = formula
            
            # Elements search
            if elements:
                search_criteria["elements"] = elements
            
            # Exclude elements
            if exclude_elements:
                search_criteria["exclude_elements"] = exclude_elements
            
            # Chemical system
            if chemsys:
                search_criteria["chemsys"] = chemsys
            
            # Band gap range
            if band_gap_min is not None or band_gap_max is not None:
                band_gap_range = []
                if band_gap_min is not None:
                    band_gap_range.append(band_gap_min)
                else:
                    band_gap_range.append(0)
                
                if band_gap_max is not None:
                    band_gap_range.append(band_gap_max)
                else:
                    band_gap_range.append(float('inf'))
                
                search_criteria["band_gap"] = tuple(band_gap_range)
            
            # Crystal system filter
            if crystal_system:
                from emmet.core.symmetry import CrystalSystem
                search_criteria["crystal_system"] = CrystalSystem(crystal_system)
            
            # Stability filters
            if is_stable:
                search_criteria["is_stable"] = True
            elif energy_above_hull_max is not None:
                search_criteria["energy_above_hull"] = (0, energy_above_hull_max)
            
            # Magnetic filter
            if is_magnetic is not None:
                search_criteria["is_magnetic"] = is_magnetic
            
            # Theoretical filter
            if theoretical is not None:
                search_criteria["theoretical"] = theoretical
            
            # Perform search using summary endpoint
            summaries = mpr.materials.summary.search(
                **search_criteria,
                fields=[
                    # Basic identification
                    "material_id",
                    "formula_pretty",
                    "formula_anonymous",
                    "nsites",
                    "elements",
                    "nelements",
                    "composition",
                    "composition_reduced",
                    
                    # Structure - crystal_system/space_group accessed via symmetry
                    "symmetry",  # Contains crystal_system, space_group, point_group
                    "structure",  # Contains full structure if needed
                    "volume",
                    "density",
                    "density_atomic",
                    
                    # Electronic properties
                    "band_gap",
                    "cbm",
                    "vbm",
                    "efermi",
                    "is_gap_direct",
                    "is_metal",
                    
                    # Magnetic properties
                    "is_magnetic",
                    "ordering",
                    "total_magnetization",
                    "total_magnetization_normalized_vol",
                    "total_magnetization_normalized_formula_units",
                    "num_magnetic_sites",
                    "num_unique_magnetic_sites",
                    
                    # Thermodynamic properties
                    "energy_above_hull",
                    "formation_energy_per_atom",
                    "is_stable",
                    "equilibrium_reaction_energy_per_atom",
                    "uncorrected_energy_per_atom",
                    
                    # Other
                    "theoretical",
                    "database_IDs"
                ]
            )
            
            # Limit results
            summaries = summaries[:max_results]
            
            # Format results
            materials = []
            for summary in summaries:
                material_info = {
                    "material_id": summary.material_id,
                    "formula": summary.formula_pretty,
                    "formula_reduced": str(summary.composition_reduced),
                    "elements": [el.value for el in summary.elements],
                    "nelements": summary.nelements,
                    "nsites": summary.nsites,
                    
                    # Crystal structure - access through symmetry object
                    "crystal_system": summary.symmetry.crystal_system.value if summary.symmetry else "N/A",
                    "space_group_symbol": summary.symmetry.symbol if summary.symmetry else "N/A",
                    "space_group_number": summary.symmetry.number if summary.symmetry else "N/A",
                    "point_group": summary.symmetry.point_group if summary.symmetry else "N/A",
                    
                    # Physical properties
                    "volume": round(summary.volume, 3) if summary.volume else "N/A",
                    "density": round(summary.density, 3) if summary.density else "N/A",
                    
                    # Electronic properties
                    "band_gap": round(summary.band_gap, 4) if summary.band_gap is not None else "N/A",
                    "cbm": round(summary.cbm, 4) if hasattr(summary, 'cbm') and summary.cbm is not None else "N/A",
                    "vbm": round(summary.vbm, 4) if hasattr(summary, 'vbm') and summary.vbm is not None else "N/A",
                    "efermi": round(summary.efermi, 4) if hasattr(summary, 'efermi') and summary.efermi is not None else "N/A",
                    "is_gap_direct": summary.is_gap_direct if summary.is_gap_direct is not None else "N/A",
                    "is_metal": summary.is_metal,
                    
                    # Magnetic properties
                    "is_magnetic": summary.is_magnetic,
                    "magnetic_ordering": summary.ordering if hasattr(summary, 'ordering') else "N/A",
                    "total_magnetization": round(summary.total_magnetization, 3) if summary.total_magnetization else "N/A",
                    
                    # Thermodynamic properties
                    "energy_above_hull": round(summary.energy_above_hull, 4) if summary.energy_above_hull is not None else "N/A",
                    "formation_energy_per_atom": round(summary.formation_energy_per_atom, 4) if summary.formation_energy_per_atom else "N/A",
                    "is_stable": summary.is_stable,
                    
                    # Synthesis info
                    "theoretical": summary.theoretical
                }
                
                materials.append(material_info)

            # Prepare response
            response = {
                "success": len(materials) > 0,
                "query": {
                    "formula": formula,
                    "elements": elements,
                    "exclude_elements": exclude_elements,
                    "chemsys": chemsys,
                    "band_gap_min": band_gap_min,
                    "band_gap_max": band_gap_max,
                    "crystal_system": crystal_system,
                    "is_stable": is_stable,
                    "energy_above_hull_max": energy_above_hull_max,
                    "is_magnetic": is_magnetic,
                    "theoretical": theoretical,
                    "max_results": max_results
                },
                "count": len(materials),
                "materials": materials
            }
            
            if len(materials) == 0:
                response["error"] = "No materials found matching the search criteria"
            
            return response
    
    except Exception as e:
        error_msg = f"Error searching Materials Project: {str(e)}"
        return {
            "success": False,
            "query": {
                "formula": formula,
                "elements": elements,
                "exclude_elements": exclude_elements,
                "chemsys": chemsys,
                "band_gap_min": band_gap_min,
                "band_gap_max": band_gap_max,
                "crystal_system": crystal_system,
                "is_stable": is_stable,
                "energy_above_hull_max": energy_above_hull_max,
                "is_magnetic": is_magnetic,
                "theoretical": theoretical,
                "max_results": max_results
            },
            "count": 0,
            "materials": [],
            "error": error_msg
        }
    