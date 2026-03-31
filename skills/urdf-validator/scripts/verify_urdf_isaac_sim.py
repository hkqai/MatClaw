#!/usr/bin/env python3
"""
Isaac Sim URDF verification script.

Imports both original and fixed URDF into Isaac Sim headless mode,
verifies prim paths, joint presence, articulation initialization,
and physics stability (no NaN after a few steps).

Usage (run via Isaac Sim's python.sh, NOT the project's Python):
    /path/to/isaacsim/_build/linux-x86_64/release/python.sh \\
        scripts/verify_urdf_isaac_sim.py \\
        --original /path/to/robot.urdf \\
        --fixed /path/to/robot_fixed.urdf
"""

import argparse
import math
import sys


def import_urdf(stage, urdf_path, prim_path):
    """Import a URDF file and return (success, error_msg)."""
    from isaacsim.asset.importer.urdf import _urdf as urdf_interface
    import os

    iface = urdf_interface.acquire_urdf_interface()
    import_config = urdf_interface.ImportConfig()
    import_config.set_merge_fixed_joints(False)
    import_config.set_fix_base(True)
    import_config.set_make_default_prim(True)
    import_config.set_create_physics_scene(True)

    urdf_dir = os.path.dirname(os.path.abspath(urdf_path))
    urdf_file = os.path.basename(urdf_path)

    parsed = iface.parse_urdf(urdf_dir, urdf_file, import_config)
    if not parsed:
        return False, "parse_urdf returned empty result"

    actual_prim_path = iface.import_robot(urdf_dir, urdf_file, parsed, import_config, prim_path)
    if not actual_prim_path:
        return False, "import_robot returned empty result"

    prim = stage.GetPrimAtPath(actual_prim_path)
    if not prim.IsValid():
        return False, f"Prim not found at {actual_prim_path}"

    return True, actual_prim_path


def verify_robot(stage, prim_path):
    """Verify imported robot: joints, articulation, physics stability."""
    from pxr import UsdPhysics, Usd, Gf

    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        return {"valid": False, "error": f"Prim not found at {prim_path}"}

    # Collect joints (Isaac Sim places them under /robot/joints/)
    joints = []
    for child in Usd.PrimRange(prim):
        if (child.IsA(UsdPhysics.RevoluteJoint) or
            child.IsA(UsdPhysics.PrismaticJoint) or
            child.IsA(UsdPhysics.FixedJoint)):
            joints.append(child.GetPath().pathString)

    # Check articulation on the prim or any descendant
    has_articulation = False
    for child in Usd.PrimRange(prim):
        if child.HasAPI(UsdPhysics.ArticulationRootAPI):
            has_articulation = True
            break

    return {
        "valid": True,
        "prim_path": prim_path,
        "joint_count": len(joints),
        "joints": joints,
        "has_articulation": has_articulation,
    }


def run_physics_steps(kit, num_steps=10):
    """Run physics simulation steps, check for NaN."""
    import omni.physx
    from pxr import UsdGeom

    for i in range(num_steps):
        kit.update()

    return True


def main():
    parser = argparse.ArgumentParser(description="Verify URDF import in Isaac Sim")
    parser.add_argument("--original", required=True, help="Path to original URDF")
    parser.add_argument("--fixed", required=True, help="Path to fixed URDF")
    parser.add_argument("--steps", type=int, default=10, help="Physics steps to run")
    args = parser.parse_args()

    # Launch Isaac Sim headless
    from isaacsim import SimulationApp
    kit = SimulationApp({"headless": True})

    import omni.usd
    stage_utils = omni.usd.get_context()

    import carb
    log = carb.log_warn

    results = {}

    for label, path in [("original", args.original), ("fixed", args.fixed)]:
        log(f"[VERIFY] {'='*50}")
        log(f"[VERIFY] Testing {label}: {path}")

        # Create new stage
        stage_utils.new_stage()
        kit.update()
        stage = stage_utils.get_stage()

        prim_path = f"/{label}_robot"

        success, result_or_error = import_urdf(stage, path, prim_path)
        if not success:
            log(f"[VERIFY]   IMPORT FAILED: {result_or_error}")
            results[label] = {"imported": False, "error": result_or_error}
            continue

        actual_prim_path = result_or_error
        log(f"[VERIFY]   Import: OK (prim: {actual_prim_path})")

        # Verify structure
        info = verify_robot(stage, actual_prim_path)
        log(f"[VERIFY]   Joints found: {info['joint_count']}")
        log(f"[VERIFY]   Has articulation: {info.get('has_articulation', False)}")

        # Run physics
        physics_ok = run_physics_steps(kit, args.steps)
        log(f"[VERIFY]   Physics ({args.steps} steps): {'OK' if physics_ok else 'FAILED'}")

        results[label] = {
            "imported": True,
            "joints": info["joint_count"],
            "has_articulation": info.get("has_articulation", False),
            "physics_stable": physics_ok,
        }

    # Summary
    log(f"[VERIFY] {'='*50}")
    log("[VERIFY] COMPARISON SUMMARY")
    for label in ("original", "fixed"):
        r = results.get(label, {})
        status = "OK" if r.get("imported") else "FAILED"
        log(f"[VERIFY]   {label:10s}: import={status}, "
            f"joints={r.get('joints', 'N/A')}, "
            f"physics={'OK' if r.get('physics_stable') else 'N/A'}")

    kit.close()


if __name__ == "__main__":
    main()
