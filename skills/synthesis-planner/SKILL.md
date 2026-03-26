---
name: synthesis-planner
description: Intelligent synthesis route planning for inorganic materials. ALWAYS tries literature search first via Materials Project, only falls back to template-based routes when no literature data exists. Use this skill whenever the user needs a synthesis protocol - it enforces literature-first methodology.
---

# Synthesis Route Planning Skill

This skill orchestrates synthesis route generation using a strict prioritization:
1. **FIRST: Literature-validated routes** from Materials Project (high confidence, proven)
2. **ONLY IF NONE FOUND: Template-based heuristic routes** (low confidence, requires validation)

## CRITICAL RULE: ALWAYS TRY LITERATURE SEARCH FIRST

**You MUST attempt mp_search_recipe before considering template_route_generator.**

The core philosophy: **Literature data is gold. Templates are last resort.**

---

## Tool Catalogue

### 1. `mp_search_recipe` — Literature Recipe Search
Queries Materials Project Synthesis Database for experimental synthesis procedures from published literature.

**Key parameters:**
- `target_formula`: Material composition (e.g., `'LiCoO2'`, `'BaTiO3'`)
- `synthesis_type`: Filter by method (`'solid-state'`, `'sol-gel'`, `'hydrothermal'`, etc.)
- `precursor_formula`: Find recipes using specific precursors
- `format_routes`: If `True`, automatically converts recipes to standardized routes (eliminates need for separate conversion step!)
- `limit`: Maximum number of recipes/routes to return (1-30, default 10). When `format_routes=True`, this controls the number of formatted routes returned.
- `temperature_min`, `temperature_max`, `heating_time_min`, `heating_time_max`: Filter recipes by min/max temperature/time directly in the search

**Returns (when format_routes=False):** 
```python
{
  "success": True,
  "count": 206,  # Number of literature recipes found
  "recipes": [
    {
      "target_formula": "LiCoO2",
      "precursors_formula_s": ["Li2CO3", "Co3O4"],
      "synthesis_type": "solid-state",
      "reaction_string": "0.333 Co3O4 + 0.5 Li2CO3 + 0.083 O2 == 1 LiCoO2 + 0.5 CO2",
      "operations": [
        {
          "type": "heating",
          "conditions": {"heating_temperature": [850], "heating_time": [12], "heating_atmosphere": ["air"]}
        }
      ]
    }
  ]
}
```

**Returns (when format_routes=True):**
```python
{
  "success": True,
  "target_composition": "LiCoO2",
  "n_routes": 5,
  "original_count": 206,  # Total recipes found before formatting
  "filtered_count": 0,  # Number filtered by constraints
  "routes": [
    {
      "route_id": 1,
      "source": "literature",
      "method": "solid_state",
      "confidence": 0.90,
      "precursors": [...],
      "steps": [
        {"step": 1, "action": "mix_and_grind", ...},
        {"step": 2, "action": "calcine", "temperature_c": 850, ...}
      ],
      "doi": "10.1234/example",
      "basis": "Literature-derived from Materials Project"
    }
  ]
}
```

**When to use `format_routes=True` vs `False`:**
- **Use `True`** when you need standardized synthesis routes ready for execution or planning (most common for synthesis planning)
- **Use `False`** when you need raw recipe data for analysis, comparison, or custom processing of literature information
- The `limit` parameter controls the number of recipes/routes returned (default 10, max 30)

**Coverage:** ~10-20K materials with literature synthesis data. Common battery materials, perovskites, and simple oxides are well-represented.

---

### 2. `template_route_generator` — Heuristic Route Generation
Generates template-based synthesis routes using Materials Project precursor data and heuristic process parameters.

**Key parameters:**
- `target_material`: `{'composition': 'LiCoO2'}`
- `synthesis_method`: `'solid_state'`, `'hydrothermal'`, `'sol_gel'`, or `'auto'`
- `constraints`: Optional limits (`max_temperature`, `max_time`, `exclude_precursors`, etc.)

**Returns:**
```python
{
  "success": True,
  "target_composition": "LiCoO2",
  "routes": [
    {
      "method": "solid_state",
      "source": "template_with_mp_precursors",
      "confidence": 0.40,  # Low - unvalidated heuristic
      "precursors": [...],  # From MP literature for this material
      "steps": [...],  # From heuristic templates
      "requires_review": True,  # Human approval needed
      "warnings": ["Using 206 recipes from Materials Project for precursor selection"]
    }
  ]
}
```

**Key characteristics:**
- Uses MP to find precursors actually used for this material in literature
- Applies template-based heuristics for temperatures/times/steps
- Lower confidence than literature routes
- Requires human review before autonomous execution

**When templates are used:**
- No literature recipes exist in MP for this material
- User explicitly requests template generation
- User provides constraints that filter out all literature routes

---

## MANDATORY Decision Logic Workflow

**IMPORTANT: This is not optional. Always follow this exact sequence:**

```
User Request: "Generate synthesis route for Material X"
    ↓
┌─────────────────────────────────────────────┐
│ STEP 1 (REQUIRED): mp_search_recipe()      │
│ Search Materials Project literature first   │
│ TIP: Set format_routes based on your need  │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ Found literature recipes?       │
│ (count > 0 or n_routes > 0)     │
└─────────────────────────────────┘
    │
    ├─→ YES: Literature Path (HIGH CONFIDENCE)
    │       ↓
    │   ┌──────────────────────────────────────────────┐
    │   │ Use format_routes=True in mp_search_recipe   │
    │   │   mp_search_recipe(                          │
    │   │       target_formula="NiO",                  │
    │   │       format_routes=True                     │
    │   │   )                                          │
    │   │ → Returns standardized routes directly       │
    │   │ → Single efficient step                      │
    │   └──────────────────────────────────────────────┘
    │       ↓
    │   ┌──────────────────────────────────────────────┐
    │   │ Return: Literature Routes                    │
    │   │ • Source: "literature"                       │
    │   │ • Confidence: 0.90 (high)                    │
    │   │ • Requires Review: Minimal                   │
    │   │ • Basis: "206 literature recipes"            │
    │   └──────────────────────────────────────────────┘
    │
    └─→ NO: Template Path (LOW CONFIDENCE - LAST RESORT)
            ↓
        ┌──────────────────────────────────────────────┐
        │ STEP 3 (FALLBACK ONLY):                     │
        │ template_route_generator()                   │
        │    - Query MP for precursors used            │
        │    - Apply heuristic temperature/time rules  │
        │    - Generate standardized steps             │
        │ WARNING: Only use if Step 1 returned 0 hits  │
        └──────────────────────────────────────────────┘
            ↓
        ┌──────────────────────────────────────────────┐
        │ Return: Template Routes + WARNINGS           │
        │ • Source: "template_with_mp_precursors"      │
        │ • Confidence: 0.40 (low)                     │
        │ • Requires Review: True                      │
        │ • Warning: "No literature precedent found"   │
        │ • Recommendation: "Validate before use"      │
        │                                              │
        │ INFORM USER: This is unvalidated, try        │
        │ literature search for similar materials      │
        └──────────────────────────────────────────────┘
```

---

## Usage Examples

### Example 1: Well-Studied Material (Literature Path)

```python
# User: "Generate a synthesis route for LiCoO2"

# Single-step approach with format_routes=True
routes_result = mp_search_recipe(
    target_formula="LiCoO2",
    format_routes=True,
    limit=5  # Controls number of routes returned
)
# Result: Directly returns standardized routes!
# {
#   "success": true,
#   "n_routes": 5,
#   "original_count": 206,
#   "routes": [...]  # Fully formatted routes
# }

# Return high-confidence literature routes
# routes_result["routes"][0]:
# {
#   "method": "solid_state",
#   "source": "literature",
#   "confidence": 0.90,
#   "precursors": [
#     {"compound": "Li2CO3", "amount": None, "form": "carbonate"},
#     {"compound": "Co3O4", "amount": None, "form": "oxide"}
#   ],
#   "steps": [
#     {"step": 1, "action": "MixingOperation", "description": "mix and grind"},
#     {"step": 2, "action": "HeatingOperation", "description": "calcine at 850°C for 12 h in air", 
#      "temperature_c": 850, "duration": 12, "atmosphere": "air"}
#   ],
#   "doi": "10.1234/example",
#   "basis": "Literature-derived from Materials Project"
# }
```

**Agent message to user:**
> "Found 206 literature synthesis recipes for LiCoO2 in Materials Project. Generated 5 validated routes based on actual experimental procedures. Recommended route uses Li2CO3 + Co3O4 precursors, calcination at 850°C for 12h in air. This is a well-established synthesis with high confidence (0.90)."

---

### Example 2: Novel Material (Template Path)

```python
# User: "Generate a synthesis route for Li0.7Na0.3Co0.95Ni0.05O2"

# Step 1: Search MP for literature recipes
mp_result = mp_search_recipe(
    target_formula=["Li0.7Na0.3Co0.95Ni0.05O2"]
)
# Result: count = 0 recipes (novel doped composition) → Template path

# Step 2: Fall back to template generator
template_result = template_route_generator(
    target_material={"composition": "Li0.7Na0.3Co0.95Ni0.05O2"},
    synthesis_method="auto"  # Will auto-select solid_state
)

# Step 3: Return low-confidence template routes with warnings
# template_result["routes"][0]:
# {
#   "method": "solid_state",
#   "source": "template_with_mp_precursors",
#   "confidence": 0.40,
#   "precursors": [
#     {"compound": "Li2CO3", "form": "carbonate"},  # From MP precursor data
#     {"compound": "Na2CO3", "form": "carbonate"},
#     {"compound": "Co3O4", "form": "oxide"},
#     {"compound": "NiO", "form": "oxide"}
#   ],
#   "steps": [
#     {"action": "mix_and_grind", "duration": "30 min"},
#     {"action": "calcine", "temperature_c": 850, "hold_time_h": 16, "atmosphere": "air"}
#   ],
#   "requires_review": True,
#   "warnings": [
#     "No literature precedent found for this composition",
#     "Template based on heuristics - validation required",
#     "Using precursor data from 150 similar lithium cobaltate recipes"
#   ]
# }
```

**Agent message to user:**
> "WARNING: No literature synthesis found for this novel composition. Generated template-based route using heuristics and precursor data from similar materials. **This route has NOT been validated experimentally** (confidence: 0.40) and requires expert review before execution. Recommended starting point: carbonate precursors, 850°C calcination. Consider testing on a small scale first."

---

### Example 3: Constrained Search

```python
# User: "I need a low-temperature synthesis route for NiO (max 300°C)"

# Single-step with constraints
routes = mp_search_recipe(
    target_formula="NiO",
    format_routes=True,
    temperature_max=300,  # Filter by max temperature in search
    keywords=["hydrothermal", "sol-gel"],  # Hint for low-temp methods
    limit=5  # Number of routes to return
)

if routes["success"] and routes["n_routes"] > 0:
    # SUCCESS: Return literature-validated low-temp routes
    return routes
else:
    # ONLY NOW fall back to template (user should be informed this is unvalidated)
    return template_route_generator(
        target_material={"composition": "NiO"},
        synthesis_method="hydrothermal",
        constraints={"max_temperature": 300}
    )
```

---

## Safety & Validation Guidelines

### For Literature Routes (High Confidence)
✅ **Generally safe for autonomous execution:**
- Routes are from published experimental procedures
- Conditions have been validated by the materials science community
- Precursors and temperatures are proven to work

⚠️ **Still recommend:**
- Small-scale test batch first
- Verify precursor availability and purity
- Check equipment compatibility (e.g., autoclave rating for hydrothermal)

### For Template Routes (Low Confidence)
❌ **NOT safe for autonomous execution without review:**
- Heuristic-based temperatures may be incorrect
- Precursor combinations may not react as expected
- May produce wrong phases or no reaction at all
- Chemical compatibility not verified

✅ **Required steps before execution:**
1. **Expert review** by materials scientist familiar with this chemistry
2. **Literature search** for similar materials to validate assumptions
3. **Phase diagram check** if available for this system
4. **Small-scale test** (mg quantities) before scaling up
5. **Characterization plan** to verify phase purity (XRD, etc.)

### Red Flags Requiring Extra Caution
**WARNING - Template routes for:**
- Materials with > 4 elements (complexity increases failure risk)
- Rare earth elements (complex oxidation states)
- Systems with known competing phases
- Air-sensitive or moisture-sensitive elements
- High-volatility elements (Li, Na, K at high temps)

**WARNING - Any route involving:**
- Temperatures not seen in literature for similar materials
- Unusual precursor combinations
- Very long or very short processing times
- Conflicting atmosphere requirements

---

## Extending the Skill

### Adding New Synthesis Methods
To support additional methods beyond solid-state/hydrothermal/sol-gel:

1. Add method logic to `template_route_generator`
2. Update `synthesis_method` parameter options
3. Add corresponding heuristics for temperature/time estimation
4. Document in this SKILL.md

### Integrating ML-Based Predictions
Future enhancement: ML model to predict synthesis conditions from composition

```python
# Hypothetical future tool
ml_result = synthesis_condition_predictor(
    target_formula="LiCoO2"
)
# Returns: predicted_temperature, predicted_precursors, confidence

# Skill orchestrates:
# 1. Try MP literature (highest confidence)
# 2. Try ML prediction (medium confidence)
# 3. Fall back to templates (lowest confidence)
```

### Connecting to Characterization
After generating routes, connect to validation:

```python
# Generate route
route = synthesis_route_planner(...)

# Execute synthesis (outside scope of this skill)
sample = execute_synthesis(route)

# Validate product
xrd_result = characterization_protocol_generator(
    sample=sample,
    target_composition=route["target_composition"],
    techniques=["XRD", "SEM"]
)
```

---

## Troubleshooting

### "No MP recipes found but I know they exist"
- Check formula formatting (use reduced formula: `LiCoO2` not `Li1Co1O2`)
- MP database may not have indexed all papers yet
- Try related compositions (e.g., search `LiCoO2` to inform `LiNiO2` synthesis)

### "Template generates unrealistic temperatures"
- Templates use heuristics that may not capture all edge cases
- Cross-reference with similar materials in literature
- Adjust using `constraints={'max_temperature': ...}` parameter
- This is expected behavior - templates are starting points, not gospel

### "All routes require 'review' flag"
- If even literature routes have `requires_review=True`, check your safety settings
- Template routes always require review - this is by design
- For production autonomous labs, implement automated safety checks

### "MP API key errors"
- Ensure `MP_API_KEY` environment variable is set
- Get your key from: https://materialsproject.org/api
- Test connection: `mp_search_recipe(target_formula=['Si'])`

---

## Quick Reference

### Function Signatures (Copy-Paste Ready)

```python
# 1a. Search Materials Project for standardized synthesis routes
routes = mp_search_recipe(
    target_formula="NiO",           # Required: material formula
    format_routes=True,             # Returns standardized routes ready for execution
    limit=10,                       # Optional: max routes to return (default 10)
    temperature_max=None,           # Optional: filter by max temp in search
    heating_time_max=None,          # Optional: filter by max time in search
    synthesis_type=None             # Optional: e.g., "solid-state"
)

# 1b. Search Materials Project for raw recipe data (for analysis/comparison)
recipes = mp_search_recipe(
    target_formula="NiO",           # Required: material formula
    format_routes=False,            # Returns raw recipe data from literature
    limit=10,                       # Optional: max recipes to return (default 10)
    temperature_max=None,           # Optional: filter by max temp in search
    synthesis_type=None             # Optional: e.g., "solid-state"
)

# 2. Generate template-based routes (FALLBACK ONLY)
template_routes = template_route_generator(
    target_material={"composition": "NiO"},
    synthesis_method="auto",        # Options: "solid_state", "hydrothermal", "sol_gel", "auto"
    constraints=None                # Optional: same as above
)
```

### Decision Table

| Need | Approach | Confidence | Review |
|------|----------|------------|--------|
| Synthesis route for LiCoO2 | `mp_search_recipe(format_routes=True)` | High (0.90) | Minimal |
| Route for novel composition | `mp_search_recipe(format_routes=True)` → if fails → `template_route_generator` | Low (0.40) if template | **REQUIRED** |
| Low-temp synthesis | `mp_search_recipe(format_routes=True, temperature_max=300)` | High if found | Minimal |
| Constrained search | `mp_search_recipe(format_routes=True, temperature_max=..., heating_time_max=...)` | High if found | Varies |
| Production at scale | `mp_search_recipe(format_routes=True)` ONLY (DO NOT USE TEMPLATES) | High | Recommended |
| Analyze/compare recipes | `mp_search_recipe(format_routes=False)` - returns raw recipe data | N/A | N/A |

**GOLDEN RULE: ALWAYS search mp_search_recipe first. Only use template_route_generator if no literature routes found.**

**Note:** Use `format_routes=True` when you need standardized routes for synthesis planning. Use `format_routes=False` when you need raw recipe data for analysis or comparison.

---