"""
Tests for ase_connect_or_create_db tool.

Run with: pytest tests/test_ase/test_ase_connect_or_create_db.py -v
"""

import pytest
import os
from pathlib import Path
from tools.ase.ase_connect_or_create_db import ase_connect_or_create_db


# Fixtures 

@pytest.fixture
def tmp_db_path(tmp_path):
    """Return a path to a non-existent SQLite database file inside a temp dir."""
    return str(tmp_path / "test.db")


@pytest.fixture
def existing_db(tmp_path):
    """Create a real (empty) ASE SQLite database and return its path."""
    from ase.db import connect
    db_path = str(tmp_path / "existing.db")
    db = connect(db_path)
    db.count()  # force file creation
    return db_path


@pytest.fixture
def populated_db(tmp_path):
    """Create an ASE SQLite database with one entry and return its path."""
    from ase.db import connect
    from ase.build import bulk
    db_path = str(tmp_path / "populated.db")
    db = connect(db_path)
    db.write(bulk("Cu", "fcc", a=3.6))
    return db_path


# Basic creation / connection

class TestCreateAndConnect:

    def test_creates_new_db(self, tmp_db_path):
        """Creates a new SQLite database when it does not exist."""
        result = ase_connect_or_create_db(db_path=tmp_db_path)
        assert result["success"] is True
        assert Path(tmp_db_path).exists()

    def test_returns_correct_path(self, tmp_db_path):
        """Result db_path matches the requested path."""
        result = ase_connect_or_create_db(db_path=tmp_db_path)
        assert result["success"] is True
        assert result["db_path"] == tmp_db_path

    def test_returns_sqlite_backend(self, tmp_db_path):
        """Backend reported as 'sqlite'."""
        result = ase_connect_or_create_db(db_path=tmp_db_path)
        assert result["success"] is True
        assert result["backend"] == "sqlite"

    def test_new_db_exists_false(self, tmp_db_path):
        """exists=False when the file did not exist before."""
        result = ase_connect_or_create_db(db_path=tmp_db_path)
        assert result["success"] is True
        assert result["exists"] is False

    def test_existing_db_exists_true(self, existing_db):
        """exists=True when connecting to a pre-existing database."""
        result = ase_connect_or_create_db(db_path=existing_db)
        assert result["success"] is True
        assert result["exists"] is True

    def test_new_db_zero_entries(self, tmp_db_path):
        """Newly created database reports 0 entries."""
        result = ase_connect_or_create_db(db_path=tmp_db_path)
        assert result["success"] is True
        assert result["count"] == 0

    def test_populated_db_correct_count(self, populated_db):
        """Database with one entry reports count=1."""
        result = ase_connect_or_create_db(db_path=populated_db)
        assert result["success"] is True
        assert result["count"] == 1

    def test_creates_parent_directories(self, tmp_path):
        """Missing parent directories are created automatically."""
        nested_path = str(tmp_path / "a" / "b" / "c" / "nested.db")
        result = ase_connect_or_create_db(db_path=nested_path)
        assert result["success"] is True
        assert Path(nested_path).exists()

    def test_success_message_present(self, tmp_db_path):
        """A human-readable message is always included."""
        result = ase_connect_or_create_db(db_path=tmp_db_path)
        assert result["success"] is True
        assert "message" in result
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0


# Writable / read-only modes 

class TestWritableModes:

    def test_append_true_is_writable(self, tmp_db_path):
        """append=True → writable=True."""
        result = ase_connect_or_create_db(db_path=tmp_db_path, append=True)
        assert result["success"] is True
        assert result["writable"] is True

    def test_append_false_is_readonly(self, existing_db):
        """append=False → writable=False when supported; failure is also acceptable."""
        result = ase_connect_or_create_db(db_path=existing_db, append=False)
        if result["success"]:
            assert result["writable"] is False
        else:
            # Some ASE/platform combinations refuse read-only SQLite connections;
            # the tool must still return a structured error in that case.
            assert "error" in result


# create_if_missing flag 

class TestCreateIfMissing:

    def test_create_if_missing_true_creates_file(self, tmp_db_path):
        """create_if_missing=True creates the file when absent."""
        result = ase_connect_or_create_db(db_path=tmp_db_path, create_if_missing=True)
        assert result["success"] is True
        assert Path(tmp_db_path).exists()

    def test_create_if_missing_false_errors_on_missing(self, tmp_db_path):
        """create_if_missing=False fails when the file does not exist."""
        result = ase_connect_or_create_db(db_path=tmp_db_path, create_if_missing=False)
        assert result["success"] is False
        assert "error" in result

    def test_create_if_missing_false_succeeds_on_existing(self, existing_db):
        """create_if_missing=False succeeds when the file already exists."""
        result = ase_connect_or_create_db(db_path=existing_db, create_if_missing=False)
        assert result["success"] is True


# Error handling 

class TestErrorHandling:

    def test_invalid_backend(self, tmp_db_path):
        """Unknown backend name returns an error."""
        result = ase_connect_or_create_db(db_path=tmp_db_path, backend="hdf5")
        assert result["success"] is False
        assert "error" in result

    def test_invalid_postgresql_connection_string(self):
        """Malformed PostgreSQL connection string returns an error."""
        result = ase_connect_or_create_db(
            db_path="not_a_valid_connection_string",
            backend="postgresql",
        )
        assert result["success"] is False
        assert "error" in result

    def test_invalid_mysql_connection_string(self):
        """Malformed MySQL connection string returns an error."""
        result = ase_connect_or_create_db(
            db_path="not_a_valid_connection_string",
            backend="mysql",
        )
        assert result["success"] is False
        assert "error" in result


# Response structure 

class TestResponseStructure:

    def test_all_expected_fields_on_success(self, tmp_db_path):
        """Successful result contains all documented fields."""
        result = ase_connect_or_create_db(db_path=tmp_db_path)
        for key in ("success", "db_path", "backend", "exists", "writable", "count", "message"):
            assert key in result, f"Missing key: {key}"

    def test_error_result_contains_error_key(self, tmp_db_path):
        """Failed result always contains an 'error' string."""
        result = ase_connect_or_create_db(db_path=tmp_db_path, create_if_missing=False)
        assert result["success"] is False
        assert isinstance(result.get("error"), str)
        assert len(result["error"]) > 0

    def test_idempotent_multiple_connections(self, tmp_db_path):
        """Connecting to the same path twice should succeed both times."""
        r1 = ase_connect_or_create_db(db_path=tmp_db_path)
        r2 = ase_connect_or_create_db(db_path=tmp_db_path)
        assert r1["success"] is True
        assert r2["success"] is True
        assert r2["exists"] is True  # second call sees the file created by the first
