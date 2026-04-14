"""
ARROWS experiment suggestion tool for active learning synthesis optimization.

Given an existing campaign directory populated by arrows_initialize_campaign, this
tool reads the current ARROWS state (Rxn_TD.csv, Settings.json, PairwiseRxns.csv,
Exp.json) and returns the next experiment(s) to run.

Decision logic (mirrors suggest.py):
1. Load all campaign state from disk.
2. Build phase diagrams at each campaign temperature (needed only when pairwise
   reactions have been learned - required for the energy re-ranking step).
3. Apply pairwise knowledge: use the learned pairwise reaction database to predict
   how precursor sets will evolve and re-rank accordingly.
4. Walk the ranked list of precursor sets (most thermodynamically favorable first).
   For each set, iterate through temperatures (lowest first).  The first
   precursor-set/temperature combination that has not yet been sampled is a
   suggestion.  Repeat until batch_size suggestions are collected.
5. If every reaction has already been sampled, report campaign_complete=True.

This is the second step in the ARROWS active learning loop:
    arrows_initialize_campaign → [arrows_suggest_experiment → robot → arrows_record_result] × N

Based on: https://github.com/njszym/ARROWS
Publication: https://doi.org/10.1038/s41467-023-42329-9
"""

from typing import Dict, Any, List, Optional, Annotated
from pydantic import Field
import os
import json
import csv
from tools.arrows._arrows_utils import arrows_cwd


def arrows_suggest_experiment(
    campaign_dir: Annotated[
        str,
        Field(
            description=(
                "Path to the campaign directory created by arrows_initialize_campaign. "
                "Must contain Settings.json and Rxn_TD.csv. "
                "Exp.json and PairwiseRxns.csv are loaded automatically if present. "
                "Example: './campaigns/Ba2YCu3O7_run1'"
            )
        )
    ],
    batch_size: Annotated[
        int,
        Field(
            default=1,
            ge=1,
            le=50,
            description=(
                "Number of experiments to suggest per call (1–50). "
                "Suggestions are drawn from different precursor sets / temperatures in "
                "ranked order (most thermodynamically favorable first). "
                "Default: 1 (sequential active learning)."
            )
        )
    ] = 1,
    explore: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If False (default), exploit: prioritise precursor sets with the highest "
                "thermodynamic driving force toward the target. "
                "If True, explore: prioritise sets with the most new pairwise interfaces "
                "to maximise information gain."
            )
        )
    ] = False,
    enforce_thermo: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, only accept pairwise reactions that are thermodynamically "
                "favorable (ΔG < 0). If False (default), allow all learned pairwise "
                "reactions regardless of their driving force."
            )
        )
    ] = False,
    greedy: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, assume that any pairwise reaction observed below the minimum "
                "campaign temperature will *always* occur first when those two reactants "
                "are present together.  Use with caution: this assumption may not hold "
                "across different precursor sets. Default: False."
            )
        )
    ] = False,
) -> Dict[str, Any]:
    """
    Suggest the next experiment(s) in an ARROWS active learning campaign.

    Reads campaign state from disk, applies any learned pairwise reaction knowledge,
    and returns the highest-ranked precursor set(s) and temperature(s) that have not
    yet been experimentally tested.

    IMPORTANT: Requires the ARROWS package to be installed:
        pip install git+https://github.com/njszym/ARROWS.git
    Requires git LFS for the bundled MP thermodynamic energetics file.

    Also requires MP_API_KEY environment variable for live Materials Project phase
    diagram queries (used internally to re-rank after pairwise learning).

    Returns
    -------
    dict:
        success             (bool)  Whether suggestion generation succeeded.
        campaign_dir        (str)   Absolute path to the campaign directory.
        target              (str)   Reduced formula of the synthesis target.
        n_suggestions       (int)   Number of experiments suggested (≤ batch_size).
        suggestions         (list)  Ordered list of suggested experiments, each:
            batch_index         (int)   1-based index within this batch.
            precursors          (list)  Precursor chemical formulae.
            temperature_C       (int)   Suggested synthesis temperature (°C).
            rank                (int)   Current ARROWS rank of this precursor set.
            predicted_products  (list)  Products predicted by the pairwise model.
            reaction_energy_meV_per_atom (float) Current ΔG score (meV/atom).
        campaign_complete   (bool)  True if all ranked reactions have been sampled.
        n_reactions_total   (int)   Total number of reactions in the campaign.
        n_reactions_sampled (int)   Number of precursor-set/temperature combos already run.
        temperatures        (list)  Campaign temperature list.
        message             (str)   Human-readable summary.
        warnings            (list)  Non-critical warnings.
        error               (str)   Error message if success=False.
    """

    warnings: List[str] = []

    # ------------------------------------------------------------------
    # 1. Validate campaign directory and required files
    # ------------------------------------------------------------------
    campaign_dir_abs = os.path.abspath(campaign_dir)
    settings_path = os.path.join(campaign_dir_abs, "Settings.json")
    rxn_td_path = os.path.join(campaign_dir_abs, "Rxn_TD.csv")
    pairwise_csv_path = os.path.join(campaign_dir_abs, "PairwiseRxns.csv")
    exp_json_path = os.path.join(campaign_dir_abs, "Exp.json")

    if not os.path.isdir(campaign_dir_abs):
        return {
            "success": False,
            "error": f"Campaign directory not found: {campaign_dir_abs}"
        }
    if not os.path.isfile(settings_path):
        return {
            "success": False,
            "error": (
                f"Settings.json not found in {campaign_dir_abs}. "
                "Run arrows_initialize_campaign first to initialise the campaign."
            )
        }
    if not os.path.isfile(rxn_td_path):
        return {
            "success": False,
            "error": (
                f"Rxn_TD.csv not found in {campaign_dir_abs}. "
                "Run arrows_initialize_campaign first to generate reaction data."
            )
        }

    # ------------------------------------------------------------------
    # 2. Import ARROWS and pymatgen
    # ------------------------------------------------------------------
    try:
        from arrows import energetics, reactions, pairwise, exparser
    except ImportError:
        return {
            "success": False,
            "error": (
                "ARROWS package not found. Install with:\n"
                "  pip install git+https://github.com/njszym/ARROWS.git\n"
                "Note: git LFS must be installed first for the bundled MP energetics data."
            )
        }

    try:
        from pymatgen.core.composition import Composition
        from itertools import combinations
    except ImportError:
        return {
            "success": False,
            "error": "pymatgen not available. Install with: pip install pymatgen"
        }

    # ------------------------------------------------------------------
    # 3. Load campaign settings
    # ------------------------------------------------------------------
    try:
        with open(settings_path) as f:
            settings = json.load(f)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load Settings.json: {e}"
        }

    try:
        available_precursors = list(settings["Precursors"])
        allow_oxidation = str(settings.get("Allow Oxidation", "True")) == "True"
        target_product = Composition(settings["Target"]).reduced_formula
        allowed_byproducts = settings.get("Allowed Byproducts", ["CO2"])
        temps = settings["Temperatures"]
        open_sys = str(settings.get("Open System", "True")) == "True"
        atmosphere = settings.get("Atmosphere", "air")
    except Exception as e:
        return {
            "success": False,
            "error": f"Invalid Settings.json format: {e}"
        }

    if not temps:
        return {
            "success": False,
            "error": "Settings.json contains an empty Temperatures list."
        }

    # Extend precursor pool with gaseous species (mirrors suggest.py __main__ block)
    effective_precursors = list(available_precursors)
    if allow_oxidation:
        if "O2" not in effective_precursors:
            effective_precursors.append("O2")
        if "CO2" not in effective_precursors:
            effective_precursors.append("CO2")

    increasing_temps = sorted(temps)

    # ------------------------------------------------------------------
    # 4. Load Exp.json (optional — absent on first iteration)
    # ------------------------------------------------------------------
    exp_data = None
    if os.path.isfile(exp_json_path):
        try:
            with open(exp_json_path) as f:
                raw = json.load(f)
            # ARROWS stores results under a top-level "Universal File" key
            exp_data = raw.get("Universal File", raw)
        except Exception as e:
            warnings.append(
                f"Failed to load Exp.json ({e}). "
                "Treating all experiments as unsampled."
            )

    # ------------------------------------------------------------------
    # 5. Build phase diagrams
    #    Required by the ranking-update step when pairwise reactions are
    #    known (reactions.get_dG needs pd_dict to re-score evolved sets).
    #    arrows_cwd() downloads MP_Energetics.json if missing and sets CWD
    #    so ARROWS' relative data path resolves correctly.
    # ------------------------------------------------------------------
    try:
        with arrows_cwd():
            pd_dict = energetics.get_pd_dict(
                effective_precursors,
                temps,
                atmos=atmosphere
            )
    except Exception as e:
        return {
            "success": False,
            "campaign_dir": campaign_dir_abs,
            "error": (
                f"Failed to build phase diagrams: {e}\n"
                "Check that all precursor formulae are valid Materials Project entries."
            ),
            "warnings": warnings
        }

    # ------------------------------------------------------------------
    # 6. Load Rxn_TD.csv into sorted_rxn_info
    #    Internal ARROWS format per row (9 elements):
    #    [reactants, amounts, reactants_copy, amounts_copy, products,
    #     expec_yield, interfaces, num_interfaces, energ]
    #    The reactants_copy / amounts_copy fields (indices 2–3) may be
    #    updated by pairwise evolution; indices 0–1 always hold originals.
    # ------------------------------------------------------------------
    try:
        sorted_rxn_info = []
        with open(rxn_td_path) as csv_file:
            reader = csv.reader(csv_file)
            for i, row in enumerate(reader):
                if i == 0:
                    continue  # header
                reactants = [Composition(c).reduced_formula for c in row[0].split(" + ")]
                interfaces = [set(pair) for pair in combinations(reactants, 2)]
                amounts = [float(v) for v in row[1].split(" + ")]
                products = row[2].split(" + ")
                energ = float(row[3])
                sorted_rxn_info.append([
                    reactants, amounts,   # [0] original precursors, [1] original amounts
                    reactants, amounts,   # [2] effective precursors, [3] effective amounts
                    products,             # [4] expected products
                    0.0,                  # [5] expected yield
                    interfaces,           # [6] pairwise interfaces
                    len(interfaces),      # [7] number of interfaces
                    energ,                # [8] reaction energy (meV/atom)
                ])

        if not sorted_rxn_info:
            return {
                "success": False,
                "campaign_dir": campaign_dir_abs,
                "error": "Rxn_TD.csv is empty. Re-run arrows_initialize_campaign."
            }
    except Exception as e:
        return {
            "success": False,
            "campaign_dir": campaign_dir_abs,
            "error": f"Failed to parse Rxn_TD.csv: {e}",
            "warnings": warnings
        }

    # Apply initial ordering (mirrors suggest.load_rxn_data sort)
    if explore:
        sorted_rxn_info = sorted(sorted_rxn_info, key=lambda x: (-x[7], x[8]))
    else:
        sorted_rxn_info = sorted(sorted_rxn_info, key=lambda x: (x[8], -x[7]))

    n_reactions_total = len(sorted_rxn_info) * len(increasing_temps)

    # ------------------------------------------------------------------
    # 7. Load PairwiseRxns.csv and update ranking (optional)
    #    This is the ARROWS active learning update: pairwise reactions
    #    learned from previous experiments are used to predict how each
    #    precursor set will evolve and re-score it accordingly.
    # ------------------------------------------------------------------
    rxn_db = pairwise.rxn_database()

    if os.path.isfile(pairwise_csv_path):
        try:
            rxn_db.load(filepath=pairwise_csv_path)

            # --- Inline equivalent of suggest.update_ranking ---
            # Re-predict how each precursor set evolves given learned pairwise rxns.
            # This updates the "effective" materials (indices 2-3) and re-scores.
            evolved_rxn_info = []
            for starting_rxn in sorted_rxn_info:
                original_set = starting_rxn[0]
                original_amounts = starting_rxn[1]
                starting_materials = starting_rxn[2]
                starting_amounts = starting_rxn[3]

                new_materials, new_amounts = pairwise.pred_evolution(
                    starting_materials, starting_amounts,
                    rxn_db, greedy, temps, allow_oxidation
                )

                # pred_evolution returns None if insufficient data
                if new_materials is None or new_amounts is None:
                    evolved_rxn_info.append(starting_rxn)
                    continue

                if set(new_materials) != set(starting_materials):
                    if target_product in new_materials:
                        ind = new_materials.index(target_product)
                        expec_yield = new_amounts[ind]
                        new_products = [target_product]
                        energ = 0.0
                    else:
                        expec_yield = 0.0
                        try:
                            with arrows_cwd():
                                new_products, energ = reactions.get_dG(
                                    new_materials, new_amounts,
                                    target_product, allowed_byproducts,
                                    open_sys, pd_dict, min(temps)
                                )
                        except Exception:
                            # Skip this set if energy cannot be calculated
                            continue

                    all_ifaces = [frozenset(p) for p in combinations(new_materials, 2)]
                    known_ifaces = list(rxn_db.as_dict().keys())
                    new_ifaces = [set(i) for i in set(all_ifaces) - set(known_ifaces)]
                    evolved_rxn_info.append([
                        original_set, original_amounts,
                        new_materials, new_amounts,
                        new_products, expec_yield,
                        new_ifaces, len(new_ifaces),
                        energ
                    ])
                else:
                    evolved_rxn_info.append(starting_rxn)

            # Re-sort after evolution
            if explore:
                sorted_rxn_info = sorted(
                    evolved_rxn_info, key=lambda x: (-x[5], -x[7], x[8])
                )
            else:
                sorted_rxn_info = sorted(
                    evolved_rxn_info, key=lambda x: (-x[5], x[8], -x[7])
                )

        except Exception as e:
            warnings.append(
                f"Failed to apply PairwiseRxns.csv ({e}). "
                "Falling back to initial thermodynamic ranking."
            )

    # ------------------------------------------------------------------
    # 8. Walk the ranked list to find unsampled experiments
    # ------------------------------------------------------------------
    suggestions: List[Dict[str, Any]] = []
    n_sampled = 0

    for rank, rxn in enumerate(sorted_rxn_info, start=1):
        if len(suggestions) >= batch_size:
            break

        original_precursors = rxn[0]  # Always use original set for Exp.json lookup
        predicted_products = rxn[4]
        rxn_energy = rxn[8]

        for T in increasing_temps:
            if len(suggestions) >= batch_size:
                break

            # Query Exp.json for this precursor-set / temperature combo
            sampled = False
            if exp_data is not None:
                try:
                    products, _ = exparser.get_products(original_precursors, T, exp_data)
                    sampled = products is not None
                    if sampled:
                        n_sampled += 1
                except Exception:
                    pass  # Treat as unsampled on error

            if not sampled:
                suggestions.append({
                    "batch_index": len(suggestions) + 1,
                    "precursors": list(original_precursors),
                    "temperature_C": int(T),
                    "rank": rank,
                    "predicted_products": list(predicted_products),
                    "reaction_energy_meV_per_atom": round(float(rxn_energy), 4),
                })

    # ------------------------------------------------------------------
    # 9. Build response
    # ------------------------------------------------------------------
    campaign_complete = len(suggestions) == 0

    if campaign_complete:
        message = (
            f"Campaign complete for target '{target_product}'. "
            f"All {n_reactions_total} precursor-set/temperature combinations have been sampled. "
            "Review Exp.json for synthesis outcomes."
        )
    elif len(suggestions) == 1:
        s = suggestions[0]
        message = (
            f"Suggested experiment: {' + '.join(s['precursors'])} at {s['temperature_C']} °C "
            f"(ARROWS rank {s['rank']}, ΔG = {s['reaction_energy_meV_per_atom']:.1f} meV/atom)."
        )
    else:
        s = suggestions[0]
        message = (
            f"Suggesting {len(suggestions)} experiment(s). "
            f"Top suggestion: {' + '.join(s['precursors'])} at {s['temperature_C']} °C "
            f"(ARROWS rank {s['rank']}, ΔG = {s['reaction_energy_meV_per_atom']:.1f} meV/atom)."
        )

    return {
        "success": True,
        "campaign_dir": campaign_dir_abs,
        "target": target_product,
        "n_suggestions": len(suggestions),
        "suggestions": suggestions,
        "campaign_complete": campaign_complete,
        "n_reactions_total": n_reactions_total,
        "n_reactions_sampled": n_sampled,
        "temperatures": increasing_temps,
        "message": message,
        "warnings": warnings,
    }
