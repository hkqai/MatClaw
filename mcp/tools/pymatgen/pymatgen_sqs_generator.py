"""
Tool for generating Special Quasirandom Structures (SQS) for disordered alloy and
solid-solution modelling in inorganic materials.

A SQS is a small, fully ordered supercell whose pair (and optionally higher-order)
correlation functions best mimic those of a perfectly random alloy at the same composition.
They are the standard approach for modelling disordered bulk systems — high-entropy oxides,
solid-solution cathodes, mixed perovskites, etc. — with periodic DFT codes.

Relationship to pymatgen_enumeration_generator
----------------------------------------------
  enumeration_generator: enumerates ALL symmetry-distinct ordered configurations
      - best for small cells, low-symmetry mixing, finding ground-state orderings.
  sqs_generator: finds the SINGLE best quasirandom approximant
      - best for solid-solution / high-entropy systems where disorder is the target.

Backend
-------
  Default: pure Python / NumPy Monte Carlo — no external binary dependencies.
  Optional: ATAT mcsqs binary via pymatgen's mcsqs_caller (use_mcsqs=True).
"""

from typing import Dict, Any, Optional, List, Union, Annotated
from pydantic import Field


def pymatgen_sqs_generator(
    input_structures: Annotated[
        Union[Dict[str, Any], List[Dict[str, Any]], str, List[str]],
        Field(
            description=(
                "Input structure(s) with fractional site occupancies (disordered). "
                "Accepts the same formats as pymatgen_enumeration_generator: "
                "a single Structure dict (from Structure.as_dict()), a list of dicts, "
                "a CIF string, or a list of CIF strings. "
                "Each structure must have at least one site with partial occupancy."
            )
        )
    ],
    supercell_size: Annotated[
        int,
        Field(
            default=8,
            ge=1,
            le=64,
            description=(
                "Target number of formula units in the SQS supercell (1–64). "
                "The tool finds the smallest uniform scaling that meets or exceeds this value. "
                "Larger supercells give better quasirandomness but are more expensive for DFT. "
                "Typical values: 8–16 for binary, 12–24 for ternary. "
                "Ignored when supercell_matrix is provided. "
                "Default: 8."
            )
        )
    ] = 8,
    supercell_matrix: Annotated[
        Optional[Union[List[int], List[List[int]]]],
        Field(
            default=None,
            description=(
                "Explicit supercell expansion matrix. "
                "List of 3 integers [nx, ny, nz] for diagonal scaling, or a 3×3 list of lists "
                "for a full transformation matrix. Example: [2, 2, 2] → 2×2×2 supercell. "
                "When provided, supercell_size is ignored."
            )
        )
    ] = None,
    n_structures: Annotated[
        int,
        Field(
            default=3,
            ge=1,
            le=20,
            description=(
                "Number of independent SQS candidates to generate per input structure (1–20). "
                "Each run starts from a different random initial configuration. "
                "Candidates are ranked by SQS error (best first) when sort_by='sqs_error'. "
                "Default: 3."
            )
        )
    ] = 3,
    n_mc_steps: Annotated[
        int,
        Field(
            default=50000,
            ge=100,
            le=5000000,
            description=(
                "Number of Monte Carlo swap steps per SQS candidate (100–5,000,000). "
                "More steps improve the quality of the SQS at the cost of runtime. "
                "Convergence is typically reached in 10,000–100,000 steps for binary systems "
                "and 50,000–500,000 for ternary. "
                "Default: 50,000."
            )
        )
    ] = 50000,
    n_shells: Annotated[
        int,
        Field(
            default=4,
            ge=1,
            le=10,
            description=(
                "Number of nearest-neighbour shells to include in the SQS objective function "
                "(1–10). More shells produce better long-range quasirandomness but increase "
                "the computational cost of each MC step. "
                "Default: 4."
            )
        )
    ] = 4,
    shell_weights: Annotated[
        Optional[List[float]],
        Field(
            default=None,
            description=(
                "Per-shell weights for the SQS objective. Length must equal n_shells. "
                "Higher weight = closer match required for that shell. "
                "Default (None): weights = [1/1, 1/2, 1/3, …, 1/n_shells] "
                "(decreasing with shell index to prioritise nearest neighbours)."
            )
        )
    ] = None,
    sort_by: Annotated[
        str,
        Field(
            default="sqs_error",
            description=(
                "Ranking criterion for returned structures. "
                "'sqs_error': rank by SQS objective value — lowest error first (recommended). "
                "'random': return in generation order without re-ranking. "
                "Default: 'sqs_error'."
            )
        )
    ] = "sqs_error",
    seed: Annotated[
        Optional[int],
        Field(
            default=None,
            description=(
                "Random seed for reproducibility. If None (default), results are non-deterministic. "
                "Each candidate within a call uses a deterministic derived seed so that "
                "n_structures=3, seed=42 always produces the same three structures."
            )
        )
    ] = None,
    use_mcsqs: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, attempt to use the ATAT mcsqs binary via pymatgen's mcsqs_caller. "
                "mcsqs typically produces higher-quality SQS than the built-in Monte Carlo "
                "for large multicomponent systems. "
                "Falls back to the built-in Monte Carlo if the binary is not on PATH. "
                "Default: False (use built-in Monte Carlo)."
            )
        )
    ] = False,
    mcsqs_timeout: Annotated[
        int,
        Field(
            default=60,
            ge=5,
            le=600,
            description=(
                "Timeout in seconds for the mcsqs binary call (5–600). "
                "Only used when use_mcsqs=True. "
                "Default: 60 s."
            )
        )
    ] = 60,
    output_format: Annotated[
        str,
        Field(
            default="dict",
            description=(
                "Output format for the returned structures. "
                "'dict': pymatgen Structure.as_dict() — default, round-trippable. "
                "'poscar': VASP POSCAR string. "
                "'cif': CIF string. "
                "'json': JSON-serialised Structure dict string."
            )
        )
    ] = "dict"
) -> Dict[str, Any]:
    """
    Generate Special Quasirandom Structures (SQS) for disordered solid-solution modelling.

    Takes disordered structures with fractional site occupancies and produces fully ordered
    supercells whose Warren-Cowley pair correlation functions match those of a perfectly
    random alloy as closely as possible.

    Algorithm (built-in Monte Carlo backend)
    -----------------------------------------
    1.  Build a supercell of the requested size from the disordered input.
    2.  Identify mixing sublattices (groups of sites with partial occupancy).
    3.  Assign species to sublattice sites at random, preserving the target stoichiometry
        exactly (integer site counts obtained by nearest-integer rounding with correction).
    4.  Detect nearest-neighbour shells by distance clustering up to a cutoff.
    5.  Compute Warren-Cowley (WC) short-range order parameters α_AB(r) for all species
        pairs in each shell.  For a perfectly random alloy α = 0 everywhere.
    6.  Run Monte Carlo: at each step, swap two randomly chosen atoms of different species
        on the same sublattice.  Accept swaps that reduce the weighted SQS objective:
            E = Σ_{shells} w_s · Σ_{pairs (A,B)} α_AB(s)²
        Reject swaps that increase E (pure greedy minimisation — no temperature).
    7.  Track the best configuration encountered.  Repeat from step 3 for each candidate.
    8.  Sort candidates by final SQS error and return.

    Returns
    -------
    dict:
        success             (bool)  Whether at least one SQS was generated.
        count               (int)   Number of SQS structures returned.
        structures          (list)  Ordered SQS structures in requested output_format.
        metadata            (list)  Per-structure metadata:
            index               (int)   1-based sequential index.
            source_formula      (str)   Reduced formula of the disordered input.
            sqs_formula         (str)   Reduced formula of the SQS supercell.
            n_sites             (int)   Number of atoms in the SQS supercell.
            supercell_size      (int)   Expansion factor relative to the input cell.
            sqs_error           (float) Weighted sum of squared WC parameters (lower = better).
            warren_cowley       (dict)  WC parameters α_AB(s) per shell per pair.
            composition         (dict)  Actual element counts in the SQS.
            n_mc_steps          (int)   MC steps executed.
            backend             (str)   'monte_carlo' or 'mcsqs'.
            mcsqs_used          (bool)  Whether the mcsqs binary was used.
        input_info          (dict)  Summary of the input structures.
        sqs_params          (dict)  Parameters used for the SQS run.
        message             (str)   Human-readable status message.
        warnings            (list)  Non-fatal warnings (absent if none).
        error               (str)   Error message if success=False.
    """
    import numpy as np

    # Imports
    try:
        from pymatgen.core import Structure, Lattice, Element
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import pymatgen: {e}. Install with: pip install pymatgen"
        }

    # Validate parameters
    valid_formats = {"dict", "poscar", "cif", "json"}
    if output_format not in valid_formats:
        return {
            "success": False,
            "error": f"Invalid output_format '{output_format}'. Must be one of {sorted(valid_formats)}."
        }

    valid_sort = {"sqs_error", "random"}
    if sort_by not in valid_sort:
        return {
            "success": False,
            "error": f"Invalid sort_by '{sort_by}'. Must be one of {sorted(valid_sort)}."
        }

    if shell_weights is not None:
        if len(shell_weights) != n_shells:
            return {
                "success": False,
                "error": (
                    f"shell_weights length ({len(shell_weights)}) must equal "
                    f"n_shells ({n_shells})."
                )
            }
        if any(w < 0 for w in shell_weights):
            return {"success": False, "error": "All shell_weights must be >= 0."}
        _weights = np.array(shell_weights, dtype=float)
    else:
        _weights = np.array([1.0 / (s + 1) for s in range(n_shells)])

    # Validate / parse supercell_matrix
    _sc_matrix = None
    if supercell_matrix is not None:
        if isinstance(supercell_matrix, list):
            if len(supercell_matrix) == 3 and all(isinstance(x, int) for x in supercell_matrix):
                nx, ny, nz = supercell_matrix
                if any(v < 1 for v in [nx, ny, nz]):
                    return {"success": False, "error": "supercell_matrix diagonal values must all be >= 1."}
                _sc_matrix = [[nx, 0, 0], [0, ny, 0], [0, 0, nz]]
            elif (len(supercell_matrix) == 3 and
                  all(isinstance(row, list) and len(row) == 3 for row in supercell_matrix)):
                _sc_matrix = supercell_matrix
            else:
                return {
                    "success": False,
                    "error": "supercell_matrix must be [nx, ny, nz] or a 3×3 list of lists."
                }
        else:
            return {"success": False, "error": "supercell_matrix must be a list."}

    # Parse input structures
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

    warnings: List[str] = []

    # Helper: format a Structure
    def _format(struct: Structure):
        try:
            if output_format == "dict":
                return struct.as_dict()
            elif output_format == "poscar":
                from pymatgen.io.vasp import Poscar
                return str(Poscar(struct))
            elif output_format == "cif":
                from pymatgen.io.cif import CifWriter
                return str(CifWriter(struct))
            elif output_format == "json":
                import json
                return json.dumps(struct.as_dict())
        except Exception as e:
            warnings.append(f"Output formatting failed: {e}")
            return None

    # Helper: build supercell from a disordered structure
    def _build_supercell(disordered: Structure):
        sc = disordered.copy()
        if _sc_matrix is not None:
            sc.make_supercell(_sc_matrix)
            det = int(round(abs(np.linalg.det(np.array(_sc_matrix, dtype=float)))))
            return sc, _sc_matrix, det
        else:
            factor = 1
            n = len(disordered)
            while n * (factor ** 3) < supercell_size:
                factor += 1
            mat = [[factor, 0, 0], [0, factor, 0], [0, 0, factor]]
            sc.make_supercell(mat)
            return sc, mat, factor ** 3

    # Helper: identify mixing sublattices
    def _get_sublattices(sc: Structure):
        """
        Returns list of sublattice dicts:
          {
            'indices': [site indices with this occupancy pattern],
            'occupancy': {species: target_fraction, ...},
            'species_counts': {species: int},  # integer counts for this sublattice
          }
        Groups sites by their rounded occupancy signature.
        """
        from collections import defaultdict

        # Group by occupancy signature (set of species and fractions, rounded)
        sig_groups: Dict[tuple, List[int]] = defaultdict(list)
        for i, site in enumerate(sc):
            occ = site.species
            sig = tuple(sorted((str(sp), round(float(f), 4)) for sp, f in occ.items()))
            sig_groups[sig].append(i)

        sublattices = []
        for sig, indices in sig_groups.items():
            if len(sig) == 1 and sig[0][1] > 0.9999:
                # Fully ordered site — not a mixing sublattice
                continue

            # Build occupancy dict
            occ_dict = {sp: f for sp, f in sig}
            n_sites = len(indices)

            # Compute integer counts — distribute among species preserving totals
            counts = _int_distribute(occ_dict, n_sites)

            if sum(counts.values()) != n_sites:
                # Fallback: just round
                counts = {sp: round(f * n_sites) for sp, f in occ_dict.items()}

            sublattices.append({
                "indices": indices,
                "occupancy": occ_dict,
                "species_counts": counts,
            })

        return sublattices

    def _int_distribute(fracs: Dict[str, float], n: int) -> Dict[str, int]:
        """Distribute n integers among species according to fractional occupancies.
        Uses the largest-remainder method to ensure exact sum = n."""
        base = {sp: int(f * n) for sp, f in fracs.items()}
        remainder = n - sum(base.values())
        # Sort by fractional part descending and add 1 to top `remainder` species
        frac_parts = sorted(
            [(sp, (f * n) - int(f * n)) for sp, f in fracs.items()],
            key=lambda x: x[1], reverse=True
        )
        for i in range(remainder):
            base[frac_parts[i][0]] += 1
        return base

    # Helper: create random ordered configuration
    def _random_order(sc_disordered: Structure, sublattices: List[Dict], rng: np.random.Generator) -> Structure:
        """
        Replace partial occupancies with a random fully ordered configuration,
        exactly preserving integer stoichiometry per sublattice.
        Returns a new fully ordered Structure.
        """
        species_list = []
        for site in sc_disordered:
            # Each site records a species placeholder — we'll override below
            occ = site.species
            # Default: pick the most abundant species on the site
            dominant = max(occ.items(), key=lambda x: x[1])[0]
            species_list.append(str(dominant))

        for sl in sublattices:
            # Build shuffled assignment list
            assignment: List[str] = []
            for sp, cnt in sl["species_counts"].items():
                assignment.extend([sp] * cnt)
            rng.shuffle(assignment)
            for idx, sp in zip(sl["indices"], assignment):
                species_list[idx] = sp

        return Structure(
            sc_disordered.lattice,
            species_list,
            [site.frac_coords for site in sc_disordered],
        )

    # Helper: detect NN shells
    def _get_shells(struct: Structure, n_shells: int):
        """
        Returns list of shells, each shell = list of (i, j) index pairs.
        Shells are determined by clustering pairwise distances.
        """
        # Use a cutoff that covers at least n_shells shells
        # Estimate: cutoff = n_shells * mean_nn_distance * 1.5
        latt = struct.lattice
        rough_cutoff = min(latt.a, latt.b, latt.c) * (n_shells + 1)

        neighbors = struct.get_all_neighbors(rough_cutoff, include_index=True)

        # Collect all unique distances
        all_dists = []
        for i, nbrs in enumerate(neighbors):
            for nbr in nbrs:
                if nbr[2] > i:  # avoid double counting
                    all_dists.append(round(nbr[1], 4))

        if not all_dists:
            return []

        all_dists_sorted = sorted(set(all_dists))

        # Cluster into shells: new shell when gap > 0.2 Å (or 15% of previous distance)
        shell_boundaries: List[float] = []
        prev = all_dists_sorted[0]
        for d in all_dists_sorted[1:]:
            gap = d - prev
            if gap > max(0.15, 0.15 * prev):
                shell_boundaries.append((prev + d) / 2)
            prev = d

        # Build shell pair lists
        shells: List[List[tuple]] = [[] for _ in range(n_shells)]
        for i, nbrs in enumerate(neighbors):
            for nbr in nbrs:
                j = nbr[2]
                dist = nbr[1]
                # Find which shell
                shell_idx = 0
                for b in shell_boundaries:
                    if dist > b:
                        shell_idx += 1
                    else:
                        break
                if shell_idx < n_shells:
                    shells[shell_idx].append((i, j))

        # Trim empty tail
        while shells and not shells[-1]:
            shells.pop()

        return shells[:n_shells]

    # Helper: compute Warren-Cowley parameters
    def _compute_wc(species_arr: np.ndarray, shells: List[List[tuple]], element_list: List[str]) -> tuple:
        """
        Compute Warren-Cowley short-range order parameters and SQS objective.

        alpha_AB(s) = P(B around A in shell s) / x_B - 1

        For a random alloy: alpha_AB = 0 for all pairs and shells.

        Returns (wc_dict, sqs_error, total_pairs_by_shell).
        wc_dict: {shell_idx: { "A-B": alpha }}
        """
        n_elem = len(element_list)
        elem_idx = {sp: i for i, sp in enumerate(element_list)}

        # Count compositions — only over mixing sublattice sites
        counts = np.zeros(n_elem, dtype=float)
        for sp in species_arr:
            if sp in elem_idx:
                counts[elem_idx[sp]] += 1
        n_mixing = counts.sum()
        if n_mixing == 0:
            return {}, 0.0
        x = counts / n_mixing  # mole fractions of mixing species only

        wc_dict: Dict[int, Dict[str, float]] = {}
        total_error = 0.0

        for s_idx, pairs in enumerate(shells):
            if not pairs or s_idx >= len(_weights):
                continue
            w = _weights[s_idx] if s_idx < len(_weights) else 0.0
            if w == 0.0:
                continue

            # Count pair occurrences — only between mixing sublattice sites
            pair_counts = np.zeros((n_elem, n_elem), dtype=float)
            for (i, j) in pairs:
                sp_i = species_arr[i]
                sp_j = species_arr[j]
                if sp_i not in elem_idx or sp_j not in elem_idx:
                    continue  # skip pairs involving non-mixing (fully-ordered) sites
                a = elem_idx[sp_i]
                b = elem_idx[sp_j]
                pair_counts[a, b] += 1
                pair_counts[b, a] += 1  # undirected

            # Total pairs per origin species
            origin_counts = pair_counts.sum(axis=1)  # how many shell-s neighbours of each species

            shell_wc: Dict[str, float] = {}
            shell_err = 0.0
            for A in range(n_elem):
                if origin_counts[A] == 0 or x[A] == 0:
                    continue
                for B in range(A, n_elem):
                    if x[B] == 0:
                        continue
                    label = f"{element_list[A]}-{element_list[B]}"
                    p_b_given_a = pair_counts[A, B] / origin_counts[A]
                    alpha = p_b_given_a / x[B] - 1.0
                    shell_wc[label] = round(float(alpha), 6)
                    shell_err += alpha ** 2

            wc_dict[s_idx + 1] = shell_wc
            total_error += w * shell_err

        return wc_dict, float(total_error)

    # Helper: delta objective from swapping sites i and j
    def _delta_swap(
        species_arr: np.ndarray,
        i: int,
        j: int,
        shells_adj: List[Dict[int, List[int]]],
        elem_idx: Dict[str, int],
        x: np.ndarray,
    ) -> float:
        """
        Compute the change in SQS objective from swapping species at sites i and j.
        Uses incremental update rather than full recomputation.
        """
        sp_i = species_arr[i]
        sp_j = species_arr[j]
        if sp_i == sp_j:
            return 0.0

        ei = elem_idx[sp_i]
        ej = elem_idx[sp_j]
        n_elem = len(x)

        delta_E = 0.0

        for s_idx, adj in enumerate(shells_adj):
            if s_idx >= len(_weights):
                break
            w = _weights[s_idx]
            if w == 0.0:
                continue

            # Neighbours of i and j in this shell
            nbrs_i = adj.get(i, [])
            nbrs_j = adj.get(j, [])

            # Count how many of each element are neighbours of i and j in this shell
            cnt_i = np.zeros(n_elem, dtype=float)
            cnt_j = np.zeros(n_elem, dtype=float)
            for nb in nbrs_i:
                sp_nb = species_arr[nb]
                if sp_nb in elem_idx:
                    cnt_i[elem_idx[sp_nb]] += 1
            for nb in nbrs_j:
                sp_nb = species_arr[nb]
                if sp_nb in elem_idx:
                    cnt_j[elem_idx[sp_nb]] += 1

            # Check if i is a neighbour of j (or vice versa) in this shell
            i_in_j = i in adj.get(j, [])
            j_in_i = j in adj.get(i, [])

            # We'll compute the contribution to error from sites i and j before and after swap
            # This is an approximation — fast but not exact for fully coupled systems
            # It's sufficient for the Monte Carlo objective
            def _local_alpha_sum(site_idx, neighbours, el_idx):
                """Sum of alpha² involving this site as origin (mixing sites only)."""
                if not neighbours:
                    return 0.0
                cnt = np.zeros(n_elem, dtype=float)
                for nb in neighbours:
                    sp_nb = species_arr[nb]
                    if sp_nb in elem_idx:
                        cnt[elem_idx[sp_nb]] += 1
                total_nbrs = cnt.sum()
                if total_nbrs == 0:
                    return 0.0
                si = elem_idx[species_arr[site_idx]]
                s = 0.0
                for B in range(n_elem):
                    if x[B] > 0:
                        p = cnt[B] / total_nbrs
                        a = p / x[B] - 1.0
                        s += a * a
                return s

            before_i = _local_alpha_sum(i, nbrs_i, elem_idx)
            before_j = _local_alpha_sum(j, nbrs_j, elem_idx)

            # Temporarily swap
            species_arr[i] = sp_j
            species_arr[j] = sp_i

            after_i = _local_alpha_sum(i, nbrs_i, elem_idx)
            after_j = _local_alpha_sum(j, nbrs_j, elem_idx)

            # Undo swap
            species_arr[i] = sp_i
            species_arr[j] = sp_j

            delta_E += w * (after_i + after_j - before_i - before_j)

        return delta_E

    # mcsqs backend
    def _try_mcsqs(disordered: Structure) -> Optional[List[Structure]]:
        """Try to run ATAT mcsqs. Returns list of ordered Structures or None on failure."""
        import shutil
        if not shutil.which("mcsqs"):
            warnings.append(
                "mcsqs binary not found on PATH. "
                "Install ATAT (https://www.brown.edu/Departments/Engineering/Labs/avdw/atat/) "
                "or use the default Monte Carlo backend (use_mcsqs=False)."
            )
            return None
        try:
            from pymatgen.command_line.mcsqs_caller import run_mcsqs
            result = run_mcsqs(
                structure=disordered,
                clusters={2: 4.0, 3: 3.0},
                scaling=supercell_size,
                search_time=mcsqs_timeout / 60.0,
                random_seed=seed or 0,
            )
            if result and result.bestsqs:
                return [result.bestsqs]
        except Exception as e:
            warnings.append(f"mcsqs call failed: {e}. Falling back to Monte Carlo.")
        return None

    # Main loop
    all_structures: List[Any] = []
    all_metadata: List[Dict[str, Any]] = []

    for struct_idx, disordered in enumerate(structures):
        src_formula = disordered.composition.reduced_formula

        # Validate: must have at least one disordered site
        if disordered.is_ordered:
            warnings.append(
                f"Structure '{src_formula}' is already fully ordered (no partial occupancies). "
                "SQS generation requires at least one site with mixed occupancy. Skipping."
            )
            continue

        # Optional mcsqs path
        if use_mcsqs:
            mcsqs_results = _try_mcsqs(disordered)
            if mcsqs_results:
                for mcs in mcsqs_results[:n_structures]:
                    formatted = _format(mcs)
                    if formatted is None:
                        continue
                    meta = {
                        "index": len(all_structures) + 1,
                        "source_formula": src_formula,
                        "sqs_formula": mcs.composition.reduced_formula,
                        "n_sites": len(mcs),
                        "supercell_size": max(1, len(mcs) // max(1, len(disordered))),
                        "sqs_error": None,
                        "warren_cowley": None,
                        "composition": {
                            el.symbol: int(amt)
                            for el, amt in mcs.composition.items()
                        },
                        "n_mc_steps": 0,
                        "backend": "mcsqs",
                        "mcsqs_used": True,
                    }
                    all_structures.append(formatted)
                    all_metadata.append(meta)
                continue  # skip MC for this structure

        # Build supercell
        try:
            sc_disordered, sc_mat_used, sc_det = _build_supercell(disordered)
        except Exception as e:
            warnings.append(f"Failed to build supercell for '{src_formula}': {e}. Skipping.")
            continue

        n_sc_atoms = len(sc_disordered)

        # Identify mixing sublattices
        sublattices = _get_sublattices(sc_disordered)
        if not sublattices:
            warnings.append(
                f"No mixing sublattices found in '{src_formula}' supercell. "
                "Ensure the structure has partial occupancy. Skipping."
            )
            continue

        # Collect all mobile species across sublattices
        all_species_set: set = set()
        for sl in sublattices:
            all_species_set.update(sl["species_counts"].keys())
        element_list = sorted(all_species_set)

        # Build adjacency lists once (for incremental MC delta)
        # First, create a template ordered structure with any valid ordering
        template_rng = np.random.default_rng(seed if seed is not None else 42)
        template_struct = _random_order(sc_disordered, sublattices, template_rng)

        shells = _get_shells(template_struct, n_shells)
        if not shells:
            warnings.append(
                f"No nearest-neighbour shells detected for '{src_formula}'. "
                "Consider reducing supercell_size or n_shells."
            )
            continue

        # Build adjacency dict per shell: site_idx -> list of neighbour site indices
        shells_adj: List[Dict[int, List[int]]] = []
        for shell_pairs in shells:
            adj: Dict[int, List[int]] = {}
            for (i, j) in shell_pairs:
                adj.setdefault(i, []).append(j)
                adj.setdefault(j, []).append(i)
            shells_adj.append(adj)

        # Identify all swappable site pairs per sublattice
        # For each sublattice, group site indices by current species
        # (needed for efficient random swap selection)

        # Monte Carlo loop across n_structures candidates
        elem_idx = {sp: i for i, sp in enumerate(element_list)}

        candidates: List[Dict[str, Any]] = []  # {species_arr, error, wc_dict}

        for cand_idx in range(n_structures):
            # Seed per candidate = derived from global seed
            cand_seed = None if seed is None else seed + struct_idx * 1000 + cand_idx
            rng = np.random.default_rng(cand_seed)

            # Random initial ordering
            cur_struct = _random_order(sc_disordered, sublattices, rng)
            species_arr = np.array([site.specie.symbol for site in cur_struct], dtype=object)

            # Compute initial composition mole fractions (for WC params)
            # Divide by mixing-site count only (exclude fully-ordered sites)
            counts = np.zeros(len(element_list), dtype=float)
            for sp in species_arr:
                if sp in elem_idx:
                    counts[elem_idx[sp]] += 1
            n_mixing_sites = counts.sum()
            x = counts / n_mixing_sites if n_mixing_sites > 0 else counts

            # Compute initial error
            current_wc, current_error = _compute_wc(species_arr, shells, element_list)

            best_species = species_arr.copy()
            best_error = current_error
            best_wc = current_wc

            # Build per-sublattice site lists for swapping
            # A sublattice site list: just the indices that belong to mixing sublattices
            mixing_indices: List[int] = []
            for sl in sublattices:
                mixing_indices.extend(sl["indices"])
            mixing_indices = list(set(mixing_indices))

            # Map site index → sublattice index
            site_to_sl: Dict[int, int] = {}
            for sl_i, sl in enumerate(sublattices):
                for idx in sl["indices"]:
                    site_to_sl[idx] = sl_i

            # Precompute per-sublattice lists of (index, species) for O(1) random selection
            sl_site_lists: List[List[int]] = [list(sl["indices"]) for sl in sublattices]

            steps_done = 0
            for step in range(n_mc_steps):
                # Pick a random sublattice
                sl_i = int(rng.integers(0, len(sublattices)))
                sl_sites = sl_site_lists[sl_i]
                if len(sl_sites) < 2:
                    continue

                # Pick two random sites on this sublattice with different species
                max_tries = 10
                found = False
                for _ in range(max_tries):
                    ai, bi = rng.integers(0, len(sl_sites), size=2)
                    if ai == bi:
                        continue
                    site_a = sl_sites[int(ai)]
                    site_b = sl_sites[int(bi)]
                    if species_arr[site_a] != species_arr[site_b]:
                        found = True
                        break
                if not found:
                    continue

                # Fast incremental delta evaluation
                dE = _delta_swap(species_arr, site_a, site_b, shells_adj, elem_idx, x)

                if dE < 0:
                    # Accept: apply swap
                    species_arr[site_a], species_arr[site_b] = (
                        species_arr[site_b], species_arr[site_a]
                    )
                    current_error += dE
                    if current_error < best_error:
                        best_species = species_arr.copy()
                        best_error = current_error

                steps_done += 1

            # Compute final WC parameters from best configuration
            final_wc, final_error = _compute_wc(best_species, shells, element_list)
            best_error = final_error  # use exact value

            candidates.append({
                "species_arr": best_species,
                "error": best_error,
                "wc_dict": final_wc,
                "n_steps": steps_done,
            })

        # Sort candidates
        if sort_by == "sqs_error":
            candidates.sort(key=lambda c: c["error"])

        # Build output structures
        for cand in candidates:
            ordered_struct = Structure(
                sc_disordered.lattice,
                list(cand["species_arr"]),
                [site.frac_coords for site in sc_disordered],
            )

            formatted = _format(ordered_struct)
            if formatted is None:
                continue

            comp_dict = {
                el.symbol: int(amt)
                for el, amt in ordered_struct.composition.items()
            }

            meta = {
                "index": len(all_structures) + 1,
                "source_formula": src_formula,
                "sqs_formula": ordered_struct.composition.reduced_formula,
                "n_sites": len(ordered_struct),
                "supercell_size": sc_det,
                "sqs_error": round(float(cand["error"]), 8),
                "warren_cowley": {
                    f"shell_{s}": v for s, v in cand["wc_dict"].items()
                },
                "composition": comp_dict,
                "n_mc_steps": cand["n_steps"],
                "backend": "monte_carlo",
                "mcsqs_used": False,
            }
            all_structures.append(formatted)
            all_metadata.append(meta)

    # Final response
    if not all_structures:
        return {
            "success": False,
            "error": "No SQS structures could be generated with the given parameters.",
            "warnings": warnings if warnings else None,
        }

    input_info = {
        "n_input_structures": len(structures),
        "input_formulas": [s.composition.reduced_formula for s in structures],
    }

    sqs_params = {
        "supercell_size_target": supercell_size,
        "supercell_matrix": supercell_matrix,
        "n_structures": n_structures,
        "n_mc_steps": n_mc_steps,
        "n_shells": n_shells,
        "shell_weights": list(_weights),
        "sort_by": sort_by,
        "seed": seed,
        "use_mcsqs": use_mcsqs,
        "output_format": output_format,
    }

    result: Dict[str, Any] = {
        "success": True,
        "count": len(all_structures),
        "structures": all_structures,
        "metadata": all_metadata,
        "input_info": input_info,
        "sqs_params": sqs_params,
        "message": (
            f"Generated {len(all_structures)} SQS structure(s) from "
            f"{len(structures)} input structure(s) using the "
            f"{'mcsqs' if use_mcsqs else 'Monte Carlo'} backend."
        ),
    }
    if warnings:
        result["warnings"] = warnings
    return result
