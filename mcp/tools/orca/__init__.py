"""
orca_tools: ORCA analysis and cube-generation utilities for MCP workflows.

This package provides structured tools for:
- parsing and summarizing ORCA output files
- validating cube-generation environments
- generating MO, electron-density, and ESP cube files

Package design:
- Public functions return structured dictionaries with a `success` field
- Non-fatal reliability concerns are returned in a `warnings` list
- Analysis tools are read-oriented
- Cube tools depend on `orca_plot`, writable directories, and compatible ORCA behavior

Recommended high-level entry points for skills and MCP:
- summarize_orca_output
- batch_summarize_orca_outputs
- validate_environment
- validate_orca_calc_dir
- generate_homo_lumo_cubes
- generate_density_and_esp_cubes

Typical workflow:
1. validate_environment()
2. validate_orca_calc_dir()
3. summarize_orca_output() or cube-generation functions
"""

from .orca_analysis_tools import (
    scan_orca_output_files,
    pick_orca_output,
    check_orca_convergence,
    extract_final_single_point_energy,
    extract_homo_lumo,
    check_imaginary_frequencies,
    summarize_orca_output,
    batch_summarize_orca_outputs,
    format_result_for_terminal,
)

from .orca_cube_tools import (
    validate_environment,
    validate_orca_calc_dir,
    find_matching_gbw,
    generate_mo_cube,
    generate_homo_lumo_cubes,
    generate_density_and_esp_cubes,
)

__all__ = [
    # Analysis tools
    "scan_orca_output_files",
    "pick_orca_output",
    "check_orca_convergence",
    "extract_final_single_point_energy",
    "extract_homo_lumo",
    "check_imaginary_frequencies",
    "summarize_orca_output",
    "batch_summarize_orca_outputs",
    "format_result_for_terminal",
    # Cube / environment tools
    "validate_environment",
    "validate_orca_calc_dir",
    "find_matching_gbw",
    "generate_mo_cube",
    "generate_homo_lumo_cubes",
    "generate_density_and_esp_cubes",
]

__version__ = "0.1.0"
