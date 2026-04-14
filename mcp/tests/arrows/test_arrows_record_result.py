"""
Tests for arrows_record_result tool.

Mock strategy
-------------
arrows_record_result imports ARROWS inside the function body.  To keep tests
fast, offline, and deterministic the following ARROWS symbols are patched:

  arrows.energetics.get_pd_dict      -- builds phase diagrams (needed by retroanalyze)
  arrows.pairwise.retroanalyze       -- infers pairwise reactions from observed products
  arrows.pairwise.rxn_database       -- pairwise reaction database (load / update / save)

The file I/O (Exp.json, PairwiseRxns.csv) is NOT mocked — it runs against real
temporary directories so that the JSON/CSV round-trip behaviour is also tested.

Integration tests that actually call ARROWS are marked with ``@integration``
and only run when `MP_API_KEY` is available (via the ``mp_api_key`` fixture).
"""

import csv
import json
import os
import sys
from unittest.mock import MagicMock, patch, call

import pytest

from tools.arrows.arrows_record_result import arrows_record_result

# ---------------------------------------------------------------------------
# Skip markers
# ---------------------------------------------------------------------------

arrows_installed = pytest.mark.skipif(
    "arrows" not in sys.modules
    and not __import__("importlib").util.find_spec("arrows"),
    reason="ARROWS package not installed",
)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

SAMPLE_SETTINGS = {
    "Precursors": ["BaO", "TiO2"],
    "Target": "BaTiO3",
    "Allowed Byproducts": ["CO2"],
    "Temperatures": [700, 800, 900],
    "Open System": "True",
    "Allow Oxidation": "True",
    "Atmosphere": "air",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_settings(campaign_dir, settings=None):
    """Write Settings.json to campaign_dir."""
    if settings is None:
        settings = SAMPLE_SETTINGS
    with open(os.path.join(campaign_dir, "Settings.json"), "w") as f:
        json.dump(settings, f)


def _write_exp_json(campaign_dir, exp_data: dict):
    """Write Exp.json to campaign_dir (wraps in Universal File key)."""
    with open(os.path.join(campaign_dir, "Exp.json"), "w") as f:
        json.dump({"Universal File": exp_data}, f, indent=4)


def _write_pairwise_csv(campaign_dir):
    """Write an empty PairwiseRxns.csv header."""
    with open(os.path.join(campaign_dir, "PairwiseRxns.csv"), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Pairwise reactants", "Pairwise Products", "Temperature Range"])


def _mock_pd_dict(precursors, temperatures, atmos="air"):
    """Fake pd_dict keyed by temperature integer."""
    return {t: MagicMock(name=f"pd_{t}") for t in temperatures}


def _make_mock_rxn_db():
    """Create a mock rxn_database instance."""
    db = MagicMock()
    db.is_empty = True
    db.known_rxns = {}
    db.load = MagicMock()
    db.update = MagicMock(return_value=False)
    db.save = MagicMock()
    return db


# ---------------------------------------------------------------------------
# 1. Input Validation — no ARROWS required
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Bad inputs must be rejected before any ARROWS calls are made."""

    def test_rejects_nonexistent_campaign_dir(self, tmp_path):
        result = arrows_record_result(
            campaign_dir=str(tmp_path / "does_not_exist"),
            precursors=["BaO", "TiO2"],
            temperature_C=800,
            products=["BaTiO3_99"],
            weight_fractions=[1.0],
        )
        assert result["success"] is False
        assert "not found" in result["error"].lower() or "directory" in result["error"].lower()

    def test_rejects_missing_settings_json(self, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        result = arrows_record_result(
            campaign_dir=str(campaign),
            precursors=["BaO", "TiO2"],
            temperature_C=800,
            products=["BaTiO3_99"],
            weight_fractions=[1.0],
        )
        assert result["success"] is False
        assert "settings.json" in result["error"].lower()

    def test_rejects_mismatched_products_and_weight_fractions(self, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))
        result = arrows_record_result(
            campaign_dir=str(campaign),
            precursors=["BaO", "TiO2"],
            temperature_C=800,
            products=["BaTiO3_99", "BaO_225"],      # 2 products
            weight_fractions=[1.0],                  # only 1 weight fraction
        )
        assert result["success"] is False
        assert "same length" in result["error"].lower() or "length" in result["error"].lower()

    def test_rejects_empty_products_list(self, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))
        result = arrows_record_result(
            campaign_dir=str(campaign),
            precursors=["BaO", "TiO2"],
            temperature_C=800,
            products=[],
            weight_fractions=[],
        )
        assert result["success"] is False
        assert "empty" in result["error"].lower() or "not be empty" in result["error"].lower()

    def test_rejects_corrupted_settings_json(self, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        with open(os.path.join(str(campaign), "Settings.json"), "w") as f:
            f.write("{not valid json")
        result = arrows_record_result(
            campaign_dir=str(campaign),
            precursors=["BaO", "TiO2"],
            temperature_C=800,
            products=["BaTiO3_99"],
            weight_fractions=[1.0],
        )
        assert result["success"] is False

    def test_warns_when_weight_fractions_sum_far_from_one(self, tmp_path):
        """Sum ≠ ~1.0 should produce a warning but not fail outright."""
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        with (
            patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict),
            patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()),
            patch("arrows.pairwise.retroanalyze", return_value=(
                "No reactions occurred.", [], [], None, []
            )),
        ):
            result = arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[0.3],          # far from 1.0
            )

        # Should still succeed (warning only, not an error)
        assert result["success"] is True
        assert any("weight fraction" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# 2. ARROWS import error path
# ---------------------------------------------------------------------------


class TestArrowsNotInstalled:
    """When ARROWS is absent the Exp.json must still be written."""

    def test_exp_json_written_even_when_arrows_absent(self, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        hidden = {k: None for k in [
            "arrows", "arrows.energetics", "arrows.pairwise", "arrows.exparser",
        ]}
        with patch.dict(sys.modules, hidden):
            result = arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        assert result["success"] is True
        assert os.path.isfile(os.path.join(str(campaign), "Exp.json"))
        assert any("arrows" in w.lower() for w in result["warnings"])

    def test_pairwise_csv_not_created_when_arrows_absent(self, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        hidden = {k: None for k in [
            "arrows", "arrows.energetics", "arrows.pairwise", "arrows.exparser",
        ]}
        with patch.dict(sys.modules, hidden):
            result = arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        # PairwiseRxns.csv must NOT be created if ARROWS not available
        assert not os.path.isfile(os.path.join(str(campaign), "PairwiseRxns.csv"))


# ---------------------------------------------------------------------------
# 3. Exp.json creation and formatting
# ---------------------------------------------------------------------------


@arrows_installed
class TestExpJsonWriting:
    """Verify that Exp.json is written with the correct ARROWS-compatible structure."""

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_creates_exp_json_when_absent(self, mock_retro, mock_pd, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        with patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()):
            result = arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        assert result["success"] is True
        exp_path = os.path.join(str(campaign), "Exp.json")
        assert os.path.isfile(exp_path)

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_exp_json_has_universal_file_key(self, mock_retro, mock_pd, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        with patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()):
            arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        with open(os.path.join(str(campaign), "Exp.json")) as f:
            data = json.load(f)
        assert "Universal File" in data

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_precursor_key_is_sorted_reduced_formulae(self, mock_retro, mock_pd, tmp_path):
        """Key must be alphabetically sorted reduced formulae joined by ', '."""
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        with patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()):
            arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["TiO2", "BaO"],     # deliberately reversed
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        with open(os.path.join(str(campaign), "Exp.json")) as f:
            data = json.load(f)
        uf = data["Universal File"]
        # Both "BaO, TiO2" and "TiO2, BaO" are unacceptable — only sorted one exists
        assert "BaO, TiO2" in uf
        assert "TiO2, BaO" not in uf

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_temperature_key_format(self, mock_retro, mock_pd, tmp_path):
        """Temperature key must be '<int> C' format."""
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        with patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()):
            arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        with open(os.path.join(str(campaign), "Exp.json")) as f:
            data = json.load(f)
        temps = data["Universal File"]["BaO, TiO2"]["Temperatures"]
        assert "800 C" in temps

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_experimentally_verified_is_true(self, mock_retro, mock_pd, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        with patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()):
            arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        with open(os.path.join(str(campaign), "Exp.json")) as f:
            data = json.load(f)
        entry = data["Universal File"]["BaO, TiO2"]["Temperatures"]["800 C"]
        assert entry["Experimentally Verified"] is True

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_products_and_weight_fractions_stored(self, mock_retro, mock_pd, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        with patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()):
            arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99", "BaO_225"],
                weight_fractions=[0.9, 0.1],
            )

        with open(os.path.join(str(campaign), "Exp.json")) as f:
            data = json.load(f)
        entry = data["Universal File"]["BaO, TiO2"]["Temperatures"]["800 C"]
        assert entry["products"] == ["BaTiO3_99", "BaO_225"]
        assert entry["product weight fractions"] == pytest.approx([0.9, 0.1])

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_appends_to_existing_exp_json(self, mock_retro, mock_pd, tmp_path):
        """A second call must add to the file rather than overwrite it."""
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))
        _write_exp_json(str(campaign), {
            "Y2O3, BaO, CuO": {
                "Temperatures": {
                    "900 C": {
                        "Experimentally Verified": True,
                        "products": ["Ba2YCu3O6_139"],
                        "product weight fractions": [1.0],
                    }
                }
            }
        })

        with patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()):
            arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        with open(os.path.join(str(campaign), "Exp.json")) as f:
            data = json.load(f)
        uf = data["Universal File"]
        # Both entries must be present
        assert "Y2O3, BaO, CuO" in uf
        assert "BaO, TiO2" in uf

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_overwrite_warns_and_replaces_entry(self, mock_retro, mock_pd, tmp_path):
        """Recording the same precursors+temperature twice emits a warning."""
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))
        _write_exp_json(str(campaign), {
            "BaO, TiO2": {
                "Temperatures": {
                    "800 C": {
                        "Experimentally Verified": True,
                        "products": ["BaO_225"],
                        "product weight fractions": [1.0],
                    }
                }
            }
        })

        with patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()):
            result = arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        assert result["success"] is True
        assert result["overwrite"] is True
        assert any("overwriting" in w.lower() for w in result["warnings"])

        # The entry must contain the NEW products
        with open(os.path.join(str(campaign), "Exp.json")) as f:
            data = json.load(f)
        entry = data["Universal File"]["BaO, TiO2"]["Temperatures"]["800 C"]
        assert entry["products"] == ["BaTiO3_99"]


# ---------------------------------------------------------------------------
# 4. PairwiseRxns.csv creation and updating
# ---------------------------------------------------------------------------


@arrows_installed
class TestPairwiseCsv:
    """Verify that PairwiseRxns.csv is created / updated correctly."""

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_pairwise_csv_created_when_absent(self, mock_retro, mock_pd, tmp_path):
        """When PairwiseRxns.csv is absent, save() must be called and result path reported."""
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        mock_db = _make_mock_rxn_db()
        with patch("arrows.pairwise.rxn_database", return_value=mock_db):
            result = arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        assert result["success"] is True
        # save() must have been called with the expected path
        mock_db.save.assert_called_once_with(
            to=os.path.join(str(campaign), "PairwiseRxns.csv")
        )
        # The returned path must point to the expected location even though
        # save() is mocked (file not actually written)
        assert result["pairwise_csv_path"] == os.path.join(
            str(campaign), "PairwiseRxns.csv"
        )

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_pairwise_csv_loaded_when_present(self, mock_retro, mock_pd, tmp_path):
        """If PairwiseRxns.csv already exists, rxn_database.load() must be called."""
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))
        _write_pairwise_csv(str(campaign))

        mock_db = _make_mock_rxn_db()
        with patch("arrows.pairwise.rxn_database", return_value=mock_db):
            arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        mock_db.load.assert_called_once()

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_pairwise_csv_not_loaded_when_absent(self, mock_retro, mock_pd, tmp_path):
        """If PairwiseRxns.csv is absent, rxn_database.load() must NOT be called."""
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        mock_db = _make_mock_rxn_db()
        with patch("arrows.pairwise.rxn_database", return_value=mock_db):
            arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        mock_db.load.assert_not_called()

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_rxn_database_save_always_called(self, mock_retro, mock_pd, tmp_path):
        """save() must be called even when retroanalyze learns nothing new."""
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        mock_db = _make_mock_rxn_db()
        with patch("arrows.pairwise.rxn_database", return_value=mock_db):
            arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        mock_db.save.assert_called_once()

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_retroanalyze_called_with_correct_precursors(
        self, mock_retro, mock_pd, tmp_path
    ):
        """retroanalyze must receive reduced + sorted precursor formulae."""
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        with patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()):
            arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["TiO2", "BaO"],   # reversed on purpose
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        # retroanalyze must receive sorted precursors as positional arg
        call_kwargs = mock_retro.call_args
        precs_arg = call_kwargs.kwargs.get(
            "precursors", call_kwargs.args[0] if call_kwargs.args else None
        )
        assert sorted(precs_arg) == ["BaO", "TiO2"]

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_corrupted_pairwise_csv_warns_and_continues(
        self, mock_retro, mock_pd, tmp_path
    ):
        """A malformed PairwiseRxns.csv must produce a warning, not crash."""
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))
        with open(os.path.join(str(campaign), "PairwiseRxns.csv"), "w") as f:
            f.write("garbage, not, a, valid, csv\nwith no schema\n")

        # Make load() raise an exception (simulating corrupt file)
        mock_db = _make_mock_rxn_db()
        mock_db.load.side_effect = Exception("parse error")
        with patch("arrows.pairwise.rxn_database", return_value=mock_db):
            result = arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        assert result["success"] is True
        assert any("pairedrxns" in w.lower() or "pairwise" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# 5. Return value contract
# ---------------------------------------------------------------------------


@arrows_installed
class TestReturnValue:
    """Verify that every required field is present and typed correctly."""

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_all_required_keys_present_on_success(self, mock_retro, mock_pd, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        with patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()):
            result = arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        required = {
            "success", "campaign_dir", "precursor_key", "temperature_key",
            "products_recorded", "weight_fractions_recorded",
            "exp_json_path", "pairwise_csv_path",
            "new_reactions_learned", "retroanalyze_message",
            "overwrite", "message", "warnings",
        }
        assert required.issubset(result.keys())

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_campaign_dir_is_absolute(self, mock_retro, mock_pd, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        with patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()):
            result = arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        assert os.path.isabs(result["campaign_dir"])

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_precursor_key_format(self, mock_retro, mock_pd, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        with patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()):
            result = arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["TiO2", "BaO"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        assert result["precursor_key"] == "BaO, TiO2"

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_temperature_key_format(self, mock_retro, mock_pd, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        with patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()):
            result = arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=850,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        assert result["temperature_key"] == "850 C"

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_success_flag_is_true(self, mock_retro, mock_pd, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        with patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()):
            result = arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        assert result["success"] is True

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "Reaction pathway fully determined.", [
            [["BaO", "TiO2"], ["BaTiO3"]]
        ], ["BaTiO3"], None, []
    ))
    def test_new_reactions_learned_positive_when_updated(
        self, mock_retro, mock_pd, tmp_path
    ):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        mock_db = _make_mock_rxn_db()
        mock_db.update.return_value = True
        mock_db.known_rxns = {"BaO+TiO2": [[{"BaTiO3"}, [0, 800], "Local"]]}

        with patch("arrows.pairwise.rxn_database", return_value=mock_db):
            result = arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        assert result["new_reactions_learned"] > 0

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_overwrite_false_on_fresh_entry(self, mock_retro, mock_pd, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        with patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()):
            result = arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        assert result["overwrite"] is False

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_exp_json_path_and_pairwise_csv_path_are_absolute(
        self, mock_retro, mock_pd, tmp_path
    ):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        with patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()):
            result = arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        assert os.path.isabs(result["exp_json_path"])
        assert os.path.isabs(result["pairwise_csv_path"])

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_warnings_is_list(self, mock_retro, mock_pd, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        with patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()):
            result = arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        assert isinstance(result["warnings"], list)

    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    @patch("arrows.pairwise.retroanalyze", return_value=(
        "No reactions occurred.", [], [], None, []
    ))
    def test_no_warnings_on_clean_run(self, mock_retro, mock_pd, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        with patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()):
            result = arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        assert result["warnings"] == []


# ---------------------------------------------------------------------------
# 6. Retroanalyze message routing
# ---------------------------------------------------------------------------


@arrows_installed
class TestRetroanalyzeMsgRouting:
    """Verify that different retroanalyze messages are forwarded correctly."""

    @pytest.mark.parametrize("mssg", [
        "No reactions occurred.",
        "Reaction pathway fully determined.",
        "Reaction pathway partially determined.",
        "Only known intermediate reactions occured.",
    ])
    @patch("arrows.energetics.get_pd_dict", side_effect=_mock_pd_dict)
    def test_retroanalyze_message_stored_in_return(self, mock_pd, mssg, tmp_path):
        campaign = tmp_path / "camp"
        campaign.mkdir()
        _write_settings(str(campaign))

        with (
            patch("arrows.pairwise.retroanalyze", return_value=(
                mssg, [], [], None, []
            )),
            patch("arrows.pairwise.rxn_database", return_value=_make_mock_rxn_db()),
        ):
            result = arrows_record_result(
                campaign_dir=str(campaign),
                precursors=["BaO", "TiO2"],
                temperature_C=800,
                products=["BaTiO3_99"],
                weight_fractions=[1.0],
            )

        assert result["success"] is True
        assert result["retroanalyze_message"] == mssg


# ---------------------------------------------------------------------------
# 7. Integration with real ARROWS calls (skip if MP_API_KEY absent)
# ---------------------------------------------------------------------------


@arrows_installed
@pytest.mark.usefixtures("mp_api_key")
class TestIntegration:
    """End-to-end integration tests that call real ARROWS functionality."""

    def test_record_result_for_batio3_campaign(self, tmp_path):
        """
        Simulate recording the first experiment result for BaTiO3 synthesis:
          precursors = BaO + TiO2 at 800 °C → BaTiO3.
        Verifies the full path: Exp.json write + real retroanalyze + PairwiseRxns.csv save.
        """
        campaign = tmp_path / "batio3_campaign"
        campaign.mkdir()
        _write_settings(str(campaign))

        result = arrows_record_result(
            campaign_dir=str(campaign),
            precursors=["BaO", "TiO2"],
            temperature_C=800,
            products=["BaTiO3_99"],
            weight_fractions=[1.0],
        )

        assert result["success"] is True, f"Tool failed: {result.get('error')}"
        assert os.path.isfile(result["exp_json_path"])
        assert os.path.isfile(result["pairwise_csv_path"])

        # Check Exp.json content
        with open(result["exp_json_path"]) as f:
            data = json.load(f)
        uf = data["Universal File"]
        assert "BaO, TiO2" in uf
        assert "800 C" in uf["BaO, TiO2"]["Temperatures"]

    def test_round_trip_with_suggest(self, tmp_path):
        """
        After recording a result, arrows_suggest_experiment must recognise
        that experiment as sampled and not suggest it again.
        """
        from tools.arrows.arrows_initialize_campaign import arrows_initialize_campaign
        from tools.arrows.arrows_suggest_experiment import arrows_suggest_experiment

        campaign = tmp_path / "batio3_campaign_rt"
        campaign_str = str(campaign)

        # Prepare
        prep = arrows_initialize_campaign(
            target="BaTiO3",
            precursors=["BaO", "TiO2"],
            temperatures=[800, 900],
            campaign_dir=campaign_str,
        )
        assert prep["success"] is True, f"Prepare failed: {prep.get('error')}"

        # Suggest first experiment
        sug1 = arrows_suggest_experiment(campaign_dir=campaign_str)
        assert sug1["success"] is True
        first = sug1["suggestions"][0]

        # Record the result
        rec = arrows_record_result(
            campaign_dir=campaign_str,
            precursors=first["precursors"],
            temperature_C=first["temperature_C"],
            products=["BaTiO3_99"],
            weight_fractions=[1.0],
        )
        assert rec["success"] is True

        # Suggest again — the recorded experiment must not appear again
        sug2 = arrows_suggest_experiment(campaign_dir=campaign_str)
        assert sug2["success"] is True
        if not sug2["campaign_complete"]:
            second_combos = [
                (tuple(sorted(s["precursors"])), s["temperature_C"])
                for s in sug2["suggestions"]
            ]
            first_combo = (tuple(sorted(first["precursors"])), first["temperature_C"])
            assert first_combo not in second_combos, (
                f"Recorded experiment {first_combo} was suggested again."
            )
