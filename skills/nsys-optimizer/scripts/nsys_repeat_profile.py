#!/usr/bin/env python3
"""Profile a command multiple times with nsys, saving reports to a temp directory.

Usage:
    python nsys_repeat_profile.py --cmd "python examples/scene.py" \
        --label baseline --runs 10 --outdir /tmp/nsys_ab

    python nsys_repeat_profile.py --cmd "python examples/scene_optimized.py" \
        --label optimized --runs 10 --outdir /tmp/nsys_ab

Reports are saved as <outdir>/<label>/run_00.nsys-rep, run_01.nsys-rep, etc.
SQLite exports are generated alongside each .nsys-rep for later analysis.
"""

import argparse
import os
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(
        description="Run nsys profile multiple times for statistical profiling."
    )
    parser.add_argument(
        "--cmd", required=True, help="Command to profile (quoted string)."
    )
    parser.add_argument(
        "--label",
        required=True,
        help="Label for this condition (e.g. 'baseline', 'optimized').",
    )
    parser.add_argument(
        "--runs", type=int, default=10, help="Number of profiling runs (default: 10)."
    )
    parser.add_argument(
        "--outdir",
        default="/tmp/nsys_ab",
        help="Output directory (default: /tmp/nsys_ab).",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Number of warmup runs before profiling (default: 1).",
    )
    parser.add_argument(
        "--nsys-extra",
        default="",
        help="Extra flags to pass to nsys profile (e.g. '--trace=cuda').",
    )
    args = parser.parse_args()

    label_dir = os.path.join(args.outdir, args.label)
    os.makedirs(label_dir, exist_ok=True)

    env = os.environ.copy()
    env["DISPLAY"] = ""  # Force headless

    # Warmup runs (not profiled)
    for i in range(args.warmup):
        print(f"[warmup {i + 1}/{args.warmup}] {args.cmd}")
        subprocess.run(args.cmd, shell=True, env=env, capture_output=True)

    # Profiling runs
    for i in range(args.runs):
        report_path = os.path.join(label_dir, f"run_{i:02d}")
        nsys_cmd = (
            f"nsys profile --stats=false -o {report_path} -f true "
            f"{args.nsys_extra} {args.cmd}"
        )
        print(f"[run {i + 1}/{args.runs}] profiling -> {report_path}.nsys-rep")
        t0 = time.time()
        result = subprocess.run(
            nsys_cmd, shell=True, env=env, capture_output=True, text=True
        )
        elapsed = time.time() - t0

        if result.returncode != 0:
            print(f"  ERROR (exit {result.returncode}):")
            print(result.stderr[-500:] if result.stderr else "(no stderr)")
            sys.exit(1)

        # Export to SQLite for analysis
        nsys_rep_path = f"{report_path}.nsys-rep"
        sqlite_path = f"{report_path}.sqlite"
        export_cmd = (
            f"nsys export --type=sqlite -o {sqlite_path} "
            f"--force-overwrite true {nsys_rep_path}"
        )
        subprocess.run(export_cmd, shell=True, capture_output=True)

        print(f"  done in {elapsed:.1f}s")

    print(f"\nAll {args.runs} runs saved to {label_dir}/")
    print(f"Run nsys_compare.py to analyze results.")


if __name__ == "__main__":
    main()
