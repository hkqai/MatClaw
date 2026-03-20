"""Tests for urdf_validate tool."""

import pytest
from tools.urdf import urdf_validate


class TestValidRobot:
    """A clean URDF should pass all checks."""

    def test_no_errors(self, valid_robot_path):
        result = urdf_validate(file_path=valid_robot_path)
        assert result["success"] is True
        assert result["issues_by_severity"]["error"] == 0

    def test_robot_name(self, valid_robot_path):
        result = urdf_validate(file_path=valid_robot_path)
        assert result["robot_name"] == "valid_robot"


class TestUsdNaming:
    """Detect non-USD-compliant names."""

    def test_bad_names_detected(self, bad_names_path):
        result = urdf_validate(file_path=bad_names_path, categories=["usd_naming"])
        assert result["success"] is True
        assert result["total_issues"] > 0

        names_flagged = {i["element_name"] for i in result["issues"]}
        # Links with bad names
        assert "base-link" in names_flagged
        assert "link.with.dots" in names_flagged
        assert "3rd_link" in names_flagged
        assert "link with spaces" in names_flagged
        # under_score_ok should NOT be flagged
        assert "under_score_ok" not in names_flagged

    def test_bad_joint_names(self, bad_names_path):
        result = urdf_validate(file_path=bad_names_path, categories=["usd_naming"])
        joint_issues = [i for i in result["issues"] if i["element_type"] == "joint"]
        assert len(joint_issues) > 0

    def test_robot_name_flagged(self, bad_names_path):
        result = urdf_validate(file_path=bad_names_path, categories=["usd_naming"])
        robot_issues = [i for i in result["issues"] if i["element_type"] == "robot"]
        assert len(robot_issues) == 1


class TestMaterials:
    """Detect duplicate material definitions."""

    def test_duplicate_detected(self, duplicate_materials_path):
        result = urdf_validate(file_path=duplicate_materials_path, categories=["materials"])
        assert result["success"] is True
        mat_issues = [i for i in result["issues"] if i["category"] == "materials"]
        error_issues = [i for i in mat_issues if i["severity"] == "error"]
        assert len(error_issues) >= 1
        assert any("red" in i["element_name"] for i in error_issues)


class TestJointLimits:
    """Detect joint limit issues."""

    def test_infinite_limits(self, bad_joint_limits_path):
        result = urdf_validate(file_path=bad_joint_limits_path, categories=["joint_limits"])
        assert result["success"] is True
        names = {i["element_name"] for i in result["issues"]}
        assert "joint_inf" in names

    def test_missing_effort_velocity(self, bad_joint_limits_path):
        result = urdf_validate(file_path=bad_joint_limits_path, categories=["joint_limits"])
        effort_issues = [i for i in result["issues"]
                         if "effort" in i["message"] or "velocity" in i["message"]]
        assert len(effort_issues) >= 1

    def test_missing_limit_element(self, bad_joint_limits_path):
        result = urdf_validate(file_path=bad_joint_limits_path, categories=["joint_limits"])
        no_limit = [i for i in result["issues"] if "missing <limit>" in i["message"]]
        assert len(no_limit) >= 1


class TestInertial:
    """Detect missing/bad inertial properties."""

    def test_missing_inertial(self, missing_inertial_path):
        result = urdf_validate(file_path=missing_inertial_path, categories=["inertial"])
        assert result["success"] is True
        errors = [i for i in result["issues"] if i["severity"] == "error"]
        # base_link has geometry but no inertial
        names = {i["element_name"] for i in errors}
        assert "base_link" in names

    def test_zero_mass(self, missing_inertial_path):
        result = urdf_validate(file_path=missing_inertial_path, categories=["inertial"])
        zero_mass = [i for i in result["issues"] if "non-positive mass" in i["message"]]
        assert len(zero_mass) >= 1

    def test_empty_link_info(self, missing_inertial_path):
        result = urdf_validate(file_path=missing_inertial_path,
                               categories=["inertial"], min_severity="info")
        info_issues = [i for i in result["issues"] if i["severity"] == "info"]
        assert any("empty_link" in i["element_name"] for i in info_issues)


class TestCollision:
    """Detect visual without collision."""

    def test_missing_collision(self, missing_collision_path):
        result = urdf_validate(file_path=missing_collision_path, categories=["collision"])
        assert result["success"] is True
        names = {i["element_name"] for i in result["issues"]}
        assert "base_link" in names
        assert "good_link" not in names


class TestMeshReferences:
    """Detect broken mesh paths."""

    def test_broken_refs(self, broken_mesh_refs_path):
        result = urdf_validate(file_path=broken_mesh_refs_path, categories=["mesh_references"])
        assert result["success"] is True
        errors = [i for i in result["issues"] if i["severity"] == "error"]
        assert len(errors) >= 2  # visual + collision

    def test_package_uri_info(self, broken_mesh_refs_path):
        result = urdf_validate(file_path=broken_mesh_refs_path,
                               categories=["mesh_references"], min_severity="info")
        info_issues = [i for i in result["issues"] if i["severity"] == "info"]
        assert any("package://" in i["message"] for i in info_issues)


class TestFiltering:
    """Test category and severity filtering."""

    def test_category_filter(self, kitchen_sink_path):
        result = urdf_validate(file_path=kitchen_sink_path, categories=["usd_naming"])
        cats = {i["category"] for i in result["issues"]}
        assert cats == {"usd_naming"}

    def test_severity_filter(self, kitchen_sink_path):
        result = urdf_validate(file_path=kitchen_sink_path, min_severity="error")
        for issue in result["issues"]:
            assert issue["severity"] == "error"

    def test_invalid_category(self):
        result = urdf_validate(urdf_string="<robot name='r'/>", categories=["bogus"])
        assert result["success"] is False
        assert "bogus" in result["error"]


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_nonexistent_file(self):
        result = urdf_validate(file_path="/nonexistent/robot.urdf")
        assert result["success"] is False

    def test_no_input(self):
        result = urdf_validate()
        assert result["success"] is False

    def test_both_inputs(self):
        result = urdf_validate(file_path="/tmp/a.urdf", urdf_string="<robot/>")
        assert result["success"] is False

    def test_urdf_string(self):
        urdf = '<robot name="test"><link name="base"/></robot>'
        result = urdf_validate(urdf_string=urdf)
        assert result["success"] is True

    def test_not_robot_root(self):
        result = urdf_validate(urdf_string="<sdf/>")
        assert result["success"] is False
