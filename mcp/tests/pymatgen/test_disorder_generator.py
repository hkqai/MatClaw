"""
Tests for pymatgen_disorder_generator tool.

Tests creating disordered structures with mixed site occupancies from ordered inputs.
Primary fixture: ordered_cucr2se4 — CuCr₂Se₄ spinel structure from Materials Project.
"""

import json
import pytest
from tools.pymatgen.pymatgen_disorder_generator import pymatgen_disorder_generator


def _has_disorder(structure_dict: dict) -> bool:
    """Return True if any site in a Structure dict has multiple species."""
    from pymatgen.core import Structure
    s = Structure.from_dict(structure_dict)
    return any(not site.is_ordered for site in s)


# TestBasicDisorder
class TestBasicDisorder:
    """Smoke tests: tool runs without error and returns well-formed output."""

    def test_returns_success_with_simple_disorder(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}}
        )
        assert result["success"] is True

    def test_count_matches_input(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}}
        )
        assert result["count"] == 1
        assert len(result["structures"]) == 1

    def test_metadata_length_matches_structures(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}}
        )
        assert len(result["metadata"]) == len(result["structures"])

    def test_output_structure_is_disordered(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}}
        )
        assert _has_disorder(result["structures"][0]), \
            "Output should have partial occupancies (disorder)"

    def test_result_has_message(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}}
        )
        assert "message" in result
        assert isinstance(result["message"], str)

    def test_result_has_substitution_rules(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}}
        )
        assert "substitution_rules" in result
        assert isinstance(result["substitution_rules"], dict)

    def test_result_has_input_info(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}}
        )
        assert "input_info" in result


# TestMetadataFields
class TestMetadataFields:
    """Verify all documented per-structure metadata keys are present."""

    REQUIRED_KEYS = {
        "index",
        "original_formula",
        "formula",
        "reduced_formula",
        "disorder_applied",
        "charge_neutral",
        "n_sites",
        "volume",
        "lattice",
    }

    def test_all_required_keys_present(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}}
        )
        meta = result["metadata"][0]
        for key in self.REQUIRED_KEYS:
            assert key in meta, f"Missing metadata key: {key}"

    def test_index_is_one_based(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}}
        )
        assert result["metadata"][0]["index"] == 1

    def test_disorder_applied_is_dict(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}}
        )
        assert isinstance(result["metadata"][0]["disorder_applied"], dict)

    def test_disorder_applied_contains_element(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}}
        )
        disorder_info = result["metadata"][0]["disorder_applied"]
        assert "Cr" in disorder_info

    def test_n_sites_positive(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}}
        )
        assert result["metadata"][0]["n_sites"] > 0

    def test_volume_positive(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}}
        )
        assert result["metadata"][0]["volume"] > 0

    def test_lattice_has_parameters(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}}
        )
        lattice = result["metadata"][0]["lattice"]
        required_params = {"a", "b", "c", "alpha", "beta", "gamma"}
        for param in required_params:
            assert param in lattice, f"Missing lattice parameter: {param}"


# TestSiteSubstitutions
class TestSiteSubstitutions:
    """Test that site_substitutions are applied correctly."""

    def test_simple_binary_disorder(self, ordered_cucr2se4):
        """Cr → {Cr: 0.85, Sn: 0.15} should create mixed occupancy on Cr sites."""
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}}
        )
        from pymatgen.core import Structure
        s = Structure.from_dict(result["structures"][0])
        
        # Find a Cr site (should now have mixed occupancy)
        cr_site = None
        for site in s:
            if "Cr" in [str(sp) for sp in site.species.keys()]:
                cr_site = site
                break
        
        assert cr_site is not None, "Should have at least one Cr-containing site"
        species_dict = {str(sp): occ for sp, occ in cr_site.species.items()}
        
        if len(species_dict) > 1:  # Disorder applied
            assert "Cr" in species_dict
            assert "Sn" in species_dict
            assert abs(species_dict["Cr"] - 0.85) < 0.01
            assert abs(species_dict["Sn"] - 0.15) < 0.01

    def test_ternary_disorder(self, ordered_cucr2se4):
        """Test three-element mixing on same site."""
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.5, "Sn": 0.3, "Ti": 0.2}}
        )
        from pymatgen.core import Structure
        s = Structure.from_dict(result["structures"][0])
        
        # Check that disorder was applied
        assert _has_disorder(result["structures"][0])

    def test_multiple_element_substitutions(self, ordered_cucr2se4):
        """Test applying disorder to multiple elements simultaneously."""
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={
                "Cr": {"Cr": 0.85, "Sn": 0.15},
                "Se": {"Se": 0.5, "S": 0.5}
            }
        )
        assert result["success"] is True
        
        disorder_info = result["metadata"][0]["disorder_applied"]
        assert "Cr" in disorder_info
        assert "Se" in disorder_info


# TestValidation
class TestValidation:
    """Test input validation and error handling."""

    def test_fractions_must_sum_to_one(self, ordered_cucr2se4):
        """Fractions that don't sum to 1.0 should raise error."""
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.5, "Sn": 0.3}}  # sums to 0.8
        )
        assert result["success"] is False
        assert "sum to" in result["error"].lower()

    def test_negative_fractions_rejected(self, ordered_cucr2se4):
        """Negative fractions should be rejected."""
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 1.2, "Sn": -0.2}}
        )
        assert result["success"] is False
        assert "negative" in result["error"].lower()

    def test_empty_substitutions_rejected(self, ordered_cucr2se4):
        """Empty site_substitutions should be rejected."""
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={}
        )
        assert result["success"] is False

    def test_invalid_output_format_rejected(self, ordered_cucr2se4):
        """Invalid output_format should be rejected."""
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}},
            output_format="invalid_format"
        )
        assert result["success"] is False
        assert "output_format" in result["error"].lower()

    def test_element_not_in_structure_warns(self, ordered_cucr2se4):
        """Substituting an element not in the structure should warn."""
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Li": {"Li": 0.5, "Na": 0.5}}  # No Li in CuCr2Se4
        )
        # Should succeed but warn
        assert result["success"] is True
        assert result["warnings"] is not None
        assert any("Li" in w for w in result["warnings"])


# TestOutputFormats
class TestOutputFormats:
    """Test different output formats."""

    def test_dict_format(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}},
            output_format="dict"
        )
        assert isinstance(result["structures"][0], dict)
        assert "@module" in result["structures"][0]

    def test_cif_format(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}},
            output_format="cif"
        )
        assert isinstance(result["structures"][0], str)
        assert "data_" in result["structures"][0] or "_cell_" in result["structures"][0]

    def test_json_format(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}},
            output_format="json"
        )
        assert isinstance(result["structures"][0], str)
        # Should be valid JSON
        parsed = json.loads(result["structures"][0])
        assert isinstance(parsed, dict)


# TestCompositionTolerance
class TestCompositionTolerance:
    """Test composition_tolerance parameter."""

    def test_strict_tolerance_rejects_small_deviation(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.14}},  # sums to 0.99
            composition_tolerance=0.005  # Very strict
        )
        assert result["success"] is False

    def test_loose_tolerance_accepts_small_deviation(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.14}},  # sums to 0.99
            composition_tolerance=0.02  # Looser
        )
        assert result["success"] is True


# TestMultipleStructures
class TestMultipleStructures:
    """Test processing multiple input structures."""

    def test_two_structures_returns_two_outputs(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=[ordered_cucr2se4, ordered_cucr2se4],
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}}
        )
        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["structures"]) == 2

    def test_input_info_tracks_multiple_structures(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=[ordered_cucr2se4, ordered_cucr2se4],
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}}
        )
        assert result["input_info"]["n_input_structures"] == 2


# TestChargeNeutrality
class TestChargeNeutrality:
    """Test charge neutrality validation."""

    def test_charge_neutrality_validation_runs(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}},
            validate_charge_neutrality=True
        )
        assert result["success"] is True
        # charge_neutral should be set (could be True, False, or None)
        assert "charge_neutral" in result["metadata"][0]

    def test_skip_charge_neutrality_validation(self, ordered_cucr2se4):
        result = pymatgen_disorder_generator(
            input_structures=ordered_cucr2se4,
            site_substitutions={"Cr": {"Cr": 0.85, "Sn": 0.15}},
            validate_charge_neutrality=False
        )
        assert result["success"] is True
