"""
Isaac Lab Scene Loader — Code Generator

Reads a YAML scene description and generates a standalone Isaac Lab Python
script.  Only USD assets (.usd, .usda, .usdc, .usdz) are supported.

Usage:
    python isaac_scene_loader.py <scene.yaml> [output_script.py]

If output_script.py is omitted the generated script is written to
<yaml_stem>_isaac.py next to the YAML file.

See docs/isaac_sim_yaml_scene_format.md for the YAML format specification.
"""

# Robot support notes:
# Robots are loaded via isaaclab.assets.ArticulationCfg with a UsdFileCfg spawn config.
# Only name, usd_path, position, rotation, and end_effector_frame are supported.

import sys
import os
import yaml
import numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USD_EXTENSIONS = frozenset({".usd", ".usda", ".usdc", ".usdz"})


def _rotvec_deg_to_quat_wxyz(rotvec_deg: list) -> list:
    """Convert a rotation vector (degrees) to a quaternion [w, x, y, z].

    A zero vector maps to the identity quaternion [1, 0, 0, 0].
    """
    rotvec_rad = np.deg2rad(rotvec_deg)
    r = Rotation.from_rotvec(rotvec_rad)
    xyzw = r.as_quat()          # scipy convention: [x, y, z, w]
    return [float(xyzw[3]), float(xyzw[0]), float(xyzw[1]), float(xyzw[2])]


# ---------------------------------------------------------------------------
# Asset processing
# ---------------------------------------------------------------------------

def _process_assets(assets_config: list) -> list:
    """Validate and compute per-asset data for code generation.

    Returns a list of dicts:
        {
            name        : str,
            source_path : str,   # absolute path to the USD file
            position    : [x, y, z],
            quat_wxyz   : [w, x, y, z],
            scale       : [sx, sy, sz],
            physics     : bool,
        }
    """
    processed = []
    for asset in assets_config:
        name        = asset["name"]
        source_path = os.path.normpath(asset["file"])

        if not os.path.exists(source_path):
            raise FileNotFoundError(
                f"Asset '{name}': file not found: {source_path}"
            )

        ext = Path(source_path).suffix.lower()
        if ext not in _USD_EXTENSIONS:
            raise ValueError(
                f"Asset '{name}': unsupported format '{ext}'. "
                f"Only USD formats are supported: {sorted(_USD_EXTENSIONS)}"
            )

        position = [float(v) for v in asset.get("position", [0.0, 0.0, 0.0])]
        rotation = [float(v) for v in asset.get("rotation", [0.0, 0.0, 0.0])]
        scale    = [float(v) for v in asset.get("scale",    [1.0, 1.0, 1.0])]
        physics  = bool(asset.get("physics", False))
        pinned   = bool(asset.get("pinned",  False))

        processed.append({
            "name":        name,
            "source_path": source_path,
            "position":    position,
            "quat_wxyz":   _rotvec_deg_to_quat_wxyz(rotation),
            "scale":       scale,
            "physics":     physics,
            "pinned":      pinned,
        })

    return processed


# ---------------------------------------------------------------------------
# Robot processing
# ---------------------------------------------------------------------------

def _process_robots(robots_config: list) -> list:
    """Validate and compute per-robot data for code generation.

    Returns a list of dicts:
        {
            name               : str,
            source_path        : str,   # absolute path to the USD file
            position           : [x, y, z],
            quat_wxyz          : [w, x, y, z],
            end_effector_frame : str,
        }
    """
    processed = []
    for robot in robots_config:
        name        = robot["name"]
        source_path = os.path.normpath(robot["usd_path"])

        if not os.path.exists(source_path):
            raise FileNotFoundError(
                f"Robot '{name}': file not found: {source_path}"
            )

        ext = Path(source_path).suffix.lower()
        if ext not in _USD_EXTENSIONS:
            raise ValueError(
                f"Robot '{name}': unsupported format '{ext}'. "
                f"Only USD formats are supported: {sorted(_USD_EXTENSIONS)}"
            )

        position           = [float(v) for v in robot.get("position", [0.0, 0.0, 0.0])]
        rotation           = [float(v) for v in robot.get("rotation", [0.0, 0.0, 0.0])]
        end_effector_frame = robot["end_effector_frame"]
        fix_root           = bool(robot.get("fix_root", False))
        # prim_path overrides the default /World/{name}; useful for MJCF-converted
        # USDs where the articulation root is nested (e.g. /World/ur5e/worldBody).
        prim_path_override = robot.get("prim_path", None)

        processed.append({
            "name":               name,
            "source_path":        source_path,
            "position":           position,
            "quat_wxyz":          _rotvec_deg_to_quat_wxyz(rotation),
            "end_effector_frame": end_effector_frame,
            "fix_root":           fix_root,
            "prim_path_override": prim_path_override,
        })

    return processed


# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------

_PREAMBLE = '''\
#!/usr/bin/env python3
"""
Auto-generated Isaac Lab scene script.
Source YAML : {yaml_path}

Run with:
    ./isaaclab.sh -p {script_name}
"""

import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Auto-generated Isaac Lab scene.")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import isaaclab.sim as sim_utils                                       # noqa: E402
from isaaclab.assets import Articulation, ArticulationCfg              # noqa: E402
from isaaclab.actuators import ImplicitActuatorCfg                     # noqa: E402
import isaaclab.utils.math as math_utils                               # noqa: E402
'''

_SCENE_FUNC_HEADER = """\

# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------

def design_scene() -> dict:
    \"\"\"Build the scene and return a dict of named Articulation objects.\"\"\"
    return_vals = {}

    # Ground plane
    cfg_ground = sim_utils.GroundPlaneCfg()
    cfg_ground.func("/World/defaultGroundPlane", cfg_ground)

    # Distant light
    cfg_light = sim_utils.DistantLightCfg(intensity=3000.0, color=(0.75, 0.75, 0.75))
    cfg_light.func("/World/lightDistant", cfg_light, translation=(1, 0, 10))
"""

_MAIN_BLOCK = """\

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    sim_cfg = sim_utils.SimulationCfg(dt=0.01, device=args_cli.device)
    sim = sim_utils.SimulationContext(sim_cfg)
    sim.set_camera_view([2.0, 0.0, 2.5], [-0.5, 0.0, 0.5])

    scene_entities = design_scene()
    robots = {k: v for k, v in scene_entities.items() if isinstance(v, Articulation)}

    sim.reset()
    for robot in robots.values():
        robot.update(dt=0.0)
    print("[INFO]: Setup complete...")

    while simulation_app.is_running():
        sim.step()
        for robot in robots.values():
            robot.update(dt=sim_cfg.dt)


if __name__ == "__main__":
    main()
    simulation_app.close()
"""


def _fmt_tuple(vals: list) -> str:
    return ", ".join(str(v) for v in vals)


def _is_uniform_scale(scale: list) -> bool:
    return scale[0] == scale[1] == scale[2]


def _asset_block(asset: dict) -> str:
    """Generate spawning code for one asset."""
    name      = asset["name"]
    src       = asset["source_path"]
    pos       = asset["position"]
    q         = asset["quat_wxyz"]
    scale     = asset["scale"]
    physics   = asset["physics"]
    pinned    = asset["pinned"]
    prim_path = f"/World/{name}"

    lines = []
    lines.append(f"")
    if pinned:
        tag = "pinned"
    elif physics:
        tag = "physics"
    else:
        tag = "static"
    lines.append(f"    # {name}  ({tag})")

    # Build UsdFileCfg kwargs
    cfg_parts = [f'usd_path="{src}"']

    if _is_uniform_scale(scale) and scale[0] != 1.0:
        cfg_parts.append(f"scale={scale[0]}")

    if pinned:
        cfg_parts.append("rigid_props=sim_utils.RigidBodyPropertiesCfg(kinematic_enabled=True)")
        cfg_parts.append("collision_props=sim_utils.CollisionPropertiesCfg()")
    elif physics:
        cfg_parts.append("rigid_props=sim_utils.RigidBodyPropertiesCfg()")
        cfg_parts.append("mass_props=sim_utils.MassPropertiesCfg(mass=1.0)")
        cfg_parts.append("collision_props=sim_utils.CollisionPropertiesCfg()")

    cfg_args = ",\n        ".join(cfg_parts)
    lines.append(f"    cfg_{name} = sim_utils.UsdFileCfg(\n        {cfg_args},\n    )")

    # Spawn call
    orientation = f"({_fmt_tuple(q)})"
    translation = f"({_fmt_tuple(pos)})"
    lines.append(
        f'    cfg_{name}.func("{prim_path}", cfg_{name}, '
        f'translation={translation}, orientation={orientation})'
    )

    # Non-uniform scale requires post-spawn xform ops
    if not _is_uniform_scale(scale):
        lines.append(f"    # Non-uniform scale — applied via USD xform op")
        lines.append(f"    from pxr import UsdGeom, Gf  # noqa: E402")
        lines.append(f'    _xform = UsdGeom.Xformable(sim_utils.find_first_matching_prim("{prim_path}"))')
        lines.append(f"    _xform.AddScaleOp().Set(Gf.Vec3d({_fmt_tuple(scale)}))")

    return "\n".join(lines)


def _robot_block(robot: dict) -> str:
    """Generate spawning and registration code for one robot."""
    name      = robot["name"]
    src       = robot["source_path"]
    pos       = robot["position"]
    q         = robot["quat_wxyz"]
    ee_frame  = robot["end_effector_frame"]
    fix_root          = robot["fix_root"]
    prim_path_override = robot["prim_path_override"]
    prim_path = prim_path_override if prim_path_override else f"/World/{name}"

    var = f"robot_{name}"

    lines = [
        f"",
        f"    # {name}  (articulation, ee_frame='{ee_frame}')",
    ]
    if fix_root:
        lines.append(f"    # fix_root=True: USD must be converted with --fix-base (fix_root_link is not set here)")
    lines += [
        f"    {var}_cfg = ArticulationCfg(",
        f'        prim_path="{prim_path}",',
        f"        spawn=sim_utils.UsdFileCfg(",
        f'            usd_path="{src}",',
        f"            rigid_props=sim_utils.RigidBodyPropertiesCfg(",
        f"                rigid_body_enabled=True,",
        f"                max_linear_velocity=1000.0,",
        f"                max_angular_velocity=1000.0,",
        f"                max_depenetration_velocity=100.0,",
        f"                enable_gyroscopic_forces=True,",
        f"            ),",
        f"            articulation_props=sim_utils.ArticulationRootPropertiesCfg(",
        f"                enabled_self_collisions=False,",
        f"                solver_position_iteration_count=4,",
        f"                solver_velocity_iteration_count=0,",
    ]
    lines += [
        f"            ),",
        f"        ),",
        f"        init_state=ArticulationCfg.InitialStateCfg(",
        f"            pos=({_fmt_tuple(pos)},),",
        f"            rot=({_fmt_tuple(q)},),",
        f"        ),",
        f"        actuators={{",
        f'            "all_joints": ImplicitActuatorCfg(',
        f'                joint_names_expr=[".*"],',
        f"                stiffness=1000.0,",
        f"                damping=0.1,",
        f"            ),",
        f"        }},",
        f"    )",
        f"    {var} = Articulation(cfg={var}_cfg)",
        f"    # End-effector frame: '{ee_frame}'",
        f"    # Access via: {var}.find_bodies('{ee_frame}')",
        f"    return_vals['{name}'] = {var}",
    ]

    return "\n".join(lines)


def _generate_script(
    processed_assets: list,
    processed_robots: list,
    output_path: str,
    yaml_path: str,
) -> None:
    """Assemble and write the standalone Isaac Lab Python script."""
    script_name = os.path.basename(output_path)

    parts = [
        _PREAMBLE.format(yaml_path=yaml_path, script_name=script_name),
        _SCENE_FUNC_HEADER,
    ]

    for robot in processed_robots:
        parts.append(_robot_block(robot))

    for asset in processed_assets:
        parts.append(_asset_block(asset))

    parts.append("\n    return return_vals")  # close design_scene()
    parts.append("")  # blank line before main
    parts.append(_MAIN_BLOCK)

    with open(output_path, "w") as fh:
        fh.write("\n".join(parts))

    print(f"Generated: {output_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <scene.yaml> [output_script.py]")
        sys.exit(1)

    yaml_path = os.path.abspath(sys.argv[1])
    if not os.path.exists(yaml_path):
        print(f"Error: YAML not found: {yaml_path}", file=sys.stderr)
        sys.exit(1)

    yaml_dir  = os.path.dirname(yaml_path)
    yaml_stem = Path(yaml_path).stem

    output_path = (
        os.path.abspath(sys.argv[2])
        if len(sys.argv) >= 3
        else os.path.join(yaml_dir, f"{yaml_stem}_isaac.py")
    )

    print(f"Scene YAML : {yaml_path}")
    print(f"Output     : {output_path}")

    with open(yaml_path) as fh:
        scene_data = yaml.safe_load(fh)

    robots_config = scene_data.get("scene", {}).get("robots", [])
    assets_config = scene_data.get("scene", {}).get("assets", [])

    if not robots_config and not assets_config:
        print("Warning: no robots or assets found under scene — generating empty scene.")

    processed_robots = _process_robots(robots_config)
    processed_assets = _process_assets(assets_config)
    _generate_script(processed_assets, processed_robots, output_path, yaml_path)


if __name__ == "__main__":
    main()
