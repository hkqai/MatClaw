---
name: synthesis-planner
description: Intelligent synthesis route planning for inorganic materials. ALWAYS tries literature search first via Materials Project, only falls back to template-based routes when no literature data exists. Use this skill whenever the user needs a synthesis protocol - it enforces literature-first methodology.
---

# Synthesis Route Planning Skill

This skill orchestrates synthesis route generation using a strict prioritization:
1. **FIRST: Literature-validated routes** from Materials Project (high confidence, proven)
2. **IF NONE FOUND: ML-predicted routes** for solid-state synthesis (medium confidence, data-driven)
3. **ONLY IF ML FAILS: Template-based heuristic routes** (low confidence, requires validation)

## CRITICAL RULE: ALWAYS TRY LITERATURE SEARCH FIRST

**You MUST attempt mp_search_recipe before considering ML predictions or template_route_generator.**

The core philosophy: **Literature data is gold. ML predictions are silver. Templates are last resort.**

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

### 2. `er_predict_precursors` — ML Precursor Prediction (Solid-State Only)
**NEW**: ML-based precursor prediction using trained neural networks on synthesis literature.

**CRITICAL LIMITATION: SOLID-STATE SYNTHESIS ONLY.** Cannot be used for hydrothermal, sol-gel, or other synthesis methods.

**Key parameters:**
- `target_formula`: Material composition (e.g., `'Li7La3Zr2O12'`, `'BaTiO3'`)
- `top_k`: Number of precursor sets to return (default 5, range 1-20)
- `return_individual`: If True, also return individual element predictions (not yet implemented)

**Returns:**
```python
{
  "target": "Li7La3Zr2O12",
  "precursor_sets": [
    {"precursors": ["Li2CO3", "La2O3", "ZrO2"], "confidence": 0.6121},
    {"precursors": ["Li2O", "La2O3", "ZrO2"], "confidence": 0.2341},
    {"precursors": ["LiOH", "La2O3", "ZrO2"], "confidence": 0.0892}
  ],
  "top_prediction": {"precursors": ["Li2CO3", "La2O3", "ZrO2"], "confidence": 0.6121},
  "metadata": {"model": "elemwise_retro", "device": "cpu"}
}
```

**Confidence interpretation:**
- **>0.5**: High confidence, precursors commonly used in literature
- **0.2-0.5**: Medium confidence, reasonable alternatives
- **<0.2**: Low confidence, less common combinations

**When to use:**
- No literature routes found in MP for this specific composition
- User requests solid-state synthesis specifically
- Target is inorganic oxide/oxysalt (model trained on these)

**When NOT to use:**
- Hydrothermal, sol-gel, CVD, or other non-solid-state methods
- Organic-inorganic hybrids or MOFs
- User explicitly requests literature-only routes

---

### 3. `er_predict_temperature` — ML Temperature Prediction (Solid-State Only)
**NEW**: ML-based synthesis temperature prediction given target and precursors.

**CRITICAL LIMITATION: SOLID-STATE SYNTHESIS ONLY.** Cannot be used for hydrothermal, sol-gel, or other synthesis methods.

**Key parameters:**
- `target_formula`: Material composition (e.g., `'Li7La3Zr2O12'`)
- `precursors`: List of precursor formulas (e.g., `['Li2CO3', 'La2O3', 'ZrO2']`)

**Returns:**
```python
{
  "target": "Li7La3Zr2O12",
  "precursors": ["Li2CO3", "La2O3", "ZrO2"],
  "temperature_celsius": 908.3,
  "temperature_kelvin": 1181.5,
  "metadata": {"model": "elemwise_retro", "device": "cpu"}
}
```

**Typical accuracy:**
- Mean absolute error: ±50-100°C on test set
- Use as starting point, not definitive temperature
- Cross-check with similar materials in literature

**When to use:**
- Have precursor set (from `er_predict_precursors` or other source)
- Need temperature estimate for solid-state synthesis
- No literature temperature data available

**When NOT to use:**
- Hydrothermal, sol-gel, CVD, or other non-solid-state methods
- Literature routes already provide temperature
- Precursors contain elements not in target (will raise error)

**Element validation:**
- Tool validates that precursor elements match target elements
- Raises `ValueError` if mismatch detected
- Ensures chemical consistency

---

### 4. `template_route_generator` — Heuristic Route Generation
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

## MANDATORY Synthesis Route Planning Algorithm

**IMPORTANT: This is not optional. Always follow this exact sequence.**

### EXECUTION SUMMARY FOR LLMs

**Complete order you MUST follow:**

1. **STEP 1 - LITERATURE SEARCH**: Always try Materials Project first
2. **DECISION POINT**: Check if literature routes found
3. **STEP 2A - RETURN LITERATURE**: If found, return high-confidence routes
4. **STEP 2B - ML PREDICTION**: If NOT found AND solid-state, try ML prediction
5. **STEP 2C - TEMPLATE FALLBACK**: If ML fails/unavailable, generate template routes with warnings

**CRITICAL RULES:**
- NEVER skip Step 1 (literature search)
- NEVER use ML/templates if literature routes exist
- ONLY use ML tools for solid-state synthesis
- ALWAYS warn user when returning ML or template routes
- Templates require human review before execution

---

### STEP 1: LITERATURE SEARCH (MANDATORY FIRST STEP)

**Input:** User request for synthesis route of material with formula X

**Step 1.1:** Determine user's need for output format
```
IF user needs standardized routes for synthesis planning:
    SET format_routes = True
ELSE IF user needs raw recipe data for analysis:
    SET format_routes = False
ELSE:
    # Default to standardized routes
    SET format_routes = True
```

**Step 1.2:** Extract any constraints from user request
```
SET constraints = {
    temperature_max: extract_from_request() OR None,
    heating_time_max: extract_from_request() OR None,
    synthesis_type: extract_from_request() OR None,
    keywords: extract_keywords() OR None
}
```

**Step 1.3:** Search Materials Project literature database
```
CALL mp_search_recipe(
    target_formula=X,
    format_routes=format_routes,
    limit=10,  # Or user-specified limit
    temperature_max=constraints.temperature_max,
    heating_time_max=constraints.heating_time_max,
    synthesis_type=constraints.synthesis_type
)

STORE result in mp_result
```

**Step 1.4:** Check search outcome
```
IF format_routes == True:
    SET found_routes = (mp_result.success AND mp_result.n_routes > 0)
ELSE:
    SET found_routes = (mp_result.success AND mp_result.count > 0)

IF found_routes:
    GOTO STEP 2A (Literature path)
ELSE:
    GOTO STEP 2B (ML prediction path)
```

---

### STEP 2A: RETURN LITERATURE ROUTES (HIGH CONFIDENCE PATH)

**Condition:** Only execute if Step 1.4 found literature routes

**Step 2A.1:** Extract route information
```
IF format_routes == True:
    SET routes = mp_result.routes
    SET route_count = mp_result.n_routes
    SET original_count = mp_result.original_count
ELSE:
    SET recipes = mp_result.recipes
    SET recipe_count = mp_result.count
```

**Step 2A.2:** Validate route quality
```
FOR each route in routes:
    # Routes from literature are high confidence
    ASSERT route.source == "literature"
    ASSERT route.confidence >= 0.85
    
    # Minimal review required
    SET route.requires_intensive_review = False
    SET route.autonomous_execution_approved = True  # With standard safety checks
```

**Step 2A.3:** Format user message
```
MESSAGE = "Found {original_count} literature synthesis recipes for {target_formula} in Materials Project. "
MESSAGE += "Generated {route_count} validated routes based on actual experimental procedures. "

# Describe recommended route
best_route = routes[0]
MESSAGE += f"Recommended route uses {format_precursors(best_route.precursors)}, "
MESSAGE += f"{best_route.steps[main_step].description}. "
MESSAGE += f"This is a well-established synthesis with high confidence ({best_route.confidence:.2f})."
```

**Step 2A.4:** Return result
```
RETURN {
    "success": True,
    "source": "literature",
    "confidence": "high",
    "routes": routes,
    "original_recipe_count": original_count,
    "route_count": route_count,
    "requires_review": "minimal",
    "autonomous_execution": "approved_with_safety_checks",
    "user_message": MESSAGE
}
```

---

### STEP 2B: ML PREDICTION PATH (MEDIUM CONFIDENCE - SOLID-STATE ONLY)

**Condition:** Only execute if Step 1.4 found NO literature routes

**IMPORTANT:** This path only works for SOLID-STATE synthesis. Skip to Step 2C for other methods.

**Step 2B.1:** Check if ML prediction is applicable
```
IF constraints.synthesis_type is specified AND constraints.synthesis_type != "solid-state":
    LOG "ML prediction not applicable for {constraints.synthesis_type}"
    GOTO STEP 2C (Template fallback)

IF user_request explicitly mentions "hydrothermal", "sol-gel", "CVD", etc.:
    LOG "ML prediction only supports solid-state synthesis"
    GOTO STEP 2C (Template fallback)

# Default assumption: solid-state for inorganic oxides
SET use_ml = True
```

**Step 2B.2:** Predict precursor sets using ML
```
TRY:
    CALL er_predict_precursors(
        target_formula=target_formula,
        top_k=5
    )
    STORE result in ml_precursors
EXCEPT Exception:
    LOG "ML precursor prediction failed, falling back to templates"
    GOTO STEP 2C (Template fallback)

IF ml_precursors.top_prediction.confidence < 0.2:
    LOG "Low ML confidence ({confidence}), falling back to templates"
    GOTO STEP 2C (Template fallback)
```

**Step 2B.3:** Predict synthesis temperature
```
FOR each precursor_set in ml_precursors.precursor_sets (top 3):
    TRY:
        CALL er_predict_temperature(
            target_formula=target_formula,
            precursors=precursor_set.precursors
        )
        STORE result in ml_temperature
        BREAK  # Success, use first valid prediction
    EXCEPT ValueError as e:
        LOG "Element mismatch for {precursor_set}: {e}"
        CONTINUE  # Try next precursor set
    EXCEPT Exception as e:
        LOG "Temperature prediction failed: {e}"
        CONTINUE

IF no valid ml_temperature:
    LOG "All ML temperature predictions failed, falling back to templates"
    GOTO STEP 2C (Template fallback)
```

**Step 2B.4:** Format ML-based route
```
SET ml_route = {
    "method": "solid_state",
    "source": "ml_prediction",
    "confidence": ml_precursors.top_prediction.confidence,  # 0.2-0.8 typical
    "precursors": [
        {"compound": prec, "form": infer_form(prec)}
        for prec in ml_precursors.top_prediction.precursors
    ],
    "steps": [
        {"step": 1, "action": "mix_and_grind", "description": "Mix precursors and grind"},
        {
            "step": 2,
            "action": "calcine",
            "description": f"Calcine at {ml_temperature.temperature_celsius}°C",
            "temperature_c": ml_temperature.temperature_celsius,
            "duration": infer_duration(ml_temperature.temperature_celsius),  # Heuristic: 8-16h
            "atmosphere": "air"  # Default for oxides
        }
    ],
    "requires_review": True,
    "ml_metadata": {
        "precursor_confidence": ml_precursors.top_prediction.confidence,
        "alternative_precursors": ml_precursors.precursor_sets[1:3],
        "temperature_uncertainty": "±50-100°C"
    },
    "warnings": [
        "ML-predicted route (not experimentally validated for this composition)",
        f"Precursor confidence: {ml_precursors.top_prediction.confidence:.2f}",
        "Temperature prediction has ±50-100°C uncertainty",
        "Small-scale test recommended before scale-up"
    ]
}
```

**Step 2B.5:** Format user message
```
MESSAGE = f"No literature synthesis found for {target_formula}. "
MESSAGE += f"Generated ML-predicted solid-state route using neural network trained on synthesis literature.\n\n"
MESSAGE += f"**Predicted precursors** (confidence: {ml_precursors.top_prediction.confidence:.2f}):\n"
for prec in ml_precursors.top_prediction.precursors:
    MESSAGE += f"  - {prec}\n"
MESSAGE += f"\n**Predicted temperature**: {ml_temperature.temperature_celsius}°C (±50-100°C uncertainty)\n\n"
MESSAGE += f"This is a data-driven prediction with medium confidence ({ml_route['confidence']:.2f}). "
MESSAGE += "Recommended to cross-check with similar materials in literature and test at small scale first.\n\n"
MESSAGE += "**Alternative precursor sets:**\n"
for i, alt in enumerate(ml_precursors.precursor_sets[1:3], 2):
    MESSAGE += f"  {i}. {alt['precursors']} (confidence: {alt['confidence']:.2f})\n"
```

**Step 2B.6:** Return ML-predicted route
```
RETURN {
    "success": True,
    "source": "ml_prediction",
    "confidence": "medium",
    "routes": [ml_route],
    "requires_review": "recommended",
    "autonomous_execution": "with_validation",
    "warnings": [
        "ML-predicted route, not experimentally validated",
        "Cross-reference with similar materials recommended",
        "Small-scale test advised"
    ],
    "user_message": MESSAGE
}
```

---

### STEP 2C: TEMPLATE FALLBACK (LOW CONFIDENCE PATH)

**Condition:** Execute if Step 2B (ML) failed, inapplicable, or low confidence

**WARNING:** This path generates unvalidated heuristic routes that REQUIRE human review

**Step 2C.1:** Log ML/literature search failure
```
LOG "WARNING: No literature routes found for {target_formula}"
LOG "Falling back to template-based generation (low confidence)"
```

**Step 2C.2:** Determine synthesis method
```
IF user specified method:
    SET method = user_specified_method
ELSE IF constraints.temperature_max < 400:
    SET method = "hydrothermal"  # Prefer low-temp method
ELSE:
    SET method = "auto"  # Let template generator decide
```

**Step 2C.3:** Generate template routes
```
CALL template_route_generator(
    target_material={"composition": target_formula},
    synthesis_method=method,
    constraints=constraints
)

STORE result in template_result
```

**Step 2C.4:** Validate template output and add warnings
```
FOR each route in template_result.routes:
    # Template routes are low confidence
    ASSERT route.source == "template_with_mp_precursors"
    ASSERT route.confidence <= 0.50
    
    # Add mandatory warnings
    IF route.warnings is None:
        SET route.warnings = []
    
    APPEND "No literature or ML precedent found for this composition" to route.warnings
    APPEND "Template based on heuristics - experimental validation required" to route.warnings
    APPEND "DO NOT execute without expert review" to route.warnings
    
    # Flag for mandatory review
    SET route.requires_review = True
    SET route.requires_expert_validation = True
    SET route.autonomous_execution_approved = False
```

**Step 2C.5:** Format user warning message
```
MESSAGE = "⚠️ WARNING: No literature synthesis or ML prediction succeeded for {target_formula}. "
MESSAGE += "Generated template-based route using heuristics and precursor data from similar materials. "
MESSAGE += "\n\n**This route has NOT been validated experimentally** "
MESSAGE += "(confidence: {route.confidence:.2f}) and requires expert review before execution.\n\n"
MESSAGE += "Recommended starting point: {format_precursors(route.precursors)}, "
MESSAGE += "{route.steps[main_step].description}.\n\n"
MESSAGE += "**SAFETY REQUIREMENTS:**\n"
MESSAGE += "1. Expert review by materials scientist\n"
MESSAGE += "2. Literature search for similar materials\n"
MESSAGE += "3. Small-scale test (mg quantities) first\n"
MESSAGE += "4. Phase characterization plan (XRD, etc.)\n\n"
MESSAGE += "Consider searching for related compositions with known synthesis routes."
```

**Step 2C.6:** Return result with warnings
```
RETURN {
    "success": True,
    "source": "template",
    "confidence": "low",
    "routes": template_result.routes,
    "requires_review": "MANDATORY",
    "autonomous_execution": "FORBIDDEN",
    "warnings": [
        "No literature or ML precedent found",
        "Template-based heuristics only",
        "Expert validation required before execution",
        "High risk of incorrect conditions or wrong phase"
    ],
    "safety_requirements": [
        "Expert review required",
        "Small-scale test mandatory",
        "Characterization plan needed"
    ],
    "user_message": MESSAGE
}
```

---

### ERROR HANDLING

**Error Type 1: MP API failure in Step 1**
```
IF mp_search_recipe fails with NetworkError:
    TRY:
        RETRY with exponential backoff (max 3 attempts)
    EXCEPT all retries failed:
        RETURN {
            "success": False,
            "error": "Materials Project API unavailable",
            "recommendation": "Try again later or use cached data if available"
        }
```

**Error Type 2: Invalid formula**
```
IF mp_search_recipe fails with FormulaError:
    RETURN {
        "success": False,
        "error": "Invalid chemical formula: {target_formula}",
        "recommendation": "Check formula formatting (e.g., 'LiCoO2' not 'Li1Co1O2')"
    }
```

**Error Type 3: Template generation failure**
```
IF template_route_generator fails:
    RETURN {
        "success": False,
        "error": "Cannot generate template route",
        "recommendation": "Search for similar materials with known synthesis or consult literature"
    }
```

---

### CONFIDENCE SCORING RULES

**High Confidence (0.85-1.0):**
- Source: Literature from Materials Project
- Basis: Published experimental procedures
- Validation: Peer-reviewed by community
- Action: Minimal review, approved for autonomous execution

**Medium Confidence (0.50-0.84):**
- Source: ML predictions (er_predict_precursors + er_predict_temperature)
- Basis: Data-driven models trained on synthesis literature
- Validation: Statistical validation on test set (±50-100°C temperature error)
- Action: Moderate review, small-scale test recommended
- **ONLY for solid-state synthesis**

**Low Confidence (0.0-0.49):**
- Source: Pure heuristic templates
- Basis: Generic rules not validated for this material
- Validation: None
- Action: MANDATORY expert review, small-scale testing REQUIRED

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

### Example 2: Novel Material (ML Prediction Path - Solid-State)

```python
# User: "Generate a solid-state synthesis route for Li7La3Zr2O12 (LLZO)"

# Step 1: Search MP for literature recipes
mp_result = mp_search_recipe(
    target_formula="Li7La3Zr2O12",
    format_routes=True
)
# Result: n_routes = 0 (novel composition) → Try ML prediction

# Step 2: ML precursor prediction
ml_precursors = er_predict_precursors(
    target_formula="Li7La3Zr2O12",
    top_k=5
)
# Result:
# {
#   "top_prediction": {"precursors": ["Li2CO3", "La2O3", "ZrO2"], "confidence": 0.6121},
#   "precursor_sets": [
#     {"precursors": ["Li2CO3", "La2O3", "ZrO2"], "confidence": 0.6121},
#     {"precursors": ["Li2O", "La2O3", "ZrO2"], "confidence": 0.2341},
#     ...
#   ]
# }

# Step 3: ML temperature prediction
ml_temperature = er_predict_temperature(
    target_formula="Li7La3Zr2O12",
    precursors=["Li2CO3", "La2O3", "ZrO2"]
)
# Result: {"temperature_celsius": 908.3, "temperature_kelvin": 1181.5}

# Step 4: Format ML-based route
ml_route = {
    "method": "solid_state",
    "source": "ml_prediction",
    "confidence": 0.61,
    "precursors": [
        {"compound": "Li2CO3", "form": "carbonate"},
        {"compound": "La2O3", "form": "oxide"},
        {"compound": "ZrO2", "form": "oxide"}
    ],
    "steps": [
        {"step": 1, "action": "mix_and_grind", "description": "Mix and grind precursors"},
        {
            "step": 2,
            "action": "calcine",
            "description": "Calcine at 908°C for 12h in air",
            "temperature_c": 908,
            "duration": 12,
            "atmosphere": "air"
        }
    ],
    "requires_review": True,
    "ml_metadata": {
        "precursor_confidence": 0.6121,
        "temperature_uncertainty": "±50-100°C"
    },
    "warnings": [
        "ML-predicted route (not experimentally validated)",
        "Precursor confidence: 0.61",
        "Temperature uncertainty: ±50-100°C"
    ]
}
```

**Agent message to user:**
> "No literature synthesis found for Li7La3Zr2O12. Generated ML-predicted solid-state route using neural network trained on synthesis literature.
>
> **Predicted precursors** (confidence: 0.61):
>   - Li2CO3
>   - La2O3
>   - ZrO2
>
> **Predicted temperature**: 908°C (±50-100°C uncertainty)
>
> This is a data-driven prediction with medium confidence (0.61). Recommended to cross-check with similar materials in literature and test at small scale first.
>
> **Alternative precursor sets:**
>   2. ['Li2O', 'La2O3', 'ZrO2'] (confidence: 0.23)
>   3. ['LiOH', 'La2O3', 'ZrO2'] (confidence: 0.09)"

---

### Example 3: Novel Material (Template Path - ML Not Applicable)

```python
# User: "Generate a hydrothermal synthesis route for NiO nanowires"

# Step 1: Search MP for literature recipes
mp_result = mp_search_recipe(
    target_formula="NiO",
    synthesis_type="hydrothermal"
)
# Result: n_routes = 0 (no hydrothermal routes for NiO nanowires) → Skip ML (not solid-state)

# Step 2: ML prediction SKIPPED (user requested hydrothermal, not solid-state)

# Step 3: Fall back to template generator
template_result = template_route_generator(
    target_material={"composition": "NiO"},
    synthesis_method="hydrothermal"
)

# Step 3: Return low-confidence template routes with warnings
# template_result["routes"][0]:
# {
#   "method": "hydrothermal",
#   "source": "template_with_mp_precursors",
#   "confidence": 0.35,
#   "precursors": [
#     {"compound": "Ni(NO3)2", "form": "nitrate"},  # From MP precursor data
#     {"compound": "NaOH", "form": "base"}
#   ],
#   "steps": [
#     {"action": "dissolve", "description": "Dissolve precursors in water"},
#     {"action": "autoclave", "temperature_c": 180, "hold_time_h": 12, "atmosphere": "autogenous"}
#   ],
#   "requires_review": True,
#   "warnings": [
#     "No literature or ML precedent found for hydrothermal NiO nanowires",
#     "Template based on heuristics - validation required",
#     "ML tools not applicable (hydrothermal synthesis)"
#   ]
# }
```

**Agent message to user:**
> "⚠️ WARNING: No literature synthesis or ML prediction succeeded for hydrothermal NiO nanowires. Generated template-based route using heuristics. **This route has NOT been validated experimentally** (confidence: 0.35) and requires expert review before execution. ML tools are not applicable for hydrothermal synthesis (solid-state only). Consider searching for related compositions."

---

### Example 4: Constrained Search

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

### Extending ML Predictions to Other Synthesis Methods
**Current limitation:** ML tools (`er_predict_precursors`, `er_predict_temperature`) only work for solid-state synthesis.

**Future enhancement:** Train models for other synthesis methods:

```python
# Hypothetical future tools
ml_hydrothermal = er_predict_hydrothermal_conditions(
    target_formula="NiO",
    morphology="nanowires"
)
# Returns: predicted_temperature, pH, time, surfactants

ml_solgel = er_predict_solgel_conditions(
    target_formula="BaTiO3"
)
# Returns: precursors, solvents, calcination_temp

# Skill orchestrates:
# 1. Try MP literature (highest confidence)
# 2. Try method-specific ML prediction (medium confidence)
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

# 2a. ML precursor prediction (SOLID-STATE ONLY)
ml_precursors = er_predict_precursors(
    target_formula="Li7La3Zr2O12",  # Required: material formula
    top_k=5,                        # Optional: number of precursor sets (default 5)
    return_individual=False         # Optional: individual element predictions (not implemented)
)

# 2b. ML temperature prediction (SOLID-STATE ONLY)
ml_temperature = er_predict_temperature(
    target_formula="Li7La3Zr2O12",  # Required: material formula
    precursors=["Li2CO3", "La2O3", "ZrO2"]  # Required: precursor list
)

# 3. Generate template-based routes (FALLBACK ONLY)
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
| Route for novel oxide (solid-state) | `mp_search_recipe` → `er_predict_precursors` + `er_predict_temperature` → `template_route_generator` | Medium (0.50-0.70) if ML | Recommended |
| Route for novel material (non-solid-state) | `mp_search_recipe(format_routes=True)` → `template_route_generator` (skip ML) | Low (0.40) | **REQUIRED** |
| Low-temp synthesis | `mp_search_recipe(format_routes=True, temperature_max=300)` | High if found | Minimal |
| Constrained search | `mp_search_recipe(format_routes=True, temperature_max=..., heating_time_max=...)` | High if found | Varies |
| Production at scale | `mp_search_recipe(format_routes=True)` ONLY (DO NOT USE ML/TEMPLATES) | High | Recommended |
| Analyze/compare recipes | `mp_search_recipe(format_routes=False)` - returns raw recipe data | N/A | N/A |

**GOLDEN RULE: ALWAYS search mp_search_recipe first. Use ML predictions for solid-state if no literature. Only use template_route_generator as last resort.**

**Note:** Use `format_routes=True` when you need standardized routes for synthesis planning. Use `format_routes=False` when you need raw recipe data for analysis or comparison.

---