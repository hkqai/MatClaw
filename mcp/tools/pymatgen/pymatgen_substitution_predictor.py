"""
Tool for predicting likely element substitutions using ICSD data mining.
Uses pymatgen's SubstitutionPredictor which analyzes substitution patterns
from 100k+ ICSD structures to suggest chemically reasonable element replacements.
"""

from typing import Dict, Any, List, Optional, Annotated
from pydantic import Field


def pymatgen_substitution_predictor(
    composition: Annotated[
        str,
        Field(
            description="Chemical composition/formula to find substitutions for "
            "(e.g., 'La4WO9', 'LiFePO4', 'NaCl'). Can be reduced or full formula."
        )
    ],
    to_this_composition: Annotated[
        bool,
        Field(
            default=False,
            description="Direction of substitution prediction. "
            "If True: finds compositions that could transform INTO this composition. "
            "If False: finds compositions that this composition could transform INTO. "
            "Default: False (find what this can become)."
        )
    ] = False,
    threshold: Annotated[
        float,
        Field(
            default=0.001,
            ge=0.0,
            le=1.0,
            description="Probability threshold for including substitution suggestions (0.0-1.0). "
            "Lower values return more suggestions but with lower confidence. "
            "Typical values: 0.001 (permissive), 0.01 (moderate), 0.1 (strict). "
            "Default: 0.001."
        )
    ] = 0.001,
    alpha: Annotated[
        float,
        Field(
            default=-5.0,
            description="Weight parameter for never-observed substitutions. "
            "More negative = penalize unobserved substitutions more heavily. "
            "Default: -5.0 (standard pymatgen default)."
        )
    ] = -5.0,
    max_suggestions: Annotated[
        Optional[int],
        Field(
            default=None,
            ge=1,
            le=100,
            description="Maximum number of substitution suggestions to return (1-100). "
            "If None, returns all suggestions above threshold. "
            "Default: None (unlimited)."
        )
    ] = None,
    group_by_probability: Annotated[
        bool,
        Field(
            default=True,
            description="If True, groups results by probability tiers (high/medium/low). "
            "If False, returns flat list sorted by probability. "
            "Default: True."
        )
    ] = True
) -> Dict[str, Any]:
    """
    Predict likely element substitutions using ICSD-derived substitution probabilities.
    
    This tool uses data mining from the Inorganic Crystal Structure Database (ICSD)
    to identify which element substitutions are chemically reasonable based on
    historical occurrence patterns in real materials. Perfect for discovering
    compositional analogues (e.g., La4WO9 → Pr4MoO9) or dopant candidates.
    
    Based on: Hautier et al., Chem. Mater. 2010, 22, 3762-3767
    DOI: 10.1021/cm100795d
    
    Examples:
        # Find what La4WO9 could become
        >>> pymatgen_substitution_predictor("La4WO9", to_this_composition=False)
        # Returns: {"La": "Pr", "W": "Mo"}, {"La": "Ce", "W": "Mo"}, ...
        
        # Find what could become LiFePO4
        >>> pymatgen_substitution_predictor("LiFePO4", to_this_composition=True)
        # Returns: {"Na": "Li", "Mn": "Fe"}, {"K": "Li", "Co": "Fe"}, ...
    
    Returns:
        dict: Results containing:
            - success (bool): Whether prediction succeeded
            - composition (str): Input composition (reduced formula)
            - direction (str): "from" or "to" this composition
            - count (int): Number of suggestions found
            - suggestions (list or dict): Substitution predictions, format depends on group_by_probability:
                If grouped (default):
                    - high_probability (list): Suggestions with p > 0.1
                    - medium_probability (list): Suggestions with 0.01 < p ≤ 0.1
                    - low_probability (list): Suggestions with p ≤ 0.01
                If flat list:
                    - List of dicts, each containing:
                        - substitutions (dict): Element mapping (e.g., {"La": "Pr", "W": "Mo"})
                        - probability (float): Estimated probability (0-1)
                        - confidence (str): "high", "medium", or "low"
            - metadata (dict):
                - predictor_params (dict): threshold, alpha values used
                - data_source (str): "ICSD via pymatgen SubstitutionPredictor"
            - message (str): Success message
            - error (str): Error message if failed
    """
    
    try:
        # Import pymatgen components
        try:
            from pymatgen.core import Composition
            from pymatgen.analysis.structure_prediction.substitution_probability import (
                SubstitutionPredictor
            )
        except ImportError as e:
            return {
                "success": False,
                "error": f"Failed to import pymatgen: {str(e)}. Install with: pip install pymatgen"
            }
        
        # Parse composition and add oxidation states
        try:
            comp = Composition(composition)
            reduced_formula = comp.reduced_formula
            
            # SubstitutionPredictor requires oxidation states
            comp = comp.add_charges_from_oxi_state_guesses()
        except Exception as e:
            return {
                "success": False,
                "error": f"Invalid composition '{composition}': {str(e)}"
            }
        
        # Initialize predictor
        try:
            predictor = SubstitutionPredictor(
                lambda_table=None,  # Use default ICSD-derived table
                alpha=alpha,
                threshold=threshold
            )
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to initialize SubstitutionPredictor: {str(e)}"
            }
        
        # Get substitution predictions
        try:
            predictions = predictor.composition_prediction(
                composition=comp,
                to_this_composition=to_this_composition
            )
        except Exception as e:
            return {
                "success": False,
                "error": f"Prediction failed for '{reduced_formula}': {str(e)}"
            }
        
        # Process predictions
        if not predictions:
            return {
                "success": True,
                "composition": reduced_formula,
                "direction": "to" if to_this_composition else "from",
                "count": 0,
                "suggestions": [] if not group_by_probability else {
                    "high_probability": [],
                    "medium_probability": [],
                    "low_probability": []
                },
                "metadata": {
                    "predictor_params": {"threshold": threshold, "alpha": alpha},
                    "data_source": "ICSD via pymatgen SubstitutionPredictor"
                },
                "message": f"No substitution predictions found for {reduced_formula} above threshold {threshold}"
            }
        
        # Format predictions with probability estimates
        formatted_suggestions = []
        total_predictions = len(predictions)
        
        for idx, pred_dict in enumerate(predictions):
            # Extract probability (pymatgen provides this)
            probability = pred_dict.get('probability', 0.0)
            subs_dict = pred_dict.get('substitutions', {})
            
            # Convert Species objects to element symbol strings
            substitutions = {
                str(k.element): str(v.element) 
                for k, v in subs_dict.items()
            }
            
            # Assign confidence based on probability
            if probability > 0.1:
                confidence = "high"
            elif probability > 0.01:
                confidence = "medium"
            else:
                confidence = "low"
            
            suggestion = {
                "substitutions": substitutions,
                "probability": probability,
                "confidence": confidence,
                "rank": idx + 1
            }
            formatted_suggestions.append(suggestion)
            
            # Stop if we've reached max_suggestions
            if max_suggestions and len(formatted_suggestions) >= max_suggestions:
                break
        
        # Group by probability if requested
        if group_by_probability:
            grouped = {
                "high_probability": [s for s in formatted_suggestions if s["confidence"] == "high"],
                "medium_probability": [s for s in formatted_suggestions if s["confidence"] == "medium"],
                "low_probability": [s for s in formatted_suggestions if s["confidence"] == "low"]
            }
            suggestions_output = grouped
        else:
            suggestions_output = formatted_suggestions
        
        # Build result
        result = {
            "success": True,
            "composition": reduced_formula,
            "direction": "to" if to_this_composition else "from",
            "count": len(formatted_suggestions),
            "suggestions": suggestions_output,
            "metadata": {
                "predictor_params": {
                    "threshold": threshold,
                    "alpha": alpha,
                    "max_suggestions": max_suggestions
                },
                "data_source": "ICSD via pymatgen SubstitutionPredictor",
                "total_predictions_before_limit": total_predictions
            },
            "message": f"Found {len(formatted_suggestions)} substitution prediction(s) for {reduced_formula}"
        }
        
        return result
        
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import required module: {str(e)}. Install pymatgen: pip install pymatgen"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error during substitution prediction: {str(e)}",
            "error_type": type(e).__name__
        }
