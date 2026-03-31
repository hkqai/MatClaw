"""
Tests for pubchem_search_compounds tool.

These tests make real HTTP requests to PubChem. An internet connection is
required. Well-known stable compounds (aspirin CID 2244, caffeine CID 2519,
ethanol CID 702, water CID 962) are used so results are consistent.

Run with: pytest tests/pubchem/test_pubchem_search_compounds.py -v
"""

import pytest
from tools.pubchem.pubchem_search_compounds import pubchem_search_compounds


# Basic search behaviour
class TestBasicSearch:

    def test_name_search_aspirin_success(self):
        """Searching 'aspirin' by name returns at least one result."""
        result = pubchem_search_compounds(identifier="aspirin", namespace="name")
        assert result["success"] is True
        assert result["count"] >= 1

    def test_aspirin_cid_is_2244(self):
        """Aspirin's canonical CID is 2244."""
        result = pubchem_search_compounds(identifier="aspirin", namespace="name", max_results=1)
        assert result["success"] is True
        assert result["compounds"][0]["cid"] == 2244

    def test_aspirin_molecular_formula(self):
        """Aspirin has molecular formula C9H8O4."""
        result = pubchem_search_compounds(identifier="aspirin", namespace="name", max_results=1)
        assert result["compounds"][0]["molecular_formula"] == "C9H8O4"

    def test_aspirin_inchikey(self):
        """Aspirin's InChIKey is stable and well-known."""
        result = pubchem_search_compounds(identifier="aspirin", namespace="name", max_results=1)
        assert result["compounds"][0]["inchikey"] == "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"

    def test_compound_has_smiles(self):
        """Returned compound includes a non-empty 'smiles' string."""
        result = pubchem_search_compounds(identifier="aspirin", namespace="name", max_results=1)
        smiles = result["compounds"][0]["smiles"]
        assert isinstance(smiles, str)
        assert len(smiles) > 0

    def test_compound_has_inchi(self):
        """Returned compound includes a non-empty 'inchi' string."""
        result = pubchem_search_compounds(identifier="aspirin", namespace="name", max_results=1)
        inchi = result["compounds"][0]["inchi"]
        assert isinstance(inchi, str)
        assert inchi.startswith("InChI=")

    def test_compound_has_synonyms_list(self):
        """synonyms is a list capped at 5 entries."""
        result = pubchem_search_compounds(identifier="aspirin", namespace="name", max_results=1)
        syns = result["compounds"][0]["synonyms"]
        assert isinstance(syns, list)
        assert len(syns) <= 5

    def test_compound_has_search_term(self):
        """Returned compound records the original search term."""
        result = pubchem_search_compounds(identifier="aspirin", namespace="name", max_results=1)
        assert result["compounds"][0]["search_term"] == "aspirin"

    def test_caffeine_cid_is_2519(self):
        """Caffeine's canonical CID is 2519."""
        result = pubchem_search_compounds(identifier="caffeine", namespace="name", max_results=1)
        assert result["success"] is True
        assert result["compounds"][0]["cid"] == 2519

    def test_caffeine_molecular_formula(self):
        """Caffeine has molecular formula C8H10N4O2."""
        result = pubchem_search_compounds(identifier="caffeine", namespace="name", max_results=1)
        assert result["compounds"][0]["molecular_formula"] == "C8H10N4O2"


# Query dictionary
class TestQueryDict:

    def test_query_dict_present(self):
        """'query' dict is always present in the result."""
        result = pubchem_search_compounds(identifier="aspirin")
        assert "query" in result
        assert isinstance(result["query"], dict)

    def test_query_echoes_identifier(self):
        """query.identifiers contains the original search term."""
        result = pubchem_search_compounds(identifier="aspirin")
        assert "aspirin" in result["query"]["identifiers"]

    def test_query_echoes_namespace(self):
        """query.namespace reflects the namespace passed in."""
        result = pubchem_search_compounds(identifier="CCO", namespace="smiles")
        assert result["query"]["namespace"] == "smiles"

    def test_query_echoes_max_results(self):
        """query.max_results reflects the limit passed in."""
        result = pubchem_search_compounds(identifier="aspirin", max_results=3)
        assert result["query"]["max_results"] == 3

    def test_query_searchtype_none_by_default(self):
        """query.searchtype is None when not supplied."""
        result = pubchem_search_compounds(identifier="aspirin")
        assert result["query"]["searchtype"] is None

    def test_single_string_stored_as_list(self):
        """A single string identifier is stored as a one-element list in query."""
        result = pubchem_search_compounds(identifier="aspirin")
        assert isinstance(result["query"]["identifiers"], list)
        assert len(result["query"]["identifiers"]) == 1


# Empty / no-results case
class TestEmptyResults:

    def test_nonexistent_compound_success_false(self):
        """A completely fabricated name returns success=False."""
        result = pubchem_search_compounds(identifier="xyznonexistentcompound99999999")
        assert result["success"] is False

    def test_nonexistent_compound_count_zero(self):
        """A completely fabricated name returns count=0."""
        result = pubchem_search_compounds(identifier="xyznonexistentcompound99999999")
        assert result["count"] == 0

    def test_nonexistent_compound_empty_list(self):
        """A completely fabricated name returns an empty compounds list."""
        result = pubchem_search_compounds(identifier="xyznonexistentcompound99999999")
        assert result["compounds"] == []

    def test_nonexistent_compound_has_error_key(self):
        """No results → 'error' key is present with a non-empty string."""
        result = pubchem_search_compounds(identifier="xyznonexistentcompound99999999")
        assert "error" in result
        assert isinstance(result["error"], str)
        assert len(result["error"]) > 0


# Namespace variants
class TestNamespaceVariants:

    def test_smiles_namespace_ethanol(self):
        """Searching ethanol by SMILES 'CCO' returns its CID 702."""
        result = pubchem_search_compounds(identifier="CCO", namespace="smiles", max_results=1)
        assert result["success"] is True
        assert result["compounds"][0]["cid"] == 702

    def test_formula_namespace_water(self):
        """Searching by formula 'H2O' returns at least one compound."""
        result = pubchem_search_compounds(identifier="H2O", namespace="formula", max_results=5)
        assert result["success"] is True
        assert result["count"] >= 1
        formulas = [c["molecular_formula"] for c in result["compounds"]]
        assert "H2O" in formulas

    def test_inchikey_namespace_aspirin(self):
        """Searching by aspirin's InChIKey returns CID 2244."""
        result = pubchem_search_compounds(
            identifier="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
            namespace="inchikey",
        )
        assert result["success"] is True
        assert result["compounds"][0]["cid"] == 2244

    def test_cid_namespace(self):
        """Searching by CID '2244' returns aspirin."""
        result = pubchem_search_compounds(identifier="2244", namespace="cid")
        assert result["success"] is True
        assert result["compounds"][0]["cid"] == 2244


# Multiple identifiers
class TestMultipleIdentifiers:

    def test_list_of_identifiers_aggregated(self):
        """Searching ['aspirin', 'caffeine'] returns at least two compounds."""
        result = pubchem_search_compounds(
            identifier=["aspirin", "caffeine"],
            namespace="name",
            max_results=1,
        )
        assert result["success"] is True
        assert result["count"] >= 2

    def test_duplicate_cids_deduplicated(self):
        """The same compound found via two synonyms appears only once."""
        result = pubchem_search_compounds(
            identifier=["aspirin", "acetylsalicylic acid"],
            namespace="name",
            max_results=1,
        )
        cids = [c["cid"] for c in result["compounds"]]
        assert len(cids) == len(set(cids))


# max_results limiting
class TestMaxResults:

    def test_max_results_respected(self):
        """Returned compound count does not exceed max_results."""
        result = pubchem_search_compounds(
            identifier="C6H6", namespace="formula", max_results=3
        )
        assert result["count"] <= 3

    def test_max_results_one(self):
        """max_results=1 returns exactly one compound for a known name."""
        result = pubchem_search_compounds(identifier="aspirin", max_results=1)
        assert result["count"] == 1


# Response structure
class TestResponseStructure:

    def test_all_top_level_fields_on_success(self):
        """Successful result contains all documented top-level fields."""
        result = pubchem_search_compounds(identifier="aspirin")
        for key in ("success", "query", "count", "compounds"):
            assert key in result, f"Missing key: {key}"

    def test_success_is_bool(self):
        """'success' is always a bool."""
        result = pubchem_search_compounds(identifier="aspirin")
        assert isinstance(result["success"], bool)

    def test_count_matches_compounds_length(self):
        """'count' always equals len(compounds)."""
        result = pubchem_search_compounds(identifier="caffeine")
        assert result["count"] == len(result["compounds"])

    def test_compounds_is_list(self):
        """'compounds' is always a list."""
        result = pubchem_search_compounds(identifier="aspirin")
        assert isinstance(result["compounds"], list)

    def test_each_compound_has_required_keys(self):
        """Every compound entry has cid, molecular_formula, smiles, inchi, inchikey, synonyms."""
        result = pubchem_search_compounds(identifier="aspirin", max_results=1)
        entry = result["compounds"][0]
        for key in ("cid", "molecular_formula", "smiles", "inchi", "inchikey", "synonyms"):
            assert key in entry, f"Missing compound key: {key}"

    def test_error_result_has_error_key(self):
        """Failed result always includes a non-empty 'error' string."""
        result = pubchem_search_compounds(identifier="xyznonexistentcompound99999999")
        assert result["success"] is False
        assert isinstance(result.get("error"), str)
        assert len(result["error"]) > 0
