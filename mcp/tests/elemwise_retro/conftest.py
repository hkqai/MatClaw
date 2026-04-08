"""
Pytest fixtures shared across elemwise_retro tool tests.
"""

import pytest
import torch
import numpy as np
from unittest.mock import MagicMock


@pytest.fixture
def mock_embedding_dict():
    """Fixture providing mock element embeddings."""
    # Create a simple embedding dictionary with common elements
    elements = ['Li', 'La', 'Zr', 'O', 'C', 'Na', 'Fe', 'P', 'Co']
    embedding_dim = 64
    
    return {
        elem: [np.random.random() for _ in range(embedding_dim)]
        for elem in elements
    }


@pytest.fixture
def mock_anion_parts():
    """Fixture providing mock anion parts dictionary."""
    return {
        "O": ["O"],
        "CO3": ["C", "O"],
        "NO3": ["N", "O"],
        "SO4": ["S", "O"],
        "PO4": ["P", "O"],
    }


@pytest.fixture
def mock_stoichiometry_dict():
    """Fixture providing mock stoichiometry dictionary."""
    return {
        "LiO": ["Li2O"],
        "LiCO3": ["Li2CO3"],
        "LaO": ["La2O3"],
        "ZrO": ["ZrO2"],
        "NaO": ["Na2O"],
        "FeO": ["Fe2O3", "FeO"],
        "PO": ["P2O5"],
        "CoO": ["Co3O4", "CoO"],
    }


@pytest.fixture
def mock_precursor_model():
    """Fixture providing a mock precursor prediction model."""
    model = MagicMock()
    model.eval = MagicMock()
    model.to = MagicMock(return_value=model)
    
    # Mock model output - returns (template_output, _)
    # template_output shape: [num_source_elements, num_anion_classes]
    mock_output = torch.randn(2, 5)  # 2 source elements, 5 anion classes
    model.return_value = (mock_output, None)
    
    return model


@pytest.fixture
def mock_temperature_model():
    """Fixture providing a mock temperature prediction model."""
    model = MagicMock()
    model.eval = MagicMock()
    model.to = MagicMock(return_value=model)
    
    # Mock model output - returns concatenated [prediction, log_std]
    prediction = torch.tensor([[900.0, 0.1]])  # Temperature and log_std
    model.return_value = (prediction, None)
    
    return model


@pytest.fixture
def mock_normalizer():
    """Fixture providing a mock temperature normalizer."""
    normalizer = MagicMock()
    # Mock denorm to return the input value (or apply simple transformation)
    normalizer.denorm = MagicMock(side_effect=lambda x: x)
    return normalizer


@pytest.fixture
def simple_target_formulas():
    """Fixture providing simple target formulas for testing."""
    return [
        "Li7La3Zr2O12",  # Complex oxide
        "LiFePO4",        # Battery material
        "NaCoO2",         # Simple ternary
    ]


@pytest.fixture
def simple_precursor_sets():
    """Fixture providing simple precursor sets for testing."""
    return {
        "Li7La3Zr2O12": ["Li2CO3", "La2O3", "ZrO2"],
        "LiFePO4": ["Li2CO3", "Fe2O3", "P2O5"],
        "NaCoO2": ["Na2O", "Co3O4"],
    }
