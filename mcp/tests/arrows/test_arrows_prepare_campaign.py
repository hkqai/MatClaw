"""
Tests for arrows_prepare_campaign tool.

Tests are organized into three categories:

1. Input validation  — no external dependencies, runs always.
2. Import error path — verifies graceful handling when ARROWS is not installed.
3. Functional tests  — require ARROWS to be installed; all network calls are
   mocked so the tests remain fast and offline-capable.

Mocking strategy
----------------
arrows_prepare_campaign performs its ARROWS imports *inside* the function body,
so we patch the live module attributes after the function has already imported
them (arrows.energetics.get_pd_dict, etc.).  The pymatgen.core.composition import
is also done inside the function but pymatgen is always available in this project.

For the "ARROWS not installed" path we temporarily hide the package from
sys.modules using unittest.mock.patch.dict so the ImportError branch is entered.
"""

import csv
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from tools.arrows.arrows_prepare_campaign import arrows_prepare_campaign

# ---------------------------------------------------------------------------
# Skip markers
# ---------------------------------------------------------------------------

arrows_installed = pytest.mark.skipif(
    "arrows" not in sys.modules and not __import__("importlib").util.find_spec("arrows"),
    reason="ARROWS package not installed",
)

# ---------------------------------------------------------------------------
# Shared minimal "good" inputs
# ---------------------------------------------------------------------------

MINIMAL_PRECURSORS = ["Y2O3", "BaO", "CuO", "BaCO3"]
MINIMAL_TARGET = "Ba2YCu3O7"
MINIMAL_TEMPS = [800, 900]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_pd_dict(precursors, temperatures, atmos="air"):
    """Return a fake pd_dict keyed by temperature."""
    return {t: MagicMock(name=f"pd_{t}") for t in temperatures}


def _mock_get_precursor_sets(precursors, target, allowed_byproducts, max_pc, allow_oxidation):
    """Return two fake balanced precursor sets."""
    return [
        (["Y2O3", "BaO", "CuO"], ["Ba2YCu3O7", "CO2"]),
        (["Y2O3", "BaCO3", "CuO"], ["Ba2YCu3O7", "CO2"]),
    ]


def _mock_get_balanced_coeffs(reactants, products):
    """Return plausible stoichiometric coefficients."""
    return ([1.0] * len(reactants), [1.0] * len(products))


def _mock_get_rxn_energy(reactants, products, temp, pd):
    """Return a negative reaction energy (thermodynamically favorable)."""
    # Second set is slightly less favorable so ranking is deterministic
    if "BaCO3" in reactants:
        return -500.0
    return -700.0


# ---------------------------------------------------------------------------
# 1. Input Validation (no ARROWS dependency)
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Validate that bad inputs are rejected before ARROWS is ever called."""

    def test_rejects_empty_precursors(self, tmp_path):
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=[],
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(tmp_path / "campaign"),
        )
        assert result["success"] is False
        assert "precursor" in result["error"].lower()

    def test_rejects_single_precursor(self, tmp_path):
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=["Y2O3"],
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(tmp_path / "campaign"),
        )
        assert result["success"] is False
        assert "precursor" in result["error"].lower()

    def test_rejects_empty_temperatures(self, tmp_path):
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=[],
            campaign_dir=str(tmp_path / "campaign"),
        )
        assert result["success"] is False
        assert "temperature" in result["error"].lower()

    def test_rejects_invalid_atmosphere(self, tmp_path):
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(tmp_path / "campaign"),
            atmosphere="vacuum",
        )
        assert result["success"] is False
        assert "atmosphere" in result["error"].lower()


# ---------------------------------------------------------------------------
# 2. ARROWS Import Error Path
# ---------------------------------------------------------------------------


class TestArrowsNotInstalled:
    """Verify graceful failure when the ARROWS package is absent."""

    def test_returns_clear_error_when_arrows_missing(self, tmp_path):
        hidden = {
            "arrows": None,
            "arrows.energetics": None,
            "arrows.reactions": None,
            "arrows.searcher": None,
        }
        with patch.dict(sys.modules, hidden):
            result = arrows_prepare_campaign(
                target=MINIMAL_TARGET,
                precursors=MINIMAL_PRECURSORS,
                temperatures=MINIMAL_TEMPS,
                campaign_dir=str(tmp_path / "campaign"),
            )

        assert result["success"] is False
        assert "ARROWS" in result["error"]
        assert "pip install" in result["error"]

    def test_error_does_not_create_campaign_files(self, tmp_path):
        """No partial output should be written when ARROWS is absent."""
        campaign_dir = tmp_path / "campaign"
        hidden = {"arrows": None, "arrows.energetics": None,
                  "arrows.reactions": None, "arrows.searcher": None}
        with patch.dict(sys.modules, hidden):
            arrows_prepare_campaign(
                target=MINIMAL_TARGET,
                precursors=MINIMAL_PRECURSORS,
                temperatures=MINIMAL_TEMPS,
                campaign_dir=str(campaign_dir),
            )

        assert not (campaign_dir / "Rxn_TD.csv").exists()
        assert not (campaign_dir / "Settings.json").exists()


# ---------------------------------------------------------------------------
# 3. Functional Tests (ARROWS mocked at module attribute level)
# ---------------------------------------------------------------------------


@arrows_installed
class TestCampaignDirectoryManagement:
    """Verify campaign directory is created and paths are absolute."""

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_creates_campaign_dir_if_missing(self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path):
        campaign_dir = tmp_path / "new_campaign"
        assert not campaign_dir.exists()

        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(campaign_dir),
        )

        assert result["success"] is True
        assert campaign_dir.exists()

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_returns_absolute_campaign_dir(self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path):
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(tmp_path / "campaign"),
        )

        assert result["success"] is True
        assert os.path.isabs(result["campaign_dir"])

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_reuses_existing_campaign_dir(self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path):
        """Calling twice should overwrite without error."""
        campaign_dir = str(tmp_path / "campaign")
        for _ in range(2):
            result = arrows_prepare_campaign(
                target=MINIMAL_TARGET,
                precursors=MINIMAL_PRECURSORS,
                temperatures=MINIMAL_TEMPS,
                campaign_dir=campaign_dir,
            )
        assert result["success"] is True


@arrows_installed
class TestReturnStructure:
    """Verify the shape and types of the return dictionary."""

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_required_top_level_keys_present(self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path):
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(tmp_path / "campaign"),
        )

        assert result["success"] is True
        for key in (
            "campaign_dir", "target", "n_reactions", "reactions",
            "rxn_td_path", "settings_path", "n_precursors_available",
            "temperatures", "atmosphere", "message", "warnings",
        ):
            assert key in result, f"Missing key: {key}"

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_n_reactions_matches_reactions_list(self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path):
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(tmp_path / "campaign"),
        )

        assert result["n_reactions"] == len(result["reactions"])

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_each_reaction_has_required_fields(self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path):
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(tmp_path / "campaign"),
        )

        for rxn in result["reactions"]:
            for field in ("rank", "precursors", "amounts", "products", "reaction_energy_meV_per_atom"):
                assert field in rxn, f"Reaction missing field: {field}"
            assert isinstance(rxn["precursors"], list)
            assert isinstance(rxn["amounts"], list)
            assert isinstance(rxn["products"], list)
            assert isinstance(rxn["reaction_energy_meV_per_atom"], float)

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_target_formula_is_normalised(self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path):
        """Pymatgen reduced formula normalisation should be applied."""
        result = arrows_prepare_campaign(
            target="Ba2YCu3O7",               # Already reduced
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(tmp_path / "campaign"),
        )
        assert result["success"] is True
        assert result["target"] == "Ba2YCu3O7"

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_n_precursors_available_matches_input(self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path):
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(tmp_path / "campaign"),
        )
        # Reported count is the user-supplied pool, not the extended pool with O2/CO2
        assert result["n_precursors_available"] == len(MINIMAL_PRECURSORS)

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_message_contains_target_and_count(self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path):
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(tmp_path / "campaign"),
        )
        assert MINIMAL_TARGET in result["message"]
        assert str(result["n_reactions"]) in result["message"]


@arrows_installed
class TestReactionRanking:
    """Verify reactions are sorted from most to least thermodynamically favorable."""

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_reactions_sorted_by_dG_ascending(self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path):
        """Rank 1 (most favorable) should have the most negative ΔG."""
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(tmp_path / "campaign"),
        )

        energies = [r["reaction_energy_meV_per_atom"] for r in result["reactions"]]
        assert energies == sorted(energies), "Reactions are not sorted ascending by ΔG"

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_ranks_are_sequential_from_one(self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path):
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(tmp_path / "campaign"),
        )

        ranks = [r["rank"] for r in result["reactions"]]
        assert ranks == list(range(1, len(ranks) + 1))


@arrows_installed
class TestOutputFiles:
    """Verify Rxn_TD.csv and Settings.json are written correctly."""

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_rxn_td_csv_created(self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path):
        campaign_dir = str(tmp_path / "campaign")
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=campaign_dir,
        )
        assert result["success"] is True
        assert os.path.isfile(result["rxn_td_path"])

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_rxn_td_csv_header_and_row_count(self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path):
        campaign_dir = str(tmp_path / "campaign")
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=campaign_dir,
        )

        with open(result["rxn_td_path"]) as f:
            reader = list(csv.reader(f))

        # Header row + one data row per reaction
        assert reader[0] == ["Precursors", "Amounts", "Products", "Reaction energy (meV/atom)"]
        assert len(reader) == result["n_reactions"] + 1

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_rxn_td_csv_sorted_by_energy(self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path):
        """Rows in CSV should be sorted most favorable first (most negative ΔG)."""
        campaign_dir = str(tmp_path / "campaign")
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=campaign_dir,
        )

        with open(result["rxn_td_path"]) as f:
            reader = list(csv.reader(f))

        energies = [float(row[3]) for row in reader[1:]]
        assert energies == sorted(energies)

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_settings_json_created(self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path):
        campaign_dir = str(tmp_path / "campaign")
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=campaign_dir,
        )
        assert result["success"] is True
        assert os.path.isfile(result["settings_path"])

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_settings_json_content(self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path):
        campaign_dir = str(tmp_path / "campaign")
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=campaign_dir,
            allow_oxidation=True,
            open_system=True,
            atmosphere="air",
        )

        with open(result["settings_path"]) as f:
            settings = json.load(f)

        assert settings["Target"] == MINIMAL_TARGET
        assert settings["Temperatures"] == MINIMAL_TEMPS
        assert settings["Allow Oxidation"] == "True"
        assert settings["Open System"] == "True"
        assert settings["Atmosphere"] == "air"
        # User-supplied precursors (without injected O2/CO2)
        for p in MINIMAL_PRECURSORS:
            assert p in settings["Precursors"]

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_settings_json_stores_max_precursors(self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path):
        campaign_dir = str(tmp_path / "campaign")
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=campaign_dir,
            max_precursors=3,
        )

        with open(result["settings_path"]) as f:
            settings = json.load(f)

        assert settings.get("Max Precursors") == 3

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_settings_json_omits_max_precursors_when_not_set(
        self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path
    ):
        campaign_dir = str(tmp_path / "campaign")
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=campaign_dir,
        )

        with open(result["settings_path"]) as f:
            settings = json.load(f)

        assert "Max Precursors" not in settings


@arrows_installed
class TestDefaultParameters:
    """Verify default parameter behaviour matches ARROWS conventions."""

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_allow_oxidation_true_adds_O2_CO2_to_effective_pool(
        self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path
    ):
        """When allow_oxidation=True, get_pd_dict should receive O2 and CO2."""
        arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(tmp_path / "campaign"),
            allow_oxidation=True,
        )
        call_precursors = mock_pd.call_args[0][0]
        assert "O2" in call_precursors
        assert "CO2" in call_precursors

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_allow_oxidation_false_excludes_O2_from_effective_pool(
        self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path
    ):
        """When allow_oxidation=False, O2 must NOT be in get_pd_dict call."""
        arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(tmp_path / "campaign"),
            allow_oxidation=False,
        )
        call_precursors = mock_pd.call_args[0][0]
        assert "O2" not in call_precursors

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_default_allowed_byproducts_with_oxidation(
        self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path
    ):
        """Default byproducts should be ['O2', 'CO2'] when allow_oxidation=True."""
        campaign_dir = str(tmp_path / "campaign")
        arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=campaign_dir,
            allow_oxidation=True,
        )
        with open(os.path.join(campaign_dir, "Settings.json")) as f:
            settings = json.load(f)
        assert "O2" in settings["Allowed Byproducts"]
        assert "CO2" in settings["Allowed Byproducts"]

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_default_allowed_byproducts_without_oxidation(
        self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path
    ):
        """Default byproducts should be ['CO2'] only when allow_oxidation=False."""
        campaign_dir = str(tmp_path / "campaign")
        arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=campaign_dir,
            allow_oxidation=False,
        )
        with open(os.path.join(campaign_dir, "Settings.json")) as f:
            settings = json.load(f)
        assert "O2" not in settings["Allowed Byproducts"]
        assert "CO2" in settings["Allowed Byproducts"]

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_explicit_allowed_byproducts_override_defaults(
        self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path
    ):
        """Explicit allowed_byproducts should bypass auto-defaults."""
        campaign_dir = str(tmp_path / "campaign")
        arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=campaign_dir,
            allowed_byproducts=["H2O"],
        )
        with open(os.path.join(campaign_dir, "Settings.json")) as f:
            settings = json.load(f)
        assert settings["Allowed Byproducts"] == ["H2O"]

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_inert_atmosphere_stored_in_settings(
        self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path
    ):
        campaign_dir = str(tmp_path / "campaign")
        arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=campaign_dir,
            atmosphere="inert",
        )
        with open(os.path.join(campaign_dir, "Settings.json")) as f:
            settings = json.load(f)
        assert settings["Atmosphere"] == "inert"


@arrows_installed
class TestErrorHandlingDuringExecution:
    """Verify graceful failure when ARROWS functions raise exceptions."""

    @patch("arrows.energetics.get_pd_dict", side_effect=RuntimeError("MP API error"))
    def test_phase_diagram_failure_returns_error(self, mock_pd, tmp_path):
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(tmp_path / "campaign"),
        )
        assert result["success"] is False
        assert "phase diagram" in result["error"].lower() or "MP API" in result["error"]

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", return_value=[])
    def test_no_balanced_sets_returns_error(self, mock_pc, mock_pd, tmp_path):
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(tmp_path / "campaign"),
        )
        assert result["success"] is False
        assert result["n_reactions"] == 0
        assert "precursor" in result["error"].lower() or "balanced" in result["error"].lower()

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=Exception("balancer error"))
    @patch("arrows.reactions.get_rxn_energy", side_effect=_mock_get_rxn_energy)
    def test_all_reactions_fail_energy_returns_error(
        self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path
    ):
        """If every reaction fails energy evaluation, tool returns failure."""
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(tmp_path / "campaign"),
        )
        assert result["success"] is False

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.searcher.get_precursor_sets", side_effect=_mock_get_precursor_sets)
    @patch("arrows.reactions.get_balanced_coeffs", side_effect=_mock_get_balanced_coeffs)
    @patch("arrows.reactions.get_rxn_energy", side_effect=[Exception("one failed"), -600.0])
    def test_partial_failure_adds_warning(self, mock_erg, mock_rxn_e, mock_pc, mock_pd, tmp_path):
        """If some (not all) reactions fail energy evaluation, result is still success
        but a warning is added."""
        result = arrows_prepare_campaign(
            target=MINIMAL_TARGET,
            precursors=MINIMAL_PRECURSORS,
            temperatures=MINIMAL_TEMPS,
            campaign_dir=str(tmp_path / "campaign"),
        )
        assert result["success"] is True
        assert result["n_reactions"] == 1
        assert len(result["warnings"]) > 0
        warning_text = " ".join(result["warnings"]).lower()
        assert "1" in warning_text or "skip" in warning_text


# ---------------------------------------------------------------------------
# 4. Integration Tests (live ARROWS + live MP API, opt-in only)
# ---------------------------------------------------------------------------


@arrows_installed
@pytest.mark.integration
@pytest.mark.usefixtures("mp_api_key")
class TestIntegration:
    """
    End-to-end tests against the live Materials Project API via ARROWS.

    Run with:
        pytest -m integration

    These are excluded from the default test suite to avoid network dependency
    and latency in CI.  BaTiO3 is used as the target: BaO + TiO2 → BaTiO3 is a
    classic binary solid-state reaction with a well-characterised thermodynamic
    driving force and compact Ba-Ti-O chemical space.
    """

    def test_successful_campaign_for_simple_binary(self, tmp_path):
        """Full round-trip: phase diagram → enumeration → ranking → file output."""
        result = arrows_prepare_campaign(
            target="BaTiO3",
            precursors=["BaO", "TiO2"],
            temperatures=[800, 900],
            campaign_dir=str(tmp_path / "campaign"),
        )

        assert result["success"] is True
        assert result["target"] == "BaTiO3"
        assert result["n_reactions"] >= 1
        assert len(result["reactions"]) == result["n_reactions"]

    def test_rxn_td_csv_written_and_parsable(self, tmp_path):
        """Rxn_TD.csv produced by a real campaign must be readable by ARROWS suggest.py."""
        result = arrows_prepare_campaign(
            target="BaTiO3",
            precursors=["BaO", "TiO2"],
            temperatures=[800, 900],
            campaign_dir=str(tmp_path / "campaign"),
        )

        assert result["success"] is True
        assert os.path.isfile(result["rxn_td_path"])

        with open(result["rxn_td_path"]) as f:
            reader = list(csv.reader(f))

        # ARROWS suggest.py expects exactly this header
        assert reader[0] == ["Precursors", "Amounts", "Products", "Reaction energy (meV/atom)"]
        # At least one data row
        assert len(reader) >= 2
        # Energy column must be a valid float
        for row in reader[1:]:
            float(row[3])

    def test_settings_json_loadable_by_arrows(self, tmp_path):
        """Settings.json must satisfy ARROWS' expected key structure."""
        result = arrows_prepare_campaign(
            target="BaTiO3",
            precursors=["BaO", "TiO2"],
            temperatures=[800, 900],
            campaign_dir=str(tmp_path / "campaign"),
        )

        assert result["success"] is True

        with open(result["settings_path"]) as f:
            settings = json.load(f)

        # All keys required by ARROWS suggest.py / gather_rxns.py
        for key in ("Precursors", "Target", "Allowed Byproducts", "Temperatures",
                    "Open System", "Allow Oxidation"):
            assert key in settings, f"Settings.json missing required ARROWS key: {key}"

        assert isinstance(settings["Precursors"], list)
        assert isinstance(settings["Temperatures"], list)

    def test_reactions_are_thermodynamically_favorable(self, tmp_path):
        """For a well-known system all returned reactions should have ΔG < 0."""
        result = arrows_prepare_campaign(
            target="BaTiO3",
            precursors=["BaO", "TiO2"],
            temperatures=[800, 900],
            campaign_dir=str(tmp_path / "campaign"),
        )

        assert result["success"] is True
        for rxn in result["reactions"]:
            assert rxn["reaction_energy_meV_per_atom"] < 0, (
                f"Expected negative ΔG, got {rxn['reaction_energy_meV_per_atom']} "
                f"for precursors: {rxn['precursors']}"
            )

    def test_no_warnings_on_clean_run(self, tmp_path):
        """A well-formed campaign with valid inputs should produce no warnings."""
        result = arrows_prepare_campaign(
            target="BaTiO3",
            precursors=["BaO", "TiO2"],
            temperatures=[800, 900],
            campaign_dir=str(tmp_path / "campaign"),
        )

        assert result["success"] is True
        assert result["warnings"] == [], f"Unexpected warnings: {result['warnings']}"
