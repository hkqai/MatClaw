"""
ARROWS result recording tool for active learning synthesis optimization.

Given an experimental outcome (precursors, temperature, observed products and
weight fractions) from a robot synthesis run, this tool:

1. Updates Exp.json with the raw experimental result.
2. Loads the current PairwiseRxns.csv (creating it if absent).
3. Uses pairwise.retroanalyze to extract what pairwise reaction knowledge can be
   learned from the observed products.
4. Calls rxn_database.update with the inferred knowledge.
5. Saves the updated PairwiseRxns.csv back to disk.

This is the third step in the ARROWS active learning loop:
    arrows_prepare_campaign → [arrows_suggest_experiment → robot → arrows_record_result] x N

Based on: https://github.com/njszym/ARROWS
Publication: https://doi.org/10.1038/s41467-023-42329-9
"""

from typing import Dict, Any, List, Optional, Annotated
from pydantic import Field
import os
import json
from tools.arrows._arrows_utils import arrows_cwd


def arrows_record_result(
    campaign_dir: Annotated[
        str,
        Field(
            description=(
                "Path to the campaign directory created by arrows_prepare_campaign. "
                "Must contain Settings.json. Exp.json will be created or updated. "
                "PairwiseRxns.csv will be created or updated. "
                "Example: './campaigns/BaTiO3_run1'"
            )
        )
    ],
    precursors: Annotated[
        List[str],
        Field(
            description=(
                "List of precursor chemical formulae that were mixed in this experiment "
                "(e.g., ['BaO', 'TiO2']). Order does not matter; formulae are "
                "automatically reduced and sorted before storage."
            )
        )
    ],
    temperature_C: Annotated[
        int,
        Field(
            description=(
                "Synthesis temperature in °C at which this experiment was run "
                "(e.g., 800). Must match one of the temperatures used in the campaign."
            )
        )
    ],
    products: Annotated[
        List[str],
        Field(
            description=(
                "List of observed product phases, each given as formula with space-group "
                "suffix (e.g., ['BaTiO3_99', 'BaO_225']). The space-group number "
                "identifies the polymorph. Use formula_0 if no space-group is known. "
                "Must have the same length as weight_fractions."
            )
        )
    ],
    weight_fractions: Annotated[
        List[float],
        Field(
            description=(
                "Weight fractions of each observed product (0-1, must sum to ~1.0). "
                "Must have the same length as products. "
                "Example: [0.9, 0.1] for 90% target + 10% impurity."
            )
        )
    ],
) -> Dict[str, Any]:
    """
    Record an experimental result in an ARROWS active learning campaign.

    Updates Exp.json and PairwiseRxns.csv with the observed outcome, enabling
    subsequent calls to arrows_suggest_experiment to leverage the new knowledge.
    """

    warnings: List[str] = []

    # ------------------------------------------------------------------
    # 1. Validate campaign directory and settings
    # ------------------------------------------------------------------
    campaign_dir_abs = os.path.abspath(campaign_dir)
    if not os.path.isdir(campaign_dir_abs):
        return {
            "success": False,
            "campaign_dir": campaign_dir_abs,
            "error": f"Campaign directory not found: {campaign_dir_abs}",
            "warnings": warnings,
        }

    settings_path = os.path.join(campaign_dir_abs, "Settings.json")
    if not os.path.isfile(settings_path):
        return {
            "success": False,
            "campaign_dir": campaign_dir_abs,
            "error": f"Settings.json not found in {campaign_dir_abs}. "
                     "Run arrows_prepare_campaign first.",
            "warnings": warnings,
        }

    try:
        with open(settings_path) as f:
            settings = json.load(f)
    except Exception as e:
        return {
            "success": False,
            "campaign_dir": campaign_dir_abs,
            "error": f"Failed to read Settings.json: {e}",
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    # 2. Validate input dimensions
    # ------------------------------------------------------------------
    if len(products) != len(weight_fractions):
        return {
            "success": False,
            "campaign_dir": campaign_dir_abs,
            "error": (
                f"products ({len(products)}) and weight_fractions "
                f"({len(weight_fractions)}) must have the same length."
            ),
            "warnings": warnings,
        }

    if len(products) == 0:
        return {
            "success": False,
            "campaign_dir": campaign_dir_abs,
            "error": "products list must not be empty.",
            "warnings": warnings,
        }

    wt_sum = sum(weight_fractions)
    if not (0.85 <= wt_sum <= 1.15):
        warnings.append(
            f"Weight fractions sum to {wt_sum:.3f}; expected ~1.0. "
            "ARROWS retroanalyze may behave unexpectedly."
        )

    # ------------------------------------------------------------------
    # 3. Build Exp.json key from precursors
    #    (reduced formulae, sorted alphabetically, joined by ', ')
    # ------------------------------------------------------------------
    try:
        from pymatgen.core.composition import Composition as _Comp
        reduced_precs = sorted(_Comp(p).reduced_formula for p in precursors)
    except Exception as e:
        return {
            "success": False,
            "campaign_dir": campaign_dir_abs,
            "error": f"Failed to reduce precursor formulae: {e}",
            "warnings": warnings,
        }

    precursor_key = ", ".join(reduced_precs)
    temp_key = f"{int(temperature_C)} C"

    # ------------------------------------------------------------------
    # 4. Load or initialise Exp.json
    # ------------------------------------------------------------------
    exp_path = os.path.join(campaign_dir_abs, "Exp.json")
    if os.path.isfile(exp_path):
        try:
            with open(exp_path) as f:
                exp_json = json.load(f)
        except Exception as e:
            return {
                "success": False,
                "campaign_dir": campaign_dir_abs,
                "error": f"Failed to read Exp.json: {e}",
                "warnings": warnings,
            }
    else:
        exp_json = {"Universal File": {}}

    exp_data = exp_json.get("Universal File", {})

    # Check for overwrite
    existing_products = None
    if precursor_key in exp_data:
        temps_recorded = exp_data[precursor_key].get("Temperatures", {})
        if temp_key in temps_recorded:
            existing_products = temps_recorded[temp_key].get("products")
            warnings.append(
                f"Overwriting existing result for '{precursor_key}' at {temp_key}."
            )

    # ------------------------------------------------------------------
    # 5. Write new entry to Exp.json
    # ------------------------------------------------------------------
    new_entry = {
        "Experimentally Verified": True,
        "products": list(products),
        "product weight fractions": [float(w) for w in weight_fractions],
    }

    if precursor_key not in exp_data:
        exp_data[precursor_key] = {"Temperatures": {}}
    if "Temperatures" not in exp_data[precursor_key]:
        exp_data[precursor_key]["Temperatures"] = {}

    exp_data[precursor_key]["Temperatures"][temp_key] = new_entry
    exp_json["Universal File"] = exp_data

    try:
        with open(exp_path, "w") as f:
            json.dump(exp_json, f, indent=4)
    except Exception as e:
        return {
            "success": False,
            "campaign_dir": campaign_dir_abs,
            "error": f"Failed to write Exp.json: {e}",
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    # 6. Retroanalyze: extract pairwise reaction knowledge
    # ------------------------------------------------------------------
    pairwise_path = os.path.join(campaign_dir_abs, "PairwiseRxns.csv")
    new_reactions_learned = 0
    retroanalyze_message = None

    allowed_byproducts = settings.get("Allowed Byproducts", [])
    temperatures = settings.get("Temperatures", [temperature_C])
    open_system = settings.get("Open System", "True").lower() == "true"

    try:
        from arrows import energetics, pairwise

        # Build phase diagrams (required by retroanalyze)
        atmosphere = settings.get("Atmosphere", "air")
        with arrows_cwd():
            pd_dict = energetics.get_pd_dict(
                list(reduced_precs), temperatures, atmos=atmosphere
            )

        # Load or create the pairwise reaction database
        rxn_db = pairwise.rxn_database()
        if os.path.isfile(pairwise_path):
            try:
                # rxn_database.load() uses a relative or absolute path
                rxn_db.load(filepath=pairwise_path)
            except Exception as e:
                warnings.append(
                    f"Failed to load PairwiseRxns.csv ({e}); starting fresh database."
                )

        # Stoichiometric amounts: equal molar amounts for each precursor
        initial_amounts = [1.0] * len(reduced_precs)

        # Products formatted as reduced formulae (strip space-group suffix)
        try:
            reduced_products = [
                _Comp(p.split("_")[0]).reduced_formula for p in products
            ]
        except Exception as e:
            return {
                "success": False,
                "campaign_dir": campaign_dir_abs,
                "error": f"Failed to reduce product formulae: {e}",
                "warnings": warnings,
            }

        with arrows_cwd():
            mssg, sus_rxn_info, known_products, intermediates, inert_pairs = (
                pairwise.retroanalyze(
                    precursors=list(reduced_precs),
                    initial_amounts=initial_amounts,
                    products=reduced_products,
                    final_wts=list(weight_fractions),
                    pd_dict=pd_dict,
                    temp=temperature_C,
                    allowed_byproducts=allowed_byproducts,
                    open_sys=open_system,
                    rxn_database=rxn_db,
                )
            )

        retroanalyze_message = mssg

        # Update the pairwise database with what we learned
        is_updated = rxn_db.update(
            mssg=mssg,
            sus_rxn_info=sus_rxn_info if sus_rxn_info is not None else [],
            known_products=known_products if known_products is not None else [],
            inert_pairs=inert_pairs if inert_pairs is not None else [],
            temp=temperature_C,
        )
        if is_updated:
            new_reactions_learned = len(rxn_db.known_rxns)

        # Save updated pairwise database
        rxn_db.save(to=pairwise_path)

    except ImportError:
        warnings.append(
            "ARROWS package not installed; skipping retroanalysis. "
            "Exp.json was updated but PairwiseRxns.csv was not modified."
        )
    except Exception as e:
        warnings.append(
            f"Retroanalysis failed ({e}); Exp.json was saved but "
            "PairwiseRxns.csv may be incomplete."
        )

    # ------------------------------------------------------------------
    # 7. Build response
    # ------------------------------------------------------------------
    message = (
        f"Recorded result for '{precursor_key}' at {temp_key}. "
        f"Products: {', '.join(products)}."
    )
    if retroanalyze_message and retroanalyze_message != "Reaction already probed.":
        message += f" Pairwise analysis: {retroanalyze_message}"
    if new_reactions_learned:
        message += f" Pairwise database now contains {new_reactions_learned} known reaction(s)."

    return {
        "success": True,
        "campaign_dir": campaign_dir_abs,
        "precursor_key": precursor_key,
        "temperature_key": temp_key,
        "products_recorded": list(products),
        "weight_fractions_recorded": [float(w) for w in weight_fractions],
        "exp_json_path": exp_path,
        "pairwise_csv_path": pairwise_path,
        "new_reactions_learned": new_reactions_learned,
        "retroanalyze_message": retroanalyze_message,
        "overwrite": existing_products is not None,
        "message": message,
        "warnings": warnings,
    }
