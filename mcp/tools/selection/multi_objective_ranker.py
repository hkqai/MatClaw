"""
Multi-objective ranking tool for materials candidate prioritization.

Ranks material candidates based on multiple objectives using various strategies:
- Pareto frontier analysis (non-dominated sorting)
- Weighted sum optimization
- Constraint-based filtering with secondary ranking
- Diversity-aware selection

Designed for high-throughput materials discovery workflows where candidates
must be prioritized before expensive DFT simulations.
"""

from typing import Dict, Any, List, Optional, Annotated, Literal, Tuple
from pydantic import Field
import math


def multi_objective_ranker(
    candidates: Annotated[
        List[Dict[str, Any]],
        Field(
            description=(
                "List of candidate materials to rank. Each candidate must have:\n"
                "- 'id': Unique identifier (str or int)\n"
                "- 'objectives': Dict mapping objective names to numeric scores\n"
                "- 'structure' (optional): Structure dict for diversity calculation\n"
                "Example: [{'id': 'mat_001', 'objectives': {'stability': -2.5, 'synthesizability': 0.8}}]"
            )
        )
    ],
    objectives: Annotated[
        Dict[str, str],
        Field(
            description=(
                "Optimization direction for each objective.\n"
                "Keys: objective names (must match keys in candidate objectives)\n"
                "Values: 'minimize' or 'maximize'\n"
                "Example: {'stability': 'minimize', 'synthesizability': 'maximize'}"
            )
        )
    ],
    strategy: Annotated[
        Literal["pareto", "weighted_sum", "constraint"],
        Field(
            default="pareto",
            description=(
                "Ranking strategy:\n"
                "- 'pareto': Non-dominated sorting (Pareto frontier)\n"
                "- 'weighted_sum': Scalarize objectives with weights\n"
                "- 'constraint': Apply hard constraints, then rank by primary objective"
            )
        )
    ] = "pareto",
    weights: Annotated[
        Optional[Dict[str, float]],
        Field(
            default=None,
            description=(
                "Weights for weighted_sum strategy. Must sum to 1.0.\n"
                "Example: {'stability': 0.6, 'synthesizability': 0.4}\n"
                "Required if strategy='weighted_sum', ignored otherwise."
            )
        )
    ] = None,
    constraints: Annotated[
        Optional[Dict[str, Dict[str, float]]],
        Field(
            default=None,
            description=(
                "Hard constraints for constraint strategy.\n"
                "Format: {'objective_name': {'min': value, 'max': value}}\n"
                "Example: {'synthesizability': {'min': 0.5}, 'stability': {'max': 0.0}}\n"
                "Used only if strategy='constraint'."
            )
        )
    ] = None,
    primary_objective: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "Primary objective for constraint strategy ranking.\n"
                "After filtering by constraints, candidates ranked by this objective.\n"
                "Required if strategy='constraint'."
            )
        )
    ] = None,
    top_k: Annotated[
        int,
        Field(
            default=100,
            ge=1,
            description="Maximum number of top-ranked candidates to return. Default: 100"
        )
    ] = 100,
    diversity_filter: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, apply diversity filtering to avoid selecting similar structures.\n"
                "Requires 'structure' key in candidates for fingerprint comparison.\n"
                "Default: False"
            )
        )
    ] = False,
    diversity_threshold: Annotated[
        float,
        Field(
            default=0.1,
            ge=0.0,
            le=1.0,
            description=(
                "Minimum structural dissimilarity (0-1) required between selected candidates.\n"
                "Higher values = more diverse selection. Only used if diversity_filter=True.\n"
                "Default: 0.1"
            )
        )
    ] = 0.1,
    normalize_objectives: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True, normalize all objectives to [0, 1] before ranking.\n"
                "Recommended for weighted_sum strategy. Default: True"
            )
        )
    ] = True,
) -> Dict[str, Any]:
    """
    Rank material candidates using multi-objective optimization strategies.
    
    This tool prioritizes candidates for downstream simulation or synthesis based
    on multiple competing objectives (e.g., stability, synthesizability, performance).
    Essential for high-throughput workflows where only top candidates can be simulated.
    
    Returns
    -------
    {
        "success": bool,
        "strategy": str,
        "total_candidates": int,
        "ranked_candidates": List[Dict],  # Top-k candidates with ranking metadata
        "pareto_fronts": Optional[List[List]],  # Only for pareto strategy
        "statistics": Dict,  # Summary statistics
        "error": Optional[str]
    }
    
    Each ranked candidate includes:
        - All original fields (id, objectives, structure, etc.)
        - "rank": Final rank (1 = best)
        - "score": Computed score (strategy-dependent)
        - "pareto_rank": Pareto front number (pareto strategy only)
        - "dominated_by": Count of candidates that dominate this one
    """
    
    # Validation
    if not candidates:
        return {
            "success": False,
            "error": "candidates list cannot be empty.",
            "strategy": strategy,
        }
    
    # Validate candidate structure
    for i, candidate in enumerate(candidates):
        if "id" not in candidate:
            return {
                "success": False,
                "error": f"Candidate at index {i} missing required 'id' field.",
                "strategy": strategy,
            }
        if "objectives" not in candidate:
            return {
                "success": False,
                "error": f"Candidate '{candidate.get('id')}' missing 'objectives' field.",
                "strategy": strategy,
            }
        if not isinstance(candidate["objectives"], dict):
            return {
                "success": False,
                "error": f"Candidate '{candidate['id']}' objectives must be a dict.",
                "strategy": strategy,
            }
    
    # Validate objectives
    if not objectives:
        return {
            "success": False,
            "error": "objectives dict cannot be empty.",
            "strategy": strategy,
        }
    
    for obj_name, direction in objectives.items():
        if direction not in ["minimize", "maximize"]:
            return {
                "success": False,
                "error": f"Objective '{obj_name}' direction must be 'minimize' or 'maximize', got '{direction}'.",
                "strategy": strategy,
            }
    
    # Check that all candidates have all objectives
    for candidate in candidates:
        for obj_name in objectives.keys():
            if obj_name not in candidate["objectives"]:
                return {
                    "success": False,
                    "error": f"Candidate '{candidate['id']}' missing objective '{obj_name}'.",
                    "strategy": strategy,
                }
            value = candidate["objectives"][obj_name]
            if not isinstance(value, (int, float)) or math.isnan(value):
                return {
                    "success": False,
                    "error": f"Candidate '{candidate['id']}' objective '{obj_name}' has invalid value: {value}",
                    "strategy": strategy,
                }
    
    # Strategy-specific validation
    if strategy == "weighted_sum":
        if weights is None:
            return {
                "success": False,
                "error": "weights parameter required for weighted_sum strategy.",
                "strategy": strategy,
            }
        if set(weights.keys()) != set(objectives.keys()):
            return {
                "success": False,
                "error": f"weights keys {set(weights.keys())} must match objectives keys {set(objectives.keys())}.",
                "strategy": strategy,
            }
        weight_sum = sum(weights.values())
        if not (0.99 <= weight_sum <= 1.01):  # Allow small floating point errors
            return {
                "success": False,
                "error": f"weights must sum to 1.0, got {weight_sum}.",
                "strategy": strategy,
            }
    
    if strategy == "constraint":
        if primary_objective is None:
            return {
                "success": False,
                "error": "primary_objective required for constraint strategy.",
                "strategy": strategy,
            }
        if primary_objective not in objectives:
            return {
                "success": False,
                "error": f"primary_objective '{primary_objective}' not in objectives.",
                "strategy": strategy,
            }
        if constraints:
            for obj_name in constraints.keys():
                if obj_name not in objectives:
                    return {
                        "success": False,
                        "error": f"Constraint objective '{obj_name}' not in objectives.",
                        "strategy": strategy,
                    }
    
    # Normalize objectives if requested
    working_candidates = [c.copy() for c in candidates]
    obj_ranges = {}
    
    if normalize_objectives:
        for obj_name in objectives.keys():
            values = [c["objectives"][obj_name] for c in working_candidates]
            min_val = min(values)
            max_val = max(values)
            obj_ranges[obj_name] = {"min": min_val, "max": max_val, "range": max_val - min_val}
            
            # Normalize to [0, 1]
            if max_val > min_val:
                for candidate in working_candidates:
                    original = candidate["objectives"][obj_name]
                    normalized = (original - min_val) / (max_val - min_val)
                    if "original_objectives" not in candidate:
                        candidate["original_objectives"] = candidate["objectives"].copy()
                    candidate["objectives"][obj_name] = normalized
            # If all values are the same, leave as-is (already normalized)
    
    # Apply ranking strategy
    try:
        if strategy == "pareto":
            result = _rank_pareto(working_candidates, objectives, top_k)
        elif strategy == "weighted_sum":
            result = _rank_weighted_sum(working_candidates, objectives, weights, top_k)
        elif strategy == "constraint":
            result = _rank_constraint(working_candidates, objectives, constraints, primary_objective, top_k)
        else:
            return {
                "success": False,
                "error": f"Unknown strategy: {strategy}",
                "strategy": strategy,
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error during ranking: {str(e)}",
            "strategy": strategy,
        }
    
    # Apply diversity filtering if requested
    if diversity_filter and result["success"]:
        try:
            result["ranked_candidates"] = _apply_diversity_filter(
                result["ranked_candidates"],
                diversity_threshold,
                top_k
            )
            result["diversity_filtered"] = True
            result["diversity_threshold"] = diversity_threshold
        except Exception as e:
            result["diversity_filter_error"] = str(e)
            result["diversity_filtered"] = False
    
    # Add statistics
    if result["success"] and result.get("ranked_candidates"):
        result["statistics"] = _compute_statistics(result["ranked_candidates"], objectives)
    
    result["normalize_objectives"] = normalize_objectives
    if normalize_objectives:
        result["objective_ranges"] = obj_ranges
    
    return result


def _rank_pareto(
    candidates: List[Dict[str, Any]],
    objectives: Dict[str, str],
    top_k: int
) -> Dict[str, Any]:
    """Rank candidates using Pareto dominance (non-dominated sorting)."""
    
    # Calculate domination relationships
    n = len(candidates)
    domination_counts = [0] * n  # How many candidates dominate this one
    dominated_by = [[] for _ in range(n)]  # Which candidates this one dominates
    
    for i in range(n):
        for j in range(i + 1, n):
            dominance = _check_dominance(
                candidates[i]["objectives"],
                candidates[j]["objectives"],
                objectives
            )
            if dominance == 1:  # i dominates j
                dominated_by[i].append(j)
                domination_counts[j] += 1
            elif dominance == -1:  # j dominates i
                dominated_by[j].append(i)
                domination_counts[i] += 1
    
    # Non-dominated sorting
    pareto_fronts = []
    remaining = set(range(n))
    
    while remaining:
        # Find non-dominated candidates in remaining set
        current_front = [i for i in remaining if domination_counts[i] == 0]
        if not current_front:
            # Shouldn't happen, but handle cycle
            current_front = list(remaining)
        
        pareto_fronts.append(current_front)
        remaining -= set(current_front)
        
        # Update domination counts for next iteration
        for i in current_front:
            for j in dominated_by[i]:
                if j in remaining:
                    domination_counts[j] -= 1
    
    # Assign ranks and scores
    ranked = []
    rank = 1
    for front_idx, front in enumerate(pareto_fronts):
        for candidate_idx in front:
            candidate = candidates[candidate_idx].copy()
            candidate["rank"] = rank
            candidate["pareto_front"] = front_idx + 1
            candidate["score"] = -front_idx  # Higher front = lower score
            candidate["dominated_count"] = sum(1 for j in range(n) if candidate_idx in dominated_by[j])
            ranked.append(candidate)
            rank += 1
        
        if len(ranked) >= top_k:
            break
    
    return {
        "success": True,
        "strategy": "pareto",
        "total_candidates": len(candidates),
        "ranked_candidates": ranked[:top_k],
        "pareto_fronts": [[candidates[i]["id"] for i in front] for front in pareto_fronts],
        "num_fronts": len(pareto_fronts),
    }


def _rank_weighted_sum(
    candidates: List[Dict[str, Any]],
    objectives: Dict[str, str],
    weights: Dict[str, float],
    top_k: int
) -> Dict[str, Any]:
    """Rank candidates using weighted sum scalarization."""
    
    scored_candidates = []
    
    for candidate in candidates:
        score = 0.0
        for obj_name, direction in objectives.items():
            value = candidate["objectives"][obj_name]
            weight = weights[obj_name]
            
            # For minimization, negate the value (so lower is better becomes higher is better)
            if direction == "minimize":
                score -= value * weight
            else:
                score += value * weight
        
        scored_candidate = candidate.copy()
        scored_candidate["score"] = score
        scored_candidates.append(scored_candidate)
    
    # Sort by score (higher is better)
    scored_candidates.sort(key=lambda x: x["score"], reverse=True)
    
    # Assign ranks
    for rank, candidate in enumerate(scored_candidates, start=1):
        candidate["rank"] = rank
    
    return {
        "success": True,
        "strategy": "weighted_sum",
        "total_candidates": len(candidates),
        "ranked_candidates": scored_candidates[:top_k],
        "weights_used": weights,
    }


def _rank_constraint(
    candidates: List[Dict[str, Any]],
    objectives: Dict[str, str],
    constraints: Optional[Dict[str, Dict[str, float]]],
    primary_objective: str,
    top_k: int
) -> Dict[str, Any]:
    """Rank candidates by applying constraints then sorting by primary objective."""
    
    # Filter by constraints
    feasible = []
    infeasible = []
    
    for candidate in candidates:
        is_feasible = True
        violated_constraints = []
        
        if constraints:
            # Use original objectives for constraint checking if normalization was applied
            obj_dict = candidate.get("original_objectives", candidate["objectives"])
            
            for obj_name, bounds in constraints.items():
                value = obj_dict[obj_name]
                
                if "min" in bounds and value < bounds["min"]:
                    is_feasible = False
                    violated_constraints.append(f"{obj_name} < {bounds['min']} (got {value:.4f})")
                
                if "max" in bounds and value > bounds["max"]:
                    is_feasible = False
                    violated_constraints.append(f"{obj_name} > {bounds['max']} (got {value:.4f})")
        
        candidate_copy = candidate.copy()
        if is_feasible:
            feasible.append(candidate_copy)
        else:
            candidate_copy["violated_constraints"] = violated_constraints
            infeasible.append(candidate_copy)
    
    if not feasible:
        return {
            "success": False,
            "strategy": "constraint",
            "total_candidates": len(candidates),
            "feasible_count": 0,
            "infeasible_count": len(infeasible),
            "error": "No candidates satisfy the constraints.",
            "sample_violations": infeasible[:5],
        }
    
    # Sort feasible candidates by primary objective
    direction = objectives[primary_objective]
    reverse = (direction == "maximize")
    feasible.sort(key=lambda x: x["objectives"][primary_objective], reverse=reverse)
    
    # Assign ranks and scores
    for rank, candidate in enumerate(feasible, start=1):
        candidate["rank"] = rank
        candidate["score"] = candidate["objectives"][primary_objective]
        if direction == "minimize":
            candidate["score"] = -candidate["score"]  # Negate so higher rank = better
    
    return {
        "success": True,
        "strategy": "constraint",
        "total_candidates": len(candidates),
        "feasible_count": len(feasible),
        "infeasible_count": len(infeasible),
        "ranked_candidates": feasible[:top_k],
        "constraints_used": constraints,
        "primary_objective": primary_objective,
    }


def _check_dominance(
    obj_a: Dict[str, float],
    obj_b: Dict[str, float],
    objectives: Dict[str, str]
) -> int:
    """
    Check if obj_a dominates obj_b.
    
    Returns:
        1 if a dominates b
        -1 if b dominates a
        0 if neither dominates (incomparable)
    """
    a_better = False
    b_better = False
    
    for obj_name, direction in objectives.items():
        val_a = obj_a[obj_name]
        val_b = obj_b[obj_name]
        
        if direction == "minimize":
            if val_a < val_b:
                a_better = True
            elif val_b < val_a:
                b_better = True
        else:  # maximize
            if val_a > val_b:
                a_better = True
            elif val_b < val_a:
                b_better = True
    
    if a_better and not b_better:
        return 1
    elif b_better and not a_better:
        return -1
    else:
        return 0


def _apply_diversity_filter(
    ranked_candidates: List[Dict[str, Any]],
    threshold: float,
    top_k: int
) -> List[Dict[str, Any]]:
    """
    Filter candidates to ensure structural diversity.
    
    Uses greedy selection: iteratively select highest-ranked candidate
    that is sufficiently different from all previously selected.
    """
    if not ranked_candidates:
        return []
    
    # Check if structures are available
    if "structure" not in ranked_candidates[0]:
        raise ValueError("Diversity filtering requires 'structure' field in candidates")
    
    selected = []
    
    for candidate in ranked_candidates:
        if not selected:
            # Always take the top candidate
            selected.append(candidate)
            continue
        
        # Check dissimilarity with all selected candidates
        is_diverse = True
        for selected_candidate in selected:
            similarity = _compute_structure_similarity(
                candidate.get("structure"),
                selected_candidate.get("structure")
            )
            if similarity > (1.0 - threshold):  # If too similar
                is_diverse = False
                break
        
        if is_diverse:
            selected.append(candidate)
        
        if len(selected) >= top_k:
            break
    
    return selected


def _compute_structure_similarity(struct_a: Any, struct_b: Any) -> float:
    """
    Compute structural similarity between two structures.
    
    Placeholder implementation - in practice, would use structure fingerprints.
    Returns value in [0, 1] where 0 = completely different, 1 = identical.
    """
    # TODO: Integrate with structure_fingerprinter tool for real similarity
    # For now, return 0 (assume all structures are different)
    # This prevents diversity filtering from being too aggressive
    
    if struct_a is None or struct_b is None:
        return 0.0
    
    # Simple placeholder: compare composition if available
    try:
        if isinstance(struct_a, dict) and isinstance(struct_b, dict):
            # Check if they have the same composition
            comp_a = struct_a.get("@class")
            comp_b = struct_b.get("@class")
            if comp_a == comp_b:
                return 0.5  # Same type, might be similar
        return 0.0
    except:
        return 0.0


def _compute_statistics(
    ranked_candidates: List[Dict[str, Any]],
    objectives: Dict[str, str]
) -> Dict[str, Any]:
    """Compute summary statistics for ranked candidates."""
    
    if not ranked_candidates:
        return {}
    
    stats = {
        "count": len(ranked_candidates),
        "objective_stats": {}
    }
    
    # Get objective key (either original or normalized)
    obj_key = "original_objectives" if "original_objectives" in ranked_candidates[0] else "objectives"
    
    for obj_name in objectives.keys():
        values = [c[obj_key][obj_name] for c in ranked_candidates]
        stats["objective_stats"][obj_name] = {
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
            "median": sorted(values)[len(values) // 2],
        }
    
    # Score statistics
    if "score" in ranked_candidates[0]:
        scores = [c["score"] for c in ranked_candidates]
        stats["score_range"] = {
            "min": min(scores),
            "max": max(scores),
            "mean": sum(scores) / len(scores),
        }
    
    return stats
