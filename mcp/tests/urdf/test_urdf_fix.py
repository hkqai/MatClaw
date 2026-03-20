"""Tests for urdf_fix tool."""

import os
import tempfile
import xml.etree.ElementTree as ET

import pytest
from tools.urdf import urdf_fix, urdf_validate


class TestUsdNamingFix:
    """Fix non-USD-compliant names."""

    def test_renames_links(self, bad_names_path):
        result = urdf_fix(file_path=bad_names_path, output_path="/tmp/test_fix_names.urdf",
                          fix_categories=["usd_naming"])
        assert result["success"] is True
        assert result["total_fixes"] > 0
        assert "base-link" in result["name_mapping"]

    def test_updates_references(self, bad_names_path):
        result = urdf_fix(file_path=bad_names_path, output_path="/tmp/test_fix_refs.urdf",
                          fix_categories=["usd_naming"])
        # Parse fixed file and verify parent/child references match renamed links
        tree = ET.parse(result["output_path"])
        root = tree.getroot()

        link_names = {l.get("name") for l in root.iter("link")}
        for joint in root.iter("joint"):
            parent = joint.find("parent")
            child = joint.find("child")
            if parent is not None:
                assert parent.get("link") in link_names, \
                    f"Joint {joint.get('name')} parent '{parent.get('link')}' not in links"
            if child is not None:
                assert child.get("link") in link_names, \
                    f"Joint {joint.get('name')} child '{child.get('link')}' not in links"

    def test_leading_digit_prefix(self, bad_names_path):
        result = urdf_fix(file_path=bad_names_path, output_path="/tmp/test_fix_digit.urdf",
                          fix_categories=["usd_naming"])
        # "3rd_link" should become "n_3rd_link"
        assert result["name_mapping"].get("3rd_link", "").startswith("n_")


class TestMaterialFix:
    """Deduplicate materials."""

    def test_dedup_materials(self, duplicate_materials_path):
        result = urdf_fix(file_path=duplicate_materials_path,
                          output_path="/tmp/test_fix_mat.urdf",
                          fix_categories=["materials"])
        assert result["success"] is True
        mat_fixes = [f for f in result["fixes"] if f["category"] == "materials"]
        assert len(mat_fixes) >= 1


class TestJointLimitsFix:
    """Fix infinite limits and missing effort/velocity."""

    def test_clamp_inf(self, bad_joint_limits_path):
        result = urdf_fix(file_path=bad_joint_limits_path,
                          output_path="/tmp/test_fix_joints.urdf",
                          fix_categories=["joint_limits"])
        assert result["success"] is True

        # Parse and verify no infinite limits remain
        tree = ET.parse(result["output_path"])
        for joint in tree.getroot().iter("joint"):
            limit = joint.find("limit")
            if limit is not None:
                for attr in ("lower", "upper", "effort", "velocity"):
                    val = limit.get(attr)
                    if val is not None:
                        assert val not in ("inf", "-inf", "INF", "-INF"), \
                            f"Joint {joint.get('name')} still has {attr}={val}"

    def test_adds_missing_limit(self, bad_joint_limits_path):
        result = urdf_fix(file_path=bad_joint_limits_path,
                          output_path="/tmp/test_fix_nolimit.urdf",
                          fix_categories=["joint_limits"])
        fix_msgs = [f["message"] for f in result["fixes"]]
        assert any("joint_no_limit" in msg for msg in fix_msgs)

    def test_adds_effort_velocity(self, bad_joint_limits_path):
        result = urdf_fix(file_path=bad_joint_limits_path,
                          output_path="/tmp/test_fix_ev.urdf",
                          fix_categories=["joint_limits"])
        fix_msgs = [f["message"] for f in result["fixes"]]
        assert any("effort" in msg for msg in fix_msgs)
        assert any("velocity" in msg for msg in fix_msgs)


class TestInertialFix:
    """Fix missing inertial properties."""

    def test_adds_inertial(self, missing_inertial_path):
        result = urdf_fix(file_path=missing_inertial_path,
                          output_path="/tmp/test_fix_inertial.urdf",
                          fix_categories=["inertial"])
        assert result["success"] is True
        fix_msgs = [f["message"] for f in result["fixes"]]
        assert any("base_link" in msg for msg in fix_msgs)

    def test_fixes_zero_mass(self, missing_inertial_path):
        result = urdf_fix(file_path=missing_inertial_path,
                          output_path="/tmp/test_fix_mass.urdf",
                          fix_categories=["inertial"],
                          default_mass=0.5)
        fix_msgs = [f["message"] for f in result["fixes"]]
        assert any("non-positive mass" in msg or "zero" in msg.lower() for msg in fix_msgs)

    def test_custom_defaults(self, missing_inertial_path):
        result = urdf_fix(file_path=missing_inertial_path,
                          output_path="/tmp/test_fix_custom.urdf",
                          fix_categories=["inertial"],
                          default_mass=2.0,
                          default_inertia=0.01)
        tree = ET.parse(result["output_path"])
        # base_link should now have inertial with our custom defaults
        for link in tree.getroot().iter("link"):
            if link.get("name") == "base_link":
                mass = link.find("inertial/mass")
                assert mass is not None
                assert float(mass.get("value")) == 2.0


class TestRoundTrip:
    """Fix then re-validate should yield zero errors for fixed categories."""

    def test_fix_then_validate_naming(self, bad_names_path):
        fix_result = urdf_fix(file_path=bad_names_path,
                              output_path="/tmp/test_rt_names.urdf",
                              fix_categories=["usd_naming"])
        val_result = urdf_validate(file_path=fix_result["output_path"],
                                   categories=["usd_naming"],
                                   min_severity="error")
        assert val_result["issues_by_severity"]["error"] == 0

    def test_fix_then_validate_joints(self, bad_joint_limits_path):
        fix_result = urdf_fix(file_path=bad_joint_limits_path,
                              output_path="/tmp/test_rt_joints.urdf",
                              fix_categories=["joint_limits"])
        val_result = urdf_validate(file_path=fix_result["output_path"],
                                   categories=["joint_limits"],
                                   min_severity="error")
        assert val_result["issues_by_severity"]["error"] == 0

    def test_fix_then_validate_inertial(self, missing_inertial_path):
        fix_result = urdf_fix(file_path=missing_inertial_path,
                              output_path="/tmp/test_rt_inertial.urdf",
                              fix_categories=["inertial"])
        val_result = urdf_validate(file_path=fix_result["output_path"],
                                   categories=["inertial"],
                                   min_severity="error")
        assert val_result["issues_by_severity"]["error"] == 0

    def test_kitchen_sink_round_trip(self, kitchen_sink_path):
        fix_result = urdf_fix(file_path=kitchen_sink_path,
                              output_path="/tmp/test_rt_kitchen.urdf")
        assert fix_result["success"] is True
        assert fix_result["total_fixes"] > 0

        # Re-validate: fixable categories should have zero errors
        val_result = urdf_validate(
            file_path=fix_result["output_path"],
            categories=["usd_naming", "joint_limits", "inertial", "materials"],
            min_severity="error",
        )
        assert val_result["issues_by_severity"]["error"] == 0


class TestNonDestructive:
    """Original file must not be modified."""

    def test_original_unchanged(self, bad_names_path):
        with open(bad_names_path, "r") as f:
            original = f.read()

        urdf_fix(file_path=bad_names_path, output_path="/tmp/test_nd.urdf")

        with open(bad_names_path, "r") as f:
            after = f.read()

        assert original == after

    def test_default_output_path(self, bad_names_path):
        result = urdf_fix(file_path=bad_names_path)
        assert result["success"] is True
        assert "_fixed" in result["output_path"]
        # Clean up
        if os.path.exists(result["output_path"]):
            os.remove(result["output_path"])


class TestUrdfString:
    """Test with urdf_string input."""

    def test_fix_string(self):
        urdf = '''<robot name="test-bot">
            <link name="base-link">
                <visual><geometry><box size="0.1 0.1 0.1"/></geometry></visual>
                <collision><geometry><box size="0.1 0.1 0.1"/></geometry></collision>
            </link>
        </robot>'''
        result = urdf_fix(urdf_string=urdf)
        assert result["success"] is True
        assert "fixed_urdf" in result
        assert "test_bot" in result["fixed_urdf"] or "test-bot" not in result["fixed_urdf"]


class TestEdgeCases:

    def test_invalid_category(self):
        result = urdf_fix(urdf_string="<robot name='r'/>", fix_categories=["bogus"])
        assert result["success"] is False

    def test_no_input(self):
        result = urdf_fix()
        assert result["success"] is False
