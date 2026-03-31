"""Fixtures for URDF tool tests."""

import os
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def valid_robot_path():
    return os.path.join(FIXTURES_DIR, "valid_robot.urdf")


@pytest.fixture
def bad_names_path():
    return os.path.join(FIXTURES_DIR, "bad_names.urdf")


@pytest.fixture
def duplicate_materials_path():
    return os.path.join(FIXTURES_DIR, "duplicate_materials.urdf")


@pytest.fixture
def bad_joint_limits_path():
    return os.path.join(FIXTURES_DIR, "bad_joint_limits.urdf")


@pytest.fixture
def missing_inertial_path():
    return os.path.join(FIXTURES_DIR, "missing_inertial.urdf")


@pytest.fixture
def broken_mesh_refs_path():
    return os.path.join(FIXTURES_DIR, "broken_mesh_refs.urdf")


@pytest.fixture
def missing_collision_path():
    return os.path.join(FIXTURES_DIR, "missing_collision.urdf")


@pytest.fixture
def kitchen_sink_path():
    return os.path.join(FIXTURES_DIR, "kitchen_sink.urdf")
