"""
Shared utilities for Bayesian Optimization tools.

This module provides core functionality for parameter space handling, Gaussian Process
modeling, acquisition function computation, and state management for generic Bayesian
Optimization campaigns.

Design Philosophy:
- Domain-agnostic: works with any parameter types and objectives
- Robust: extensive validation and error handling
- Flexible: supports continuous, discrete, categorical parameters
- Efficient: caches models and supports batch suggestions
"""

import json
import os
from typing import Dict, Any, List, Tuple, Optional, Union
import numpy as np
from pathlib import Path


# ============================================================================
# Parameter Space Utilities
# ============================================================================

def validate_parameter_space(parameter_space: List[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
    """
    Validate parameter space specification.
    
    Parameters
    ----------
    parameter_space : List[Dict[str, Any]]
        List of parameter definitions
        
    Returns
    -------
    Tuple[bool, Optional[str]]
        (is_valid, error_message)
    """
    if not isinstance(parameter_space, list):
        return False, "parameter_space must be a list"
    
    if len(parameter_space) == 0:
        return False, "parameter_space must contain at least one parameter"
    
    param_names = set()
    
    for i, param in enumerate(parameter_space):
        if not isinstance(param, dict):
            return False, f"Parameter {i} must be a dictionary"
        
        # Check required fields
        if "name" not in param:
            return False, f"Parameter {i} missing required field 'name'"
        if "type" not in param:
            return False, f"Parameter {i} missing required field 'type'"
        
        name = param["name"]
        param_type = param["type"]
        
        # Check for duplicate names
        if name in param_names:
            return False, f"Duplicate parameter name: {name}"
        param_names.add(name)
        
        # Validate based on type
        if param_type == "continuous":
            if "bounds" not in param:
                return False, f"Continuous parameter '{name}' missing 'bounds'"
            bounds = param["bounds"]
            if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
                return False, f"Parameter '{name}' bounds must be [min, max]"
            if bounds[0] >= bounds[1]:
                return False, f"Parameter '{name}' bounds invalid: min >= max"
                
        elif param_type == "discrete":
            if "values" not in param:
                return False, f"Discrete parameter '{name}' missing 'values'"
            values = param["values"]
            if not isinstance(values, list) or len(values) == 0:
                return False, f"Parameter '{name}' values must be non-empty list"
                
        elif param_type == "categorical":
            if "choices" not in param:
                return False, f"Categorical parameter '{name}' missing 'choices'"
            choices = param["choices"]
            if not isinstance(choices, list) or len(choices) == 0:
                return False, f"Parameter '{name}' choices must be non-empty list"
            if len(choices) != len(set(choices)):
                return False, f"Parameter '{name}' has duplicate choices"
                
        else:
            return False, f"Parameter '{name}' has invalid type: {param_type}"
    
    return True, None


def validate_objective_config(objective_config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate objective configuration.
    
    Parameters
    ----------
    objective_config : Dict[str, Any]
        Objective specification
        
    Returns
    -------
    Tuple[bool, Optional[str]]
        (is_valid, error_message)
    """
    if not isinstance(objective_config, dict):
        return False, "objective_config must be a dictionary"
    
    if "type" not in objective_config:
        return False, "objective_config missing required field 'type'"
    
    obj_type = objective_config["type"]
    if obj_type not in ["single_objective", "multi_objective"]:
        return False, f"Invalid objective type: {obj_type}"
    
    if "metrics" not in objective_config:
        return False, "objective_config missing required field 'metrics'"
    
    metrics = objective_config["metrics"]
    if not isinstance(metrics, list) or len(metrics) == 0:
        return False, "metrics must be a non-empty list"
    
    if obj_type == "single_objective" and len(metrics) > 1:
        return False, "single_objective requires exactly one metric"
    
    if "direction" in objective_config:
        direction = objective_config["direction"]
        valid_directions = ["maximize", "minimize"]
        
        if isinstance(direction, str):
            if direction not in valid_directions:
                return False, f"Invalid direction: {direction}"
        elif isinstance(direction, list):
            if len(direction) != len(metrics):
                return False, "direction list must match metrics length"
            for d in direction:
                if d not in valid_directions:
                    return False, f"Invalid direction in list: {d}"
        else:
            return False, "direction must be string or list of strings"
    
    return True, None


def encode_parameters(
    params: Dict[str, Any],
    parameter_space: List[Dict[str, Any]]
) -> np.ndarray:
    """
    Encode parameter dictionary to numerical array for GP modeling.
    
    Parameters
    ----------
    params : Dict[str, Any]
        Parameter values
    parameter_space : List[Dict[str, Any]]
        Parameter space definition
        
    Returns
    -------
    np.ndarray
        Encoded parameter vector
    """
    encoded = []
    
    for param_def in parameter_space:
        name = param_def["name"]
        param_type = param_def["type"]
        value = params[name]
        
        if param_type == "continuous":
            # Normalize to [0, 1]
            bounds = param_def["bounds"]
            if param_def.get("log_scale", False):
                log_bounds = [np.log(b) for b in bounds]
                normalized = (np.log(value) - log_bounds[0]) / (log_bounds[1] - log_bounds[0])
            else:
                normalized = (value - bounds[0]) / (bounds[1] - bounds[0])
            encoded.append(normalized)
            
        elif param_type == "discrete":
            # Map to index position normalized to [0, 1]
            values = param_def["values"]
            idx = values.index(value)
            normalized = idx / (len(values) - 1) if len(values) > 1 else 0.5
            encoded.append(normalized)
            
        elif param_type == "categorical":
            # One-hot encoding
            choices = param_def["choices"]
            one_hot = [1.0 if c == value else 0.0 for c in choices]
            encoded.extend(one_hot)
    
    return np.array(encoded)


def decode_parameters(
    encoded: np.ndarray,
    parameter_space: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Decode numerical array back to parameter dictionary.
    
    Parameters
    ----------
    encoded : np.ndarray
        Encoded parameter vector
    parameter_space : List[Dict[str, Any]]
        Parameter space definition
        
    Returns
    -------
    Dict[str, Any]
        Parameter values
    """
    params = {}
    idx = 0
    
    for param_def in parameter_space:
        name = param_def["name"]
        param_type = param_def["type"]
        
        if param_type == "continuous":
            normalized = encoded[idx]
            bounds = param_def["bounds"]
            
            if param_def.get("log_scale", False):
                log_bounds = [np.log(b) for b in bounds]
                value = np.exp(normalized * (log_bounds[1] - log_bounds[0]) + log_bounds[0])
            else:
                value = normalized * (bounds[1] - bounds[0]) + bounds[0]
            
            params[name] = float(value)
            idx += 1
            
        elif param_type == "discrete":
            normalized = encoded[idx]
            values = param_def["values"]
            # Round to nearest discrete value
            position = normalized * (len(values) - 1)
            discrete_idx = int(np.round(position))
            discrete_idx = np.clip(discrete_idx, 0, len(values) - 1)
            params[name] = values[discrete_idx]
            idx += 1
            
        elif param_type == "categorical":
            choices = param_def["choices"]
            one_hot = encoded[idx:idx + len(choices)]
            # Select category with highest value
            category_idx = int(np.argmax(one_hot))
            params[name] = choices[category_idx]
            idx += len(choices)
    
    return params


def get_encoded_dimension(parameter_space: List[Dict[str, Any]]) -> int:
    """
    Get the total dimension of the encoded parameter space.
    
    Parameters
    ----------
    parameter_space : List[Dict[str, Any]]
        Parameter space definition
        
    Returns
    -------
    int
        Total encoded dimension
    """
    dim = 0
    for param_def in parameter_space:
        if param_def["type"] in ["continuous", "discrete"]:
            dim += 1
        elif param_def["type"] == "categorical":
            dim += len(param_def["choices"])
    return dim


# ============================================================================
# Gaussian Process Utilities
# ============================================================================

def fit_gp_model(
    X: np.ndarray,
    y: np.ndarray,
    noise_variance: float = 1e-6
) -> Any:
    """
    Fit a Gaussian Process regression model.
    
    Parameters
    ----------
    X : np.ndarray
        Input features (n_samples, n_features)
    y : np.ndarray
        Target values (n_samples,)
    noise_variance : float
        Observation noise variance
        
    Returns
    -------
    GP model object
    """
    try:
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import Matern, ConstantKernel, WhiteKernel
    except ImportError:
        raise ImportError(
            "scikit-learn required for Gaussian Process modeling.\n"
            "Install with: pip install scikit-learn"
        )
    
    # Construct kernel: Constant * Matern + WhiteKernel for noise
    kernel = ConstantKernel(1.0, constant_value_bounds=(1e-3, 1e3)) * \
             Matern(length_scale=1.0, length_scale_bounds=(1e-2, 1e2), nu=2.5) + \
             WhiteKernel(noise_level=noise_variance, noise_level_bounds=(1e-10, 1e-1))
    
    gp = GaussianProcessRegressor(
        kernel=kernel,
        n_restarts_optimizer=10,
        normalize_y=True,
        random_state=42
    )
    
    gp.fit(X, y)
    return gp


# ============================================================================
# Acquisition Functions
# ============================================================================

def expected_improvement(
    X: np.ndarray,
    gp_model: Any,
    y_best: float,
    xi: float = 0.01
) -> np.ndarray:
    """
    Expected Improvement acquisition function.
    
    Parameters
    ----------
    X : np.ndarray
        Candidate points (n_candidates, n_features)
    gp_model : GP model
        Fitted Gaussian Process model
    y_best : float
        Best observed value so far
    xi : float
        Exploration-exploitation trade-off parameter
        
    Returns
    -------
    np.ndarray
        EI values for each candidate
    """
    try:
        from scipy.stats import norm
    except ImportError:
        raise ImportError("scipy required for acquisition functions")
    
    mu, sigma = gp_model.predict(X, return_std=True)
    
    # Ensure mu and sigma are 1D arrays
    mu = mu.flatten()
    sigma = sigma.flatten()
    
    # Avoid division by zero
    sigma = np.maximum(sigma, 1e-9)
    
    improvement = mu - y_best - xi
    Z = improvement / sigma
    
    ei = improvement * norm.cdf(Z) + sigma * norm.pdf(Z)
    return ei


def upper_confidence_bound(
    X: np.ndarray,
    gp_model: Any,
    beta: float = 2.0
) -> np.ndarray:
    """
    Upper Confidence Bound acquisition function.
    
    Parameters
    ----------
    X : np.ndarray
        Candidate points
    gp_model : GP model
        Fitted Gaussian Process model
    beta : float
        Exploration parameter (higher = more exploration)
        
    Returns
    -------
    np.ndarray
        UCB values
    """
    mu, sigma = gp_model.predict(X, return_std=True)
    return mu + beta * sigma


def probability_of_improvement(
    X: np.ndarray,
    gp_model: Any,
    y_best: float,
    xi: float = 0.01
) -> np.ndarray:
    """
    Probability of Improvement acquisition function.
    
    Parameters
    ----------
    X : np.ndarray
        Candidate points
    gp_model : GP model
        Fitted Gaussian Process model
    y_best : float
        Best observed value so far
    xi : float
        Exploration parameter
        
    Returns
    -------
    np.ndarray
        PI values
    """
    try:
        from scipy.stats import norm
    except ImportError:
        raise ImportError("scipy required for acquisition functions")
    
    mu, sigma = gp_model.predict(X, return_std=True)
    sigma = np.maximum(sigma, 1e-9)
    
    Z = (mu - y_best - xi) / sigma
    return norm.cdf(Z)


# ============================================================================
# State Management
# ============================================================================

def save_campaign_state(
    campaign_dir: str,
    state: Dict[str, Any]
) -> None:
    """
    Save campaign state to JSON file.
    
    Parameters
    ----------
    campaign_dir : str
        Campaign directory path
    state : Dict[str, Any]
        State dictionary to save
    """
    state_path = os.path.join(campaign_dir, "bo_state.json")
    
    # Convert numpy types to Python types for JSON serialization
    state_serializable = _convert_to_json_serializable(state)
    
    with open(state_path, 'w') as f:
        json.dump(state_serializable, f, indent=2)


def load_campaign_state(campaign_dir: str) -> Dict[str, Any]:
    """
    Load campaign state from JSON file.
    
    Parameters
    ----------
    campaign_dir : str
        Campaign directory path
        
    Returns
    -------
    Dict[str, Any]
        Campaign state
    """
    state_path = os.path.join(campaign_dir, "bo_state.json")
    
    if not os.path.exists(state_path):
        raise FileNotFoundError(f"Campaign state not found: {state_path}")
    
    with open(state_path, 'r') as f:
        return json.load(f)


def _convert_to_json_serializable(obj: Any) -> Any:
    """
    Recursively convert numpy types to Python native types for JSON serialization.
    
    Parameters
    ----------
    obj : Any
        Object to convert
        
    Returns
    -------
    Any
        JSON-serializable version of the object
    """
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: _convert_to_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_to_json_serializable(item) for item in obj]
    else:
        return obj


def save_observations(
    campaign_dir: str,
    observations: List[Dict[str, Any]]
) -> None:
    """
    Save observations to JSON file.
    
    Parameters
    ----------
    campaign_dir : str
        Campaign directory path
    observations : List[Dict[str, Any]]
        List of observation records
    """
    obs_path = os.path.join(campaign_dir, "bo_observations.json")
    
    # Convert numpy types to Python types for JSON serialization
    observations_serializable = _convert_to_json_serializable(observations)
    
    with open(obs_path, 'w') as f:
        json.dump(observations_serializable, f, indent=2)


def load_observations(campaign_dir: str) -> List[Dict[str, Any]]:
    """
    Load observations from JSON file.
    
    Parameters
    ----------
    campaign_dir : str
        Campaign directory path
        
    Returns
    -------
    List[Dict[str, Any]]
        List of observation records
    """
    obs_path = os.path.join(campaign_dir, "bo_observations.json")
    
    if not os.path.exists(obs_path):
        return []
    
    with open(obs_path, 'r') as f:
        return json.load(f)


# ============================================================================
# Random Sampling Utilities
# ============================================================================

def sample_random_parameters(
    parameter_space: List[Dict[str, Any]],
    n_samples: int = 1,
    seed: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Generate random parameter samples from the parameter space.
    
    Parameters
    ----------
    parameter_space : List[Dict[str, Any]]
        Parameter space definition
    n_samples : int
        Number of samples to generate
    seed : Optional[int]
        Random seed for reproducibility
        
    Returns
    -------
    List[Dict[str, Any]]
        List of random parameter dictionaries
    """
    if seed is not None:
        np.random.seed(seed)
    
    samples = []
    
    for _ in range(n_samples):
        params = {}
        
        for param_def in parameter_space:
            name = param_def["name"]
            param_type = param_def["type"]
            
            if param_type == "continuous":
                bounds = param_def["bounds"]
                if param_def.get("log_scale", False):
                    log_bounds = [np.log(b) for b in bounds]
                    value = np.exp(np.random.uniform(log_bounds[0], log_bounds[1]))
                else:
                    value = np.random.uniform(bounds[0], bounds[1])
                params[name] = float(value)
                
            elif param_type == "discrete":
                values = param_def["values"]
                params[name] = np.random.choice(values)
                
            elif param_type == "categorical":
                choices = param_def["choices"]
                params[name] = np.random.choice(choices)
        
        samples.append(params)
    
    return samples
