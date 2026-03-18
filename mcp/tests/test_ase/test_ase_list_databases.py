"""
Tests for ase_list_databases tool.

Run with: pytest tests/test_ase/test_ase_list_databases.py -v
"""

import pytest
import os
from pathlib import Path
from tools.ase.ase_list_databases import ase_list_databases


# Fixtures

@pytest.fixture
def empty_dir(tmp_path):
    """A temporary directory with no .db files."""
    d = tmp_path / "empty"
    d.mkdir()
    return str(d)


@pytest.fixture
def single_db_dir(tmp_path):
    """A temporary directory containing one valid empty ASE database."""
    from ase.db import connect
    d = tmp_path / "single"
    d.mkdir()
    db_path = str(d / "sim.db")
    db = connect(db_path)
    db.count()
    return str(d)


@pytest.fixture
def populated_dir(tmp_path):
    """A temporary directory with two populated ASE databases."""
    from ase.db import connect
    from ase.build import bulk, molecule
    from ase.calculators.singlepoint import SinglePointCalculator
    import numpy as np

    d = tmp_path / "populated"
    d.mkdir()

    # db1: two Cu entries
    db1 = connect(str(d / "copper.db"))
    cu = bulk("Cu", "fcc", a=3.6)
    cu.calc = SinglePointCalculator(cu, energy=-3.72)
    db1.write(cu, method="EMT")
    cu2 = bulk("Cu", "fcc", a=3.5)
    db1.write(cu2)

    # db2: one H2O entry with metadata
    db2 = connect(str(d / "molecules.db"))
    h2o = molecule("H2O")
    h2o.calc = SinglePointCalculator(h2o, energy=-14.22)
    db2.write(h2o, source="calculated", keywords="molecule")

    return str(d)


@pytest.fixture
def nested_dir(tmp_path):
    """A directory tree with .db files at different depths."""
    from ase.db import connect
    from ase.build import bulk

    root = tmp_path / "nested"
    root.mkdir()
    sub = root / "sub"
    sub.mkdir()

    # root-level db
    db_root = connect(str(root / "root.db"))
    db_root.write(bulk("Fe", "bcc", a=2.87))

    # sub-level db
    db_sub = connect(str(sub / "sub.db"))
    db_sub.write(bulk("Au", "fcc", a=4.08))

    return str(root)


@pytest.fixture
def mixed_dir(tmp_path):
    """A directory containing one valid ASE db and one plain text file renamed .db."""
    from ase.db import connect
    from ase.build import bulk

    d = tmp_path / "mixed"
    d.mkdir()

    # Valid ASE database
    db = connect(str(d / "valid.db"))
    db.write(bulk("Cu", "fcc", a=3.6))

    # Invalid "database" (plain text disguised as .db)
    (d / "fake.db").write_text("this is not an ase database")

    return str(d)


# Basic discovery

class TestBasicDiscovery:

    def test_empty_dir_returns_zero(self, empty_dir):
        """No .db files in directory → count=0."""
        result = ase_list_databases(search_dirs=[empty_dir])
        assert result["success"] is True
        assert result["count"] == 0
        assert result["databases"] == []

    def test_finds_single_db(self, single_db_dir):
        """Finds the one .db file present in the directory."""
        result = ase_list_databases(search_dirs=[single_db_dir])
        assert result["success"] is True
        assert result["count"] == 1

    def test_finds_multiple_dbs(self, populated_dir):
        """Finds both .db files in the directory."""
        result = ase_list_databases(search_dirs=[populated_dir])
        assert result["success"] is True
        assert result["count"] == 2

    def test_nonexistent_dir_returns_zero(self, tmp_path):
        """A directory that doesn't exist is silently skipped."""
        result = ase_list_databases(search_dirs=[str(tmp_path / "no_such_dir")])
        assert result["success"] is True
        assert result["count"] == 0

    def test_multiple_search_dirs(self, single_db_dir, populated_dir):
        """Supplying multiple search dirs aggregates results."""
        result = ase_list_databases(search_dirs=[single_db_dir, populated_dir])
        assert result["success"] is True
        assert result["count"] == 3  # 1 + 2

    def test_no_duplicate_entries(self, populated_dir):
        """Listing the same directory twice doesn't produce duplicate entries."""
        result = ase_list_databases(search_dirs=[populated_dir, populated_dir])
        assert result["success"] is True
        paths = [db["path"] for db in result["databases"]]
        assert len(paths) == len(set(paths))


# Per-entry structure

class TestEntryStructure:

    def test_each_entry_has_path(self, single_db_dir):
        """Every entry has a non-empty 'path' string."""
        result = ase_list_databases(search_dirs=[single_db_dir])
        for db in result["databases"]:
            assert "path" in db
            assert isinstance(db["path"], str)
            assert len(db["path"]) > 0

    def test_each_entry_has_filename(self, single_db_dir):
        """Every entry has a 'filename' ending in '.db'."""
        result = ase_list_databases(search_dirs=[single_db_dir])
        for db in result["databases"]:
            assert "filename" in db
            assert db["filename"].endswith(".db")

    def test_each_entry_has_size_bytes(self, single_db_dir):
        """Every entry has a non-negative integer 'size_bytes'."""
        result = ase_list_databases(search_dirs=[single_db_dir])
        for db in result["databases"]:
            assert "size_bytes" in db
            assert isinstance(db["size_bytes"], int)
            assert db["size_bytes"] >= 0

    def test_each_entry_has_size_mb(self, single_db_dir):
        """Every entry has a non-negative float 'size_mb'."""
        result = ase_list_databases(search_dirs=[single_db_dir])
        for db in result["databases"]:
            assert "size_mb" in db
            assert db["size_mb"] >= 0.0

    def test_each_entry_has_created_and_modified(self, single_db_dir):
        """Every entry has 'created' and 'modified' timestamps."""
        result = ase_list_databases(search_dirs=[single_db_dir])
        for db in result["databases"]:
            assert "created" in db
            assert "modified" in db

    def test_path_is_absolute(self, single_db_dir):
        """Returned paths are absolute."""
        result = ase_list_databases(search_dirs=[single_db_dir])
        for db in result["databases"]:
            assert os.path.isabs(db["path"])

    def test_filename_matches_basename_of_path(self, populated_dir):
        """filename == os.path.basename(path) for every entry."""
        result = ase_list_databases(search_dirs=[populated_dir])
        for db in result["databases"]:
            assert db["filename"] == os.path.basename(db["path"])


# Validation

class TestValidation:

    def test_valid_db_marked_valid_true(self, single_db_dir):
        """A genuine ASE database is marked valid=True when validate=True."""
        result = ase_list_databases(search_dirs=[single_db_dir], validate=True)
        assert result["success"] is True
        assert result["databases"][0]["valid"] is True

    def test_valid_count_accurate(self, populated_dir):
        """valid_count equals the number of entries with valid=True."""
        result = ase_list_databases(search_dirs=[populated_dir], validate=True)
        expected = sum(1 for db in result["databases"] if db.get("valid") is True)
        assert result["valid_count"] == expected

    def test_mixed_dir_valid_db_always_valid(self, mixed_dir):
        """A genuine ASE database in a mixed directory is always marked valid=True."""
        result = ase_list_databases(search_dirs=[mixed_dir], validate=True)
        assert result["success"] is True
        valids = {db["filename"]: db["valid"] for db in result["databases"]}
        # The real ASE database must be valid regardless of other files present.
        assert valids["valid.db"] is True
        # Both files must still be discovered.
        assert result["count"] == 2

    def test_validate_false_skips_validation(self, single_db_dir):
        """validate=False sets valid='not_validated' and doesn't attempt connection."""
        result = ase_list_databases(search_dirs=[single_db_dir], validate=False)
        assert result["success"] is True
        assert result["databases"][0]["valid"] == "not_validated"

    def test_entry_count_present_when_validated(self, populated_dir):
        """entry_count is present for valid databases when validate=True."""
        result = ase_list_databases(search_dirs=[populated_dir], validate=True)
        for db in result["databases"]:
            if db.get("valid") is True:
                assert "entry_count" in db
                assert isinstance(db["entry_count"], int)

    def test_entry_count_correct(self, populated_dir):
        """entry_count matches the actual number of rows in each database."""
        result = ase_list_databases(search_dirs=[populated_dir], validate=True)
        counts = {db["filename"]: db["entry_count"] for db in result["databases"] if db.get("valid")}
        assert counts["copper.db"] == 2
        assert counts["molecules.db"] == 1


# Summary statistics

class TestIncludeSummary:

    def test_formulas_present_when_summary_true(self, populated_dir):
        """formulas list is present when include_summary=True and db is non-empty."""
        result = ase_list_databases(search_dirs=[populated_dir], include_summary=True)
        assert result["success"] is True
        for db in result["databases"]:
            if db.get("valid") is True and db.get("entry_count", 0) > 0:
                assert "formulas" in db
                assert isinstance(db["formulas"], list)

    def test_formulas_are_unique(self, populated_dir):
        """Each formula appears only once in the formulas list."""
        result = ase_list_databases(search_dirs=[populated_dir], include_summary=True)
        for db in result["databases"]:
            if "formulas" in db:
                assert len(db["formulas"]) == len(set(db["formulas"]))

    def test_unique_formulas_count_accurate(self, populated_dir):
        """unique_formulas equals len(formulas)."""
        result = ase_list_databases(search_dirs=[populated_dir], include_summary=True)
        for db in result["databases"]:
            if "formulas" in db:
                assert db["unique_formulas"] == len(db["formulas"])

    def test_include_summary_false_omits_formulas(self, populated_dir):
        """formulas is absent when include_summary=False."""
        result = ase_list_databases(search_dirs=[populated_dir], include_summary=False)
        assert result["success"] is True
        for db in result["databases"]:
            assert "formulas" not in db

    def test_copper_db_contains_cu_formula(self, populated_dir):
        """copper.db summary includes 'Cu' in formulas."""
        result = ase_list_databases(search_dirs=[populated_dir], include_summary=True)
        copper = next(db for db in result["databases"] if db["filename"] == "copper.db")
        assert "Cu" in copper.get("formulas", [])

    def test_total_entries_is_sum_of_valid_entry_counts(self, populated_dir):
        """top-level total_entries equals sum of entry_count across valid dbs."""
        result = ase_list_databases(search_dirs=[populated_dir], validate=True)
        expected = sum(db.get("entry_count", 0) for db in result["databases"] if db.get("valid") is True)
        assert result["total_entries"] == expected

    def test_total_size_mb_is_non_negative(self, populated_dir):
        """total_size_mb is a non-negative float."""
        result = ase_list_databases(search_dirs=[populated_dir])
        assert result["total_size_mb"] >= 0.0


# Pattern filtering

class TestPatternFilter:

    def test_pattern_matches_specific_name(self, populated_dir):
        """pattern='copper.db' returns only the copper database."""
        result = ase_list_databases(search_dirs=[populated_dir], pattern="copper.db")
        assert result["success"] is True
        assert result["count"] == 1
        assert result["databases"][0]["filename"] == "copper.db"

    def test_wildcard_prefix_pattern(self, populated_dir):
        """pattern='mol*.db' matches only molecules.db."""
        result = ase_list_databases(search_dirs=[populated_dir], pattern="mol*.db")
        assert result["success"] is True
        assert result["count"] == 1
        assert result["databases"][0]["filename"] == "molecules.db"

    def test_pattern_no_match_returns_zero(self, populated_dir):
        """A pattern that matches nothing returns count=0."""
        result = ase_list_databases(search_dirs=[populated_dir], pattern="nonexistent_*.db")
        assert result["success"] is True
        assert result["count"] == 0

    def test_default_pattern_matches_all_db_files(self, populated_dir):
        """Default pattern '*.db' matches all .db files."""
        result = ase_list_databases(search_dirs=[populated_dir])
        assert result["success"] is True
        assert result["count"] == 2


# Recursive search

class TestRecursiveSearch:

    def test_non_recursive_misses_subdir_files(self, nested_dir):
        """recursive=False finds only root-level .db files."""
        result = ase_list_databases(search_dirs=[nested_dir], recursive=False)
        assert result["success"] is True
        filenames = [db["filename"] for db in result["databases"]]
        assert "root.db" in filenames
        assert "sub.db" not in filenames

    def test_recursive_finds_all_files(self, nested_dir):
        """recursive=True finds .db files in subdirectories as well."""
        result = ase_list_databases(search_dirs=[nested_dir], recursive=True)
        assert result["success"] is True
        filenames = [db["filename"] for db in result["databases"]]
        assert "root.db" in filenames
        assert "sub.db" in filenames

    def test_recursive_count_greater_than_non_recursive(self, nested_dir):
        """Recursive search returns more files than non-recursive when subdirs exist."""
        r_non = ase_list_databases(search_dirs=[nested_dir], recursive=False)
        r_rec = ase_list_databases(search_dirs=[nested_dir], recursive=True)
        assert r_rec["count"] > r_non["count"]


# Top-level response structure

class TestResponseStructure:

    def test_all_top_level_fields_present_on_success(self, single_db_dir):
        """Successful result contains all documented top-level fields."""
        result = ase_list_databases(search_dirs=[single_db_dir])
        for key in ("success", "count", "valid_count", "total_size_mb",
                    "total_entries", "databases", "search_info", "message"):
            assert key in result, f"Missing key: {key}"

    def test_success_is_bool(self, single_db_dir):
        """'success' is always a bool."""
        result = ase_list_databases(search_dirs=[single_db_dir])
        assert isinstance(result["success"], bool)

    def test_message_is_non_empty_string(self, single_db_dir):
        """'message' is a non-empty string."""
        result = ase_list_databases(search_dirs=[single_db_dir])
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0

    def test_search_info_echoes_parameters(self, populated_dir):
        """search_info reflects the parameters that were passed."""
        result = ase_list_databases(
            search_dirs=[populated_dir],
            pattern="*.db",
            recursive=False,
            validate=True,
        )
        si = result["search_info"]
        assert populated_dir in si["search_dirs"]
        assert si["pattern"] == "*.db"
        assert si["recursive"] is False
        assert si["validated"] is True

    def test_databases_is_list(self, populated_dir):
        """'databases' is always a list."""
        result = ase_list_databases(search_dirs=[populated_dir])
        assert isinstance(result["databases"], list)

    def test_count_matches_databases_length(self, populated_dir):
        """'count' equals len(databases)."""
        result = ase_list_databases(search_dirs=[populated_dir])
        assert result["count"] == len(result["databases"])

    def test_idempotent_successive_calls(self, populated_dir):
        """Calling the tool twice returns the same count."""
        r1 = ase_list_databases(search_dirs=[populated_dir])
        r2 = ase_list_databases(search_dirs=[populated_dir])
        assert r1["count"] == r2["count"]
