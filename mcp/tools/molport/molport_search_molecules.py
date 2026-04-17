"""
Tool for searching Molport database for chemicals by SMILES structure.
Requires MOLPORT_API_KEY environment variable with your Molport API key.
"""

from typing import Dict, Any, Optional, Literal, Annotated
from pydantic import Field
import requests
import os


def molport_search_molecules(
    smiles: Annotated[
        str,
        Field(description="SMILES string of the molecule to search for (e.g., 'CCO', 'CC(C)(C)OC(=O)N1CCCCCC1C(O)=O')")
    ],
    search_type: Annotated[
        Literal["substructure", "superstructure", "exact", "similarity", "perfect", "exact_fragment"],
        Field(default="exact_fragment", description="Search type: 'substructure' (1), 'superstructure' (2), 'exact' (3), 'similarity' (4), 'perfect' (5), 'exact_fragment' (6, default)")
    ] = "exact_fragment",
    similarity_index: Annotated[
        Optional[float],
        Field(default=0.9, ge=0.0, le=1.0, description="Similarity threshold (0-1) for similarity searches. Default: 0.9. Only used when search_type='similarity'.")
    ] = 0.9,
    max_results: Annotated[
        int,
        Field(default=100, ge=1, le=10000, description="Maximum number of results to return (1-10000). Default: 100.")
    ] = 100,
    max_search_time: Annotated[
        Optional[int],
        Field(default=None, description="Maximum search time in milliseconds. If not specified, uses Molport default.")
    ] = None,
    compound_set: Annotated[
        Literal["all", "natural_compounds"],
        Field(default="all", description="Compound set to search: 'all' (0, default) or 'natural_compounds' (1)")
    ] = "all"
) -> Dict[str, Any]:
    """
    Search Molport chemical database by SMILES structure.
    
    Returns matching molecules with their Molport IDs, which can be used with
    molport_get_molecule_info to retrieve detailed pricing and supplier information.
    
    Search Types:
        - exact_fragment (default): Exact match on molecular fragment
        - exact: Exact molecular structure match
        - perfect: Perfect structure match (most strict)
        - similarity: Similar structures using Tanimoto similarity
        - substructure: Query is substructure of results
        - superstructure: Query is superstructure of results
    
    Examples:
        - Exact search: smiles="CCO", search_type="exact"
        - Similarity search: smiles="CC(C)(C)OC(=O)N1CCCCCC1C(O)=O", search_type="similarity", similarity_index=0.9
        - Substructure search: smiles="c1ccccc1", search_type="substructure"
    
    Args:
        smiles: SMILES string of the molecule
        search_type: Type of chemical search to perform
        similarity_index: Similarity threshold (0-1) for similarity searches
        max_results: Maximum number of results to return (1-10000)
        max_search_time: Optional maximum search time in milliseconds
        compound_set: Whether to search all compounds or only natural compounds
    
    Returns:
        Dictionary containing:
            - success: Boolean indicating if search succeeded
            - query: Original search parameters
            - count: Number of molecules found
            - molecules: List of molecule dictionaries with:
                - molport_id (int): Numeric Molport ID
                - molport_id_string (str): String Molport ID (e.g., "Molport-001-785-844")
                - smiles (str): SMILES notation
                - canonical_smiles (str): Canonical SMILES notation
                - verified_amount (int): Verified supplier amount
                - unverified_amount (int): Unverified supplier amount
                - supplier_count (int): Total supplier count (verified + unverified)
                - similarity_index (float): Similarity score (for similarity searches)
            - error: Error message if search failed
    """
    try:
        # Get API key from environment
        api_key = os.getenv("MOLPORT_API_KEY")
        if not api_key:
            error_msg = "MOLPORT_API_KEY environment variable not set. Get your API key from https://www.molport.com/shop/api"
            return {
                "success": False,
                "query": {"smiles": smiles, "search_type": search_type},
                "count": 0,
                "molecules": [],
                "error": error_msg
            }
        
        # Map search type to API integer
        search_type_map = {
            "substructure": 1,
            "superstructure": 2,
            "exact": 3,
            "similarity": 4,
            "perfect": 5,
            "exact_fragment": 6
        }
        
        # Map compound set to API integer
        compound_set_map = {
            "all": 0,
            "natural_compounds": 1
        }
        
        # Build request payload
        payload = {
            "API Key": api_key,
            "Structure": smiles,
            "Search Type": search_type_map[search_type],
            "Maximum Result Count": max_results,
            "Set Id": compound_set_map[compound_set]
        }
        
        # Add optional parameters
        if search_type == "similarity":
            payload["Chemical Similarity Index"] = similarity_index
        
        if max_search_time is not None:
            payload["Maximum Search Time"] = max_search_time
        
        # Make API request
        response = requests.post(
            "https://api.molport.com/api/chemical-search/search",
            json=payload,
            timeout=30
        )
        
        # Check response status
        if response.status_code != 200:
            error_msg = f"Molport API error: HTTP {response.status_code}"
            try:
                error_data = response.json()
                if "message" in error_data:
                    error_msg += f" - {error_data['message']}"
            except:
                pass
            
            return {
                "success": False,
                "query": {
                    "smiles": smiles,
                    "search_type": search_type,
                    "similarity_index": similarity_index if search_type == "similarity" else None,
                    "max_results": max_results
                },
                "count": 0,
                "molecules": [],
                "error": error_msg
            }
        
        # Parse response
        data = response.json()
        
        # Extract molecules from response
        molecules = []
        if "Data" in data and "Molecules" in data["Data"]:
            for item in data["Data"]["Molecules"]:
                molecule_info = {
                    "molport_id": item.get("Id"),
                    "molport_id_string": item.get("MolPort Id"),
                    "smiles": item.get("SMILES"),
                    "canonical_smiles": item.get("Canonical SMILES"),
                    "verified_amount": item.get("Verified Amount", 0),
                    "unverified_amount": item.get("Unverified Amount", 0),
                    "supplier_count": item.get("Verified Amount", 0) + item.get("Unverified Amount", 0),
                    "similarity_index": item.get("Similarity Index")
                }
                molecules.append(molecule_info)
        
        # Prepare response
        result = {
            "success": True,
            "query": {
                "smiles": smiles,
                "search_type": search_type,
                "similarity_index": similarity_index if search_type == "similarity" else None,
                "max_results": max_results,
                "compound_set": compound_set
            },
            "count": len(molecules),
            "molecules": molecules
        }
        
        if len(molecules) == 0:
            result["success"] = False
            result["error"] = "No molecules found matching the search criteria"
        
        return result
        
    except requests.exceptions.Timeout:
        error_msg = "Request to Molport API timed out"
        return {
            "success": False,
            "query": {"smiles": smiles, "search_type": search_type},
            "count": 0,
            "molecules": [],
            "error": error_msg
        }
    
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error accessing Molport API: {str(e)}"
        return {
            "success": False,
            "query": {"smiles": smiles, "search_type": search_type},
            "count": 0,
            "molecules": [],
            "error": error_msg
        }
    
    except Exception as e:
        error_msg = f"Error searching Molport: {str(e)}"
        return {
            "success": False,
            "query": {"smiles": smiles, "search_type": search_type},
            "count": 0,
            "molecules": [],
            "error": error_msg
        }
