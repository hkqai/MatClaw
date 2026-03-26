"""
MCP tool: lula_generate_robot_description

Generates a Lula robot description YAML from a URDF file for use with
Isaac Sim's motion planning backends (CuMotion / RMPflow / Lula).

The most labour-intensive part of creating a Lula description — the
collision spheres — is automated here via:
  1. Mesh loading (STL, DAE, OBJ, or URDF primitives box/cylinder/sphere)
  2. Mesh repair to watertight (pymeshfix if available, then trimesh fallback)
  3. Voxelisation of the mesh interior
  4. Euclidean distance transform (each interior voxel = distance to surface)
  5. Greedy sphere packing along the medial axis

Dependencies (install into the venv):
    pip install trimesh scipy
    pip install pymeshfix   # optional, improves mesh repair quality
"""

from typing import Any, Dict, List, Optional, Annotated
from pydantic import Field

from ._lula_core import generate_lula_robot_description as _generate


def lula_generate_robot_description(
    urdf_path: Annotated[
        str,
        Field(description="Absolute path to the URDF file to convert."),
    ],
    output_path: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "Where to write the Lula description YAML. "
                "Defaults to <urdf_basename>_lula_description.yaml in the same directory."
            ),
        ),
    ] = None,
    mesh_search_paths: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description=(
                "Extra directories to search when resolving mesh filenames "
                "(including package:// URIs). The URDF directory is always tried first."
            ),
        ),
    ] = None,
    controlled_joint_names: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description=(
                "Explicit list of joint names to include in the Lula c-space "
                "(the joints the motion planner directly controls). "
                "When omitted, all non-fixed joints are used."
            ),
        ),
    ] = None,
    max_spheres_per_link: Annotated[
        int,
        Field(
            default=16,
            ge=1,
            le=64,
            description=(
                "Maximum number of collision spheres to generate per link. "
                "More spheres give tighter coverage but increase planning time."
            ),
        ),
    ] = 16,
    voxel_fraction: Annotated[
        float,
        Field(
            default=0.04,
            gt=0.0,
            le=0.5,
            description=(
                "Voxel size as a fraction of the link's largest bounding-box "
                "dimension. Smaller values give finer resolution (slower, more "
                "spheres). 0.04 (4 %%) is a good starting point."
            ),
        ),
    ] = 0.04,
    skip_sphere_links: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description=(
                "Link names to exclude from sphere generation "
                "(e.g. virtual frames or world links with no geometry)."
            ),
        ),
    ] = None,
) -> Dict[str, Any]:
    """
    Generate a Lula robot description YAML file from a URDF.

    Creates the configuration file required by Isaac Sim's Lula / CuMotion
    motion planners:
      - c-space definition (controlled joints)
      - default joint positions
      - per-joint acceleration and jerk limits (heuristic; tune as needed)
      - c-space-to-URDF rules for joints outside the c-space
      - per-link collision spheres (generated automatically)

    Collision spheres are built using voxelisation and a distance-transform
    medial-axis greedy packing strategy, which reliably handles non-watertight
    meshes by first repairing them with pymeshfix (if installed) or trimesh.

    Returns:
        dict with keys:
            success (bool)
            output_path (str): path to the written YAML
            robot_name (str)
            cspace (list[str]): joint names in the c-space
            num_controllable_joints (int)
            num_links_with_spheres (int)
            total_spheres (int)
            warnings (list[str]): non-fatal issues encountered
            summary (str): human-readable summary
            error (str): present only on failure
    """
    return _generate(
        urdf_path=urdf_path,
        output_path=output_path,
        mesh_search_paths=mesh_search_paths,
        controlled_joint_names=controlled_joint_names,
        max_spheres_per_link=max_spheres_per_link,
        voxel_fraction=voxel_fraction,
        skip_sphere_links=skip_sphere_links,
    )
