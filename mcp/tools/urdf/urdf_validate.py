"""
Tool for validating URDF files for Isaac Sim / USD compatibility.

Checks for USD naming violations, duplicate materials, joint limit issues,
missing inertial properties, collision geometry gaps, and broken mesh references.
"""

from typing import Any, Dict, List, Optional, Annotated
from pydantic import Field

from ._urdf_core import (
    parse_urdf,
    run_all_validations,
    VALID_CATEGORIES,
    SEVERITY_ORDER,
)


def urdf_validate(
    file_path: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Path to the URDF file to validate. "
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
    categories: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description="List of validation categories to check. "
            "Options: 'usd_naming', 'materials', 'joint_limits', 'inertial', "
            "'collision', 'mesh_references'. Default: all categories."
        )
    ] = None,
    min_severity: Annotated[
        str,
        Field(
            default="info",
            description="Minimum severity level to include in results. "
            "Options: 'error', 'warning', 'info'. Default: 'info' (show all)."
        )
    ] = "info",
) -> Dict[str, Any]:
    """
    Validate a URDF file for Isaac Sim / USD compatibility issues.

    Checks for common problems that cause silent failures when importing
    URDF files into Isaac Sim: non-compliant naming, duplicate materials,
    unbounded joint limits, missing inertial properties, missing collision
    geometry, and broken mesh file references.

    Returns:
        dict: Validation results including:
            - success (bool): Whether validation completed (not whether URDF is clean)
            - file_path (str): Path to the validated file
            - total_issues (int): Total number of issues found
            - issues_by_severity (dict): Count of issues per severity level
            - issues (list): List of issue details
            - summary (str): Human-readable summary
            - error (str): Error message if validation failed
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

    try:
        issues = run_all_validations(tree, urdf_dir, categories=categories,
                                     min_severity=min_severity)
    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
        }

    # Group by severity
    issues_by_severity = {"error": 0, "warning": 0, "info": 0}
    for issue in issues:
        issues_by_severity[issue.severity] = issues_by_severity.get(issue.severity, 0) + 1

    # Group by category
    issues_by_category = {}
    for issue in issues:
        issues_by_category[issue.category] = issues_by_category.get(issue.category, 0) + 1

    # Build summary
    parts = []
    if issues_by_severity["error"]:
        parts.append(f"{issues_by_severity['error']} error(s)")
    if issues_by_severity["warning"]:
        parts.append(f"{issues_by_severity['warning']} warning(s)")
    if issues_by_severity["info"]:
        parts.append(f"{issues_by_severity['info']} info")

    if parts:
        summary = f"Found {', '.join(parts)} across {len(issues_by_category)} category(ies)"
    else:
        summary = "URDF passed all validation checks"

    robot_name = tree.getroot().get("name", "unknown")

    return {
        "success": True,
        "file_path": file_path,
        "robot_name": robot_name,
        "total_issues": len(issues),
        "issues_by_severity": issues_by_severity,
        "issues_by_category": issues_by_category,
        "issues": [issue.to_dict() for issue in issues],
        "summary": summary,
    }
