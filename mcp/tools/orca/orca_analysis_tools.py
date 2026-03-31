"""
ORCA analysis tools for MCP workflows and skill-driven automation.

This module contains read-oriented utilities for parsing and summarizing
ORCA output files. It is designed for use in MCP tools and higher-level
skills that need structured information from ORCA `.out` files without
requiring external executables such as `orca_plot`.

Primary capabilities:
- Scan directories for ORCA `.out` files
- Heuristically select the most relevant ORCA output from a directory
- Check normal termination and inferred convergence state
- Extract final single-point energy
- Extract HOMO/LUMO indices and energies
- Detect imaginary frequencies
- Summarize one or many ORCA output files into structured dictionaries

Design conventions:
- Public functions return dictionaries with a boolean `success` field
- Fatal user-facing problems are returned as structured `error` fields
- Non-fatal reliability concerns are returned in a `warnings` list
- Paths are normalized with pathlib where practical
- Parsing is heuristic and assumes standard ORCA output formatting

Recommended usage with MCP and skills:
1. Use `summarize_orca_output()` as the main single-file analysis entry point.
2. Use `batch_summarize_orca_outputs()` for recursive batch analysis.
3. Use `pick_orca_output()` only when the workflow truly needs automatic
   selection from a directory with one or more candidate `.out` files.
4. Always inspect `warnings` before presenting results as fully reliable.

Important limitations:
- HOMO/LUMO parsing is most reliable for standard closed-shell outputs.
- Open-shell, UHF, ROHF, UKS, or unusual ORCA output layouts may require
  manual verification.
- Frequency parsing assumes standard ORCA text formatting conventions.
- These functions do not verify that a selected file is scientifically
  the "correct" output for a workflow; they provide structured heuristics.

This module is intended to remain read-oriented and lightweight. It does not
call `orca_plot` and does not require writable calculation directories.
"""

from __future__ import annotations

import re
from pathlib import Path
from pprint import pformat
from typing import Any, Dict, List, Optional


def _merge_warnings(*items: Any) -> List[str]:
    """Merge warning messages from strings, lists, or result dictionaries.

    This helper is internal. It de-duplicates warning messages while preserving
    readable order, making it convenient for higher-level tools to aggregate
    warnings from several lower-level parsing steps.

    Args:
        items:
            A mixture of:
            - warning strings
            - lists of warning strings
            - dictionaries containing a `warnings` field

    Returns:
        A de-duplicated list of warning strings.
    """
    warnings: List[str] = []
    for item in items:
        if isinstance(item, dict):
            for w in item.get("warnings", []) or []:
                if isinstance(w, str) and w not in warnings:
                    warnings.append(w)
        elif isinstance(item, list):
            for w in item:
                if isinstance(w, str) and w not in warnings:
                    warnings.append(w)
        elif isinstance(item, str):
            if item not in warnings:
                warnings.append(item)
    return warnings


def _read_text_file(path: Path) -> tuple[bool, str, Optional[str], List[str]]:
    """Read a text file in a forgiving way for ORCA parsing.

    This helper is internal. It uses `errors="ignore"` so that partially messy
    files can still be parsed. Because that can hide encoding problems, the
    helper may also emit warnings.

    Args:
        path:
            Path to the file to read.

    Returns:
        Tuple of:
        - success flag
        - decoded text
        - error message or None
        - list of warnings
    """
    warnings: List[str] = []
    if not path.exists() or not path.is_file():
        return False, "", f"File not found: {path}", warnings

    try:
        text = path.read_text(errors="ignore")
        if not text.strip():
            warnings.append(
                f"File is empty or unreadable after decoding with errors='ignore': {path}"
            )
        return True, text, None, warnings
    except Exception as e:
        return False, "", f"Failed to read file '{path}': {e}", warnings


def _detect_orca_version_from_output_text(text: str) -> Optional[str]:
    """Try to infer an ORCA version string from output text.

    This helper is internal and best-effort only. The result is mainly useful
    for diagnostics and reliability warnings in skill-driven workflows.

    Args:
        text:
            Full ORCA output text.

    Returns:
        Version string if found, otherwise None.
    """
    patterns = [
        r"Program Version\s+([^\s]+)",
        r"ORCA VERSION\s+([^\s]+)",
        r"\* O   R   C   A \*.*?Version\s+([^\s]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip()
    return None


def _looks_like_orca_output(text: str) -> bool:
    """Heuristically decide whether text resembles ORCA output.

    This helper is internal and is used to reduce accidental selection of
    unrelated `.out` files in mixed workflow directories.

    Args:
        text:
            File contents to inspect.

    Returns:
        True if ORCA-like markers are found, otherwise False.
    """
    markers = [
        "ORCA",
        "FINAL SINGLE POINT ENERGY",
        "ORBITAL ENERGIES",
        "ORCA TERMINATED NORMALLY",
    ]
    return any(m in text for m in markers)


def scan_orca_output_files(root_dir: str) -> Dict[str, Any]:
    """Recursively scan a directory for ORCA `.out` files.

    Recommended use:
    - Use this as a low-level discovery helper in batch workflows.
    - Higher-level skills usually should prefer `batch_summarize_orca_outputs()`
      instead of using this function directly.

    Args:
        root_dir:
            Root directory to scan recursively.

    Returns:
        Dictionary containing:
        - success:
            True if scanning completed
        - root_dir:
            Absolute resolved root directory
        - count:
            Number of `.out` files discovered
        - files:
            List of absolute file paths
        - warnings:
            Non-fatal findings such as zero results
        - error:
            Present when success is False

    Notes for MCP/skills:
    - This function only discovers `.out` files. It does not prove that every
      file is a valid ORCA output file.
    - Skills should not interpret the presence of `.out` files as proof that
      downstream parsing will succeed.
    """
    root = Path(root_dir).expanduser().resolve()
    warnings: List[str] = []

    if not root.exists() or not root.is_dir():
        return {
            "success": False,
            "error": f"Directory does not exist or is not a directory: {root_dir}",
            "root_dir": str(root),
            "files": [],
            "warnings": warnings,
        }

    files = sorted(str(p.resolve()) for p in root.rglob("*.out") if p.is_file())
    if not files:
        warnings.append("No .out files found under the requested root directory.")

    return {
        "success": True,
        "root_dir": str(root),
        "count": len(files),
        "files": files,
        "warnings": warnings,
    }


def pick_orca_output(calc_dir: str, preference: str = "optimization") -> Dict[str, Any]:
    """Select the most relevant ORCA output file from a calculation directory.

    This is a low-level helper for directory-based workflows. It scores `.out`
    files using lightweight filename and content heuristics.

    Recommended use:
    - Use when a workflow must choose one `.out` file automatically.
    - Skills should surface `warnings` when the selection is ambiguous.

    Args:
        calc_dir:
            Directory containing one or more candidate ORCA `.out` files.
        preference:
            Output-selection preference. Must be one of:
            - "optimization"
            - "single_point"
            - "auto"

    Returns:
        Dictionary containing:
        - success
        - directory
        - preference
        - selected_file
        - selected_score
        - candidates
        - warnings
        - error (on failure)

    Selection behavior:
    - Uses filename hints and text markers such as:
      `ORBITAL ENERGIES`, `FINAL SINGLE POINT ENERGY`, `HURRAY`,
      `GEOMETRY OPTIMIZATION`, and file size.
    - `auto` performs a simple content-based choice between
      optimization-like and single-point-like outputs.

    Limitations:
    - This is heuristic, not definitive.
    - In mixed directories with multiple related jobs, the selected file may
      still require human confirmation.

    Guidance for MCP/skills:
    - If `warnings` mention ambiguous scoring, the downstream workflow should
      clearly communicate reduced confidence to the user.
    """
    path = Path(calc_dir).expanduser().resolve()
    warnings: List[str] = []

    if preference not in {"optimization", "single_point", "auto"}:
        return {
            "success": False,
            "error": (
                f"Invalid preference '{preference}'. "
                "Expected one of: optimization, single_point, auto"
            ),
            "warnings": warnings,
        }

    if not path.exists() or not path.is_dir():
        return {
            "success": False,
            "error": f"Directory does not exist or is not a directory: {calc_dir}",
            "warnings": warnings,
        }

    outs = sorted(path.glob("*.out"))
    if not outs:
        return {
            "success": False,
            "error": f"No .out files found in directory: {path}",
            "warnings": warnings,
        }

    candidates = []
    for out_path in outs:
        score = 0
        filename_lower = out_path.name.lower()

        ok, text, _, read_warnings = _read_text_file(out_path)
        warnings = _merge_warnings(warnings, read_warnings)
        if not ok:
            text = ""
            score = -10

        looks_orca = _looks_like_orca_output(text)
        if text and not looks_orca:
            score -= 10

        if text:
            if "ORBITAL ENERGIES" in text:
                score += 10
            if "FINAL SINGLE POINT ENERGY" in text:
                score += 5
            if "TOTAL SCF ENERGY" in text or "TOTAL ENERGY" in text:
                score += 2
            if "ORCA TERMINATED NORMALLY" in text:
                score += 3

            try:
                size_bonus = min(out_path.stat().st_size // 100000, 10)
                score += int(size_bonus)
            except Exception:
                warnings.append(f"Could not read file size for scoring: {out_path}")

            pref = preference
            if pref == "auto":
                pref = "optimization" if (
                    "HURRAY" in text or "GEOMETRY OPTIMIZATION" in text
                ) else "single_point"

            if pref == "optimization":
                if "HURRAY" in text or "GEOMETRY OPTIMIZATION" in text:
                    score += 20
                if "opt" in filename_lower:
                    score += 5
                if (
                    "_sp" in filename_lower
                    or filename_lower.endswith("sp.out")
                    or "single" in filename_lower
                ):
                    score -= 5

            elif pref == "single_point":
                if (
                    "_sp" in filename_lower
                    or filename_lower.endswith("sp.out")
                    or "single" in filename_lower
                ):
                    score += 10
                if "RI-MP2" in text or "DLPNO" in text or "SINGLE POINT" in text:
                    score += 8
                if "HURRAY" in text:
                    score -= 5

        candidates.append(
            {
                "file": str(out_path.resolve()),
                "filename": out_path.name,
                "score": int(score),
                "size_bytes": out_path.stat().st_size if out_path.exists() else None,
                "looks_like_orca_output": looks_orca,
            }
        )

    candidates_sorted = sorted(candidates, key=lambda x: (x["score"], x["file"]))
    best = candidates_sorted[-1]

    if len(candidates_sorted) > 1:
        top = candidates_sorted[-1]
        second = candidates_sorted[-2]
        if abs(top["score"] - second["score"]) <= 3:
            warnings.append(
                "Top two .out candidates have very similar scores; output selection may be ambiguous."
            )

    if not best.get("looks_like_orca_output", False):
        warnings.append("Selected .out file does not strongly resemble a standard ORCA output.")

    return {
        "success": True,
        "directory": str(path),
        "preference": preference,
        "selected_file": best["file"],
        "selected_score": best["score"],
        "candidates": candidates_sorted,
        "warnings": warnings,
    }


def check_orca_convergence(out_file: str) -> Dict[str, Any]:
    """Check normal termination and inferred convergence state for an ORCA output.

    This function is intended for single-file analysis workflows and is commonly
    used inside `summarize_orca_output()`.

    Args:
        out_file:
            Path to an ORCA `.out` file.

    Returns:
        Dictionary containing:
        - success
        - file
        - terminated_normally
        - optimization_converged
        - inferred_job_type
        - is_converged
        - matched_keywords
        - markers
        - warnings
        - error (on failure)

    Interpretation notes:
    - For optimization-like outputs, this function treats `HURRAY` as the main
      optimization-convergence marker.
    - For non-optimization outputs, normal termination is treated as the main
      convergence criterion.
    - This is a practical heuristic, not a full ORCA job-state parser.

    Guidance for MCP/skills:
    - If warnings mention missing `HURRAY` in an optimization-like output,
      do not present the job as confidently converged.
    """
    path = Path(out_file).expanduser().resolve()
    warnings: List[str] = []

    ok, text, err, read_warnings = _read_text_file(path)
    warnings = _merge_warnings(warnings, read_warnings)
    if not ok:
        return {"success": False, "error": err, "warnings": warnings}

    terminated_normally = "ORCA TERMINATED NORMALLY" in text
    has_hurray = "HURRAY" in text
    has_geom_opt = "GEOMETRY OPTIMIZATION" in text
    has_freq = "VIBRATIONAL FREQUENCIES" in text or "IR SPECTRUM" in text

    matched_keywords = []
    if terminated_normally:
        matched_keywords.append("ORCA TERMINATED NORMALLY")
    if has_hurray:
        matched_keywords.append("HURRAY")
    if has_geom_opt:
        matched_keywords.append("GEOMETRY OPTIMIZATION")
    if has_freq:
        matched_keywords.append("VIBRATIONAL FREQUENCIES/IR SPECTRUM")

    if has_hurray or has_geom_opt:
        inferred_job_type = "optimization"
    elif has_freq:
        inferred_job_type = "frequency_or_related"
    else:
        inferred_job_type = "single_point_or_other"

    if inferred_job_type == "optimization":
        is_converged = terminated_normally and has_hurray
        if has_geom_opt and not has_hurray:
            warnings.append(
                "Output looks like a geometry optimization but does not contain 'HURRAY'; "
                "optimization convergence may be incomplete or formatting may differ."
            )
    else:
        is_converged = terminated_normally

    if not terminated_normally:
        warnings.append("Output does not contain 'ORCA TERMINATED NORMALLY'.")

    return {
        "success": True,
        "file": str(path),
        "terminated_normally": terminated_normally,
        "optimization_converged": has_hurray,
        "inferred_job_type": inferred_job_type,
        "is_converged": is_converged,
        "matched_keywords": matched_keywords,
        "markers": {
            "orca_terminated_normally_found": terminated_normally,
            "hurray_found": has_hurray,
            "geometry_optimization_found": has_geom_opt,
            "frequency_related_marker_found": has_freq,
        },
        "warnings": warnings,
    }


def extract_final_single_point_energy(out_file: str) -> Dict[str, Any]:
    """Extract the last `FINAL SINGLE POINT ENERGY` from an ORCA output file.

    This function is suitable for standard ORCA outputs that include a
    `FINAL SINGLE POINT ENERGY` line.

    Args:
        out_file:
            Path to an ORCA `.out` file.

    Returns:
        Dictionary containing:
        - success
        - file
        - energy_hartree
        - warnings
        - error (on failure)

    Limitations:
    - Not every ORCA workflow produces this exact line.
    - Missing data is returned as structured failure instead of being guessed.

    Guidance for MCP/skills:
    - If this function fails while other checks succeed, do not invent an
      energy value. Report the absence clearly.
    """
    path = Path(out_file).expanduser().resolve()
    warnings: List[str] = []

    ok, text, err, read_warnings = _read_text_file(path)
    warnings = _merge_warnings(warnings, read_warnings)
    if not ok:
        return {"success": False, "error": err, "warnings": warnings}

    matches = re.findall(r"FINAL SINGLE POINT ENERGY\s+(-?\d+\.\d+)", text)
    if not matches:
        return {
            "success": False,
            "error": "FINAL SINGLE POINT ENERGY not found",
            "file": str(path),
            "warnings": warnings,
        }

    energy = float(matches[-1])
    return {
        "success": True,
        "file": str(path),
        "energy_hartree": energy,
        "warnings": warnings,
    }


def extract_homo_lumo(out_file: str) -> Dict[str, Any]:
    """Extract HOMO/LUMO orbital indices and energies from an ORCA output file.

    This function is intended for standard ORCA orbital tables and is most
    reliable for closed-shell calculations with conventional output layout.

    Args:
        out_file:
            Path to an ORCA `.out` file.

    Returns:
        Dictionary containing:
        - success
        - file
        - homo_no
        - homo_ev
        - lumo_no
        - lumo_ev
        - gap_ev
        - warnings
        - error (on failure)

    Parsing strategy:
    - Finds all `ORBITAL ENERGIES` blocks
    - Uses the last such block
    - Treats the last occupied orbital as HOMO and the first unoccupied as LUMO

    Important limitations:
    - Open-shell, UHF, ROHF, UKS, or spin-separated outputs may not map cleanly
      onto this simple HOMO/LUMO interpretation.
    - Multiple orbital blocks may indicate a more complex output layout.
    - Results should be treated as heuristic when warnings are present.

    Guidance for MCP/skills:
    - If warnings mention open-shell markers or multiple orbital blocks,
      tell the user that frontier orbital assignment may require manual review.
    """
    path = Path(out_file).expanduser().resolve()
    warnings: List[str] = []

    ok, text, err, read_warnings = _read_text_file(path)
    warnings = _merge_warnings(warnings, read_warnings)
    if not ok:
        return {"success": False, "error": err, "warnings": warnings}

    lines = text.splitlines()

    version = _detect_orca_version_from_output_text(text)
    if version:
        warnings.append(f"Detected ORCA version from output text: {version}")

    open_shell_markers = ["UHF", "ROHF", "UKS", "OPEN SHELL", "Spin contamination"]
    found_open_shell_markers = [m for m in open_shell_markers if m in text]
    if found_open_shell_markers:
        warnings.append(
            "Open-shell markers detected in output; HOMO/LUMO parsing may be spin-channel dependent."
        )

    start_indices = [i for i, line in enumerate(lines) if "ORBITAL ENERGIES" in line]
    if not start_indices:
        return {
            "success": False,
            "error": "ORBITAL ENERGIES block not found",
            "file": str(path),
            "warnings": warnings,
        }

    if len(start_indices) > 1:
        warnings.append(
            f"Multiple ORBITAL ENERGIES blocks found ({len(start_indices)}); using the last block."
        )

    last_block = start_indices[-1]
    homo_no = None
    homo_ev = None
    lumo_no = None
    lumo_ev = None

    started_data = False
    for i in range(last_block + 1, len(lines)):
        line = lines[i].strip()
        if not line:
            if started_data and homo_no is not None and lumo_no is not None:
                break
            continue

        parts = line.split()
        parsed = False
        if len(parts) >= 4:
            try:
                no = int(parts[0])
                occ = float(parts[1])
                e_ev = float(parts[3])
                started_data = True
                parsed = True

                if occ > 0.1:
                    homo_no = no
                    homo_ev = e_ev
                elif occ < 0.1 and lumo_no is None:
                    lumo_no = no
                    lumo_ev = e_ev
                    break
            except Exception:
                parsed = False

        if started_data and not parsed:
            if homo_no is not None and lumo_no is not None:
                break

    if homo_no is None or lumo_no is None:
        return {
            "success": False,
            "error": "Failed to parse HOMO/LUMO orbital numbers and energies",
            "file": str(path),
            "warnings": warnings,
        }

    if homo_ev is None or lumo_ev is None:
        return {
            "success": False,
            "error": "Failed to parse HOMO/LUMO energies",
            "file": str(path),
            "warnings": warnings,
        }

    return {
        "success": True,
        "file": str(path),
        "homo_no": int(homo_no),
        "homo_ev": float(homo_ev),
        "lumo_no": int(lumo_no),
        "lumo_ev": float(lumo_ev),
        "gap_ev": float(lumo_ev) - float(homo_ev),
        "warnings": warnings,
    }


def check_imaginary_frequencies(out_file: str) -> Dict[str, Any]:
    """Detect imaginary vibrational frequencies in an ORCA output file.

    This function is intended for standard ORCA frequency-analysis outputs.

    Args:
        out_file:
            Path to an ORCA `.out` file.

    Returns:
        Dictionary containing:
        - success
        - file
        - imaginary_frequency_count
        - imaginary_frequencies_cm-1
        - has_imaginary_frequencies
        - warnings
        - error (on failure)

    Interpretation notes:
    - Zero parsed imaginary frequencies does not always prove that the
      structure is a minimum.
    - If the file does not clearly resemble a frequency calculation, the
      result may be syntactically successful but scientifically incomplete.

    Guidance for MCP/skills:
    - If warnings indicate absence of clear frequency markers, do not overstate
      the meaning of `imaginary_frequency_count = 0`.
    """
    path = Path(out_file).expanduser().resolve()
    warnings: List[str] = []

    ok, text, err, read_warnings = _read_text_file(path)
    warnings = _merge_warnings(warnings, read_warnings)
    if not ok:
        return {"success": False, "error": err, "warnings": warnings}

    lines = text.splitlines()
    imag_freqs = []
    freq_pattern = re.compile(r"^\s*\d+\s*:\s*(-?\d+\.\d+)\s*cm\*\*-1", re.IGNORECASE)

    has_frequency_markers = (
        "VIBRATIONAL FREQUENCIES" in text
        or "NORMAL MODES" in text
        or "IR SPECTRUM" in text
        or "Raman spectrum" in text
    )

    matched_any_frequency_line = False
    for line in lines:
        match = freq_pattern.search(line)
        if match:
            matched_any_frequency_line = True
            value = float(match.group(1))
            if value < 0:
                imag_freqs.append(value)

    if has_frequency_markers and not matched_any_frequency_line:
        warnings.append(
            "Output appears to contain frequency analysis markers, but no standard frequency lines were parsed."
        )

    if not has_frequency_markers:
        warnings.append(
            "No obvious frequency-analysis markers found; zero imaginary frequencies does not imply a successful minimum."
        )

    return {
        "success": True,
        "file": str(path),
        "imaginary_frequency_count": len(imag_freqs),
        "imaginary_frequencies_cm-1": imag_freqs,
        "has_imaginary_frequencies": len(imag_freqs) > 0,
        "warnings": warnings,
    }


def summarize_orca_output(out_file: str) -> Dict[str, Any]:
    """Summarize key information from a single ORCA output file.

    This is a recommended high-level entry point for single-file ORCA analysis
    in MCP tools and skill-driven workflows.

    It combines:
    - convergence checks
    - final-energy extraction
    - HOMO/LUMO parsing
    - imaginary-frequency detection

    Args:
        out_file:
            Path to an ORCA `.out` file.

    Returns:
        Dictionary containing:
        - success
        - file
        - convergence
        - final_energy
        - orbital_energies
        - frequency_analysis
        - warnings

    Guidance for MCP/skills:
    - Use this when the workflow already knows which `.out` file to analyze.
    - Inspect nested warnings before presenting the summary as fully reliable,
      especially for orbital and frequency interpretation.
    """
    conv = check_orca_convergence(out_file)
    energy = extract_final_single_point_energy(out_file)
    orb = extract_homo_lumo(out_file)
    freq = check_imaginary_frequencies(out_file)

    summary_success = all(item.get("success", False) for item in (conv, energy, orb, freq))
    warnings = _merge_warnings(conv, energy, orb, freq)

    return {
        "success": summary_success,
        "file": str(Path(out_file).expanduser().resolve()),
        "convergence": conv,
        "final_energy": energy,
        "orbital_energies": orb,
        "frequency_analysis": freq,
        "warnings": warnings,
    }


def batch_summarize_orca_outputs(root_dir: str) -> Dict[str, Any]:
    """Summarize all ORCA output files found under a root directory.

    This is a recommended high-level entry point for recursive batch analysis
    in MCP tools and skills.

    Args:
        root_dir:
            Root directory to scan recursively for `.out` files.

    Returns:
        Dictionary containing:
        - success
        - root_dir
        - count
        - results
        - warnings
        - error (on failure)

    Notes:
    - This function scans recursively and summarizes each discovered file.
    - It does not deduplicate related outputs from the same project.

    Guidance for MCP/skills:
    - In mixed directories, results may include multiple related outputs.
      Present paths clearly and do not assume one result per project.
    """
    scanned = scan_orca_output_files(root_dir)
    if not scanned["success"]:
        return scanned

    results = []
    all_warnings = _merge_warnings(scanned)
    for file_path in scanned["files"]:
        result = summarize_orca_output(file_path)
        results.append(result)
        all_warnings = _merge_warnings(all_warnings, result)

    return {
        "success": True,
        "root_dir": scanned["root_dir"],
        "count": len(results),
        "results": results,
        "warnings": all_warnings,
    }


def format_result_for_terminal(title: str, result: Dict[str, Any]) -> str:
    """Format a result dictionary for human-readable terminal output.

    This helper is optional for MCP use, but useful for manual testing in
    scripts, notebooks, and interactive shell sessions.

    Args:
        title:
            Short descriptive label for the tool call.
        result:
            Result dictionary returned by a public tool function.

    Returns:
        A formatted multi-line string suitable for terminal display.

    Guidance:
    - This function is for presentation only.
    - Skills should inspect structured fields like `success`, `warnings`,
      and nested result dictionaries instead of relying on this string.
    """
    status = "OK" if result.get("success") else "FAILED"
    return f"[{status}] {title}\n{pformat(result, sort_dicts=False)}"
