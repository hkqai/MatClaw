"""
Tool for generating perturbed structure ensembles via random atomic displacements and/or strain.
Useful for creating thermal ensembles, testing structural robustness, and data augmentation.
Preserves composition and periodicity; optionally restores symmetry after perturbation.
"""

from typing import Dict, Any, Optional, List, Union, Annotated
from pydantic import Field


def pymatgen_perturbation_generator(
    input_structures: Annotated[
        Union[Dict[str, Any], List[Dict[str, Any]], str, List[str]],
        Field(description=(
            "Input structure(s) to perturb. Can be: single Structure dict "
            "(from Structure.as_dict()), list of dicts, CIF string, or list of CIF strings. "
            "IMPORTANT FORMAT NOTE:"
            "- Dict format MUST be pymatgen Structure.as_dict() format (contains '@module' and 'lattice' keys). "
            "- When using MP structures, convert to CIF string first or use  CIF format for best compatibility."
        ))
    ],
    displacement_max: Annotated[
        float,
        Field(description=(
            "Maximum magnitude of random atomic displacement in Ångströms. "
            "Each atom is displaced by a random vector whose length is uniformly "
            "sampled in [0, displacement_max]. Set to 0.0 to disable displacements. "
            "Typical range: 0.05–0.2 Å. Default: 0.1 Å."
        ), ge=0.0, le=2.0)
    ] = 0.1,
    strain_percent: Annotated[
        Union[float, List[float], None],
        Field(description=(
            "Strain to apply to the lattice in percent. "
            "Single float: uniform isotropic strain applied to all axes (e.g. 1.0 = +1%). "
            "Two-element list [min, max]: each structure's strain is sampled uniformly in this range "
            "(e.g. [-1.0, 1.0]). "
            "Six-element list [e_xx, e_yy, e_zz, e_xy, e_xz, e_yz]: explicit Voigt strain tensor in %. "
            "None (default): no strain applied."
        ))
    ] = None,
    n_structures: Annotated[
        int,
        Field(description=(
            "Number of perturbed structures to generate per input structure (1–200). "
            "Default: 10."
        ), ge=1, le=200)
    ] = 10,
    seed: Annotated[
        Optional[int],
        Field(description=(
            "Random seed for reproducibility. If None (default), results are non-deterministic. "
            "When set, each input structure's perturbations are fully reproducible."
        ))
    ] = None,
    preserve_symmetry: Annotated[
        bool,
        Field(description=(
            "If True, attempts to restore the space group symmetry of the original structure "
            "after perturbation using pymatgen's SpacegroupAnalyzer. This reduces the effective "
            "disorder but keeps the structure symmetrically valid. Default: False."
        ))
    ] = False,
    output_format: Annotated[
        str,
        Field(description=(
            "Output format: 'dict' (Structure.as_dict()), "
            "'poscar' (VASP POSCAR string), 'cif' (CIF string), 'json' (JSON string). "
            "Default: 'dict'."
        ))
    ] = "dict"
) -> Dict[str, Any]:
    """
    Generate an ensemble of perturbed structures from one or more input structures.

    Perturbations include:
    - Random atomic displacements ("rattling"): each atom is displaced by a random
      vector with length sampled uniformly in [0, displacement_max].
    - Lattice strain: the unit cell is deformed according to strain_percent, applied
      as a symmetric strain tensor to the lattice matrix.

    Both perturbations can be applied simultaneously or independently.

    Returns
    -------
    dict:
        success         (bool)
        count           (int)   total structures generated
        structures      (list)  in requested output_format
        metadata        (list)  per-structure info
        input_info      (dict)  summary of input structures
        perturbation_params (dict) parameters used
        message         (str)
        warnings        (list, optional)
        error           (str, optional)
    """
    import numpy as np

    try:
        from pymatgen.core import Structure
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import pymatgen: {str(e)}. Install with: pip install pymatgen"
        }

    # Validate output_format
    valid_formats = {"dict", "poscar", "cif", "json", "ase"}
    if output_format not in valid_formats:
        return {
            "success": False,
            "error": f"Invalid output_format: '{output_format}'. Must be one of {sorted(valid_formats)}."
        }

    # Validate strain_percent
    if strain_percent is not None:
        if isinstance(strain_percent, (int, float)):
            strain_mode = "uniform"
            strain_value = float(strain_percent)
        elif isinstance(strain_percent, list):
            if len(strain_percent) == 2:
                strain_mode = "range"
                strain_min, strain_max = float(strain_percent[0]), float(strain_percent[1])
                if strain_min > strain_max:
                    return {
                        "success": False,
                        "error": "strain_percent range: first element must be <= second element."
                    }
                strain_value = (strain_min, strain_max)
            elif len(strain_percent) == 6:
                strain_mode = "voigt"
                strain_value = [float(v) for v in strain_percent]
            else:
                return {
                    "success": False,
                    "error": (
                        "strain_percent list must have 2 elements [min, max] "
                        "or 6 elements [e_xx, e_yy, e_zz, e_xy, e_xz, e_yz]. "
                        f"Got {len(strain_percent)} elements."
                    )
                }
        else:
            return {
                "success": False,
                "error": f"Invalid strain_percent type: {type(strain_percent).__name__}."
            }
    else:
        strain_mode = None
        strain_value = None

    # Parse input structures
    if isinstance(input_structures, (dict, str)):
        raw_list = [input_structures]
    elif isinstance(input_structures, list):
        raw_list = input_structures
    else:
        return {
            "success": False,
            "error": f"Invalid input_structures type: {type(input_structures).__name__}"
        }

    structures = []
    for i, item in enumerate(raw_list):
        try:
            if isinstance(item, dict):
                structures.append(Structure.from_dict(item))
            elif isinstance(item, str):
                structures.append(Structure.from_str(item, fmt="cif"))
            else:
                return {
                    "success": False,
                    "error": f"Input structure {i} must be a dict or CIF string, got {type(item).__name__}"
                }
        except Exception as e:
            return {"success": False, "error": f"Failed to parse input structure {i}: {str(e)}"}

    if not structures:
        return {"success": False, "error": "No valid input structures provided."}

    # Set up RNG
    rng = np.random.default_rng(seed)

    # Helper: apply strain tensor to a lattice matrix
    def apply_strain(lattice_matrix: np.ndarray, strain_tensor: np.ndarray) -> np.ndarray:
        """
        Apply a symmetric strain tensor (3x3) to a lattice matrix.
        new_lattice = (I + epsilon) @ lattice
        """
        deformation = np.eye(3) + strain_tensor
        return deformation @ lattice_matrix

    def build_strain_tensor(mode: str, value) -> np.ndarray:
        """Build a 3x3 symmetric strain tensor from mode/value."""
        eps = np.zeros((3, 3))
        if mode == "uniform":
            e = value / 100.0
            eps[0, 0] = eps[1, 1] = eps[2, 2] = e
        elif mode == "range":
            s_min, s_max = value
            e = rng.uniform(s_min, s_max) / 100.0
            eps[0, 0] = eps[1, 1] = eps[2, 2] = e
        elif mode == "voigt":
            # [e_xx, e_yy, e_zz, e_xy, e_xz, e_yz] in percent
            v = [x / 100.0 for x in value]
            eps[0, 0] = v[0]
            eps[1, 1] = v[1]
            eps[2, 2] = v[2]
            eps[0, 1] = eps[1, 0] = v[3] / 2.0
            eps[0, 2] = eps[2, 0] = v[4] / 2.0
            eps[1, 2] = eps[2, 1] = v[5] / 2.0
        return eps

    # Main generation loop
    generated_structures = []
    metadata_list = []
    warnings = []

    for struct in structures:
        struct_label = struct.composition.reduced_formula
        n_atoms = len(struct)

        for variant_idx in range(n_structures):
            try:
                new_struct = struct.copy()

                # Atomic displacements
                actual_disp_max = 0.0
                disp_rms = 0.0
                if displacement_max > 0.0:
                    # Sample random displacement vectors in Cartesian coords
                    # Direction: uniform on sphere; magnitude: uniform in [0, displacement_max]
                    directions = rng.standard_normal((n_atoms, 3))
                    norms = np.linalg.norm(directions, axis=1, keepdims=True)
                    norms = np.where(norms < 1e-10, 1.0, norms)
                    directions = directions / norms

                    magnitudes = rng.uniform(0.0, displacement_max, size=n_atoms)
                    displacements = directions * magnitudes[:, np.newaxis]  # (N, 3) Cartesian Å

                    # Apply to each site
                    for i, site in enumerate(new_struct):
                        new_struct.translate_sites(
                            [i],
                            displacements[i],
                            frac_coords=False,
                            to_unit_cell=True
                        )

                    actual_disp_max = float(np.max(magnitudes))
                    disp_rms = float(np.sqrt(np.mean(magnitudes ** 2)))

                # Lattice strain
                strain_applied = None
                strain_tensor_used = None
                if strain_mode is not None:
                    eps = build_strain_tensor(strain_mode, strain_value)
                    strain_tensor_used = eps.tolist()

                    old_matrix = np.array(new_struct.lattice.matrix)
                    new_matrix = apply_strain(old_matrix, eps)

                    # Reconstruct structure with new lattice, keeping fractional coords
                    from pymatgen.core import Lattice
                    new_lattice = Lattice(new_matrix)
                    frac_coords = new_struct.frac_coords
                    species = [str(site.specie) for site in new_struct]
                    new_struct = Structure(new_lattice, species, frac_coords)

                    # Summary: diagonal strain components in percent
                    strain_applied = {
                        "e_xx_pct": round(eps[0, 0] * 100, 4),
                        "e_yy_pct": round(eps[1, 1] * 100, 4),
                        "e_zz_pct": round(eps[2, 2] * 100, 4),
                        "e_xy_pct": round(eps[0, 1] * 2 * 100, 4),
                        "e_xz_pct": round(eps[0, 2] * 2 * 100, 4),
                        "e_yz_pct": round(eps[1, 2] * 2 * 100, 4),
                    }

                # Symmetry restoration
                symmetry_restored = False
                if preserve_symmetry:
                    try:
                        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
                        sga = SpacegroupAnalyzer(new_struct, symprec=0.3)
                        sym_struct = sga.get_symmetrized_structure()
                        # Use the primitive cell of the symmetrized structure
                        new_struct = sym_struct
                        symmetry_restored = True
                    except Exception as e:
                        warnings.append(
                            f"Structure {struct_label} variant {variant_idx + 1}: "
                            f"symmetry restoration failed ({e})."
                        )

                # Format output
                try:
                    if output_format == "dict":
                        formatted = new_struct.as_dict()
                    elif output_format == "poscar":
                        from pymatgen.io.vasp import Poscar
                        formatted = str(Poscar(new_struct))
                    elif output_format == "cif":
                        from pymatgen.io.cif import CifWriter
                        formatted = str(CifWriter(new_struct))
                    elif output_format == "json":
                        import json
                        formatted = json.dumps(new_struct.as_dict())
                    elif output_format == "ase":
                        # Convert to ASE-compatible format
                        formatted = {
                            "numbers": [site.specie.Z for site in new_struct.sites],
                            "positions": [site.coords.tolist() for site in new_struct.sites],
                            "cell": new_struct.lattice.matrix.tolist(),
                            "pbc": [True, True, True]
                        }
                except Exception as e:
                    warnings.append(
                        f"Structure {struct_label} variant {variant_idx + 1}: "
                        f"output formatting failed ({e})."
                    )
                    continue

                # Metadata
                metadata = {
                    "index": len(generated_structures) + 1,
                    "source_structure": struct_label,
                    "variant": variant_idx + 1,
                    "formula": new_struct.composition.reduced_formula,
                    "n_sites": len(new_struct),
                    "volume": float(new_struct.volume),
                    "volume_change_pct": round(
                        (new_struct.volume - struct.volume) / struct.volume * 100, 4
                    ),
                    "displacement_max_actual_ang": round(actual_disp_max, 6),
                    "displacement_rms_ang": round(disp_rms, 6),
                    "strain_applied": strain_applied,
                    "symmetry_restored": symmetry_restored,
                }

                generated_structures.append(formatted)
                metadata_list.append(metadata)

            except Exception as e:
                warnings.append(
                    f"Structure {struct_label} variant {variant_idx + 1}: "
                    f"unexpected error ({e})."
                )
                continue

    # Final response
    if not generated_structures:
        return {
            "success": False,
            "error": "No perturbed structures could be generated.",
            "warnings": warnings
        }

    perturbation_params = {
        "displacement_max_ang": displacement_max,
        "strain_percent": strain_percent,
        "strain_mode": strain_mode,
        "n_structures_per_input": n_structures,
        "seed": seed,
        "preserve_symmetry": preserve_symmetry,
        "output_format": output_format,
    }

    input_info = {
        "n_input_structures": len(structures),
        "input_formulas": [s.composition.reduced_formula for s in structures],
    }

    result = {
        "success": True,
        "count": len(generated_structures),
        "structures": generated_structures,
        "metadata": metadata_list,
        "input_info": input_info,
        "perturbation_params": perturbation_params,
        "message": (
            f"Generated {len(generated_structures)} perturbed structure(s) "
            f"from {len(structures)} input structure(s)."
        ),
    }
    if warnings:
        result["warnings"] = warnings
    return result
