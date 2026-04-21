"""
Tool for retrieving detailed molecule information and pricing from Molport database.
Requires MOLPORT_API_KEY environment variable with your Molport API key.
"""

from typing import Dict, Any, Annotated
from pydantic import Field
import requests
import os


def molport_get_molecule_info(
    molport_id: Annotated[
        int | str,
        Field(description="Molport molecule ID (e.g., 2325020). Obtained from molport_search_molecules.")
    ]
) -> Dict[str, Any]:
    """
    Retrieve detailed information and pricing for a specific molecule from Molport.
    
    Returns comprehensive data including:
        - Molecular identifiers (SMILES, IUPAC name, formula, molecular weight)
        - Pricing information from multiple suppliers
        - Availability, stock levels, and delivery times
        - Purity specifications and packaging options
        - Synonyms
    
    Use molport_search_molecules first to find molecule IDs, then use this tool
    to get detailed pricing and availability information.
    
    Examples:
        - Get pricing: molport_id=2325020
        - Get info: molport_id="Molport-002-325-020"
    
    Args:
        molport_id: Molport molecule identifier (integer or string, e.g., 2325020 or "Molport-002-325-020")
    
    Returns:
        Dictionary containing:
            - success (bool): Whether the request was successful
            - molport_id: The molecule ID queried
            - molecule (dict): Molecular properties including:
                - molport_id (int): Numeric Molport ID
                - molport_id_string (str): String Molport ID
                - smiles, canonical_smiles: SMILES notations
                - iupac_name: IUPAC name
                - molecular_formula, molecular_weight: Formula and weight
                - synonyms: List of synonym names (up to 5)
            - suppliers (list): List of supplier dictionaries with:
                - supplier_name, supplier_id: Supplier identification
                - supplier_type: "Screening Block Suppliers" or "Building Block Suppliers"
                - catalog_id, catalog_number: Catalog information
                - stock, stock_measure: Available quantity and unit
                - purity: Purity specification
                - currency, country: Supplier currency and location
                - packaging (list): Available packages with amount, measure, price, currency, delivery_days
            - supplier_count (int): Total number of suppliers
            - error (str, optional): Error message if request failed
    """
    try:
        # Get API key from environment
        api_key = os.getenv("MOLPORT_API_KEY")
        if not api_key:
            error_msg = "MOLPORT_API_KEY environment variable not set. Get your API key from https://www.molport.com/shop/api"
            return {
                "success": False,
                "molport_id": molport_id,
                "molecule": {},
                "suppliers": [],
                "supplier_count": 0,
                "error": error_msg
            }
        
        # Make API request
        response = requests.get(
            f"https://api.molport.com/api/molecule/load",
            params={"molecule": str(molport_id), "apikey": api_key},
            timeout=30
        )
        
        # Check response status
        if response.status_code != 200:
            error_msg = f"Molport API error: HTTP {response.status_code}"
            try:
                error_data = response.json()
                if "message" in error_data:
                    error_msg += f" - {error_data['message']}"
                elif "error" in error_data:
                    error_msg += f" - {error_data['error']}"
            except:
                pass
            
            return {
                "success": False,
                "molport_id": molport_id,
                "molecule": {},
                "suppliers": [],
                "supplier_count": 0,
                "error": error_msg
            }
        
        # Parse response
        data = response.json()
        
        # Check if molecule was found
        if not data or "Result" not in data or data["Result"].get("Status") != 1:
            error_msg = f"Molecule ID {molport_id} not found in Molport database"
            if data and "Result" in data and "Message" in data["Result"]:
                error_msg += f" - {data['Result']['Message']}"
            return {
                "success": False,
                "molport_id": molport_id,
                "molecule": {},
                "suppliers": [],
                "supplier_count": 0,
                "error": error_msg
            }
        
        # Extract molecule information from Data.Molecule
        molecule_data = data.get("Data", {}).get("Molecule", {})
        if not molecule_data:
            error_msg = f"Molecule ID {molport_id} not found in Molport database"
            return {
                "success": False,
                "molport_id": molport_id,
                "molecule": {},
                "suppliers": [],
                "supplier_count": 0,
                "error": error_msg
            }
        
        molecule_info = {
            "molport_id": molecule_data.get("Id"),
            "molport_id_string": molecule_data.get("Molport Id"),
            "smiles": molecule_data.get("SMILES"),
            "canonical_smiles": molecule_data.get("Canonical SMILES"),
            "iupac_name": molecule_data.get("IUPAC"),
            "molecular_formula": molecule_data.get("Formula"),
            "molecular_weight": molecule_data.get("Molecular Weight"),
            "status": molecule_data.get("Status"),
            "type": molecule_data.get("Type"),
            "largest_stock": molecule_data.get("Largest Stock"),
            "largest_stock_measure": molecule_data.get("Largest Stock Measure"),
            "synonyms": molecule_data.get("Synonyms", [])[:5] if molecule_data.get("Synonyms") else []
        }
        
        # Extract supplier and pricing information from Catalogues
        suppliers = []
        catalogues = molecule_data.get("Catalogues", {})
        
        # Process both Screening Block and Building Block suppliers
        for supplier_type in ["Screening Block Suppliers", "Building Block Suppliers"]:
            supplier_list = catalogues.get(supplier_type, [])
            if isinstance(supplier_list, list):
                for supplier_data in supplier_list:
                    supplier_name = supplier_data.get("Supplier Name")
                    supplier_id = supplier_data.get("Supplier Id")
                    supplier_currency = supplier_data.get("Currency")
                    country = supplier_data.get("Country Name")
                    
                    # Each supplier can have multiple catalog entries
                    for catalog in supplier_data.get("Catalogues", []):
                        supplier_info = {
                            "supplier_name": supplier_name,
                            "supplier_id": supplier_id,
                            "supplier_type": supplier_type,
                            "catalog_id": catalog.get("Catalog Id"),
                            "catalog_number": catalog.get("Catalog Number"),
                            "stock": catalog.get("Stock"),
                            "stock_measure": catalog.get("Stock Measure"),
                            "purity": catalog.get("Purity"),
                            "last_update": catalog.get("Last Update Date"),
                            "currency": supplier_currency,
                            "country": country,
                            "packaging": []
                        }
                        
                        # Extract packaging/pricing options
                        packings = catalog.get("Available Packings", [])
                        if isinstance(packings, list):
                            for package in packings:
                                package_info = {
                                    "amount": package.get("Amount"),
                                    "measure": package.get("Measure"),
                                    "price": package.get("Price"),
                                    "currency": package.get("Currency"),
                                    "delivery_days": package.get("Delivery Days"),
                                    "ship_by_air": package.get("Ship By Air", False)
                                }
                                supplier_info["packaging"].append(package_info)
                        
                        suppliers.append(supplier_info)
        
        # Prepare response
        result = {
            "success": True,
            "molport_id": molport_id,
            "molecule": molecule_info,
            "suppliers": suppliers,
            "supplier_count": len(suppliers)
        }
        
        if len(suppliers) == 0:
            result["warning"] = "No supplier pricing information available for this molecule"
        
        return result
        
    except requests.exceptions.Timeout:
        error_msg = "Request to Molport API timed out"
        return {
            "success": False,
            "molport_id": molport_id,
            "molecule": {},
            "suppliers": [],
            "supplier_count": 0,
            "error": error_msg
        }
    
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error accessing Molport API: {str(e)}"
        return {
            "success": False,
            "molport_id": molport_id,
            "molecule": {},
            "suppliers": [],
            "supplier_count": 0,
            "error": error_msg
        }
    
    except Exception as e:
        error_msg = f"Error retrieving molecule info from Molport: {str(e)}"
        return {
            "success": False,
            "molport_id": molport_id,
            "molecule": {},
            "suppliers": [],
            "supplier_count": 0,
            "error": error_msg
        }
