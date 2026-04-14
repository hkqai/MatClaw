"""
Bayesian Optimization observation recording tool.

This tool records experimental results (parameter settings + measured outcomes) to
a BO campaign. It validates inputs against the campaign's parameter space and
objective configuration, then updates the observation database.

This is the feedback mechanism that enables the BO algorithm to learn and improve.
Works with any measurement types: XRD, SEM, TEM, electrochemical, mechanical, etc.
"""

from typing import Dict, Any, List, Optional, Annotated
from pydantic import Field
import os
from datetime import datetime
from tools.bayesian_optimization._bo_utils import (
    load_campaign_state,
    load_observations,
    save_observations,
    save_campaign_state
)


def bo_record_result(
    campaign_dir: Annotated[
        str,
        Field(
            description=(
                "Path to the campaign directory created by bo_initialize_campaign. "
                "Must contain bo_state.json and bo_observations.json."
            )
        )
    ],
    parameters: Annotated[
        Dict[str, Any],
        Field(
            description=(
                "Parameter values used in this experiment. Must match the parameter_space "
                "defined during campaign initialization.\n\n"
                "Example:\n"
                "{\n"
                "  'temperature': 850.0,\n"
                "  'pressure': 1.5,\n"
                "  'precursor_A': 'Li2CO3',\n"
                "  'stirring_speed': 500\n"
                "}"
            )
        )
    ],
    observations: Annotated[
        Dict[str, float],
        Field(
            description=(
                "Measured outcomes from the experiment. Keys should include the objective "
                "metrics defined in the campaign, plus any additional measurements.\n\n"
                "Example (XRD-based synthesis):\n"
                "{\n"
                "  'phase_purity': 0.92,        # Primary objective\n"
                "  'target_fraction': 0.85,     # Additional metric\n"
                "  'crystallinity': 0.78        # Additional metric\n"
                "}\n\n"
                "Example (electrochemical testing):\n"
                "{\n"
                "  'capacity_mAh_g': 145.3,     # Primary objective\n"
                "  'cycle_retention_100': 0.89, # Secondary objective\n"
                "  'coulombic_efficiency': 0.995\n"
                "}"
            )
        )
    ],
    metadata: Annotated[
        Optional[Dict[str, Any]],
        Field(
            default=None,
            description=(
                "Optional metadata associated with this experiment "
                "(e.g., file paths, timestamps, operator notes).\n\n"
                "Example:\n"
                "{\n"
                "  'xrd_file': '/data/xrd/sample_042.xy',\n"
                "  'sem_images': ['/data/sem/img1.png', '/data/sem/img2.png'],\n"
                "  'synthesis_date': '2026-04-13',\n"
                "  'operator': 'John Doe',\n"
                "  'notes': 'Sample showed good homogeneity'\n"
                "}"
            )
        )
    ] = None,
    observation_id: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "Optional unique identifier for this observation. "
                "If None, auto-generated as 'obs_{index}'."
            )
        )
    ] = None,
) -> Dict[str, Any]:
    """
    Record an experimental observation in a Bayesian Optimization campaign.

    Validates parameters and observations against campaign configuration, then
    appends to the observation database. Updates campaign state to track progress.

    Returns
    -------
    dict:
        success            (bool)    Whether recording succeeded
        campaign_dir       (str)     Absolute path to campaign directory
        observation_id     (str)     Unique ID for this observation
        n_observations     (int)     Total observations recorded so far
        initial_phase      (bool)    True if still collecting initial random samples
        parameters         (dict)    Recorded parameter values
        observations       (dict)    Recorded measurement values
        objective_value    (float)   Primary objective metric value
        recorded_at        (str)     Timestamp of recording
        message            (str)     Human-readable summary
        warnings           (list)    Non-critical warnings
        error              (str)     Error message if success=False
    """
    warnings: List[str] = []

    # ----------------------------------------------------------------
    # 1. Validate campaign directory and load state
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
            "error": (
                f"Campaign state not found in {campaign_dir_abs}. "
                "Run bo_initialize_campaign first."
            ),
            "warnings": warnings
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load campaign state: {e}",
            "warnings": warnings
        }

    parameter_space = state["parameter_space"]
    objective_config = state["objective_config"]

    # ----------------------------------------------------------------
    # 2. Validate parameters against parameter space
    # ----------------------------------------------------------------
    param_names = {p["name"] for p in parameter_space}
    provided_params = set(parameters.keys())

    missing_params = param_names - provided_params
    extra_params = provided_params - param_names

    if missing_params:
        return {
            "success": False,
            "error": f"Missing required parameters: {sorted(missing_params)}",
            "warnings": warnings
        }

    if extra_params:
        warnings.append(f"Unexpected parameters will be ignored: {sorted(extra_params)}")

    # Validate parameter values
    for param_def in parameter_space:
        name = param_def["name"]
        value = parameters[name]
        param_type = param_def["type"]

        if param_type == "continuous":
            if not isinstance(value, (int, float)):
                return {
                    "success": False,
                    "error": f"Parameter '{name}' must be numeric, got {type(value).__name__}",
                    "warnings": warnings
                }
            bounds = param_def["bounds"]
            if not (bounds[0] <= value <= bounds[1]):
                warnings.append(
                    f"Parameter '{name}' value {value} outside bounds {bounds}. "
                    "This may reduce model accuracy."
                )

        elif param_type == "discrete":
            allowed_values = param_def["values"]
            if value not in allowed_values:
                return {
                    "success": False,
                    "error": f"Parameter '{name}' value {value} not in allowed values: {allowed_values}",
                    "warnings": warnings
                }

        elif param_type == "categorical":
            allowed_choices = param_def["choices"]
            if value not in allowed_choices:
                return {
                    "success": False,
                    "error": f"Parameter '{name}' value '{value}' not in allowed choices: {allowed_choices}",
                    "warnings": warnings
                }

    # ----------------------------------------------------------------
    # 3. Validate observations against objective config
    # ----------------------------------------------------------------
    required_metrics = objective_config["metrics"]
    provided_metrics = set(observations.keys())

    missing_metrics = set(required_metrics) - provided_metrics
    if missing_metrics:
        return {
            "success": False,
            "error": f"Missing required objective metrics: {sorted(missing_metrics)}",
            "warnings": warnings
        }

    # Validate all observation values are numeric
    for metric_name, value in observations.items():
        if not isinstance(value, (int, float)):
            return {
                "success": False,
                "error": f"Observation '{metric_name}' must be numeric, got {type(value).__name__}",
                "warnings": warnings
            }

    # ----------------------------------------------------------------
    # 4. Load existing observations and create new record
    # ----------------------------------------------------------------
    try:
        existing_observations = load_observations(campaign_dir_abs)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load existing observations: {e}",
            "warnings": warnings
        }

    recorded_at = datetime.utcnow().isoformat()
    
    if observation_id is None:
        observation_id = f"obs_{len(existing_observations) + 1:04d}"

    # Check for duplicate observation ID
    existing_ids = {obs.get("observation_id") for obs in existing_observations}
    if observation_id in existing_ids:
        warnings.append(f"Observation ID '{observation_id}' already exists. Using anyway.")

    new_observation = {
        "observation_id": observation_id,
        "parameters": parameters,
        "observations": observations,
        "metadata": metadata or {},
        "recorded_at": recorded_at
    }

    existing_observations.append(new_observation)

    # ----------------------------------------------------------------
    # 5. Save updated observations and state
    # ----------------------------------------------------------------
    try:
        save_observations(campaign_dir_abs, existing_observations)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to save observations: {e}",
            "warnings": warnings
        }

    # Update campaign state
    n_observations = len(existing_observations)
    state["n_observations"] = n_observations
    
    # Check if initial random phase is complete
    if not state.get("initial_phase_complete", False):
        if n_observations >= state["n_initial_random"]:
            state["initial_phase_complete"] = True
            state["status"] = "optimizing"
        else:
            state["status"] = "initial_sampling"

    try:
        save_campaign_state(campaign_dir_abs, state)
    except Exception as e:
        warnings.append(f"Failed to update campaign state: {e}")

    # ----------------------------------------------------------------
    # 6. Prepare response
    # ----------------------------------------------------------------
    primary_metric = required_metrics[0]
    objective_value = observations[primary_metric]

    initial_phase = not state.get("initial_phase_complete", False)
    
    if initial_phase:
        remaining_initial = state["n_initial_random"] - n_observations
        message = (
            f"Recorded observation {observation_id} ({n_observations}/{state['n_initial_random']} "
            f"initial samples). {remaining_initial} more needed to start BO optimization."
        )
    else:
        message = (
            f"Recorded observation {observation_id} (total: {n_observations}). "
            f"Primary objective ({primary_metric}): {objective_value:.4f}"
        )

    return {
        "success": True,
        "campaign_dir": campaign_dir_abs,
        "observation_id": observation_id,
        "n_observations": n_observations,
        "initial_phase": initial_phase,
        "initial_phase_complete": state.get("initial_phase_complete", False),
        "parameters": parameters,
        "observations": observations,
        "objective_value": objective_value,
        "primary_metric": primary_metric,
        "recorded_at": recorded_at,
        "message": message,
        "warnings": warnings
    }
