"""
Tool for enumerating symmetry-inequivalent ordered supercell decorations of disordered structures.

Takes input structures with fractional site occupancies and generates all symmetry-inequivalent
ordered supercell approximants up to a given supercell-size limit, ranked by Ewald electrostatic
energy or supercell size.

Core use cases in inorganic materials discovery:
  - Building DFT candidate pools for intermediate compositions (e.g., Li_x Na_{1-x} Cl)
  - Identifying likely ground-state cation orderings in layered oxides, spinels, perovskites
  - Generating training data for cluster expansion (CE) models
  - Exploring vacancy and interstitial configurations systematically
"""

from typing import Dict, Any, Optional, List, Union, Annotated
from pydantic import Field


# ---------------------------------------------------------------------------
# Private helper: format one ordered structure and append to output lists
# ---------------------------------------------------------------------------
def _append_result(
    ordered_struct,
    ewald_energy,
    src_formula: str,
    parent_struct,
    n_atoms_parent: int,
    symm_prec: float,
    output_format: str,
    generated_structures: list,
    metadata_list: list,
    warnings: list,
    backend: str,
) -> None:
    """Format an ordered structure and append it (with metadata) to the output lists."""
    sg_number = None
    sg_symbol = None
    try:
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
        sga = SpacegroupAnalyzer(ordered_struct, symprec=symm_prec)
        sg_number = sga.get_space_group_number()
        sg_symbol = sga.get_space_group_symbol()
    except Exception:
        pass

    supercell_size = max(1, round(len(ordered_struct) / n_atoms_parent))

    try:
        if output_format == "dict":
            formatted = ordered_struct.as_dict()
        elif output_format == "poscar":
            from pymatgen.io.vasp import Poscar
            formatted = str(Poscar(ordered_struct))
        elif output_format == "cif":
            from pymatgen.io.cif import CifWriter
            formatted = str(CifWriter(ordered_struct))
        elif output_format == "json":
            import json
            formatted = json.dumps(ordered_struct.as_dict())
        else:
            warnings.append(f"Unknown output_format '{output_format}' — skipping structure.")
            return
    except Exception as e:
        warnings.append(f"Could not format structure (source: '{src_formula}'): {e}. Skipping.")
        return

    meta = {
        "index": len(generated_structures) + 1,
        "source_structure": src_formula,
        "formula": ordered_struct.composition.reduced_formula,
        "n_sites": len(ordered_struct),
        "supercell_size": supercell_size,
        "volume": float(ordered_struct.volume),
        "space_group_number": sg_number,
        "space_group_symbol": sg_symbol,
        "ewald_energy": float(ewald_energy) if ewald_energy is not None else None,
        "is_ordered": ordered_struct.is_ordered,
        "backend": backend,
    }
    generated_structures.append(formatted)
    metadata_list.append(meta)


def pymatgen_enumeration_generator(
    input_structures: Annotated[
        Union[Dict[str, Any], List[Dict[str, Any]], str, List[str]],
        Field(
            description=(
                "Input structure(s) with fractional site occupancies (disordered). "
                "Can be: single Structure dict (from Structure.as_dict()), "
                "list of Structure dicts, CIF string, or list of CIF strings. "
                "Each structure must have at least one site with partial occupancy; "
                "fully ordered structures are skipped unless check_ordered_input=False."
            )
        )
    ],
    min_cell_size: Annotated[
        int,
        Field(
            default=1,
            ge=1,
            le=8,
            description=(
                "Minimum supercell size multiplier (1–8). "
                "The enumeration considers supercells from min_cell_size to max_cell_size "
                "formula units. Default: 1."
            )
        )
    ] = 1,
    max_cell_size: Annotated[
        int,
        Field(
            default=4,
            ge=1,
            le=8,
            description=(
                "Maximum supercell size multiplier (1–8). "
                "Controls the combinatorial scale of the enumeration — the number of "
                "configurations grows factorially with cell size. "
                "Recommended: ≤ 4 for binary mixtures, ≤ 2 for ternary. "
                "Larger values can be very slow. Default: 4."
            )
        )
    ] = 4,
    n_structures: Annotated[
        int,
        Field(
            default=20,
            ge=1,
            le=500,
            description=(
                "Maximum number of ordered structures to return per input structure (1–500). "
                "The enumeration may find fewer configurations than this limit. "
                "Default: 20."
            )
        )
    ] = 20,
    sort_by: Annotated[
        str,
        Field(
            default="ewald",
            description=(
                "Ranking criterion for returned structures. "
                "'ewald': rank by Ewald electrostatic energy — lowest energy first. "
                "  Requires oxidation states; use add_oxidation_states=True if not decorated. "
                "  Best criterion for ionic materials (oxides, fluorides, etc.). "
                "'num_sites': rank by supercell size — smallest supercells first. "
                "'random': return in arbitrary enumlib order (no re-ranking). "
                "Default: 'ewald'."
            )
        )
    ] = "ewald",
    symm_prec: Annotated[
        float,
        Field(
            default=0.1,
            ge=0.001,
            le=0.5,
            description=(
                "Symmetry tolerance in Angstroms for identifying equivalent configurations (0.001–0.5). "
                "Higher values merge more structures as equivalent (fewer results). "
                "Lower values distinguish more subtle symmetry differences (more results). "
                "Default: 0.1 Å."
            )
        )
    ] = 0.1,
    refine_structure: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True, re-symmetrizes the input structure using SpacegroupAnalyzer "
                "before passing it to the enumerator. Recommended to ensure the symmetry "
                "operations used during enumeration are correct. Default: True."
            )
        )
    ] = True,
    check_ordered_input: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True (default), structures that are already fully ordered (no partial "
                "occupancies) are skipped and a warning is emitted. "
                "If False, ordered structures are passed to the enumerator anyway "
                "(useful when you want to systematically generate supercell orderings of an "
                "already-ordered phase for defect or substitution studies)."
            )
        )
    ] = True,
    add_oxidation_states: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True (default) and sort_by='ewald', automatically assigns oxidation "
                "states to the structure using pymatgen's BVAnalyzer before enumeration. "
                "This is required for Ewald energy ranking. "
                "If BVAnalyzer fails, the tool falls back to sort_by='num_sites' and "
                "records a warning. Set to False if the structure already carries oxidation "
                "states or if you want to suppress automatic decoration."
            )
        )
    ] = True,
    output_format: Annotated[
        str,
        Field(
            default="dict",
            description=(
                "Output format for the returned structures. "
                "'dict': pymatgen Structure.as_dict() (default, round-trippable). "
                "'poscar': VASP POSCAR string. "
                "'cif': CIF string. "
                "'json': JSON-serialised Structure dict string."
            )
        )
    ] = "dict"
) -> Dict[str, Any]:
    """
    Enumerate symmetry-inequivalent ordered supercell decorations of disordered structures.

    Uses pymatgen's EnumerateStructureTransformation, which wraps the Hart-Forcade enumlib
    algorithm (enum.x), to find all symmetry-distinct ways of assigning species to sites in
    supercells of the parent disordered cell up to max_cell_size formula units.

    The returned structures are fully ordered (no partial occupancies) and ready for direct
    use in DFT calculations, cluster expansion fitting, or further processing by
    pymatgen_perturbation_generator.

    Requirements:
        - pymatgen must be installed: pip install pymatgen
        - enumlib (enum.x) must be on PATH for EnumerateStructureTransformation to work.
          Install via: pip install enumlib  OR  conda install -c conda-forge enumlib

    Returns:
        dict:
            success             (bool)  Whether enumeration succeeded for at least one structure.
            count               (int)   Total number of ordered structures generated.
            structures          (list)  Ordered structures in requested output_format.
            metadata            (list)  Per-structure information:
                index               (int)   Sequential index (1-based).
                source_structure    (str)   Reduced formula of the input structure.
                formula             (str)   Reduced formula of this ordered structure.
                n_sites             (int)   Number of atoms in the supercell.
                supercell_size      (int)   Supercell multiplier relative to parent cell.
                volume              (float) Cell volume in Å³.
                space_group_number  (int)   Space group number (if determinable).
                space_group_symbol  (str)   Hermann-Mauguin symbol (if determinable).
                ewald_energy        (float) Ewald energy in eV (if sort_by='ewald').
                is_ordered          (bool)  Should always be True for valid results.
            input_info          (dict)  Summary of the input structures.
            enumeration_params  (dict)  Parameters used for the enumeration run.
            message             (str)   Human-readable status message.
            warnings            (list)  Any non-fatal warnings generated.
            error               (str)   Error message if success=False.
    """
    try:
        from pymatgen.core import Structure
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import pymatgen: {e}. Install with: pip install pymatgen"
        }

    # --- Validate parameters ---
    valid_formats = {"dict", "poscar", "cif", "json"}
    if output_format not in valid_formats:
        return {
            "success": False,
            "error": f"Invalid output_format '{output_format}'. Must be one of {sorted(valid_formats)}."
        }

    valid_sort = {"ewald", "num_sites", "random"}
    if sort_by not in valid_sort:
        return {
            "success": False,
            "error": f"Invalid sort_by '{sort_by}'. Must be one of {sorted(valid_sort)}."
        }

    if min_cell_size > max_cell_size:
        return {
            "success": False,
            "error": f"min_cell_size ({min_cell_size}) must be <= max_cell_size ({max_cell_size})."
        }

    # --- Parse input structures ---
    if isinstance(input_structures, (dict, str)):
        raw_list = [input_structures]
    elif isinstance(input_structures, list):
        raw_list = input_structures
    else:
        return {
            "success": False,
            "error": f"Invalid input_structures type: {type(input_structures).__name__}."
        }

    structures: List[Structure] = []
    for i, item in enumerate(raw_list):
        try:
            if isinstance(item, dict):
                structures.append(Structure.from_dict(item))
            elif isinstance(item, str):
                structures.append(Structure.from_str(item, fmt="cif"))
            else:
                return {
                    "success": False,
                    "error": (
                        f"Input structure {i} must be a dict or CIF string, "
                        f"got {type(item).__name__}."
                    )
                }
        except Exception as e:
            return {"success": False, "error": f"Failed to parse input structure {i}: {e}"}

    if not structures:
        return {"success": False, "error": "No valid input structures provided."}

    # --- Detect enumlib availability ---
    import shutil
    _enumlib_available = shutil.which("enum.x") is not None

    if not _enumlib_available:
        return {
            "success": False,
            "error": (
                "enum.x (enumlib) is not on PATH and is required for structure enumeration. "
                "enumlib is NOT available on PyPI or conda for Windows natively. "
                "Install via WSL (Windows Subsystem for Linux): "
                "  1. Install WSL: wsl --install  "
                "  2. Inside WSL: conda install -c conda-forge enumlib  "
                "  3. Add the WSL enum.x path to your Windows PATH. "
                "On Linux/macOS: conda install -c conda-forge enumlib"
            ),
            "enumlib_available": False,
        }

    # --- Import enumeration class ---
    try:
        from pymatgen.transformations.advanced_transformations import (
            EnumerateStructureTransformation,
        )
    except ImportError as e:
        return {
            "success": False,
            "error": (
                f"Failed to import EnumerateStructureTransformation: {e}. "
                "Ensure pymatgen is installed: pip install pymatgen"
            )
        }

    # --- Main enumeration loop ---
    generated_structures: List[Any] = []
    metadata_list: List[Dict[str, Any]] = []
    warnings: List[str] = []
    skipped_ordered: List[str] = []

    for struct in structures:
        src_formula = struct.composition.reduced_formula

        # Skip already-ordered structures if requested
        if check_ordered_input and struct.is_ordered:
            skipped_ordered.append(src_formula)
            warnings.append(
                f"Structure '{src_formula}' is already fully ordered (no partial occupancies) "
                "and was skipped. Set check_ordered_input=False to enumerate it anyway."
            )
            continue

        # Optionally add oxidation states for Ewald ranking
        struct_for_enum = struct.copy()
        effective_sort = sort_by
        if sort_by == "ewald" and add_oxidation_states:
            try:
                from pymatgen.analysis.bond_valence import BVAnalyzer
                bva = BVAnalyzer()
                struct_for_enum = bva.get_oxi_state_decorated_structure(struct_for_enum)
            except Exception as e:
                warnings.append(
                    f"Structure '{src_formula}': could not auto-assign oxidation states "
                    f"({e}). Falling back to sort_by='num_sites' for this structure."
                )
                effective_sort = "num_sites"

        sort_criteria = effective_sort if effective_sort in ("ewald", "num_sites") else "num_sites"

        trans = EnumerateStructureTransformation(
            min_cell_size=min_cell_size,
            max_cell_size=max_cell_size,
            symm_prec=symm_prec,
            refine_structure=refine_structure,
            check_ordered_symmetry=False,
            sort_criteria=sort_criteria,
        )

        try:
            raw = trans.apply_transformation(struct_for_enum, return_ranked_list=n_structures)
        except RuntimeError as e:
            err_str = str(e)
            if "enum" in err_str.lower() or "executable" in err_str.lower():
                return {
                    "success": False,
                    "error": (
                        "enum.x (enumlib) call failed — it may have been removed from PATH. "
                        f"Original error: {err_str}"
                    )
                }
            warnings.append(f"Enumeration failed for '{src_formula}': {err_str}")
            continue
        except Exception as e:
            warnings.append(f"Enumeration failed for '{src_formula}': {e}")
            continue

        if isinstance(raw, Structure):
            raw = [{"structure": raw, "energy": None}]
        elif not isinstance(raw, list):
            warnings.append(f"Unexpected return type from enumeration for '{src_formula}'.")
            continue

        if sort_by == "random":
            import random as _rng
            _rng.shuffle(raw)

        n_atoms_parent = len(struct)
        for entry in raw[:n_structures]:
            s = entry["structure"] if isinstance(entry, dict) else entry
            e = entry.get("energy") if isinstance(entry, dict) else None
            _append_result(
                s, e, src_formula, struct, n_atoms_parent,
                symm_prec, output_format,
                generated_structures, metadata_list, warnings,
                backend="enumlib"
            )

    # --- Build response ---
    if not generated_structures:
        msg = "No ordered structures were generated."
        if skipped_ordered:
            msg += (
                f" All {len(skipped_ordered)} input structure(s) were fully ordered and skipped. "
                "Set check_ordered_input=False to enumerate ordered structures."
            )
        return {
            "success": False,
            "error": msg,
            "warnings": warnings if warnings else None,
        }

    input_info = {
        "n_input_structures": len(structures),
        "input_formulas": [s.composition.reduced_formula for s in structures],
        "n_skipped_ordered": len(skipped_ordered),
    }

    enumeration_params = {
        "backend": "enumlib",
        "enumlib_available": True,
        "min_cell_size": min_cell_size,
        "max_cell_size": max_cell_size,
        "n_structures_requested": n_structures,
        "sort_by": sort_by,
        "symm_prec": symm_prec,
        "refine_structure": refine_structure,
        "check_ordered_input": check_ordered_input,
        "add_oxidation_states": add_oxidation_states,
        "output_format": output_format,
    }

    result: Dict[str, Any] = {
        "success": True,
        "count": len(generated_structures),
        "structures": generated_structures,
        "metadata": metadata_list,
        "input_info": input_info,
        "enumeration_params": enumeration_params,
        "message": (
            f"Enumerated {len(generated_structures)} ordered structure(s) from "
            f"{len(structures)} input structure(s) "
            f"(max_cell_size={max_cell_size}, sort_by='{sort_by}')."
        ),
    }
    if warnings:
        result["warnings"] = warnings
    return result
