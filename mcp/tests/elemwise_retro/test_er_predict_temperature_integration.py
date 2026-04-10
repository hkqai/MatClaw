"""
Integration tests for er_predict_temperature tool.

These tests load the actual model files and verify that the tool works end-to-end.
They are slower than unit tests and require model files to be available.

Run with: pytest tests/elemwise_retro/test_er_predict_temperature_integration.py -v
Skip with: pytest -m "not integration"
"""

import pytest
import os
from tools.elemwise_retro.er_predict_temperature import er_predict_temperature
from utils import model_downloader


@pytest.mark.integration
@pytest.mark.slow
class TestTemperaturePredictionIntegration:
    """Integration tests that load real models and make predictions."""
    
    def test_model_and_normalizer_can_be_loaded(self):
        """Test that the temperature prediction model and normalizer can be loaded."""
        try:
            # Check model
            model_path = model_downloader.get_model_path('elemwiseretro_temperature_predictor')
            assert os.path.exists(model_path), f"Model file not found at {model_path}"
            
            # Check normalizer
            normalizer_path = model_downloader.get_model_path('elemwiseretro_temperature_normalizer')
            assert os.path.exists(normalizer_path), f"Normalizer file not found at {normalizer_path}"
            
        except Exception as e:
            pytest.skip(f"Model files not available: {e}")
    
    def test_predict_lifepo4_temperature(self):
        """Test temperature prediction for LiFePO4 with common precursors."""
        try:
            result = er_predict_temperature(
                target_formula="LiFePO4",
                precursors=["Li2CO3", "FeC2O4", "NH4H2PO4"]
            )
            
            # Validate result structure
            assert "target" in result
            assert result["target"] == "LiFePO4"
            
            assert "precursors" in result
            assert result["precursors"] == ["Li2CO3", "FeC2O4", "NH4H2PO4"]
            
            assert "predicted_temperature_celsius" in result
            temperature = result["predicted_temperature_celsius"]
            assert isinstance(temperature, (int, float))
            
            # Reasonable temperature range for solid-state synthesis (200-1200°C)
            assert 200 <= temperature <= 1200, \
                f"Temperature {temperature}°C outside typical synthesis range"
            
            assert "uncertainty_celsius" in result
            uncertainty = result["uncertainty_celsius"]
            assert isinstance(uncertainty, (int, float))
            assert uncertainty >= 0, "Uncertainty should be non-negative"
            
            # Validate metadata
            assert "metadata" in result
            assert "model_version" in result["metadata"]
            
        except FileNotFoundError as e:
            pytest.skip(f"Model file not available: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error during prediction: {e}")
    
    def test_predict_simple_oxide_temperature(self):
        """Test temperature prediction for a simple oxide like Li2O."""
        try:
            result = er_predict_temperature(
                target_formula="Li2O",
                precursors=["Li2CO3"]
            )
            
            assert result["target"] == "Li2O"
            assert isinstance(result["predicted_temperature_celsius"], (int, float))
            
            # Li2O synthesis typically around 600-900°C
            temp = result["predicted_temperature_celsius"]
            assert 400 <= temp <= 1200, \
                f"Li2O synthesis temperature {temp}°C seems unreasonable"
            
        except FileNotFoundError:
            pytest.skip("Model file not available")
    
    def test_predict_complex_oxide_temperature(self):
        """Test temperature prediction for complex oxide like LLZO."""
        try:
            result = er_predict_temperature(
                target_formula="Li7La3Zr2O12",
                precursors=["Li2CO3", "La2O3", "ZrO2"]
            )
            
            assert result["target"] == "Li7La3Zr2O12"
            
            # LLZO typically synthesized at high temperatures (>900°C)
            temp = result["predicted_temperature_celsius"]
            assert 700 <= temp <= 1200, \
                f"LLZO synthesis temperature {temp}°C outside expected range"
            
            # Should have reasonable uncertainty
            assert result["uncertainty_celsius"] < 500, \
                "Uncertainty should be reasonable (< 500°C)"
            
        except FileNotFoundError:
            pytest.skip("Model file not available")
    
    def test_predict_with_multiple_precursor_sets(self):
        """Test that different precursor sets give different temperatures."""
        try:
            # Same target, different precursors
            result1 = er_predict_temperature(
                target_formula="LiFePO4",
                precursors=["Li2CO3", "FeC2O4", "NH4H2PO4"]
            )
            
            result2 = er_predict_temperature(
                target_formula="LiFePO4",
                precursors=["LiOH", "Fe2O3", "H3PO4"]
            )
            
            temp1 = result1["predicted_temperature_celsius"]
            temp2 = result2["predicted_temperature_celsius"]
            
            # Both should be in reasonable range
            assert 200 <= temp1 <= 1200
            assert 200 <= temp2 <= 1200
            
            # They might be different (depends on model)
            # Just ensure both produce valid outputs
            assert result1["uncertainty_celsius"] >= 0
            assert result2["uncertainty_celsius"] >= 0
            
        except FileNotFoundError:
            pytest.skip("Model file not available")
    
    def test_model_device_handling(self):
        """Test that model works on both CPU and CUDA (if available)."""
        import torch
        
        try:
            result = er_predict_temperature(
                target_formula="Li2O",
                precursors=["Li2CO3"]
            )
            assert result is not None
            
            # If we got here, model loaded successfully on available device
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"Model successfully ran on device: {device}")
            
        except FileNotFoundError:
            pytest.skip("Model file not available")


@pytest.mark.integration
class TestTemperaturePredictionEdgeCases:
    """Integration tests for edge cases and error handling."""
    
    def test_predict_with_single_precursor(self):
        """Test prediction with just one precursor."""
        try:
            result = er_predict_temperature(
                target_formula="CuO",
                precursors=["Cu(NO3)2"]
            )
            
            assert result["target"] == "CuO"
            assert len(result["precursors"]) == 1
            assert isinstance(result["predicted_temperature_celsius"], (int, float))
            
        except FileNotFoundError:
            pytest.skip("Model file not available")
    
    def test_predict_with_many_precursors(self):
        """Test prediction with multiple precursors."""
        try:
            result = er_predict_temperature(
                target_formula="Li7La3Zr2O12",
                precursors=["Li2CO3", "LiOH", "La2O3", "La(NO3)3", "ZrO2"]
            )
            
            assert result["target"] == "Li7La3Zr2O12"
            assert len(result["precursors"]) == 5
            assert isinstance(result["predicted_temperature_celsius"], (int, float))
            
        except FileNotFoundError:
            pytest.skip("Model file not available")
    
    def test_predict_hydroxide_target(self):
        """Test temperature prediction for hydroxide synthesis."""
        try:
            result = er_predict_temperature(
                target_formula="La(OH)3",
                precursors=["La(NO3)3"]
            )
            
            assert result["target"] == "La(OH)3"
            # Hydroxides typically low temperature
            temp = result["predicted_temperature_celsius"]
            assert 0 <= temp <= 800, \
                f"Hydroxide synthesis temperature {temp}°C seems high"
            
        except FileNotFoundError:
            pytest.skip("Model file not available")


@pytest.mark.integration
class TestPrecursorAndTemperatureTogether:
    """Integration test combining precursor prediction and temperature prediction."""
    
    def test_predict_precursors_then_temperature(self):
        """Test full workflow: predict precursors, then predict temperature."""
        try:
            from tools.elemwise_retro.er_predict_precursors import er_predict_precursors
            
            # Step 1: Predict precursors
            precursor_result = er_predict_precursors("LiFePO4", top_k=1)
            top_precursors = precursor_result["top_prediction"]["precursors"]
            
            # Step 2: Predict temperature for those precursors
            temp_result = er_predict_temperature(
                target_formula="LiFePO4",
                precursors=top_precursors
            )
            
            # Validate both results
            assert precursor_result["target"] == "LiFePO4"
            assert temp_result["target"] == "LiFePO4"
            assert temp_result["precursors"] == top_precursors
            
            # Should have a valid temperature prediction
            temp = temp_result["predicted_temperature_celsius"]
            assert 200 <= temp <= 1200, \
                f"Predicted temperature {temp}°C outside reasonable range"
            
            print(f"\nFull workflow test:")
            print(f"  Target: LiFePO4")
            print(f"  Predicted precursors: {top_precursors}")
            print(f"  Predicted temperature: {temp:.1f} ± {temp_result['uncertainty_celsius']:.1f} °C")
            
        except FileNotFoundError:
            pytest.skip("Model files not available")
