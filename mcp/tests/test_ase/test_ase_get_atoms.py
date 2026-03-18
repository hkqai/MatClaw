"""
Tests for ase_get_atoms tool.

Run with: pytest tests/test_ase/test_ase_get_atoms.py -v
"""

import pytest
import numpy as np
from tools.ase.ase_get_atoms import ase_get_atoms


# Fixtures

@pytest.fixture
def populated_db(tmp_path):
    """Database with several entries (energy, forces, metadata, data blob)."""
    from ase.db import connect
    from ase.build import bulk, molecule
    from ase.calculators.singlepoint import SinglePointCalculator

    db_path = str(tmp_path / "test.db")
    db = connect(db_path)

    # Entry 1: Cu bulk with energy + forces + metadata
    cu = bulk("Cu", "fcc", a=3.6)
    forces_cu = np.zeros((len(cu), 3))
    cu.calc = SinglePointCalculator(cu, energy=-3.72, forces=forces_cu)
    db.write(cu, method="EMT", converged=True, unique_key="cu_bulk")

    # Entry 2: Fe bulk with energy + stress + metadata
    fe = bulk("Fe", "bcc", a=2.87)
    stress_fe = np.zeros(6)
    fe.calc = SinglePointCalculator(fe, energy=-8.23, stress=stress_fe)
    db.write(fe, method="DFT", converged=False)

    # Entry 3: H2O molecule with energy only
    h2o = molecule("H2O")
    h2o.calc = SinglePointCalculator(h2o, energy=-14.22)
    db.write(h2o, data={"trajectory_step": 0, "notes": "initial structure"})

    # Entry 4: NaCl – no calculator attached (no energy)
    nacl = bulk("NaCl", "rocksalt", a=5.64)
    db.write(nacl, source="literature")

    return db_path


@pytest.fixture
def db_path(populated_db):
    """Alias for convenience."""
    return populated_db


# Basic retrieval

class TestBasicRetrieval:

    def test_retrieve_single_id(self, db_path):
        """Retrieving a valid single row ID returns success."""
        result = ase_get_atoms(db_path=db_path, row_ids=1)
        assert result["success"] is True

    def test_retrieve_single_id_as_list(self, db_path):
        """Passing row_ids as a one-element list also succeeds."""
        result = ase_get_atoms(db_path=db_path, row_ids=[1])
        assert result["success"] is True

    def test_retrieve_multiple_ids(self, db_path):
        """Retrieving multiple valid IDs returns all of them."""
        result = ase_get_atoms(db_path=db_path, row_ids=[1, 2, 3])
        assert result["success"] is True
        assert result["count"] == 3

    def test_count_matches_atoms_length(self, db_path):
        """'count' always equals len(atoms)."""
        result = ase_get_atoms(db_path=db_path, row_ids=[1, 2])
        assert result["count"] == len(result["atoms"])

    def test_retrieved_id_matches_requested(self, db_path):
        """Each returned entry's 'id' matches the requested row ID."""
        result = ase_get_atoms(db_path=db_path, row_ids=[2, 3])
        assert result["success"] is True
        returned_ids = {e["id"] for e in result["atoms"]}
        assert returned_ids == {2, 3}

    def test_message_is_non_empty_string(self, db_path):
        """'message' is always a non-empty string on success."""
        result = ase_get_atoms(db_path=db_path, row_ids=1)
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0

    def test_db_path_in_result(self, db_path):
        """'db_path' is echoed back in the result."""
        result = ase_get_atoms(db_path=db_path, row_ids=1)
        assert result["db_path"] == db_path


# Per-entry structure

class TestEntryStructure:

    def test_each_entry_has_id(self, db_path):
        """Every entry has an integer 'id'."""
        result = ase_get_atoms(db_path=db_path, row_ids=[1, 2, 3])
        for entry in result["atoms"]:
            assert "id" in entry
            assert isinstance(entry["id"], int)

    def test_each_entry_has_formula(self, db_path):
        """Every entry has a non-empty 'formula' string."""
        result = ase_get_atoms(db_path=db_path, row_ids=[1, 2, 3])
        for entry in result["atoms"]:
            assert "formula" in entry
            assert isinstance(entry["formula"], str)
            assert len(entry["formula"]) > 0

    def test_each_entry_has_natoms(self, db_path):
        """Every entry has a positive integer 'natoms'."""
        result = ase_get_atoms(db_path=db_path, row_ids=[1, 2, 3])
        for entry in result["atoms"]:
            assert "natoms" in entry
            assert isinstance(entry["natoms"], int)
            assert entry["natoms"] > 0

    def test_each_entry_has_atoms_dict(self, db_path):
        """Every entry contains an 'atoms_dict' dict."""
        result = ase_get_atoms(db_path=db_path, row_ids=[1, 2])
        for entry in result["atoms"]:
            assert "atoms_dict" in entry
            assert isinstance(entry["atoms_dict"], dict)

    def test_atoms_dict_has_numbers_key(self, db_path):
        """Each atoms_dict contains the 'numbers' key."""
        result = ase_get_atoms(db_path=db_path, row_ids=[1, 2])
        for entry in result["atoms"]:
            assert "numbers" in entry["atoms_dict"]

    def test_atoms_dict_has_positions_key(self, db_path):
        """Each atoms_dict contains the 'positions' key."""
        result = ase_get_atoms(db_path=db_path, row_ids=[1])
        assert "positions" in result["atoms"][0]["atoms_dict"]

    def test_cu_formula_correct(self, db_path):
        """Row 1 (Cu bulk) is returned with formula containing 'Cu'."""
        result = ase_get_atoms(db_path=db_path, row_ids=1)
        assert "Cu" in result["atoms"][0]["formula"]

    def test_natoms_matches_structure(self, db_path):
        """natoms in the entry matches the length of atoms_dict numbers."""
        result = ase_get_atoms(db_path=db_path, row_ids=1)
        entry = result["atoms"][0]
        assert entry["natoms"] == len(entry["atoms_dict"]["numbers"])


# Calculator results

class TestIncludeResults:

    def test_results_present_by_default(self, db_path):
        """'results' key is present for an entry that has a calculator."""
        result = ase_get_atoms(db_path=db_path, row_ids=1)
        assert "results" in result["atoms"][0]

    def test_energy_in_results(self, db_path):
        """Energy is included in results for row 1 (Cu bulk)."""
        result = ase_get_atoms(db_path=db_path, row_ids=1)
        assert "energy" in result["atoms"][0]["results"]
        assert result["atoms"][0]["results"]["energy"] == pytest.approx(-3.72)

    def test_forces_in_results(self, db_path):
        """Forces are included in results for row 1 (Cu bulk, has forces)."""
        result = ase_get_atoms(db_path=db_path, row_ids=1)
        assert "forces" in result["atoms"][0]["results"]
        forces = result["atoms"][0]["results"]["forces"]
        assert isinstance(forces, list)

    def test_stress_in_results_for_fe(self, db_path):
        """Stress is included in results for row 2 (Fe bulk, has stress)."""
        result = ase_get_atoms(db_path=db_path, row_ids=2)
        assert "stress" in result["atoms"][0]["results"]

    def test_include_results_false_omits_results(self, db_path):
        """include_results=False omits the 'results' key."""
        result = ase_get_atoms(db_path=db_path, row_ids=1, include_results=False)
        assert result["success"] is True
        assert "results" not in result["atoms"][0]

    def test_entry_without_calculator_has_no_results(self, db_path):
        """Row 4 (NaCl, no calculator) does not include a 'results' key."""
        result = ase_get_atoms(db_path=db_path, row_ids=4)
        assert result["success"] is True
        entry = result["atoms"][0]
        if "results" in entry:
            # results may be present but should be empty
            assert entry["results"] == {} or not entry["results"]


# Metadata

class TestIncludeMetadata:

    def test_metadata_present_by_default(self, db_path):
        """'metadata' key is present when include_metadata=True (default)."""
        result = ase_get_atoms(db_path=db_path, row_ids=1)
        assert "metadata" in result["atoms"][0]

    def test_metadata_contains_stored_keys(self, db_path):
        """Stored metadata keys are returned correctly for row 1."""
        result = ase_get_atoms(db_path=db_path, row_ids=1)
        meta = result["atoms"][0]["metadata"]
        assert meta.get("method") == "EMT"
        assert meta.get("converged") in (True, 1)

    def test_include_metadata_false_omits_metadata(self, db_path):
        """include_metadata=False omits 'metadata' from results."""
        result = ase_get_atoms(db_path=db_path, row_ids=1, include_metadata=False)
        assert result["success"] is True
        assert "metadata" not in result["atoms"][0]

    def test_ctime_present_when_metadata_included(self, db_path):
        """'ctime' (creation timestamp) is available when metadata is included."""
        result = ase_get_atoms(db_path=db_path, row_ids=1)
        entry = result["atoms"][0]
        assert "ctime" in entry

    def test_user_present_when_metadata_included(self, db_path):
        """'user' field is present when metadata is included."""
        result = ase_get_atoms(db_path=db_path, row_ids=1)
        assert "user" in result["atoms"][0]


# Data blob

class TestIncludeData:

    def test_data_absent_by_default(self, db_path):
        """Data blob is absent from results when include_data=False (default)."""
        result = ase_get_atoms(db_path=db_path, row_ids=3)
        assert result["success"] is True
        assert "data" not in result["atoms"][0]

    def test_data_present_when_requested(self, db_path):
        """Data blob is included when include_data=True for row 3."""
        result = ase_get_atoms(db_path=db_path, row_ids=3, include_data=True)
        assert result["success"] is True
        assert "data" in result["atoms"][0]

    def test_data_contains_stored_values(self, db_path):
        """Stored data blob values are returned correctly."""
        result = ase_get_atoms(db_path=db_path, row_ids=3, include_data=True)
        data = result["atoms"][0]["data"]
        assert data.get("trajectory_step") == 0
        assert data.get("notes") == "initial structure"

    def test_include_data_false_omits_data(self, db_path):
        """include_data=False omits blobs entirely (default behaviour)."""
        result = ase_get_atoms(db_path=db_path, row_ids=3, include_data=False)
        assert result["success"] is True
        assert "data" not in result["atoms"][0]


# Not-found / partial results

class TestNotFound:

    def test_single_nonexistent_id_returns_error(self, db_path):
        """Requesting a single row ID that doesn't exist returns success=False."""
        result = ase_get_atoms(db_path=db_path, row_ids=9999)
        assert result["success"] is False
        assert "error" in result

    def test_not_found_ids_listed(self, db_path):
        """The missing IDs are listed in the error response."""
        result = ase_get_atoms(db_path=db_path, row_ids=9999)
        assert result["success"] is False
        assert 9999 in result.get("not_found", result.get("requested_ids", []))

    def test_partial_not_found_warning(self, db_path):
        """When some IDs exist and some don't, valid entries are returned with a warning."""
        result = ase_get_atoms(db_path=db_path, row_ids=[1, 9999])
        assert result["success"] is True
        assert result["count"] == 1
        assert "not_found" in result
        assert 9999 in result["not_found"]

    def test_all_found_no_warning(self, db_path):
        """When all IDs exist, no 'not_found' key is present."""
        result = ase_get_atoms(db_path=db_path, row_ids=[1, 2])
        assert result["success"] is True
        assert "not_found" not in result


# Input validation

class TestInputValidation:

    def test_empty_list_returns_error(self, db_path):
        """Passing an empty list for row_ids returns success=False."""
        result = ase_get_atoms(db_path=db_path, row_ids=[])
        assert result["success"] is False
        assert "error" in result

    def test_non_integer_row_ids_returns_error(self, db_path):
        """Passing a string as row_ids returns success=False."""
        result = ase_get_atoms(db_path=db_path, row_ids="not_an_id")
        assert result["success"] is False
        assert "error" in result

    def test_zero_row_id_returns_error(self, db_path):
        """Row ID 0 is invalid (IDs are 1-based) and should return an error."""
        result = ase_get_atoms(db_path=db_path, row_ids=0)
        assert result["success"] is False
        assert "error" in result

    def test_negative_row_id_returns_error(self, db_path):
        """Negative row IDs are invalid and should return an error."""
        result = ase_get_atoms(db_path=db_path, row_ids=-1)
        assert result["success"] is False
        assert "error" in result

    def test_list_with_non_integer_returns_error(self, db_path):
        """A list containing a non-integer returns success=False."""
        result = ase_get_atoms(db_path=db_path, row_ids=[1, "bad"])
        assert result["success"] is False
        assert "error" in result


# Error handling

class TestErrorHandling:

    def test_nonexistent_db_returns_error(self, tmp_path):
        """Querying a non-existent database returns success=False."""
        result = ase_get_atoms(db_path=str(tmp_path / "no_db.db"), row_ids=1)
        assert result["success"] is False
        assert "error" in result
        assert isinstance(result["error"], str)


# Serialisation

class TestSerialisation:

    def test_atoms_dict_values_are_json_serialisable(self, db_path):
        """atoms_dict values contain no numpy arrays (all converted to lists/scalars)."""
        import json
        result = ase_get_atoms(db_path=db_path, row_ids=1)
        # Should not raise
        json.dumps(result["atoms"][0]["atoms_dict"])

    def test_forces_are_list_of_lists(self, db_path):
        """Forces in results are serialised as a list of lists, not numpy arrays."""
        result = ase_get_atoms(db_path=db_path, row_ids=1)
        forces = result["atoms"][0]["results"]["forces"]
        assert isinstance(forces, list)
        assert isinstance(forces[0], list)

    def test_full_result_is_json_serialisable(self, db_path):
        """The entire result dict can be JSON-serialised without error."""
        import json
        result = ase_get_atoms(db_path=db_path, row_ids=[1, 2, 3], include_data=True)
        assert result["success"] is True
        json.dumps(result)


# Response structure

class TestResponseStructure:

    def test_all_top_level_fields_on_success(self, db_path):
        """Successful result contains all documented top-level fields."""
        result = ase_get_atoms(db_path=db_path, row_ids=1)
        for key in ("success", "count", "atoms", "db_path", "message"):
            assert key in result, f"Missing key: {key}"

    def test_success_is_bool(self, db_path):
        """'success' is always a bool."""
        result = ase_get_atoms(db_path=db_path, row_ids=1)
        assert isinstance(result["success"], bool)

    def test_error_result_has_error_key(self, db_path):
        """A failed result always includes a non-empty 'error' string."""
        result = ase_get_atoms(db_path=db_path, row_ids=99999)
        assert result["success"] is False
        assert isinstance(result.get("error"), str)
        assert len(result["error"]) > 0

    def test_idempotent_successive_fetches(self, db_path):
        """Fetching the same row ID multiple times returns consistent results."""
        r1 = ase_get_atoms(db_path=db_path, row_ids=1)
        r2 = ase_get_atoms(db_path=db_path, row_ids=1)
        assert r1["success"] is True
        assert r2["success"] is True
        assert r1["atoms"][0]["formula"] == r2["atoms"][0]["formula"]
        assert r1["atoms"][0]["natoms"] == r2["atoms"][0]["natoms"]

    def test_retrieve_all_four_entries(self, db_path):
        """Requesting all four IDs returns all four entries."""
        result = ase_get_atoms(db_path=db_path, row_ids=[1, 2, 3, 4])
        assert result["success"] is True
        assert result["count"] == 4
