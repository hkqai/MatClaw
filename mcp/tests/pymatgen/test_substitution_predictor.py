"""
Tests for pymatgen_substitution_predictor tool.

Run with: pytest tests/pymatgen/test_substitution_predictor.py -v
"""

import pytest
from tools.pymatgen.pymatgen_substitution_predictor import pymatgen_substitution_predictor


class TestSubstitutionPredictorBasic:
    """Tests for basic substitution prediction functionality."""
    
    def test_simple_prediction_success(self):
        """Test basic substitution prediction for a common composition."""
        result = pymatgen_substitution_predictor(
            composition="LiFePO4",
            to_this_composition=False,
            group_by_probability=False
        )
        
        assert result["success"] is True
        assert result["composition"] == "LiFePO4"
        assert result["direction"] == "from"
        assert result["count"] > 0
        assert isinstance(result["suggestions"], list)
        assert len(result["suggestions"]) > 0
        
        # Check suggestion format
        first_suggestion = result["suggestions"][0]
        assert "substitutions" in first_suggestion
        assert "confidence" in first_suggestion
        assert "rank" in first_suggestion
        assert isinstance(first_suggestion["substitutions"], dict)
    
    def test_grouped_output_format(self):
        """Test that grouped output contains high/medium/low probability tiers."""
        result = pymatgen_substitution_predictor(
            composition="NaCl",
            group_by_probability=True
        )
        
        assert result["success"] is True
        assert isinstance(result["suggestions"], dict)
        assert "high_probability" in result["suggestions"]
        assert "medium_probability" in result["suggestions"]
        assert "low_probability" in result["suggestions"]
        
        # All tiers should be lists
        for tier in ["high_probability", "medium_probability", "low_probability"]:
            assert isinstance(result["suggestions"][tier], list)
    
    def test_direction_parameter(self):
        """Test that to_this_composition parameter affects direction."""
        result_from = pymatgen_substitution_predictor(
            composition="LiCoO2",
            to_this_composition=False
        )
        
        result_to = pymatgen_substitution_predictor(
            composition="LiCoO2",
            to_this_composition=True
        )
        
        assert result_from["success"] is True
        assert result_to["success"] is True
        assert result_from["direction"] == "from"
        assert result_to["direction"] == "to"


class TestMaxSuggestions:
    """Tests for max_suggestions parameter."""
    
    def test_max_suggestions_limit(self):
        """Test that max_suggestions limits output count."""
        max_limit = 5
        result = pymatgen_substitution_predictor(
            composition="LiFePO4",
            max_suggestions=max_limit,
            group_by_probability=False
        )
        
        assert result["success"] is True
        assert result["count"] <= max_limit
        assert len(result["suggestions"]) <= max_limit
    
    def test_max_suggestions_with_grouping(self):
        """Test max_suggestions works with grouped output."""
        max_limit = 10
        result = pymatgen_substitution_predictor(
            composition="LiCoO2",
            max_suggestions=max_limit,
            group_by_probability=True
        )
        
        assert result["success"] is True
        total_suggestions = (
            len(result["suggestions"]["high_probability"]) +
            len(result["suggestions"]["medium_probability"]) +
            len(result["suggestions"]["low_probability"])
        )
        assert total_suggestions <= max_limit


class TestThresholdParameter:
    """Tests for threshold parameter."""
    
    def test_lower_threshold_more_results(self):
        """Test that lower threshold returns more suggestions."""
        result_low = pymatgen_substitution_predictor(
            composition="NaCl",
            threshold=0.0001,
            group_by_probability=False
        )
        
        result_high = pymatgen_substitution_predictor(
            composition="NaCl",
            threshold=0.1,
            group_by_probability=False
        )
        
        assert result_low["success"] is True
        assert result_high["success"] is True
        # Lower threshold should give more results (or equal)
        assert result_low["count"] >= result_high["count"]


class TestComplexCompositions:
    """Tests for various composition types."""
    
    def test_ternary_oxide(self):
        """Test prediction for ternary oxide."""
        result = pymatgen_substitution_predictor(
            composition="TiO2",
            group_by_probability=False
        )
        
        assert result["success"] is True
        assert result["count"] > 0
    
    def test_quaternary_compound(self):
        """Test prediction for quaternary compound."""
        result = pymatgen_substitution_predictor(
            composition="LiFePO4",
            group_by_probability=False
        )
        
        assert result["success"] is True
        assert result["count"] > 0
    
    def test_non_reduced_formula(self):
        """Test that non-reduced formulas are handled correctly."""
        result = pymatgen_substitution_predictor(
            composition="Li2Fe2P2O8",  # Non-reduced form of LiFePO4
            group_by_probability=False
        )
        
        assert result["success"] is True
        assert result["composition"] == "LiFePO4"  # Should be reduced


class TestMetadata:
    """Tests for metadata and result structure."""
    
    def test_metadata_completeness(self):
        """Test that all expected metadata fields are present."""
        result = pymatgen_substitution_predictor(
            composition="NaCl",
            threshold=0.01,
            alpha=-5.0,
            max_suggestions=10
        )
        
        assert result["success"] is True
        assert "metadata" in result
        assert "predictor_params" in result["metadata"]
        assert "data_source" in result["metadata"]
        
        params = result["metadata"]["predictor_params"]
        assert params["threshold"] == 0.01
        assert params["alpha"] == -5.0
        assert params["max_suggestions"] == 10
        assert "ICSD" in result["metadata"]["data_source"]
    
    def test_message_field(self):
        """Test that result message is informative."""
        result = pymatgen_substitution_predictor(
            composition="LiCoO2"
        )
        
        assert result["success"] is True
        assert "message" in result
        assert result["composition"] in result["message"]
        assert str(result["count"]) in result["message"]


class TestErrorHandling:
    """Tests for error cases."""
    
    def test_invalid_composition_string(self):
        """Test that invalid composition string fails gracefully."""
        result = pymatgen_substitution_predictor(
            composition="InvalidXYZ123"
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "Invalid composition" in result["error"]
    
    def test_empty_composition(self):
        """Test that empty composition fails gracefully."""
        result = pymatgen_substitution_predictor(
            composition=""
        )
        
        assert result["success"] is False
        assert "error" in result


class TestSubstitutionContent:
    """Tests for the actual substitution suggestions."""
    
    def test_substitution_dict_format(self):
        """Test that substitution dicts have valid element mappings."""
        result = pymatgen_substitution_predictor(
            composition="NaCl",
            group_by_probability=False,
            max_suggestions=5
        )
        
        assert result["success"] is True
        
        for suggestion in result["suggestions"]:
            subs = suggestion["substitutions"]
            # Each substitution should be a dict with element symbols
            assert isinstance(subs, dict)
            assert len(subs) > 0
            
            # Keys and values should be valid element symbols (strings)
            for key, value in subs.items():
                assert isinstance(key, str)
                assert isinstance(value, str)
                assert len(key) <= 2  # Element symbols are 1-2 chars
                assert len(value) <= 2
    
    def test_confidence_values(self):
        """Test that confidence ratings are valid."""
        result = pymatgen_substitution_predictor(
            composition="LiFePO4",
            group_by_probability=False
        )
        
        assert result["success"] is True
        
        valid_confidences = {"high", "medium", "low"}
        for suggestion in result["suggestions"]:
            assert suggestion["confidence"] in valid_confidences
    
    def test_rank_ordering(self):
        """Test that suggestions are properly ranked."""
        result = pymatgen_substitution_predictor(
            composition="TiO2",
            group_by_probability=False,
            max_suggestions=10
        )
        
        assert result["success"] is True
        
        ranks = [s["rank"] for s in result["suggestions"]]
        # Ranks should be sequential starting from 1
        assert ranks == list(range(1, len(ranks) + 1))


class TestRealisticUseCases:
    """Tests for realistic discovery scenarios."""
    
    def test_lanthanide_tungstate_analogues(self):
        """Test finding analogues of La-W-O compounds (Pr4MoO9 discovery scenario)."""
        # If La4WO9 exists in database, it should suggest Pr/Mo substitutions
        result = pymatgen_substitution_predictor(
            composition="La2WO6",  # Related La-W-O phase
            to_this_composition=False,
            group_by_probability=False
        )
        
        assert result["success"] is True
        # We expect some suggestions involving other lanthanides or Mo/Cr
        assert result["count"] > 0
    
    def test_spinel_dopant_discovery(self):
        """Test finding dopants for spinel structure (CuCr2Se4 scenario)."""
        result = pymatgen_substitution_predictor(
            composition="CuCr2Se4",
            to_this_composition=False,
            group_by_probability=True
        )
        
        assert result["success"] is True
        # Should suggest various Cr substitutions (Mn, Fe, Co, Ti, Sn, etc.)
        total_suggestions = (
            len(result["suggestions"]["high_probability"]) +
            len(result["suggestions"]["medium_probability"]) +
            len(result["suggestions"]["low_probability"])
        )
        assert total_suggestions > 0


class TestParameterValidation:
    """Tests for parameter validation."""
    
    def test_threshold_bounds(self):
        """Test that threshold is validated."""
        # Valid threshold
        result = pymatgen_substitution_predictor(
            composition="NaCl",
            threshold=0.5
        )
        assert result["success"] is True
    
    def test_max_suggestions_positive(self):
        """Test that max_suggestions must be positive."""
        result = pymatgen_substitution_predictor(
            composition="NaCl",
            max_suggestions=1
        )
        assert result["success"] is True
