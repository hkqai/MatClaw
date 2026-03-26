"""
Tool for generating ML-ready structure fingerprints/representations.

Computes physics-informed structural descriptors for materials:
- SOAP  (Smooth Overlap of Atomic Positions)   — local chemical environment
- MBTR  (Many-Body Tensor Representation)       — global periodic descriptor
- Sine Matrix                                   — periodic Coulomb-like matrix
- Coulomb Matrix                                — atom-pair electrostatic matrix

Uses dscribe for SOAP/MBTR/SineMatrix and optionally for Coulomb Matrix.
All representations return JSON-serialisable lists of floats that can be fed
directly into scikit-learn, PyTorch, or any downstream ML pipeline.

Why important:
  Enables similarity-based candidate screening, diversity filtering, and ML
  property prediction by providing consistent, fixed-length feature vectors.
"""

from typing import Dict, Any, Optional, Union, Annotated, List
from pydantic import Field


def structure_fingerprinter(
    input_structure: Annotated[
        Union[Dict[str, Any], str],
        Field(
            description=(
                "Crystal structure to fingerprint. Accepted formats:\n"
                "- Pymatgen Structure dict (from Structure.as_dict())\n"
                "- CIF string\n"
                "- POSCAR/CONTCAR string\n"
                "Output of pymatgen tools or Materials Project API can be passed directly."
            )
        )
    ],
    representations: Annotated[
        List[str],
        Field(
            default=["soap"],
            description=(
                "List of representations to compute. Choose one or more of:\n"
                "- 'soap'          : Smooth Overlap of Atomic Positions (local, per-site or averaged)\n"
                "- 'mbtr'          : Many-Body Tensor Representation (global)\n"
                "- 'sine_matrix'   : Periodic Coulomb-like matrix eigenspectrum (global)\n"
                "- 'coulomb_matrix': Standard Coulomb matrix eigenspectrum (global, molecule-like)\n"
                "Default: ['soap']"
            )
        )
    ] = ["soap"],
    # SOAP parameters
    soap_r_cut: Annotated[
        float,
        Field(
            default=6.0,
            ge=1.0,
            le=20.0,
            description="SOAP: Radial cutoff radius in Ångström. Default: 6.0"
        )
    ] = 6.0,
    soap_n_max: Annotated[
        int,
        Field(
            default=8,
            ge=1,
            le=20,
            description="SOAP: Number of radial basis functions. Default: 8"
        )
    ] = 8,
    soap_l_max: Annotated[
        int,
        Field(
            default=6,
            ge=0,
            le=15,
            description="SOAP: Maximum degree of spherical harmonics. Default: 6"
        )
    ] = 6,
    soap_sigma: Annotated[
        float,
        Field(
            default=0.5,
            ge=0.01,
            le=5.0,
            description="SOAP: Width of Gaussian smearing (Å). Default: 0.5"
        )
    ] = 0.5,
    soap_average: Annotated[
        str,
        Field(
            default="inner",
            description=(
                "SOAP averaging over sites:\n"
                "- 'off'   : Per-site vectors (shape [n_sites, n_features])\n"
                "- 'inner' : Average in feature space (shape [n_features])\n"
                "- 'outer' : Average in density space then project (shape [n_features])\n"
                "Default: 'inner' (single global vector)"
            )
        )
    ] = "inner",
    # MBTR parameters
    mbtr_k: Annotated[
        List[int],
        Field(
            default=[1, 2, 3],
            description=(
                "MBTR: Which many-body terms to include (1, 2, and/or 3).\n"
                "k=1: elemental distribution, k=2: pairwise geometry, k=3: angular.\n"
                "Default: [1, 2, 3]"
            )
        )
    ] = [1, 2, 3],
    mbtr_grid_n: Annotated[
        int,
        Field(
            default=50,
            ge=10,
            le=500,
            description="MBTR: Number of grid points per term. Default: 50"
        )
    ] = 50,
    # Matrix parameters (Sine Matrix & Coulomb Matrix)
    matrix_n_atoms_max: Annotated[
        Optional[int],
        Field(
            default=None,
            description=(
                "Maximum number of atoms for matrix descriptors. If None, uses the\n"
                "actual number of atoms in the structure. Set explicitly when comparing\n"
                "multiple structures of different sizes. Default: None (auto)"
            )
        )
    ] = None,
    # Species──
    species: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description=(
                "Explicit list of element symbols to include in the descriptor (e.g. ['Li', 'Co', 'O']).\n"
                "Required when comparing fingerprints across different structures — all structures\n"
                "must use the same species list for meaningful similarity comparisons.\n"
                "If None, automatically inferred from the input structure."
            )
        )
    ] = None,
    # Normalisation──
    normalize: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, L2-normalise each output fingerprint vector to unit length.\n"
                "Useful for cosine-similarity comparisons. Default: False"
            )
        )
    ] = False,
) -> Dict[str, Any]:
    """
    Generate ML-ready fingerprints for a crystal structure.

    Produces one or more fixed-length representation vectors suitable for
    machine-learning pipelines, similarity searches, and diversity analysis.

    Returns
    -------
    dict:
        success             (bool)  Whether fingerprinting succeeded.
        composition         (str)   Reduced formula of the input structure.
        n_sites             (int)   Number of sites in the primitive/input cell.
        representations     (dict)  Computed fingerprints, keyed by name:
            soap            (dict)  SOAP result:
                vector          (list[float] | list[list[float]])
                                Per-site array if soap_average='off', else 1-D.
                length          (int)   Fingerprint vector length (or [n_sites, length]).
                n_features      (int)   Feature vector dimension per site.
                species         (list)  Species the descriptor was built for.
                params          (dict)  Hyperparameters used.
            mbtr            (dict)  MBTR result:
                vector          (list[float])  Global 1-D fingerprint.
                length          (int)
                species         (list)
                params          (dict)
            sine_matrix     (dict)  Sine Matrix eigenspectrum:
                vector          (list[float])
                length          (int)
                params          (dict)
            coulomb_matrix  (dict)  Coulomb Matrix eigenspectrum:
                vector          (list[float])
                length          (int)
                params          (dict)
        normalized          (bool)  Whether vectors were L2-normlaised.
        metadata            (dict)  Run metadata.
        message             (str)   Human-readable summary.
        error               (str)   Error message (if failed).
    """
    try:
        from pymatgen.core import Structure
        from pymatgen.io.cif import CifParser
        from pymatgen.io.vasp import Poscar
        import io
    except ImportError as e:
        return {"success": False, "error": f"Failed to import pymatgen: {e}. Install with: pip install pymatgen"}

    try:
        import numpy as np
    except ImportError as e:
        return {"success": False, "error": f"Failed to import numpy: {e}. Install with: pip install numpy"}

    try:
        from ase import Atoms as AseAtoms
        from pymatgen.io.ase import AseAtomsAdaptor
    except ImportError as e:
        return {"success": False, "error": f"Failed to import ase: {e}. Install with: pip install ase"}

    try:
        from dscribe.core.system import System as _DScribeSystem
        from ase import Atoms as _AseAtoms

        def _patched_system_init(
            self,
            symbols=None,
            positions=None,
            numbers=None,
            tags=None,
            momenta=None,
            masses=None,
            magmoms=None,
            charges=None,
            scaled_positions=None,
            cell=None,
            pbc=None,
            celldisp=None,
            constraint=None,
            calculator=None,
            info=None,
            wyckoff_positions=None,
            equivalent_atoms=None,
        ):
            # Call the base ASE Atoms.__init__ with keywords to avoid the
            # positional-arg ordering mismatch in ASE 3.26+.
            _AseAtoms.__init__(
                self,
                symbols=symbols,
                positions=positions,
                numbers=numbers,
                tags=tags,
                momenta=momenta,
                masses=masses,
                magmoms=magmoms,
                charges=charges,
                scaled_positions=scaled_positions,
                cell=cell,
                pbc=pbc,
                celldisp=celldisp,
                constraint=constraint,
                calculator=calculator,
                info=info if info is not None else {},
            )
            self.wyckoff_positions = wyckoff_positions
            self.equivalent_atoms = equivalent_atoms
            self._cell_inverse = None
            self._displacement_tensor = None
            self._distance_matrix = None
            self._inverse_distance_matrix = None

        _DScribeSystem.__init__ = _patched_system_init  # type: ignore[method-assign]
    except ImportError as e:
        return {"success": False, "error": f"Failed to import dscribe: {e}. Install with: pip install dscribe"}

    # Input validation
    representations_lower = [r.lower().strip() for r in representations]
    valid_reps = {"soap", "mbtr", "sine_matrix", "coulomb_matrix"}
    invalid = set(representations_lower) - valid_reps
    if invalid:
        return {
            "success": False,
            "error": f"Unknown representation(s): {invalid}. Valid options: {valid_reps}"
        }
    if not representations_lower:
        return {"success": False, "error": "At least one representation must be specified."}

    if soap_average not in ("off", "inner", "outer"):
        return {"success": False, "error": f"soap_average must be 'off', 'inner', or 'outer', got '{soap_average}'."}

    # Parse structure
    try:
        structure = None
        if isinstance(input_structure, dict):
            module = input_structure.get("@module", "")
            cls = input_structure.get("@class", "")
            # pymatgen module is "pymatgen.core.structure" (lowercase), class is "Structure"
            is_structure = (
                "structure" in module.lower()
                or "Structure" in cls
                or "IStructure" in cls
            )
            if is_structure:
                structure = Structure.from_dict(input_structure)
            else:
                return {"success": False, "error": "Dict input must be a pymatgen Structure dict (@module containing 'structure' or @class 'Structure')."}
        elif isinstance(input_structure, str):
            text = input_structure.strip()
            if not text:
                return {"success": False, "error": "Input structure string is empty."}
            # Try CIF
            if "data_" in text[:200] or "_cell_length_a" in text[:500]:
                try:
                    parser = CifParser(io.StringIO(text))
                    structures = parser.parse_structures(primitive=True)
                    if not structures:
                        return {"success": False, "error": "CIF string parsed but contained no structures."}
                    structure = structures[0]
                except Exception as e:
                    return {"success": False, "error": f"Failed to parse CIF string: {e}"}
            else:
                # Try POSCAR
                try:
                    poscar = Poscar.from_str(text)
                    structure = poscar.structure
                except Exception as e:
                    return {"success": False, "error": f"Failed to parse string as CIF or POSCAR: {e}"}
        else:
            return {"success": False, "error": f"Unsupported input_structure type: {type(input_structure).__name__}"}

        if structure is None or len(structure) == 0:
            return {"success": False, "error": "Parsed structure contains no sites."}

    except Exception as e:
        return {"success": False, "error": f"Failed to parse input structure: {e}"}

    # Convert to ASE Atoms
    try:
        adaptor = AseAtomsAdaptor()
        _raw_atoms = adaptor.get_atoms(structure)
        # Rebuild a clean ASE Atoms to strip any stray arrays (momenta/velocities)
        # that pymatgen may add and that cause ASE validation errors inside dscribe.
        atoms = AseAtoms(
            symbols=_raw_atoms.get_chemical_symbols(),
            positions=_raw_atoms.get_positions(),
            cell=_raw_atoms.get_cell(),
            pbc=True,
        )
    except Exception as e:
        return {"success": False, "error": f"Failed to convert to ASE Atoms: {e}"}

    # Infer species
    if species is None:
        inferred_species = sorted(list(set(str(el) for el in structure.composition.elements)))
    else:
        inferred_species = sorted(list(set(species)))

    n_sites = len(structure)
    n_atoms_max = matrix_n_atoms_max if matrix_n_atoms_max is not None else n_sites

    # Helper: normalise vector
    def _maybe_normalize(arr: np.ndarray) -> np.ndarray:
        if not normalize:
            return arr
        if arr.ndim == 1:
            norm = np.linalg.norm(arr)
            return arr / norm if norm > 0 else arr
        # Per-row normalisation for 2-D (per-site SOAP)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms = np.where(norms > 0, norms, 1.0)
        return arr / norms

    results: Dict[str, Any] = {}

    # SOAP
    if "soap" in representations_lower:
        try:
            from dscribe.descriptors import SOAP

            soap_desc = SOAP(
                species=inferred_species,
                r_cut=soap_r_cut,
                n_max=soap_n_max,
                l_max=soap_l_max,
                sigma=soap_sigma,
                average=soap_average,
                periodic=True,
            )

            soap_out = soap_desc.create(atoms)   # ndarray

            soap_out = _maybe_normalize(soap_out)

            n_features = soap_desc.get_number_of_features()

            if soap_average == "off":
                # shape (n_sites, n_features)
                vector_data = soap_out.tolist()
                length = [n_sites, n_features]
            else:
                vector_data = soap_out.tolist()
                length = len(vector_data)

            results["soap"] = {
                "vector": vector_data,
                "length": length,
                "n_features": n_features,
                "species": inferred_species,
                "params": {
                    "r_cut": soap_r_cut,
                    "n_max": soap_n_max,
                    "l_max": soap_l_max,
                    "sigma": soap_sigma,
                    "average": soap_average,
                },
            }
        except Exception as e:
            results["soap"] = {"error": f"SOAP computation failed: {e}"}

    # MBTR  (dscribe 2.x: one instance per k-body term; results are concatenated)
    if "mbtr" in representations_lower:
        try:
            from dscribe.descriptors import MBTR

            mbtr_vectors = []

            # k=1 : elemental distribution (atomic number)
            if 1 in mbtr_k:
                m1 = MBTR(
                    species=inferred_species,
                    geometry={"function": "atomic_number"},
                    grid={"min": 1, "max": 100, "n": mbtr_grid_n, "sigma": 0.1},
                    weighting={"function": "unity"},
                    normalize_gaussians=True,
                    normalization="l2",
                    periodic=True,
                )
                mbtr_vectors.append(m1.create(atoms))

            # k=2 : pairwise inverse distance
            if 2 in mbtr_k:
                m2 = MBTR(
                    species=inferred_species,
                    geometry={"function": "inverse_distance"},
                    grid={"min": 0.0, "max": 1.0, "n": mbtr_grid_n, "sigma": 0.01},
                    weighting={"function": "exp", "r_cut": 10, "threshold": 1e-3},
                    normalize_gaussians=True,
                    normalization="l2",
                    periodic=True,
                )
                mbtr_vectors.append(m2.create(atoms))

            # k=3 : angular — cosine of bond angle
            if 3 in mbtr_k:
                m3 = MBTR(
                    species=inferred_species,
                    geometry={"function": "cosine"},
                    grid={"min": -1, "max": 1, "n": mbtr_grid_n, "sigma": 0.1},
                    weighting={"function": "smooth_cutoff", "r_cut": 5},
                    normalize_gaussians=True,
                    normalization="l2",
                    periodic=True,
                )
                mbtr_vectors.append(m3.create(atoms))

            if not mbtr_vectors:
                raise ValueError("No valid k-body terms specified.")

            import numpy as _np
            mbtr_out = _np.concatenate(mbtr_vectors) if len(mbtr_vectors) > 1 else mbtr_vectors[0]
            mbtr_out = _maybe_normalize(mbtr_out)

            results["mbtr"] = {
                "vector": mbtr_out.tolist(),
                "length": mbtr_out.shape[-1],
                "species": inferred_species,
                "params": {
                    "k": mbtr_k,
                    "grid_n": mbtr_grid_n,
                },
            }
        except Exception as e:
            results["mbtr"] = {"error": f"MBTR computation failed: {e}"}

    # Sine Matrix
    if "sine_matrix" in representations_lower:
        try:
            from dscribe.descriptors import SineMatrix

            sm_desc = SineMatrix(
                n_atoms_max=n_atoms_max,
                permutation="eigenspectrum",
            )
            sm_out = sm_desc.create(atoms)  # 1-D eigenspectrum
            sm_out = _maybe_normalize(sm_out)

            results["sine_matrix"] = {
                "vector": sm_out.tolist(),
                "length": len(sm_out.tolist()),
                "params": {
                    "n_atoms_max": n_atoms_max,
                    "permutation": "eigenspectrum",
                },
            }
        except Exception as e:
            results["sine_matrix"] = {"error": f"Sine Matrix computation failed: {e}"}

    # Coulomb Matrix
    if "coulomb_matrix" in representations_lower:
        try:
            from dscribe.descriptors import CoulombMatrix

            cm_desc = CoulombMatrix(
                n_atoms_max=n_atoms_max,
                permutation="eigenspectrum",
            )
            cm_out = cm_desc.create(atoms)  # 1-D eigenspectrum
            cm_out = _maybe_normalize(cm_out)

            results["coulomb_matrix"] = {
                "vector": cm_out.tolist(),
                "length": len(cm_out.tolist()),
                "params": {
                    "n_atoms_max": n_atoms_max,
                    "permutation": "eigenspectrum",
                },
            }
        except Exception as e:
            results["coulomb_matrix"] = {"error": f"Coulomb Matrix computation failed: {e}"}

    # Check at least one representation succeeded─
    all_errors = {k: v for k, v in results.items() if "error" in v}
    any_success = any("vector" in v for v in results.values())

    if not any_success:
        error_msgs = "; ".join(f"{k}: {v['error']}" for k, v in all_errors.items())
        return {"success": False, "error": f"All requested representations failed: {error_msgs}"}

    # Build length summary for message──
    rep_summaries = []
    for name, data in results.items():
        if "vector" in data:
            length = data["length"]
            if isinstance(length, list):
                rep_summaries.append(f"{name}:[{length[0]}×{length[1]}]")
            else:
                rep_summaries.append(f"{name}:{length}d")
        else:
            rep_summaries.append(f"{name}:FAILED")

    composition_str = structure.composition.reduced_formula

    # Warnings for partial failures
    warnings = []
    for name, data in all_errors.items():
        warnings.append(f"{name} failed: {data['error']}")

    response: Dict[str, Any] = {
        "success": True,
        "composition": composition_str,
        "n_sites": n_sites,
        "species_used": inferred_species,
        "representations": results,
        "normalized": normalize,
        "metadata": {
            "n_atoms_max": n_atoms_max,
            "requested_representations": representations_lower,
            "successful_representations": [k for k in results if "vector" in results[k]],
            "failed_representations": list(all_errors.keys()),
        },
        "message": (
            f"Fingerprinted {composition_str} ({n_sites} sites) with "
            f"{', '.join(rep_summaries)}."
        ),
    }

    if warnings:
        response["warnings"] = warnings

    return response
