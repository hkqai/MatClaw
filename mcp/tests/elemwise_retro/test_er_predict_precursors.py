"""
Tests for er_predict_precursors tool.

Run with: pytest tests/elemwise_retro/test_er_predict_precursors.py -v
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
import torch
import json
from tools.elemwise_retro.er_predict_precursors import (
    er_predict_precursors,
    _get_source_elements,
    _composition_to_graph,
    _add_source_mask,
    PrecursorPredictor,
)


class TestInputValidation:
    """Tests for input validation."""
    
    def test_empty_target_formula_raises_error(self):
        """Empty target formula should raise ValueError."""
        with pytest.raises(ValueError, match="target_formula must be a non-empty string"):
            er_predict_precursors("", top_k=5)
    
    def test_whitespace_target_formula_raises_error(self):
        """Whitespace-only target formula should raise ValueError."""
        with pytest.raises(ValueError, match="target_formula must be a non-empty string"):
            er_predict_precursors("   ", top_k=5)
    
    def test_none_target_formula_raises_error(self):
        """None target formula should raise ValueError."""
        with pytest.raises(ValueError, match="target_formula must be a non-empty string"):
            er_predict_precursors(None, top_k=5)
    
    def test_invalid_top_k_type_raises_error(self):
        """Non-integer top_k should raise ValueError."""
        with pytest.raises(ValueError, match="top_k must be an integer"):
            er_predict_precursors("Li2O", top_k="5")
    
    def test_top_k_too_small_raises_error(self):
        """top_k < 1 should raise ValueError."""
        with pytest.raises(ValueError, match="top_k must be an integer between 1 and 20"):
            er_predict_precursors("Li2O", top_k=0)
    
    def test_top_k_too_large_raises_error(self):
        """top_k > 20 should raise ValueError."""
        with pytest.raises(ValueError, match="top_k must be an integer between 1 and 20"):
            er_predict_precursors("Li2O", top_k=21)
    
    def test_valid_top_k_boundary_values(self):
        """top_k = 1 and top_k = 20 should be accepted."""
        with patch('tools.elemwise_retro.er_predict_precursors._get_predictor') as mock_get:
            mock_predictor = MagicMock()
            mock_predictor.predict.return_value = {
                "target": "Li2O",
                "precursor_sets": [{"precursors": ["Li2O"], "confidence": 0.9}],
                "top_prediction": {"precursors": ["Li2O"], "confidence": 0.9},
                "metadata": {}
            }
            mock_get.return_value = mock_predictor
            
            # Should not raise
            result1 = er_predict_precursors("Li2O", top_k=1)
            assert result1["target"] == "Li2O"
            
            result20 = er_predict_precursors("Li2O", top_k=20)
            assert result20["target"] == "Li2O"


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
    
    def test_get_source_elements_multiple_compositions(self):
        """Test extraction from multiple compositions."""
        source, env = _get_source_elements(["Li2O", "La2O3", "ZrO2"])
        assert "Li" in source
        assert "La" in source
        assert "Zr" in source
        assert "O" in env
        # Should not have duplicates
        assert source.count("Li") == 1
        assert env.count("O") == 1
    
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


class TestPrecursorPredictor:
    """Tests for PrecursorPredictor class."""
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"Li": [0.1]}')
    @patch('tools.elemwise_retro.er_predict_precursors.model_downloader')
    @patch('tools.elemwise_retro.er_predict_precursors.load_model_with_hyperparameters')
    def test_predictor_lazy_loading(self, mock_load_model, mock_downloader, mock_file):
        """Test that predictor loads models lazily."""
        # Mock the model loader to return a mock model
        mock_model = MagicMock()
        mock_model.eval = MagicMock(return_value=None)
        mock_model.to = MagicMock(return_value=mock_model)
        mock_load_model.return_value = mock_model
        
        mock_downloader.get_model_path.return_value = "/fake/path/model.pt"
        
        # Mock json.load for the various JSON files
        def json_load_side_effect(f):
            filename = getattr(f, 'name', '')
            if 'embedding' in filename:
                return {"Li": [0.1] * 64, "O": [0.2] * 64}
            elif 'anion' in filename:
                return {"O": ["O"]}
            elif 'formulas' in filename:
                return {"LiO": ["Li2O"]}
            return {}
        
        with patch('json.load', side_effect=json_load_side_effect):
            predictor = PrecursorPredictor()
            
            # Model should not be loaded yet
            assert not predictor._loaded
            assert predictor.model is None
            
            # This should trigger loading
            predictor._ensure_loaded()
            
            # Now it should be loaded
            assert predictor._loaded
            assert predictor.model is not None
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('tools.elemwise_retro.er_predict_precursors.model_downloader')
    @patch('tools.elemwise_retro.er_predict_precursors._predict_precursor_sets_internal')
    @patch('tools.elemwise_retro.er_predict_precursors.load_model_with_hyperparameters')
    @patch('tools.elemwise_retro.er_predict_precursors.json.load')
    def test_predictor_returns_correct_structure(self, mock_json_load, mock_load_model, mock_internal_predict, mock_downloader, mock_file):
        """Test that predictor returns correctly structured result."""
        # Mock the model loader to return a mock model
        mock_model = MagicMock()
        mock_model.to = MagicMock(return_value=mock_model)
        mock_load_model.return_value = mock_model
        
        # Mock internal prediction to return precursor sets
        mock_internal_predict.return_value = [(['Li2CO3', 'La2O3'], 0.85), (['LiNO3', 'La(OH)3'], 0.60)]
        
        mock_downloader.get_model_path.return_value = "/fake/path/model.pt"
        
        # Mock json.load to return appropriate data based on call order
        mock_json_load.side_effect = [
            {elem: [0.1] * 64 for elem in ['Li', 'O', 'La', 'Zr', 'C']},  # embedding_dict
            {"O": ["O"], "CO3": ["C", "O"]},  # anion_parts
            {"LiO": ["Li2O"], "LaO": ["La2O3"], "ZrO": ["ZrO2"]}  # stoichiometry_dict
        ]
        
        predictor = PrecursorPredictor()
        result = predictor.predict("Li2O", top_k=3)
        
        # Check structure
        assert "target" in result
        assert "precursor_sets" in result
        assert "top_prediction" in result
        assert "metadata" in result
        
        # Check target
        assert result["target"] == "Li2O"
        
        # Check precursor_sets structure
        assert isinstance(result["precursor_sets"], list)
        if len(result["precursor_sets"]) > 0:
            pred_set = result["precursor_sets"][0]
            assert "precursors" in pred_set
            assert "confidence" in pred_set
            assert isinstance(pred_set["precursors"], list)
            assert isinstance(pred_set["confidence"], float)
        
        # Check metadata
        assert "model_type" in result["metadata"]
        assert "device" in result["metadata"]
        assert result["metadata"]["model_type"] == "ElemwiseRetro"


class TestPredictPrecursors:
    """Tests for the main er_predict_precursors function."""
    
    @patch('tools.elemwise_retro.er_predict_precursors._get_predictor')
    def test_predict_precursors_calls_predictor(self, mock_get_predictor):
        """Test that er_predict_precursors calls the predictor correctly."""
        mock_predictor = MagicMock()
        expected_result = {
            "target": "LiFePO4",
            "precursor_sets": [
                {"precursors": ["Li2CO3", "Fe2O3", "P2O5"], "confidence": 0.85}
            ],
            "top_prediction": {"precursors": ["Li2CO3", "Fe2O3", "P2O5"], "confidence": 0.85},
            "metadata": {"model_type": "ElemwiseRetro", "device": "cpu"}
        }
        mock_predictor.predict.return_value = expected_result
        mock_get_predictor.return_value = mock_predictor
        
        result = er_predict_precursors("LiFePO4", top_k=5)
        
        mock_predictor.predict.assert_called_once_with("LiFePO4", 5)
        assert result == expected_result
    
    @patch('tools.elemwise_retro.er_predict_precursors._get_predictor')
    def test_predict_precursors_propagates_runtime_error(self, mock_get_predictor):
        """Test that runtime errors are properly wrapped and propagated."""
        mock_predictor = MagicMock()
        mock_predictor.predict.side_effect = Exception("Model loading failed")
        mock_get_predictor.return_value = mock_predictor
        
        with pytest.raises(RuntimeError, match="Precursor prediction failed"):
            er_predict_precursors("Li2O", top_k=5)
    
    @patch('tools.elemwise_retro.er_predict_precursors._get_predictor')
    def test_predict_precursors_default_top_k(self, mock_get_predictor):
        """Test that default top_k value is used when not specified."""
        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = {
            "target": "Li2O",
            "precursor_sets": [],
            "top_prediction": None,
            "metadata": {}
        }
        mock_get_predictor.return_value = mock_predictor
        
        er_predict_precursors("Li2O")
        
        # Should be called with default top_k=5
        mock_predictor.predict.assert_called_once_with("Li2O", 5)


class TestRealWorldScenarios:
    """Tests for realistic usage scenarios."""
    
    @patch('tools.elemwise_retro.er_predict_precursors._get_predictor')
    def test_battery_material_prediction(self, mock_get_predictor):
        """Test prediction for a realistic battery material."""
        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = {
            "target": "LiFePO4",
            "precursor_sets": [
                {"precursors": ["Li2CO3", "Fe2O3", "P2O5"], "confidence": 0.85},
                {"precursors": ["LiOH", "Fe2O3", "H3PO4"], "confidence": 0.72},
                {"precursors": ["Li2CO3", "FePO4"], "confidence": 0.65},
            ],
            "top_prediction": {"precursors": ["Li2CO3", "Fe2O3", "P2O5"], "confidence": 0.85},
            "metadata": {"model_type": "ElemwiseRetro", "device": "cpu", "num_predictions": 3}
        }
        mock_get_predictor.return_value = mock_predictor
        
        result = er_predict_precursors("LiFePO4", top_k=3)
        
        assert result["target"] == "LiFePO4"
        assert len(result["precursor_sets"]) == 3
        assert result["top_prediction"]["confidence"] == 0.85
        # Confidence should decrease with rank
        assert result["precursor_sets"][0]["confidence"] >= result["precursor_sets"][1]["confidence"]
        assert result["precursor_sets"][1]["confidence"] >= result["precursor_sets"][2]["confidence"]
    
    @patch('tools.elemwise_retro.er_predict_precursors._get_predictor')
    def test_solid_electrolyte_prediction(self, mock_get_predictor):
        """Test prediction for a complex solid electrolyte."""
        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = {
            "target": "Li7La3Zr2O12",
            "precursor_sets": [
                {"precursors": ["Li2CO3", "La2O3", "ZrO2"], "confidence": 0.78},
                {"precursors": ["LiOH", "La2O3", "ZrO2"], "confidence": 0.65},
            ],
            "top_prediction": {"precursors": ["Li2CO3", "La2O3", "ZrO2"], "confidence": 0.78},
            "metadata": {"model_type": "ElemwiseRetro", "device": "cpu", "num_predictions": 2}
        }
        mock_get_predictor.return_value = mock_predictor
        
        result = er_predict_precursors("Li7La3Zr2O12", top_k=2)
        
        assert result["target"] == "Li7La3Zr2O12"
        assert len(result["precursor_sets"]) == 2
        # Should have precursors for all elements (Li, La, Zr)
        top_precursors = result["top_prediction"]["precursors"]
        assert any("Li" in p for p in top_precursors)
        assert any("La" in p for p in top_precursors)
        assert any("Zr" in p for p in top_precursors)


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""
    
    def test_invalid_chemical_formula_handled(self):
        """Test that invalid chemical formulas are handled gracefully."""
        with patch('tools.elemwise_retro.er_predict_precursors._get_predictor') as mock_get:
            mock_predictor = MagicMock()
            # Pymatgen will raise an error for invalid formulas
            mock_predictor.predict.side_effect = ValueError("Invalid composition")
            mock_get.return_value = mock_predictor
            
            with pytest.raises(RuntimeError, match="Precursor prediction failed"):
                er_predict_precursors("XyZ123Invalid", top_k=5)
    
    @patch('tools.elemwise_retro.er_predict_precursors._get_predictor')
    def test_single_precursor_prediction(self, mock_get_predictor):
        """Test prediction with top_k=1 returns single result."""
        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = {
            "target": "Li2O",
            "precursor_sets": [
                {"precursors": ["Li2O"], "confidence": 0.95}
            ],
            "top_prediction": {"precursors": ["Li2O"], "confidence": 0.95},
            "metadata": {"model_type": "ElemwiseRetro", "device": "cpu", "num_predictions": 1}
        }
        mock_get_predictor.return_value = mock_predictor
        
        result = er_predict_precursors("Li2O", top_k=1)
        
        assert len(result["precursor_sets"]) == 1
        assert result["top_prediction"] == result["precursor_sets"][0]
