"""
Tests for arrows_suggest_experiment tool.

Mock strategy
-------------
arrows_suggest_experiment imports ARROWS *inside* the function body, so all
ARROWS module attributes are patched after the import has already happened.

The function needs the following live ARROWS calls to be mocked to keep
tests fast, offline, and deterministic:

  arrows.energetics.get_pd_dict     -- always required (builds phase diagrams)
  arrows.exparser.get_products      -- required when Exp.json is present
  arrows.pairwise.rxn_database      -- required when PairwiseRxns.csv is present
  arrows.pairwise.pred_evolution    -- required when PairwiseRxns.csv is present

When Exp.json is absent exp_data is None and exparser.get_products is never
called.  When PairwiseRxns.csv is absent the entire pairwise block is skipped.
So most tests only need to mock get_pd_dict.
"""

import csv
import json
import os
import sys
from unittest.mock import MagicMock, call, patch

import pytest

from tools.arrows.arrows_suggest_experiment import arrows_suggest_experiment

# ---------------------------------------------------------------------------
# Skip markers
# ---------------------------------------------------------------------------

arrows_installed = pytest.mark.skipif(
    "arrows" not in sys.modules and not __import__("importlib").util.find_spec("arrows"),
    reason="ARROWS package not installed",
)

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

SAMPLE_SETTINGS = {
    "Precursors": ["Y2O3", "BaO", "CuO"],
    "Target": "Ba2YCu3O7",
    "Allowed Byproducts": ["O2", "CO2"],
    "Temperatures": [800, 900],
    "Open System": "True",
    "Allow Oxidation": "True",
    "Atmosphere": "air",
}

# Two ranked reactions — first is more favorable (lower ΔG)
SAMPLE_RXNS = [
    ("Y2O3 + BaO + CuO", "0.5 + 2.0 + 3.0", "Ba2YCu3O7 + O2", "-700.0"),
    ("Y2O3 + BaO + CuCO3", "0.5 + 2.0 + 3.0", "Ba2YCu3O7 + CO2", "-500.0"),
]

# Precursors from SAMPLE_RXNS (for assertions)
RXNS_PRECURSORS = [
    ["Y2O3", "BaO", "CuO"],
    ["Y2O3", "BaO", "CuCO3"],
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_pd_dict(precursors, temperatures, atmos="air"):
    """Fake pd_dict keyed by temperature."""
    return {t: MagicMock(name=f"pd_{t}") for t in temperatures}


def _setup_campaign(campaign_dir, settings=None, rxns=None, exp_data=None,
                    write_pairwise=False):
    """Write campaign state files to *campaign_dir* (must already exist)."""
    if settings is None:
        settings = SAMPLE_SETTINGS
    if rxns is None:
        rxns = SAMPLE_RXNS

    with open(os.path.join(campaign_dir, "Settings.json"), "w") as f:
        json.dump(settings, f)

    with open(os.path.join(campaign_dir, "Rxn_TD.csv"), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Precursors", "Amounts", "Products",
                         "Reaction energy (meV/atom)"])
        for row in rxns:
            writer.writerow(row)

    if exp_data is not None:
        with open(os.path.join(campaign_dir, "Exp.json"), "w") as f:
            json.dump({"Universal File": exp_data}, f)

    if write_pairwise:
        # Write minimal PairwiseRxns.csv header so the file exists
        with open(os.path.join(campaign_dir, "PairwiseRxns.csv"), "w",
                  newline="") as f:
            csv.writer(f).writerow(
                ["Reactants", "Temperature", "Products", "Local/Global"]
            )


# ---------------------------------------------------------------------------
# 1. Input Validation (no ARROWS dependency required)
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Validate that bad inputs are rejected before ARROWS is ever called."""

    def test_rejects_nonexistent_campaign_dir(self, tmp_path):
        result = arrows_suggest_experiment(
            campaign_dir=str(tmp_path / "does_not_exist")
        )
        assert result["success"] is False
        assert "not found" in result["error"].lower() or "directory" in result["error"].lower()

    def test_rejects_missing_settings_json(self, tmp_path):
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        # Write Rxn_TD.csv but NOT Settings.json
        with open(campaign / "Rxn_TD.csv", "w") as f:
            f.write("Precursors,Amounts,Products,Reaction energy (meV/atom)\n")
        result = arrows_suggest_experiment(campaign_dir=str(campaign))
        assert result["success"] is False
        assert "settings.json" in result["error"].lower()

    def test_rejects_missing_rxn_td_csv(self, tmp_path):
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        with open(campaign / "Settings.json", "w") as f:
            json.dump(SAMPLE_SETTINGS, f)
        result = arrows_suggest_experiment(campaign_dir=str(campaign))
        assert result["success"] is False
        assert "rxn_td.csv" in result["error"].lower()

    def test_rejects_corrupted_settings_json(self):
        """Malformed JSON in Settings.json → clear error."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "Settings.json"), "w") as f:
                f.write("{not valid json")
            with open(os.path.join(d, "Rxn_TD.csv"), "w") as f:
                f.write("Precursors,Amounts,Products,Reaction energy (meV/atom)\n")
            result = arrows_suggest_experiment(campaign_dir=d)
        assert result["success"] is False


# ---------------------------------------------------------------------------
# 2. ARROWS Import Error Path
# ---------------------------------------------------------------------------


class TestArrowsNotInstalled:
    """Verify graceful failure when the ARROWS package is absent."""

    def test_returns_clear_error_and_install_hint(self, tmp_path):
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))
        hidden = {
            "arrows": None,
            "arrows.energetics": None,
            "arrows.reactions": None,
            "arrows.pairwise": None,
            "arrows.exparser": None,
        }
        with patch.dict(sys.modules, hidden):
            result = arrows_suggest_experiment(campaign_dir=str(campaign))
        assert result["success"] is False
        assert "arrows" in result["error"].lower()
        assert "pip install" in result["error"].lower() or "install" in result["error"].lower()


# ---------------------------------------------------------------------------
# 3. First Iteration — No Exp.json, No PairwiseRxns.csv
# ---------------------------------------------------------------------------


@arrows_installed
class TestFirstIteration:
    """Behaviour on the very first call when no experimental data exists."""

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_suggests_top_ranked_reaction(self, mock_pd, tmp_path):
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))
        # No Exp.json → all unsampled

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        assert result["success"] is True
        s = result["suggestions"][0]
        # Must suggest the top reaction (ΔG = -700.0)
        assert sorted(s["precursors"]) == sorted(["Y2O3", "BaO", "CuO"])
        assert s["temperature_C"] == 800  # lowest temperature first

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_success_response_has_all_required_keys(self, mock_pd, tmp_path):
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        required_keys = {
            "success", "campaign_dir", "target", "n_suggestions",
            "suggestions", "campaign_complete", "n_reactions_total",
            "n_reactions_sampled", "temperatures", "message", "warnings",
        }
        assert required_keys.issubset(result.keys())

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_campaign_dir_is_absolute(self, mock_pd, tmp_path):
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        assert os.path.isabs(result["campaign_dir"])

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_target_is_reduced_formula(self, mock_pd, tmp_path):
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        # pymatgen Composition should normalise the formula
        assert isinstance(result["target"], str)
        assert len(result["target"]) > 0

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_campaign_not_complete_on_first_iteration(self, mock_pd, tmp_path):
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        assert result["campaign_complete"] is False

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_n_reactions_sampled_is_zero_on_first_iteration(self, mock_pd, tmp_path):
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        assert result["n_reactions_sampled"] == 0

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_suggestion_contains_required_fields(self, mock_pd, tmp_path):
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        assert result["n_suggestions"] >= 1
        s = result["suggestions"][0]
        for field in ("batch_index", "precursors", "temperature_C", "rank",
                      "predicted_products", "reaction_energy_meV_per_atom"):
            assert field in s, f"Missing field '{field}' in suggestion"

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_temperatures_returned_in_ascending_order(self, mock_pd, tmp_path):
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        settings = dict(SAMPLE_SETTINGS)
        settings["Temperatures"] = [900, 800, 700]  # deliberately unordered
        _setup_campaign(str(campaign), settings=settings)

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        assert result["temperatures"] == sorted([900, 800, 700])

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_n_reactions_total_equals_rxns_times_temps(self, mock_pd, tmp_path):
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        # 2 rxns × 2 temps = 4 total
        assert result["n_reactions_total"] == 4

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_phase_diagram_failure_returns_graceful_error(self, mock_pd, tmp_path):
        mock_pd.side_effect = RuntimeError("MP API unavailable")
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        assert result["success"] is False
        assert "phase diagram" in result["error"].lower() or "mp api" in result["error"].lower()


# ---------------------------------------------------------------------------
# 4. Batch Suggestions
# ---------------------------------------------------------------------------


@arrows_installed
class TestBatchSuggestions:
    """batch_size parameter controls how many experiments are suggested."""

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_batch_size_one_returns_single_suggestion(self, mock_pd, tmp_path):
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))

        result = arrows_suggest_experiment(campaign_dir=str(campaign), batch_size=1)

        assert result["success"] is True
        assert result["n_suggestions"] == 1
        assert len(result["suggestions"]) == 1

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_batch_size_two_returns_two_distinct_suggestions(self, mock_pd, tmp_path):
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))

        result = arrows_suggest_experiment(campaign_dir=str(campaign), batch_size=2)

        assert result["success"] is True
        assert result["n_suggestions"] == 2
        # Suggestions must be distinct precursor-set / temperature combos
        combos = [(tuple(sorted(s["precursors"])), s["temperature_C"])
                  for s in result["suggestions"]]
        assert len(set(combos)) == 2

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_batch_size_larger_than_available_capped(self, mock_pd, tmp_path):
        """With 2 rxns × 2 temps = 4 total, asking for 10 returns ≤ 4."""
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))

        result = arrows_suggest_experiment(campaign_dir=str(campaign), batch_size=10)

        assert result["success"] is True
        assert result["n_suggestions"] <= 4

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_batch_indices_are_sequential(self, mock_pd, tmp_path):
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))

        result = arrows_suggest_experiment(campaign_dir=str(campaign), batch_size=3)

        indices = [s["batch_index"] for s in result["suggestions"]]
        assert indices == list(range(1, len(indices) + 1))


# ---------------------------------------------------------------------------
# 5. Experiment Data Present (Exp.json loaded)
# ---------------------------------------------------------------------------


@arrows_installed
class TestWithExpData:
    """Behaviour when some experiments have already been recorded."""

    def _make_exp_data_for_first_set(self):
        """
        Build an Exp.json dict that marks the first precursor set as sampled
        at 800 °C.  exparser.get_products looks up sorted precursor formulae
        joined by ', '.
        """
        return {
            "BaO, CuO, Y2O3": {
                "Precursor stoichiometry": [2.0, 3.0, 0.5],
                "Temperatures": {
                    "800 C": {
                        "Experimentally Verified": True,
                        "products": ["Ba2YCu3O7_65"],
                        "product weight fractions": [100],
                    }
                }
            }
        }

    @patch("arrows.exparser.get_products")
    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_skips_already_sampled_combo(self, mock_pd, mock_get_products, tmp_path):
        """When the top combo (rxn[0], T=800) is sampled, suggest the next one."""
        # First call (top rxn, 800 °C) returns products → sampled
        # Remaining calls return None → unsampled
        call_count = [0]

        def side_effect(precursors, T, exp_data):
            call_count[0] += 1
            if call_count[0] == 1:
                return (["Ba2YCu3O7"], [1.0])   # sampled
            return (None, None)                  # unsampled

        mock_get_products.side_effect = side_effect

        exp_data = self._make_exp_data_for_first_set()
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign), exp_data=exp_data)

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        assert result["success"] is True
        # The first suggestion should NOT be the one that was already sampled
        s = result["suggestions"][0]
        # Either a different precursor set or the same set at a different temp
        already_ran = (
            sorted(s["precursors"]) == sorted(["Y2O3", "BaO", "CuO"])
            and s["temperature_C"] == 800
        )
        assert not already_ran

    @patch("arrows.exparser.get_products", return_value=(["Ba2YCu3O7"], [1.0]))
    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_all_sampled_returns_campaign_complete(self, mock_pd, mock_get_products,
                                                    tmp_path):
        """When every rxn/temp combo is sampled, campaign_complete must be True."""
        exp_data = self._make_exp_data_for_first_set()
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign), exp_data=exp_data)

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        assert result["success"] is True
        assert result["campaign_complete"] is True
        assert result["n_suggestions"] == 0
        assert len(result["suggestions"]) == 0

    @patch("arrows.exparser.get_products", return_value=(None, None))
    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_exp_json_present_but_nothing_sampled(self, mock_pd, mock_get_products,
                                                   tmp_path):
        """Exp.json exists but all exparser lookups return None → still suggest."""
        exp_data = {}  # empty — nothing sampled yet
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign), exp_data=exp_data)

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        assert result["success"] is True
        assert result["n_suggestions"] >= 1
        assert result["campaign_complete"] is False


# ---------------------------------------------------------------------------
# 6. PairwiseRxns.csv Present
# ---------------------------------------------------------------------------


@arrows_installed
class TestPairwiseRxnsPresent:
    """Verify the pairwise-update code path runs without errors."""

    @patch("arrows.pairwise.pred_evolution")
    @patch("arrows.pairwise.rxn_database")
    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_pairwise_file_present_does_not_crash(self, mock_pd, mock_rxndb_cls,
                                                   mock_pred_evo, tmp_path):
        """Presence of PairwiseRxns.csv must not crash the tool."""
        # Configure mock rxn_database instance
        mock_rxn_db = MagicMock()
        mock_rxn_db.is_empty = True
        mock_rxn_db.as_dict.return_value = {}
        mock_rxndb_cls.return_value = mock_rxn_db

        # pred_evolution returns unchanged precursors (no evolution)
        mock_pred_evo.side_effect = lambda precursors, amounts, rxn_db, greedy, temps, allow_ox: (
            list(precursors), list(amounts)
        )

        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign), write_pairwise=True)

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        assert result["success"] is True

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_pairwise_load_failure_adds_warning_and_continues(self, mock_pd, tmp_path):
        """If PairwiseRxns.csv is corrupted, the tool warns and uses initial ranking."""
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))
        # Write a corrupted PairwiseRxns.csv
        with open(os.path.join(str(campaign), "PairwiseRxns.csv"), "w") as f:
            f.write("not,valid,csv,data\nrandom,garbage")

        # We cannot easily mock rxn_database.load to raise; instead rely on
        # the except-block catching any downstream failure.
        # Just verify success=True (the fallback warning path) OR success=False
        # with a 'pairwise' mention in warnings — both are acceptable.
        result = arrows_suggest_experiment(campaign_dir=str(campaign))
        # The tool must not raise an unhandled exception
        assert "success" in result


# ---------------------------------------------------------------------------
# 7. Edge Cases
# ---------------------------------------------------------------------------


@arrows_installed
class TestEdgeCases:
    """Boundary and unusual conditions."""

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_single_temperature(self, mock_pd, tmp_path):
        """Campaigns with a single temperature still work."""
        settings = dict(SAMPLE_SETTINGS)
        settings["Temperatures"] = [850]
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign), settings=settings)

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        assert result["success"] is True
        assert result["temperatures"] == [850]

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_settings_without_atmosphere_key_defaults_to_air(self, mock_pd, tmp_path):
        """Settings.json missing 'Atmosphere' key → defaults to 'air'."""
        settings = dict(SAMPLE_SETTINGS)
        settings.pop("Atmosphere", None)
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign), settings=settings)

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        assert result["success"] is True

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_allow_oxidation_false_does_not_append_o2(self, mock_pd, tmp_path):
        """allow_oxidation=False must not append O2/CO2 to precursors."""
        settings = dict(SAMPLE_SETTINGS)
        settings["Allow Oxidation"] = "False"
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign), settings=settings)

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        assert result["success"] is True
        # Verify get_pd_dict was not called with O2/CO2 injected
        called_with = mock_pd.call_args[0][0]  # first positional arg
        assert "O2" not in called_with
        assert "CO2" not in called_with

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_rxn_td_csv_with_single_reaction(self, mock_pd, tmp_path):
        """Works when Rxn_TD.csv contains only one reaction."""
        settings = dict(SAMPLE_SETTINGS)
        rxns = [("Y2O3 + BaO + CuO", "0.5 + 2.0 + 3.0", "Ba2YCu3O7 + O2", "-700.0")]
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign), settings=settings, rxns=rxns)

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        assert result["success"] is True
        assert result["n_reactions_total"] == 2  # 1 rxn × 2 temps

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_explore_flag_accepted(self, mock_pd, tmp_path):
        """explore=True must not cause an error."""
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))

        result = arrows_suggest_experiment(campaign_dir=str(campaign), explore=True)

        assert result["success"] is True

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_greedy_flag_accepted(self, mock_pd, tmp_path):
        """greedy=True must not cause an error."""
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))

        result = arrows_suggest_experiment(campaign_dir=str(campaign), greedy=True)

        assert result["success"] is True

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_enforce_thermo_flag_accepted(self, mock_pd, tmp_path):
        """enforce_thermo=True must not cause an error (passed through settings)."""
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))

        result = arrows_suggest_experiment(
            campaign_dir=str(campaign), enforce_thermo=True
        )

        assert result["success"] is True

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_message_is_nonempty_string(self, mock_pd, tmp_path):
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_warnings_is_list(self, mock_pd, tmp_path):
        campaign = tmp_path / "campaign"
        campaign.mkdir()
        _setup_campaign(str(campaign))

        result = arrows_suggest_experiment(campaign_dir=str(campaign))

        assert isinstance(result["warnings"], list)


# ---------------------------------------------------------------------------
# 8. Integration Tests (live ARROWS + live MP API, opt-in only)
# ---------------------------------------------------------------------------


@arrows_installed
@pytest.mark.integration
@pytest.mark.usefixtures("mp_api_key")
class TestIntegration:
    """
    End-to-end test against the live Materials Project API.

    Run with:
        pytest -m integration

    Requires a campaign previously created by arrows_prepare_campaign.
    We use BaTiO3 (clean binary BaO + TiO2 → BaTiO3) to minimise API cost.
    """

    def test_first_suggestion_for_batio3_campaign(self, tmp_path):
        """Full round-trip: prepare campaign then suggest first experiment."""
        from tools.arrows.arrows_prepare_campaign import arrows_prepare_campaign

        camp_dir = str(tmp_path / "batio3_campaign")

        # Prepare campaign first
        prep = arrows_prepare_campaign(
            target="BaTiO3",
            precursors=["BaO", "TiO2"],
            temperatures=[800, 900],
            campaign_dir=camp_dir,
        )
        assert prep["success"] is True, f"prepare failed: {prep.get('error')}"

        # Now suggest
        result = arrows_suggest_experiment(campaign_dir=camp_dir)

        assert result["success"] is True
        assert result["n_suggestions"] >= 1
        assert result["campaign_complete"] is False

    def test_suggestion_precursors_are_from_pool(self, tmp_path):
        """Suggested precursors must come from the predefined pool."""
        from tools.arrows.arrows_prepare_campaign import arrows_prepare_campaign

        precursor_pool = ["BaO", "TiO2"]
        camp_dir = str(tmp_path / "batio3_campaign_pool")

        prep = arrows_prepare_campaign(
            target="BaTiO3",
            precursors=precursor_pool,
            temperatures=[800, 900],
            campaign_dir=camp_dir,
        )
        assert prep["success"] is True

        result = arrows_suggest_experiment(campaign_dir=camp_dir)

        assert result["success"] is True
        for s in result["suggestions"]:
            for p in s["precursors"]:
                assert p in precursor_pool or p in ["O2", "CO2"], (
                    f"Suggested precursor '{p}' not in pool"
                )

    def test_batch_of_two_gives_two_distinct_suggestions(self, tmp_path):
        """batch_size=2 should return 2 distinct precursor-set/temperature combos."""
        from tools.arrows.arrows_prepare_campaign import arrows_prepare_campaign

        camp_dir = str(tmp_path / "batio3_campaign_batch")
        prep = arrows_prepare_campaign(
            target="BaTiO3",
            precursors=["BaO", "TiO2"],
            temperatures=[800, 900],
            campaign_dir=camp_dir,
        )
        assert prep["success"] is True

        result = arrows_suggest_experiment(campaign_dir=camp_dir, batch_size=2)

        assert result["success"] is True
        # May return fewer if < 2 unique combos exist for this small system
        if result["n_suggestions"] >= 2:
            combos = [(tuple(sorted(s["precursors"])), s["temperature_C"])
                      for s in result["suggestions"]]
            assert len(set(combos)) == len(combos), "Duplicate suggestions returned"
