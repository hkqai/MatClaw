# Selection Tools

Multi-objective ranking and candidate selection tools for high-throughput materials discovery.

## Tools

### `multi_objective_ranker`

Ranks material candidates based on multiple competing objectives to prioritize which candidates should proceed to expensive DFT simulations.

**Key Features:**
- **3 ranking strategies**: Pareto frontier, weighted sum, constraint-based
- **Automatic normalization**: Handles objectives with different scales
- **Diversity filtering**: Optional structural diversity constraints
- **Flexible input**: Works with any combination of objectives from analysis/ML tools

## Usage Examples

### Pareto Ranking (Non-dominated Sorting)

Find the Pareto frontier of materials optimizing multiple objectives:

```python
candidates = [
    {"id": "mat_001", "objectives": {"stability": -2.5, "band_gap": 1.8, "synthesizability": 0.9}},
    {"id": "mat_002", "objectives": {"stability": -1.8, "band_gap": 2.5, "synthesizability": 0.7}},
    # ... more candidates
]

objectives = {
    "stability": "minimize",        # Lower formation energy = better
    "band_gap": "maximize",         # Larger band gap = better
    "synthesizability": "maximize"  # Higher probability = better
}

result = multi_objective_ranker(
    candidates=candidates,
    objectives=objectives,
    strategy="pareto",
    top_k=50
)

# Result contains:
# - ranked_candidates: Top 50 non-dominated solutions
# - pareto_fronts: List of Pareto frontiers
# - statistics: Summary stats for each objective
```

### Weighted Sum

Combine multiple objectives with user-defined weights:

```python
result = multi_objective_ranker(
    candidates=candidates,
    objectives=objectives,
    strategy="weighted_sum",
    weights={
        "stability": 0.5,
        "band_gap": 0.3,
        "synthesizability": 0.2
    },
    top_k=20
)
```

### Constraint-Based

Apply hard constraints, then rank by primary objective:

```python
result = multi_objective_ranker(
    candidates=candidates,
    objectives=objectives,
    strategy="constraint",
    constraints={
        "synthesizability": {"min": 0.7},  # Must be synthesizable
        "stability": {"max": 0.0},         # Must be stable
        "band_gap": {"min": 1.5, "max": 3.0}  # Target range
    },
    primary_objective="band_gap",  # Rank feasible candidates by band gap
    top_k=30
)
```

## Integration with MatClaw Workflow

**Typical high-throughput pipeline:**

```
1. Generation (pymatgen tools)
   ↓
2. Analysis (structure_analyzer, composition_analyzer, stability_analyzer)
   ↓
3. ML Prediction (synthesizability, property predictions)
   ↓
4. Multi-Objective Ranking ← THIS TOOL
   ↓
5. DFT Simulation (VASP-ASE) - only top-k candidates
   ↓
6. Store Results (ASE database)
```

**Example workflow code:**

```python
# 1. Generate candidates
structures = pymatgen_substitution_generator(...)

# 2. Analyze each candidate
candidates = []
for struct in structures:
    # Get structural features
    struct_features = structure_analyzer(struct)
    
    # Get stability estimate
    stability = stability_analyzer(struct)
    
    # Get ML predictions
    synth_pred = predict_synthesizability(struct)
    
    candidates.append({
        "id": struct["id"],
        "structure": struct,
        "objectives": {
            "stability": stability["hull_distance"],
            "synthesizability": synth_pred["probability"],
            "volume": struct_features["volume"]
        }
    })

# 3. Rank candidates
ranked = multi_objective_ranker(
    candidates=candidates,
    objectives={
        "stability": "minimize",
        "synthesizability": "maximize",
        "volume": "minimize"
    },
    strategy="pareto",
    top_k=100
)

# 4. Simulate only top candidates
for candidate in ranked["ranked_candidates"][:20]:
    # Run expensive VASP calculation
    vasp_result = run_vasp_calculation(candidate["structure"])
    ase_store_result(vasp_result)
```

## Advanced Features

### Diversity Filtering

Ensure selected candidates are structurally diverse (requires `structure` field):

```python
result = multi_objective_ranker(
    candidates=candidates,
    objectives=objectives,
    strategy="pareto",
    diversity_filter=True,
    diversity_threshold=0.15,  # 15% minimum dissimilarity
    top_k=50
)
```

### Disable Normalization

For cases where objectives are already on comparable scales:

```python
result = multi_objective_ranker(
    candidates=candidates,
    objectives=objectives,
    strategy="weighted_sum",
    weights=weights,
    normalize_objectives=False  # Use raw values
)
```

## Output Format

```python
{
    "success": True,
    "strategy": "pareto",
    "total_candidates": 1000,
    "ranked_candidates": [
        {
            "id": "mat_001",
            "rank": 1,
            "score": 1.85,
            "pareto_front": 1,
            "objectives": {...},           # Normalized values
            "original_objectives": {...},  # Original values
            "structure": {...}
        },
        # ...
    ],
    "pareto_fronts": [...],  # Only for pareto strategy
    "statistics": {
        "count": 50,
        "objective_stats": {
            "stability": {"min": -3.2, "max": -1.5, "mean": -2.3, "median": -2.2},
            # ...
        }
    }
}
```

## Tips

1. **Strategy selection:**
   - Use `pareto` when you want to see trade-offs between objectives
   - Use `weighted_sum` when you have clear preferences
   - Use `constraint` when you have hard requirements

2. **Normalization:**
   - Enable (default) when objectives have different scales (e.g., energy in eV, volume in Ų, probabilities 0-1)
   - Constraints always checked against original values

3. **Top-k selection:**
   - Set `top_k` based on your computational budget
   - DFT simulations are expensive (~hours per structure)
   - Typically: 20-100 structures for initial screening

4. **Diversity:**
   - Use diversity filtering for exploration (find novel structures)
   - Skip for exploitation (find similar high-performers)
