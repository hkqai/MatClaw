"""
Bayesian Optimization experiment suggestion tool.

This tool suggests the next experiment(s) to run by fitting a Gaussian Process
surrogate model to observed data and optimizing an acquisition function.

Supports multiple acquisition strategies:
- Expected Improvement (EI): balances exploration and exploitation
- Upper Confidence Bound (UCB): tunable exploration
- Probability of Improvement (PI): conservative exploitation
- Random: pure exploration (useful for baseline comparison)
"""

from typing import Dict, Any, List, Optional, Annotated
from pydantic import Field
import os
import numpy as np
from tools.bayesian_optimization._bo_utils import (
    load_campaign_state,
    load_observations,
    encode_parameters,
    decode_parameters,
    get_encoded_dimension,
    fit_gp_model,
    expected_improvement,
    upper_confidence_bound,
    probability_of_improvement,
    sample_random_parameters
)


def bo_suggest_experiment(
    campaign_dir: Annotated[
        str,
        Field(
            description=(
                "Path to the campaign directory created by bo_initialize_campaign. "
                "Must contain bo_state.json and bo_observations.json with recorded data."
            )
        )
    ],
    batch_size: Annotated[
        int,
        Field(
            default=1,
            ge=1,
            le=50,
            description=(
                "Number of experiments to suggest. For batch_size > 1, uses sequential "
                "greedy selection (each suggestion accounts for previous ones in the batch). "
                "Default: 1."
            )
        )
    ] = 1,
    acquisition_function: Annotated[
        str,
        Field(
            default="ei",
            description=(
                "Acquisition function to use for selecting next experiments:\n"
                "  - 'ei': Expected Improvement (recommended, balances exploration/exploitation)\n"
                "  - 'ucb': Upper Confidence Bound (tunable via exploration_weight)\n"
                "  - 'pi': Probability of Improvement (more exploitative)\n"
                "  - 'random': Random sampling (useful for baseline or pure exploration)\n"
                "Default: 'ei'"
            )
        )
    ] = "ei",
    exploration_weight: Annotated[
        float,
        Field(
            default=0.01,
            ge=0.0,
            le=10.0,
            description=(
                "Exploration parameter for acquisition functions:\n"
                "  - For 'ei' and 'pi': xi parameter (0 = pure exploitation, larger = more exploration)\n"
                "  - For 'ucb': beta parameter (typical range 1-3, higher = more exploration)\n"
                "Default: 0.01 for ei/pi, 2.0 for ucb"
            )
        )
    ] = 0.01,
    n_candidates: Annotated[
        int,
        Field(
            default=10000,
            ge=100,
            le=100000,
            description=(
                "Number of random candidate points to evaluate when optimizing the "
                "acquisition function. Higher values improve optimization quality but "
                "increase computation time. Default: 10000."
            )
        )
    ] = 10000,
    random_seed: Annotated[
        Optional[int],
        Field(
            default=None,
            description=(
                "Random seed for reproducibility. If None, results will vary between runs."
            )
        )
    ] = None,
) -> Dict[str, Any]:
    """
    Suggest next experiment(s) using Bayesian Optimization.

    Fits a Gaussian Process model to observed data and suggests parameter settings
    that maximize the acquisition function. During the initial random phase, returns
    random samples instead of using the GP model.

    Returns
    -------
    dict:
        success                (bool)    Whether suggestion succeeded
        campaign_dir           (str)     Absolute path to campaign directory
        n_suggestions          (int)     Number of suggestions returned
        suggestions            (list)    List of suggested parameter dictionaries
        acquisition_function   (str)     Acquisition function used
        using_gp_model         (bool)    True if GP model was used, False if random sampling
        n_observations         (int)     Number of observations used for modeling
        gp_model_score         (float)   GP model R² score (if applicable)
        best_observed_value    (float)   Best objective value observed so far
        best_observed_params   (dict)    Parameters that achieved best value
        primary_metric         (str)     Name of primary objective metric
        optimization_direction (str)     'maximize' or 'minimize'
        message                (str)     Human-readable summary
        warnings               (list)    Non-critical warnings
        error                  (str)     Error message if success=False
    """
    warnings: List[str] = []

    # ----------------------------------------------------------------
    # 1. Validate inputs
    # ----------------------------------------------------------------
    valid_acq_functions = ["ei", "ucb", "pi", "random"]
    if acquisition_function not in valid_acq_functions:
        return {
            "success": False,
            "error": f"Invalid acquisition_function '{acquisition_function}'. "
                     f"Must be one of: {valid_acq_functions}",
            "warnings": warnings
        }

    # ----------------------------------------------------------------
    # 2. Load campaign state and observations
    # ----------------------------------------------------------------
    campaign_dir_abs = os.path.abspath(campaign_dir)

    if not os.path.isdir(campaign_dir_abs):
        return {
            "success": False,
            "error": f"Campaign directory not found: {campaign_dir_abs}",
            "warnings": warnings
        }

    try:
        state = load_campaign_state(campaign_dir_abs)
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"Campaign state not found. Run bo_initialize_campaign first.",
            "warnings": warnings
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load campaign state: {e}",
            "warnings": warnings
        }

    try:
        observations = load_observations(campaign_dir_abs)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load observations: {e}",
            "warnings": warnings
        }

    parameter_space = state["parameter_space"]
    objective_config = state["objective_config"]
    primary_metric = objective_config["metrics"][0]

    # Determine optimization direction
    direction = objective_config.get("direction", "maximize")
    if isinstance(direction, list):
        direction = direction[0]  # Use first metric's direction
    
    maximize = (direction == "maximize")

    # ----------------------------------------------------------------
    # 3. Check if we should use GP model or random sampling
    # ----------------------------------------------------------------
    n_observations = len(observations)
    initial_phase_complete = state.get("initial_phase_complete", False)
    
    # Use random sampling if still in initial phase or explicitly requested
    use_random = (not initial_phase_complete) or (acquisition_function == "random")

    if use_random:
        if acquisition_function == "random":
            warnings.append("Using random sampling as requested (no GP model)")
        else:
            warnings.append(
                f"Initial sampling phase ({n_observations}/{state['n_initial_random']} collected). "
                "Using random sampling; GP model will be used after initial phase."
            )
        
        # Generate random suggestions
        if random_seed is not None:
            np.random.seed(random_seed)
        
        suggestions = sample_random_parameters(parameter_space, n_samples=batch_size)
        
        return {
            "success": True,
            "campaign_dir": campaign_dir_abs,
            "n_suggestions": len(suggestions),
            "suggestions": suggestions,
            "acquisition_function": "random",
            "using_gp_model": False,
            "n_observations": n_observations,
            "primary_metric": primary_metric,
            "optimization_direction": direction,
            "message": f"Generated {len(suggestions)} random suggestions (initial sampling phase)",
            "warnings": warnings
        }

    # ----------------------------------------------------------------
    # 4. Prepare data for GP modeling
    # ----------------------------------------------------------------
    if n_observations < 2:
        return {
            "success": False,
            "error": f"Need at least 2 observations for GP modeling, have {n_observations}",
            "warnings": warnings
        }

    # Extract parameters and objective values
    X_list = []
    y_list = []
    
    for obs in observations:
        params = obs["parameters"]
        obs_values = obs["observations"]
        
        # Encode parameters to numerical array
        try:
            x_encoded = encode_parameters(params, parameter_space)
            X_list.append(x_encoded)
        except Exception as e:
            warnings.append(f"Failed to encode observation {obs.get('observation_id')}: {e}")
            continue
        
        # Extract primary objective value
        if primary_metric not in obs_values:
            warnings.append(
                f"Observation {obs.get('observation_id')} missing primary metric '{primary_metric}'"
            )
            continue
        
        y_value = obs_values[primary_metric]
        
        # If minimizing, negate the value (GP always maximizes)
        if not maximize:
            y_value = -y_value
        
        y_list.append(y_value)

    if len(X_list) == 0:
        return {
            "success": False,
            "error": "No valid observations for GP modeling",
            "warnings": warnings
        }

    X = np.array(X_list)
    y = np.array(y_list)

    # ----------------------------------------------------------------
    # 5. Fit Gaussian Process model
    # ----------------------------------------------------------------
    try:
        gp_model = fit_gp_model(X, y)
        gp_score = gp_model.score(X, y)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fit GP model: {e}",
            "warnings": warnings
        }

    if gp_score < 0:
        warnings.append(
            f"GP model has poor fit (R² = {gp_score:.3f}). "
            "Consider collecting more observations or checking data quality."
        )

    y_best = np.max(y)
    best_idx = np.argmax(y)
    best_obs = observations[best_idx]
    best_params = best_obs["parameters"]
    best_value_original = best_obs["observations"][primary_metric]

    # ----------------------------------------------------------------
    # 6. Generate candidate points
    # ----------------------------------------------------------------
    if random_seed is not None:
        np.random.seed(random_seed)

    # Generate random candidates in the parameter space
    candidate_params = sample_random_parameters(
        parameter_space,
        n_samples=n_candidates,
        seed=random_seed
    )

    # Encode candidates to numerical arrays
    X_candidates = np.array([
        encode_parameters(params, parameter_space)
        for params in candidate_params
    ])
    


    # ----------------------------------------------------------------
    # 7. Evaluate acquisition function
    # ----------------------------------------------------------------
    try:
        if acquisition_function == "ei":
            xi = exploration_weight
            acq_values = expected_improvement(X_candidates, gp_model, y_best, xi=xi)
        elif acquisition_function == "ucb":
            beta = exploration_weight if exploration_weight > 0.1 else 2.0
            acq_values = upper_confidence_bound(X_candidates, gp_model, beta=beta)
        elif acquisition_function == "pi":
            xi = exploration_weight
            acq_values = probability_of_improvement(X_candidates, gp_model, y_best, xi=xi)
        else:
            raise ValueError(f"Unknown acquisition function: {acquisition_function}")
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to compute acquisition function: {e}",
            "warnings": warnings
        }

    # ----------------------------------------------------------------
    # 8. Select suggestions (greedy batch selection)
    # ----------------------------------------------------------------
    suggestions = []
    selected_indices = []

    for i in range(batch_size):
        # Find best candidate not yet selected
        remaining_mask = np.ones(len(acq_values), dtype=bool)
        remaining_mask[selected_indices] = False
        
        if not np.any(remaining_mask):
            warnings.append(f"Only {i} unique suggestions found (requested {batch_size})")
            break
        
        remaining_acq = acq_values.copy()
        remaining_acq[~remaining_mask] = -np.inf
        
        best_idx = np.argmax(remaining_acq)
        selected_indices.append(best_idx)
        
        suggestion = candidate_params[best_idx]
        suggestions.append(suggestion)
        
        # For batch suggestions, update GP model with hypothetical observation
        # (assumes the suggestion will achieve the predicted mean)
        if i < batch_size - 1:
            x_new = X_candidates[best_idx:best_idx+1]
            mu_new, _ = gp_model.predict(x_new, return_std=True)
            
            # Augment training data
            X = np.vstack([X, x_new])
            y = np.append(y, mu_new[0])
            
            # Refit model
            try:
                gp_model = fit_gp_model(X, y)
            except:
                warnings.append("Failed to refit GP model for batch selection")
                break

    # ----------------------------------------------------------------
    # 9. Prepare response
    # ----------------------------------------------------------------
    message = (
        f"Generated {len(suggestions)} suggestion(s) using {acquisition_function.upper()} "
        f"acquisition (GP model trained on {n_observations} observations). "
        f"Best observed {primary_metric}: {best_value_original:.4f}"
    )

    return {
        "success": True,
        "campaign_dir": campaign_dir_abs,
        "n_suggestions": len(suggestions),
        "suggestions": suggestions,
        "acquisition_function": acquisition_function,
        "exploration_weight": exploration_weight,
        "using_gp_model": True,
        "n_observations": n_observations,
        "gp_model_score": float(gp_score),
        "best_observed_value": best_value_original,
        "best_observed_params": best_params,
        "primary_metric": primary_metric,
        "optimization_direction": direction,
        "message": message,
        "warnings": warnings
    }
