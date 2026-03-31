"""
ARROWS campaign preparation tool for active learning synthesis optimization.

Prepares a new ARROWS active learning campaign by:
1. Building temperature-dependent phase diagrams from Materials Project data
2. Enumerating all precursor sets that can produce the target material
3. Calculating thermodynamic driving force (ΔG) for each set
4. Ranking precursor sets by thermodynamic favorability
5. Persisting campaign state (Rxn_TD.csv, Settings.json) to a campaign directory

This is the first step in the ARROWS active learning loop:
    arrows_prepare_campaign → [arrows_suggest_experiment → robot → arrows_record_result] × N

Based on: https://github.com/njszym/ARROWS
Publication: https://doi.org/10.1038/s41467-023-42329-9
"""

from typing import Dict, Any, List, Optional, Annotated
from pydantic import Field
import os
import json
import csv
from tools.active_learning._arrows_utils import arrows_cwd


def arrows_prepare_campaign(
    target: Annotated[
        str,
        Field(
            description=(
                "Chemical formula of the desired synthesis target (e.g., 'Ba2YCu3O7', 'LiCoO2'). "
                "Must be a phase present in or near the Materials Project database for thermodynamic "
                "data to be available."
            )
        )
    ],
    precursors: Annotated[
        List[str],
        Field(
            description=(
                "List of available precursor chemical formulae (e.g., ['Y2O3', 'BaO', 'CuO', 'BaCO3']). "
                "These are all phases that the robot may use across any experiment in this campaign. "
                "The tool will enumerate all balanced subsets. Larger pools increase combinatorial cost: "
                "recommended ≤ 15 precursors unless max_precursors is set."
            )
        )
    ],
    temperatures: Annotated[
        List[int],
        Field(
            description=(
                "List of synthesis temperatures in °C to sample during the campaign "
                "(e.g., [600, 700, 800, 900]). Phase diagrams are built at each temperature. "
                "At least two temperatures are recommended for meaningful active learning."
            )
        )
    ],
    campaign_dir: Annotated[
        str,
        Field(
            description=(
                "Absolute or relative path to the campaign working directory where ARROWS state files "
                "will be saved: Rxn_TD.csv (ranked reaction data) and Settings.json (campaign config). "
                "Directory will be created if it does not exist. "
                "Example: './campaigns/Ba2YCu3O7_run1'"
            )
        )
    ],
    allowed_byproducts: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description=(
                "Gaseous or removable phases allowed to form in addition to the target "
                "(e.g., ['O2', 'CO2']). Defaults to ['O2', 'CO2'] when allow_oxidation=True, "
                "else ['CO2']. Set explicitly to restrict or extend allowed byproducts."
            )
        )
    ] = None,
    allow_oxidation: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True, O2 may participate as a reactant (net oxidation of precursors is allowed). "
                "Set to False for synthesis under inert or reducing atmosphere where oxidation states "
                "can only be fixed or reduced."
            )
        )
    ] = True,
    open_system: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True, accounts for gaseous species (O2, CO2) escaping the reaction vessel. "
                "Set to False for closed-system synthesis where all species are conserved."
            )
        )
    ] = True,
    atmosphere: Annotated[
        str,
        Field(
            default="air",
            description=(
                "Synthesis atmosphere used to adjust thermodynamic free energy corrections. "
                "Options: 'air' (default, applies O2/CO2 partial pressure corrections), "
                "'inert' (N2 or Ar, no oxidation corrections)."
            )
        )
    ] = "air",
    max_precursors: Annotated[
        Optional[int],
        Field(
            default=None,
            description=(
                "Maximum number of precursors per set. Defaults to the Gibbs phase rule limit "
                "(number of elements in the chemical space). Reduce this to limit combinatorial "
                "explosion for large precursor pools (e.g., max_precursors=3 for 3-component sets)."
            )
        )
    ] = None,
) -> Dict[str, Any]:
    """
    Prepare a new ARROWS active learning campaign for solid-state synthesis optimization.

    Enumerates and ranks all thermodynamically viable precursor sets for synthesizing
    a target material. The output Rxn_TD.csv and Settings.json define the campaign state
    required by arrows_suggest_experiment in subsequent iterations.

    IMPORTANT: Requires the ARROWS package to be installed:
        pip install git+https://github.com/njszym/ARROWS.git
    Requires git LFS for the bundled MP thermodynamic energetics file.

    Also requires MP_API_KEY environment variable for live Materials Project phase diagram queries.

    Returns
    -------
    dict:
        success                  (bool)   Whether campaign preparation succeeded.
        campaign_dir             (str)    Absolute path to the campaign directory.
        target                   (str)    Reduced formula of the target material.
        n_reactions              (int)    Number of viable precursor sets found.
        reactions                (list)   Ranked reaction data, each entry:
            rank                     (int)    Rank by thermodynamic favorability (1 = most favorable).
            precursors               (list)   Precursor chemical formulae.
            amounts                  (list)   Stoichiometric coefficients (normalized to target).
            products                 (list)   Expected products (target + allowed byproducts).
            reaction_energy_meV_per_atom (float) ΔG in meV/atom (negative = favorable).
        rxn_td_path              (str)    Absolute path to saved Rxn_TD.csv.
        settings_path            (str)    Absolute path to saved Settings.json.
        n_precursors_available   (int)    Number of precursors in the pool.
        temperatures             (list)   Temperatures used.
        atmosphere               (str)    Atmosphere used.
        message                  (str)    Human-readable summary.
        warnings                 (list)   Non-critical warnings.
        error                    (str)    Error message if success=False.
    """

    warnings = []

    # --- Validate atmosphere ---
    if atmosphere not in ("air", "inert"):
        return {
            "success": False,
            "error": f"atmosphere must be 'air' or 'inert', got '{atmosphere}'."
        }

    # --- Validate temperatures ---
    if not temperatures or len(temperatures) == 0:
        return {
            "success": False,
            "error": "At least one temperature must be provided."
        }

    # --- Validate precursors ---
    if not precursors or len(precursors) < 2:
        return {
            "success": False,
            "error": "At least two precursors must be provided."
        }

    # --- Import ARROWS ---
    try:
        from arrows import energetics, reactions, searcher
    except ImportError:
        return {
            "success": False,
            "error": (
                "ARROWS package not found. Install with:\n"
                "  pip install git+https://github.com/njszym/ARROWS.git\n"
                "Note: git LFS must be installed first for the bundled MP energetics data."
            )
        }

    # --- Import pymatgen (required by ARROWS) ---
    try:
        from pymatgen.core.composition import Composition
    except ImportError:
        return {
            "success": False,
            "error": "pymatgen not available. Install with: pip install pymatgen"
        }

    # --- Normalise target formula ---
    try:
        target_formula = Composition(target).reduced_formula
    except Exception as e:
        return {
            "success": False,
            "error": f"Invalid target formula '{target}': {e}"
        }

    # --- Normalise precursor formulae ---
    try:
        normalised_precursors = [Composition(p).reduced_formula for p in precursors]
    except Exception as e:
        return {
            "success": False,
            "error": f"Invalid precursor formula: {e}"
        }

    # --- Resolve allowed byproducts ---
    if allowed_byproducts is None:
        if allow_oxidation:
            allowed_byproducts = ["O2", "CO2"]
        else:
            allowed_byproducts = ["CO2"]
    else:
        try:
            allowed_byproducts = [Composition(bp).reduced_formula for bp in allowed_byproducts]
        except Exception as e:
            return {
                "success": False,
                "error": f"Invalid allowed_byproducts formula: {e}"
            }

    # --- Extend precursor pool with gaseous species if needed ---
    effective_precursors = list(normalised_precursors)
    if allow_oxidation:
        if "O2" not in effective_precursors:
            effective_precursors.append("O2")
        if "CO2" not in effective_precursors:
            effective_precursors.append("CO2")

    # --- Resolve campaign directory ---
    campaign_dir_abs = os.path.abspath(campaign_dir)
    os.makedirs(campaign_dir_abs, exist_ok=True)

    settings_path = os.path.join(campaign_dir_abs, "Settings.json")
    rxn_td_path = os.path.join(campaign_dir_abs, "Rxn_TD.csv")

    # --- Build phase diagrams ---
    # arrows_cwd() ensures MP_Energetics.json is present (downloading on first use)
    # and temporarily sets CWD to site-packages so ARROWS' relative path resolves.
    try:
        with arrows_cwd():
            pd_dict = energetics.get_pd_dict(
                effective_precursors,
                temperatures,
                atmos=atmosphere
            )
    except Exception as e:
        return {
            "success": False,
            "campaign_dir": campaign_dir_abs,
            "target": target_formula,
            "error": (
                f"Failed to build phase diagrams: {e}\n"
                "Check that all precursor formulae are valid Materials Project entries."
            ),
            "warnings": warnings
        }

    # --- Enumerate balanced precursor sets ---
    try:
        balanced_sets = searcher.get_precursor_sets(
            effective_precursors,
            target_formula,
            allowed_byproducts=allowed_byproducts,
            max_pc=max_precursors,
            allow_oxidation=allow_oxidation
        )
    except Exception as e:
        return {
            "success": False,
            "campaign_dir": campaign_dir_abs,
            "target": target_formula,
            "error": f"Failed to enumerate precursor sets: {e}",
            "warnings": warnings
        }

    if not balanced_sets:
        return {
            "success": False,
            "campaign_dir": campaign_dir_abs,
            "target": target_formula,
            "n_reactions": 0,
            "error": (
                f"No balanced precursor sets found for target '{target_formula}'. "
                "Check that the target is reachable from the supplied precursors and byproducts, "
                "or expand the precursor pool."
            ),
            "warnings": warnings
        }

    # --- Calculate reaction energies ---
    min_temp = min(temperatures)
    min_pd = pd_dict[min_temp]

    rxn_info = []
    n_failed = 0
    for (reactants, products) in balanced_sets:
        try:
            precursor_amounts = reactions.get_balanced_coeffs(reactants, products)[0]
            precursor_amounts = [round(float(val), 3) for val in precursor_amounts]
            with arrows_cwd():
                rxn_energy = reactions.get_rxn_energy(
                    reactants, products, min_temp, min_pd
                )
            rxn_info.append([reactants, precursor_amounts, products, rxn_energy])
        except Exception:
            # Skip reactions that cannot be balanced or energetically evaluated
            n_failed += 1
            continue

    if n_failed > 0:
        warnings.append(
            f"{n_failed} precursor set(s) could not be energetically evaluated and were skipped. "
            "This may indicate missing MP entries for some compounds."
        )

    if not rxn_info:
        return {
            "success": False,
            "campaign_dir": campaign_dir_abs,
            "target": target_formula,
            "n_reactions": 0,
            "error": "All precursor sets failed thermodynamic evaluation. Check precursor formulae.",
            "warnings": warnings
        }

    # --- Sort by thermodynamic favorability (most negative ΔG first) ---
    sorted_rxn_info = sorted(rxn_info, key=lambda x: x[-1])

    # --- Save Rxn_TD.csv ---
    try:
        with open(rxn_td_path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Precursors", "Amounts", "Products", "Reaction energy (meV/atom)"])
            for rxn in sorted_rxn_info:
                writer.writerow([
                    " + ".join(rxn[0]),
                    " + ".join([str(v) for v in rxn[1]]),
                    " + ".join(rxn[2]),
                    round(float(rxn[3]), 2)
                ])
    except Exception as e:
        return {
            "success": False,
            "campaign_dir": campaign_dir_abs,
            "target": target_formula,
            "error": f"Failed to write Rxn_TD.csv: {e}",
            "warnings": warnings
        }

    # --- Save Settings.json ---
    settings = {
        "Precursors": normalised_precursors,
        "Target": target_formula,
        "Allowed Byproducts": allowed_byproducts,
        "Temperatures": temperatures,
        "Open System": str(open_system),
        "Allow Oxidation": str(allow_oxidation),
        "Atmosphere": atmosphere,
    }
    if max_precursors is not None:
        settings["Max Precursors"] = max_precursors

    try:
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        return {
            "success": False,
            "campaign_dir": campaign_dir_abs,
            "target": target_formula,
            "error": f"Failed to write Settings.json: {e}",
            "warnings": warnings
        }

    # --- Build structured reaction list for return ---
    reactions_out = []
    for rank, rxn in enumerate(sorted_rxn_info, start=1):
        reactions_out.append({
            "rank": rank,
            "precursors": rxn[0],
            "amounts": rxn[1],
            "products": rxn[2],
            "reaction_energy_meV_per_atom": round(float(rxn[3]), 4)
        })

    # --- Summary message ---
    most_favorable = reactions_out[0]
    message = (
        f"Campaign prepared for target '{target_formula}'. "
        f"Found {len(reactions_out)} viable precursor set(s) across {len(temperatures)} temperature(s). "
        f"Most thermodynamically favorable: {' + '.join(most_favorable['precursors'])} "
        f"(ΔG = {most_favorable['reaction_energy_meV_per_atom']:.1f} meV/atom). "
        f"Campaign state saved to: {campaign_dir_abs}"
    )

    return {
        "success": True,
        "campaign_dir": campaign_dir_abs,
        "target": target_formula,
        "n_reactions": len(reactions_out),
        "reactions": reactions_out,
        "rxn_td_path": rxn_td_path,
        "settings_path": settings_path,
        "n_precursors_available": len(normalised_precursors),
        "temperatures": temperatures,
        "atmosphere": atmosphere,
        "message": message,
        "warnings": warnings,
    }
