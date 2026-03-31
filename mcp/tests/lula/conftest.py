"""Fixtures for lula tool tests."""

import os
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

UR5E_URDF = "/home/kennychufk/workspace/cadWs/Universal_Robots_ROS2_Description/ur5e_fixed.urdf"
PIPER_URDF = (
    "/home/kennychufk/workspace/pythonWs/EI-project-isaac-sim-assets"
    "/piper_isaac_sim/piper_description/urdf/piper_description.urdf"
)


@pytest.fixture
def simple_arm_path():
    return os.path.join(FIXTURES_DIR, "simple_arm.urdf")


@pytest.fixture
def ur5e_path():
    if not os.path.exists(UR5E_URDF):
        pytest.skip("UR5e URDF not found at expected path")
    return UR5E_URDF


@pytest.fixture
def piper_path():
    if not os.path.exists(PIPER_URDF):
        pytest.skip("Piper URDF not found at expected path")
    return PIPER_URDF
