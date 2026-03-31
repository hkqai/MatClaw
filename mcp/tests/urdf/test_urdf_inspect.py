"""Tests for urdf_inspect tool."""

import pytest
from tools.urdf import urdf_inspect


class TestBasicInspect:
    """Basic structural inspection."""

    def test_valid_robot(self, valid_robot_path):
        result = urdf_inspect(file_path=valid_robot_path)
        assert result["success"] is True
        assert result["robot_name"] == "valid_robot"
        assert result["link_count"] == 2
        assert result["joint_count"] == 1
        assert result["root_link"] == "base_link"

    def test_joint_types(self, valid_robot_path):
        result = urdf_inspect(file_path=valid_robot_path)
        assert "revolute" in result["joint_types"]
        assert result["joint_types"]["revolute"] == 1

    def test_mass(self, valid_robot_path):
        result = urdf_inspect(file_path=valid_robot_path)
        assert result["total_mass"] == 1.5  # 1.0 + 0.5


class TestKinematicTree:
    """Kinematic tree visualization."""

    def test_tree_contains_links(self, valid_robot_path):
        result = urdf_inspect(file_path=valid_robot_path)
        tree = result["kinematic_tree"]
        assert "base_link" in tree
        assert "child_link" in tree

    def test_tree_contains_joints(self, valid_robot_path):
        result = urdf_inspect(file_path=valid_robot_path)
        tree = result["kinematic_tree"]
        assert "base_to_child" in tree


class TestMeshFiles:
    """Mesh file listing."""

    def test_broken_mesh_listed(self, broken_mesh_refs_path):
        result = urdf_inspect(file_path=broken_mesh_refs_path)
        assert len(result["mesh_files"]) >= 2
        filenames = [m["filename"] for m in result["mesh_files"]]
        assert any("nonexistent_visual" in f for f in filenames)


class TestMaterials:
    """Material listing."""

    def test_materials_listed(self, duplicate_materials_path):
        result = urdf_inspect(file_path=duplicate_materials_path)
        assert len(result["materials"]) >= 1
        names = [m["name"] for m in result["materials"]]
        assert "red" in names
        assert "green" in names


class TestComplexRobot:
    """Test with the kitchen sink fixture."""

    def test_kitchen_sink(self, kitchen_sink_path):
        result = urdf_inspect(file_path=kitchen_sink_path)
        assert result["success"] is True
        assert result["link_count"] == 2
        assert result["joint_count"] == 1


class TestUrdfString:
    """Test with string input."""

    def test_string_input(self):
        urdf = '''<robot name="mini">
            <link name="a"><inertial><mass value="1.0"/>
                <inertia ixx="0.01" ixy="0" ixz="0" iyy="0.01" iyz="0" izz="0.01"/>
            </inertial></link>
            <link name="b"/>
            <joint name="j" type="fixed">
                <parent link="a"/><child link="b"/>
            </joint>
        </robot>'''
        result = urdf_inspect(urdf_string=urdf)
        assert result["success"] is True
        assert result["robot_name"] == "mini"
        assert result["link_count"] == 2
        assert result["total_mass"] == 1.0


class TestEdgeCases:

    def test_no_input(self):
        result = urdf_inspect()
        assert result["success"] is False

    def test_nonexistent_file(self):
        result = urdf_inspect(file_path="/nonexistent.urdf")
        assert result["success"] is False
