"""
Temperature Prediction Tool for MCP

This module provides a standalone tool for predicting synthesis temperatures for inorganic materials
given a target composition and precursor set.
Designed to be exposed as an MCP (Model Context Protocol) tool.

This is a self-contained module with no dependencies on other project files.
"""

import json
import os
from typing import List, Dict, Any, Tuple

import numpy as np
import torch
import pickle as pk
from pymatgen.core import Composition

# torch_scatter is an optional dependency - check if available
try:
    from torch_scatter import scatter_mean
except ImportError:
    raise ImportError(
        "torch_scatter is required for elemwise_retro tools but not installed.\n"
        "Install it with one of these commands:\n"
        "  For GLIBC >= 2.32: pip install torch-scatter -f https://data.pyg.org/whl/torch-2.10.0+cpu.html\n"
        "  For GLIBC <  2.32: conda install pytorch-scatter -c pyg\n"
        "See requirements.txt for more details."
    )

# Import model module for pickle unpickling
from . import model

# Import model downloader for automatic model downloads
from utils import model_downloader

# ================================================================================================
# CONSTANTS - Element Classifications
# ================================================================================================

ALKALI_METAL = ['Li', 'Na', 'K', 'Rb', 'Cs']
ALKALINE_EARTH_METAL = ['Be', 'Mg', 'Ca', 'Sr', 'Ba']
TRANSITION_METAL = ['Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',
                    'Y', 'Zr', 'Nb', 'Mo', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'Hf',
                    'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg']
LANTHANIDE_ELEM = ['La', 'Ce', 'Pr', 'Nd', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb', 'Lu']
ACTINIDE_ELEM = ['Ac', 'Th', 'Pa', 'U', 'Np', 'Pu', 'Am', 'Cm', 'Bk', 'Cf', 'Es', 'Fm', 'Md', 'No', 'Lr']
POST_TRANSITION_METAL = ['Al', 'Ga', 'In', 'Sn', 'Tl', 'Pb', 'Bi']
METALLOID = ['B', 'Si', 'Ge', 'As', 'Sb', 'Te']

# Essential elements for solid-state synthesis (source elements)
ESSENTIAL_ELEM = (ALKALI_METAL + ALKALINE_EARTH_METAL + TRANSITION_METAL +
                  LANTHANIDE_ELEM + ACTINIDE_ELEM + POST_TRANSITION_METAL + 
                  METALLOID + ['P', 'Se', 'S'])


# ================================================================================================
# CORE UTILITY FUNCTIONS
# ================================================================================================

def _get_source_elements(compositions: List[str]) -> Tuple[List[str], List[str]]:
    """Extract source elements (cations) and environment elements (anions) from compositions."""
    source_elem = []
    env_elem = []
    
    for comp in compositions:
        comp_dict = Composition(comp).get_el_amt_dict()
        elements_seq = list(comp_dict.keys())
        
        for elem in elements_seq:
            if elem in ESSENTIAL_ELEM:
                if elem not in source_elem:
                    source_elem.append(elem)
            else:
                if elem not in env_elem:
                    env_elem.append(elem)
    
    return source_elem, env_elem


def _composition_to_graph(composition: str, embedding_dict: Dict[str, List[float]]) -> Tuple[Tuple, List[str]]:
    """Convert a chemical composition to a graph representation for neural network input."""
    comp_dict = Composition(composition).get_el_amt_dict()
    elements_seq = list(comp_dict.keys())
    weights = list(comp_dict.values())
    weights = np.atleast_2d(weights).T / np.sum(weights)  # Normalize weights
    
    try:
        atom_fea = np.vstack([
            np.array(embedding_dict[str(element)]) for element in elements_seq
        ])
    except KeyError as ex:
        raise NotImplementedError(
            f"Element {ex} in '{composition}' has no embedding vector"
        )
    
    # Create fully-connected graph indices
    env_idx = list(range(len(elements_seq)))
    if len(env_idx) == 1:
        self_fea_idx = [0]
        nbr_fea_idx = [0]
    else:
        self_fea_idx = []
        nbr_fea_idx = []
        nbrs = len(elements_seq) - 1
        for i, _ in enumerate(elements_seq):
            self_fea_idx += [i] * nbrs
            nbr_fea_idx += env_idx[:i] + env_idx[i + 1:]
    
    # Convert to tensors
    atom_weights = torch.Tensor(weights)
    atom_fea = torch.Tensor(atom_fea)
    self_fea_idx = torch.LongTensor(self_fea_idx)
    nbr_fea_idx = torch.LongTensor(nbr_fea_idx)
    
    return ((atom_weights, atom_fea, self_fea_idx, nbr_fea_idx), composition), elements_seq


def _add_source_mask(graph: Tuple, source_elem: List[str]) -> Tuple:
    """Add a mask vector to identify source elements in the graph."""
    composition = graph[1]
    comp_dict = Composition(composition).get_el_amt_dict()
    
    mask_vec = []
    for elem in comp_dict.keys():
        if str(elem) in source_elem:
            mask_vec.append([source_elem.index(elem)])
        else:
            mask_vec.append([-1])  # -1 indicates non-source elements
    
    return (graph[0], graph[1], torch.tensor(mask_vec))


def _collate_temperature_batch(dataset_list: List[Tuple]) -> Tuple:
    """Collate individual graph data points into a batch for temperature prediction model (dual-input)."""
    # Initialize batch lists for targets
    batch_tar_atom_weights = []
    batch_tar_atom_fea = []
    batch_tar_self_fea_idx = []
    batch_tar_nbr_fea_idx = []
    batch_tar_atom_cry_idx = []
    batch_tar_metal_mask = []
    batch_tar_source_elem_idx = []
    
    # Initialize batch lists for precursors
    batch_pre_atom_weights = []
    batch_pre_atom_fea = []
    batch_pre_self_fea_idx = []
    batch_pre_nbr_fea_idx = []
    batch_pre_atom_cry_idx = []
    batch_pre_metal_mask = []
    batch_pre_source_elem_idx = []
    
    batch_y = []
    batch_comp = []
    batch_cry_ids = []

    tar_cry_base_idx = 0
    pre_cry_base_idx = 0
    tar_source_n_i = 0
    pre_source_n_i = 0
    
    for i, (x_tar_set, x_pre_set, tar_source_elem_idx, pre_source_elem_idx, y, cry_id) in enumerate(dataset_list):
        # Process target compositions
        n_i = 0
        tar_set = []
        for j, x_tar in enumerate(x_tar_set):
            atom_weights, atom_fea, self_fea_idx, nbr_fea_idx = x_tar[0]
            n_ij = atom_fea.shape[0]

            batch_tar_atom_weights.append(atom_weights)
            batch_tar_atom_fea.append(atom_fea)
            batch_tar_self_fea_idx.append(self_fea_idx + tar_cry_base_idx)
            batch_tar_nbr_fea_idx.append(nbr_fea_idx + tar_cry_base_idx)
            batch_tar_metal_mask.append(x_tar[2])
            
            tar_cry_base_idx += n_ij
            n_i += n_ij
            tar_set.append(x_tar[1])
        
        batch_tar_source_elem_idx.append(torch.tensor(tar_source_elem_idx) + tar_source_n_i)
        tar_source_n_i += max(tar_source_elem_idx) + 1
        batch_tar_atom_cry_idx.append(torch.tensor([i] * n_i))
        
        # Process precursor compositions
        n_i = 0
        pre_set = []
        for j, x_pre in enumerate(x_pre_set):
            atom_weights, atom_fea, self_fea_idx, nbr_fea_idx = x_pre[0]
            n_ij = atom_fea.shape[0]

            batch_pre_atom_weights.append(atom_weights)
            batch_pre_atom_fea.append(atom_fea)
            batch_pre_self_fea_idx.append(self_fea_idx + pre_cry_base_idx)
            batch_pre_nbr_fea_idx.append(nbr_fea_idx + pre_cry_base_idx)
            batch_pre_metal_mask.append(x_pre[2])
            
            pre_cry_base_idx += n_ij
            n_i += n_ij
            pre_set.append(x_pre[1])
        
        batch_pre_source_elem_idx.append(torch.tensor(pre_source_elem_idx) + pre_source_n_i)
        pre_source_n_i += max(pre_source_elem_idx) + 1
        batch_pre_atom_cry_idx.append(torch.tensor([i] * n_i))
        
        # Batch targets and metadata
        batch_y.append(y)
        batch_comp.append((tar_set, pre_set))
        batch_cry_ids.append(cry_id)

    return (
        (
            torch.cat(batch_tar_atom_weights, dim=0),
            torch.cat(batch_tar_atom_fea, dim=0),
            torch.cat(batch_tar_self_fea_idx, dim=0),
            torch.cat(batch_tar_nbr_fea_idx, dim=0),
            torch.cat(batch_tar_atom_cry_idx),
            torch.cat(batch_tar_metal_mask, dim=0),
            torch.cat(batch_tar_source_elem_idx, dim=0),
        ),
        (
            torch.cat(batch_pre_atom_weights, dim=0),
            torch.cat(batch_pre_atom_fea, dim=0),
            torch.cat(batch_pre_self_fea_idx, dim=0),
            torch.cat(batch_pre_nbr_fea_idx, dim=0),
            torch.cat(batch_pre_atom_cry_idx),
            torch.cat(batch_pre_metal_mask, dim=0),
            torch.cat(batch_pre_source_elem_idx, dim=0),
        ),
        torch.stack(batch_y, dim=0).reshape(-1, 1),
        batch_comp,
        batch_cry_ids,
    )


def _predict_synthesis_temperature_internal(
    target_composition: List[str],
    precursor_composition: List[str],
    model: torch.nn.Module,
    normalizer: Any,
    device: torch.device,
    embedding_dict: Dict[str, List[float]]
) -> float:
    """Internal function to predict synthesis temperature using the model."""
    dataset = []
    
    # Process target compositions
    x_tar_set = []
    elements_seq_set = []
    for composition in target_composition:
        x_tar, elements_seq = _composition_to_graph(composition, embedding_dict)
        source_elems, _ = _get_source_elements([composition])
        x_tar = _add_source_mask(x_tar, source_elems)
        x_tar_set.append(x_tar)
        elements_seq_set.append(elements_seq)
    
    # Get target source element indices
    source_elem_seq = []
    tar_source_elem_idx = []
    count = 0
    all_tar_source_elems, _ = _get_source_elements(target_composition)
    
    for elem_seq in elements_seq_set:
        for elem in elem_seq:
            if elem in all_tar_source_elems:
                if elem not in source_elem_seq:
                    source_elem_seq.append(elem)
                    tar_source_elem_idx.append(count)
                    count += 1
                else:
                    tar_source_elem_idx.append(source_elem_seq.index(elem))
    
    # Process precursor compositions
    x_pre_set = []
    elements_seq_set = []
    for composition in precursor_composition:
        x_pre, elements_seq = _composition_to_graph(composition, embedding_dict)
        source_elems, _ = _get_source_elements([composition])
        x_pre = _add_source_mask(x_pre, source_elems)
        x_pre_set.append(x_pre)
        elements_seq_set.append(elements_seq)
    
    # Get precursor source element indices
    source_elem_seq = []
    pre_source_elem_idx = []
    count = 0
    all_pre_source_elems, _ = _get_source_elements(precursor_composition)
    
    for elem_seq in elements_seq_set:
        for elem in elem_seq:
            if elem in all_pre_source_elems:
                if elem not in source_elem_seq:
                    source_elem_seq.append(elem)
                    pre_source_elem_idx.append(count)
                    count += 1
                else:
                    pre_source_elem_idx.append(source_elem_seq.index(elem))
    
    # Verify element correspondence
    if max(tar_source_elem_idx) != max(pre_source_elem_idx):
        raise ValueError(
            f"Target and precursor source element mismatch: "
            f"target has {max(tar_source_elem_idx) + 1} source elements, "
            f"precursors have {max(pre_source_elem_idx) + 1}"
        )
    
    # Create dummy label and prepare batch
    y = torch.mean(torch.tensor([0.0]))
    dataset.append((x_tar_set, x_pre_set, tar_source_elem_idx, pre_source_elem_idx, y, 0))

    input_tar, input_pre, batch_y, batch_comp, batch_i = _collate_temperature_batch(dataset)
    
    # Move to device
    input_tar = tuple([tensor.to(device) for tensor in input_tar])
    input_pre = tuple([tensor.to(device) for tensor in input_pre])
    
    # Predict temperature
    with torch.no_grad():
        output, _ = model(input_tar, input_pre)
        output, log_std = output.chunk(2, dim=1)
        pred = normalizer.denorm(output.data.cpu())
    
    return round(pred[0].item(), 1)


# ============================================================================
# Model Manager (Encapsulates State)
# ============================================================================

class TemperaturePredictor:
    """
    Encapsulates model loading and prediction logic.
    
    Models are loaded lazily on first prediction and cached in memory.
    This is a standard pattern for ML inference services to avoid reloading
    large model files (hundreds of MB) on every request.
    """
    
    def __init__(self, base_dir: str = None):
        """
        Initialize predictor (models loaded lazily on first use).
        
        Args:
            base_dir: Base directory for model files. If None, uses parent of this file.
        """
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.model = None
        self.normalizer = None
        self.device = None
        self.embedding_dict = None
        self._loaded = False
    
    def _ensure_loaded(self):
        """Load models and data files if not already loaded."""
        if self._loaded:
            return
        
        # Load embeddings
        embedding_path = os.path.join(self.base_dir, "assets/element_embedding.json")
        with open(embedding_path, 'r', encoding='utf-8-sig') as f:
            self.embedding_dict = json.load(f)
        
        # Load model and normalizer (downloaded from GitHub releases if not cached)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        model_path = model_downloader.get_model_path('elemwiseretro_temperature_predictor')
        self.model = pk.load(open(model_path, 'rb'))
        self.model.to(self.device)
        self.model.eval()
        
        normalizer_path = model_downloader.get_model_path('elemwiseretro_temperature_normalizer')
        self.normalizer = pk.load(open(normalizer_path, 'rb'))
        
        self._loaded = True
    
    def predict(self, target_formula: str, precursors: List[str]) -> Dict[str, Any]:
        """
        Predict synthesis temperature for a target-precursor pair.
        
        Args:
            target_formula: Chemical formula of target material
            precursors: List of precursor formulas
            
        Returns:
            Dictionary with temperature predictions and metadata
        """
        self._ensure_loaded()
        
        target_composition = [target_formula]
        predicted_temp = _predict_synthesis_temperature_internal(
            target_composition,
            precursors,
            self.model,
            self.normalizer,
            self.device,
            self.embedding_dict
        )
        
        return {
            "target": target_formula,
            "precursors": precursors,
            "temperature_celsius": float(predicted_temp),
            "temperature_kelvin": float(predicted_temp + 273.15),
            "metadata": {
                "model_type": "ElemwiseRetro",
                "device": str(self.device),
                "temperature_unit": "celsius"
            }
        }


# Module-level singleton instance (lazy-loaded)
_predictor = None


def _get_predictor() -> TemperaturePredictor:
    """Get or create the module-level predictor singleton."""
    global _predictor
    if _predictor is None:
        _predictor = TemperaturePredictor()
    return _predictor


# ============================================================================
# MCP Tool Function
# ============================================================================

def er_predict_temperature(
    target_formula: str,
    precursors: List[str]
) -> Dict[str, Any]:
    """
    Predict the synthesis temperature for a target material given precursors.
    
    This function predicts the optimal synthesis temperature (in °C) for producing
    a target inorganic material from a given set of precursor compounds using a
    trained neural network model.
    
    Models are cached in memory after first call for performance (2-3 second load time).
    This is thread-safe for read operations after initial load.
    
    Args:
        target_formula: Chemical formula of the target material (e.g., "Li7La3Zr2O12")
        precursors: List of precursor formulas (e.g., ["Li2CO3", "La2O3", "ZrO2"])
    
    Returns:
        Dictionary containing:
        - target: The input target formula
        - precursors: The input precursor list
        - temperature_celsius: Predicted synthesis temperature in °C
        - temperature_kelvin: Predicted temperature in Kelvin
        - metadata: Model and device information
    
    Example:
        >>> result = er_predict_temperature("Li7La3Zr2O12", ["Li2CO3", "La2O3", "ZrO2"])
        >>> print(result['temperature_celsius'])
        908.3
    
    Raises:
        ValueError: If inputs are invalid or precursors don't match target elements
        RuntimeError: If model loading or prediction fails
    """
    # Validate inputs
    if not target_formula or not isinstance(target_formula, str) or not target_formula.strip():
        raise ValueError("target_formula must be a non-empty string")
    
    if not precursors or not isinstance(precursors, list):
        raise ValueError("precursors must be a non-empty list of strings")
    
    if not all(isinstance(p, str) for p in precursors):
        raise ValueError("all precursors must be strings")
    
    try:
        predictor = _get_predictor()
        return predictor.predict(target_formula, precursors)
    except ValueError as e:
        # Re-raise validation errors from internal function
        raise ValueError(f"Element mismatch: {str(e)}") from e
    except Exception as e:
        raise RuntimeError(f"Temperature prediction failed: {str(e)}") from e


# ============================================================================
# CLI Interface (for testing)
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Predict synthesis temperature for inorganic materials'
    )
    parser.add_argument(
        'target',
        type=str,
        help='Target material formula (e.g., "Li7La3Zr2O12")'
    )
    parser.add_argument(
        'precursors',
        type=str,
        nargs='+',
        help='Precursor formulas (e.g., Li2CO3 La2O3 ZrO2)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    
    args = parser.parse_args()
    
    # Run prediction
    result = er_predict_temperature(args.target, args.precursors)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\nTemperature Prediction")
        print("=" * 80)
        print(f"Target:     {result['target']}")
        print(f"Precursors: {result['precursors']}")
        print(f"\nPredicted Temperature: {result['temperature_celsius']}°C")
        print(f"                      ({result['temperature_kelvin']:.1f} K)")
        print(f"\n{'=' * 80}")
        print(f"Device: {result['metadata']['device']}")
