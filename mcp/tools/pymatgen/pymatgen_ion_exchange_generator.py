"""
Tool for performing charge-neutral ion-exchange operations on structures.
Replaces a mobile ion (e.g., Li) with one or more new ions (e.g., Na, Mg),
automatically adjusting stoichiometry to maintain charge neutrality.
Supports partial exchange, multiple replacement ions, and returns only charge-neutral structures.
"""

from typing import Dict, Any, Optional, List, Union, Annotated
from pydantic import Field
import random


def pymatgen_ion_exchange_generator(
    input_structures: Annotated[
        Union[Dict[str, Any], List[Dict[str, Any]], str, List[str]],
        Field(description=(
            "Input structure(s) to apply ion exchange to. Can be: single Structure dict "
            "(from Structure.as_dict()), list of dicts, CIF string, or list of CIF strings."
        ))
    ],
    replace_ion: Annotated[
        str,
        Field(description="Mobile ion species to replace, e.g. 'Li'.")
    ],
    with_ions: Annotated[
        Union[List[str], Dict[str, float]],
        Field(description=(
            "Replacement ion(s). "
            "List form: ['Na', 'K'] — each ion gets equal weight from exchange_fraction. "
            "Dict form: {'Na': 0.6, 'Mg': 0.4} — relative weights used to split exchange_fraction "
            "(charge-balanced stoichiometry is automatically computed)."
        ))
    ],
    exchange_fraction: Annotated[
        Union[float, List[float]],
        Field(description=(
            "Fraction(s) of replace_ion sites to exchange (0.0–1.0). "
            "Single float: same fraction applied to every with_ion. "
            "List matching with_ions: per-ion exchange fractions (charge balance is enforced independently). "
            "Default: 1.0 (full exchange)."
        ))
    ] = 1.0,
    allow_oxidation_state_change: Annotated[
        bool,
        Field(description=(
            "If False (default), only charge-neutral structures are returned. "
            "If True, structures that cannot achieve charge neutrality are still returned but "
            "flagged with charge_neutral=False."
        ))
    ] = False,
    max_structures: Annotated[
        int,
        Field(description=(
            "Maximum number of charge-neutral structures to generate per input structure. "
            "Default: 10."
        ), ge=1, le=200)
    ] = 10,
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
    Perform charge-neutral ion exchange on input structures.

    Automatically adjusts stoichiometry so that the total ionic charge of replaced
    sites is preserved.  For example, replacing Li⁺ (charge +1) with Mg²⁺ (charge +2)
    requires only half as many Mg atoms; any unoccupied Li sites are removed (vacancies).

    Algorithm
   ------
    1. Assign oxidation states via BVAnalyzer.
    2. Locate all replace_ion sites and determine their oxidation state.
    3. For each with_ion, determine its common oxidation state.
    4. Compute the charge-balanced number of new-ion sites:
           n_new = round(n_exchange * replace_oxi * ion_weight / new_oxi)
       where n_exchange = round(n_sites * exchange_fraction).
    5. Randomly assign sites to each new ion; remove leftover replace_ion sites
       (so the total ionic charge is preserved).
    6. Check actual charge neutrality of the result via BVAnalyzer.
    7. Return only neutral structures unless allow_oxidation_state_change=True.

    Returns
   ----
    dict:
        success         (bool)
        count           (int)  number of structures generated
        structures      (list) in requested output_format
        metadata        (list) per-structure info
        input_info      (dict) summary of input structures
        exchange_rules  (dict) parsed exchange configuration
        message         (str)
        warnings        (list, optional)
        error           (str, optional)
    """
    try:
        from pymatgen.core import Structure, Element
        from pymatgen.transformations.site_transformations import ReplaceSiteSpeciesTransformation
        from pymatgen.analysis.bond_valence import BVAnalyzer
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

    # Parse with_ions and weights
    if isinstance(with_ions, dict):
        ion_list = list(with_ions.keys())
        raw_weights = list(with_ions.values())
    else:
        ion_list = list(with_ions)
        raw_weights = [1.0] * len(ion_list)

    if not ion_list:
        return {"success": False, "error": "with_ions must not be empty."}

    total_weight = sum(raw_weights)
    if total_weight <= 0:
        return {"success": False, "error": "Sum of with_ions weights must be > 0."}
    norm_weights = [w / total_weight for w in raw_weights]

    # Parse exchange_fraction per ion
    if isinstance(exchange_fraction, list):
        if len(exchange_fraction) != len(ion_list):
            return {
                "success": False,
                "error": (
                    f"Length of exchange_fraction list ({len(exchange_fraction)}) "
                    f"must match number of with_ions ({len(ion_list)})."
                )
            }
        ion_fractions = [float(f) for f in exchange_fraction]
    else:
        ion_fractions = [float(exchange_fraction)] * len(ion_list)

    for f in ion_fractions:
        if not (0.0 < f <= 1.0):
            return {"success": False, "error": f"exchange_fraction values must be in (0, 1]. Got {f}."}

    # Get common oxidation state for each with_ion
    def get_common_oxi(symbol: str) -> float:
        try:
            el = Element(symbol)
            states = el.common_oxidation_states
            return float(states[0]) if states else 1.0
        except Exception:
            return 1.0

    ion_oxis = [get_common_oxi(ion) for ion in ion_list]

    # Build exchange_rules summary for output
    exchange_rules = {
        "replace_ion": replace_ion,
        "with_ions": [
            {
                "ion": ion,
                "weight": round(norm_weights[i], 4),
                "exchange_fraction": ion_fractions[i],
                "assumed_oxi_state": ion_oxis[i]
            }
            for i, ion in enumerate(ion_list)
        ],
        "allow_oxidation_state_change": allow_oxidation_state_change
    }

    # Main generation loop
    generated_structures = []
    metadata_list = []
    warnings = []

    for struct_idx, struct in enumerate(structures):
        struct_label = struct.composition.reduced_formula

        # Locate replace_ion sites (by symbol, no oxidation states needed)
        replace_indices = [
            i for i, site in enumerate(struct)
            if site.specie.symbol == replace_ion
        ]
        if not replace_indices:
            warnings.append(f"Structure {struct_label}: no '{replace_ion}' sites found. Skipping.")
            continue

        # Try to get oxidation state via BVAnalyzer; fall back to common
        replace_oxi = get_common_oxi(replace_ion)  # default
        try:
            bva = BVAnalyzer()
            struct_oxi = bva.get_oxi_state_decorated_structure(struct)
            replace_oxi = float(struct_oxi[replace_indices[0]].specie.oxi_state)
        except Exception as e:
            warnings.append(
                f"Structure {struct_label}: BVAnalyzer failed ({e}). "
                f"Using assumed oxidation state {replace_oxi:+.0f} for {replace_ion}."
            )

        n_sites = len(replace_indices)

        # Generate max_structures variants
        struct_generated = 0
        max_attempts = max_structures * 5

        for _attempt in range(max_attempts):
            if struct_generated >= max_structures:
                break

            indices_shuffled = replace_indices.copy()
            random.shuffle(indices_shuffled)

            assignments: Dict[int, str] = {}
            sites_to_remove: List[int] = []
            success_plan = True
            pointer = 0

            ion_plan = []
            for ion, frac, oxi, weight in zip(ion_list, ion_fractions, ion_oxis, norm_weights):
                n_claimed = round(n_sites * frac * weight)
                n_claimed = max(1, min(n_claimed, n_sites - pointer))

                # Charge-balanced number of new-ion atoms
                n_new = round(n_claimed * abs(replace_oxi) / abs(oxi)) if abs(oxi) > 1e-9 else 0

                if n_new == 0:
                    warnings.append(
                        f"Structure {struct_label}: cannot charge-balance {ion} "
                        f"(oxi={oxi:+.0f}) against {replace_ion} (oxi={replace_oxi:+.0f}). "
                        f"Skipping this ion."
                    )
                    pointer += n_claimed
                    ion_plan.append((ion, 0, n_claimed))
                    continue

                for _ in range(n_new):
                    if pointer >= len(indices_shuffled):
                        success_plan = False
                        break
                    assignments[indices_shuffled[pointer]] = ion
                    pointer += 1

                leftover = n_claimed - n_new
                for _ in range(leftover):
                    if pointer < len(indices_shuffled):
                        sites_to_remove.append(indices_shuffled[pointer])
                        pointer += 1

                ion_plan.append((ion, n_new, n_claimed))

            if not success_plan or not assignments:
                continue

            # Apply replacements
            try:
                trans = ReplaceSiteSpeciesTransformation(indices_species_map=assignments)
                new_struct = trans.apply_transformation(struct)
            except Exception as e:
                warnings.append(f"Structure {struct_label}: ReplaceSiteSpeciesTransformation failed: {e}")
                continue

            # Remove vacancy sites
            vacancy_count = len(sites_to_remove)
            if vacancy_count > 0:
                remaining_replace = [
                    i for i, site in enumerate(new_struct)
                    if site.specie.symbol == replace_ion
                ]
                to_remove = sorted(
                    random.sample(remaining_replace, min(vacancy_count, len(remaining_replace))),
                    reverse=True
                )
                new_struct.remove_sites(to_remove)

            # Check charge neutrality
            charge_neutral: Optional[bool] = None
            total_charge: Optional[float] = None
            try:
                bva2 = BVAnalyzer()
                new_oxi_struct = bva2.get_oxi_state_decorated_structure(new_struct)
                total_charge = float(sum(site.specie.oxi_state for site in new_oxi_struct))
                charge_neutral = abs(total_charge) < 0.05
            except Exception as e:
                warnings.append(f"Structure {struct_label}: charge check failed: {e}")
                charge_neutral = None

            if charge_neutral is False and not allow_oxidation_state_change:
                continue

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
                warnings.append(f"Structure {struct_label}: output formatting failed: {e}")
                continue

            # Build metadata
            ion_details = {}
            for ion, n_new, n_claimed in ion_plan:
                ion_details[ion] = {
                    "n_sites_assigned": n_new,
                    "n_sites_claimed": n_claimed,
                    "assumed_oxi_state": get_common_oxi(ion)
                }

            metadata = {
                "index": len(generated_structures) + 1,
                "source_structure": struct_label,
                "formula": new_struct.composition.reduced_formula,
                "composition": str(new_struct.composition),
                "replaced_ion": replace_ion,
                "replaced_ion_oxi": replace_oxi,
                "n_replace_sites_original": n_sites,
                "n_vacancies_created": vacancy_count,
                "ions_placed": ion_details,
                "charge_neutral": charge_neutral,
                "total_charge": total_charge,
                "n_sites": len(new_struct),
                "volume": float(new_struct.volume)
            }

            generated_structures.append(formatted)
            metadata_list.append(metadata)
            struct_generated += 1

    if not generated_structures:
        return {
            "success": False,
            "error": (
                "No charge-neutral structures could be generated with the given parameters. "
                "Try allow_oxidation_state_change=True or adjust exchange_fraction / with_ions."
            ),
            "exchange_rules": exchange_rules,
            "warnings": warnings
        }

    input_info = {
        "n_input_structures": len(structures),
        "input_formulas": [s.composition.reduced_formula for s in structures]
    }

    result = {
        "success": True,
        "count": len(generated_structures),
        "structures": generated_structures,
        "metadata": metadata_list,
        "input_info": input_info,
        "exchange_rules": exchange_rules,
        "message": (
            f"Generated {len(generated_structures)} structure(s) via ion exchange "
            f"({replace_ion} → {', '.join(ion_list)})"
        )
    }
    if warnings:
        result["warnings"] = warnings
    return result

