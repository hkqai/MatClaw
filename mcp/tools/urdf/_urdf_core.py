"""
Core URDF parsing, validation, and utility logic.

Internal module shared by urdf_validate, urdf_fix, and urdf_inspect tools.
Uses only stdlib xml.etree.ElementTree (zero external dependencies).
"""

import copy
import math
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Issue dataclass
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    severity: str  # "error", "warning", "info"
    category: str  # "usd_naming", "materials", "joint_limits", "inertial", "collision", "mesh_references"
    element_type: str  # "link", "joint", "material", etc.
    element_name: str
    message: str
    xpath: str = ""
    fix_available: bool = False
    details: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USD_SAFE_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}

VALID_CATEGORIES = [
    "usd_naming",
    "materials",
    "joint_limits",
    "inertial",
    "collision",
    "mesh_references",
]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_urdf(file_path: Optional[str] = None,
               urdf_string: Optional[str] = None) -> Tuple[ET.ElementTree, str]:
    """Parse a URDF from file path or string.

    Returns (ElementTree, urdf_dir) where urdf_dir is the directory
    containing the URDF file (used for resolving relative paths).
    """
    if file_path and urdf_string:
        raise ValueError("Provide either file_path or urdf_string, not both.")
    if not file_path and not urdf_string:
        raise ValueError("Provide either file_path or urdf_string.")

    if file_path:
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"URDF file not found: {file_path}")
        tree = ET.parse(str(path))
        urdf_dir = str(path.parent)
    else:
        root = ET.fromstring(urdf_string)
        tree = ET.ElementTree(root)
        urdf_dir = os.getcwd()

    # Basic sanity check
    root = tree.getroot()
    if root.tag != "robot":
        raise ValueError(f"Expected root element <robot>, got <{root.tag}>")

    return tree, urdf_dir


# ---------------------------------------------------------------------------
# USD naming helpers
# ---------------------------------------------------------------------------

def is_usd_safe_name(name: str) -> bool:
    """Check if a name is valid for USD prim paths."""
    return bool(USD_SAFE_NAME_RE.match(name))


def make_usd_safe_name(name: str, existing_names: Optional[set] = None) -> str:
    """Convert a name to a USD-safe name.

    Rules:
    - Replace any non-alphanumeric character (except underscore) with '_'
    - Prefix 'n_' if name starts with a digit
    - Collapse consecutive underscores
    - Handle collisions with existing_names by appending _2, _3, etc.
    """
    if existing_names is None:
        existing_names = set()

    # Replace non-alnum/underscore with underscore
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", name)

    # Collapse consecutive underscores
    safe = re.sub(r"_+", "_", safe)

    # Strip leading/trailing underscores (but keep at least one char)
    safe = safe.strip("_") or "unnamed"

    # Prefix if starts with digit
    if safe[0].isdigit():
        safe = "n_" + safe

    # Handle collisions
    base = safe
    counter = 2
    while safe in existing_names:
        safe = f"{base}_{counter}"
        counter += 1

    return safe


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------

def validate_usd_naming(tree: ET.ElementTree) -> List[Issue]:
    """Check all link, joint, and material names for USD compliance."""
    issues = []
    root = tree.getroot()

    # Check robot name
    robot_name = root.get("name", "")
    if robot_name and not is_usd_safe_name(robot_name):
        issues.append(Issue(
            severity="warning",
            category="usd_naming",
            element_type="robot",
            element_name=robot_name,
            message=f"Robot name '{robot_name}' contains characters not safe for USD",
            xpath="/robot",
            fix_available=True,
        ))

    # Check links
    for link in root.iter("link"):
        name = link.get("name", "")
        if name and not is_usd_safe_name(name):
            issues.append(Issue(
                severity="error",
                category="usd_naming",
                element_type="link",
                element_name=name,
                message=f"Link name '{name}' contains characters not safe for USD prim paths",
                xpath=f"//link[@name='{name}']",
                fix_available=True,
            ))

    # Check joints
    for joint in root.iter("joint"):
        name = joint.get("name", "")
        if name and not is_usd_safe_name(name):
            issues.append(Issue(
                severity="error",
                category="usd_naming",
                element_type="joint",
                element_name=name,
                message=f"Joint name '{name}' contains characters not safe for USD prim paths",
                xpath=f"//joint[@name='{name}']",
                fix_available=True,
            ))

    # Check materials
    for material in root.iter("material"):
        name = material.get("name", "")
        if name and not is_usd_safe_name(name):
            issues.append(Issue(
                severity="warning",
                category="usd_naming",
                element_type="material",
                element_name=name,
                message=f"Material name '{name}' contains characters not safe for USD",
                xpath=f"//material[@name='{name}']",
                fix_available=True,
            ))

    return issues


def validate_materials(tree: ET.ElementTree, urdf_dir: str) -> List[Issue]:
    """Check for duplicate material names and texture issues."""
    issues = []
    root = tree.getroot()

    # Collect top-level material definitions
    materials: Dict[str, List] = {}
    for material in root.findall("material"):
        name = material.get("name", "")
        if not name:
            continue

        color_elem = material.find("color")
        rgba = color_elem.get("rgba", "") if color_elem is not None else ""

        texture_elem = material.find("texture")
        texture = texture_elem.get("filename", "") if texture_elem is not None else ""

        key = name
        if key not in materials:
            materials[key] = []
        materials[key].append({"rgba": rgba, "texture": texture, "element": material})

    # Check for duplicates with different values
    for name, defs in materials.items():
        if len(defs) > 1:
            rgbas = set(d["rgba"] for d in defs)
            textures = set(d["texture"] for d in defs)
            if len(rgbas) > 1 or len(textures) > 1:
                issues.append(Issue(
                    severity="error",
                    category="materials",
                    element_type="material",
                    element_name=name,
                    message=f"Material '{name}' defined {len(defs)} times with different values",
                    xpath=f"//material[@name='{name}']",
                    fix_available=True,
                    details={"count": len(defs)},
                ))

    # Check texture files
    for material in root.iter("material"):
        texture_elem = material.find("texture")
        if texture_elem is not None:
            filename = texture_elem.get("filename", "")
            if filename:
                # Check for JPG (USD prefers PNG)
                if filename.lower().endswith((".jpg", ".jpeg")):
                    issues.append(Issue(
                        severity="warning",
                        category="materials",
                        element_type="material",
                        element_name=material.get("name", ""),
                        message=f"Texture '{filename}' is JPEG; USD/Isaac Sim prefers PNG",
                        xpath=f"//material[@name='{material.get('name', '')}']/texture",
                        fix_available=False,
                    ))

                # Check if texture file exists (skip package:// paths)
                if not filename.startswith("package://"):
                    tex_path = Path(urdf_dir) / filename
                    if not tex_path.exists():
                        issues.append(Issue(
                            severity="error",
                            category="materials",
                            element_type="material",
                            element_name=material.get("name", ""),
                            message=f"Texture file not found: {filename}",
                            xpath=f"//material[@name='{material.get('name', '')}']/texture",
                            fix_available=False,
                        ))

    return issues


def validate_joint_limits(tree: ET.ElementTree) -> List[Issue]:
    """Check joints for infinite limits, missing effort/velocity."""
    issues = []
    root = tree.getroot()

    for joint in root.iter("joint"):
        joint_name = joint.get("name", "")
        joint_type = joint.get("type", "")

        # Fixed and floating joints don't need limits
        if joint_type in ("fixed", "floating"):
            continue

        limit = joint.find("limit")

        if joint_type in ("revolute", "prismatic"):
            if limit is None:
                issues.append(Issue(
                    severity="error",
                    category="joint_limits",
                    element_type="joint",
                    element_name=joint_name,
                    message=f"Joint '{joint_name}' (type={joint_type}) is missing <limit> element",
                    xpath=f"//joint[@name='{joint_name}']",
                    fix_available=True,
                ))
                continue

            # Check for infinite/missing position limits
            lower = limit.get("lower")
            upper = limit.get("upper")
            if lower is not None and upper is not None:
                try:
                    lower_val = float(lower)
                    upper_val = float(upper)
                    if math.isinf(lower_val) or math.isinf(upper_val):
                        issues.append(Issue(
                            severity="error",
                            category="joint_limits",
                            element_type="joint",
                            element_name=joint_name,
                            message=f"Joint '{joint_name}' has infinite position limits",
                            xpath=f"//joint[@name='{joint_name}']/limit",
                            fix_available=True,
                            details={"lower": lower_val, "upper": upper_val},
                        ))
                except ValueError:
                    pass

        # Check effort and velocity for all non-fixed joints
        if limit is not None:
            effort = limit.get("effort")
            velocity = limit.get("velocity")

            if effort is None:
                issues.append(Issue(
                    severity="warning",
                    category="joint_limits",
                    element_type="joint",
                    element_name=joint_name,
                    message=f"Joint '{joint_name}' is missing effort limit",
                    xpath=f"//joint[@name='{joint_name}']/limit",
                    fix_available=True,
                ))
            elif effort is not None:
                try:
                    if math.isinf(float(effort)):
                        issues.append(Issue(
                            severity="warning",
                            category="joint_limits",
                            element_type="joint",
                            element_name=joint_name,
                            message=f"Joint '{joint_name}' has infinite effort limit",
                            xpath=f"//joint[@name='{joint_name}']/limit",
                            fix_available=True,
                        ))
                except ValueError:
                    pass

            if velocity is None:
                issues.append(Issue(
                    severity="warning",
                    category="joint_limits",
                    element_type="joint",
                    element_name=joint_name,
                    message=f"Joint '{joint_name}' is missing velocity limit",
                    xpath=f"//joint[@name='{joint_name}']/limit",
                    fix_available=True,
                ))
            elif velocity is not None:
                try:
                    if math.isinf(float(velocity)):
                        issues.append(Issue(
                            severity="warning",
                            category="joint_limits",
                            element_type="joint",
                            element_name=joint_name,
                            message=f"Joint '{joint_name}' has infinite velocity limit",
                            xpath=f"//joint[@name='{joint_name}']/limit",
                            fix_available=True,
                        ))
                except ValueError:
                    pass

    return issues


def validate_inertial(tree: ET.ElementTree) -> List[Issue]:
    """Check links for missing or zero inertial properties."""
    issues = []
    root = tree.getroot()

    for link in root.iter("link"):
        link_name = link.get("name", "")
        has_visual = link.find("visual") is not None
        has_collision = link.find("collision") is not None
        inertial = link.find("inertial")

        # Only flag missing inertial if the link has geometry
        if (has_visual or has_collision) and inertial is None:
            issues.append(Issue(
                severity="error",
                category="inertial",
                element_type="link",
                element_name=link_name,
                message=f"Link '{link_name}' has geometry but no <inertial> element",
                xpath=f"//link[@name='{link_name}']",
                fix_available=True,
            ))
            continue

        if inertial is None:
            # Empty link (e.g., world frame) — info only
            if not has_visual and not has_collision:
                issues.append(Issue(
                    severity="info",
                    category="inertial",
                    element_type="link",
                    element_name=link_name,
                    message=f"Link '{link_name}' is empty (no visual, collision, or inertial)",
                    xpath=f"//link[@name='{link_name}']",
                    fix_available=False,
                ))
            continue

        # Check mass
        mass_elem = inertial.find("mass")
        if mass_elem is not None:
            try:
                mass_val = float(mass_elem.get("value", "0"))
                if mass_val <= 0:
                    issues.append(Issue(
                        severity="error",
                        category="inertial",
                        element_type="link",
                        element_name=link_name,
                        message=f"Link '{link_name}' has non-positive mass ({mass_val})",
                        xpath=f"//link[@name='{link_name}']/inertial/mass",
                        fix_available=True,
                        details={"mass": mass_val},
                    ))
            except ValueError:
                pass
        else:
            issues.append(Issue(
                severity="error",
                category="inertial",
                element_type="link",
                element_name=link_name,
                message=f"Link '{link_name}' inertial is missing <mass> element",
                xpath=f"//link[@name='{link_name}']/inertial",
                fix_available=True,
            ))

        # Check inertia tensor
        inertia_elem = inertial.find("inertia")
        if inertia_elem is not None:
            attrs = ["ixx", "iyy", "izz"]
            all_zero = True
            for attr in attrs:
                try:
                    val = float(inertia_elem.get(attr, "0"))
                    if val != 0:
                        all_zero = False
                    if val < 0:
                        issues.append(Issue(
                            severity="error",
                            category="inertial",
                            element_type="link",
                            element_name=link_name,
                            message=f"Link '{link_name}' has negative inertia {attr}={val}",
                            xpath=f"//link[@name='{link_name}']/inertial/inertia",
                            fix_available=True,
                        ))
                except ValueError:
                    pass

            if all_zero:
                issues.append(Issue(
                    severity="warning",
                    category="inertial",
                    element_type="link",
                    element_name=link_name,
                    message=f"Link '{link_name}' has all-zero diagonal inertia tensor",
                    xpath=f"//link[@name='{link_name}']/inertial/inertia",
                    fix_available=True,
                ))
        else:
            issues.append(Issue(
                severity="error",
                category="inertial",
                element_type="link",
                element_name=link_name,
                message=f"Link '{link_name}' inertial is missing <inertia> element",
                xpath=f"//link[@name='{link_name}']/inertial",
                fix_available=True,
            ))

    return issues


def validate_collision(tree: ET.ElementTree) -> List[Issue]:
    """Check for links with visual geometry but no collision geometry."""
    issues = []
    root = tree.getroot()

    for link in root.iter("link"):
        link_name = link.get("name", "")
        has_visual = link.find("visual") is not None
        has_collision = link.find("collision") is not None

        if has_visual and not has_collision:
            issues.append(Issue(
                severity="warning",
                category="collision",
                element_type="link",
                element_name=link_name,
                message=f"Link '{link_name}' has visual geometry but no collision geometry",
                xpath=f"//link[@name='{link_name}']",
                fix_available=False,
            ))

    return issues


def validate_mesh_references(tree: ET.ElementTree, urdf_dir: str) -> List[Issue]:
    """Check that all mesh file references exist on disk."""
    issues = []
    root = tree.getroot()

    for link in root.iter("link"):
        link_name = link.get("name", "")
        for geom_type in ("visual", "collision"):
            for geom_parent in link.findall(geom_type):
                geom = geom_parent.find("geometry")
                if geom is None:
                    continue
                mesh = geom.find("mesh")
                if mesh is None:
                    continue
                filename = mesh.get("filename", "")
                if not filename:
                    continue

                # Skip package:// — requires ROS workspace context
                if filename.startswith("package://"):
                    issues.append(Issue(
                        severity="info",
                        category="mesh_references",
                        element_type="link",
                        element_name=link_name,
                        message=f"Mesh uses package:// URI: {filename} (cannot verify without ROS)",
                        xpath=f"//link[@name='{link_name}']/{geom_type}/geometry/mesh",
                        fix_available=False,
                    ))
                    continue

                mesh_path = Path(urdf_dir) / filename
                if not mesh_path.exists():
                    issues.append(Issue(
                        severity="error",
                        category="mesh_references",
                        element_type="link",
                        element_name=link_name,
                        message=f"Mesh file not found: {filename}",
                        xpath=f"//link[@name='{link_name}']/{geom_type}/geometry/mesh",
                        fix_available=False,
                        details={"filename": filename, "resolved_path": str(mesh_path)},
                    ))

    return issues


def run_all_validations(tree: ET.ElementTree, urdf_dir: str,
                        categories: Optional[List[str]] = None,
                        min_severity: str = "info") -> List[Issue]:
    """Run all validation checks and return combined issues.

    Args:
        tree: Parsed URDF ElementTree
        urdf_dir: Directory containing the URDF file
        categories: Optional list of categories to check (default: all)
        min_severity: Minimum severity to include ("error", "warning", "info")
    """
    validators = {
        "usd_naming": lambda: validate_usd_naming(tree),
        "materials": lambda: validate_materials(tree, urdf_dir),
        "joint_limits": lambda: validate_joint_limits(tree),
        "inertial": lambda: validate_inertial(tree),
        "collision": lambda: validate_collision(tree),
        "mesh_references": lambda: validate_mesh_references(tree, urdf_dir),
    }

    if categories:
        for cat in categories:
            if cat not in validators:
                raise ValueError(f"Unknown category: {cat}. Valid: {list(validators.keys())}")
        selected = {k: v for k, v in validators.items() if k in categories}
    else:
        selected = validators

    all_issues = []
    for validator_fn in selected.values():
        all_issues.extend(validator_fn())

    # Filter by severity
    sev_threshold = SEVERITY_ORDER.get(min_severity, 2)
    all_issues = [i for i in all_issues if SEVERITY_ORDER.get(i.severity, 2) <= sev_threshold]

    return all_issues


# ---------------------------------------------------------------------------
# Kinematic tree helpers
# ---------------------------------------------------------------------------

def build_joint_tree(tree: ET.ElementTree) -> dict:
    """Build a kinematic tree structure from the URDF.

    Returns dict with:
        - root: root link name
        - links: {name: {children: [...], parent: str|None}}
        - joints: [{name, type, parent_link, child_link}]
    """
    root = tree.getroot()

    links = {}
    for link in root.iter("link"):
        name = link.get("name", "")
        links[name] = {"children": [], "parent": None, "joint_to_parent": None}

    joints = []
    for joint in root.iter("joint"):
        jname = joint.get("name", "")
        jtype = joint.get("type", "")
        parent_elem = joint.find("parent")
        child_elem = joint.find("child")
        parent_link = parent_elem.get("link", "") if parent_elem is not None else ""
        child_link = child_elem.get("link", "") if child_elem is not None else ""

        joints.append({
            "name": jname,
            "type": jtype,
            "parent_link": parent_link,
            "child_link": child_link,
        })

        if child_link in links:
            links[child_link]["parent"] = parent_link
            links[child_link]["joint_to_parent"] = jname
        if parent_link in links:
            links[parent_link]["children"].append(child_link)

    # Find root link(s) — links with no parent
    roots = [name for name, info in links.items() if info["parent"] is None]

    return {
        "root": roots[0] if roots else None,
        "roots": roots,
        "links": links,
        "joints": joints,
    }


def _render_tree_ascii(links: dict, node: str, prefix: str = "", is_last: bool = True) -> List[str]:
    """Recursively render kinematic tree as ASCII art."""
    connector = "└── " if is_last else "├── "
    joint_name = links[node].get("joint_to_parent", "")
    joint_str = f" [{joint_name}]" if joint_name else ""
    lines = [f"{prefix}{connector}{node}{joint_str}"]

    children = links[node]["children"]
    new_prefix = prefix + ("    " if is_last else "│   ")
    for i, child in enumerate(children):
        is_child_last = (i == len(children) - 1)
        lines.extend(_render_tree_ascii(links, child, new_prefix, is_child_last))

    return lines


def render_kinematic_tree(tree: ET.ElementTree) -> str:
    """Render the kinematic tree as ASCII art."""
    jtree = build_joint_tree(tree)
    links = jtree["links"]
    root = jtree["root"]

    if root is None:
        return "(empty kinematic tree)"

    lines = [root]
    children = links[root]["children"]
    for i, child in enumerate(children):
        is_last = (i == len(children) - 1)
        lines.extend(_render_tree_ascii(links, child, "", is_last))

    return "\n".join(lines)


def compute_mass_distribution(tree: ET.ElementTree) -> dict:
    """Compute per-link masses and total mass."""
    root = tree.getroot()
    mass_breakdown = {}
    total_mass = 0.0

    for link in root.iter("link"):
        link_name = link.get("name", "")
        inertial = link.find("inertial")
        if inertial is not None:
            mass_elem = inertial.find("mass")
            if mass_elem is not None:
                try:
                    mass = float(mass_elem.get("value", "0"))
                    mass_breakdown[link_name] = mass
                    total_mass += mass
                except ValueError:
                    mass_breakdown[link_name] = None
            else:
                mass_breakdown[link_name] = None
        # Don't include links without inertial in breakdown

    return {
        "total_mass": round(total_mass, 6),
        "mass_breakdown": mass_breakdown,
    }
