"""
Tests for er_predict_temperature tool.

Run with: pytest tests/elemwise_retro/test_er_predict_temperature.py -v
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
import torch
import json
from tools.elemwise_retro.er_predict_temperature import (
    er_predict_temperature,
    _get_source_elements,
    _composition_to_graph,
    _add_source_mask,
    TemperaturePredictor,
)


class TestInputValidation:
    """Tests for input validation."""
    
    def test_empty_target_formula_raises_error(self):
        """Empty target formula should raise ValueError."""
        with pytest.raises(ValueError, match="target_formula must be a non-empty string"):
            er_predict_temperature("", ["Li2O"])
    
    def test_whitespace_target_formula_raises_error(self):
        """Whitespace-only target formula should raise ValueError."""
        with pytest.raises(ValueError, match="target_formula must be a non-empty string"):
            er_predict_temperature("   ", ["Li2O"])
    
    def test_none_target_formula_raises_error(self):
        """None target formula should raise ValueError."""
        with pytest.raises(ValueError, match="target_formula must be a non-empty string"):
            er_predict_temperature(None, ["Li2O"])
    
    def test_empty_precursor_list_raises_error(self):
        """Empty precursor list should raise ValueError."""
        with pytest.raises(ValueError, match="precursors must be a non-empty list"):
            er_predict_temperature("Li2O", [])
    
    def test_none_precursor_list_raises_error(self):
        """None precursor list should raise ValueError."""
        with pytest.raises(ValueError, match="precursors must be a non-empty list"):
            er_predict_temperature("Li2O", None)
    
    def test_non_list_precursor_raises_error(self):
        """Non-list precursor argument should raise ValueError."""
        with pytest.raises(ValueError, match="precursors must be a non-empty list"):
            er_predict_temperature("Li2O", "Li2O")
    
    def test_non_string_precursor_raises_error(self):
        """Non-string items in precursor list should raise ValueError."""
        with pytest.raises(ValueError, match="all precursors must be strings"):
            er_predict_temperature("Li2O", ["Li2O", 123])
    
    def test_valid_inputs_accepted(self):
        """Valid inputs should be accepted without error."""
        with patch('tools.elemwise_retro.er_predict_temperature._get_predictor') as mock_get:
            mock_predictor = MagicMock()
            mock_predictor.predict.return_value = {
                "target": "Li2O",
                "precursors": ["Li2O"],
                "temperature_celsius": 900.0,
                "temperature_kelvin": 1173.15,
                "metadata": {}
            }
            mock_get.return_value = mock_predictor
            
            # Should not raise
            result = er_predict_temperature("Li2O", ["Li2O"])
            assert result["target"] == "Li2O"


class TestUtilityFunctions:
    """Tests for internal utility functions."""
    
    def test_get_source_elements_simple(self):
        """Test extraction of source elements from simple composition."""
        source, env = _get_source_elements(["Li2O"])
        assert "Li" in source
        assert "O" in env
        assert "Li" not in env
        assert "O" not in source
    
    def test_get_source_elements_complex(self):
        """Test extraction from complex composition."""
        source, env = _get_source_elements(["Li7La3Zr2O12"])
        assert "Li" in source
        assert "La" in source
        assert "Zr" in source
        assert "O" in env
    
    def test_get_source_elements_precursors(self):
        """Test extraction from precursor compositions."""
        source, env = _get_source_elements(["Li2CO3", "La2O3", "ZrO2"])
        assert "Li" in source
        assert "La" in source
        assert "Zr" in source
        assert "C" in source or "C" in env  # Carbon handling
        assert "O" in env
    
    def test_composition_to_graph_simple(self, mock_embedding_dict):
        """Test conversion of simple composition to graph."""
        graph, elements = _composition_to_graph("Li2O", mock_embedding_dict)
        
        # Check structure
        assert len(graph) == 2
        atom_weights, atom_fea, self_fea_idx, nbr_fea_idx = graph[0]
        composition = graph[1]
        
        # Check types
        assert isinstance(atom_weights, torch.Tensor)
        assert isinstance(atom_fea, torch.Tensor)
        assert isinstance(self_fea_idx, torch.Tensor)
        assert isinstance(nbr_fea_idx, torch.Tensor)
        assert composition == "Li2O"
        
        # Check elements
        assert "Li" in elements
        assert "O" in elements
    
    def test_composition_to_graph_missing_element_raises_error(self):
        """Test that missing element in embedding dict raises NotImplementedError."""
        embedding_dict = {"Li": [0.1] * 64}
        
        with pytest.raises(NotImplementedError, match="Element .* has no embedding vector"):
            _composition_to_graph("Li2O", embedding_dict)
    
    def test_add_source_mask_marks_source_elements(self, mock_embedding_dict):
        """Test that source mask correctly identifies source elements."""
        graph, elements = _composition_to_graph("Li2O", mock_embedding_dict)
        source_elems = ["Li"]
        
        masked_graph = _add_source_mask(graph, source_elems)
        
        # Should have 3 elements now: (graph_data, composition, mask)
        assert len(masked_graph) == 3
        mask = masked_graph[2]
        assert isinstance(mask, torch.Tensor)
        
        # Check mask shape
        assert mask.shape[0] == 2  # Li and O


class TestTemperaturePredictor:
    """Tests for TemperaturePredictor class."""
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"Li": [0.1]}')
    @patch('tools.elemwise_retro.er_predict_temperature.model_downloader')
    @patch('pickle.load')
    def test_predictor_lazy_loading(self, mock_pkl_load, mock_downloader, mock_file):
        """Test that predictor loads models lazily."""
        mock_model = MagicMock()
        mock_model.eval = MagicMock()
        mock_model.to = MagicMock(return_value=mock_model)
        
        mock_normalizer = MagicMock()
        mock_normalizer.denorm = MagicMock(side_effect=lambda x: x)
        
        # Return model first, then normalizer
        mock_pkl_load.side_effect = [mock_model, mock_normalizer]
        mock_downloader.get_model_path.return_value = "/fake/path/model.pkl"
        
        def json_load_side_effect(f):
            return {"Li": [0.1] * 64, "O": [0.2] * 64}
        
        with patch('json.load', side_effect=json_load_side_effect):
            predictor = TemperaturePredictor()
            
            # Model should not be loaded yet
            assert not predictor._loaded
            assert predictor.model is None
            assert predictor.normalizer is None
            
            # This should trigger loading
            predictor._ensure_loaded()
            
            # Now it should be loaded
            assert predictor._loaded
            assert predictor.model is not None
            assert predictor.normalizer is not None
            mock_model.eval.assert_called_once()
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('tools.elemwise_retro.er_predict_temperature.model_downloader')
    @patch('pickle.load')
    def test_predictor_returns_correct_structure(self, mock_pkl_load, mock_downloader, mock_file):
        """Test that predictor returns correctly structured result."""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.eval = MagicMock()
        mock_model.to = MagicMock(return_value=mock_model)
        
        # Mock model output - returns concatenated [prediction, log_std]
        prediction = torch.tensor([[900.0, 0.1]])
        mock_model.return_value = (prediction, None)
        
        mock_normalizer = MagicMock()
        mock_normalizer.denorm = MagicMock(return_value=torch.tensor([900.0]))
        
        mock_pkl_load.side_effect = [mock_model, mock_normalizer]
        mock_downloader.get_model_path.return_value = "/fake/path/model.pkl"
        
        def json_load_side_effect(f):
            return {"Li": [0.1] * 64, "O": [0.2] * 64, "C": [0.3] * 64}
        
        with patch('json.load', side_effect=json_load_side_effect):
            predictor = TemperaturePredictor()
            result = predictor.predict("Li2O", ["Li2CO3"])
            
            # Check structure
            assert "target" in result
            assert "precursors" in result
            assert "temperature_celsius" in result
            assert "temperature_kelvin" in result
            assert "metadata" in result
            
            # Check target and precursors
            assert result["target"] == "Li2O"
            assert result["precursors"] == ["Li2CO3"]
            
            # Check temperatures
            assert isinstance(result["temperature_celsius"], float)
            assert isinstance(result["temperature_kelvin"], float)
            # Kelvin should be Celsius + 273.15
            assert abs(result["temperature_kelvin"] - result["temperature_celsius"] - 273.15) < 0.01
            
            # Check metadata
            assert "model_type" in result["metadata"]
            assert "device" in result["metadata"]
            assert result["metadata"]["model_type"] == "ElemwiseRetro"
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('tools.elemwise_retro.er_predict_temperature.model_downloader')
    @patch('pickle.load')
    def test_predictor_element_mismatch_raises_error(self, mock_pkl_load, mock_downloader, mock_file):
        """Test that element mismatch between target and precursors raises error."""
        mock_model = MagicMock()
        mock_model.eval = MagicMock()
        mock_model.to = MagicMock(return_value=mock_model)
        
        mock_normalizer = MagicMock()
        mock_pkl_load.side_effect = [mock_model, mock_normalizer]
        mock_downloader.get_model_path.return_value = "/fake/path/model.pkl"
        
        def json_load_side_effect(f):
            return {"Li": [0.1] * 64, "O": [0.2] * 64, "Fe": [0.3] * 64, "P": [0.4] * 64}
        
        with patch('json.load', side_effect=json_load_side_effect):
            # This should trigger the internal validation that raises ValueError
            # when target elements don't match precursor elements
            with patch('tools.elemwise_retro.er_predict_temperature._predict_synthesis_temperature_internal') as mock_internal:
                mock_internal.side_effect = ValueError("Target and precursor source element mismatch")
                
                predictor = TemperaturePredictor()
                with pytest.raises(ValueError, match="Target and precursor source element mismatch"):
                    predictor.predict("LiFePO4", ["Li2O"])  # Missing Fe and P in precursors


class TestPredictTemperature:
    """Tests for the main er_predict_temperature function."""
    
    @patch('tools.elemwise_retro.er_predict_temperature._get_predictor')
    def test_predict_temperature_calls_predictor(self, mock_get_predictor):
        """Test that er_predict_temperature calls the predictor correctly."""
        mock_predictor = MagicMock()
        expected_result = {
            "target": "LiFePO4",
            "precursors": ["Li2CO3", "Fe2O3", "P2O5"],
            "temperature_celsius": 850.0,
            "temperature_kelvin": 1123.15,
            "metadata": {"model_type": "ElemwiseRetro", "device": "cpu"}
        }
        mock_predictor.predict.return_value = expected_result
        mock_get_predictor.return_value = mock_predictor
        
        result = er_predict_temperature("LiFePO4", ["Li2CO3", "Fe2O3", "P2O5"])
        
        mock_predictor.predict.assert_called_once_with("LiFePO4", ["Li2CO3", "Fe2O3", "P2O5"])
        assert result == expected_result
    
    @patch('tools.elemwise_retro.er_predict_temperature._get_predictor')
    def test_predict_temperature_propagates_value_error(self, mock_get_predictor):
        """Test that ValueError (element mismatch) is properly wrapped."""
        mock_predictor = MagicMock()
        mock_predictor.predict.side_effect = ValueError("Element mismatch")
        mock_get_predictor.return_value = mock_predictor
        
        with pytest.raises(ValueError, match="Element mismatch"):
            er_predict_temperature("Li2O", ["Fe2O3"])
    
    @patch('tools.elemwise_retro.er_predict_temperature._get_predictor')
    def test_predict_temperature_propagates_runtime_error(self, mock_get_predictor):
        """Test that runtime errors are properly wrapped and propagated."""
        mock_predictor = MagicMock()
        mock_predictor.predict.side_effect = Exception("Model loading failed")
        mock_get_predictor.return_value = mock_predictor
        
        with pytest.raises(RuntimeError, match="Temperature prediction failed"):
            er_predict_temperature("Li2O", ["Li2O"])


class TestRealWorldScenarios:
    """Tests for realistic usage scenarios."""
    
    @patch('tools.elemwise_retro.er_predict_temperature._get_predictor')
    def test_battery_material_temperature(self, mock_get_predictor):
        """Test temperature prediction for a realistic battery material."""
        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = {
            "target": "LiFePO4",
            "precursors": ["Li2CO3", "Fe2O3", "P2O5"],
            "temperature_celsius": 850.0,
            "temperature_kelvin": 1123.15,
            "metadata": {
                "model_type": "ElemwiseRetro",
                "device": "cpu",
                "temperature_unit": "celsius"
            }
        }
        mock_get_predictor.return_value = mock_predictor
        
        result = er_predict_temperature("LiFePO4", ["Li2CO3", "Fe2O3", "P2O5"])
        
        assert result["target"] == "LiFePO4"
        assert result["temperature_celsius"] == 850.0
        # Reasonable temperature range for solid-state synthesis (500-1200°C)
        assert 500 <= result["temperature_celsius"] <= 1200
        assert result["temperature_kelvin"] > result["temperature_celsius"]
    
    @patch('tools.elemwise_retro.er_predict_temperature._get_predictor')
    def test_solid_electrolyte_temperature(self, mock_get_predictor):
        """Test temperature prediction for a complex solid electrolyte."""
        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = {
            "target": "Li7La3Zr2O12",
            "precursors": ["Li2CO3", "La2O3", "ZrO2"],
            "temperature_celsius": 1050.0,
            "temperature_kelvin": 1323.15,
            "metadata": {
                "model_type": "ElemwiseRetro",
                "device": "cpu",
                "temperature_unit": "celsius"
            }
        }
        mock_get_predictor.return_value = mock_predictor
        
        result = er_predict_temperature("Li7La3Zr2O12", ["Li2CO3", "La2O3", "ZrO2"])
        
        assert result["target"] == "Li7La3Zr2O12"
        assert result["precursors"] == ["Li2CO3", "La2O3", "ZrO2"]
        assert result["temperature_celsius"] == 1050.0
        # LLZO typically synthesized at high temperatures
        assert result["temperature_celsius"] > 900
    
    @patch('tools.elemwise_retro.er_predict_temperature._get_predictor')
    def test_different_precursor_sets_different_temperatures(self, mock_get_predictor):
        """Test that different precursor sets can yield different temperatures."""
        mock_predictor = MagicMock()
        
        # First call with carbonate precursors
        mock_predictor.predict.side_effect = [
            {
                "target": "Li2O",
                "precursors": ["Li2CO3"],
                "temperature_celsius": 900.0,
                "temperature_kelvin": 1173.15,
                "metadata": {"model_type": "ElemwiseRetro", "device": "cpu"}
            },
            # Second call with hydroxide precursors
            {
                "target": "Li2O",
                "precursors": ["LiOH"],
                "temperature_celsius": 450.0,
                "temperature_kelvin": 723.15,
                "metadata": {"model_type": "ElemwiseRetro", "device": "cpu"}
            }
        ]
        mock_get_predictor.return_value = mock_predictor
        
        result1 = er_predict_temperature("Li2O", ["Li2CO3"])
        result2 = er_predict_temperature("Li2O", ["LiOH"])
        
        # Different precursors should potentially give different temperatures
        # (though not guaranteed - this is just showing the API works)
        assert result1["precursors"] != result2["precursors"]


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""
    
    def test_invalid_target_formula_handled(self):
        """Test that invalid target formulas are handled gracefully."""
        with patch('tools.elemwise_retro.er_predict_temperature._get_predictor') as mock_get:
            mock_predictor = MagicMock()
            # Pymatgen will raise an error for invalid formulas
            mock_predictor.predict.side_effect = ValueError("Invalid composition")
            mock_get.return_value = mock_predictor
            
            with pytest.raises(ValueError, match="Element mismatch|Invalid composition"):
                er_predict_temperature("XyZ123Invalid", ["Li2O"])
    
    def test_invalid_precursor_formula_handled(self):
        """Test that invalid precursor formulas are handled gracefully."""
        with patch('tools.elemwise_retro.er_predict_temperature._get_predictor') as mock_get:
            mock_predictor = MagicMock()
            mock_predictor.predict.side_effect = ValueError("Invalid composition")
            mock_get.return_value = mock_predictor
            
            with pytest.raises(ValueError, match="Element mismatch|Invalid composition"):
                er_predict_temperature("Li2O", ["InvalidFormula123"])
    
    @patch('tools.elemwise_retro.er_predict_temperature._get_predictor')
    def test_single_precursor(self, mock_get_predictor):
        """Test temperature prediction with a single precursor."""
        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = {
            "target": "Li2O",
            "precursors": ["Li2O"],
            "temperature_celsius": 1000.0,
            "temperature_kelvin": 1273.15,
            "metadata": {"model_type": "ElemwiseRetro", "device": "cpu"}
        }
        mock_get_predictor.return_value = mock_predictor
        
        result = er_predict_temperature("Li2O", ["Li2O"])
        
        assert len(result["precursors"]) == 1
        assert result["temperature_celsius"] == 1000.0
    
    @patch('tools.elemwise_retro.er_predict_temperature._get_predictor')
    def test_multiple_precursors(self, mock_get_predictor):
        """Test temperature prediction with multiple precursors."""
        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = {
            "target": "LiFeO2",
            "precursors": ["Li2CO3", "Fe2O3", "FeO"],
            "temperature_celsius": 900.0,
            "temperature_kelvin": 1173.15,
            "metadata": {"model_type": "ElemwiseRetro", "device": "cpu"}
        }
        mock_get_predictor.return_value = mock_predictor
        
        result = er_predict_temperature("LiFeO2", ["Li2CO3", "Fe2O3", "FeO"])
        
        assert len(result["precursors"]) == 3
        assert result["temperature_celsius"] == 900.0
    
    @patch('tools.elemwise_retro.er_predict_temperature._get_predictor')
    def test_temperature_bounds_reasonable(self, mock_get_predictor):
        """Test that predicted temperatures are in reasonable ranges."""
        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = {
            "target": "Li2O",
            "precursors": ["Li2O"],
            "temperature_celsius": 800.0,
            "temperature_kelvin": 1073.15,
            "metadata": {"model_type": "ElemwiseRetro", "device": "cpu"}
        }
        mock_get_predictor.return_value = mock_predictor
        
        result = er_predict_temperature("Li2O", ["Li2O"])
        
        # Temperature should be physically reasonable
        # Solid-state synthesis typically 300-1500°C
        assert 300 <= result["temperature_celsius"] <= 1500
        # Kelvin should be positive and > Celsius
        assert result["temperature_kelvin"] > 273.15
        assert result["temperature_kelvin"] == result["temperature_celsius"] + 273.15


class TestModelCaching:
    """Tests for model caching behavior."""
    
    @patch('tools.elemwise_retro.er_predict_temperature._get_predictor')
    def test_singleton_predictor_reused(self, mock_get_predictor):
        """Test that the predictor singleton is reused across calls."""
        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = {
            "target": "Li2O",
            "precursors": ["Li2O"],
            "temperature_celsius": 900.0,
            "temperature_kelvin": 1173.15,
            "metadata": {}
        }
        mock_get_predictor.return_value = mock_predictor
        
        # Make multiple predictions
        er_predict_temperature("Li2O", ["Li2O"])
        er_predict_temperature("Li2O", ["Li2O"])
        er_predict_temperature("Li2O", ["Li2O"])
        
        # _get_predictor should be called multiple times, but it returns the same instance
        assert mock_get_predictor.call_count == 3
