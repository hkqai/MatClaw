"""
Precursor Prediction Tool for MCP

This module provides a standalone tool for predicting synthesis precursors for inorganic materials.
Designed to be exposed as an MCP (Model Context Protocol) tool.

This is a self-contained module with no dependencies on other project files.
"""

import json
import os
from typing import List, Dict, Any, Tuple

import numpy as np
import torch
import torch.nn.functional as F
import pickle as pk
from pymatgen.core import Composition
from torch_scatter import scatter_mean

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


def _collate_precursor_batch(dataset_list: List[Tuple]) -> Tuple:
    """Collate individual graph data points into a batch for precursor prediction model."""
    # Initialize batch lists
    batch_tar_atom_weights = []
    batch_tar_atom_fea = []
    batch_tar_self_fea_idx = []
    batch_tar_nbr_fea_idx = []
    batch_tar_atom_cry_idx = []
    batch_tar_metal_mask = []
    batch_tar_source_elem_idx = []
    batch_y = []
    batch_y2 = []
    batch_comp = []
    batch_ratio = []
    batch_cry_ids = []

    tar_cry_base_idx = 0
    source_n_i = 0
    
    for i, (x_tar_set, source_elem_idx, y, y2, y_stoi, y_ratio, cry_id) in enumerate(dataset_list):
        n_i = 0
        tar_set = []
        
        for j, x_tar in enumerate(x_tar_set):
            atom_weights, atom_fea, self_fea_idx, nbr_fea_idx = x_tar[0]
            n_ij = atom_fea.shape[0]  # Number of atoms in this composition

            # Batch features
            batch_tar_atom_weights.append(atom_weights)
            batch_tar_atom_fea.append(atom_fea)

            # Adjust indices for batched graph
            batch_tar_self_fea_idx.append(self_fea_idx + tar_cry_base_idx)
            batch_tar_nbr_fea_idx.append(nbr_fea_idx + tar_cry_base_idx)
            batch_tar_metal_mask.append(x_tar[2])
            
            tar_cry_base_idx += n_ij
            n_i += n_ij
            tar_set.append(x_tar[1])
        
        # Map source element indices
        batch_tar_source_elem_idx.append(torch.tensor(source_elem_idx) + source_n_i)
        source_n_i += max(source_elem_idx) + 1
        
        # Map atoms to crystal index
        batch_tar_atom_cry_idx.append(torch.tensor([i] * n_i))

        # Batch targets
        batch_y.append(y)
        batch_y2.append(y2)
        batch_comp.append((tar_set, y_stoi))
        batch_ratio += y_ratio
        batch_cry_ids.append(cry_id)

    return (
        (
            torch.cat(batch_tar_atom_weights, dim=0),
            torch.cat(batch_tar_atom_fea, dim=0),
            torch.cat(batch_tar_self_fea_idx, dim=0),
            torch.cat(batch_tar_nbr_fea_idx, dim=0),
            torch.cat(batch_tar_atom_cry_idx),
        ),
        torch.cat(batch_tar_metal_mask, dim=0),
        torch.cat(batch_tar_source_elem_idx, dim=0),
        torch.cat(batch_y, dim=0),
        torch.cat(batch_y2, dim=0),
        batch_comp,
        batch_ratio,
        batch_cry_ids,
    )


def _predict_precursor_sets_internal(
    target_composition: List[str],
    top_k: int,
    model: torch.nn.Module,
    device: torch.device,
    embedding_dict: Dict[str, List[float]],
    anion_parts: Dict[str, Any],
    stoichiometry_dict: Dict[str, List[str]]
) -> List[Tuple[List[str], float]]:
    """Internal function to predict precursor sets using the model."""
    # Build graph representations
    dataset = []
    x_tar_set = []
    elements_seq_set = []
    
    for composition in target_composition:
        x_tar, elements_seq = _composition_to_graph(composition, embedding_dict)
        source_elems, _ = _get_source_elements([composition])
        x_tar = _add_source_mask(x_tar, source_elems)
        x_tar_set.append(x_tar)
        elements_seq_set.append(elements_seq)
    
    # Get unique source elements and their indices
    source_elem_seq = []
    source_elem_idx = []
    count = 0
    all_source_elems, _ = _get_source_elements(target_composition)
    
    for elem_seq in elements_seq_set:
        for elem in elem_seq:
            if elem in all_source_elems:
                if elem not in source_elem_seq:
                    source_elem_seq.append(elem)
                    source_elem_idx.append(count)
                    count += 1
                else:
                    source_elem_idx.append(source_elem_seq.index(elem))

    # Create dummy labels for inference
    y = torch.Tensor(np.array([np.zeros(len(anion_parts))]))
    y2 = torch.Tensor(np.array([np.zeros(len(embedding_dict['Li']))]))
    dataset.append((x_tar_set, source_elem_idx, y, y2, [''], [], 0))

    # Prepare batch
    input_tar, metal_mask, source_elem_idx, batch_y, batch_y2, batch_comp, batch_ratio, batch_i = _collate_precursor_batch(dataset)
    input_tar = tuple([tensor.to(device) for tensor in input_tar])
    metal_mask = metal_mask.to(device)
    source_elem_idx = source_elem_idx.to(device)
    
    pre_set_idx = scatter_mean(
        input_tar[4][torch.where(metal_mask != -1)[0]], 
        source_elem_idx, 
        dim=0
    )

    # Get model predictions
    with torch.no_grad():
        template_output, _ = model(input_tar, metal_mask, source_elem_idx, pre_set_idx)

    # Extract top-k predictions for each element
    score_matrix = []
    pred_matrix = []
    for k in range(top_k):
        scores = torch.kthvalue(
            F.softmax(template_output, dim=1), 
            template_output.shape[1] - k
        )[0]
        preds = torch.kthvalue(
            F.softmax(template_output, dim=1), 
            template_output.shape[1] - k
        )[1]
        score_matrix.append(scores)
        pred_matrix.append(preds)
    
    score_matrix = torch.stack(score_matrix, dim=0)
    pred_matrix = torch.stack(pred_matrix, dim=0)

    # Compute all combinations' joint probabilities
    set_num = template_output.shape[0]  # Number of source elements
    set_score_list = None
    
    for elem_idx in range(set_num):
        if elem_idx == 0:
            set_score_list = score_matrix[:, elem_idx:elem_idx+1]
        else:
            # Multiply probabilities: P(set) = P(A) × P(B) × P(C) × ...
            set_score_list = torch.matmul(
                set_score_list, 
                score_matrix[:, elem_idx:elem_idx+1].T
            ).reshape(-1, 1)

    # Find top-k combinations 
    top_k_result = []
    for k in range(top_k):
        kst_score = round(
            torch.kthvalue(set_score_list.T, len(set_score_list) - k)[0].item(), 
            4
        )
        kst_idx = torch.kthvalue(set_score_list.T, len(set_score_list) - k)[1].item()
        
        # Decode multi-dimensional index
        kst_pre_set = []
        for idx in range(set_num):
            kst_pre_set.append(pred_matrix[int(kst_idx / (top_k ** (set_num - idx - 1))), idx].item())
            kst_idx = kst_idx % (top_k ** (set_num - idx - 1))
        top_k_result.append((kst_pre_set, kst_score))

    # Convert predictions to chemical formulas
    kth_precursors = []
    anion_list = list(anion_parts)
    
    for k in range(len(top_k_result)):
        set_score = top_k_result[k][1]
        precursors_set = []
        
        for l in range(len(source_elem_seq)):
            source_part = source_elem_seq[l]
            counter_part = anion_list[top_k_result[k][0][l]]
            stoi_space = stoichiometry_dict.get(source_part + counter_part, [])
            
            if len(stoi_space) == 0:
                precursor = f'({source_part})({counter_part})'
            else:
                precursor = stoi_space[0]
            
            precursors_set.append(precursor)
        
        kth_precursors.append((precursors_set, set_score))

    return kth_precursors


# ============================================================================
# Model Manager (Encapsulates State)
# ============================================================================

class PrecursorPredictor:
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
        self.device = None
        self.embedding_dict = None
        self.anion_parts = None
        self.stoichiometry_dict = None
        self._loaded = False
    
    def _ensure_loaded(self):
        """Load models and data files if not already loaded."""
        if self._loaded:
            return
        
        # Load embeddings
        embedding_path = os.path.join(self.base_dir, "assets/element_embedding.json")
        with open(embedding_path, 'r', encoding='utf-8-sig') as f:
            self.embedding_dict = json.load(f)
        
        # Load data files
        anion_path = os.path.join(self.base_dir, "assets/precursor_anion_classes.json")
        with open(anion_path, "r") as f:
            self.anion_parts = json.load(f)
        
        stoi_path = os.path.join(self.base_dir, "assets/element_anion_formulas.json")
        with open(stoi_path, "r") as f:
            self.stoichiometry_dict = json.load(f)
        
        # Load model (downloaded from GitHub releases if not cached)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model_path = model_downloader.get_model_path('elemwiseretro_precursor_predictor')
        self.model = pk.load(open(model_path, 'rb'))
        self.model.to(self.device)
        self.model.eval()
        
        self._loaded = True
    
    def predict(self, target_formula: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Predict precursor sets for a target material.
        
        Args:
            target_formula: Chemical formula of target material
            top_k: Number of precursor sets to return
            
        Returns:
            Dictionary with precursor predictions and metadata
        """
        self._ensure_loaded()
        
        target_composition = [target_formula]
        set_predictions = _predict_precursor_sets_internal(
            target_composition,
            top_k,
            self.model,
            self.device,
            self.embedding_dict,
            self.anion_parts,
            self.stoichiometry_dict
        )
        
        # Format results
        precursor_sets = [
            {
                "precursors": precursors,
                "confidence": float(score)
            }
            for precursors, score in set_predictions
        ]
        
        return {
            "target": target_formula,
            "precursor_sets": precursor_sets,
            "top_prediction": precursor_sets[0] if precursor_sets else None,
            "metadata": {
                "model_type": "ElemwiseRetro",
                "device": str(self.device),
                "num_predictions": len(precursor_sets)
            }
        }


# Module-level singleton instance (lazy-loaded)
_predictor = None


def _get_predictor() -> PrecursorPredictor:
    """Get or create the module-level predictor singleton."""
    global _predictor
    if _predictor is None:
        _predictor = PrecursorPredictor()
    return _predictor


# ============================================================================
# MCP Tool Function
# ============================================================================

def predict_precursors(
    target_formula: str,
    top_k: int = 5,
    return_individual: bool = False
) -> Dict[str, Any]:
    """
    Predict synthesis precursor sets for an inorganic target material.
    
    This function predicts the most likely precursor combinations for synthesizing
    a given target inorganic material using a trained neural network model.
    
    Models are cached in memory after first call for performance (2-3 second load time).
    This is thread-safe for read operations after initial load.
    
    Args:
        target_formula: Chemical formula of the target material (e.g., "Li7La3Zr2O12")
        top_k: Number of precursor sets to return (default: 5, range: 1-20)
        return_individual: If True, also return individual element predictions (not yet implemented)
    
    Returns:
        Dictionary containing:
        - target: The input target formula
        - precursor_sets: List of dicts with 'precursors' (list) and 'confidence' (float)
        - top_prediction: The highest confidence precursor set
        - metadata: Model and device information
    
    Example:
        >>> result = predict_precursors("Li7La3Zr2O12", top_k=3)
        >>> print(result['top_prediction'])
        {'precursors': ['Li2CO3', 'La2O3', 'ZrO2'], 'confidence': 0.6121}
    
    Raises:
        ValueError: If target_formula is invalid or top_k is out of range
        RuntimeError: If model loading or prediction fails
    """
    # Validate inputs
    if not target_formula or not isinstance(target_formula, str) or not target_formula.strip():
        raise ValueError("target_formula must be a non-empty string")
    
    if not isinstance(top_k, int) or top_k < 1 or top_k > 20:
        raise ValueError("top_k must be an integer between 1 and 20")
    
    try:
        predictor = _get_predictor()
        return predictor.predict(target_formula, top_k)
    except Exception as e:
        raise RuntimeError(f"Precursor prediction failed: {str(e)}") from e


# ============================================================================
# CLI Interface (for testing)
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Predict synthesis precursors for inorganic materials'
    )
    parser.add_argument(
        'target',
        type=str,
        help='Target material formula (e.g., "Li7La3Zr2O12")'
    )
    parser.add_argument(
        '--top-k',
        type=int,
        default=5,
        help='Number of precursor sets to return (default: 5)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    
    args = parser.parse_args()
    
    # Run prediction
    result = predict_precursors(args.target, args.top_k)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\nPrecursor Predictions for {result['target']}")
        print("=" * 80)
        
        for i, pred in enumerate(result['precursor_sets'], 1):
            print(f"\nRank {i} (confidence: {pred['confidence']:.4f}):")
            print(f"  {pred['precursors']}")
        
        print(f"\n{'=' * 80}")
        print(f"Device: {result['metadata']['device']}")
