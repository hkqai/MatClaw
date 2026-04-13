"""
Bayesian Optimization tools for generic experimental optimization.

This module provides domain-agnostic Bayesian Optimization tools that work with
any parameter types (continuous, discrete, categorical) and any measurement types
(XRD, SEM, electrochemical, mechanical, etc.).

Tools:
------
- bo_initialize_campaign: Set up a new BO campaign with parameter space definition
- bo_record_result: Record experimental results to the campaign database
- bo_suggest_experiment: Generate next experiment suggestions using GP model + acquisition

Key Features:
-------------
- Generic parameter space: continuous, discrete, and categorical parameters
- Generic objectives: any numerical measurements
- Multiple acquisition functions: EI, UCB, PI, random
- Batch suggestions: generate multiple experiments at once
- Robust validation: extensive input checking and error handling
- State persistence: all campaign data saved to JSON files

Example Workflow:
-----------------
1. Initialize campaign with parameter space and objectives
2. Perform initial random experiments and record results
3. Get BO suggestions for next experiments
4. Execute experiments and record results
5. Repeat steps 3-4 until optimization converges

Unlike domain-specific tools (e.g., ARROWS for synthesis), these tools make no
assumptions about the application domain and work for any optimization problem.
"""

from .bo_initialize_campaign import bo_initialize_campaign
from .bo_record_result import bo_record_result
from .bo_suggest_experiment import bo_suggest_experiment

__all__ = [
    "bo_initialize_campaign",
    "bo_record_result",
    "bo_suggest_experiment",
]
