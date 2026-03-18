"""
Tests for ase_store_result tool.

Run with: pytest tests/test_ase/test_ase_store_result.py -v
"""

import pytest
from pathlib import Path
from tools.ase.ase_store_result import ase_store_result


# Fixtures

@pytest.fixture
def tmp_db_path(tmp_path):
    """Return a path to a freshly created (empty) ASE SQLite database."""
    from ase.db import connect
    db_path = str(tmp_path / "test.db")
    db = connect(db_path)
    db.count()  # force file creation
    return db_path


@pytest.fixture
def copper_atoms_dict():
    """Return a serialised bulk Cu Atoms object (atoms.todict())."""
    from ase.build import bulk
    return bulk("Cu", "fcc", a=3.6).todict()


@pytest.fixture
def water_atoms_dict():
    """Return a serialised water molecule Atoms object."""
    from ase import Atoms
    import numpy as np
    atoms = Atoms(
        "H2O",
        positions=[[0, 0, 0], [0, 0, 1.0], [0, 1.0, 0]],
        cell=[10, 10, 10],
        pbc=False,
    )
    return atoms.todict()


@pytest.fixture
def sample_results():
    """Return a minimal calculator results dict."""
    import numpy as np
    return {
        "energy": -3.72,
        "forces": [[0.0, 0.0, 0.0], [0.1, -0.1, 0.0], [0.0, 0.0, 0.0]],
    }


# Basic storage

class TestBasicStorage:

    def test_stores_new_entry(self, tmp_db_path, copper_atoms_dict):
        """Successfully stores a new Atoms entry and returns success."""
        result = ase_store_result(db_path=tmp_db_path, atoms_dict=copper_atoms_dict)
        assert result["success"] is True

    def test_returns_integer_row_id(self, tmp_db_path, copper_atoms_dict):
        """Returned row_id is a positive integer."""
        result = ase_store_result(db_path=tmp_db_path, atoms_dict=copper_atoms_dict)
        assert result["success"] is True
        assert isinstance(result["row_id"], int)
        assert result["row_id"] >= 1

    def test_returns_correct_db_path(self, tmp_db_path, copper_atoms_dict):
        """Returned db_path matches the requested path."""
        result = ase_store_result(db_path=tmp_db_path, atoms_dict=copper_atoms_dict)
        assert result["success"] is True
        assert result["db_path"] == tmp_db_path

    def test_returns_correct_formula(self, tmp_db_path, copper_atoms_dict):
        """Returned formula reflects the stored structure."""
        result = ase_store_result(db_path=tmp_db_path, atoms_dict=copper_atoms_dict)
        assert result["success"] is True
        assert "Cu" in result["formula"]

    def test_returns_n_atoms(self, tmp_db_path, copper_atoms_dict):
        """Returned n_atoms is a positive integer."""
        result = ase_store_result(db_path=tmp_db_path, atoms_dict=copper_atoms_dict)
        assert result["success"] is True
        assert isinstance(result["n_atoms"], int)
        assert result["n_atoms"] > 0

    def test_new_entry_updated_false(self, tmp_db_path, copper_atoms_dict):
        """updated=False for a brand-new entry (no unique_key collision)."""
        result = ase_store_result(db_path=tmp_db_path, atoms_dict=copper_atoms_dict)
        assert result["success"] is True
        assert result["updated"] is False

    def test_multiple_entries_get_unique_ids(self, tmp_db_path, copper_atoms_dict, water_atoms_dict):
        """Two separate writes produce different row IDs."""
        r1 = ase_store_result(db_path=tmp_db_path, atoms_dict=copper_atoms_dict)
        r2 = ase_store_result(db_path=tmp_db_path, atoms_dict=water_atoms_dict)
        assert r1["success"] is True
        assert r2["success"] is True
        assert r1["row_id"] != r2["row_id"]

    def test_entry_persists_in_database(self, tmp_db_path, copper_atoms_dict):
        """Stored entry can be read back from the database."""
        from ase.db import connect
        ase_store_result(db_path=tmp_db_path, atoms_dict=copper_atoms_dict)
        db = connect(tmp_db_path)
        assert db.count() >= 1

    def test_creates_db_if_not_exists(self, tmp_path, copper_atoms_dict):
        """Tool creates the database file when it does not yet exist."""
        db_path = str(tmp_path / "new.db")
        result = ase_store_result(db_path=db_path, atoms_dict=copper_atoms_dict)
        assert result["success"] is True
        assert Path(db_path).exists()


# Storing with calculator results

class TestWithResults:

    def test_stores_energy(self, tmp_db_path, copper_atoms_dict):
        """Energy is stored and returned when provided in results dict."""
        results = {"energy": -3.72}
        result = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            results=results,
        )
        assert result["success"] is True
        assert "energy" in result
        assert result["energy"] == pytest.approx(-3.72)

    def test_stores_energy_and_forces(self, tmp_db_path, copper_atoms_dict):
        """Energy and forces are both stored without error."""
        import numpy as np
        n_atoms = len(copper_atoms_dict["numbers"])
        results = {
            "energy": -3.72,
            "forces": np.zeros((n_atoms, 3)).tolist(),
        }
        result = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            results=results,
        )
        assert result["success"] is True
        assert result["energy"] == pytest.approx(-3.72)

    def test_stores_with_stress(self, tmp_db_path, copper_atoms_dict):
        """Stress tensor is accepted without error."""
        import numpy as np
        results = {
            "energy": -3.72,
            "stress": np.zeros(6).tolist(),
        }
        result = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            results=results,
        )
        assert result["success"] is True

    def test_no_energy_key_absent_when_results_none(self, tmp_db_path, copper_atoms_dict):
        """'energy' key is absent from result when no results are provided."""
        result = ase_store_result(db_path=tmp_db_path, atoms_dict=copper_atoms_dict)
        assert result["success"] is True
        assert "energy" not in result

    def test_energy_persists_in_database(self, tmp_db_path, copper_atoms_dict):
        """Stored energy can be retrieved from the database."""
        from ase.db import connect
        results = {"energy": -3.72}
        r = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            results=results,
        )
        db = connect(tmp_db_path)
        row = db.get(id=r["row_id"])
        assert row.energy == pytest.approx(-3.72)


# Storing with key_value_pairs metadata

class TestWithKeyValuePairs:

    def test_stores_string_metadata(self, tmp_db_path, copper_atoms_dict):
        """String metadata key-value pairs are stored without error."""
        result = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            key_value_pairs={"method": "DFT_PBE"},
        )
        assert result["success"] is True

    def test_stores_numeric_metadata(self, tmp_db_path, copper_atoms_dict):
        """Numeric metadata values are stored without error."""
        result = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            key_value_pairs={"temperature": 300},
        )
        assert result["success"] is True

    def test_stores_boolean_metadata(self, tmp_db_path, copper_atoms_dict):
        """Boolean metadata values are stored without error."""
        result = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            key_value_pairs={"converged": True},
        )
        assert result["success"] is True

    def test_metadata_persists_in_database(self, tmp_db_path, copper_atoms_dict):
        """String metadata can be read back from the database."""
        from ase.db import connect
        r = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            key_value_pairs={"campaign_id": "test_run"},
        )
        db = connect(tmp_db_path)
        row = db.get(id=r["row_id"])
        assert row.campaign_id == "test_run"

    def test_invalid_metadata_key_returns_error(self, tmp_db_path, copper_atoms_dict):
        """Metadata keys with invalid characters return an error."""
        result = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            key_value_pairs={"invalid-key!": "value"},
        )
        assert result["success"] is False
        assert "error" in result

    def test_none_key_value_pairs_ignored(self, tmp_db_path, copper_atoms_dict):
        """key_value_pairs=None stores the entry without error."""
        result = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            key_value_pairs=None,
        )
        assert result["success"] is True


# Unique key deduplication and updating

class TestUniqueKey:

    def test_unique_key_stored_in_result(self, tmp_db_path, copper_atoms_dict):
        """unique_key is echoed back in the success result."""
        result = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            unique_key="cu_bulk_v1",
        )
        assert result["success"] is True
        assert result["unique_key"] == "cu_bulk_v1"

    def test_first_write_updated_false(self, tmp_db_path, copper_atoms_dict):
        """First write with a unique_key reports updated=False."""
        result = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            unique_key="cu_bulk_v1",
        )
        assert result["success"] is True
        assert result["updated"] is False

    def test_second_write_updated_true(self, tmp_db_path, copper_atoms_dict):
        """Second write with the same unique_key reports updated=True."""
        ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            unique_key="cu_bulk_v1",
        )
        result = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            unique_key="cu_bulk_v1",
        )
        assert result["success"] is True
        assert result["updated"] is True

    def test_second_write_reuses_same_row_id(self, tmp_db_path, copper_atoms_dict):
        """Updating an entry via unique_key preserves the original row ID."""
        r1 = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            unique_key="cu_bulk_v1",
        )
        r2 = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            unique_key="cu_bulk_v1",
        )
        assert r1["row_id"] == r2["row_id"]

    def test_different_unique_keys_create_separate_entries(
        self, tmp_db_path, copper_atoms_dict
    ):
        """Two different unique_keys produce two distinct row IDs."""
        r1 = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            unique_key="key_a",
        )
        r2 = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            unique_key="key_b",
        )
        assert r1["success"] is True
        assert r2["success"] is True
        assert r1["row_id"] != r2["row_id"]


# Storing with arbitrary data blob

class TestWithData:

    def test_stores_data_blob(self, tmp_db_path, copper_atoms_dict):
        """Arbitrary data dict is stored without error."""
        result = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            data={"trajectory": [1, 2, 3], "notes": "test run"},
        )
        assert result["success"] is True

    def test_none_data_ignored(self, tmp_db_path, copper_atoms_dict):
        """data=None stores the entry without error."""
        result = ase_store_result(
            db_path=tmp_db_path,
            atoms_dict=copper_atoms_dict,
            data=None,
        )
        assert result["success"] is True


# Error handling

class TestErrorHandling:

    def test_missing_numbers_key_returns_error(self, tmp_db_path):
        """atoms_dict missing 'numbers' key returns an error."""
        bad_dict = {"positions": [[0, 0, 0]], "cell": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}
        result = ase_store_result(db_path=tmp_db_path, atoms_dict=bad_dict)
        assert result["success"] is False
        assert "error" in result

    def test_non_dict_atoms_dict_returns_error(self, tmp_db_path):
        """Passing a non-dict as atoms_dict returns an error."""
        result = ase_store_result(db_path=tmp_db_path, atoms_dict="not_a_dict")
        assert result["success"] is False
        assert "error" in result

    def test_corrupted_atoms_dict_returns_error(self, tmp_db_path):
        """A dict with 'numbers' but nonsense values returns an error."""
        bad_dict = {"numbers": "not_an_array", "positions": None, "cell": None}
        result = ase_store_result(db_path=tmp_db_path, atoms_dict=bad_dict)
        assert result["success"] is False
        assert "error" in result

    def test_nonexistent_directory_db_path(self, tmp_path, copper_atoms_dict):
        """A db_path in a deeply nested non-existent directory either succeeds
        (tool creates dirs) or returns a structured error."""
        db_path = str(tmp_path / "a" / "b" / "c" / "sim.db")
        result = ase_store_result(db_path=db_path, atoms_dict=copper_atoms_dict)
        # Either success (tool auto-creates dirs) or a structured failure
        if result["success"]:
            assert Path(db_path).exists()
        else:
            assert "error" in result
            assert isinstance(result["error"], str)


# Response structure

class TestResponseStructure:

    def test_all_expected_fields_on_success(self, tmp_db_path, copper_atoms_dict):
        """Successful result contains all documented fields."""
        result = ase_store_result(db_path=tmp_db_path, atoms_dict=copper_atoms_dict)
        for key in ("success", "row_id", "db_path", "formula", "n_atoms", "updated", "message"):
            assert key in result, f"Missing key: {key}"

    def test_success_is_bool(self, tmp_db_path, copper_atoms_dict):
        """'success' field is always a bool."""
        result = ase_store_result(db_path=tmp_db_path, atoms_dict=copper_atoms_dict)
        assert isinstance(result["success"], bool)

    def test_message_is_non_empty_string(self, tmp_db_path, copper_atoms_dict):
        """'message' field is a non-empty string on success."""
        result = ase_store_result(db_path=tmp_db_path, atoms_dict=copper_atoms_dict)
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0

    def test_error_result_contains_error_key(self, tmp_db_path):
        """Failed result always includes an 'error' string."""
        result = ase_store_result(db_path=tmp_db_path, atoms_dict="bad")
        assert result["success"] is False
        assert isinstance(result.get("error"), str)
        assert len(result["error"]) > 0

    def test_idempotent_successive_stores(self, tmp_db_path, copper_atoms_dict):
        """Calling the tool multiple times without unique_key always succeeds."""
        for _ in range(3):
            result = ase_store_result(db_path=tmp_db_path, atoms_dict=copper_atoms_dict)
            assert result["success"] is True
