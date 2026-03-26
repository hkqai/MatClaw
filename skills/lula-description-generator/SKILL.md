---
name: lula-description-generator
description: Generates Lula robot description YAML from a URDF file for Isaac Sim motion planning (CuMotion/RMPflow/Lula), including automatic collision sphere generation via mesh repair + voxelisation + medial-axis sphere packing
---
# Lula Robot Description Generator

Generates Lula robot description YAML files from URDF files for use with
Isaac Sim's CuMotion / RMPflow / Lula motion planning backends.

## What this skill does

A Lula description file configures:
- **C-space** — the joints the motion planner directly controls
- **Default joint positions** — home configuration
- **Acceleration & jerk limits** — per-joint motion constraints
- **C-space-to-URDF rules** — how joints outside the c-space are handled
- **Collision spheres** — per-link convex approximations for obstacle avoidance

The collision spheres are the hardest part to create manually.
Isaac Sim's built-in sphere generator frequently fails on non-watertight meshes.
This skill automates sphere generation using:
1. Mesh repair (pymeshfix → trimesh fallback)
2. Voxelisation of the mesh interior
3. Euclidean distance transform (voxel value = distance to nearest surface)
4. Greedy medial-axis sphere packing

## MCP tool

```
lula_generate_robot_description(
    urdf_path,               # absolute path to URDF
    output_path=None,        # defaults to <urdf_dir>/<name>_lula_description.yaml
    mesh_search_paths=None,  # extra dirs for mesh resolution (incl. package:// URIs)
    controlled_joint_names=None,  # explicit cspace list; auto-detected if omitted
    max_spheres_per_link=16, # 8–32 is typical; more = tighter fit but slower planning
    voxel_fraction=0.04,     # 4% of max bounding-box dim; lower = finer but slower
    skip_sphere_links=None,  # links to exclude from sphere generation (virtual frames)
)
```

Returns: `success`, `output_path`, `cspace`, `num_links_with_spheres`,
`total_spheres`, `warnings`, `summary`.

## Standard workflow

### Phase 1 — Inspect the URDF

Use `urdf_inspect` to understand the robot structure before generating:
- How many links and joints?
- Which joints are controllable (revolute/prismatic/continuous)?
- Are there gripper/finger joints separate from the arm?
- Are mesh paths resolvable (`package://` URIs need search paths)?

### Phase 2 — Decide the c-space

For manipulator arms, the c-space is typically the arm joints only
(NOT gripper fingers). Gripper joints should appear in `cspace_to_urdf_rules`
as `fixed` entries.

**Example: UR5e** — c-space is 6 revolute joints:
```
controlled_joint_names=["shoulder_pan_joint", "shoulder_lift_joint",
                        "elbow_joint", "wrist_1_joint",
                        "wrist_2_joint", "wrist_3_joint"]
```

**Example: Piper** — 6-DOF arm (joint1–joint6); gripper joints (joint7, joint8)
go in `cspace_to_urdf_rules`:
```
controlled_joint_names=["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
```

When `controlled_joint_names` is omitted, ALL non-fixed joints are included.

### Phase 3 — Resolve mesh paths

If the URDF uses `package://` URIs, provide `mesh_search_paths` pointing to
the directory that contains the package folder. For example:

```
URDF: package://piper_description/meshes/base_link.STL
workspace: /home/user/ws/piper_isaac_sim/
→ mesh_search_paths=["/home/user/ws/piper_isaac_sim"]
```

For relative mesh paths (e.g. UR5e), the URDF directory is searched
automatically — no `mesh_search_paths` needed.

### Phase 4 — Generate

```python
result = lula_generate_robot_description(
    urdf_path="/abs/path/to/robot.urdf",
    controlled_joint_names=[...],
    mesh_search_paths=[...],   # only if needed
    max_spheres_per_link=16,
)
```

Check `result["warnings"]` for any links where sphere generation failed or
meshes could not be found. These links will be absent from `collision_spheres`.

### Phase 5 — Review & tune

Open the generated YAML and verify:

1. **C-space**: correct joints listed?
2. **default_q**: sensible home position? Zeros are usually fine for upright configs.
3. **acceleration/jerk limits**: generated as heuristic (5× and 2500× velocity
   limit). Tune for your robot's real specs if needed.
4. **collision_spheres**: visually inspect in Isaac Sim's Robot Description Editor
   (`Tools → Robotics → Lula Robot Description Editor`) — load the YAML and use
   the 3D viewport to verify coverage.

Common tuning knobs:
- Increase `max_spheres_per_link` (e.g. 24–32) for better coverage on complex links.
- Decrease `voxel_fraction` (e.g. 0.02) for finer mesh sampling on thin geometry.
- Add problematic links to `skip_sphere_links` and hand-author their spheres if
  the automatic result is poor.

## Known limitations & pitfalls

- **Mesh repair** repairs topology but may slightly alter geometry. Sphere centres
  reflect the repaired mesh, which is usually fine for collision purposes.
- **Concave links** (e.g. U-shaped brackets) require more spheres for good coverage.
  The medial-axis packing naturally handles concave shapes but may need
  `max_spheres_per_link ≥ 24`.
- **package:// URIs** without a matching search path will silently skip sphere
  generation for those links. Always check `warnings`.
- **Very small links** (e.g. sensor frames, fingertips < 1 cm) may produce only
  1–2 spheres. This is usually fine.
- **YAML heuristic limits**: `acceleration_limits` and `jerk_limits` are
  heuristic estimates. For production use, replace with values from the robot
  datasheet or identify them via system identification.

## Output format

```yaml
api_version: 1.0

cspace:
  - joint1
  - joint2

default_q: [0.0, 0.0]

acceleration_limits: [15.0, 10.0]
jerk_limits: [7500.0, 5000.0]

cspace_to_urdf_rules:
  - {name: finger_joint, rule: fixed, value: 0.0}

collision_spheres:
  - base_link:
    - center: [0.0, 0.0, 0.05]
      radius: 0.047
  - link1:
    - center: [0.0, 0.0, 0.1]
      radius: 0.04
```

## Loading into Isaac Sim

1. Import your URDF via `File → Import → URDF`
2. Open `Tools → Robotics → Lula Robot Description Editor`
3. Load the generated YAML
4. Inspect collision spheres in the 3D viewport
5. Re-export once satisfied (YAML or XRDF format)

## Backlog / future improvements

- Support for MJCF input format
- Auto-detection of mimic joints for `cspace_to_urdf_rules`
- Sphere quality scoring and iterative refinement
- Direct XRDF output format
