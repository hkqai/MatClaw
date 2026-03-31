"""
Tool for generating defect supercells for point-defect calculations.

Creates supercells containing a single point defect (vacancy, substitutional, or interstitial)
at every symmetry-inequivalent site of the host structure.  Each returned structure is
charge-neutral (the charge state is tracked in metadata only) and is ready for direct use
in DFT electronic-structure calculations or further perturbation via
pymatgen_perturbation_generator.
"""

from typing import Dict, Any, Optional, List, Union, Annotated
from pydantic import Field


def pymatgen_defect_generator(
    input_structure: Annotated[
        Union[Dict[str, Any], str],
        Field(
            description=(
                "Bulk host structure as a pymatgen Structure dict (from Structure.as_dict()), "
                "or a CIF string.  This is the perfect, defect-free reference cell — typically "
                "the output of pymatgen_prototype_builder, pymatgen_substitution_generator, "
                "pymatgen_ion_exchange_generator, or an mp_get_material_properties structure."
            )
        )
    ],
    vacancy_species: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description=(
                "Element symbol(s) for which to generate vacancy defects. "
                "Example: ['Li', 'O'] generates V_Li and V_O defects. "
                "One supercell is generated per symmetry-inequivalent site of each species. "
                "If None and no other defect type is requested, vacancies for ALL species "
                "in the structure are generated."
            )
        )
    ] = None,
    substitution_species: Annotated[
        Optional[Dict[str, Union[str, List[str]]]],
        Field(
            default=None,
            description=(
                "Substitutional point defects to generate.  Maps the host species to be "
                "replaced to the dopant species (or list of dopant species). "
                "Example: {'Li': 'Na', 'Fe': ['Mn', 'Co']} generates Na_Li, Mn_Fe, and Co_Fe "
                "defects.  One supercell is created per symmetry-inequivalent site of the "
                "host species for each dopant."
            )
        )
    ] = None,
    interstitial_species: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description=(
                "Element symbol(s) to insert as interstitial defects. "
                "Example: ['Li'] searches for symmetry-inequivalent void sites and places a "
                "Li atom at each one.  Void sites are found by a Voronoi-based search on the "
                "bulk cell and then mapped into the supercell. "
                "Interstitial finding is a best-effort heuristic; review sites before use."
            )
        )
    ] = None,
    charge_states: Annotated[
        Optional[Dict[str, List[int]]],
        Field(
            default=None,
            description=(
                "Charge states to associate with each defect label in the metadata. "
                "The structure itself is always the neutral defect geometry; charge states "
                "are recorded only in per-structure metadata for DFT setup. "
                "Keys use the standard notation: 'V_Li', 'Na_Li', 'Li_i'. "
                "Example: {'V_Li': [-1, 0, 1], 'Na_Li': [0, 1]}. "
                "If a defect label is not listed here, suggested charge states are "
                "automatically estimated from standard oxidation states."
            )
        )
    ] = None,
    supercell_min_atoms: Annotated[
        int,
        Field(
            default=64,
            ge=8,
            le=512,
            description=(
                "Target minimum number of atoms in the defect supercell (8–512). "
                "The tool finds the smallest uniform scaling that meets this threshold. "
                "Typical values: 64–128 for DFT with plane-wave codes. "
                "Ignored when supercell_matrix is provided explicitly. "
                "Default: 64."
            )
        )
    ] = 64,
    supercell_matrix: Annotated[
        Optional[Union[List[int], List[List[int]]]],
        Field(
            default=None,
            description=(
                "Explicit supercell expansion matrix.  List of 3 integers [nx, ny, nz] for "
                "diagonal scaling, or a 3×3 list of lists for a full transformation matrix. "
                "Example: [2, 2, 2] creates a 2×2×2 supercell. "
                "When provided, supercell_min_atoms is ignored."
            )
        )
    ] = None,
    inequivalent_only: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True (default), uses space-group symmetry of the bulk cell to identify "
                "symmetry-inequivalent sites and generates only one defect supercell per "
                "distinct Wyckoff site.  This is strongly recommended to avoid redundant DFT "
                "calculations. "
                "If False, generates one defect supercell for every site of the specified "
                "species regardless of symmetry equivalence."
            )
        )
    ] = True,
    interstitial_min_dist: Annotated[
        float,
        Field(
            default=1.0,
            ge=0.5,
            le=3.0,
            description=(
                "Minimum distance (Å) a candidate interstitial site must have from all "
                "existing atoms to be accepted (0.5–3.0). "
                "Increase to filter out sites in very tight voids. "
                "Default: 1.0 Å."
            )
        )
    ] = 1.0,
    max_interstitial_sites: Annotated[
        int,
        Field(
            default=5,
            ge=1,
            le=20,
            description=(
                "Maximum number of inequivalent interstitial sites to return per species (1–20). "
                "Sites are ranked by the distance to the nearest host atom (largest void first). "
                "Default: 5."
            )
        )
    ] = 5,
    symm_prec: Annotated[
        float,
        Field(
            default=0.1,
            ge=0.001,
            le=0.5,
            description=(
                "Symmetry tolerance in Ångströms passed to SpacegroupAnalyzer (0.001–0.5). "
                "Default: 0.1 Å."
            )
        )
    ] = 0.1,
    output_format: Annotated[
        str,
        Field(
            default="dict",
            description=(
                "Output format for returned structures. "
                "'dict': pymatgen Structure.as_dict() — round-trippable, default. "
                "'poscar': VASP POSCAR string. "
                "'cif': CIF string. "
                "'json': JSON-serialised Structure dict string."
            )
        )
    ] = "dict"
) -> Dict[str, Any]:
    """
    Generate defect supercells for point-defect calculations in inorganic materials.

    For each requested defect type and species, the tool:
      1. Standardises the bulk host cell and identifies symmetry-inequivalent sites
         using pymatgen's SpacegroupAnalyzer.
      2. Constructs a supercell of the requested size.
      3. Creates one defect supercell per inequivalent site (vacancy: remove atom;
         substitution: replace atom; interstitial: insert atom at void site).
      4. Records rich metadata for each structure including the defect label, Wyckoff
         position, site index, suggested charge states, and host formula.

    The output structures are compatible with all other pymatgen tools in this suite:
      - Use as input to pymatgen_perturbation_generator to generate displaced ensembles
        around the defect geometry.
      - Pass structure dicts directly to ase_store_result for database archiving.
      - Feed into VASP/GPAW/CASTEP workflows via the 'poscar' output format.

    Returns
   ----
    dict:
        success             (bool)  Whether at least one defect supercell was generated.
        count               (int)   Total number of defect supercells generated.
        structures          (list)  Defect supercells in the requested output_format.
        metadata            (list)  Per-structure metadata:
            index               (int)   1-based sequential index.
            defect_type         (str)   'vacancy', 'substitution', or 'interstitial'.
            defect_label        (str)   Standard notation: 'V_Li', 'Na_Li', 'Li_i'.
            host_species        (str)   Element being removed / replaced (or site host for interstitial).
            dopant_species      (str)   Inserted element (None for vacancies).
            wyckoff_symbol      (str)   Wyckoff letter of the defect site in the bulk cell.
            site_index_bulk     (int)   Index of the representative site in the bulk cell.
            site_index_supercell(int)   Index of the defect site in the supercell.
            site_coords_frac    (list)  Fractional coordinates of defect in supercell.
            site_coords_cart    (list)  Cartesian coordinates of defect (Å) in supercell.
            supercell_formula   (str)   Reduced formula of the defect supercell.
            n_sites_supercell   (int)   Number of atoms in the defect supercell.
            host_formula        (str)   Reduced formula of the bulk host.
            supercell_size      (int)   Expansion factor relative to the input cell.
            charge_states       (list)  Charge states to calculate (from input or auto-estimated).
            suggested_charge_states (list)  Automatically estimated charge states.
        host_info           (dict)  Summary of the bulk host structure.
        supercell_info      (dict)  Supercell generation parameters used.
        defect_params       (dict)  All defect-type parameters used.
        message             (str)   Human-readable status message.
        warnings            (list)  Non-fatal warnings (may be absent if none).
        error               (str)   Error message if success=False.
    """
    import numpy as np

    # Imports
    try:
        from pymatgen.core import Structure, Element, Lattice
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import pymatgen: {e}. Install with: pip install pymatgen"
        }

    # Validate output_format
    valid_formats = {"dict", "poscar", "cif", "json"}
    if output_format not in valid_formats:
        return {
            "success": False,
            "error": f"Invalid output_format '{output_format}'. Must be one of {sorted(valid_formats)}."
        }

    # Validate supercell_matrix
    if supercell_matrix is not None:
        if isinstance(supercell_matrix, list):
            if len(supercell_matrix) == 3 and all(isinstance(x, int) for x in supercell_matrix):
                # [nx, ny, nz] diagonal — convert to 3x3
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
    else:
        _sc_matrix = None

    # Check that at least one defect type is requested
    if vacancy_species is None and substitution_species is None and interstitial_species is None:
        # Default: vacancies for all species
        vacancy_species = None  # handled below after parsing bulk

    # Parse input structure
    try:
        if isinstance(input_structure, dict):
            bulk = Structure.from_dict(input_structure)
        elif isinstance(input_structure, str):
            bulk = Structure.from_str(input_structure, fmt="cif")
        else:
            return {
                "success": False,
                "error": f"input_structure must be a dict or CIF string, got {type(input_structure).__name__}."
            }
    except Exception as e:
        return {"success": False, "error": f"Failed to parse input_structure: {e}"}

    host_formula = bulk.composition.reduced_formula
    n_bulk_atoms = len(bulk)

    # If no defect types specified at all, default to vacancies for all species
    _all_elements = [el.symbol for el in bulk.composition.elements]
    if vacancy_species is None and substitution_species is None and interstitial_species is None:
        vacancy_species = _all_elements

    warnings: List[str] = []

    # Analyse bulk symmetry
    try:
        sga = SpacegroupAnalyzer(bulk, symprec=symm_prec)
        sym_bulk = sga.get_symmetrized_structure()
        sg_number = sga.get_space_group_number()
        sg_symbol = sga.get_space_group_symbol()
    except Exception as e:
        return {"success": False, "error": f"Symmetry analysis of bulk structure failed: {e}"}

    # equiv_groups: list of lists of site indices that are symmetry-equivalent in the bulk
    equiv_groups: List[List[int]] = sym_bulk.equivalent_indices

    # Build map: site_index -> (wyckoff_letter, group_index)
    site_wyckoff: Dict[int, str] = {}
    try:
        wyckoff_info = sga.get_symmetry_dataset()
        _wyckoff_letters = wyckoff_info.get("wyckoffs", [])
        for i, wl in enumerate(_wyckoff_letters):
            site_wyckoff[i] = wl
    except Exception:
        pass  # Wyckoff letters will be None if this fails

    def _get_wyckoff(site_idx: int) -> Optional[str]:
        return site_wyckoff.get(site_idx, None)

    def _inequivalent_sites_for_species(species_symbol: str) -> List[Dict[str, Any]]:
        """
        Return one representative site per inequivalent Wyckoff position for the given species.
        Each entry: {site_index, wyckoff, frac_coords, cart_coords}.
        """
        result_sites = []
        for group in equiv_groups:
            # Check if any site in this group matches the species
            rep_idx = group[0]
            if bulk[rep_idx].specie.symbol != species_symbol:
                continue
            wl = _get_wyckoff(rep_idx)
            result_sites.append({
                "site_index": rep_idx,
                "wyckoff": wl,
                "frac_coords": list(bulk[rep_idx].frac_coords),
                "cart_coords": list(bulk[rep_idx].coords),
                "n_equivalent": len(group),
            })
        return result_sites

    def _all_sites_for_species(species_symbol: str) -> List[Dict[str, Any]]:
        """Return every site of the given species (no symmetry deduplication)."""
        return [
            {
                "site_index": i,
                "wyckoff": _get_wyckoff(i),
                "frac_coords": list(bulk[i].frac_coords),
                "cart_coords": list(bulk[i].coords),
                "n_equivalent": 1,
            }
            for i in range(n_bulk_atoms)
            if bulk[i].specie.symbol == species_symbol
        ]

    # Build supercell
    def _build_supercell(host: Structure) -> tuple:
        """Return (supercell, scaling_matrix, scale_factor)."""
        sc = host.copy()
        if _sc_matrix is not None:
            sc.make_supercell(_sc_matrix)
            det = int(round(abs(
                np.linalg.det(np.array(_sc_matrix, dtype=float))
            )))
            return sc, _sc_matrix, det
        else:
            # Find smallest uniform scaling that gives >= supercell_min_atoms
            n = len(host)
            factor = 1
            while n * (factor ** 3) < supercell_min_atoms:
                factor += 1
            mat = [[factor, 0, 0], [0, factor, 0], [0, 0, factor]]
            sc.make_supercell(mat)
            return sc, mat, factor ** 3

    try:
        supercell_template, sc_matrix_used, sc_det = _build_supercell(bulk)
    except Exception as e:
        return {"success": False, "error": f"Failed to build supercell: {e}"}

    sc_formula = supercell_template.composition.reduced_formula
    n_sc_atoms = len(supercell_template)

    # Charge state helpers
    def _suggest_charge_states(defect_type: str, host_sym: str, dopant_sym: Optional[str]) -> List[int]:
        """
        Estimate charge states using standard oxidation state rules.
          - Vacancy V_X: charge = -(oxi_state of X)  ± 1 broadening
          - Substitution D_X: charge = oxi_D - oxi_X  ± 1 broadening
          - Interstitial X_i: charge = common oxi states of X
        Returns a small list of integers covering the likely range.
        """
        try:
            def _oxi(sym: str) -> int:
                el = Element(sym)
                states = el.common_oxidation_states
                return int(states[0]) if states else 0

            if defect_type == "vacancy":
                oxi_host = _oxi(host_sym)
                q = -oxi_host
                return sorted({q - 1, q, q + 1})
            elif defect_type == "substitution":
                oxi_host = _oxi(host_sym)
                oxi_dop = _oxi(dopant_sym)
                q = oxi_dop - oxi_host
                return sorted({q - 1, q, q + 1})
            elif defect_type == "interstitial":
                el = Element(host_sym)
                states = list(el.common_oxidation_states)
                if not states:
                    states = [0]
                return sorted(states)
        except Exception:
            pass
        return [0]

    # Formatting helper
    def _format_structure(struct: Structure) -> Any:
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
            return None

    # Map bulk frac_coords onto supercell site index
    def _find_supercell_site(sc: Structure, bulk_frac_coords: List[float], sc_matrix: List[List[int]]) -> int:
        """
        Return the index in the supercell of the atom corresponding to
        bulk site at bulk_frac_coords.  The supercell fractional coords of
        the image at [0,0,0] translation are bulk_frac / (nx, ny, nz).
        """
        sc_matrix_arr = np.array(sc_matrix, dtype=float)
        # Fractional coords in supercell = M^{-T} @ bulk_frac
        inv_mt = np.linalg.inv(sc_matrix_arr.T)
        sc_frac = inv_mt @ np.array(bulk_frac_coords)
        sc_frac = sc_frac % 1.0  # wrap to [0, 1)

        # Find closest site in supercell
        best_idx = 0
        best_dist = float("inf")
        for i, site in enumerate(sc):
            diff = sc_frac - site.frac_coords
            diff -= np.round(diff)  # minimum image
            dist = float(np.linalg.norm(diff))
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        return best_idx

    # Main generation loop
    generated_structures: List[Any] = []
    metadata_list: List[Dict[str, Any]] = []

    # 1. VACANCIES
    if vacancy_species:
        for species_sym in vacancy_species:
            if not any(el.symbol == species_sym for el in bulk.composition.elements):
                warnings.append(
                    f"Vacancy requested for '{species_sym}' but this element is not in the "
                    f"bulk structure ({host_formula}). Skipping."
                )
                continue

            sites = (
                _inequivalent_sites_for_species(species_sym)
                if inequivalent_only
                else _all_sites_for_species(species_sym)
            )

            if not sites:
                warnings.append(f"No sites found for vacancy species '{species_sym}'. Skipping.")
                continue

            defect_label_base = f"V_{species_sym}"
            suggested_q = _suggest_charge_states("vacancy", species_sym, None)
            user_q = (charge_states or {}).get(defect_label_base, None)
            final_q = user_q if user_q is not None else suggested_q

            for site_info in sites:
                # Build a fresh supercell copy for each defect
                sc = supercell_template.copy()
                sc_site_idx = _find_supercell_site(sc, site_info["frac_coords"], sc_matrix_used)

                # Record site coordinates before removal
                defect_frac = list(sc[sc_site_idx].frac_coords)
                defect_cart = list(sc[sc_site_idx].coords)

                # Remove the site (create vacancy)
                sc.remove_sites([sc_site_idx])

                formatted = _format_structure(sc)
                if formatted is None:
                    warnings.append(
                        f"Could not format vacancy {defect_label_base} at site "
                        f"{site_info['site_index']}. Skipping."
                    )
                    continue

                meta = {
                    "index": len(generated_structures) + 1,
                    "defect_type": "vacancy",
                    "defect_label": defect_label_base,
                    "host_species": species_sym,
                    "dopant_species": None,
                    "wyckoff_symbol": site_info["wyckoff"],
                    "site_index_bulk": site_info["site_index"],
                    "site_index_supercell": sc_site_idx,
                    "site_coords_frac": defect_frac,
                    "site_coords_cart": defect_cart,
                    "n_equivalent_bulk": site_info["n_equivalent"],
                    "supercell_formula": sc.composition.reduced_formula,
                    "n_sites_supercell": len(sc),
                    "host_formula": host_formula,
                    "supercell_size": sc_det,
                    "charge_states": final_q,
                    "suggested_charge_states": suggested_q,
                }
                generated_structures.append(formatted)
                metadata_list.append(meta)

    # 2. SUBSTITUTIONS
    if substitution_species:
        for host_sym, dopant_val in substitution_species.items():
            dopants = [dopant_val] if isinstance(dopant_val, str) else list(dopant_val)

            if not any(el.symbol == host_sym for el in bulk.composition.elements):
                warnings.append(
                    f"Substitution requested on host species '{host_sym}' but this element "
                    f"is not in the bulk structure ({host_formula}). Skipping."
                )
                continue

            sites = (
                _inequivalent_sites_for_species(host_sym)
                if inequivalent_only
                else _all_sites_for_species(host_sym)
            )

            if not sites:
                warnings.append(f"No sites found for substitution host species '{host_sym}'. Skipping.")
                continue

            for dopant_sym in dopants:
                # Validate dopant element
                try:
                    Element(dopant_sym)
                except ValueError:
                    warnings.append(f"'{dopant_sym}' is not a valid element symbol. Skipping.")
                    continue

                if dopant_sym == host_sym:
                    warnings.append(
                        f"Substitution {dopant_sym}_{host_sym} is a self-substitution (same element). "
                        "Skipping."
                    )
                    continue

                defect_label_base = f"{dopant_sym}_{host_sym}"
                suggested_q = _suggest_charge_states("substitution", host_sym, dopant_sym)
                user_q = (charge_states or {}).get(defect_label_base, None)
                final_q = user_q if user_q is not None else suggested_q

                for site_info in sites:
                    sc = supercell_template.copy()
                    sc_site_idx = _find_supercell_site(sc, site_info["frac_coords"], sc_matrix_used)

                    defect_frac = list(sc[sc_site_idx].frac_coords)
                    defect_cart = list(sc[sc_site_idx].coords)

                    # Replace species at that site
                    sc.replace(sc_site_idx, dopant_sym)

                    formatted = _format_structure(sc)
                    if formatted is None:
                        warnings.append(
                            f"Could not format substitution {defect_label_base} at site "
                            f"{site_info['site_index']}. Skipping."
                        )
                        continue

                    meta = {
                        "index": len(generated_structures) + 1,
                        "defect_type": "substitution",
                        "defect_label": defect_label_base,
                        "host_species": host_sym,
                        "dopant_species": dopant_sym,
                        "wyckoff_symbol": site_info["wyckoff"],
                        "site_index_bulk": site_info["site_index"],
                        "site_index_supercell": sc_site_idx,
                        "site_coords_frac": defect_frac,
                        "site_coords_cart": defect_cart,
                        "n_equivalent_bulk": site_info["n_equivalent"],
                        "supercell_formula": sc.composition.reduced_formula,
                        "n_sites_supercell": len(sc),
                        "host_formula": host_formula,
                        "supercell_size": sc_det,
                        "charge_states": final_q,
                        "suggested_charge_states": suggested_q,
                    }
                    generated_structures.append(formatted)
                    metadata_list.append(meta)

    # 3. INTERSTITIALS
    if interstitial_species:
        for species_sym in interstitial_species:
            try:
                Element(species_sym)
            except ValueError:
                warnings.append(f"'{species_sym}' is not a valid element symbol for interstitial. Skipping.")
                continue

            # Find void sites in the BULK cell using a Voronoi-node approach
            void_sites = _find_void_sites(
                bulk, species_sym,
                min_dist=interstitial_min_dist,
                max_sites=max_interstitial_sites,
                symm_prec=symm_prec,
                inequivalent_only=inequivalent_only,
                warnings=warnings,
            )

            if not void_sites:
                warnings.append(
                    f"No valid interstitial void sites found for '{species_sym}' in "
                    f"{host_formula} with min_dist={interstitial_min_dist} Å. Skipping."
                )
                continue

            defect_label_base = f"{species_sym}_i"
            suggested_q = _suggest_charge_states("interstitial", species_sym, None)
            user_q = (charge_states or {}).get(defect_label_base, None)
            final_q = user_q if user_q is not None else suggested_q

            for void_info in void_sites:
                # Map bulk void frac_coords into the supercell
                sc = supercell_template.copy()
                sc_matrix_arr = np.array(sc_matrix_used, dtype=float)
                inv_mt = np.linalg.inv(sc_matrix_arr.T)
                void_frac_bulk = np.array(void_info["frac_coords"])
                void_frac_sc = inv_mt @ void_frac_bulk
                void_frac_sc = void_frac_sc % 1.0

                # Insert the interstitial atom
                sc.append(species_sym, void_frac_sc, coords_are_cartesian=False)
                interstitial_site_idx = len(sc) - 1

                defect_frac = [float(x) for x in void_frac_sc]
                defect_cart = list(sc[-1].coords)

                formatted = _format_structure(sc)
                if formatted is None:
                    warnings.append(
                        f"Could not format interstitial {defect_label_base}. Skipping."
                    )
                    continue

                meta = {
                    "index": len(generated_structures) + 1,
                    "defect_type": "interstitial",
                    "defect_label": defect_label_base,
                    "host_species": species_sym,
                    "dopant_species": species_sym,
                    "wyckoff_symbol": void_info.get("wyckoff", None),
                    "site_index_bulk": None,
                    "site_index_supercell": interstitial_site_idx,
                    "site_coords_frac": defect_frac,
                    "site_coords_cart": defect_cart,
                    "n_equivalent_bulk": void_info.get("n_equivalent", 1),
                    "void_min_dist_ang": round(float(void_info["min_dist"]), 4),
                    "supercell_formula": sc.composition.reduced_formula,
                    "n_sites_supercell": len(sc),
                    "host_formula": host_formula,
                    "supercell_size": sc_det,
                    "charge_states": final_q,
                    "suggested_charge_states": suggested_q,
                }
                generated_structures.append(formatted)
                metadata_list.append(meta)

    # Final response
    if not generated_structures:
        return {
            "success": False,
            "error": "No defect supercells could be generated with the given parameters.",
            "warnings": warnings if warnings else None,
        }

    host_info = {
        "formula": host_formula,
        "n_atoms": n_bulk_atoms,
        "space_group_number": sg_number,
        "space_group_symbol": sg_symbol,
        "lattice": {
            "a": round(bulk.lattice.a, 6),
            "b": round(bulk.lattice.b, 6),
            "c": round(bulk.lattice.c, 6),
            "alpha": round(bulk.lattice.alpha, 4),
            "beta": round(bulk.lattice.beta, 4),
            "gamma": round(bulk.lattice.gamma, 4),
            "volume": round(bulk.lattice.volume, 4),
        },
    }

    supercell_info = {
        "n_atoms_supercell": n_sc_atoms,
        "supercell_formula": sc_formula,
        "supercell_matrix": sc_matrix_used,
        "supercell_size": sc_det,
        "supercell_min_atoms_requested": supercell_min_atoms,
        "explicit_matrix_provided": supercell_matrix is not None,
    }

    defect_params = {
        "vacancy_species": vacancy_species,
        "substitution_species": substitution_species,
        "interstitial_species": interstitial_species,
        "inequivalent_only": inequivalent_only,
        "symm_prec": symm_prec,
        "output_format": output_format,
    }

    n_vac = sum(1 for m in metadata_list if m["defect_type"] == "vacancy")
    n_sub = sum(1 for m in metadata_list if m["defect_type"] == "substitution")
    n_int = sum(1 for m in metadata_list if m["defect_type"] == "interstitial")
    parts = []
    if n_vac:
        parts.append(f"{n_vac} vacancy")
    if n_sub:
        parts.append(f"{n_sub} substitution")
    if n_int:
        parts.append(f"{n_int} interstitial")

    result: Dict[str, Any] = {
        "success": True,
        "count": len(generated_structures),
        "structures": generated_structures,
        "metadata": metadata_list,
        "host_info": host_info,
        "supercell_info": supercell_info,
        "defect_params": defect_params,
        "message": (
            f"Generated {len(generated_structures)} defect supercell(s) for {host_formula} "
            f"({', '.join(parts)}) in a {sc_det}× supercell ({n_sc_atoms} atoms, "
            f"SG {sg_number} {sg_symbol})."
        ),
    }
    if warnings:
        result["warnings"] = warnings
    return result


#
# Interstitial void-site finder
#

def _find_void_sites(
    structure,
    species_sym: str,
    min_dist: float,
    max_sites: int,
    symm_prec: float,
    inequivalent_only: bool,
    warnings: List,
) -> List[Dict[str, Any]]:
    """
    Find candidate interstitial void sites in the bulk cell.

    Uses a regular fractional-coordinate grid (20×20×20 = 8000 candidate points),
    computes the minimum distance to all existing atoms for each point, discards
    points within min_dist of any atom, then:
      1. If inequivalent_only=True, clusters grid points by symmetry using
         SpacegroupAnalyzer and returns one representative per cluster.
      2. Returns up to max_sites sites ranked by largest void radius (most spacious first).

    This approach is reliable for finding common high-symmetry interstitial sites
    (octahedral, tetrahedral voids in close-packed structures) without requiring
    external dependencies.
    """
    import numpy as np
    from pymatgen.core import Structure

    try:
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
    except ImportError:
        pass

    # Build fractional coordinate grid over the unit cell
    GRID = 20
    coords = np.array([
        [i / GRID, j / GRID, k / GRID]
        for i in range(GRID)
        for j in range(GRID)
        for k in range(GRID)
    ])  # shape: (GRID^3, 3)

    # Get all Cartesian positions of existing atoms (with periodic images via
    # nearest image convention handled by the distance matrix below)
    lattice_matrix = np.array(structure.lattice.matrix)  # (3, 3)

    # Convert all grid points to Cartesian once
    cart_grid = coords @ lattice_matrix  # (N_grid, 3)

    # For each grid point find the minimum image distance to any atom
    atom_frac = np.array([site.frac_coords for site in structure])  # (N_atoms, 3)
    atom_cart = atom_frac @ lattice_matrix  # (N_atoms, 3)

    # Compute minimum image distances with periodic boundary conditions
    # diff shape: (N_grid, N_atoms, 3)
    diff_frac = coords[:, None, :] - atom_frac[None, :, :]  # (N_grid, N_atoms, 3)
    diff_frac -= np.round(diff_frac)                         # minimum image in frac
    diff_cart = diff_frac @ lattice_matrix                   # (N_grid, N_atoms, 3)
    distances = np.sqrt(np.sum(diff_cart ** 2, axis=2))      # (N_grid, N_atoms)
    min_dists = distances.min(axis=1)                        # (N_grid,)

    # Filter by minimum distance threshold
    valid_mask = min_dists >= min_dist
    valid_indices = np.where(valid_mask)[0]

    if len(valid_indices) == 0:
        return []

    valid_coords = coords[valid_indices]      # fractional
    valid_min_dists = min_dists[valid_indices]

    # Sort by largest void (descending)
    sort_order = np.argsort(-valid_min_dists)
    valid_coords = valid_coords[sort_order]
    valid_min_dists = valid_min_dists[sort_order]

    if inequivalent_only:
        # Cluster by symmetry: for each candidate point, check if it is
        # equivalent to an already-accepted point under the space group operations.
        try:
            from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
            sga = SpacegroupAnalyzer(structure, symprec=symm_prec)
            sym_ops = sga.get_symmetry_operations()  # fractional-space operations
        except Exception as e:
            warnings.append(
                f"Could not get symmetry operations for interstitial deduplication: {e}. "
                "Returning all candidate sites without symmetry filtering."
            )
            sym_ops = []

        accepted: List[np.ndarray] = []

        def _is_equivalent_to_accepted(frac_pt: np.ndarray) -> bool:
            """Check if frac_pt is equivalent to any already-accepted site."""
            for op in sym_ops:
                rotated = op.operate(frac_pt) % 1.0
                for acc in accepted:
                    diff = rotated - acc
                    diff -= np.round(diff)
                    if np.linalg.norm(diff @ lattice_matrix) < symm_prec * 3:
                        return True
            return False

        unique_coords: List[np.ndarray] = []
        unique_dists: List[float] = []
        wyckoff_labels: List[Optional[str]] = []

        for i in range(len(valid_coords)):
            pt = valid_coords[i]
            if not _is_equivalent_to_accepted(pt):
                accepted.append(pt)
                unique_coords.append(pt)
                unique_dists.append(float(valid_min_dists[i]))
                wyckoff_labels.append(None)  # interstitials don't have Wyckoff labels a priori
                if len(unique_coords) >= max_sites:
                    break

        result_coords = unique_coords
        result_dists = unique_dists
        result_wyckoffs = wyckoff_labels
    else:
        n_take = min(max_sites, len(valid_coords))
        result_coords = [valid_coords[i] for i in range(n_take)]
        result_dists = [float(valid_min_dists[i]) for i in range(n_take)]
        result_wyckoffs = [None] * n_take

    void_sites = []
    for frac, d, wl in zip(result_coords, result_dists, result_wyckoffs):
        void_sites.append({
            "frac_coords": [float(x) for x in frac],
            "min_dist": d,
            "wyckoff": wl,
            "n_equivalent": 1,
        })

    return void_sites
