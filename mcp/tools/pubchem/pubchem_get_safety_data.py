from typing import List, Dict, Any, Optional, Annotated
from pydantic import Field
import requests
import pubchempy as pcp


def pubchem_get_safety_data(
    cids: Annotated[
        int | List[int], 
        Field(description="PubChem Compound ID(s). Pass a single integer (cids=702) or a list of integers (cids=[702, 2244]). Note: parameter name is 'cids' (plural) for both cases.")
    ],
    include_sections: Annotated[
        Optional[List[str]], 
        Field(
            default=None, 
            description="List of safety data sections to retrieve. If None, returns all available sections. "
            "Available sections: 'ghs', 'toxicity', 'physical_hazards', 'health_hazards', "
            "'environmental_hazards', 'exposure_limits', 'handling_storage'"
        )
    ] = None
) -> Dict[str, Any]:
    """
    Get safety, toxicity, and hazard data for PubChem compounds.
    
    This tool retrieves comprehensive safety information including GHS classifications,
    toxicity values (LD50, LC50), physical hazards, health hazards, environmental
    hazards, and exposure limits. This data is critical for feasibility screening
    in materials discovery to filter out toxic, hazardous, or unsafe compounds.
    
    Use Cases:
        - Safety screening: Filter compounds with dangerous hazard codes (H300, H350, etc.)
        - Toxicity assessment: Check LD50/LC50 values for acute toxicity
        - Regulatory compliance: Identify compounds with restricted hazard classifications
        - Lab safety planning: Get handling and storage requirements before synthesis
        - Environmental impact: Assess aquatic toxicity and bioaccumulation potential
    
    Examples:
        - Single CID, all sections: cids=2244 (aspirin - returns comprehensive safety info)
        - Single CID, specific section: cids=702, include_sections=["ghs"]
        - Multiple CIDs: cids=[702, 2244, 5793], include_sections=["ghs", "toxicity"]
        - Toxicity focus: cids=5793, include_sections=["toxicity", "health_hazards"]
    
    IMPORTANT: The parameter is named 'cids' (plural) regardless of whether you pass one or multiple CIDs.
    
    Important Hazard Codes to Screen For:
        - H300-H330: Acute toxicity (fatal/toxic if swallowed/inhaled/skin contact)
        - H340-H350: Carcinogenicity and mutagenicity
        - H360-H362: Reproductive toxicity
        - H400-H410: Environmental hazards (aquatic toxicity)
        - H200-H242: Physical hazards (explosives, flammables, oxidizers)
    
    Args:
        cids: Single integer (e.g., cids=702) or list of integers (e.g., cids=[702, 2244]).
              Note: parameter name is 'cids' (plural) even for a single CID.
        include_sections: List of sections to retrieve. If None, returns all available.
    
    Returns:
        Dictionary containing:
            - success: Boolean indicating if retrieval succeeded
            - count: Number of compounds with safety data retrieved
            - safety_data: List of safety data dictionaries (one per CID)
            - warnings: List of any errors for individual CIDs (if partial success)
            - error: Error message if complete failure
    """
    try:
        # Normalize CIDs to list
        if isinstance(cids, int):
            cid_list = [cids]
        else:
            cid_list = list(cids)
        
        # Define all sections if none specified
        if include_sections is None:
            include_sections = [
                "ghs",
                "toxicity",
                "physical_hazards",
                "health_hazards",
                "environmental_hazards",
                "exposure_limits",
                "handling_storage"
            ]
        
        all_safety_data = []
        errors = []
        
        # Get safety data for each CID
        for cid in cid_list:
            try:
                compound_safety = {"CID": cid}
                
                # Get compound record for basic info
                try:
                    compound = pcp.Compound.from_cid(cid)
                    compound_safety["compound_name"] = compound.iupac_name or "N/A"
                    compound_safety["molecular_formula"] = compound.molecular_formula or "N/A"
                except:
                    compound_safety["compound_name"] = "N/A"
                    compound_safety["molecular_formula"] = "N/A"
                
                # Make ONE API request to get all data for this compound
                pubchem_data = _fetch_pubchem_data(cid)
                
                if pubchem_data is None:
                    errors.append(f"Failed to retrieve data for CID {cid}")
                    continue
                
                # Parse requested sections from the single API response
                if "ghs" in include_sections:
                    compound_safety["ghs"] = _get_ghs_classification(pubchem_data)
                
                if "toxicity" in include_sections:
                    compound_safety["toxicity"] = _get_toxicity_data(pubchem_data)
                
                if "physical_hazards" in include_sections:
                    compound_safety["physical_hazards"] = _get_physical_hazards(pubchem_data)
                
                if "health_hazards" in include_sections:
                    compound_safety["health_hazards"] = _get_health_hazards(pubchem_data)
                
                if "environmental_hazards" in include_sections:
                    compound_safety["environmental_hazards"] = _get_environmental_hazards(pubchem_data)
                
                if "exposure_limits" in include_sections:
                    compound_safety["exposure_limits"] = _get_exposure_limits(pubchem_data)
                
                if "handling_storage" in include_sections:
                    compound_safety["handling_storage"] = _get_handling_storage(pubchem_data)
                
                all_safety_data.append(compound_safety)
            
            except Exception as e:
                error_msg = f"Error getting safety data for CID {cid}: {str(e)}"
                errors.append(error_msg)
                continue
        
        # Prepare response
        response = {
            "success": len(all_safety_data) > 0,
            "count": len(all_safety_data),
            "safety_data": all_safety_data,
            "requested_cids": cid_list,
            "requested_sections": include_sections
        }
        
        # Add warnings if some CIDs failed
        if errors:
            response["warnings"] = errors
        
        # Add error if complete failure
        if len(all_safety_data) == 0:
            response["error"] = "No safety data retrieved for any CID"
        
        return response
    
    except Exception as e:
        error_msg = f"Error retrieving safety data: {str(e)}"
        return {
            "success": False,
            "count": 0,
            "safety_data": [],
            "requested_cids": cid_list if isinstance(cids, list) else [cids],
            "requested_sections": include_sections,
            "error": error_msg
        }


def _fetch_pubchem_data(cid: int) -> Optional[Dict[str, Any]]:
    """
    Fetch PubChem data for a compound. Makes ONE API request per compound.
    Returns the parsed JSON data or None if the request fails.
    """
    try:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return None
        
        return response.json()
    
    except Exception as e:
        return None


def _get_ghs_classification(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get GHS (Globally Harmonized System) classification data from PubChem data.
    Includes hazard codes, pictograms, signal words, and precautionary statements.
    """
    try:
        ghs_data = {
            "available": False,
            "hazard_codes": [],
            "pictograms": [],
            "signal_word": "N/A",
            "precautionary_statements": [],
            "hazard_statements": []
        }
        
        # Parse GHS data from sections
        sections = data.get("Record", {}).get("Section", [])
        ghs_section = _find_section_by_heading(sections, "GHS Classification")
        
        if ghs_section:
            ghs_data["available"] = True
            
            # Extract hazard codes (H-codes)
            hazard_codes = _extract_ghs_codes(ghs_section, "H")
            ghs_data["hazard_codes"] = hazard_codes
            
            # Extract hazard statements
            hazard_statements = _extract_text_from_section(ghs_section, "Hazards")
            ghs_data["hazard_statements"] = hazard_statements
            
            # Extract pictograms
            pictograms = _extract_text_from_section(ghs_section, "Pictogram")
            ghs_data["pictograms"] = pictograms
            
            # Extract signal word
            signal = _extract_text_from_section(ghs_section, "Signal")
            if signal:
                ghs_data["signal_word"] = signal[0] if isinstance(signal, list) else signal
            
            # Extract precautionary statements (P-codes)
            p_codes = _extract_ghs_codes(ghs_section, "P")
            ghs_data["precautionary_statements"] = p_codes
        
        return ghs_data
    
    except Exception as e:
        return {"available": False, "error": str(e)}


def _get_toxicity_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get acute toxicity data including LD50 and LC50 values from PubChem data.
    """
    try:
        toxicity_data = {
            "available": False,
            "ld50_oral": [],
            "ld50_dermal": [],
            "lc50_inhalation": [],
            "other_toxicity": []
        }
        
        sections = data.get("Record", {}).get("Section", [])
        tox_section = _find_section_by_heading(sections, "Toxicity")
        
        if not tox_section:
            tox_section = _find_section_by_heading(sections, "Health Hazards")
        
        if tox_section:
            toxicity_data["available"] = True
            
            # Extract LD50 and LC50 values
            tox_text = _extract_all_text_from_section(tox_section)
            
            for text in tox_text:
                text_lower = text.lower()
                if "ld50" in text_lower and "oral" in text_lower:
                    toxicity_data["ld50_oral"].append(text)
                elif "ld50" in text_lower and "dermal" in text_lower:
                    toxicity_data["ld50_dermal"].append(text)
                elif "lc50" in text_lower and "inhal" in text_lower:
                    toxicity_data["lc50_inhalation"].append(text)
                elif any(keyword in text_lower for keyword in ["toxic", "ld50", "lc50", "lethal"]):
                    toxicity_data["other_toxicity"].append(text)
        
        return toxicity_data
    
    except Exception as e:
        return {"available": False, "error": str(e)}


def _get_physical_hazards(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get physical hazards including flash point, flammability, explosive properties from PubChem data.
    """
    try:
        hazards = {
            "available": False,
            "flash_point": "N/A",
            "autoignition_temperature": "N/A",
            "flammability": "N/A",
            "explosive_properties": "N/A",
            "oxidizing_properties": "N/A"
        }
        
        sections = data.get("Record", {}).get("Section", [])
        
        # Look for physical hazards in various sections
        for search_heading in ["Safety and Hazards", "Fire Hazards", "Flammability"]:
            section = _find_section_by_heading(sections, search_heading)
            if section:
                hazards["available"] = True
                text_data = _extract_all_text_from_section(section)
                
                for text in text_data:
                    text_lower = text.lower()
                    if "flash point" in text_lower or "flash-point" in text_lower:
                        hazards["flash_point"] = text
                    elif "autoignition" in text_lower or "auto-ignition" in text_lower:
                        hazards["autoignition_temperature"] = text
                    elif "flammab" in text_lower:
                        hazards["flammability"] = text
                    elif "explosive" in text_lower:
                        hazards["explosive_properties"] = text
                    elif "oxidiz" in text_lower:
                        hazards["oxidizing_properties"] = text
        
        return hazards
    
    except Exception as e:
        return {"available": False, "error": str(e)}


def _get_health_hazards(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get health hazards including carcinogenicity, mutagenicity, reproductive toxicity from PubChem data.
    """
    try:
        health = {
            "available": False,
            "carcinogenicity": [],
            "mutagenicity": [],
            "reproductive_toxicity": [],
            "specific_target_organ_toxicity": [],
            "other_health_effects": []
        }
        
        sections = data.get("Record", {}).get("Section", [])
        health_section = _find_section_by_heading(sections, "Health Hazards")
        
        if health_section:
            health["available"] = True
            text_data = _extract_all_text_from_section(health_section)
            
            for text in text_data:
                text_lower = text.lower()
                if "carcinogen" in text_lower or "cancer" in text_lower:
                    health["carcinogenicity"].append(text)
                elif "mutagen" in text_lower or "genotoxic" in text_lower:
                    health["mutagenicity"].append(text)
                elif "reproductive" in text_lower or "teratogen" in text_lower:
                    health["reproductive_toxicity"].append(text)
                elif "target organ" in text_lower or "stot" in text_lower:
                    health["specific_target_organ_toxicity"].append(text)
                else:
                    health["other_health_effects"].append(text)
        
        return health
    
    except Exception as e:
        return {"available": False, "error": str(e)}


def _get_environmental_hazards(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get environmental hazards including aquatic toxicity and bioaccumulation from PubChem data.
    """
    try:
        env = {
            "available": False,
            "aquatic_toxicity": [],
            "bioaccumulation": "N/A",
            "persistence": "N/A",
            "other_environmental_effects": []
        }
        
        sections = data.get("Record", {}).get("Section", [])
        env_section = _find_section_by_heading(sections, "Ecological Information")
        
        if not env_section:
            env_section = _find_section_by_heading(sections, "Environmental Hazards")
        
        if env_section:
            env["available"] = True
            text_data = _extract_all_text_from_section(env_section)
            
            for text in text_data:
                text_lower = text.lower()
                if "aquatic" in text_lower or "fish" in text_lower or "daphnia" in text_lower:
                    env["aquatic_toxicity"].append(text)
                elif "bioaccumulation" in text_lower or "bioconcentration" in text_lower:
                    env["bioaccumulation"] = text
                elif "persistence" in text_lower or "biodegradation" in text_lower:
                    env["persistence"] = text
                else:
                    env["other_environmental_effects"].append(text)
        
        return env
    
    except Exception as e:
        return {"available": False, "error": str(e)}


def _get_exposure_limits(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get occupational exposure limits (OSHA PEL, NIOSH REL, ACGIH TLV) from PubChem data.
    """
    try:
        limits = {
            "available": False,
            "osha_pel": "N/A",
            "niosh_rel": "N/A",
            "acgih_tlv": "N/A",
            "other_limits": []
        }
        
        sections = data.get("Record", {}).get("Section", [])
        exposure_section = _find_section_by_heading(sections, "Exposure Limits")
        
        if not exposure_section:
            exposure_section = _find_section_by_heading(sections, "Exposure Standards")
        
        if exposure_section:
            limits["available"] = True
            text_data = _extract_all_text_from_section(exposure_section)
            
            for text in text_data:
                text_upper = text.upper()
                if "OSHA" in text_upper and "PEL" in text_upper:
                    limits["osha_pel"] = text
                elif "NIOSH" in text_upper and "REL" in text_upper:
                    limits["niosh_rel"] = text
                elif "ACGIH" in text_upper and "TLV" in text_upper:
                    limits["acgih_tlv"] = text
                else:
                    limits["other_limits"].append(text)
        
        return limits
    
    except Exception as e:
        return {"available": False, "error": str(e)}


def _get_handling_storage(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get handling and storage recommendations from PubChem data.
    """
    try:
        handling = {
            "available": False,
            "handling": [],
            "storage": [],
            "disposal": []
        }
        
        sections = data.get("Record", {}).get("Section", [])
        
        for search_heading in ["Handling and Storage", "Storage", "Disposal"]:
            section = _find_section_by_heading(sections, search_heading)
            if section:
                handling["available"] = True
                text_data = _extract_all_text_from_section(section)
                
                for text in text_data:
                    text_lower = text.lower()
                    if "handling" in text_lower:
                        handling["handling"].append(text)
                    elif "storage" in text_lower or "store" in text_lower:
                        handling["storage"].append(text)
                    elif "disposal" in text_lower or "dispose" in text_lower:
                        handling["disposal"].append(text)
                    else:
                        handling["handling"].append(text)
        
        return handling
    
    except Exception as e:
        return {"available": False, "error": str(e)}


# Helper functions for parsing PubChem JSON structure

def _find_section_by_heading(sections: List[Dict], heading: str) -> Optional[Dict]:
    """Recursively find a section by heading name."""
    for section in sections:
        if section.get("TOCHeading", "").lower() == heading.lower():
            return section
        
        # Check nested sections
        if "Section" in section:
            found = _find_section_by_heading(section["Section"], heading)
            if found:
                return found
    
    return None


def _extract_ghs_codes(section: Dict, code_type: str) -> List[str]:
    """Extract GHS codes (H-codes or P-codes) from a section."""
    codes = []
    text_data = _extract_all_text_from_section(section)
    
    import re
    pattern = re.compile(rf"{code_type}\d{{3}}\+?(?:\+{code_type}\d{{3}})*", re.IGNORECASE)
    
    for text in text_data:
        matches = pattern.findall(text)
        codes.extend(matches)
    
    return list(set(codes))  # Remove duplicates


def _extract_text_from_section(section: Dict, keyword: str) -> List[str]:
    """Extract text from section that contains a specific keyword."""
    results = []
    
    def search_info(info_list):
        for info in info_list:
            if "Value" in info:
                value = info["Value"]
                if isinstance(value, dict) and "StringWithMarkup" in value:
                    for markup_item in value["StringWithMarkup"]:
                        text = markup_item.get("String", "")
                        if keyword.lower() in text.lower():
                            results.append(text)
    
    if "Information" in section:
        search_info(section["Information"])
    
    if "Section" in section:
        for subsection in section["Section"]:
            results.extend(_extract_text_from_section(subsection, keyword))
    
    return results


def _extract_all_text_from_section(section: Dict) -> List[str]:
    """Extract all text strings from a section recursively."""
    results = []
    
    def search_info(info_list):
        for info in info_list:
            if "Value" in info:
                value = info["Value"]
                if isinstance(value, dict) and "StringWithMarkup" in value:
                    for markup_item in value["StringWithMarkup"]:
                        text = markup_item.get("String", "")
                        if text:
                            results.append(text)
                elif isinstance(value, dict) and "String" in value:
                    text = value["String"]
                    if text:
                        results.append(text)
                elif isinstance(value, str):
                    results.append(value)
    
    if "Information" in section:
        search_info(section["Information"])
    
    if "Section" in section:
        for subsection in section["Section"]:
            results.extend(_extract_all_text_from_section(subsection))
    
    return results
