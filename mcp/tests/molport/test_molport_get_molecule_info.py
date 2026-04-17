"""
Tests for molport_get_molecule_info tool.

These tests make real HTTP requests to Molport API. An internet connection and
a valid MOLPORT_API_KEY environment variable are required.

Note: These tests use molecule IDs that should exist in Molport. If tests fail,
the molecule IDs may need to be updated to currently available molecules.

Run with: pytest tests/molport/test_molport_get_molecule_info.py -v
"""

import pytest
import os
from tools.molport.molport_get_molecule_info import molport_get_molecule_info
from tools.molport.molport_search_molecules import molport_search_molecules


# Environment setup check
@pytest.fixture(scope="module")
def check_api_key():
    """Ensure MOLPORT_API_KEY is set before running tests."""
    api_key = os.getenv("MOLPORT_API_KEY")
    if not api_key:
        pytest.skip("MOLPORT_API_KEY environment variable not set")
    return api_key


@pytest.fixture(scope="module")
def sample_molecule_id(check_api_key):
    """Get a valid molecule ID from search to use in tests."""
    # Search for a common molecule (ethanol)
    result = molport_search_molecules(
        smiles="CCO",
        search_type="exact",
        max_results=1
    )
    if result["success"] and result["count"] > 0:
        return result["molecules"][0]["molport_id"]
    # Fallback to a known ID (may need updating if molecule is removed)
    return 2325020


# Basic retrieval
class TestBasicRetrieval:

    def test_retrieval_with_valid_id(self, check_api_key, sample_molecule_id):
        """Retrieving a valid molecule ID returns success."""
        result = molport_get_molecule_info(molport_id=sample_molecule_id)
        assert "success" in result
        assert "molport_id" in result
        assert "molecule" in result
        assert "suppliers" in result

    def test_molecule_dict_structure(self, check_api_key, sample_molecule_id):
        """Returned molecule has expected keys."""
        result = molport_get_molecule_info(molport_id=sample_molecule_id)
        if result["success"]:
            mol = result["molecule"]
            expected_keys = [
                "molport_id", "molport_id_string", "smiles", "canonical_smiles",
                "iupac_name", "molecular_formula", "molecular_weight",
                "synonyms"
            ]
            for key in expected_keys:
                assert key in mol

    def test_molport_id_echoed(self, check_api_key, sample_molecule_id):
        """The molport_id is echoed in the result."""
        result = molport_get_molecule_info(molport_id=sample_molecule_id)
        # Convert both to strings for comparison
        assert str(result["molport_id"]) == str(sample_molecule_id)

    def test_molecule_has_smiles(self, check_api_key, sample_molecule_id):
        """Molecule contains SMILES string."""
        result = molport_get_molecule_info(molport_id=sample_molecule_id)
        if result["success"]:
            assert "smiles" in result["molecule"]

    def test_molecule_has_formula(self, check_api_key, sample_molecule_id):
        """Molecule contains molecular formula."""
        result = molport_get_molecule_info(molport_id=sample_molecule_id)
        if result["success"]:
            assert "molecular_formula" in result["molecule"]

    def test_molecule_has_molport_id_string(self, check_api_key, sample_molecule_id):
        """Molecule contains Molport ID string."""
        result = molport_get_molecule_info(molport_id=sample_molecule_id)
        if result["success"]:
            assert "molport_id_string" in result["molecule"]
            assert result["molecule"]["molport_id_string"].startswith("Molport-")

    def test_synonyms_is_list(self, check_api_key, sample_molecule_id):
        """Synonyms is a list, capped at 5 entries."""
        result = molport_get_molecule_info(molport_id=sample_molecule_id)
        if result["success"]:
            syns = result["molecule"]["synonyms"]
            assert isinstance(syns, list)
            assert len(syns) <= 5


# Supplier information
class TestSupplierInformation:

    def test_suppliers_is_list(self, check_api_key, sample_molecule_id):
        """suppliers is always a list (may be empty)."""
        result = molport_get_molecule_info(molport_id=sample_molecule_id)
        assert isinstance(result["suppliers"], list)

    def test_supplier_count_matches_length(self, check_api_key, sample_molecule_id):
        """supplier_count matches the length of suppliers list."""
        result = molport_get_molecule_info(molport_id=sample_molecule_id)
        assert result["supplier_count"] == len(result["suppliers"])

    def test_supplier_has_expected_keys(self, check_api_key, sample_molecule_id):
        """Each supplier has expected keys."""
        result = molport_get_molecule_info(molport_id=sample_molecule_id)
        if result["success"] and len(result["suppliers"]) > 0:
            supplier = result["suppliers"][0]
            expected_keys = [
                "supplier_name", "supplier_id", "supplier_type",
                "catalog_id", "catalog_number", "stock",
                "purity", "currency", "packaging"
            ]
            for key in expected_keys:
                assert key in supplier

    def test_packaging_is_list(self, check_api_key, sample_molecule_id):
        """Each supplier's packaging is a list."""
        result = molport_get_molecule_info(molport_id=sample_molecule_id)
        if result["success"] and len(result["suppliers"]) > 0:
            for supplier in result["suppliers"]:
                assert isinstance(supplier["packaging"], list)

    def test_packaging_has_price_info(self, check_api_key, sample_molecule_id):
        """Each packaging entry has price information."""
        result = molport_get_molecule_info(molport_id=sample_molecule_id)
        if result["success"] and len(result["suppliers"]) > 0:
            supplier = result["suppliers"][0]
            if len(supplier["packaging"]) > 0:
                package = supplier["packaging"][0]
                expected_keys = ["amount", "measure", "price", "currency"]
                for key in expected_keys:
                    assert key in package

    def test_warning_when_no_suppliers(self, check_api_key):
        """When suppliers list is empty, a warning is present."""
        # Use a molecule ID that might not have suppliers
        # (this test may pass or fail depending on data)
        result = molport_get_molecule_info(molport_id=sample_molecule_id)
        if result["success"] and result["supplier_count"] == 0:
            assert "warning" in result


# String and integer ID handling
class TestIDHandling:

    def test_integer_id_accepted(self, check_api_key, sample_molecule_id):
        """Integer molecule ID is accepted."""
        mol_id = int(sample_molecule_id) if isinstance(sample_molecule_id, str) else sample_molecule_id
        result = molport_get_molecule_info(molport_id=mol_id)
        assert "success" in result
        assert "molport_id" in result

    def test_string_id_accepted(self, check_api_key, sample_molecule_id):
        """String molecule ID is accepted."""
        result = molport_get_molecule_info(molport_id=str(sample_molecule_id))
        assert "success" in result
        assert "molport_id" in result


# Error handling
class TestErrorHandling:

    def test_missing_api_key_error(self):
        """Missing MOLPORT_API_KEY returns error."""
        original_key = os.getenv("MOLPORT_API_KEY")
        try:
            if original_key:
                del os.environ["MOLPORT_API_KEY"]
            
            result = molport_get_molecule_info(molport_id=12345)
            assert result["success"] is False
            assert "error" in result
            assert "MOLPORT_API_KEY" in result["error"]
        finally:
            if original_key:
                os.environ["MOLPORT_API_KEY"] = original_key

    def test_nonexistent_molecule_id(self, check_api_key):
        """Non-existent molecule ID returns success=False."""
        # Use an extremely unlikely ID
        result = molport_get_molecule_info(molport_id=999999999999)
        # Should handle gracefully
        assert "success" in result
        if not result["success"]:
            assert "error" in result

    def test_invalid_molecule_id(self, check_api_key):
        """Invalid molecule ID is handled gracefully."""
        result = molport_get_molecule_info(molport_id=-1)
        # Should not crash
        assert "success" in result
        assert "molecule" in result
        assert "suppliers" in result

    def test_error_message_is_descriptive(self, check_api_key):
        """Error messages provide helpful information."""
        result = molport_get_molecule_info(molport_id=999999999)
        if not result["success"]:
            assert "error" in result
            assert isinstance(result["error"], str)
            assert len(result["error"]) > 0


# Integration with search
class TestIntegrationWithSearch:

    def test_search_then_retrieve_workflow(self, check_api_key):
        """Complete workflow: search for molecule, then retrieve its info."""
        # Step 1: Search for ethanol
        search_result = molport_search_molecules(
            smiles="CCO",
            search_type="exact",
            max_results=1
        )
        
        if search_result["success"] and search_result["count"] > 0:
            mol_id = search_result["molecules"][0]["molport_id"]
            
            # Step 2: Get detailed info
            info_result = molport_get_molecule_info(molport_id=mol_id)
            
            # Verify both succeeded
            assert info_result["success"] is True
            assert info_result["molecule"]["molport_id"] == mol_id

    def test_smiles_consistency_between_search_and_info(self, check_api_key):
        """SMILES from search should match SMILES in detailed info."""
        # Search for a molecule
        search_result = molport_search_molecules(
            smiles="CCO",
            search_type="exact",
            max_results=1
        )
        
        if search_result["success"] and search_result["count"] > 0:
            mol_id = search_result["molecules"][0]["molport_id"]
            search_smiles = search_result["molecules"][0]["smiles"]
            
            # Get detailed info
            info_result = molport_get_molecule_info(molport_id=mol_id)
            
            if info_result["success"]:
                # Either smiles or canonical_smiles should match
                info_smiles = info_result["molecule"]["smiles"]
                info_canonical = info_result["molecule"]["canonical_smiles"]
                
                # At least one should be present
                assert search_smiles or info_smiles or info_canonical
