"""
Core logic for Lula robot description generation.

Handles URDF parsing, mesh loading/repair, collision sphere generation
via voxelization + distance-transform sphere packing, and YAML output.

Internal module shared by lula_generate_robot_description tool.
"""

import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import yaml


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

class _FlowList(list):
    """A list that serialises as a YAML flow sequence (inline)."""


class _LulaDumper(yaml.Dumper):
    """Custom YAML dumper that renders _FlowList instances inline."""


def _flow_representer(dumper: yaml.Dumper, data: _FlowList):
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)


_LulaDumper.add_representer(_FlowList, _flow_representer)


# ---------------------------------------------------------------------------
# URDF parsing
# ---------------------------------------------------------------------------

def _parse_vec(s: str) -> List[float]:
    return [float(v) for v in s.strip().split()]


def _parse_urdf_for_lula(urdf_path: str) -> Dict[str, Any]:
    """
    Parse a URDF and return structured robot data needed for Lula generation.

    Returns dict with keys: robot_name, urdf_dir, links, joints.
    """
    path = Path(urdf_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"URDF file not found: {urdf_path}")

    tree = ET.parse(str(path))
    root = tree.getroot()
    if root.tag != "robot":
        raise ValueError(f"Expected <robot> root, got <{root.tag}>")

    robot_name = root.get("name", "robot")
    urdf_dir = str(path.parent)

    # --- Links ---
    links: Dict[str, Dict] = {}
    for link_elem in root.findall("link"):
        name = link_elem.get("name", "")
        collision_geoms = []
        for coll in link_elem.findall("collision"):
            geom = coll.find("geometry")
            if geom is not None:
                origin = coll.find("origin")
                collision_geoms.append((geom, origin))
        visual_geoms = []
        for vis in link_elem.findall("visual"):
            geom = vis.find("geometry")
            if geom is not None:
                origin = vis.find("origin")
                visual_geoms.append((geom, origin))
        links[name] = {
            "collision_geoms": collision_geoms,
            "visual_geoms": visual_geoms,
        }

    # --- Joints ---
    joints: Dict[str, Dict] = {}
    for joint_elem in root.findall("joint"):
        name = joint_elem.get("name", "")
        jtype = joint_elem.get("type", "fixed")

        parent_e = joint_elem.find("parent")
        child_e = joint_elem.find("child")
        parent = parent_e.get("link", "") if parent_e is not None else ""
        child = child_e.get("link", "") if child_e is not None else ""

        limit_e = joint_elem.find("limit")
        limit = None
        if limit_e is not None:
            limit = {
                "lower": float(limit_e.get("lower", "0")),
                "upper": float(limit_e.get("upper", "0")),
                "effort": float(limit_e.get("effort", "0")),
                "velocity": float(limit_e.get("velocity", "0")),
            }

        axis_e = joint_elem.find("axis")
        axis = [0.0, 0.0, 1.0]
        if axis_e is not None:
            axis = _parse_vec(axis_e.get("xyz", "0 0 1"))

        joints[name] = {
            "type": jtype,
            "parent": parent,
            "child": child,
            "limit": limit,
            "axis": axis,
        }

    return {
        "robot_name": robot_name,
        "urdf_dir": urdf_dir,
        "links": links,
        "joints": joints,
    }


def _get_controllable_joints(joints: Dict[str, Dict]) -> List[str]:
    """Return controllable joint names in definition order."""
    movable = {"revolute", "prismatic", "continuous"}
    return [n for n, j in joints.items() if j["type"] in movable]


# ---------------------------------------------------------------------------
# URDF origin transform
# ---------------------------------------------------------------------------

def _origin_to_transform(origin_elem: Optional[ET.Element]) -> np.ndarray:
    """Build a 4x4 homogeneous transform from a URDF <origin> element.

    URDF convention: R = Rz(yaw) @ Ry(pitch) @ Rx(roll), then translate.
    Returns the identity matrix when *origin_elem* is None.
    """
    T = np.eye(4)
    if origin_elem is None:
        return T

    xyz_str = origin_elem.get("xyz", "0 0 0")
    rpy_str = origin_elem.get("rpy", "0 0 0")
    xyz = _parse_vec(xyz_str)
    roll, pitch, yaw = _parse_vec(rpy_str)

    cr, sr = np.cos(roll), np.sin(roll)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cy, sy = np.cos(yaw), np.sin(yaw)

    # Rz(yaw) @ Ry(pitch) @ Rx(roll)
    T[0, 0] = cy * cp
    T[0, 1] = cy * sp * sr - sy * cr
    T[0, 2] = cy * sp * cr + sy * sr
    T[1, 0] = sy * cp
    T[1, 1] = sy * sp * sr + cy * cr
    T[1, 2] = sy * sp * cr - cy * sr
    T[2, 0] = -sp
    T[2, 1] = cp * sr
    T[2, 2] = cp * cr

    T[0, 3] = xyz[0]
    T[1, 3] = xyz[1]
    T[2, 3] = xyz[2]
    return T


# ---------------------------------------------------------------------------
# Mesh path resolution
# ---------------------------------------------------------------------------

def _resolve_mesh_path(
    filename: str,
    urdf_dir: str,
    mesh_search_paths: List[str],
) -> Optional[str]:
    """Resolve a URDF mesh filename to an absolute path."""
    if filename.startswith("package://"):
        pkg_rel = filename[len("package://"):]  # e.g. "piper_description/meshes/base.STL"
        parts = pkg_rel.split("/", 1)
        if len(parts) != 2:
            return None
        pkg_name, rel = parts

        # 1. Try explicit search paths (workspace-root/pkg_name/rel or workspace-root/rel)
        for search_root in mesh_search_paths:
            for candidate in [
                os.path.join(search_root, pkg_name, rel),
                os.path.join(search_root, rel),
            ]:
                if os.path.exists(candidate):
                    return candidate

        # 2. Walk up from urdf_dir looking for a directory named pkg_name.
        #    Common pattern: URDF is inside the package (e.g. pkg_name/urdf/robot.urdf).
        cur = urdf_dir
        for _ in range(6):  # limit search depth
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            # If the current dir is named pkg_name, meshes are siblings
            if os.path.basename(cur) == pkg_name:
                candidate = os.path.normpath(os.path.join(cur, rel))
                if os.path.exists(candidate):
                    return candidate
            # Also try parent/pkg_name/rel (workspace-root style)
            candidate = os.path.normpath(os.path.join(cur, pkg_name, rel))
            if os.path.exists(candidate):
                return candidate
            cur = parent

        return None

    if os.path.isabs(filename):
        return filename if os.path.exists(filename) else None

    # Relative path
    for base in [urdf_dir] + mesh_search_paths:
        candidate = os.path.join(base, filename)
        if os.path.exists(candidate):
            return candidate

    return None


# ---------------------------------------------------------------------------
# Geometry loading (mesh files + URDF primitives)
# ---------------------------------------------------------------------------

def _load_geometry_as_mesh(
    geom_elem: ET.Element,
    urdf_dir: str,
    mesh_search_paths: List[str],
) -> Tuple[Optional[Any], Optional[str]]:
    """
    Load a URDF <geometry> element as a trimesh object.

    Supports:
        <mesh filename="..."/>
        <box size="x y z"/>
        <cylinder radius="r" length="l"/>
        <sphere radius="r"/>

    Returns (mesh, warning) where warning may be None.
    """
    try:
        import trimesh
    except ImportError:
        return None, "trimesh not installed: pip install trimesh"

    mesh_elem = geom_elem.find("mesh")
    if mesh_elem is not None:
        filename = mesh_elem.get("filename", "")
        if not filename:
            return None, "Empty mesh filename"
        resolved = _resolve_mesh_path(filename, urdf_dir, mesh_search_paths)
        if resolved is None:
            return None, f"Mesh file not found: {filename}"
        try:
            loaded = trimesh.load(resolved, force="mesh")
        except Exception as e:
            return None, f"Failed to load {filename}: {e}"
        if isinstance(loaded, trimesh.Scene):
            geoms = list(loaded.geometry.values())
            if not geoms:
                return None, f"Empty scene in {filename}"
            loaded = trimesh.util.concatenate(geoms)
        if not isinstance(loaded, trimesh.Trimesh):
            return None, f"Unexpected type from {filename}: {type(loaded)}"
        return loaded, None

    box_elem = geom_elem.find("box")
    if box_elem is not None:
        size_str = box_elem.get("size", "0.1 0.1 0.1")
        size = np.array(_parse_vec(size_str))
        return trimesh.creation.box(extents=size), None

    cyl_elem = geom_elem.find("cylinder")
    if cyl_elem is not None:
        r = float(cyl_elem.get("radius", "0.05"))
        l = float(cyl_elem.get("length", "0.1"))
        return trimesh.creation.cylinder(radius=r, height=l), None

    sph_elem = geom_elem.find("sphere")
    if sph_elem is not None:
        r = float(sph_elem.get("radius", "0.05"))
        return trimesh.creation.icosphere(radius=r), None

    return None, "Unsupported or missing geometry element"


# ---------------------------------------------------------------------------
# Collision sphere generation via coverage-axis weighted set cover
# ---------------------------------------------------------------------------

def _repair_mesh(mesh: Any) -> Tuple[Any, str]:
    """Attempt to make a mesh watertight. Returns (mesh, note)."""
    if mesh.is_watertight:
        return mesh, ""

    # Try pymeshfix first (best quality)
    try:
        import pymeshfix
        fix = pymeshfix.MeshFix(
            mesh.vertices.astype(np.float64),
            mesh.faces.astype(np.int32),
        )
        fix.repair(verbose=False)
        import trimesh
        repaired = trimesh.Trimesh(vertices=fix.v, faces=fix.f, process=False)
        if repaired.is_watertight:
            return repaired, "repaired with pymeshfix"
    except ImportError:
        pass
    except Exception:
        pass

    # Fall back to trimesh built-ins
    import trimesh
    repaired = mesh.copy()
    trimesh.repair.fix_normals(repaired)
    trimesh.repair.fill_holes(repaired)
    note = "repaired with trimesh"
    return repaired, note


def _surface_points(mesh: Any, count: int) -> np.ndarray:
    """
    Sample *count* points on the mesh surface.

    Uses ``trimesh.sample.sample_surface`` when available, otherwise falls
    back to the raw vertex array.  Returns an (N, 3) float64 array.
    """
    try:
        pts, _ = mesh.sample(count)
        return np.asarray(pts, dtype=float)
    except Exception:
        pass
    try:
        import trimesh
        pts, _ = trimesh.sample.sample_surface(mesh, count)
        return np.asarray(pts, dtype=float)
    except Exception:
        return np.asarray(mesh.vertices, dtype=float)


def _generate_spheres_for_mesh(
    mesh: Any,
    max_spheres: int = 16,
    voxel_fraction: float = 0.04,
    max_voxels_per_dim: int = 80,
) -> Tuple[List[Dict], Optional[str]]:
    """
    Generate collision spheres using coverage-axis weighted set cover.

    Algorithm:
      1. Repair mesh to watertight.
      2. Sample a dense point cloud on the mesh surface.
      3. Voxelise interior → candidate sphere centres.
      4. For each candidate compute two radii:
         a) *DT radius* — from the distance transform (approximate, may
            slightly overshoot the true surface due to voxel quantisation).
         b) *exact radius* — distance to the nearest surface sample
            (guaranteed inscribed).
         Use the DT radius for coverage computation (it naturally reaches
         the surface, giving meaningful coverage sets) and clamp the final
         output radius to ``min(dt_radius, exact_radius)`` so it never
         exceeds the true inscribed limit.
      5. Greedy weighted set cover: repeatedly pick the candidate whose
         sphere covers the most *uncovered* surface samples.

    Returns (sphere_list, warning_or_None).
    """
    try:
        from scipy.ndimage import distance_transform_edt
        from scipy.spatial import cKDTree
    except ImportError:
        return [], "scipy not installed: pip install scipy"

    extents = mesh.bounding_box.extents
    max_extent = float(extents.max())
    if max_extent < 1e-7:
        return [], "Mesh has negligible size"

    mesh, repair_note = _repair_mesh(mesh)

    # -- Step 1: dense surface sampling --------------------------------------
    n_surface = max(5000, max_spheres * 200)
    surface_pts = _surface_points(mesh, n_surface)
    if len(surface_pts) == 0:
        return [], "Failed to sample mesh surface"
    surf_tree = cKDTree(surface_pts)

    # -- Step 2: candidate generation via voxelisation -----------------------
    raw_pitch = max_extent * voxel_fraction
    capped_pitch = max_extent / max_voxels_per_dim
    pitch = max(raw_pitch, capped_pitch, 1e-5)

    try:
        vox = mesh.voxelized(pitch=pitch).fill()
    except Exception as e:
        return [], f"Voxelisation failed: {e}"

    matrix = np.asarray(vox.matrix, dtype=bool)
    if not matrix.any():
        return [], "Voxelisation produced empty interior"

    # Padded distance transform: each interior voxel → distance to nearest
    # background voxel (in metres), corrected by half a voxel pitch.
    padded = np.pad(matrix, pad_width=1, mode="constant", constant_values=False)
    dt_padded = distance_transform_edt(padded) * pitch
    dt = dt_padded[1:-1, 1:-1, 1:-1] - 0.5 * pitch
    dt = np.maximum(dt, 0.0)

    interior_mask = dt > 0.0
    indices = np.argwhere(interior_mask)  # (N, 3)
    if len(indices) == 0:
        return [], "No interior voxels found"

    origin = np.asarray(vox.transform[:3, 3], dtype=float)
    centers = origin + indices.astype(float) * pitch

    # DT-based radii (approximate, for coverage computation).
    dt_radii = dt[interior_mask].astype(float)

    # Exact radii = distance to nearest surface sample (for clamping).
    exact_radii, _ = surf_tree.query(centers)
    exact_radii = exact_radii.astype(float)

    # Discard candidates with negligible radius
    min_radius = max_extent * 0.005
    keep = exact_radii > min_radius
    centers = centers[keep]
    dt_radii = dt_radii[keep]
    exact_radii = exact_radii[keep]
    if len(centers) == 0:
        return [], "No interior candidates with meaningful radius"

    # -- Step 3: build coverage sets using DT radii --------------------------
    # DT radii naturally reach the mesh surface (they approximate the
    # inscribed radius but include voxel-quantisation overshoot), giving
    # meaningful coverage sets for the set-cover selection.
    coverage: List[np.ndarray] = []
    for i in range(len(centers)):
        idxs = surf_tree.query_ball_point(centers[i], dt_radii[i])
        coverage.append(np.asarray(idxs, dtype=np.intp))

    # -- Step 4: greedy weighted set cover -----------------------------------
    uncovered = np.ones(len(surface_pts), dtype=bool)
    selected_indices: List[int] = []
    cov_counts = np.array([len(c) for c in coverage], dtype=np.intp)

    for _ in range(max_spheres):
        if not uncovered.any():
            break

        best_i = -1
        best_count = 0
        for i in range(len(centers)):
            if cov_counts[i] == 0:
                continue
            count = int(uncovered[coverage[i]].sum()) if len(coverage[i]) > 0 else 0
            if count > best_count:
                best_count = count
                best_i = i
        if best_count == 0:
            break

        selected_indices.append(best_i)
        uncovered[coverage[best_i]] = False
        cov_counts[best_i] = 0

    if not selected_indices:
        return [], "Set cover found no useful spheres"

    # -- Step 5: final radii — clamp to exact inscribed distance -------------
    sel_centers = centers[selected_indices]
    sel_dt = dt_radii[selected_indices]
    sel_exact = exact_radii[selected_indices]
    # Use the smaller of DT and exact to prevent overshoot, but never shrink
    # below zero.
    sel_radii = np.minimum(sel_dt, sel_exact)
    sel_radii = np.maximum(sel_radii, 0.0)

    # -- Build output --------------------------------------------------------
    spheres: List[Dict] = []
    for c, r in zip(sel_centers, sel_radii):
        spheres.append({
            "center": _FlowList([round(float(v), 5) for v in c]),
            "radius": round(float(r), 5),
        })

    warning = repair_note if repair_note else None
    return spheres, warning


# ---------------------------------------------------------------------------
# Main generation function
# ---------------------------------------------------------------------------

def generate_lula_robot_description(
    urdf_path: str,
    output_path: Optional[str] = None,
    mesh_search_paths: Optional[List[str]] = None,
    controlled_joint_names: Optional[List[str]] = None,
    max_spheres_per_link: int = 16,
    voxel_fraction: float = 0.04,
    skip_sphere_links: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generate a Lula robot description YAML from a URDF file.

    Returns result dict with success, output_path, warnings, cspace, etc.
    """
    urdf_path = str(Path(urdf_path).resolve())

    try:
        robot = _parse_urdf_for_lula(urdf_path)
    except (FileNotFoundError, ValueError) as e:
        return {"success": False, "error": str(e)}

    urdf_dir = robot["urdf_dir"]
    links = robot["links"]
    joints = robot["joints"]

    search_paths = [urdf_dir] + (mesh_search_paths or [])
    skip_sphere = set(skip_sphere_links or [])
    warnings: List[str] = []

    # --- cspace ---
    all_controllable = _get_controllable_joints(joints)
    if controlled_joint_names is not None:
        cspace = controlled_joint_names
        for j in cspace:
            if j not in joints:
                warnings.append(f"Specified joint '{j}' not found in URDF")
    else:
        cspace = all_controllable

    # --- default_q ---
    default_q: List[float] = []
    for j in cspace:
        jd = joints.get(j, {})
        lim = jd.get("limit")
        if lim:
            lo, hi = lim["lower"], lim["upper"]
            default_q.append(0.0 if lo <= 0.0 <= hi else round((lo + hi) / 2, 4))
        else:
            default_q.append(0.0)

    # --- acceleration / jerk limits (heuristic: 5× and 2500× velocity limit) ---
    accel_limits: List[float] = []
    jerk_limits: List[float] = []
    for j in cspace:
        lim = joints.get(j, {}).get("limit")
        vel = lim["velocity"] if lim and lim.get("velocity", 0) > 0 else 2.0
        accel_limits.append(round(vel * 5.0, 2))
        jerk_limits.append(round(vel * 2500.0, 1))

    # --- cspace_to_urdf_rules for controllable joints excluded from cspace ---
    cspace_set = set(cspace)
    cspace_to_urdf_rules: List[Dict] = []
    for jname, jd in joints.items():
        if jname in cspace_set or jd["type"] == "fixed":
            continue
        lim = jd.get("limit")
        val = 0.0
        if lim:
            lo, hi = lim["lower"], lim["upper"]
            val = 0.0 if lo <= 0.0 <= hi else round(lo, 4)
        cspace_to_urdf_rules.append({"name": jname, "rule": "fixed", "value": val})

    # --- collision spheres ---
    collision_spheres: List[Dict] = []
    for link_name, link_data in links.items():
        if link_name in skip_sphere:
            continue

        # Prefer collision geometry; fall back to visual
        geoms_with_origins = link_data["collision_geoms"] or link_data["visual_geoms"]
        if not geoms_with_origins:
            continue

        # Load and concatenate all collision geometries for this link,
        # transforming each from geometry frame to link frame via <origin>.
        meshes = []
        for geom_elem, origin_elem in geoms_with_origins:
            m, warn = _load_geometry_as_mesh(geom_elem, urdf_dir, search_paths)
            if m is not None:
                T = _origin_to_transform(origin_elem)
                if not np.allclose(T, np.eye(4)):
                    m.apply_transform(T)
                meshes.append(m)
            elif warn:
                warnings.append(f"Link '{link_name}': {warn}")

        if not meshes:
            continue

        if len(meshes) == 1:
            combined = meshes[0]
        else:
            try:
                import trimesh
                combined = trimesh.util.concatenate(meshes)
            except Exception as e:
                warnings.append(f"Link '{link_name}': mesh concatenation failed: {e}")
                combined = meshes[0]

        spheres, warn = _generate_spheres_for_mesh(
            combined,
            max_spheres=max_spheres_per_link,
            voxel_fraction=voxel_fraction,
        )
        if warn:
            warnings.append(f"Link '{link_name}': {warn}")
        if spheres:
            collision_spheres.append({link_name: spheres})

    # --- Build YAML structure ---
    description: Dict[str, Any] = {
        "api_version": 1.0,
        "cspace": cspace,
        "default_q": _FlowList([round(float(q), 6) for q in default_q]),
        "acceleration_limits": _FlowList(accel_limits),
        "jerk_limits": _FlowList(jerk_limits),
    }
    if cspace_to_urdf_rules:
        description["cspace_to_urdf_rules"] = cspace_to_urdf_rules
    if collision_spheres:
        description["collision_spheres"] = collision_spheres

    # --- Write output ---
    if output_path is None:
        base = os.path.splitext(urdf_path)[0]
        output_path = base + "_lula_description.yaml"

    try:
        with open(output_path, "w") as f:
            yaml.dump(
                description,
                f,
                Dumper=_LulaDumper,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                width=120,
            )
    except IOError as e:
        return {"success": False, "error": f"Failed to write output: {e}"}

    n_spheres = sum(
        len(list(d.values())[0]) for d in collision_spheres
    )

    return {
        "success": True,
        "output_path": output_path,
        "robot_name": robot["robot_name"],
        "cspace": cspace,
        "num_controllable_joints": len(cspace),
        "num_links_with_spheres": len(collision_spheres),
        "total_spheres": n_spheres,
        "warnings": warnings,
        "summary": (
            f"Robot '{robot['robot_name']}': {len(cspace)} joints in cspace, "
            f"{len(collision_spheres)} links with collision spheres "
            f"({n_spheres} total). Written to {output_path}"
        ),
    }
