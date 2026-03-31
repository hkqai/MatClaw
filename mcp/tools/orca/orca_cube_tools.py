"""
ORCA cube-generation and environment tools for MCP workflows and skills.

This module contains environment-sensitive utilities for ORCA cube generation.
Unlike the analysis module, this file is intentionally responsible for:
- checking executable availability
- checking directory writability
- matching `.gbw` files
- calling `orca_plot`
- generating MO, electron-density, and ESP cube files

Primary capabilities:
- Validate host environment for cube-generation workflows
- Validate whether a calculation directory looks safe for cube generation
- Match `.gbw` files to selected ORCA outputs
- Generate specific molecular orbital cube files
- Generate HOMO/LUMO cube files from a selected calculation
- Generate matched electron-density and ESP cube files
- Validate density/ESP grid consistency

Design conventions:
- Public functions return dictionaries with a boolean `success` field
- Fatal user-facing issues are returned as structured `error` fields
- Non-fatal reliability concerns are returned in a `warnings` list
- External program calls are wrapped in structured subprocess helpers
- File writes, renames, and deletions are handled defensively

Recommended usage with MCP and skills:
1. Call `validate_environment()` before any cube-generation workflow.
2. Call `validate_orca_calc_dir()` before selecting outputs or GBW files.
3. Prefer `generate_homo_lumo_cubes()` or `generate_density_and_esp_cubes()`
   over lower-level helpers unless the workflow truly needs granular control.
4. Always inspect `warnings` before presenting generated cubes as fully reliable.

Important limitations:
- Cube generation depends on version-sensitive `orca_plot -i` menu behavior.
- Correctness depends on correct `.gbw` matching.
- Writable access to the calculation directory is required.
- Windows is not a primary target environment.
- These tools are designed for Linux/HPC-style environments first.

This module depends on the analysis module for output-file selection and
frontier-orbital extraction logic.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .orca_analysis_tools import (
    _merge_warnings,
    extract_homo_lumo,
    pick_orca_output,
)


DEFAULT_SUBPROCESS_TIMEOUT = 15
DEFAULT_MODULE_NAME = os.environ.get("ORCA_MODULE_NAME", "orca")
SUPPORTED_ORCA_MENU_NOTE = (
    "Cube-generation logic depends on version-sensitive interactive "
    "orca_plot menu behavior."
)


def _safe_unlink(path: Path) -> Tuple[bool, Optional[str]]:
    """Safely delete a file if it exists.

    This helper is internal and is used to avoid uncaught filesystem errors
    during output-file replacement.

    Args:
        path:
            File path to remove.

    Returns:
        Tuple of:
        - success flag
        - error message or None
    """
    try:
        if path.exists():
            path.unlink()
        return True, None
    except Exception as e:
        return False, f"Failed to remove existing file '{path}': {e}"


def _safe_rename(src: Path, dst: Path) -> Tuple[bool, Optional[str]]:
    """Safely rename a file.

    This helper is internal and is used when normalizing generated cube-file
    names into stable, workflow-friendly names.

    Args:
        src:
            Source file path.
        dst:
            Destination file path.

    Returns:
        Tuple of:
        - success flag
        - error message or None
    """
    try:
        src.rename(dst)
        return True, None
    except Exception as e:
        return False, f"Failed to rename '{src}' -> '{dst}': {e}"


def _parse_ngrid(ngrid: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Validate and normalize an ngrid string for `orca_plot` workflows.

    Expected format is three positive integers separated by spaces, such as:
    `80 80 80`.

    Args:
        ngrid:
            User-provided grid specification.

    Returns:
        Tuple of:
        - success flag
        - normalized grid string or None
        - error message or None
    """
    parts = ngrid.split()
    if len(parts) != 3:
        return False, None, "ngrid must contain exactly three integers, e.g. '80 80 80'"
    try:
        values = [int(x) for x in parts]
    except Exception:
        return False, None, "ngrid must contain exactly three integers, e.g. '80 80 80'"

    if any(v <= 0 for v in values):
        return False, None, "ngrid values must all be positive integers"

    normalized = f"{values[0]} {values[1]} {values[2]}"
    return True, normalized, None


def _check_dir_writable(path: Path) -> Tuple[bool, Optional[str]]:
    """Check whether a directory appears writable.

    This helper is internal and is used before workflows that need to create,
    rename, or delete files in a calculation directory.

    Args:
        path:
            Directory path to test.

    Returns:
        Tuple of:
        - writable flag
        - error message or None
    """
    if not path.exists() or not path.is_dir():
        return False, f"Directory does not exist or is not a directory: {path}"
    try:
        with tempfile.NamedTemporaryFile(dir=str(path), delete=True):
            pass
        return True, None
    except Exception as e:
        return False, f"Directory is not writable: {path} ({e})"


def _run_subprocess(
    args: List[str],
    *,
    input_text: Optional[str] = None,
    cwd: Optional[str] = None,
    timeout: int = DEFAULT_SUBPROCESS_TIMEOUT,
) -> Dict[str, Any]:
    """Run a subprocess and capture stdout in a structured dictionary.

    This helper is internal. It makes subprocess behavior easier to integrate
    into MCP workflows by returning structured results rather than exposing
    raw exceptions where practical.

    Args:
        args:
            Command-line argument list.
        input_text:
            Optional text to pass to stdin.
        cwd:
            Optional working directory.
        timeout:
            Timeout in seconds.

    Returns:
        Dictionary containing:
        - success
        - returncode (when available)
        - stdout
        - args
        - cwd
        - timeout_seconds
        - error (on failure)
    """
    try:
        proc = subprocess.run(
            args,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            check=False,
            timeout=timeout,
        )
        return {
            "success": True,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "args": args,
            "cwd": cwd,
            "timeout_seconds": timeout,
        }
    except subprocess.TimeoutExpired as e:
        partial = ""
        if e.stdout:
            partial = e.stdout if isinstance(e.stdout, str) else str(e.stdout)
        return {
            "success": False,
            "error": f"Subprocess timed out after {timeout} seconds",
            "stdout": partial,
            "args": args,
            "cwd": cwd,
            "timeout_seconds": timeout,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to execute subprocess {args}: {e}",
            "args": args,
            "cwd": cwd,
            "timeout_seconds": timeout,
        }


def _find_executable(explicit_env_var: str, command_name: str) -> str:
    """Resolve an executable from env var, PATH, or a module-loaded shell.

    This helper is internal and primarily used for finding `orca_plot`.

    Resolution order:
    1. Explicit environment variable, such as `ORCA_PLOT`
    2. PATH lookup
    3. `bash -lc` with module-based fallback

    Args:
        explicit_env_var:
            Environment variable that may explicitly point to the executable.
        command_name:
            Executable name to search for.

    Returns:
        Absolute path to the resolved executable.

    Raises:
        RuntimeError:
            If the executable cannot be found or is not executable.

    Notes:
    - The module-based fallback is HPC-oriented and not guaranteed to work on
      all systems.
    - This helper is intentionally strict because downstream cube generation
      cannot proceed without a valid executable.
    """
    env_value = os.environ.get(explicit_env_var, "").strip()
    if env_value:
        p = Path(env_value).expanduser().resolve()
        if p.exists() and p.is_file() and os.access(p, os.X_OK):
            return str(p)
        raise RuntimeError(f"{explicit_env_var} is set but not executable: {p}")

    found = shutil.which(command_name)
    if found:
        p = Path(found).expanduser().resolve()
        if p.exists() and p.is_file() and os.access(p, os.X_OK):
            return str(p)

    bash_path = shutil.which("bash")
    if bash_path is not None:
        module_name = os.environ.get("ORCA_MODULE_NAME", DEFAULT_MODULE_NAME).strip() or DEFAULT_MODULE_NAME
        cmd = (
            f"type module >/dev/null 2>&1 && "
            f"module load {module_name} >/dev/null 2>&1; "
            f"command -v {command_name}"
        )
        proc = _run_subprocess([bash_path, "-lc", cmd], timeout=8)
        if proc.get("success"):
            found2 = (proc.get("stdout") or "").strip().splitlines()
            if found2:
                candidate = found2[-1].strip()
                if candidate:
                    p2 = Path(candidate).expanduser().resolve()
                    if p2.exists() and p2.is_file() and os.access(p2, os.X_OK):
                        return str(p2)

    raise RuntimeError(
        f"Cannot find executable '{command_name}'. "
        f"Set {explicit_env_var}, ensure it is in PATH, or configure ORCA_MODULE_NAME for module-based lookup."
    )


def validate_environment(test_dir: Optional[str] = None) -> Dict[str, Any]:
    """Validate host-environment assumptions for ORCA cube-generation workflows.

    This is a recommended high-level preflight function for skills and MCP
    workflows that plan to call cube-generation tools.

    Recommended use:
    - Call before `generate_homo_lumo_cubes()`
    - Call before `generate_density_and_esp_cubes()`

    What it checks:
    - Python version
    - Operating-system/platform context
    - Whether `bash` is available
    - Whether a module command appears usable
    - Whether `orca_plot` can be found
    - Optional writability of a target calculation directory

    Args:
        test_dir:
            Optional directory to test for writability. This is especially
            helpful before workflows that must create and rename files.

    Returns:
        Dictionary containing:
        - success:
            True when `orca_plot` was found
        - python_version
        - platform
        - system
        - bash_available
        - bash_path
        - module_command_available
        - module_name_attempted
        - orca_plot_found
        - orca_plot_path
        - orca_plot_version
        - test_dir
        - test_dir_writable
        - notes
        - warnings
        - errors

    Guidance for MCP/skills:
    - If success is False, cube-generation workflows should usually stop.
    - If warnings are present, surface them before claiming the environment is
      fully ready.
    """
    warnings: List[str] = []
    errors: List[str] = []

    pyver = sys.version.split()[0]
    system = platform.system()
    bash_path = shutil.which("bash")
    module_name = DEFAULT_MODULE_NAME

    if sys.version_info < (3, 8):
        warnings.append("Python < 3.8 is not a primary target; behavior may be less reliable.")

    if system == "Windows":
        warnings.append("Windows is not a primary target environment for this module.")

    module_cmd_available = False
    if bash_path:
        probe = _run_subprocess(
            ["bash", "-lc", "type module >/dev/null 2>&1; echo $?"],
            timeout=5,
        )
        if probe.get("success"):
            module_cmd_available = (probe.get("stdout", "").strip().splitlines() or ["1"])[-1].strip() == "0"
    else:
        warnings.append("bash not found; module-based executable fallback will be skipped.")

    orca_plot_found = False
    orca_plot_path = None
    orca_plot_version = None

    try:
        orca_plot_path = _find_executable("ORCA_PLOT", "orca_plot")
        orca_plot_found = True
    except Exception as e:
        errors.append(str(e))

    if orca_plot_found and orca_plot_path:
        version_try = _run_subprocess([orca_plot_path, "--version"], timeout=5)
        if version_try.get("success"):
            out = version_try.get("stdout", "") or ""
            if out.strip():
                orca_plot_version = out.strip().splitlines()[0].strip()
            else:
                warnings.append("orca_plot --version returned no output.")
        else:
            warnings.append("Failed to query orca_plot version with --version.")

    writable_ok = None
    writable_message = None
    if test_dir is not None:
        writable_ok, writable_message = _check_dir_writable(Path(test_dir).expanduser().resolve())
        if not writable_ok and writable_message:
            warnings.append(writable_message)

    success = orca_plot_found

    return {
        "success": success,
        "python_version": pyver,
        "platform": platform.platform(),
        "system": system,
        "bash_available": bash_path is not None,
        "bash_path": bash_path,
        "module_command_available": module_cmd_available,
        "module_name_attempted": module_name,
        "orca_plot_found": orca_plot_found,
        "orca_plot_path": orca_plot_path,
        "orca_plot_version": orca_plot_version,
        "test_dir": str(Path(test_dir).expanduser().resolve()) if test_dir else None,
        "test_dir_writable": writable_ok,
        "notes": [SUPPORTED_ORCA_MENU_NOTE],
        "warnings": warnings,
        "errors": errors,
    }


def validate_orca_calc_dir(calc_dir: str) -> Dict[str, Any]:
    """Validate whether a calculation directory looks safe for cube workflows.

    This is a recommended high-level preflight function for directory-based
    cube workflows. It is especially useful before selecting outputs, matching
    GBW files, or generating cubes.

    Recommended use:
    - Call before `generate_homo_lumo_cubes()`
    - Call before `generate_density_and_esp_cubes()`

    What it checks:
    - Whether the directory exists
    - How many `.out` files are present
    - How many `.gbw` files are present
    - Whether same-stem `.out/.gbw` pairs exist
    - Whether the directory appears writable

    Args:
        calc_dir:
            Calculation directory to inspect.

    Returns:
        Dictionary containing:
        - success
        - directory
        - out_count
        - gbw_count
        - out_files
        - gbw_files
        - same_stem_pairs
        - directory_writable
        - warnings
        - error (on failure)

    Guidance for MCP/skills:
    - Warnings about multiple `.out` or `.gbw` files are meaningful reliability
      signals and should not be ignored.
    - If no same-stem pairs exist, downstream cube generation may still run,
      but manual review is advisable.
    """
    path = Path(calc_dir).expanduser().resolve()
    warnings: List[str] = []

    if not path.exists() or not path.is_dir():
        return {
            "success": False,
            "error": f"Directory does not exist or is not a directory: {calc_dir}",
            "directory": str(path),
            "warnings": warnings,
        }

    outs = sorted(path.glob("*.out"))
    gbws = sorted(path.glob("*.gbw"))

    same_stem_pairs = []
    out_stems = {p.stem: p for p in outs}
    gbw_stems = {p.stem: p for p in gbws}
    for stem in sorted(set(out_stems) & set(gbw_stems)):
        same_stem_pairs.append(
            {
                "stem": stem,
                "out_file": str(out_stems[stem].resolve()),
                "gbw_file": str(gbw_stems[stem].resolve()),
            }
        )

    if not outs:
        warnings.append("No .out files found in this calculation directory.")
    if not gbws:
        warnings.append("No .gbw files found in this calculation directory.")
    if len(outs) > 1:
        warnings.append(
            f"Multiple .out files detected ({len(outs)}). Heuristic output selection may be ambiguous."
        )
    if len(gbws) > 1:
        warnings.append(
            f"Multiple .gbw files detected ({len(gbws)}). Fallback GBW selection may be ambiguous."
        )
    if outs and gbws and not same_stem_pairs:
        warnings.append("No same-stem .out/.gbw pairs found; GBW matching may fall back to heuristic selection.")

    writable_ok, writable_msg = _check_dir_writable(path)
    if not writable_ok and writable_msg:
        warnings.append(writable_msg)

    return {
        "success": True,
        "directory": str(path),
        "out_count": len(outs),
        "gbw_count": len(gbws),
        "out_files": [str(p.resolve()) for p in outs],
        "gbw_files": [str(p.resolve()) for p in gbws],
        "same_stem_pairs": same_stem_pairs,
        "directory_writable": writable_ok,
        "warnings": warnings,
    }


def find_matching_gbw(calc_dir: str, out_file: Optional[str] = None) -> Dict[str, Any]:
    """Find the most appropriate `.gbw` file for a calculation directory.

    This is a low-level helper used by cube-generation workflows.

    Matching strategy:
    1. Same-stem match to the selected `.out` file
    2. Stem-prefix heuristic
    3. Largest `.gbw` file in the directory

    Args:
        calc_dir:
            Directory containing candidate `.gbw` files.
        out_file:
            Optional ORCA `.out` file used to improve matching confidence.

    Returns:
        Dictionary containing:
        - success
        - gbw_file
        - match_strategy
        - match_confidence
        - warnings
        - error (on failure)

    Guidance for MCP/skills:
    - If `match_confidence` is not `high`, surface that to the user.
    - Low-confidence GBW matching is a meaningful scientific reliability risk.
    """
    path = Path(calc_dir).expanduser().resolve()
    warnings: List[str] = []

    if not path.exists() or not path.is_dir():
        return {
            "success": False,
            "error": f"Directory not found: {calc_dir}",
            "warnings": warnings,
        }

    gbws = sorted(path.glob("*.gbw"))
    if not gbws:
        return {
            "success": False,
            "error": f"No .gbw files found in directory: {path}",
            "warnings": warnings,
        }

    if out_file:
        out_path = Path(out_file).expanduser().resolve()
        out_stem = out_path.stem

        exact = path / f"{out_stem}.gbw"
        if exact.exists():
            return {
                "success": True,
                "gbw_file": str(exact.resolve()),
                "match_strategy": "same_stem",
                "match_confidence": "high",
                "warnings": warnings,
            }

        prefix_matches = [p for p in gbws if p.stem.startswith(out_stem) or out_stem.startswith(p.stem)]
        if len(prefix_matches) == 1:
            warnings.append("GBW file matched by stem-prefix heuristic, not exact same-stem matching.")
            return {
                "success": True,
                "gbw_file": str(prefix_matches[0].resolve()),
                "match_strategy": "stem_prefix",
                "match_confidence": "medium",
                "warnings": warnings,
            }
        elif len(prefix_matches) > 1:
            warnings.append(
                "Multiple GBW files matched by stem-prefix heuristic; falling back to largest candidate among them."
            )
            largest_prefix = sorted(prefix_matches, key=lambda p: (p.stat().st_size, p.name))[-1]
            return {
                "success": True,
                "gbw_file": str(largest_prefix.resolve()),
                "match_strategy": "stem_prefix_largest",
                "match_confidence": "low",
                "warnings": warnings,
            }

    largest = sorted(gbws, key=lambda p: (p.stat().st_size, p.name))[-1]
    warnings.append("No same-stem GBW match found; falling back to the largest .gbw file in the directory.")
    if len(gbws) > 1:
        warnings.append(f"Multiple GBW candidates detected ({len(gbws)}); heuristic matching may be unreliable.")

    return {
        "success": True,
        "gbw_file": str(largest.resolve()),
        "match_strategy": "largest_file",
        "match_confidence": "low",
        "warnings": warnings,
    }


def generate_mo_cube(
    calc_dir: str,
    mo_number: int,
    output_label: str,
    ngrid: str = "80 80 80",
    operator: int = 0,
    out_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a molecular-orbital cube file using `orca_plot`.

    This is a lower-level helper for cube generation. Most skill-driven
    workflows should prefer `generate_homo_lumo_cubes()` unless a specific
    orbital number is explicitly required.

    Args:
        calc_dir:
            Calculation directory containing ORCA outputs and GBW files.
        mo_number:
            Orbital number to plot.
        output_label:
            Human-readable label included in the normalized output filename.
            Examples: `HOMO`, `LUMO`, `MO25`.
        ngrid:
            Grid intervals as a string of three integers, for example
            `80 80 80`.
        operator:
            Spin operator index:
            - 0: alpha or closed-shell
            - 1: beta
        out_file:
            Optional ORCA `.out` file used to improve GBW matching.

    Returns:
        Dictionary containing:
        - success
        - calc_dir
        - gbw_file
        - cube_file
        - mo_number
        - label
        - operator
        - ngrid
        - orca_plot_path
        - orca_plot_returncode
        - warnings
        - stdout (on failure)
        - error (on failure)

    Important limitations:
    - Depends on version-sensitive `orca_plot -i` menu behavior.
    - Requires writable access to the calculation directory.
    - Correctness depends on correct `.gbw` matching.

    Guidance for MCP/skills:
    - If warnings mention low-confidence GBW matching or possible menu
      incompatibility, communicate that clearly before treating the cube as
      trustworthy.
    """
    warnings: List[str] = []

    calc_path = Path(calc_dir).expanduser().resolve()
    if not calc_path.exists() or not calc_path.is_dir():
        return {
            "success": False,
            "error": f"Directory does not exist or is not a directory: {calc_dir}",
            "warnings": warnings,
        }

    writable_ok, writable_msg = _check_dir_writable(calc_path)
    if not writable_ok:
        return {"success": False, "error": writable_msg, "warnings": warnings}

    ngrid_ok, ngrid_norm, ngrid_err = _parse_ngrid(ngrid)
    if not ngrid_ok:
        return {"success": False, "error": ngrid_err, "warnings": warnings}
    if ngrid_norm is None:
        return {
            "success": False,
            "error": "Internal error: normalized ngrid is missing after validation",
            "warnings": warnings,
        }

    if operator not in (0, 1):
        warnings.append("operator is expected to be 0 (alpha/closed-shell) or 1 (beta).")

    try:
        orca_plot = _find_executable("ORCA_PLOT", "orca_plot")
    except Exception as e:
        return {"success": False, "error": str(e), "warnings": warnings}

    gbw_info = find_matching_gbw(str(calc_path), out_file=out_file)
    warnings = _merge_warnings(warnings, gbw_info)
    if not gbw_info["success"]:
        return gbw_info

    gbw = Path(gbw_info["gbw_file"])
    command_script = ["1", "1", "4", ngrid_norm, "2", str(mo_number)]
    if operator != 0:
        command_script += ["3", str(operator)]
    command_script += ["11", "12"]
    stdin_text = "\n".join(command_script) + "\n"

    proc = _run_subprocess(
        [orca_plot, str(gbw), "-i"],
        input_text=stdin_text,
        cwd=str(calc_path),
        timeout=DEFAULT_SUBPROCESS_TIMEOUT,
    )
    if not proc.get("success"):
        return {
            "success": False,
            "error": proc.get("error", "orca_plot execution failed"),
            "stdout": proc.get("stdout"),
            "warnings": warnings,
        }

    if proc["returncode"] != 0:
        return {
            "success": False,
            "error": f"orca_plot failed with return code {proc['returncode']}",
            "stdout": proc.get("stdout"),
            "warnings": warnings,
        }

    candidates = sorted(calc_path.glob(f"{gbw.stem}.mo{mo_number}*.cube"))
    if not candidates:
        return {
            "success": False,
            "error": "Cube file was not generated",
            "stdout": proc.get("stdout"),
            "warnings": _merge_warnings(
                warnings,
                "orca_plot completed without a detectable MO cube output. "
                "This may indicate ORCA/orca_plot menu incompatibility."
            ),
        }

    if len(candidates) > 1:
        warnings.append(
            f"Multiple generated MO cube candidates detected ({len(candidates)}); selecting the last sorted candidate."
        )

    generated = candidates[-1]
    spin_tag = "a" if operator == 0 else "b"
    final_name = calc_path / (
        f"{gbw.stem}.{output_label}.mo{mo_number}{spin_tag}.ngrid{ngrid_norm.replace(' ', '')}.cube"
    )

    if final_name.exists():
        ok_rm, err_rm = _safe_unlink(final_name)
        if not ok_rm:
            return {
                "success": False,
                "error": err_rm,
                "stdout": proc.get("stdout"),
                "warnings": warnings,
            }

    ok_mv, err_mv = _safe_rename(generated, final_name)
    if not ok_mv:
        return {
            "success": False,
            "error": err_mv,
            "stdout": proc.get("stdout"),
            "warnings": warnings,
        }

    return {
        "success": True,
        "calc_dir": str(calc_path),
        "gbw_file": str(gbw),
        "cube_file": str(final_name.resolve()),
        "mo_number": mo_number,
        "label": output_label,
        "operator": operator,
        "ngrid": ngrid_norm,
        "orca_plot_path": orca_plot,
        "orca_plot_returncode": proc["returncode"],
        "warnings": warnings,
    }


def generate_homo_lumo_cubes(
    calc_dir: str,
    preference: str = "optimization",
    ngrid: str = "80 80 80",
    operator: int = 0,
) -> Dict[str, Any]:
    """Generate HOMO and LUMO cube files for a selected ORCA calculation.

    This is a recommended high-level entry point for frontier-orbital cube
    generation in MCP tools and skills.

    Workflow:
    1. Select an ORCA output file
    2. Extract HOMO/LUMO orbital information
    3. Generate HOMO cube
    4. Generate LUMO cube

    Args:
        calc_dir:
            Calculation directory containing ORCA outputs and GBW files.
        preference:
            Output-selection preference:
            - "optimization"
            - "single_point"
            - "auto"
        ngrid:
            Grid intervals as a string of three integers, for example
            `80 80 80`.
        operator:
            Spin operator index:
            - 0: alpha or closed-shell
            - 1: beta

    Returns:
        Dictionary containing:
        - success
        - calc_dir
        - selected_out_file
        - preference
        - orbital_info
        - homo_cube_result
        - lumo_cube_result
        - warnings
        - error (indirectly via nested result dictionaries)

    Important limitations:
    - HOMO/LUMO extraction is heuristic for open-shell or unusual outputs.
    - Cube generation depends on version-sensitive `orca_plot` interaction.
    - Ambiguous `.out` or `.gbw` matching reduces confidence.

    Guidance for MCP/skills:
    - Recommended preflight sequence:
      `validate_environment()` -> `validate_orca_calc_dir()` -> `generate_homo_lumo_cubes()`
    - If warnings indicate open-shell parsing or ambiguous matching, explicitly
      communicate reduced confidence.
    """
    picked = pick_orca_output(calc_dir, preference=preference)
    if not picked["success"]:
        return picked

    out_file = picked["selected_file"]
    orbital_info = extract_homo_lumo(out_file)
    warnings = _merge_warnings(picked, orbital_info)

    if not orbital_info["success"]:
        return {
            "success": False,
            "error": "Failed to extract HOMO/LUMO info before cube generation",
            "selected_out_file": out_file,
            "orbital_info": orbital_info,
            "warnings": warnings,
        }

    homo_result = generate_mo_cube(
        calc_dir=calc_dir,
        mo_number=orbital_info["homo_no"],
        output_label="HOMO",
        ngrid=ngrid,
        operator=operator,
        out_file=out_file,
    )

    lumo_result = generate_mo_cube(
        calc_dir=calc_dir,
        mo_number=orbital_info["lumo_no"],
        output_label="LUMO",
        ngrid=ngrid,
        operator=operator,
        out_file=out_file,
    )

    warnings = _merge_warnings(warnings, homo_result, lumo_result)

    return {
        "success": homo_result.get("success", False) and lumo_result.get("success", False),
        "calc_dir": str(Path(calc_dir).expanduser().resolve()),
        "selected_out_file": out_file,
        "preference": preference,
        "orbital_info": orbital_info,
        "homo_cube_result": homo_result,
        "lumo_cube_result": lumo_result,
        "warnings": warnings,
    }


def generate_density_and_esp_cubes(
    calc_dir: str,
    preference: str = "optimization",
    ngrid: str = "80 80 80",
    timeout_seconds: int = 600,
) -> Dict[str, Any]:
    """Generate matched electron-density and ESP cube files for an ORCA calculation.

    This is a recommended high-level entry point for density/ESP cube workflows
    in MCP tools and skill-driven orchestration.

    Workflow:
    1. Select an ORCA output file
    2. Find a matching `.gbw` file
    3. Generate density and ESP cubes in one `orca_plot` session
    4. Validate that both cubes share the same grid
    5. Rename outputs to stable workflow-friendly names

    Args:
        calc_dir:
            Calculation directory containing ORCA outputs and GBW files.
        preference:
            Output-selection preference:
            - "optimization"
            - "single_point"
            - "auto"
        ngrid:
            Grid intervals as a string of three integers, for example
            `80 80 80`.
        timeout_seconds:
            Timeout for each `orca_plot` density/ESP generation attempt.
            Increase this for larger grids or slower filesystems.

    Returns:
        Dictionary containing:
        - success
        - calc_dir
        - preference
        - selected_out_file
        - gbw_result
        - gbw_file
        - density_name
        - electron_density_cube
        - electrostatic_potential_cube
        - validation_result
        - ngrid
        - orca_plot_path
        - orca_plot_stdout
        - orca_plot_returncode
        - warnings
        - error (on failure)

    Reliability notes:
    - This workflow is safer than generating density and ESP separately because
      it validates grid consistency.
    - It still depends on version-sensitive `orca_plot -i` interaction and
      correct GBW matching.

    Guidance for MCP/skills:
    - Recommended preflight sequence:
      `validate_environment()` -> `validate_orca_calc_dir()` -> `generate_density_and_esp_cubes()`
    - If warnings mention ambiguous matching or unexpected output naming,
      tell the user that manual verification is recommended.
    """
    warnings: List[str] = []

    calc_path = Path(calc_dir).expanduser().resolve()
    if not calc_path.exists() or not calc_path.is_dir():
        return {
            "success": False,
            "error": f"Directory does not exist or is not a directory: {calc_dir}",
            "warnings": warnings,
        }

    writable_ok, writable_msg = _check_dir_writable(calc_path)
    if not writable_ok:
        return {"success": False, "error": writable_msg, "warnings": warnings}

    ngrid_ok, ngrid_norm, ngrid_err = _parse_ngrid(ngrid)
    if not ngrid_ok:
        return {"success": False, "error": ngrid_err, "warnings": warnings}
    if ngrid_norm is None:
        return {
            "success": False,
            "error": "Internal error: normalized ngrid is missing after validation",
            "warnings": warnings,
        }

    if timeout_seconds <= 0:
        return {
            "success": False,
            "error": "timeout_seconds must be a positive integer",
            "warnings": warnings,
        }

    picked = pick_orca_output(str(calc_path), preference=preference)
    warnings = _merge_warnings(warnings, picked)
    if not picked.get("success"):
        return {
            "success": False,
            "error": "Failed to pick ORCA output file",
            "pick_result": picked,
            "warnings": warnings,
        }

    out_file = picked["selected_file"]

    gbw_result = find_matching_gbw(str(calc_path), out_file=out_file)
    warnings = _merge_warnings(warnings, gbw_result)
    if not gbw_result.get("success"):
        return {
            "success": False,
            "error": "Failed to find matching GBW file",
            "selected_out_file": out_file,
            "pick_result": picked,
            "gbw_result": gbw_result,
            "warnings": warnings,
        }

    try:
        orca_plot = _find_executable("ORCA_PLOT", "orca_plot")
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "selected_out_file": out_file,
            "gbw_result": gbw_result,
            "warnings": warnings,
        }

    gbw = Path(gbw_result["gbw_file"]).expanduser().resolve()
    density_name = f"{gbw.stem}.scfp"

    # ORCA versions may differ in how menu 43 expects the density reference.
    # Try the canonical '<stem>.scfp' first, then a fallback '<stem>' name.
    esp_density_name_candidates = [density_name, gbw.stem]
    attempt_summaries: List[Dict[str, Any]] = []
    proc: Dict[str, Any] = {}
    used_density_name = density_name

    for idx, density_name_candidate in enumerate(esp_density_name_candidates):
        command_script = []
        command_script += ["4", ngrid_norm]
        command_script += ["1", "2"]
        command_script += ["y"]
        command_script += ["11"]
        command_script += ["1", "43"]
        command_script += [density_name_candidate]
        command_script += ["11", "12"]
        stdin_text = "\n".join(command_script) + "\n"

        proc = _run_subprocess(
            [orca_plot, str(gbw), "-i"],
            input_text=stdin_text,
            cwd=str(calc_path),
            timeout=timeout_seconds,
        )

        attempt_summaries.append(
            {
                "attempt": idx + 1,
                "esp_density_name": density_name_candidate,
                "subprocess_success": bool(proc.get("success")),
                "returncode": proc.get("returncode"),
            }
        )

        if proc.get("success") and proc.get("returncode") == 0:
            used_density_name = density_name_candidate
            if density_name_candidate != density_name:
                warnings.append(
                    "ESP generation succeeded only with fallback density reference name; "
                    "this suggests ORCA/orca_plot naming behavior differs from the canonical '<stem>.scfp' path."
                )
            break

        if idx < len(esp_density_name_candidates) - 1:
            warnings.append(
                f"orca_plot failed with ESP density name '{density_name_candidate}'; retrying with fallback candidate."
            )

    if not proc.get("success"):
        return {
            "success": False,
            "error": proc.get("error", "orca_plot execution failed"),
            "selected_out_file": out_file,
            "gbw_file": str(gbw),
            "stdout": proc.get("stdout"),
            "orca_plot_attempts": attempt_summaries,
            "warnings": warnings,
        }

    if proc["returncode"] != 0:
        return {
            "success": False,
            "error": f"orca_plot failed with return code {proc['returncode']}",
            "selected_out_file": out_file,
            "gbw_file": str(gbw),
            "stdout": proc.get("stdout"),
            "orca_plot_attempts": attempt_summaries,
            "warnings": warnings,
        }

    expected_density = calc_path / f"{gbw.stem}.eldens.cube"
    density_candidates = []
    if expected_density.exists():
        density_candidates = [expected_density]
    else:
        density_candidates += list(calc_path.glob(f"{gbw.stem}.*eldens*.cube"))
        density_candidates += list(calc_path.glob(f"{gbw.stem}*eldens*.cube"))
        if not density_candidates:
            density_candidates = list(calc_path.glob("*eldens*.cube"))
        density_candidates = [p for p in density_candidates if p.is_file()]
        density_candidates.sort(key=lambda p: (p.stat().st_mtime, p.stat().st_size))

    if not density_candidates:
        return {
            "success": False,
            "error": "Electron density cube not found after orca_plot finished",
            "selected_out_file": out_file,
            "gbw_file": str(gbw),
            "stdout": proc.get("stdout"),
            "warnings": _merge_warnings(
                warnings,
                "orca_plot completed without a detectable electron-density cube. "
                "This may indicate output naming differences or menu incompatibility."
            ),
        }

    if len(density_candidates) > 1:
        warnings.append(
            f"Multiple electron-density cube candidates detected ({len(density_candidates)}); selecting the last sorted candidate."
        )

    density_cube_raw = density_candidates[-1]

    expected_esp = calc_path / f"{density_name}.esp.cube"
    esp_candidates = []
    if expected_esp.exists():
        esp_candidates = [expected_esp]
    else:
        esp_candidates += list(calc_path.glob(f"{gbw.stem}*.esp.cube"))
        esp_candidates += list(calc_path.glob(f"{gbw.stem}*esp*.cube"))
        if not esp_candidates:
            esp_candidates = list(calc_path.glob("*esp*.cube"))
        esp_candidates = [p for p in esp_candidates if p.is_file()]
        esp_candidates.sort(key=lambda p: (p.stat().st_mtime, p.stat().st_size))

    if not esp_candidates:
        return {
            "success": False,
            "error": "ESP cube not found after orca_plot finished",
            "selected_out_file": out_file,
            "gbw_file": str(gbw),
            "stdout": proc.get("stdout"),
            "warnings": _merge_warnings(
                warnings,
                "orca_plot completed without a detectable ESP cube. "
                "This may indicate output naming differences or menu incompatibility."
            ),
        }

    if len(esp_candidates) > 1:
        warnings.append(
            f"Multiple ESP cube candidates detected ({len(esp_candidates)}); selecting the last sorted candidate."
        )

    esp_cube_raw = esp_candidates[-1]

    try:
        density_lines = density_cube_raw.read_text(errors="ignore").splitlines()
        esp_lines = esp_cube_raw.read_text(errors="ignore").splitlines()

        if len(density_lines) < 6:
            raise ValueError(f"Cube file too short / invalid header: {density_cube_raw}")
        if len(esp_lines) < 6:
            raise ValueError(f"Cube file too short / invalid header: {esp_cube_raw}")

        def _parse_signature(lines: List[str], cube_path: Path) -> Tuple[Any, ...]:
            def _parse_row(s: str, n_expected: int) -> List[str]:
                parts = s.split()
                if len(parts) < n_expected:
                    raise ValueError(f"Invalid cube header line: '{s}' in {cube_path}")
                return parts

            line3 = _parse_row(lines[2].strip(), 4)
            natoms = int(float(line3[0]))
            origin = tuple(round(float(x), 8) for x in line3[1:4])

            axes = []
            for i in range(3, 6):
                row = _parse_row(lines[i].strip(), 4)
                n = int(float(row[0]))
                vec = tuple(round(float(x), 8) for x in row[1:4])
                axes.append((n, vec))

            return (natoms, origin, axes[0], axes[1], axes[2])

        density_signature = _parse_signature(density_lines, density_cube_raw)
        esp_signature = _parse_signature(esp_lines, esp_cube_raw)

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to validate cube headers: {e}",
            "selected_out_file": out_file,
            "gbw_file": str(gbw),
            "electron_density_cube_raw": str(density_cube_raw),
            "electrostatic_potential_cube_raw": str(esp_cube_raw),
            "stdout": proc.get("stdout"),
            "warnings": warnings,
        }

    validation_result = {
        "success": True,
        "electron_density_cube_raw": str(density_cube_raw),
        "electrostatic_potential_cube_raw": str(esp_cube_raw),
        "grid_signature_density": density_signature,
        "grid_signature_esp": esp_signature,
        "is_consistent": density_signature == esp_signature,
    }

    if not validation_result["is_consistent"]:
        return {
            "success": False,
            "error": "Density cube and ESP cube do not share the same grid",
            "calc_dir": str(calc_path),
            "preference": preference,
            "selected_out_file": out_file,
            "gbw_result": gbw_result,
            "validation_result": validation_result,
            "stdout": proc.get("stdout"),
            "warnings": warnings,
        }

    ngrid_tag = ngrid_norm.replace(" ", "")
    density_final = calc_path / f"{gbw.stem}.eldens.ngrid{ngrid_tag}.cube"
    esp_final = calc_path / f"{gbw.stem}.scfp.esp.ngrid{ngrid_tag}.cube"

    if density_final.exists():
        ok_rm, err_rm = _safe_unlink(density_final)
        if not ok_rm:
            return {"success": False, "error": err_rm, "warnings": warnings}

    if esp_final.exists():
        ok_rm, err_rm = _safe_unlink(esp_final)
        if not ok_rm:
            return {"success": False, "error": err_rm, "warnings": warnings}

    ok_mv, err_mv = _safe_rename(density_cube_raw, density_final)
    if not ok_mv:
        return {"success": False, "error": err_mv, "warnings": warnings}

    ok_mv, err_mv = _safe_rename(esp_cube_raw, esp_final)
    if not ok_mv:
        return {"success": False, "error": err_mv, "warnings": warnings}

    return {
        "success": True,
        "calc_dir": str(calc_path),
        "preference": preference,
        "selected_out_file": out_file,
        "gbw_result": gbw_result,
        "gbw_file": str(gbw),
        "density_name": density_name,
        "esp_density_name_used": used_density_name,
        "electron_density_cube": str(density_final.resolve()),
        "electrostatic_potential_cube": str(esp_final.resolve()),
        "validation_result": validation_result,
        "ngrid": ngrid_norm,
        "timeout_seconds": timeout_seconds,
        "orca_plot_path": orca_plot,
        "orca_plot_stdout": proc.get("stdout"),
        "orca_plot_returncode": proc["returncode"],
        "orca_plot_attempts": attempt_summaries,
        "warnings": warnings,
    }
