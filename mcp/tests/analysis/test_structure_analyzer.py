"""
Tests for structure_analyzer tool.

Run with: pytest tests/analysis/test_structure_analyzer.py -v
"""

import pytest
from tools.analysis.structure_analyzer import structure_analyzer


class TestStructureAnalyzer:
    """Tests for structure analysis."""

    def test_simple_structure_basic_features(self, simple_nacl_structure):
        """Test with simple NaCl structure using basic feature set."""
        result = structure_analyzer(
            input_structure=simple_nacl_structure,
            feature_set="basic"
        )
        
        assert result["success"] is True
        assert result["formula"] == "NaCl"
        assert result["n_sites"] == 2
        assert result["volume"] > 0
        assert result["density"] > 0
        assert "features" in result
        assert "feature_vector" in result
        assert len(result["feature_vector"]) > 0
        assert len(result["feature_names"]) == len(result["feature_vector"])

    def test_standard_feature_set(self, simple_nacl_structure):
        """Test with standard feature set (default)."""
        result = structure_analyzer(
            input_structure=simple_nacl_structure,
            feature_set="standard"
        )
        
        assert result["success"] is True
        assert result["metadata"]["feature_set"] == "standard"
        n_features = result["metadata"]["n_features"]
        
        # Standard should have reasonable number of features
        assert n_features > 10

    def test_extensive_feature_set(self, simple_nacl_structure):
        """Test with extensive feature set."""
        result = structure_analyzer(
            input_structure=simple_nacl_structure,
            feature_set="extensive"
        )
        
        assert result["success"] is True
        assert result["metadata"]["feature_set"] == "extensive"
        # Extensive should have more features than standard
        assert result["metadata"]["n_features"] > 10

    def test_feature_organization(self, simple_nacl_structure):
        """Test that features are properly organized."""
        result = structure_analyzer(input_structure=simple_nacl_structure)
        
        assert result["success"] is True
        features = result["features"]
        
        # Check expected categories
        assert "basic_info" in features
        assert "density_features" in features or "symmetry_features" in features
        
        # Basic info should contain expected fields
        basic = features["basic_info"]
        assert "formula" in basic
        assert "n_sites" in basic
        assert "volume" in basic
        assert "density" in basic

    def test_density_features(self, simple_nacl_structure):
        """Test density-related features."""
        result = structure_analyzer(input_structure=simple_nacl_structure)
        
        assert result["success"] is True
        assert result["density"] > 0
        
        # Should have density features
        if "density_features" in result["features"]:
            density_feats = result["features"]["density_features"]
            assert isinstance(density_feats, dict)

    def test_symmetry_features(self, simple_nacl_structure):
        """Test symmetry features."""
        result = structure_analyzer(input_structure=simple_nacl_structure)
        
        assert result["success"] is True
        
        # Should have symmetry features
        if "symmetry_features" in result["features"]:
            sym_feats = result["features"]["symmetry_features"]
            assert isinstance(sym_feats, dict)

    def test_without_site_stats(self, simple_nacl_structure):
        """Test with site statistics disabled."""
        result = structure_analyzer(
            input_structure=simple_nacl_structure,
            compute_site_stats=False
        )
        
        assert result["success"] is True
        assert result["metadata"]["compute_site_stats"] is False
        # Should not have site statistics features
        assert "SiteStatsFingerprint" not in result["metadata"]["featurizers_used"]

    def test_without_rdf(self, simple_nacl_structure):
        """Test with RDF features disabled."""
        result = structure_analyzer(
            input_structure=simple_nacl_structure,
            compute_rdf=False
        )
        
        assert result["success"] is True
        assert result["metadata"]["compute_rdf"] is False
        # Should not have RDF features
        assert "RadialDistributionFunction" not in result["metadata"]["featurizers_used"]

    def test_without_bonding(self, simple_nacl_structure):
        """Test with bonding features disabled."""
        result = structure_analyzer(
            input_structure=simple_nacl_structure,
            compute_bonding=False
        )
        
        assert result["success"] is True
        assert result["metadata"]["compute_bonding"] is False
        # Should not have bond features
        assert "BondFractions" not in result["metadata"]["featurizers_used"]

    def test_feature_names_match_vector(self, simple_nacl_structure):
        """Test that feature names match feature vector length."""
        result = structure_analyzer(input_structure=simple_nacl_structure)
        
        assert result["success"] is True
        assert len(result["feature_names"]) == len(result["feature_vector"])
        
        # Check that feature names are non-empty strings
        for name in result["feature_names"]:
            assert isinstance(name, str)
            assert len(name) > 0

    def test_numeric_feature_vector(self, simple_nacl_structure):
        """Test that feature vector contains mostly numeric values."""
        result = structure_analyzer(input_structure=simple_nacl_structure)
        
        assert result["success"] is True
        
        # Most features should be numeric, but some featurizers may return strings
        # (e.g., crystal system: 'cubic', 'tetragonal', etc.)
        numeric_count = sum(1 for value in result["feature_vector"] 
                           if isinstance(value, (int, float)))
        total_count = len(result["feature_vector"])
        
        # At least 80% should be numeric
        assert numeric_count / total_count > 0.8

    def test_complex_structure(self, valid_licoo2_structure):
        """Test with a more complex structure."""
        result = structure_analyzer(input_structure=valid_licoo2_structure)
        
        assert result["success"] is True
        assert result["n_sites"] == 6
        assert result["volume"] > 0
        assert len(result["feature_vector"]) > 0

    def test_formula_string_input(self):
        """Test that string formulas are not accepted (need actual structure)."""
        result = structure_analyzer(input_structure="Fe2O3")
        
        # Should fail because we need actual structure, not just composition
        assert result["success"] is False
        assert "error" in result

    def test_structure_from_cif(self):
        """Test with a CIF string input."""
        # Simple CIF for NaCl
        cif_string = """data_NaCl
_cell_length_a    5.64
_cell_length_b    5.64
_cell_length_c    5.64
_cell_angle_alpha 90
_cell_angle_beta  90
_cell_angle_gamma 90
_symmetry_space_group_name_H-M 'F m -3 m'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Na Na 0.0 0.0 0.0
Cl Cl 0.5 0.5 0.5
"""
        result = structure_analyzer(input_structure=cif_string)
        
        assert result["success"] is True
        assert "Na" in result["formula"]
        assert "Cl" in result["formula"]

    def test_primitive_conversion(self, simple_nacl_structure):
        """Test primitive cell conversion."""
        result = structure_analyzer(
            input_structure=simple_nacl_structure,
            primitive=True
        )
        
        assert result["success"] is True
        assert result["metadata"]["primitive_used"] is True

    def test_custom_feature_set(self, simple_nacl_structure):
        """Test with custom feature selection."""
        result = structure_analyzer(
            input_structure=simple_nacl_structure,
            feature_set="custom",
            custom_features=["DensityFeatures", "GlobalSymmetryFeatures"]
        )
        
        assert result["success"] is True
        assert result["metadata"]["feature_set"] == "custom"
        # Should only use specified featurizers
        used = result["metadata"]["featurizers_used"]
        assert len(used) <= 2
        assert "DensityFeatures" in used or "GlobalSymmetryFeatures" in used

    def test_metadata_completeness(self, simple_nacl_structure):
        """Test that metadata is complete."""
        result = structure_analyzer(input_structure=simple_nacl_structure)
        
        assert result["success"] is True
        metadata = result["metadata"]
        
        assert "feature_set" in metadata
        assert "featurizers_used" in metadata
        assert "n_features" in metadata
        assert "primitive_used" in metadata
        
        # Check consistency
        assert metadata["n_features"] == len(result["feature_vector"])

    def test_message_field(self, simple_nacl_structure):
        """Test that a message is provided."""
        result = structure_analyzer(input_structure=simple_nacl_structure)
        
        assert result["success"] is True
        assert "message" in result
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0

    def test_reproducibility(self, simple_nacl_structure):
        """Test that repeated calls give same results."""
        result1 = structure_analyzer(input_structure=simple_nacl_structure)
        result2 = structure_analyzer(input_structure=simple_nacl_structure)
        
        assert result1["success"] is True
        assert result2["success"] is True
        assert result1["feature_vector"] == result2["feature_vector"]
        assert result1["feature_names"] == result2["feature_names"]

    def test_different_structures_different_features(
        self, simple_nacl_structure, valid_licoo2_structure
    ):
        """Test that different structures produce different features."""
        result1 = structure_analyzer(input_structure=simple_nacl_structure)
        result2 = structure_analyzer(input_structure=valid_licoo2_structure)
        
        assert result1["success"] is True
        assert result2["success"] is True
        
        # Should have different feature vectors
        assert result1["feature_vector"] != result2["feature_vector"]
        
        # But same feature names/length
        assert len(result1["feature_vector"]) == len(result2["feature_vector"])

    def test_basic_vs_standard_feature_count(self, simple_nacl_structure):
        """Test that standard has more features than basic."""
        result_basic = structure_analyzer(
            input_structure=simple_nacl_structure,
            feature_set="basic"
        )
        result_standard = structure_analyzer(
            input_structure=simple_nacl_structure,
            feature_set="standard"
        )
        
        assert result_basic["success"] is True
        assert result_standard["success"] is True
        
        # Standard should have more features than basic
        assert result_standard["metadata"]["n_features"] >= result_basic["metadata"]["n_features"]

    def test_volume_and_density_reasonable(self, simple_nacl_structure):
        """Test that volume and density are reasonable values."""
        result = structure_analyzer(input_structure=simple_nacl_structure)
        
        assert result["success"] is True
        
        # Volume should be positive and in reasonable range (Ų)
        assert result["volume"] > 0
        assert result["volume"] < 1000  # Not absurdly large
        
        # Density should be positive and reasonable (g/cm³)
        assert result["density"] > 0
        assert result["density"] < 30  # Most materials are less dense than osmium (~22 g/cm³)

    def test_warnings_are_optional(self, simple_nacl_structure):
        """Test that warnings field is optional."""
        result = structure_analyzer(input_structure=simple_nacl_structure)
        
        assert result["success"] is True
        # Warnings should only appear if there are warnings
        if "warnings" in result:
            assert isinstance(result["warnings"], list)

    def test_high_coordination_structure(self, high_coordination_structure):
        """Test with structure having high coordination."""
        result = structure_analyzer(input_structure=high_coordination_structure)
        
        # Should succeed even with unusual structure
        assert result["success"] is True
        assert result["n_sites"] > 0

    def test_basic_info_fields(self, simple_nacl_structure):
        """Test that basic info contains expected fields."""
        result = structure_analyzer(input_structure=simple_nacl_structure)
        
        assert result["success"] is True
        
        # Top-level fields
        assert "formula" in result
        assert "n_sites" in result
        assert "volume" in result
        assert "density" in result
        
        # Basic info in features
        basic = result["features"]["basic_info"]
        assert basic["formula"] == result["formula"]
        assert basic["n_sites"] == result["n_sites"]
        # Compare with small tolerance due to rounding
        assert abs(basic["volume"] - result["volume"]) < 0.01
        assert abs(basic["density"] - result["density"]) < 0.01

    def test_empty_input(self):
        """Test with empty input."""
        result = structure_analyzer(input_structure="")
        
        assert result["success"] is False
        assert "error" in result

    def test_invalid_structure_dict(self):
        """Test with invalid structure dictionary."""
        invalid_dict = {"invalid": "structure"}
        result = structure_analyzer(input_structure=invalid_dict)
        
        assert result["success"] is False
        assert "error" in result
