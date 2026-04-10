"""
Integration tests for er_predict_precursors tool.

These tests load the actual model files and verify that the tool works end-to-end.
They are slower than unit tests and require model files to be available.

Run with: pytest tests/elemwise_retro/test_er_predict_precursors_integration.py -v
Skip with: pytest -m "not integration"
"""

import pytest
import os
from tools.elemwise_retro.er_predict_precursors import er_predict_precursors
from utils import model_downloader


@pytest.mark.integration
@pytest.mark.slow
class TestPrecursorPredictionIntegration:
    """Integration tests that load real models and make predictions."""
    
    def test_model_can_be_loaded(self):
        """Test that the precursor prediction model can be loaded successfully."""
        try:
            # This will download the model if not cached, or use cached version
            model_path = model_downloader.get_model_path('elemwiseretro_precursor_predictor')
            assert os.path.exists(model_path), f"Model file not found at {model_path}"
        except Exception as e:
            pytest.skip(f"Model file not available: {e}")
    
    def test_predict_lifepo4_precursors(self):
        """Test prediction of precursors for LiFePO4 (battery material)."""
        try:
            result = er_predict_precursors(
                target_formula="LiFePO4",
                top_k=3
            )
            
            # Validate result structure
            assert "target" in result
            assert result["target"] == "LiFePO4"
            
            assert "precursor_sets" in result
            assert isinstance(result["precursor_sets"], list)
            assert len(result["precursor_sets"]) == 3
            
            # Validate each precursor set
            for precursor_set in result["precursor_sets"]:
                assert "precursors" in precursor_set
                assert isinstance(precursor_set["precursors"], list)
                assert len(precursor_set["precursors"]) > 0
                
                assert "confidence" in precursor_set
                assert isinstance(precursor_set["confidence"], float)
                assert 0.0 <= precursor_set["confidence"] <= 1.0
            
            # Validate top prediction
            assert "top_prediction" in result
            assert result["top_prediction"] == result["precursor_sets"][0]
            
            # Validate metadata
            assert "metadata" in result
            assert "model_version" in result["metadata"]
            
            # Expected precursors should contain Li, Fe, and P sources
            top_precursors = result["top_prediction"]["precursors"]
            elements_covered = set()
            for precursor in top_precursors:
                if "Li" in precursor:
                    elements_covered.add("Li")
                if "Fe" in precursor:
                    elements_covered.add("Fe")
                if "P" in precursor:
                    elements_covered.add("P")
            
            assert "Li" in elements_covered, "Top prediction should include Li source"
            assert "Fe" in elements_covered, "Top prediction should include Fe source"
            assert "P" in elements_covered, "Top prediction should include P source"
            
        except FileNotFoundError as e:
            pytest.skip(f"Model file not available: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error during prediction: {e}")
    
    def test_predict_simple_oxide(self):
        """Test prediction for a simple binary oxide like Li2O."""
        try:
            result = er_predict_precursors(
                target_formula="Li2O",
                top_k=5
            )
            
            assert result["target"] == "Li2O"
            assert len(result["precursor_sets"]) == 5
            
            # All precursor sets should have confidence scores
            confidences = [ps["confidence"] for ps in result["precursor_sets"]]
            # Confidences should be sorted in descending order
            assert confidences == sorted(confidences, reverse=True), \
                "Precursor sets should be sorted by confidence (descending)"
            
        except FileNotFoundError:
            pytest.skip("Model file not available")
    
    def test_predict_complex_oxide(self):
        """Test prediction for a complex oxide like Li7La3Zr2O12 (LLZO)."""
        try:
            result = er_predict_precursors(
                target_formula="Li7La3Zr2O12",
                top_k=3
            )
            
            assert result["target"] == "Li7La3Zr2O12"
            assert len(result["precursor_sets"]) == 3
            
            # Should have precursors for Li, La, and Zr
            top_precursors = result["top_prediction"]["precursors"]
            assert len(top_precursors) >= 3, \
                "Complex material should have multiple precursors"
            
        except FileNotFoundError:
            pytest.skip("Model file not available")
    
    def test_model_device_handling(self):
        """Test that model works on both CPU and CUDA (if available)."""
        import torch
        
        try:
            result = er_predict_precursors("LiFePO4", top_k=1)
            assert result is not None
            
            # If we got here, model loaded successfully on available device
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"Model successfully ran on device: {device}")
            
        except FileNotFoundError:
            pytest.skip("Model file not available")


@pytest.mark.integration
class TestPrecursorPredictionEdgeCases:
    """Integration tests for edge cases and error handling."""
    
    def test_predict_with_hydroxide(self):
        """Test prediction for hydroxide like La(OH)3."""
        try:
            result = er_predict_precursors(
                target_formula="La(OH)3",
                top_k=3
            )
            
            # Should handle formulas with O and H
            assert result["target"] == "La(OH)3"
            assert len(result["precursor_sets"]) > 0
            
        except FileNotFoundError:
            pytest.skip("Model file not available")
    
    def test_predict_with_single_top_k(self):
        """Test prediction with top_k=1."""
        try:
            result = er_predict_precursors("NaCoO2", top_k=1)
            
            assert len(result["precursor_sets"]) == 1
            assert result["top_prediction"] == result["precursor_sets"][0]
            
        except FileNotFoundError:
            pytest.skip("Model file not available")


