---
name: Isaac Lab Scene Initializer
description: >
  Guides users through authoring or extending an Isaac Lab/Isaac Sim YAML scene file (robots,
  assets, positions, physics) and generates the ready-to-run `*_isaac.py` script via the
  bundled `isaac_scene_loader.py`. Use this skill whenever the user wants to set up a virtual
  robot lab scene in Isaac Sim, add or configure robots/assets in Isaac Lab, generate an Isaac
  Lab Python script from a YAML description, initialise a new simulation environment, or load
  USD models into an Isaac Sim stage — even if they don't say "YAML" or "Isaac Lab" explicitly.
---

# Isaac Lab Scene Initializer

Guides the user from a blank slate (or partial YAML) to a validated, ready-to-run Isaac Lab
Python script. The bundled `scripts/isaac_scene_loader.py` handles all code generation.

---

## Workflow

### Phase 1 — Understand the Scene

If the user has an existing YAML, read it first and summarise what's already there.

Otherwise, ask the user (briefly — not all at once):
- Which robots? For each: USD path, position `[x, y, z]` (metres), end-effector frame name.
  Optional: `rotation`, `fix_root`, `prim_path` override.
- Which assets (lab furniture, containers, etc.)? For each: USD path, position, `scale`.
  Should the object be a static visual, a physics object (`physics: true`), or fixed-in-place
  with a collider (`pinned: true`)?
- Desired output script name (default: `<yaml_stem>_isaac.py` next to the YAML).

You do not need to have all answers before proceeding — draft the YAML with what you know and
flag missing fields clearly with `# TODO` comments.

---

### Phase 2 — Author / Extend the YAML

Write or update the YAML following this structure:

```yaml
scene:
  robots:
    - name: "robot_name"              # unique identifier, used as USD prim name
      usd_path: "/abs/path/robot.usd" # .usd / .usda / .usdc / .usdz only
      position: [x, y, z]             # metres, default [0, 0, 0]
      rotation: [rx, ry, rz]          # rotation vector (axis-angle) in degrees, default [0,0,0]
      end_effector_frame: "tool0"     # body/link name for the end-effector
      fix_root: false                 # optional; set true if USD was converted with --fix-base
      prim_path: "/World/name/root"   # optional; override default /World/{name}

  assets:
    - name: "asset_name"              # unique identifier
      file: "/abs/path/model.usd"
      position: [x, y, z]
      rotation: [rx, ry, rz]         # rotation vector, degrees
      scale: [sx, sy, sz]            # default [1, 1, 1]
      physics: false                 # true → rigid body + collision + mass=1 kg
      pinned: false                  # true → kinematic (fixed) + collision, no mass
```

**Rotation convention** — rotation vector (axis-angle), identical to Blender:
- `[0, 0, 0]` → identity
- `[0, 0, 90]` → 90° around Z
- `[45, 0, 0]` → 45° around X

**Scale** — uniform scale (all three equal) is passed to `UsdFileCfg(scale=…)`. Non-uniform
scale is applied via a USD xform op after spawning.

**`physics` vs `pinned`** — do not set both to `true` on the same asset (kinematic bodies
ignore forces, so adding mass/rigid props is contradictory). Flag this to the user.

Always output the **complete** YAML, not a partial diff.

---

### Phase 3 — Validate

Before running the generator, check the YAML for these issues. Report all problems found and
fix them (or ask the user) before proceeding:

| Check | What to verify |
|---|---|
| Required fields | Each robot has `name`, `usd_path`, `end_effector_frame`. Each asset has `name`, `file`. |
| File existence | Every `usd_path` / `file` path exists on disk (`os.path.exists`). Resolve relative paths from the YAML's directory. |
| USD extension | Extension is one of `.usd`, `.usda`, `.usdc`, `.usdz`. |
| Unique names | No two robots share a name; no two assets share a name. |
| Physics conflict | An asset must not have both `physics: true` and `pinned: true`. |
| Non-empty scene | At least one robot or asset is present (warn only — empty scenes are allowed). |

If all checks pass, tell the user "Validation passed — generating script." and continue.
If any check fails, list the problems clearly and wait for the user to resolve them before
running the generator.

---

### Phase 4 — Generate

Run the bundled script:

```bash
python /home/kennychufk/workspace/pythonWs/MatClaw/skills/isaac-lab-scene-init/scripts/isaac_scene_loader.py \
    <yaml_path> [output_script.py]
```

- If `output_script.py` is omitted the generator writes `<yaml_stem>_isaac.py` next to the
  YAML file.
- The script resolves all paths to absolute form and pre-computes quaternions internally —
  no post-processing needed.

After the generator prints `Generated: <path>`, tell the user the output path and remind them
how to run the result inside Isaac Lab:

```bash
./isaaclab.sh -p <output_script.py>
```

---

## Quick Field Reference

### Robot fields

| Field | Required | Default | Notes |
|---|---|---|---|
| `name` | Yes | — | Used as USD prim name under `/World/` |
| `usd_path` | Yes | — | Absolute or relative path to USD |
| `position` | No | `[0,0,0]` | Metres |
| `rotation` | No | `[0,0,0]` | Rotation vector, degrees |
| `end_effector_frame` | Yes | — | Body name; query at runtime via `robot.find_bodies(name)` |
| `fix_root` | No | `false` | USD converted with `--fix-base`; noted in generated comments |
| `prim_path` | No | `/World/{name}` | Use for MJCF-converted USDs with nested roots |

### Asset fields

| Field | Required | Default | Notes |
|---|---|---|---|
| `name` | Yes | — | |
| `file` | Yes | — | USD path |
| `position` | No | `[0,0,0]` | Metres |
| `rotation` | No | `[0,0,0]` | Rotation vector, degrees |
| `scale` | No | `[1,1,1]` | Uniform or non-uniform |
| `physics` | No | `false` | Rigid body + collision + 1 kg mass |
| `pinned` | No | `false` | Kinematic (fixed) + collision, no mass |

---

## Common Pitfalls

- **Relative paths** — `isaac_scene_loader.py` resolves paths from the process working
  directory, not the YAML location. Use absolute paths or run the script from the YAML's
  directory.
- **MJCF-converted robots** — the articulation root is often nested (e.g.
  `/World/ur5e/worldBody`). Use `prim_path` to point at it explicitly.
- **`fix_root` is informational** — it adds a comment in the generated script. The USD
  itself must have been converted with `--fix-base`; this flag doesn't alter the spawning
  code.
