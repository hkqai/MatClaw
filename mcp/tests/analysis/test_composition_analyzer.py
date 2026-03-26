"""
Tests for composition_analyzer tool.

Run with: pytest tests/analysis/test_composition_analyzer.py -v
"""

import pytest
from tools.analysis.composition_analyzer import composition_analyzer


class TestCompositionAnalyzer:
    """Tests for composition analysis."""

    def test_simple_formula_string(self):
        """Test with a simple composition string."""
        result = composition_analyzer(input_structure="Fe2O3")
        
        assert result["success"] is True
        assert result["composition"] == "Fe2O3"
        assert result["n_elements"] == 2
        assert set(result["element_list"]) == {"Fe", "O"}
        assert "elemental_fractions" in result
        assert "features" in result
        assert "feature_vector" in result
        assert len(result["feature_vector"]) > 0
        assert len(result["feature_names"]) == len(result["feature_vector"])

    def test_complex_composition(self):
        """Test with a complex composition."""
        result = composition_analyzer(input_structure="LiCoO2")
        
        assert result["success"] is True
        assert result["composition"] == "LiCoO2"
        assert result["n_elements"] == 3
        assert set(result["element_list"]) == {"Li", "Co", "O"}
        
        # Check elemental fractions sum to 1
        fractions = result["elemental_fractions"]
        assert abs(sum(fractions.values()) - 1.0) < 1e-6

    def test_structure_dict_input(self, simple_nacl_structure):
        """Test with a Structure dict as input."""
        result = composition_analyzer(input_structure=simple_nacl_structure)
        
        assert result["success"] is True
        assert result["composition"] == "NaCl"
        assert result["n_elements"] == 2
        assert set(result["element_list"]) == {"Na", "Cl"}

    def test_basic_feature_set(self):
        """Test with basic feature set."""
        result = composition_analyzer(
            input_structure="Fe2O3",
            feature_set="basic"
        )
        
        assert result["success"] is True
        assert result["metadata"]["feature_set"] == "basic"
        # Basic should have fewer features than standard
        n_features_basic = result["metadata"]["n_features"]
        assert n_features_basic > 0

    def test_standard_feature_set(self):
        """Test with standard feature set (default)."""
        result = composition_analyzer(
            input_structure="Fe2O3",
            feature_set="standard"
        )
        
        assert result["success"] is True
        assert result["metadata"]["feature_set"] == "standard"
        n_features_standard = result["metadata"]["n_features"]
        
        # Standard should have reasonable number of features
        assert n_features_standard > 20

    def test_extensive_feature_set(self):
        """Test with extensive feature set."""
        result = composition_analyzer(
            input_structure="Fe2O3",
            feature_set="extensive"
        )
        
        assert result["success"] is True
        assert result["metadata"]["feature_set"] == "extensive"
        # Extensive should have most features
        n_features_extensive = result["metadata"]["n_features"]
        assert n_features_extensive > 30

    def test_without_oxidation_features(self):
        """Test with oxidation features disabled."""
        result = composition_analyzer(
            input_structure="LiCoO2",
            include_oxidation_features=False
        )
        
        assert result["success"] is True
        assert result["metadata"]["include_oxidation_features"] is False
        # Should not include oxidation state featurizers
        assert "OxidationStates" not in result["metadata"]["featurizers_used"]

    def test_feature_organization(self):
        """Test that features are properly organized."""
        result = composition_analyzer(input_structure="Al2O3")
        
        assert result["success"] is True
        assert "features" in result
        features = result["features"]
        
        # Check expected categories
        assert "basic_info" in features
        assert "element_stats" in features or "stoichiometry" in features
        
        # Basic info should contain expected fields
        basic = features["basic_info"]
        assert "n_elements" in basic
        assert "element_list" in basic
        assert "elemental_fractions" in basic

    def test_elemental_fractions(self):
        """Test elemental fraction calculations."""
        result = composition_analyzer(input_structure="Li2FePO4")
        
        assert result["success"] is True
        fractions = result["elemental_fractions"]
        
        # Check individual fractions
        assert fractions["Li"] == pytest.approx(2/8, abs=1e-6)
        assert fractions["Fe"] == pytest.approx(1/8, abs=1e-6)
        assert fractions["P"] == pytest.approx(1/8, abs=1e-6)
        assert fractions["O"] == pytest.approx(4/8, abs=1e-6)

    def test_feature_names_match_vector(self):
        """Test that feature names match feature vector length."""
        result = composition_analyzer(input_structure="TiO2")
        
        assert result["success"] is True
        assert len(result["feature_names"]) == len(result["feature_vector"])
        
        # Check that feature names are non-empty strings
        for name in result["feature_names"]:
            assert isinstance(name, str)
            assert len(name) > 0

    def test_numeric_feature_vector(self):
        """Test that feature vector contains only numeric values."""
        result = composition_analyzer(input_structure="SiO2")
        
        assert result["success"] is True
        
        for value in result["feature_vector"]:
            # Should be numeric (int or float) or NaN
            assert isinstance(value, (int, float))

    def test_invalid_composition_string(self):
        """Test with invalid composition string."""
        result = composition_analyzer(input_structure="XyZ123Invalid")
        
        assert result["success"] is False
        assert "error" in result

    def test_empty_composition(self):
        """Test with empty/invalid input."""
        result = composition_analyzer(input_structure="")
        
        assert result["success"] is False
        assert "error" in result

    def test_binary_compound(self):
        """Test with binary compound."""
        result = composition_analyzer(input_structure="GaN")
        
        assert result["success"] is True
        assert result["n_elements"] == 2
        assert result["composition"] == "GaN"

    def test_ternary_compound(self):
        """Test with ternary compound."""
        result = composition_analyzer(input_structure="BaTiO3")
        
        assert result["success"] is True
        assert result["n_elements"] == 3
        assert result["composition"] == "BaTiO3"

    def test_quaternary_compound(self):
        """Test with quaternary compound."""
        result = composition_analyzer(input_structure="CuInGaSe2")
        
        assert result["success"] is True
        assert result["n_elements"] == 4
        
    def test_metadata_completeness(self):
        """Test that metadata is complete."""
        result = composition_analyzer(input_structure="ZnO")
        
        assert result["success"] is True
        metadata = result["metadata"]
        
        assert "feature_set" in metadata
        assert "featurizers_used" in metadata
        assert "n_features" in metadata
        assert "include_oxidation_features" in metadata
        
        # Check consistency
        assert metadata["n_features"] == len(result["feature_vector"])

    def test_warnings_for_difficult_composition(self):
        """Test that warnings are provided when appropriate."""
        # Some compositions might have issues with oxidation state assignment
        result = composition_analyzer(
            input_structure="PrBaCo2O5",
            include_oxidation_features=True
        )
        
        # Should succeed but might have warnings
        assert result["success"] is True
        # Warnings are optional
        if "warnings" in result:
            assert isinstance(result["warnings"], list)

    def test_custom_feature_set(self):
        """Test with custom feature selection."""
        result = composition_analyzer(
            input_structure="CaTiO3",
            feature_set="custom",
            custom_features=["ElementProperty", "Stoichiometry"]
        )
        
        assert result["success"] is True
        assert result["metadata"]["feature_set"] == "custom"
        # Should only use specified featurizers
        used = result["metadata"]["featurizers_used"]
        assert len(used) <= 2

    def test_licoo2_composition(self, valid_licoo2_structure):
        """Test with LiCoO2 structure from fixture."""
        result = composition_analyzer(input_structure=valid_licoo2_structure)
        
        assert result["success"] is True
        assert result["n_elements"] == 3
        assert "Li" in result["element_list"]
        assert "Co" in result["element_list"]
        assert "O" in result["element_list"]

    def test_message_field(self):
        """Test that a message is provided."""
        result = composition_analyzer(input_structure="Si")
        
        assert result["success"] is True
        assert "message" in result
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0

    def test_reproducibility(self):
        """Test that repeated calls give same results."""
        comp = "Al2O3"
        
        result1 = composition_analyzer(input_structure=comp)
        result2 = composition_analyzer(input_structure=comp)
        
        assert result1["success"] is True
        assert result2["success"] is True
        assert result1["feature_vector"] == result2["feature_vector"]
        assert result1["feature_names"] == result2["feature_names"]

    def test_single_element_composition(self):
        """Test with single element."""
        result = composition_analyzer(input_structure="Cu")
        
        assert result["success"] is True
        assert result["n_elements"] == 1
        assert result["element_list"] == ["Cu"]
        assert result["elemental_fractions"]["Cu"] == 1.0
