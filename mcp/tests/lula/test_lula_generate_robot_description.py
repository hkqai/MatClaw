"""Tests for lula_generate_robot_description tool."""

import os
import pytest
import yaml

pytest.importorskip("trimesh", reason="trimesh required for lula tools")
pytest.importorskip("scipy", reason="scipy required for lula tools")

from tools.lula import lula_generate_robot_description
from tools.lula._lula_core import (
    _parse_urdf_for_lula,
    _get_controllable_joints,
    _resolve_mesh_path,
    _generate_spheres_for_mesh,
)


# ---------------------------------------------------------------------------
# URDF parsing
# ---------------------------------------------------------------------------

class TestUrdfParsing:

    def test_robot_name(self, simple_arm_path):
        robot = _parse_urdf_for_lula(simple_arm_path)
        assert robot["robot_name"] == "simple_arm"

    def test_links_found(self, simple_arm_path):
        robot = _parse_urdf_for_lula(simple_arm_path)
        assert "base_link" in robot["links"]
        assert "link1" in robot["links"]
        assert "link2" in robot["links"]

    def test_joints_found(self, simple_arm_path):
        robot = _parse_urdf_for_lula(simple_arm_path)
        joints = robot["joints"]
        assert "joint1" in joints
        assert joints["joint1"]["type"] == "revolute"
        assert joints["joint1"]["limit"]["lower"] == pytest.approx(-3.14159, abs=1e-4)
        assert joints["joint1"]["limit"]["velocity"] == pytest.approx(3.0)

    def test_controllable_joints(self, simple_arm_path):
        robot = _parse_urdf_for_lula(simple_arm_path)
        cj = _get_controllable_joints(robot["joints"])
        assert "joint1" in cj
        assert "joint2" in cj
        assert "finger_joint" in cj       # prismatic is controllable
        assert "world_to_base" not in cj  # fixed joint excluded
        assert "joint2_to_tool" not in cj

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            _parse_urdf_for_lula("/nonexistent/robot.urdf")

    def test_wrong_root_raises(self, tmp_path):
        bad = tmp_path / "bad.xml"
        bad.write_text("<sdf/>")
        with pytest.raises(ValueError):
            _parse_urdf_for_lula(str(bad))


# ---------------------------------------------------------------------------
# Mesh path resolution
# ---------------------------------------------------------------------------

class TestMeshPathResolution:

    def test_relative_path(self, tmp_path):
        mesh = tmp_path / "meshes" / "base.stl"
        mesh.parent.mkdir(parents=True)
        mesh.touch()
        resolved = _resolve_mesh_path("meshes/base.stl", str(tmp_path), [])
        assert resolved == str(mesh)

    def test_absolute_path(self, tmp_path):
        mesh = tmp_path / "base.stl"
        mesh.touch()
        resolved = _resolve_mesh_path(str(mesh), str(tmp_path), [])
        assert resolved == str(mesh)

    def test_missing_returns_none(self, tmp_path):
        result = _resolve_mesh_path("does_not_exist.stl", str(tmp_path), [])
        assert result is None

    def test_package_uri_via_search_path(self, tmp_path):
        pkg_dir = tmp_path / "my_robot" / "meshes"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "link1.stl").touch()
        resolved = _resolve_mesh_path(
            "package://my_robot/meshes/link1.stl",
            str(tmp_path),
            [str(tmp_path)],
        )
        assert resolved is not None
        assert resolved.endswith("link1.stl")


# ---------------------------------------------------------------------------
# Sphere generation (synthetic meshes)
# ---------------------------------------------------------------------------

class TestSphereGeneration:

    def _box_mesh(self):
        import trimesh
        return trimesh.creation.box(extents=[0.1, 0.05, 0.2])

    def _cylinder_mesh(self):
        import trimesh
        return trimesh.creation.cylinder(radius=0.03, height=0.15)

    def test_box_generates_spheres(self):
        mesh = self._box_mesh()
        spheres, err = _generate_spheres_for_mesh(mesh, max_spheres=8, voxel_fraction=0.05)
        assert len(spheres) > 0
        assert err is None or isinstance(err, str)

    def test_cylinder_generates_spheres(self):
        mesh = self._cylinder_mesh()
        spheres, err = _generate_spheres_for_mesh(mesh, max_spheres=8, voxel_fraction=0.05)
        assert len(spheres) > 0

    def test_sphere_count_respected(self):
        mesh = self._box_mesh()
        for max_n in [1, 4, 12]:
            spheres, _ = _generate_spheres_for_mesh(mesh, max_spheres=max_n, voxel_fraction=0.05)
            assert len(spheres) <= max_n

    def test_spheres_inside_mesh(self):
        """Sphere centres should lie within (or very close to) the mesh bounds."""
        import numpy as np
        mesh = self._box_mesh()
        spheres, _ = _generate_spheres_for_mesh(mesh, max_spheres=8, voxel_fraction=0.05)
        bb_min = mesh.bounds[0]
        bb_max = mesh.bounds[1]
        for s in spheres:
            c = np.array(s["center"])
            r = s["radius"]
            # Centre + radius should not significantly exceed bounding box
            assert np.all(c >= bb_min - r * 1.1), f"Sphere centre outside bounds: {c}"
            assert np.all(c <= bb_max + r * 1.1), f"Sphere centre outside bounds: {c}"

    def test_sphere_radius_positive(self):
        mesh = self._box_mesh()
        spheres, _ = _generate_spheres_for_mesh(mesh, max_spheres=8, voxel_fraction=0.05)
        for s in spheres:
            assert s["radius"] > 0

    def test_spheres_do_not_overshoot_mesh(self):
        """Every point on each sphere's surface should be inside or near the mesh."""
        import numpy as np
        mesh = self._box_mesh()
        spheres, _ = _generate_spheres_for_mesh(mesh, max_spheres=8, voxel_fraction=0.05)
        # For a box, the half-extents give the exact signed distance boundary.
        # Check that center + radius does not exceed any face of the box.
        half = np.array([0.05, 0.025, 0.1])  # extents / 2
        for s in spheres:
            c = np.array(s["center"])
            r = s["radius"]
            # Signed distance from centre to each face of the box
            face_dists = half - np.abs(c)
            min_face_dist = float(face_dists.min())
            # Sphere radius should not exceed distance to nearest face (+ small tolerance)
            assert r <= min_face_dist + 0.005, (
                f"Sphere overshoots box: r={r:.4f}, min_face_dist={min_face_dist:.4f}"
            )

    def test_surface_coverage(self):
        """Sphere boundaries should approximate the mesh surface well.

        For collision checking, what matters is that every surface point
        is close to some sphere boundary.  We measure the *gap* from each
        surface sample to the nearest sphere boundary:
            gap = ||p - c|| - r
        A surface point is "covered" if gap <= tolerance.
        """
        import numpy as np
        import trimesh
        mesh = self._box_mesh()
        spheres, _ = _generate_spheres_for_mesh(mesh, max_spheres=12, voxel_fraction=0.04)
        surface_pts, _ = trimesh.sample.sample_surface(mesh, 2000)
        max_extent = float(mesh.bounding_box.extents.max())
        tolerance = max_extent * 0.10  # 10 % of link size
        covered = np.zeros(len(surface_pts), dtype=bool)
        for s in spheres:
            c = np.array(s["center"])
            r = s["radius"]
            gap = np.linalg.norm(surface_pts - c, axis=1) - r
            covered |= gap <= tolerance
        coverage_ratio = covered.sum() / len(covered)
        assert coverage_ratio > 0.70, (
            f"Surface coverage too low: {coverage_ratio:.1%} with {len(spheres)} spheres"
        )

    def test_elongated_shape_coverage(self):
        """A thin elongated box should get spheres spread along its length."""
        import trimesh
        mesh = trimesh.creation.box(extents=[0.01, 0.01, 0.3])
        spheres, _ = _generate_spheres_for_mesh(mesh, max_spheres=10, voxel_fraction=0.04)
        assert len(spheres) >= 2, "Elongated shape should need multiple spheres"
        # Check that spheres span a meaningful fraction of the z-extent
        z_coords = [s["center"][2] for s in spheres]
        z_span = max(z_coords) - min(z_coords)
        assert z_span > 0.1, (
            f"Spheres not spread along length: z_span={z_span:.3f} for 0.3m box"
        )


# ---------------------------------------------------------------------------
# Full tool: simple fixture
# ---------------------------------------------------------------------------

class TestSimpleArm:

    def test_success(self, simple_arm_path, tmp_path):
        out = str(tmp_path / "simple_arm_lula.yaml")
        result = lula_generate_robot_description(
            urdf_path=simple_arm_path,
            output_path=out,
        )
        assert result["success"] is True
        assert result["robot_name"] == "simple_arm"
        assert os.path.exists(out)

    def test_cspace_contains_arm_joints(self, simple_arm_path, tmp_path):
        out = str(tmp_path / "out.yaml")
        result = lula_generate_robot_description(urdf_path=simple_arm_path, output_path=out)
        assert result["success"]
        assert "joint1" in result["cspace"]
        assert "joint2" in result["cspace"]

    def test_fixed_joints_excluded_from_cspace(self, simple_arm_path, tmp_path):
        out = str(tmp_path / "out.yaml")
        result = lula_generate_robot_description(urdf_path=simple_arm_path, output_path=out)
        assert "world_to_base" not in result["cspace"]
        assert "joint2_to_tool" not in result["cspace"]

    def test_explicit_controlled_joints(self, simple_arm_path, tmp_path):
        out = str(tmp_path / "out.yaml")
        result = lula_generate_robot_description(
            urdf_path=simple_arm_path,
            output_path=out,
            controlled_joint_names=["joint1", "joint2"],
        )
        assert result["success"]
        assert result["cspace"] == ["joint1", "joint2"]

    def test_output_yaml_valid(self, simple_arm_path, tmp_path):
        out = str(tmp_path / "out.yaml")
        lula_generate_robot_description(urdf_path=simple_arm_path, output_path=out)
        with open(out) as f:
            data = yaml.safe_load(f)
        assert data["api_version"] == 1.0
        assert isinstance(data["cspace"], list)
        assert isinstance(data["default_q"], list)
        assert len(data["default_q"]) == len(data["cspace"])
        assert isinstance(data["acceleration_limits"], list)
        assert isinstance(data["jerk_limits"], list)

    def test_collision_spheres_in_yaml(self, simple_arm_path, tmp_path):
        out = str(tmp_path / "out.yaml")
        lula_generate_robot_description(urdf_path=simple_arm_path, output_path=out)
        with open(out) as f:
            data = yaml.safe_load(f)
        assert "collision_spheres" in data
        all_links = {}
        for item in data["collision_spheres"]:
            all_links.update(item)
        # links with box/cylinder geometry should have spheres
        assert len(all_links) > 0
        for link_name, spheres in all_links.items():
            for s in spheres:
                assert "center" in s
                assert "radius" in s
                assert len(s["center"]) == 3

    def test_skip_sphere_links(self, simple_arm_path, tmp_path):
        out = str(tmp_path / "out.yaml")
        result = lula_generate_robot_description(
            urdf_path=simple_arm_path,
            output_path=out,
            skip_sphere_links=["base_link", "link1"],
        )
        assert result["success"]
        with open(out) as f:
            data = yaml.safe_load(f)
        if "collision_spheres" in data:
            all_links = {}
            for item in data["collision_spheres"]:
                all_links.update(item)
            assert "base_link" not in all_links
            assert "link1" not in all_links

    def test_cspace_to_urdf_rules_for_excluded_joints(self, simple_arm_path, tmp_path):
        out = str(tmp_path / "out.yaml")
        lula_generate_robot_description(
            urdf_path=simple_arm_path,
            output_path=out,
            controlled_joint_names=["joint1", "joint2"],
        )
        with open(out) as f:
            data = yaml.safe_load(f)
        rules = {r["name"]: r for r in data.get("cspace_to_urdf_rules", [])}
        # finger_joint is prismatic but not in cspace → should be in rules
        assert "finger_joint" in rules
        assert rules["finger_joint"]["rule"] == "fixed"

    def test_default_output_path(self, simple_arm_path, tmp_path):
        """When output_path is None, file lands next to the URDF."""
        import shutil
        urdf_copy = str(tmp_path / "simple_arm.urdf")
        shutil.copy(simple_arm_path, urdf_copy)
        result = lula_generate_robot_description(urdf_path=urdf_copy)
        assert result["success"]
        expected = str(tmp_path / "simple_arm_lula_description.yaml")
        assert result["output_path"] == expected
        assert os.path.exists(expected)

    def test_missing_urdf(self):
        result = lula_generate_robot_description(urdf_path="/nonexistent/robot.urdf")
        assert result["success"] is False
        assert "error" in result


# ---------------------------------------------------------------------------
# Full tool: real robots (skipped if files absent)
# ---------------------------------------------------------------------------

class TestUr5e:

    @pytest.mark.integration
    def test_ur5e_success(self, ur5e_path, tmp_path):
        out = str(tmp_path / "ur5e_lula.yaml")
        result = lula_generate_robot_description(urdf_path=ur5e_path, output_path=out)
        assert result["success"] is True
        assert result["robot_name"] == "ur5e"

    @pytest.mark.integration
    def test_ur5e_cspace(self, ur5e_path, tmp_path):
        out = str(tmp_path / "ur5e_lula.yaml")
        result = lula_generate_robot_description(urdf_path=ur5e_path, output_path=out)
        # UR5e has 6 revolute arm joints
        arm_joints = [j for j in result["cspace"] if "joint" in j.lower()]
        assert len(arm_joints) >= 6

    @pytest.mark.integration
    def test_ur5e_has_spheres(self, ur5e_path, tmp_path):
        out = str(tmp_path / "ur5e_lula.yaml")
        result = lula_generate_robot_description(urdf_path=ur5e_path, output_path=out)
        assert result["num_links_with_spheres"] > 0
        assert result["total_spheres"] > 0

    @pytest.mark.integration
    def test_ur5e_yaml_parseable(self, ur5e_path, tmp_path):
        out = str(tmp_path / "ur5e_lula.yaml")
        lula_generate_robot_description(urdf_path=ur5e_path, output_path=out)
        with open(out) as f:
            data = yaml.safe_load(f)
        assert data["api_version"] == 1.0
        assert len(data["cspace"]) == len(data["default_q"])


class TestPiper:

    @pytest.mark.integration
    def test_piper_success(self, piper_path, tmp_path):
        out = str(tmp_path / "piper_lula.yaml")
        result = lula_generate_robot_description(
            urdf_path=piper_path,
            output_path=out,
            controlled_joint_names=["joint1", "joint2", "joint3",
                                    "joint4", "joint5", "joint6"],
        )
        assert result["success"] is True, result.get("error")
        assert result["cspace"] == ["joint1", "joint2", "joint3",
                                    "joint4", "joint5", "joint6"]

    @pytest.mark.integration
    def test_piper_has_spheres(self, piper_path, tmp_path):
        out = str(tmp_path / "piper_lula.yaml")
        result = lula_generate_robot_description(
            urdf_path=piper_path,
            output_path=out,
            controlled_joint_names=["joint1", "joint2", "joint3",
                                    "joint4", "joint5", "joint6"],
        )
        assert result["num_links_with_spheres"] > 0

    @pytest.mark.integration
    def test_piper_gripper_rules(self, piper_path, tmp_path):
        out = str(tmp_path / "piper_lula.yaml")
        lula_generate_robot_description(
            urdf_path=piper_path,
            output_path=out,
            controlled_joint_names=["joint1", "joint2", "joint3",
                                    "joint4", "joint5", "joint6"],
        )
        with open(out) as f:
            data = yaml.safe_load(f)
        rules = {r["name"]: r for r in data.get("cspace_to_urdf_rules", [])}
        # joint7 and joint8 are gripper joints not in cspace
        assert "joint7" in rules
        assert "joint8" in rules
