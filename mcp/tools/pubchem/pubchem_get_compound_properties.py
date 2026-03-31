from typing import List, Dict, Any, Optional, Annotated
from pydantic import Field
import pubchempy as pcp


def pubchem_get_compound_properties(
    cids: Annotated[
        int | List[int], 
        Field(description="PubChem Compound ID(s). Pass a single integer (cids=702) or a list of integers (cids=[702, 2244]). Note: parameter name is 'cids' (plural) for both cases.")
    ],
    properties: Annotated[
        Optional[List[str]], 
        Field(
            default=None, 
            description="List of property names to retrieve. If None, returns default comprehensive set. "
            "Common properties include: MolecularWeight, MolecularFormula, XLogP, TPSA, "
            "Complexity, HBondDonorCount, HBondAcceptorCount, RotatableBondCount, "
            "ExactMass, MonoisotopicMass, Charge, HeavyAtomCount, IsotopeAtomCount, "
            "AtomStereoCount, DefinedAtomStereoCount, UndefinedAtomStereoCount, "
            "BondStereoCount, DefinedBondStereoCount, UndefinedBondStereoCount, "
            "CovalentUnitCount, Volume3D, Conformer3DCount"
        )
    ] = None
) -> Dict[str, Any]:
    """
    Get specific properties for known PubChem compounds by CID.
    
    This tool retrieves detailed chemical and physical properties for compounds
    when you already have their PubChem Compound IDs (CIDs). Use this AFTER
    pubchem_search_compounds to get in-depth property information.
    
    Examples:
        - Single CID with defaults: cids=2244 (returns comprehensive property set)
        - Single CID with specific properties: cids=2244, properties=["MolecularWeight", "XLogP", "TPSA"]
        - Multiple CIDs: cids=[2244, 2519], properties=["MolecularWeight", "XLogP"]
        - Drug-like properties: cids=2244, properties=["MolecularWeight", "XLogP", "HBondDonorCount", "HBondAcceptorCount"]
    
    IMPORTANT: The parameter is named 'cids' (plural) regardless of whether you pass one or multiple CIDs.
    
    Common Property Categories:
        - Basic: MolecularFormula, MolecularWeight, CanonicalSMILES, InChI, InChIKey, IUPACName
        - Drug-likeness: XLogP, TPSA, HBondDonorCount, HBondAcceptorCount, RotatableBondCount
        - Complexity: Complexity, HeavyAtomCount
        - Stereochemistry: IsomericSMILES, AtomStereoCount, BondStereoCount
        - 3D: Volume3D, XStericQuadrupole, YStericQuadrupole, ZStericQuadrupole
    
    Args:
        cids: Single integer (e.g., cids=702) or list of integers (e.g., cids=[702, 2244]).
              Note: parameter name is 'cids' (plural) even for a single CID.
        properties: List of property names to retrieve. If None, returns default property set.
    
    Returns:
        Dictionary containing:
            - success: Boolean indicating if retrieval succeeded
            - count: Number of compounds with properties retrieved
            - properties: List of property dictionaries (one per CID)
            - warnings: List of any errors for individual CIDs (if partial success)
            - error: Error message if complete failure
    """
    try:
        # Normalize CIDs to list
        if isinstance(cids, int):
            cid_list = [cids]
        else:
            cid_list = list(cids)
        
        # Define default comprehensive property set if none specified
        if properties is None:
            properties = [
                # Basic identification
                "MolecularFormula",
                "MolecularWeight",
                "CanonicalSMILES",
                "IsomericSMILES",
                "InChI",
                "InChIKey",
                "IUPACName",
                
                # Drug-likeness properties (Lipinski's Rule of Five)
                "XLogP",
                "TPSA",
                "HBondDonorCount",
                "HBondAcceptorCount",
                "RotatableBondCount",
                
                # Molecular complexity
                "Complexity",
                "HeavyAtomCount",
                
                # Physical properties
                "ExactMass",
                "MonoisotopicMass",
                "Charge",
                
                # Stereochemistry
                "AtomStereoCount",
                "DefinedAtomStereoCount",
                "BondStereoCount",
                "DefinedBondStereoCount",
                
                # Structure info
                "CovalentUnitCount"
            ]
        
        all_properties = []
        errors = []
        
        # Get properties for each CID
        for cid in cid_list:
            try:
                # Use PubChemPy's get_properties function
                results = pcp.get_properties(
                    properties,
                    cid,
                    namespace='cid',
                    as_dataframe=False
                )
                
                if results and len(results) > 0:
                    prop_dict = results[0]
                    
                    # Ensure CID is included in response
                    prop_dict['CID'] = cid
                    
                    # Clean up None values and format numbers
                    cleaned_props = {}
                    for key, value in prop_dict.items():
                        if value is not None:
                            # Format floats to reasonable precision
                            if isinstance(value, float):
                                cleaned_props[key] = round(value, 4)
                            else:
                                cleaned_props[key] = value
                        else:
                            cleaned_props[key] = "N/A"
                    
                    all_properties.append(cleaned_props)
                else:
                    error_msg = f"No properties found for CID {cid}"
                    errors.append(error_msg)
            
            except Exception as e:
                error_msg = f"Error getting properties for CID {cid}: {str(e)}"
                errors.append(error_msg)
                continue
        
        # Prepare response
        response = {
            "success": len(all_properties) > 0,
            "count": len(all_properties),
            "properties": all_properties,
            "requested_cids": cid_list,
            "requested_properties": properties
        }
        
        # Add warnings if some CIDs failed
        if errors:
            response["warnings"] = errors
        
        # Add error if complete failure
        if len(all_properties) == 0:
            response["error"] = "No properties retrieved for any CID"
        
        return response
    
    except Exception as e:
        error_msg = f"Error retrieving compound properties: {str(e)}"
        return {
            "success": False,
            "count": 0,
            "properties": [],
            "requested_cids": cid_list if isinstance(cids, list) else [cids],
            "requested_properties": properties,
            "error": error_msg
        }
    

# Utility function to get common property sets
def get_property_preset(preset_name: str) -> List[str]:
    """
    Get predefined property sets for common use cases.
    
    Args:
        preset_name: Name of preset ("basic", "druglike", "full", "stereochemistry", "3d")
    
    Returns:
        List of property names
    """
    presets = {
        "basic": [
            "MolecularFormula",
            "MolecularWeight",
            "CanonicalSMILES",
            "InChI",
            "InChIKey",
            "IUPACName"
        ],
        "druglike": [
            "MolecularWeight",
            "XLogP",
            "TPSA",
            "HBondDonorCount",
            "HBondAcceptorCount",
            "RotatableBondCount",
            "Complexity"
        ],
        "stereochemistry": [
            "IsomericSMILES",
            "InChI",
            "AtomStereoCount",
            "DefinedAtomStereoCount",
            "UndefinedAtomStereoCount",
            "BondStereoCount",
            "DefinedBondStereoCount",
            "UndefinedBondStereoCount"
        ],
        "3d": [
            "Volume3D",
            "XStericQuadrupole",
            "YStericQuadrupole",
            "ZStericQuadrupole",
            "FeatureCount3D",
            "FeatureAcceptorCount3D",
            "FeatureDonorCount3D",
            "FeatureAnionCount3D",
            "FeatureCationCount3D",
            "FeatureRingCount3D",
            "FeatureHydrophobeCount3D",
            "ConformerModelRMSD3D",
            "EffectiveRotorCount3D",
            "ConformerCount3D"
        ],
        "full": None  # Returns default comprehensive set
    }
    
    return presets.get(preset_name.lower(), presets["basic"])