"""
Tests for pubchem_get_compound_properties tool.

These tests make real HTTP requests to PubChem. An internet connection is
required. Well-known stable compounds are used so results are consistent:
    - Aspirin   CID 2244   C9H8O4   MW ~180.16
    - Caffeine  CID 2519   C8H10N4O2
    - Ethanol   CID 702    C2H6O
    - Water     CID 962    H2O

Run with: pytest tests/pubchem/test_pubchem_get_compound_properties.py -v
"""

import pytest
from tools.pubchem.pubchem_get_compound_properties import pubchem_get_compound_properties


# Basic single-CID retrieval
class TestBasicRetrieval:

    def test_single_cid_int_success(self):
        """Passing a single integer CID for aspirin returns success=True."""
        result = pubchem_get_compound_properties(cids=2244)
        assert result["success"] is True

    def test_single_cid_int_count_one(self):
        """Passing a single integer CID returns count=1."""
        result = pubchem_get_compound_properties(cids=2244)
        assert result["count"] == 1

    def test_single_cid_returns_one_property_dict(self):
        """Properties list contains exactly one entry for a single CID."""
        result = pubchem_get_compound_properties(cids=2244)
        assert isinstance(result["properties"], list)
        assert len(result["properties"]) == 1

    def test_cid_echoed_in_property_dict(self):
        """The CID field in the returned property dict matches the requested CID."""
        result = pubchem_get_compound_properties(cids=2244)
        assert result["properties"][0]["CID"] == 2244

    def test_aspirin_molecular_formula(self):
        """Aspirin (CID 2244) has molecular formula C9H8O4."""
        result = pubchem_get_compound_properties(
            cids=2244,
            properties=["MolecularFormula"]
        )
        assert result["properties"][0]["MolecularFormula"] == "C9H8O4"

    def test_aspirin_molecular_weight(self):
        """Aspirin molecular weight is approximately 180.16 Da."""
        result = pubchem_get_compound_properties(
            cids=2244,
            properties=["MolecularWeight"]
        )
        mw = result["properties"][0]["MolecularWeight"]
        assert abs(float(mw) - 180.16) < 0.05

    def test_aspirin_iupac_name(self):
        """Aspirin's IUPACName contains 'acetyloxy' or 'acetic acid'."""
        result = pubchem_get_compound_properties(
            cids=2244,
            properties=["IUPACName"]
        )
        iupac = result["properties"][0]["IUPACName"].lower()
        assert "acetyloxy" in iupac or "acetic" in iupac

    def test_caffeine_molecular_formula(self):
        """Caffeine (CID 2519) has molecular formula C8H10N4O2."""
        result = pubchem_get_compound_properties(
            cids=2519,
            properties=["MolecularFormula"]
        )
        assert result["properties"][0]["MolecularFormula"] == "C8H10N4O2"


# Response structure
class TestResponseStructure:

    def test_success_key_present(self):
        """Response always contains 'success' key."""
        result = pubchem_get_compound_properties(cids=2244)
        assert "success" in result

    def test_count_key_present(self):
        """Response always contains 'count' key."""
        result = pubchem_get_compound_properties(cids=2244)
        assert "count" in result

    def test_properties_key_present(self):
        """Response always contains 'properties' key as a list."""
        result = pubchem_get_compound_properties(cids=2244)
        assert "properties" in result
        assert isinstance(result["properties"], list)

    def test_requested_cids_echoed(self):
        """requested_cids in response matches the input CID(s)."""
        result = pubchem_get_compound_properties(cids=2244)
        assert result["requested_cids"] == [2244]

    def test_requested_properties_echoed_when_specified(self):
        """requested_properties echoes the explicitly requested list."""
        props = ["MolecularFormula", "MolecularWeight"]
        result = pubchem_get_compound_properties(cids=2244, properties=props)
        assert result["requested_properties"] == props

    def test_requested_properties_not_none_for_default(self):
        """When no properties specified, requested_properties is populated with defaults."""
        result = pubchem_get_compound_properties(cids=2244)
        assert result["requested_properties"] is not None
        assert isinstance(result["requested_properties"], list)
        assert len(result["requested_properties"]) > 0


# Default property set
class TestDefaultProperties:

    def test_default_includes_molecular_formula(self):
        """Default property set includes MolecularFormula."""
        result = pubchem_get_compound_properties(cids=2244)
        assert "MolecularFormula" in result["properties"][0]

    def test_default_includes_smiles(self):
        """Default property set includes a SMILES string (returned as 'SMILES' by pubchempy)."""
        result = pubchem_get_compound_properties(cids=2244)
        props = result["properties"][0]
        assert "SMILES" in props or "CanonicalSMILES" in props

    def test_default_includes_inchikey(self):
        """Default property set includes InChIKey."""
        result = pubchem_get_compound_properties(cids=2244)
        assert "InChIKey" in result["properties"][0]

    def test_aspirin_inchikey_value(self):
        """Aspirin InChIKey matches the canonical known value."""
        result = pubchem_get_compound_properties(cids=2244)
        assert result["properties"][0]["InChIKey"] == "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"


# Multiple CIDs
class TestMultipleCIDs:

    def test_list_of_cids_success(self):
        """Passing a list of two valid CIDs returns success=True."""
        result = pubchem_get_compound_properties(
            cids=[2244, 2519],
            properties=["MolecularFormula"]
        )
        assert result["success"] is True

    def test_list_of_cids_count(self):
        """Passing a list of two valid CIDs returns count=2."""
        result = pubchem_get_compound_properties(
            cids=[2244, 2519],
            properties=["MolecularFormula"]
        )
        assert result["count"] == 2

    def test_list_of_cids_correct_formulas(self):
        """Both compounds are returned with correct molecular formulas."""
        result = pubchem_get_compound_properties(
            cids=[2244, 2519],
            properties=["MolecularFormula"]
        )
        formulas = {p["CID"]: p["MolecularFormula"] for p in result["properties"]}
        assert formulas[2244] == "C9H8O4"
        assert formulas[2519] == "C8H10N4O2"

    def test_requested_cids_list_echoed(self):
        """requested_cids contains both CIDs when a list is provided."""
        result = pubchem_get_compound_properties(
            cids=[2244, 702],
            properties=["MolecularFormula"]
        )
        assert set(result["requested_cids"]) == {2244, 702}


# Invalid / nonexistent CID handling
class TestInvalidCIDs:

    def test_invalid_cid_returns_success_false(self):
        """A negative CID (invalid) returns success=False."""
        result = pubchem_get_compound_properties(cids=-1)
        assert result["success"] is False

    def test_invalid_cid_count_zero(self):
        """A negative CID (invalid) returns count=0."""
        result = pubchem_get_compound_properties(cids=-1)
        assert result["count"] == 0

    def test_invalid_cid_error_key_present(self):
        """A negative CID (invalid) adds an 'error' key to the response."""
        result = pubchem_get_compound_properties(cids=-1)
        assert "error" in result
        assert isinstance(result["error"], str)
        assert len(result["error"]) > 0

    def test_mixed_valid_invalid_partial_success(self):
        """One valid and one invalid CID → success=True with warnings."""
        result = pubchem_get_compound_properties(
            cids=[2244, -1],
            properties=["MolecularFormula"]
        )
        assert result["success"] is True
        assert result["count"] == 1
        assert "warnings" in result
        assert len(result["warnings"]) > 0
