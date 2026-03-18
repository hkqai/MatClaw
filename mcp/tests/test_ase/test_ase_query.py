"""
Tests for ase_query tool.

Run with: pytest tests/test_ase/test_ase_query.py -v
"""

import pytest
from pathlib import Path
from tools.ase.ase_query import ase_query


# Fixtures

@pytest.fixture
def empty_db(tmp_path):
    """Create and return a path to an empty ASE SQLite database."""
    from ase.db import connect
    db_path = str(tmp_path / "empty.db")
    db = connect(db_path)
    db.count()  # force file creation
    return db_path


@pytest.fixture
def populated_db(tmp_path):
    """Create a database with several entries covering different formulas,
    energies, and metadata, and return its path."""
    from ase.db import connect
    from ase.build import bulk, molecule
    from ase.calculators.singlepoint import SinglePointCalculator
    import numpy as np

    db_path = str(tmp_path / "populated.db")
    db = connect(db_path)

    # Entry 1: Cu bulk, energy=-3.72, method=EMT, converged=True, keywords=metal
    cu = bulk("Cu", "fcc", a=3.6)
    cu.calc = SinglePointCalculator(cu, energy=-3.72, forces=np.zeros((len(cu), 3)))
    db.write(cu, method="EMT", converged=True, keywords="metal", unique_key="cu_bulk")

    # Entry 2: Fe bulk, energy=-8.23, method=DFT, converged=True, keywords=metal,magnetic
    fe = bulk("Fe", "bcc", a=2.87)
    fe.calc = SinglePointCalculator(fe, energy=-8.23, forces=np.zeros((len(fe), 3)))
    db.write(fe, method="DFT", converged=True, keywords="metal,magnetic", unique_key="fe_bulk")

    # Entry 3: H2O molecule, energy=-14.22, method=DFT, converged=False, keywords=molecule
    h2o = molecule("H2O")
    h2o.calc = SinglePointCalculator(h2o, energy=-14.22)
    db.write(h2o, method="DFT", converged=False, keywords="molecule", unique_key="h2o_mol")

    # Entry 4: NaCl bulk, energy=-3.37, method=EMT, converged=True, keywords=ionic
    from ase import Atoms
    nacl = bulk("NaCl", "rocksalt", a=5.64)
    nacl.calc = SinglePointCalculator(nacl, energy=-3.37)
    db.write(nacl, method="EMT", converged=True, keywords="ionic", unique_key="nacl_bulk")

    # Entry 5: Cu bulk duplicate (different lattice param), energy=-3.50, no metadata
    cu2 = bulk("Cu", "fcc", a=3.5)
    cu2.calc = SinglePointCalculator(cu2, energy=-3.50)
    db.write(cu2, unique_key="cu_bulk_2")

    return db_path


# Basic query behaviour

class TestBasicQuery:

    def test_query_empty_db_returns_zero(self, empty_db):
        """Querying an empty database returns count=0 and empty results list."""
        result = ase_query(db_path=empty_db)
        assert result["success"] is True
        assert result["count"] == 0
        assert result["results"] == []

    def test_query_all_returns_all_entries(self, populated_db):
        """No filters → all entries are returned."""
        result = ase_query(db_path=populated_db)
        assert result["success"] is True
        assert result["count"] == 5

    def test_results_is_a_list(self, populated_db):
        """'results' is always a list on success."""
        result = ase_query(db_path=populated_db)
        assert isinstance(result["results"], list)

    def test_count_matches_results_length(self, populated_db):
        """'count' always equals len(results)."""
        result = ase_query(db_path=populated_db)
        assert result["count"] == len(result["results"])

    def test_message_is_non_empty_string(self, populated_db):
        """'message' is a non-empty string on success."""
        result = ase_query(db_path=populated_db)
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0

    def test_query_dict_present_in_result(self, populated_db):
        """'query' dict summarising the parameters is always present."""
        result = ase_query(db_path=populated_db)
        assert "query" in result
        assert isinstance(result["query"], dict)


# Per-entry structure

class TestEntryStructure:

    def test_each_entry_has_id(self, populated_db):
        """Every result entry has an integer 'id'."""
        result = ase_query(db_path=populated_db)
        for entry in result["results"]:
            assert "id" in entry
            assert isinstance(entry["id"], int)

    def test_each_entry_has_formula(self, populated_db):
        """Every result entry has a 'formula' string."""
        result = ase_query(db_path=populated_db)
        for entry in result["results"]:
            assert "formula" in entry
            assert isinstance(entry["formula"], str)

    def test_each_entry_has_natoms(self, populated_db):
        """Every result entry has a positive integer 'natoms'."""
        result = ase_query(db_path=populated_db)
        for entry in result["results"]:
            assert "natoms" in entry
            assert isinstance(entry["natoms"], int)
            assert entry["natoms"] > 0

    def test_each_entry_has_metadata_dict(self, populated_db):
        """Every result entry includes a 'metadata' dict."""
        result = ase_query(db_path=populated_db)
        for entry in result["results"]:
            assert "metadata" in entry
            assert isinstance(entry["metadata"], dict)

    def test_entries_with_energy_have_float(self, populated_db):
        """Entries that have energies report them as floats."""
        result = ase_query(db_path=populated_db)
        for entry in result["results"]:
            if "energy" in entry:
                assert isinstance(entry["energy"], float)

    def test_no_atoms_dict_by_default(self, populated_db):
        """atoms_dict is absent from entries when include_atoms=False (default)."""
        result = ase_query(db_path=populated_db)
        for entry in result["results"]:
            assert "atoms_dict" not in entry


# Formula filtering

class TestFormulaFilter:

    def test_exact_formula_match(self, populated_db):
        """formula_mode='exact' returns only entries whose formula matches exactly."""
        result = ase_query(db_path=populated_db, formula="Cu", formula_mode="exact")
        assert result["success"] is True
        assert result["count"] >= 1
        for entry in result["results"]:
            assert entry["formula"] == "Cu"

    def test_exact_formula_no_match(self, populated_db):
        """formula_mode='exact' returns zero results for a formula not present."""
        result = ase_query(db_path=populated_db, formula="Au", formula_mode="exact")
        assert result["success"] is True
        assert result["count"] == 0

    def test_reduced_formula_matches_stoichiometric_variants(self, populated_db):
        """formula_mode='reduced' matches entries sharing the reduced formula."""
        result = ase_query(db_path=populated_db, formula="Cu", formula_mode="reduced")
        assert result["success"] is True
        # Both Cu entries (a=3.6 and a=3.5) should match
        assert result["count"] >= 2

    def test_reduced_formula_no_match(self, populated_db):
        """formula_mode='reduced' returns zero results when reduced formula absent."""
        result = ase_query(db_path=populated_db, formula="Pt", formula_mode="reduced")
        assert result["success"] is True
        assert result["count"] == 0

    def test_formula_filter_for_nacl(self, populated_db):
        """NaCl can be found by formula."""
        result = ase_query(db_path=populated_db, formula="NaCl", formula_mode="reduced")
        assert result["success"] is True
        assert result["count"] >= 1
        for entry in result["results"]:
            assert "Na" in entry["formula"] or "Cl" in entry["formula"]


# Energy range filtering

class TestEnergyFilter:

    def test_energy_min_filters_out_low_energies(self, populated_db):
        """energy_min excludes entries with energy below the threshold."""
        result = ase_query(db_path=populated_db, energy_min=-5.0)
        assert result["success"] is True
        for entry in result["results"]:
            if "energy" in entry:
                assert entry["energy"] >= -5.0

    def test_energy_max_filters_out_high_energies(self, populated_db):
        """energy_max excludes entries with energy above the threshold."""
        result = ase_query(db_path=populated_db, energy_max=-4.0)
        assert result["success"] is True
        for entry in result["results"]:
            if "energy" in entry:
                assert entry["energy"] <= -4.0

    def test_energy_range_combined(self, populated_db):
        """Both energy_min and energy_max together create a window filter."""
        result = ase_query(db_path=populated_db, energy_min=-9.0, energy_max=-3.0)
        assert result["success"] is True
        for entry in result["results"]:
            if "energy" in entry:
                assert -9.0 <= entry["energy"] <= -3.0

    def test_energy_range_empty_window(self, populated_db):
        """An impossible energy window returns no results."""
        result = ase_query(db_path=populated_db, energy_min=-1.0, energy_max=-2.0)
        assert result["success"] is True
        assert result["count"] == 0


# Property (metadata) filtering

class TestPropertyFilters:

    def test_filter_by_string_metadata(self, populated_db):
        """property_filters with a string value matches only those entries."""
        result = ase_query(db_path=populated_db, property_filters={"method": "DFT"})
        assert result["success"] is True
        assert result["count"] >= 1
        for entry in result["results"]:
            assert entry["metadata"].get("method") == "DFT"

    def test_filter_by_boolean_metadata(self, populated_db):
        """property_filters with a boolean value works correctly."""
        result = ase_query(db_path=populated_db, property_filters={"converged": True})
        assert result["success"] is True
        assert result["count"] >= 1
        for entry in result["results"]:
            assert entry["metadata"].get("converged") in (True, 1)

    def test_filter_by_multiple_metadata_keys(self, populated_db):
        """Multiple property_filters keys are ANDed together."""
        result = ase_query(
            db_path=populated_db,
            property_filters={"method": "EMT", "converged": True},
        )
        assert result["success"] is True
        for entry in result["results"]:
            assert entry["metadata"].get("method") == "EMT"
            assert entry["metadata"].get("converged") in (True, 1)

    def test_filter_nonexistent_metadata_returns_empty(self, populated_db):
        """Filtering by a metadata key that no entry has returns count=0."""
        result = ase_query(db_path=populated_db, property_filters={"method": "CCSD"})
        assert result["success"] is True
        assert result["count"] == 0


# Tags filtering

class TestTagsFilter:

    def test_single_tag_filter(self, populated_db):
        """Filtering by a single tag returns matching entries."""
        result = ase_query(db_path=populated_db, tags=["magnetic"])
        assert result["success"] is True
        assert result["count"] >= 1

    def test_multiple_tags_any_match(self, populated_db):
        """Tags filter uses ANY semantics — at least one tag must match."""
        result = ase_query(db_path=populated_db, tags=["magnetic", "ionic"])
        assert result["success"] is True
        assert result["count"] >= 2

    def test_tag_that_matches_no_entry(self, populated_db):
        """A tag not stored in any entry returns count=0."""
        result = ase_query(db_path=populated_db, tags=["nonexistent_tag_xyz"])
        assert result["success"] is True
        assert result["count"] == 0

    def test_tag_filter_for_molecule(self, populated_db):
        """Tag 'molecule' returns only the H2O entry."""
        result = ase_query(db_path=populated_db, tags=["molecule"])
        assert result["success"] is True
        assert result["count"] == 1
        assert "H" in result["results"][0]["formula"]


# Unique key filtering

class TestUniqueKeyFilter:

    def test_unique_key_returns_one_entry(self, populated_db):
        """unique_key filter returns exactly one matching entry."""
        result = ase_query(db_path=populated_db, unique_key="cu_bulk")
        assert result["success"] is True
        assert result["count"] == 1

    def test_unique_key_correct_formula(self, populated_db):
        """Entry returned by unique_key has the expected formula."""
        result = ase_query(db_path=populated_db, unique_key="fe_bulk")
        assert result["success"] is True
        assert result["count"] == 1
        assert "Fe" in result["results"][0]["formula"]

    def test_unknown_unique_key_returns_empty(self, populated_db):
        """unique_key that doesn't exist returns count=0."""
        result = ase_query(db_path=populated_db, unique_key="does_not_exist")
        assert result["success"] is True
        assert result["count"] == 0


# Limit parameter

class TestLimit:

    def test_limit_restricts_result_count(self, populated_db):
        """limit=2 returns at most 2 entries."""
        result = ase_query(db_path=populated_db, limit=2)
        assert result["success"] is True
        assert len(result["results"]) <= 2

    def test_limit_one_returns_single_entry(self, populated_db):
        """limit=1 returns exactly one entry."""
        result = ase_query(db_path=populated_db, limit=1)
        assert result["success"] is True
        assert len(result["results"]) == 1

    def test_limit_larger_than_db_returns_all(self, populated_db):
        """A limit larger than the number of entries returns all entries."""
        result = ase_query(db_path=populated_db, limit=10000)
        assert result["success"] is True
        assert result["count"] == 5


# Sorting

class TestSorting:

    def test_sort_by_energy_ascending(self, populated_db):
        """sort_by='energy', sort_order='asc' returns entries in ascending energy order."""
        result = ase_query(db_path=populated_db, sort_by="energy", sort_order="asc")
        assert result["success"] is True
        energies = [e["energy"] for e in result["results"] if "energy" in e]
        assert energies == sorted(energies)

    def test_sort_by_energy_descending(self, populated_db):
        """sort_by='energy', sort_order='desc' returns entries in descending energy order."""
        result = ase_query(db_path=populated_db, sort_by="energy", sort_order="desc")
        assert result["success"] is True
        energies = [e["energy"] for e in result["results"] if "energy" in e]
        assert energies == sorted(energies, reverse=True)

    def test_sort_by_id_ascending(self, populated_db):
        """sort_by='id', sort_order='asc' returns entries in ascending ID order."""
        result = ase_query(db_path=populated_db, sort_by="id", sort_order="asc")
        assert result["success"] is True
        ids = [e["id"] for e in result["results"]]
        assert ids == sorted(ids)

    def test_sort_by_natoms(self, populated_db):
        """sort_by='natoms' sorts by number of atoms."""
        result = ase_query(db_path=populated_db, sort_by="natoms", sort_order="asc")
        assert result["success"] is True
        natoms = [e["natoms"] for e in result["results"]]
        assert natoms == sorted(natoms)


# include_atoms flag

class TestIncludeAtoms:

    def test_include_atoms_adds_atoms_dict(self, populated_db):
        """include_atoms=True adds 'atoms_dict' to every result entry."""
        result = ase_query(db_path=populated_db, include_atoms=True, limit=2)
        assert result["success"] is True
        for entry in result["results"]:
            assert "atoms_dict" in entry
            assert isinstance(entry["atoms_dict"], dict)

    def test_atoms_dict_has_numbers_key(self, populated_db):
        """Each atoms_dict contains the 'numbers' key (atomic numbers array)."""
        result = ase_query(db_path=populated_db, include_atoms=True, formula="Cu", formula_mode="exact")
        assert result["success"] is True
        for entry in result["results"]:
            assert "numbers" in entry["atoms_dict"]

    def test_include_atoms_false_no_atoms_dict(self, populated_db):
        """include_atoms=False (default) omits atoms_dict."""
        result = ase_query(db_path=populated_db, include_atoms=False)
        assert result["success"] is True
        for entry in result["results"]:
            assert "atoms_dict" not in entry


# Error handling

class TestErrorHandling:

    def test_nonexistent_db_returns_error(self, tmp_path):
        """Querying a non-existent database returns success=False."""
        result = ase_query(db_path=str(tmp_path / "does_not_exist.db"))
        # ASE may create the file or report an error — both are acceptable;
        # if it succeeds it must return an empty result.
        if not result["success"]:
            assert "error" in result
            assert isinstance(result["error"], str)
        else:
            assert result["count"] == 0

    def test_bad_property_filter_returns_error_or_empty(self, populated_db):
        """An unsupported property filter either returns an error or empty results."""
        result = ase_query(
            db_path=populated_db,
            property_filters={"!!invalid_key": "value"},
        )
        # The tool should not raise an unhandled exception.
        assert "success" in result


# Response structure

class TestResponseStructure:

    def test_all_top_level_fields_present_on_success(self, populated_db):
        """Successful result contains all documented top-level fields."""
        result = ase_query(db_path=populated_db)
        for key in ("success", "count", "results", "query", "message"):
            assert key in result, f"Missing key: {key}"

    def test_success_is_bool(self, populated_db):
        """'success' is always a bool."""
        result = ase_query(db_path=populated_db)
        assert isinstance(result["success"], bool)

    def test_error_result_contains_error_key(self, tmp_path):
        """A failed result always includes a non-empty 'error' string."""
        bad_path = str(tmp_path / "no_such.db")
        result = ase_query(db_path=bad_path)
        if not result["success"]:
            assert isinstance(result.get("error"), str)
            assert len(result["error"]) > 0

    def test_query_dict_reflects_parameters(self, populated_db):
        """query dict echoes back the parameters used."""
        result = ase_query(
            db_path=populated_db,
            formula="Cu",
            formula_mode="exact",
            limit=10,
        )
        assert result["success"] is True
        q = result["query"]
        assert q["formula"] == "Cu"
        assert q["limit"] == 10

    def test_combined_filters_work_together(self, populated_db):
        """formula + energy_max + property_filters all applied simultaneously."""
        result = ase_query(
            db_path=populated_db,
            formula="Cu",
            formula_mode="exact",
            energy_max=-3.6,
            property_filters={"converged": True},
        )
        assert result["success"] is True
        for entry in result["results"]:
            assert entry["formula"] == "Cu"
            if "energy" in entry:
                assert entry["energy"] <= -3.6
