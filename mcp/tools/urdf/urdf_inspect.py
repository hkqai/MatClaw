"""
Tool for inspecting URDF structure: kinematic tree, mass distribution,
mesh files, materials, and joint breakdown.
"""

from typing import Any, Dict, Optional, Annotated
from pydantic import Field

from ._urdf_core import (
    parse_urdf,
    build_joint_tree,
    render_kinematic_tree,
    compute_mass_distribution,
)


def urdf_inspect(
    file_path: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Path to the URDF file to inspect. "
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
) -> Dict[str, Any]:
    """
    Inspect a URDF file and return its structural overview.

    Provides a quick summary of the robot model: link/joint counts,
    kinematic tree visualization, mesh files, materials, and mass distribution.

    Returns:
        dict: Structural information including:
            - success (bool): Whether inspection completed
            - robot_name (str): Name of the robot
            - link_count (int): Number of links
            - joint_count (int): Number of joints
            - joint_types (dict): Count of each joint type
            - root_link (str): Root link name
            - kinematic_tree (str): ASCII visualization
            - mesh_files (list): Referenced mesh file paths
            - materials (list): Material definitions
            - total_mass (float): Sum of all link masses
            - mass_breakdown (dict): Per-link masses
            - summary (str): Human-readable summary
            - error (str): Error message if inspection failed
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

    root = tree.getroot()
    robot_name = root.get("name", "unknown")

    # Links
    links = [link.get("name", "") for link in root.iter("link")]

    # Joints
    joints = []
    joint_types = {}
    for joint in root.iter("joint"):
        jname = joint.get("name", "")
        jtype = joint.get("type", "")
        joints.append({"name": jname, "type": jtype})
        joint_types[jtype] = joint_types.get(jtype, 0) + 1

    # Kinematic tree
    jtree = build_joint_tree(tree)
    kinematic_tree_ascii = render_kinematic_tree(tree)

    # Mesh files
    mesh_files = []
    for link in root.iter("link"):
        link_name = link.get("name", "")
        for geom_type in ("visual", "collision"):
            for geom_parent in link.findall(geom_type):
                geom = geom_parent.find("geometry")
                if geom is None:
                    continue
                mesh = geom.find("mesh")
                if mesh is not None:
                    filename = mesh.get("filename", "")
                    if filename:
                        mesh_files.append({
                            "link": link_name,
                            "type": geom_type,
                            "filename": filename,
                        })

    # Materials
    materials = []
    seen_materials = set()
    for material in root.iter("material"):
        mname = material.get("name", "")
        color_elem = material.find("color")
        rgba = color_elem.get("rgba", "") if color_elem is not None else ""
        texture_elem = material.find("texture")
        texture = texture_elem.get("filename", "") if texture_elem is not None else ""

        key = (mname, rgba, texture)
        if key not in seen_materials:
            seen_materials.add(key)
            entry = {"name": mname}
            if rgba:
                entry["rgba"] = rgba
            if texture:
                entry["texture"] = texture
            materials.append(entry)

    # Mass distribution
    mass_info = compute_mass_distribution(tree)

    # Summary
    summary_parts = [
        f"Robot '{robot_name}': {len(links)} links, {len(joints)} joints",
    ]
    if joint_types:
        type_strs = [f"{count} {jtype}" for jtype, count in sorted(joint_types.items())]
        summary_parts.append(f"Joint types: {', '.join(type_strs)}")
    summary_parts.append(f"Total mass: {mass_info['total_mass']} kg")
    summary_parts.append(f"Mesh files: {len(mesh_files)}")

    return {
        "success": True,
        "file_path": file_path,
        "robot_name": robot_name,
        "link_count": len(links),
        "joint_count": len(joints),
        "joint_types": joint_types,
        "root_link": jtree["root"],
        "kinematic_tree": kinematic_tree_ascii,
        "mesh_files": mesh_files,
        "materials": materials,
        "total_mass": mass_info["total_mass"],
        "mass_breakdown": mass_info["mass_breakdown"],
        "summary": " | ".join(summary_parts),
    }
