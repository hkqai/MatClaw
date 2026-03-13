from typing import List, Dict, Any, Optional, Literal, Annotated
from pydantic import Field
import pubchempy as pcp


def pubchem_search_compounds(
    identifier: Annotated[
        str | List[str],
        Field(description="Search term(s): compound name, SMILES, InChI, InChIKey, formula, or CID. Can be a single string or list of strings.")
    ],
    namespace: Annotated[
        Literal["name", "smiles", "inchi", "inchikey", "formula", "cid"],
        Field(default="name", description="Type of identifier being searched. Options: 'name', 'smiles', 'inchi', 'inchikey', 'formula', 'cid'")
    ] = "name",
    searchtype: Annotated[
        Optional[Literal["similarity", "substructure", "superstructure"]],
        Field(default=None, description="Advanced search mode. Options: 'similarity' (Tanimoto), 'substructure', or 'superstructure'. Leave None for exact/fuzzy match.")
    ] = None,
    max_results: Annotated[
        int,
        Field(default=10, ge=1, le=100, description="Maximum number of results to return (1-100)")
    ] = 10
) -> Dict[str, Any]:
    """
    Search PubChem for compounds by name, SMILES, InChI, formula, or other identifiers.
    Returns identifying information for matching compounds, including CID, name, SMILES, formula, synonyms and more.
    
    This is typically the first step in any PubChem workflow - finding candidate compounds
    before requesting detailed properties.
    
    Examples:
        - Search by name: identifier="caffeine", namespace="name"
        - Search by SMILES: identifier="CCO", namespace="smiles"
        - Search by formula: identifier="C8H10N4O2", namespace="formula"
        - Similarity search: identifier="CCO", namespace="smiles", searchtype="similarity"
        - Multiple compounds: identifier=["water", "ethanol"], namespace="name"
    
    Args:
        identifier: Search term(s) - compound name, SMILES, InChI, InChIKey, formula, or CID
        namespace: Type of identifier ('name', 'smiles', 'inchi', 'inchikey', 'formula', 'cid')
        searchtype: Optional advanced search ('similarity', 'substructure', 'superstructure')
        max_results: Maximum number of results to return (1-100)
    
    Returns:
        Dictionary containing:
            - success: Boolean indicating if search succeeded
            - query: Original search parameters
            - count: Number of compounds found
            - compounds: List of compound dictionaries with CID, name, formula, etc.
            - error: Error message if search failed
    """
    try:
        # Normalize inputs
        if isinstance(identifier, str):
            identifiers = [identifier]
        else:
            identifiers = identifier
        
        namespace = namespace.lower()
        
        all_compounds = []
        errors = []
        
        # Search for each identifier
        for search_term in identifiers:
            try:
                # Perform search based on searchtype
                if searchtype:
                    compounds = pcp.get_compounds(
                        search_term,
                        namespace=namespace,
                        searchtype=searchtype.lower(),
                        as_dataframe=False
                    )
                else:
                    # Standard search (exact or fuzzy match)
                    compounds = pcp.get_compounds(
                        search_term,
                        namespace=namespace,
                        as_dataframe=False
                    )
                
                # Limit results
                compounds = compounds[:max_results]
                
                # Extract key information from each compound
                for compound in compounds:
                    compound_info = {
                        "cid": compound.cid,
                        "iupac_name": compound.iupac_name or "N/A",
                        "molecular_formula": compound.molecular_formula or "N/A",
                        "molecular_weight": compound.molecular_weight or "N/A",
                        "connectivity_smiles": compound.connectivity_smiles or "N/A",
                        "smiles": compound.smiles or "N/A",
                        "inchi": compound.inchi or "N/A",
                        "inchikey": compound.inchikey or "N/A",
                        "synonyms": compound.synonyms[:5] if compound.synonyms else [],  # Top 5 synonyms
                        "search_term": search_term
                    }
                    all_compounds.append(compound_info)
            
            except Exception as e:
                error_msg = f"Error searching for '{search_term}': {str(e)}"
                errors.append(error_msg)
                continue
        
        # Remove duplicates based on CID
        seen_cids = set()
        unique_compounds = []
        for compound in all_compounds:
            if compound["cid"] not in seen_cids:
                seen_cids.add(compound["cid"])
                unique_compounds.append(compound)
        
        # Prepare response
        response = {
            "success": len(unique_compounds) > 0,
            "query": {
                "identifiers": identifiers,
                "namespace": namespace,
                "searchtype": searchtype,
                "max_results": max_results
            },
            "count": len(unique_compounds),
            "compounds": unique_compounds
        }
        
        if errors:
            response["warnings"] = errors
        
        if len(unique_compounds) == 0:
            response["error"] = "No compounds found matching the search criteria"
        
        return response
    
    except Exception as e:
        error_msg = f"Error searching PubChem: {str(e)}"
        return {
            "success": False,
            "query": {
                "identifiers": identifiers if isinstance(identifier, list) else [identifier],
                "namespace": namespace,
                "searchtype": searchtype,
                "max_results": max_results
            },
            "count": 0,
            "compounds": [],
            "error": error_msg
        }
