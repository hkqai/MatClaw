"""
Bayesian Optimization campaign initialization tool.

This tool creates a new Bayesian Optimization campaign by defining the parameter
space, objectives, and initial sampling strategy. Unlike domain-specific tools
(e.g., ARROWS), this is completely generic and works with any optimization problem.

Usage examples:
- Materials synthesis optimization (temperature, pressure, precursors, etc.)
- Process parameter tuning (stirring speed, heating rate, atmosphere, etc.)
- Multi-characterization objectives (XRD purity, SEM morphology, electrochemical performance)
- Any experimental optimization with mixed parameter types
"""

from typing import Dict, Any, List, Optional, Annotated
from pydantic import Field
import os
import json
from datetime import datetime
from tools.bayesian_optimization._bo_utils import (
    validate_parameter_space,
    validate_objective_config,
    sample_random_parameters,
    save_campaign_state,
    save_observations
)


def bo_initialize_campaign(
    campaign_dir: Annotated[
        str,
        Field(
            description=(
                "Path to the campaign directory where BO state files will be saved. "
                "Directory will be created if it does not exist. "
                "Example: './campaigns/synthesis_optimization_run1'"
            )
        )
    ],
    parameter_space: Annotated[
        List[Dict[str, Any]],
        Field(
            description=(
                "List of parameter definitions. Each parameter must specify 'name' and 'type'. "
                "Supported types:\n"
                "  - 'continuous': requires 'bounds' [min, max], optional 'log_scale' (bool), 'unit'\n"
                "  - 'discrete': requires 'values' (list of allowed discrete values), optional 'unit'\n"
                "  - 'categorical': requires 'choices' (list of category names)\n\n"
                "Example:\n"
                "[\n"
                "  {'name': 'temperature', 'type': 'continuous', 'bounds': [400, 1200], 'unit': 'C'},\n"
                "  {'name': 'pressure', 'type': 'continuous', 'bounds': [0.1, 10], 'unit': 'atm'},\n"
                "  {'name': 'precursor_A', 'type': 'categorical', 'choices': ['Li2CO3', 'LiOH', 'Li2O']},\n"
                "  {'name': 'stirring_speed', 'type': 'discrete', 'values': [100, 200, 500, 1000], 'unit': 'rpm'},\n"
                "  {'name': 'composition_ratio', 'type': 'continuous', 'bounds': [0.1, 10], 'log_scale': True}\n"
                "]"
            )
        )
    ],
    objective_config: Annotated[
        Dict[str, Any],
        Field(
            description=(
                "Objective configuration specifying what to optimize. Required fields:\n"
                "  - 'type': 'single_objective' or 'multi_objective'\n"
                "  - 'metrics': list of metric names to optimize (must match observation keys)\n"
                "  - 'direction': 'maximize' or 'minimize' (or list for multi-objective)\n"
                "  - 'constraints': (optional) list of constraint specifications\n\n"
                "Single objective example:\n"
                "{\n"
                "  'type': 'single_objective',\n"
                "  'metrics': ['phase_purity'],\n"
                "  'direction': 'maximize'\n"
                "}\n\n"
                "Multi-objective example:\n"
                "{\n"
                "  'type': 'multi_objective',\n"
                "  'metrics': ['capacity', 'cycle_life'],\n"
                "  'direction': ['maximize', 'maximize']\n"
                "}"
            )
        )
    ],
    n_initial_random: Annotated[
        int,
        Field(
            default=5,
            ge=1,
            le=100,
            description=(
                "Number of initial random samples to suggest before starting Bayesian "
                "optimization. These provide diversity for fitting the initial GP model. "
                "Rule of thumb: 2-5 times the number of parameters. Default: 5."
            )
        )
    ] = 5,
    campaign_name: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "Optional human-readable campaign name for identification. "
                "If not provided, uses the campaign directory name."
            )
        )
    ] = None,
    metadata: Annotated[
        Optional[Dict[str, Any]],
        Field(
            default=None,
            description=(
                "Optional metadata to associate with the campaign "
                "(e.g., {'project': 'battery_optimization', 'operator': 'John Doe'})"
            )
        )
    ] = None,
    random_seed: Annotated[
        Optional[int],
        Field(
            default=None,
            description=(
                "Random seed for initial sampling reproducibility. "
                "If None, results will vary between runs."
            )
        )
    ] = None,
) -> Dict[str, Any]:
    """
    Initialize a new Bayesian Optimization campaign.

    Creates campaign directory structure and saves configuration. Generates initial
    random samples to bootstrap the optimization process.

    Returns
    -------
    dict:
        success              (bool)     Whether initialization succeeded
        campaign_dir         (str)      Absolute path to campaign directory
        campaign_name        (str)      Campaign name
        n_parameters         (int)      Number of parameters in the space
        parameter_names      (list)     List of parameter names
        objective_type       (str)      'single_objective' or 'multi_objective'
        objective_metrics    (list)     Metrics being optimized
        n_initial_random     (int)      Number of random samples to collect
        initial_suggestions  (list)     Initial random parameter suggestions
        created_at           (str)      Campaign creation timestamp
        state_file           (str)      Path to campaign state file
        observations_file    (str)      Path to observations file
        message              (str)      Human-readable summary
        warnings             (list)     Non-critical warnings
        error                (str)      Error message if success=False
    """
    warnings: List[str] = []

    # ----------------------------------------------------------------
    # 1. Validate inputs
    # ----------------------------------------------------------------
    valid, error = validate_parameter_space(parameter_space)
    if not valid:
        return {
            "success": False,
            "error": f"Invalid parameter_space: {error}",
            "warnings": warnings
        }

    valid, error = validate_objective_config(objective_config)
    if not valid:
        return {
            "success": False,
            "error": f"Invalid objective_config: {error}",
            "warnings": warnings
        }

    # ----------------------------------------------------------------
    # 2. Create campaign directory
    # ----------------------------------------------------------------
    campaign_dir_abs = os.path.abspath(campaign_dir)
    os.makedirs(campaign_dir_abs, exist_ok=True)

    # Check if campaign already exists
    state_file = os.path.join(campaign_dir_abs, "bo_state.json")
    if os.path.exists(state_file):
        warnings.append(
            f"Campaign directory already exists at {campaign_dir_abs}. "
            "Existing state will be overwritten."
        )

    # ----------------------------------------------------------------
    # 3. Generate initial random samples
    # ----------------------------------------------------------------
    try:
        initial_samples = sample_random_parameters(
            parameter_space,
            n_samples=n_initial_random,
            seed=random_seed
        )
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to generate initial random samples: {e}",
            "warnings": warnings
        }

    # ----------------------------------------------------------------
    # 4. Prepare campaign state
    # ----------------------------------------------------------------
    if campaign_name is None:
        campaign_name = os.path.basename(campaign_dir_abs)

    created_at = datetime.utcnow().isoformat()

    state = {
        "campaign_name": campaign_name,
        "created_at": created_at,
        "parameter_space": parameter_space,
        "objective_config": objective_config,
        "n_initial_random": n_initial_random,
        "random_seed": random_seed,
        "metadata": metadata or {},
        "status": "initialized",
        "n_observations": 0,
        "initial_phase_complete": False
    }

    # ----------------------------------------------------------------
    # 5. Save campaign state and initialize observations
    # ----------------------------------------------------------------
    try:
        save_campaign_state(campaign_dir_abs, state)
        save_observations(campaign_dir_abs, [])  # Empty observations list
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to save campaign files: {e}",
            "warnings": warnings
        }

    # ----------------------------------------------------------------
    # 6. Prepare response
    # ----------------------------------------------------------------
    param_names = [p["name"] for p in parameter_space]
    param_types = [p["type"] for p in parameter_space]

    n_continuous = sum(1 for t in param_types if t == "continuous")
    n_discrete = sum(1 for t in param_types if t == "discrete")
    n_categorical = sum(1 for t in param_types if t == "categorical")

    message = (
        f"Initialized Bayesian Optimization campaign '{campaign_name}' with "
        f"{len(parameter_space)} parameters "
        f"({n_continuous} continuous, {n_discrete} discrete, {n_categorical} categorical). "
        f"Optimizing {len(objective_config['metrics'])} metric(s). "
        f"Collect {n_initial_random} initial random samples to begin optimization."
    )

    return {
        "success": True,
        "campaign_dir": campaign_dir_abs,
        "campaign_name": campaign_name,
        "n_parameters": len(parameter_space),
        "parameter_names": param_names,
        "parameter_types_summary": {
            "continuous": n_continuous,
            "discrete": n_discrete,
            "categorical": n_categorical
        },
        "objective_type": objective_config["type"],
        "objective_metrics": objective_config["metrics"],
        "n_initial_random": n_initial_random,
        "initial_suggestions": initial_samples,
        "created_at": created_at,
        "state_file": state_file,
        "observations_file": os.path.join(campaign_dir_abs, "bo_observations.json"),
        "message": message,
        "warnings": warnings
    }
