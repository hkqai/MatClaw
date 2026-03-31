"""
Tool for automatically fixing URDF issues for Isaac Sim / USD compatibility.

Applies non-destructive fixes: always writes to a new file, never modifies the original.
Returns a name_mapping dict so downstream code can be updated.
"""

import copy
import math
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Annotated
from pydantic import Field

from ._urdf_core import (
    parse_urdf,
    run_all_validations,
    is_usd_safe_name,
    make_usd_safe_name,
    VALID_CATEGORIES,
)


def _fix_usd_naming(root: ET.Element) -> tuple:
    """Fix non-USD-compliant names in links, joints, and materials.

    Returns (fixes list, name_mapping dict).
    """
    fixes = []
    name_mapping = {}
    used_names = set()

    # Collect all current names
    for link in root.iter("link"):
        used_names.add(link.get("name", ""))
    for joint in root.iter("joint"):
        used_names.add(joint.get("name", ""))

    # Fix link names
    link_renames = {}
    for link in root.iter("link"):
        old_name = link.get("name", "")
        if old_name and not is_usd_safe_name(old_name):
            new_name = make_usd_safe_name(old_name, used_names - {old_name})
            link.set("name", new_name)
            link_renames[old_name] = new_name
            used_names.discard(old_name)
            used_names.add(new_name)
            name_mapping[old_name] = new_name
            fixes.append({
                "category": "usd_naming",
                "element_type": "link",
                "old_name": old_name,
                "new_name": new_name,
                "message": f"Renamed link '{old_name}' → '{new_name}'",
            })

    # Fix joint names
    joint_renames = {}
    for joint in root.iter("joint"):
        old_name = joint.get("name", "")
        if old_name and not is_usd_safe_name(old_name):
            new_name = make_usd_safe_name(old_name, used_names - {old_name})
            joint.set("name", new_name)
            joint_renames[old_name] = new_name
            used_names.discard(old_name)
            used_names.add(new_name)
            name_mapping[old_name] = new_name
            fixes.append({
                "category": "usd_naming",
                "element_type": "joint",
                "old_name": old_name,
                "new_name": new_name,
                "message": f"Renamed joint '{old_name}' → '{new_name}'",
            })

    # Update parent/child references in joints
    for joint in root.iter("joint"):
        parent = joint.find("parent")
        if parent is not None:
            plink = parent.get("link", "")
            if plink in link_renames:
                parent.set("link", link_renames[plink])
        child = joint.find("child")
        if child is not None:
            clink = child.get("link", "")
            if clink in link_renames:
                child.set("link", link_renames[clink])

    # Fix robot name
    robot_name = root.get("name", "")
    if robot_name and not is_usd_safe_name(robot_name):
        new_name = make_usd_safe_name(robot_name, set())
        root.set("name", new_name)
        name_mapping[robot_name] = new_name
        fixes.append({
            "category": "usd_naming",
            "element_type": "robot",
            "old_name": robot_name,
            "new_name": new_name,
            "message": f"Renamed robot '{robot_name}' → '{new_name}'",
        })

    # Fix material names and update references
    material_renames = {}
    mat_used_names = set()
    for material in root.iter("material"):
        mat_used_names.add(material.get("name", ""))

    for material in root.findall("material"):
        old_name = material.get("name", "")
        if old_name and not is_usd_safe_name(old_name):
            new_name = make_usd_safe_name(old_name, mat_used_names - {old_name})
            material.set("name", new_name)
            material_renames[old_name] = new_name
            mat_used_names.discard(old_name)
            mat_used_names.add(new_name)
            fixes.append({
                "category": "usd_naming",
                "element_type": "material",
                "old_name": old_name,
                "new_name": new_name,
                "message": f"Renamed material '{old_name}' → '{new_name}'",
            })

    # Update material references in visual elements
    if material_renames:
        for visual in root.iter("visual"):
            mat_ref = visual.find("material")
            if mat_ref is not None:
                mname = mat_ref.get("name", "")
                if mname in material_renames:
                    mat_ref.set("name", material_renames[mname])

    return fixes, name_mapping


def _fix_duplicate_materials(root: ET.Element) -> List[dict]:
    """Deduplicate material definitions by appending suffixes."""
    fixes = []

    # Find top-level materials
    materials_by_name = {}
    for material in root.findall("material"):
        name = material.get("name", "")
        if name not in materials_by_name:
            materials_by_name[name] = []
        materials_by_name[name].append(material)

    for name, mat_list in materials_by_name.items():
        if len(mat_list) <= 1:
            continue

        # Keep the first, rename the rest
        for i, mat in enumerate(mat_list[1:], start=2):
            new_name = f"{name}_{i}"
            mat.set("name", new_name)
            fixes.append({
                "category": "materials",
                "element_type": "material",
                "old_name": name,
                "new_name": new_name,
                "message": f"Deduplicated material '{name}' → '{new_name}'",
            })

    return fixes


def _fix_joint_limits(root: ET.Element,
                      max_joint_position: float,
                      max_joint_velocity: float,
                      max_joint_effort: float) -> List[dict]:
    """Fix infinite limits and add missing effort/velocity."""
    fixes = []

    for joint in root.iter("joint"):
        joint_name = joint.get("name", "")
        joint_type = joint.get("type", "")

        if joint_type in ("fixed", "floating"):
            continue

        limit = joint.find("limit")

        if joint_type in ("revolute", "prismatic") and limit is None:
            limit = ET.SubElement(joint, "limit")
            limit.set("lower", str(-max_joint_position))
            limit.set("upper", str(max_joint_position))
            limit.set("effort", str(max_joint_effort))
            limit.set("velocity", str(max_joint_velocity))
            fixes.append({
                "category": "joint_limits",
                "element_type": "joint",
                "element_name": joint_name,
                "message": f"Added missing <limit> to joint '{joint_name}'",
            })
            continue

        if limit is None:
            continue

        # Clamp infinite position limits
        lower = limit.get("lower")
        upper = limit.get("upper")
        if lower is not None:
            try:
                if math.isinf(float(lower)):
                    limit.set("lower", str(-max_joint_position))
                    fixes.append({
                        "category": "joint_limits",
                        "element_type": "joint",
                        "element_name": joint_name,
                        "message": f"Clamped infinite lower limit on '{joint_name}' to {-max_joint_position}",
                    })
            except ValueError:
                pass
        if upper is not None:
            try:
                if math.isinf(float(upper)):
                    limit.set("upper", str(max_joint_position))
                    fixes.append({
                        "category": "joint_limits",
                        "element_type": "joint",
                        "element_name": joint_name,
                        "message": f"Clamped infinite upper limit on '{joint_name}' to {max_joint_position}",
                    })
            except ValueError:
                pass

        # Add missing effort
        if limit.get("effort") is None:
            limit.set("effort", str(max_joint_effort))
            fixes.append({
                "category": "joint_limits",
                "element_type": "joint",
                "element_name": joint_name,
                "message": f"Added missing effort={max_joint_effort} to '{joint_name}'",
            })
        else:
            try:
                if math.isinf(float(limit.get("effort", "0"))):
                    limit.set("effort", str(max_joint_effort))
                    fixes.append({
                        "category": "joint_limits",
                        "element_type": "joint",
                        "element_name": joint_name,
                        "message": f"Clamped infinite effort on '{joint_name}' to {max_joint_effort}",
                    })
            except ValueError:
                pass

        # Add missing velocity
        if limit.get("velocity") is None:
            limit.set("velocity", str(max_joint_velocity))
            fixes.append({
                "category": "joint_limits",
                "element_type": "joint",
                "element_name": joint_name,
                "message": f"Added missing velocity={max_joint_velocity} to '{joint_name}'",
            })
        else:
            try:
                if math.isinf(float(limit.get("velocity", "0"))):
                    limit.set("velocity", str(max_joint_velocity))
                    fixes.append({
                        "category": "joint_limits",
                        "element_type": "joint",
                        "element_name": joint_name,
                        "message": f"Clamped infinite velocity on '{joint_name}' to {max_joint_velocity}",
                    })
            except ValueError:
                pass

    return fixes


def _fix_inertial(root: ET.Element,
                  default_mass: float,
                  default_inertia: float) -> List[dict]:
    """Add missing inertial elements with configurable defaults."""
    fixes = []

    for link in root.iter("link"):
        link_name = link.get("name", "")
        has_visual = link.find("visual") is not None
        has_collision = link.find("collision") is not None
        inertial = link.find("inertial")

        if not has_visual and not has_collision:
            continue

        if inertial is None:
            inertial = ET.SubElement(link, "inertial")
            mass = ET.SubElement(inertial, "mass")
            mass.set("value", str(default_mass))
            origin = ET.SubElement(inertial, "origin")
            origin.set("rpy", "0 0 0")
            origin.set("xyz", "0 0 0")
            inertia = ET.SubElement(inertial, "inertia")
            inertia.set("ixx", str(default_inertia))
            inertia.set("ixy", "0")
            inertia.set("ixz", "0")
            inertia.set("iyy", str(default_inertia))
            inertia.set("iyz", "0")
            inertia.set("izz", str(default_inertia))
            fixes.append({
                "category": "inertial",
                "element_type": "link",
                "element_name": link_name,
                "message": f"Added default inertial to link '{link_name}' "
                           f"(mass={default_mass}, inertia={default_inertia})",
            })
            continue

        # Fix zero/negative mass
        mass_elem = inertial.find("mass")
        if mass_elem is not None:
            try:
                mass_val = float(mass_elem.get("value", "0"))
                if mass_val <= 0:
                    mass_elem.set("value", str(default_mass))
                    fixes.append({
                        "category": "inertial",
                        "element_type": "link",
                        "element_name": link_name,
                        "message": f"Replaced non-positive mass ({mass_val}) with default ({default_mass}) on '{link_name}'",
                    })
            except ValueError:
                pass
        else:
            mass_elem = ET.SubElement(inertial, "mass")
            mass_elem.set("value", str(default_mass))
            fixes.append({
                "category": "inertial",
                "element_type": "link",
                "element_name": link_name,
                "message": f"Added missing mass element to '{link_name}'",
            })

        # Fix zero inertia tensor
        inertia_elem = inertial.find("inertia")
        if inertia_elem is not None:
            diag_attrs = ["ixx", "iyy", "izz"]
            all_zero = True
            for attr in diag_attrs:
                try:
                    val = float(inertia_elem.get(attr, "0"))
                    if val != 0:
                        all_zero = False
                    if val < 0:
                        inertia_elem.set(attr, str(default_inertia))
                        fixes.append({
                            "category": "inertial",
                            "element_type": "link",
                            "element_name": link_name,
                            "message": f"Replaced negative {attr} with default on '{link_name}'",
                        })
                        all_zero = False
                except ValueError:
                    pass

            if all_zero:
                for attr in diag_attrs:
                    inertia_elem.set(attr, str(default_inertia))
                fixes.append({
                    "category": "inertial",
                    "element_type": "link",
                    "element_name": link_name,
                    "message": f"Replaced all-zero inertia with defaults on '{link_name}'",
                })
        else:
            inertia_elem = ET.SubElement(inertial, "inertia")
            inertia_elem.set("ixx", str(default_inertia))
            inertia_elem.set("ixy", "0")
            inertia_elem.set("ixz", "0")
            inertia_elem.set("iyy", str(default_inertia))
            inertia_elem.set("iyz", "0")
            inertia_elem.set("izz", str(default_inertia))
            fixes.append({
                "category": "inertial",
                "element_type": "link",
                "element_name": link_name,
                "message": f"Added missing inertia tensor to '{link_name}'",
            })

    return fixes


def _indent_xml(elem: ET.Element, level: int = 0) -> None:
    """Add indentation to XML tree for pretty-printing."""
    indent = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            _indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent
    if level == 0:
        elem.tail = "\n"


def urdf_fix(
    file_path: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Path to the URDF file to fix. "
            "Provide either file_path or urdf_string, not both."
        )
    ] = None,
    urdf_string: Annotated[
        Optional[str],
        Field(
            default=None,
            description="URDF XML content as a string. "
            "Provide either file_path or urdf_string, not both."
        )
    ] = None,
    output_path: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Path to write the fixed URDF file. "
            "If not specified, appends '_fixed' before the extension. "
            "The original file is never modified."
        )
    ] = None,
    fix_categories: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description="List of fix categories to apply. "
            "Options: 'usd_naming', 'materials', 'joint_limits', 'inertial'. "
            "Default: all available fixes."
        )
    ] = None,
    default_mass: Annotated[
        float,
        Field(
            default=0.1,
            gt=0,
            description="Default mass (kg) for links missing inertial. Default: 0.1"
        )
    ] = 0.1,
    default_inertia: Annotated[
        float,
        Field(
            default=0.001,
            gt=0,
            description="Default diagonal inertia value for links missing inertia tensors. Default: 0.001"
        )
    ] = 0.001,
    max_joint_position: Annotated[
        float,
        Field(
            default=6.283185307179586,
            gt=0,
            description="Maximum joint position limit (rad) to replace infinity. Default: 2*pi"
        )
    ] = 6.283185307179586,
    max_joint_velocity: Annotated[
        float,
        Field(
            default=3.141592653589793,
            gt=0,
            description="Default velocity limit (rad/s) for joints missing velocity. Default: pi"
        )
    ] = 3.141592653589793,
    max_joint_effort: Annotated[
        float,
        Field(
            default=100.0,
            gt=0,
            description="Default effort limit (Nm) for joints missing effort. Default: 100.0"
        )
    ] = 100.0,
) -> Dict[str, Any]:
    """
    Automatically fix common URDF issues for Isaac Sim / USD compatibility.

    Applies fixes in order: USD naming → material dedup → joint limits → inertial.
    Always writes to a new file (non-destructive). Returns a name_mapping dict
    for any renamed links/joints so downstream code can be updated.

    Returns:
        dict: Fix results including:
            - success (bool): Whether fixes were applied
            - output_path (str): Path to the fixed URDF file
            - fixed_urdf (str): Fixed URDF XML content (when input was urdf_string)
            - total_fixes (int): Number of fixes applied
            - fixes (list): Details of each fix
            - name_mapping (dict): Old name → new name for renamed elements
            - remaining_issues (int): Issues still present after fixing
            - summary (str): Human-readable summary
            - error (str): Error message if fixing failed
    """
    try:
        tree, urdf_dir = parse_urdf(file_path=file_path, urdf_string=urdf_string)
    except (ValueError, FileNotFoundError) as e:
        return {
            "success": False,
            "error": str(e),
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse URDF: {str(e)}",
        }

    # Work on a deep copy
    root = copy.deepcopy(tree.getroot())

    all_fixes = []
    name_mapping = {}

    available_fixes = {"usd_naming", "materials", "joint_limits", "inertial"}
    if fix_categories:
        for cat in fix_categories:
            if cat not in available_fixes:
                return {
                    "success": False,
                    "error": f"Unknown fix category: {cat}. Available: {sorted(available_fixes)}",
                }
        selected = set(fix_categories)
    else:
        selected = available_fixes

    # Apply fixes in order
    if "usd_naming" in selected:
        naming_fixes, naming_map = _fix_usd_naming(root)
        all_fixes.extend(naming_fixes)
        name_mapping.update(naming_map)

    if "materials" in selected:
        all_fixes.extend(_fix_duplicate_materials(root))

    if "joint_limits" in selected:
        all_fixes.extend(_fix_joint_limits(root, max_joint_position,
                                           max_joint_velocity, max_joint_effort))

    if "inertial" in selected:
        all_fixes.extend(_fix_inertial(root, default_mass, default_inertia))

    # Pretty-print
    _indent_xml(root)

    # Determine output
    fixed_tree = ET.ElementTree(root)

    result = {
        "success": True,
        "total_fixes": len(all_fixes),
        "fixes": all_fixes,
        "name_mapping": name_mapping,
    }

    if file_path:
        # Determine output path
        if output_path is None:
            p = Path(file_path)
            output_path = str(p.parent / f"{p.stem}_fixed{p.suffix}")

        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        fixed_tree.write(output_path, encoding="unicode", xml_declaration=True)
        result["output_path"] = output_path
        result["file_path"] = file_path
    else:
        # Return as string
        import io
        buf = io.StringIO()
        fixed_tree.write(buf, encoding="unicode", xml_declaration=True)
        result["fixed_urdf"] = buf.getvalue()

    # Re-validate to count remaining issues
    remaining = run_all_validations(fixed_tree, urdf_dir, min_severity="info")
    # Only count errors and warnings as remaining
    remaining_count = sum(1 for i in remaining if i.severity in ("error", "warning"))
    result["remaining_issues"] = remaining_count

    # Summary
    fix_cats = set(f["category"] for f in all_fixes)
    result["summary"] = (
        f"Applied {len(all_fixes)} fix(es) across {len(fix_cats)} category(ies). "
        f"{remaining_count} issue(s) remaining."
    )

    return result
