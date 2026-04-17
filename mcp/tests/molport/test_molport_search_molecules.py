"""
Tests for molport_search_molecules tool.

These tests make real HTTP requests to Molport API. An internet connection and
a valid MOLPORT_API_KEY environment variable are required.

Run with: pytest tests/molport/test_molport_search_molecules.py -v
"""

import pytest
import os
from tools.molport.molport_search_molecules import molport_search_molecules


# Environment setup check
@pytest.fixture(scope="module")
def check_api_key():
    """Ensure MOLPORT_API_KEY is set before running tests."""
    api_key = os.getenv("MOLPORT_API_KEY")
    if not api_key:
        pytest.skip("MOLPORT_API_KEY environment variable not set")
    return api_key


# Basic search behaviour
class TestBasicSearch:

    def test_exact_search_success(self, check_api_key):
        """Searching a common molecule by SMILES returns results."""
        result = molport_search_molecules(
            smiles="CCO",  # Ethanol
            search_type="exact",
            max_results=10
        )
        assert "success" in result
        assert "count" in result
        assert "molecules" in result
        assert result["success"] is True, f"Search failed: {result.get('error', 'Unknown error')}"
        assert result["count"] > 0, "Expected at least one molecule for CCO"

    def test_exact_fragment_search_default(self, check_api_key):
        """Default search_type is exact_fragment."""
        result = molport_search_molecules(
            smiles="CCO",
            max_results=10
        )
        assert result["query"]["search_type"] == "exact_fragment"

    def test_molecules_have_molport_id(self, check_api_key):
        """Each returned molecule has a molport_id."""
        result = molport_search_molecules(
            smiles="CCO",
            search_type="exact",
            max_results=5
        )
        assert result["success"] is True
        assert len(result["molecules"]) > 0
        for molecule in result["molecules"]:
            assert "molport_id" in molecule
            assert molecule["molport_id"] is not None

    def test_molecules_have_smiles(self, check_api_key):
        """Each returned molecule has a SMILES string."""
        result = molport_search_molecules(
            smiles="CCO",
            search_type="exact",
            max_results=5
        )
        assert result["success"] is True
        assert len(result["molecules"]) > 0
        for molecule in result["molecules"]:
            assert "smiles" in molecule

    def test_molecules_have_canonical_smiles(self, check_api_key):
        """Each returned molecule has canonical SMILES."""
        result = molport_search_molecules(
            smiles="CCO",
            search_type="exact",
            max_results=5
        )
        assert result["success"] is True
        assert len(result["molecules"]) > 0
        for molecule in result["molecules"]:
            assert "canonical_smiles" in molecule

    def test_molecules_have_supplier_count(self, check_api_key):
        """Each returned molecule has supplier count information."""
        result = molport_search_molecules(
            smiles="CCO",
            search_type="exact",
            max_results=5
        )
        assert result["success"] is True
        assert len(result["molecules"]) > 0
        for molecule in result["molecules"]:
            assert "supplier_count" in molecule
            assert isinstance(molecule["supplier_count"], int)


# Query dictionary
class TestQueryDict:

    def test_query_dict_present(self, check_api_key):
        """'query' dict is always present in the result."""
        result = molport_search_molecules(smiles="CCO")
        assert "query" in result
        assert isinstance(result["query"], dict)

    def test_query_echoes_smiles(self, check_api_key):
        """query.smiles contains the original SMILES string."""
        test_smiles = "CC(C)O"
        result = molport_search_molecules(smiles=test_smiles)
        assert result["query"]["smiles"] == test_smiles

    def test_query_echoes_search_type(self, check_api_key):
        """query.search_type reflects the search type passed in."""
        result = molport_search_molecules(smiles="CCO", search_type="similarity")
        assert result["query"]["search_type"] == "similarity"

    def test_query_echoes_max_results(self, check_api_key):
        """query.max_results reflects the limit passed in."""
        result = molport_search_molecules(smiles="CCO", max_results=50)
        assert result["query"]["max_results"] == 50

    def test_query_includes_similarity_index(self, check_api_key):
        """query includes similarity_index when search_type is similarity."""
        result = molport_search_molecules(
            smiles="CCO",
            search_type="similarity",
            similarity_index=0.85
        )
        assert result["query"]["similarity_index"] == 0.85

    def test_query_compound_set(self, check_api_key):
        """query.compound_set reflects the set passed in."""
        result = molport_search_molecules(smiles="CCO", compound_set="all")
        assert result["query"]["compound_set"] == "all"


# Search type variants
class TestSearchTypes:

    def test_exact_search_type(self, check_api_key):
        """search_type='exact' executes without error."""
        result = molport_search_molecules(
            smiles="CCO",
            search_type="exact",
            max_results=5
        )
        assert "success" in result
        assert result["query"]["search_type"] == "exact"

    def test_similarity_search_type(self, check_api_key):
        """search_type='similarity' executes without error."""
        result = molport_search_molecules(
            smiles="CCO",
            search_type="similarity",
            similarity_index=0.9,
            max_results=5
        )
        assert "success" in result
        assert result["query"]["search_type"] == "similarity"

    def test_substructure_search_type(self, check_api_key):
        """search_type='substructure' executes without error."""
        result = molport_search_molecules(
            smiles="c1ccccc1",  # Benzene ring
            search_type="substructure",
            max_results=5
        )
        assert "success" in result
        assert result["query"]["search_type"] == "substructure"

    def test_exact_fragment_search_type(self, check_api_key):
        """search_type='exact_fragment' (default) executes without error."""
        result = molport_search_molecules(
            smiles="CCO",
            search_type="exact_fragment",
            max_results=5
        )
        assert "success" in result
        assert result["query"]["search_type"] == "exact_fragment"


# Max results limiting
class TestMaxResults:

    def test_max_results_limits_output(self, check_api_key):
        """Setting max_results=3 returns at most 3 molecules."""
        result = molport_search_molecules(
            smiles="CCO",
            search_type="similarity",
            max_results=3
        )
        if result["success"]:
            assert len(result["molecules"]) <= 3

    def test_count_matches_molecules_length(self, check_api_key):
        """result.count matches the length of result.molecules."""
        result = molport_search_molecules(
            smiles="CCO",
            search_type="exact",
            max_results=5
        )
        assert result["count"] == len(result["molecules"])


# Error handling
class TestErrorHandling:

    def test_missing_api_key_error(self):
        """Missing MOLPORT_API_KEY returns error."""
        original_key = os.getenv("MOLPORT_API_KEY")
        try:
            if original_key:
                del os.environ["MOLPORT_API_KEY"]
            
            result = molport_search_molecules(smiles="CCO")
            assert result["success"] is False
            assert "error" in result
            assert "MOLPORT_API_KEY" in result["error"]
        finally:
            if original_key:
                os.environ["MOLPORT_API_KEY"] = original_key

    def test_invalid_smiles_handling(self, check_api_key):
        """Invalid SMILES should be handled gracefully."""
        result = molport_search_molecules(
            smiles="INVALID_SMILES_12345",
            max_results=5
        )
        # Should not crash, should return structured response
        assert "success" in result
        assert "molecules" in result
        assert isinstance(result["molecules"], list)

    def test_no_results_returns_false_success(self, check_api_key):
        """When no molecules found, success should be False and error present."""
        result = molport_search_molecules(
            smiles="C" * 100,  # Very unlikely to match anything
            search_type="exact",
            max_results=5
        )
        if result["count"] == 0:
            assert result["success"] is False
            assert "error" in result


# Similarity index parameter
class TestSimilarityIndex:

    def test_similarity_index_default(self, check_api_key):
        """Default similarity_index is 0.9."""
        result = molport_search_molecules(
            smiles="CCO",
            search_type="similarity"
        )
        assert result["query"]["similarity_index"] == 0.9

    def test_similarity_index_custom(self, check_api_key):
        """Custom similarity_index is reflected in query."""
        result = molport_search_molecules(
            smiles="CCO",
            search_type="similarity",
            similarity_index=0.75
        )
        assert result["query"]["similarity_index"] == 0.75

    def test_similarity_index_only_for_similarity_search(self, check_api_key):
        """similarity_index in query is None for non-similarity searches."""
        result = molport_search_molecules(
            smiles="CCO",
            search_type="exact"
        )
        assert result["query"]["similarity_index"] is None
