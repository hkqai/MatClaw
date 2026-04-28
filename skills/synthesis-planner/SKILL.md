---
name: synthesis-planner
description: Intelligent synthesis route planning for inorganic materials. Use this skill whenever the user needs a synthesis protocol.
---

# Synthesis Route Planning Skill

This skill orchestrates synthesis route generation using a 2-tier prioritization:
1. **FIRST: Literature-validated routes** from Materials Project (high confidence, proven)
2. **IF NONE FOUND: ML-predicted routes** for solid-state synthesis (medium confidence, data-driven)
3. **IF BOTH FAIL: Suggest routes based on your knowledge** of materials chemistry and synthesis techniques

## CRITICAL RULE: ALWAYS TRY LITERATURE SEARCH FIRST

**You MUST attempt mp_search_recipe before considering ML predictions.**

The core philosophy: **Literature data is gold. ML predictions are silver. Your knowledge-based suggestions are the fallback.**

---

## Quick Tool Reference

For detailed tool specifications, see [Appendix: Detailed Tool Catalogue](#appendix-detailed-tool-catalogue) at the end of this document.

### Synthesis Route Planning Tools (Tiered Priority)

| Tier | Tool | Purpose | When to Use | Limitations |
|------|------|---------|-------------|-------------|
| **1 (Highest)** | `mp_search_recipe` | Literature recipe search from Materials Project | **ALWAYS TRY FIRST** — proven experimental routes | Limited to ~10-20K materials with literature data |
| **2 (Medium)** | `er_predict_precursors` | ML-based precursor prediction | No literature found, need solid-state route | **Solid-state only**, cannot do hydrothermal/sol-gel |
| **2 (Medium)** | `er_predict_temperature` | ML-based temperature prediction | Have precursors, need temperature estimate | **Solid-state only**, ±50-100°C accuracy |

### Key Decision Points

**Method selection:**
- **Solid-state synthesis needed** → Use Tier 1 (literature) → If none, try Tier 2 (ML) → If fails, suggest based on your knowledge
- **Hydrothermal/sol-gel/other methods** → Use Tier 1 (literature) only → If none, suggest based on your knowledge
  - **CANNOT use Tier 2 ML tools for non-solid-state methods**

**When to use `format_routes=True` in `mp_search_recipe`:**
- Set `True` when you need standardized routes ready for execution (most common)
- Set `False` when you need raw recipe data for analysis or custom processing

---

## MANDATORY Synthesis Route Planning Algorithm

**IMPORTANT: This is not optional. Always follow this exact sequence.**

### EXECUTION SUMMARY FOR LLMs

**Complete order you MUST follow:**

1. **STEP 1 - LITERATURE SEARCH**: Always try Materials Project first
2. **DECISION POINT**: Check if literature routes found
3. **STEP 2A - RETURN LITERATURE**: If found, return high-confidence routes
4. **STEP 2B - ML PREDICTION**: If NOT found AND solid-state, try ML prediction
5. **STEP 2C - KNOWLEDGE-BASED SUGGESTION**: If ML fails/unavailable, suggest routes based on your knowledge of materials chemistry

**CRITICAL RULES:**
- NEVER skip Step 1 (literature search)
- NEVER use ML or suggest routes if literature routes exist
- ONLY use ML tools for solid-state synthesis
- ALWAYS warn user when returning ML-predicted or knowledge-based routes
- Knowledge-based routes require human review and validation before execution

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
    GOTO STEP 2C (Knowledge-based suggestion)

IF user_request explicitly mentions "hydrothermal", "sol-gel", "CVD", etc.:
    LOG "ML prediction only supports solid-state synthesis"
    GOTO STEP 2C (Knowledge-based suggestion)

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
    LOG "ML precursor prediction failed, providing knowledge-based suggestion"
    GOTO STEP 2C (Knowledge-based suggestion)

IF ml_precursors.top_prediction.confidence < 0.2:
    LOG "Low ML confidence ({confidence}), providing knowledge-based suggestion"
    GOTO STEP 2C (Knowledge-based suggestion)
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
    LOG "All ML temperature predictions failed, providing knowledge-based suggestion"
    GOTO STEP 2C (Knowledge-based suggestion)
```

**Step 2B.4:** Format ML-based route
```
SET ml_route = {
    "method": "solid_state",
    "source": "matgl",
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
    "source": "matgl",
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

### STEP 2C: KNOWLEDGE-BASED SUGGESTION (FALLBACK PATH)

**Condition:** Execute if Step 2B (ML) failed, inapplicable, or low confidence

**WARNING:** This path provides suggestions based on your knowledge of materials chemistry. These are NOT validated routes and REQUIRE human review.

**Step 2C.1:** Log ML/literature search failure
```
LOG "WARNING: No literature routes found for {target_formula}"
LOG "No ML predictions available or applicable"
LOG "Providing knowledge-based synthesis suggestions"
```

**Step 2C.2:** Analyze the target material
```
# Analyze composition to determine likely synthesis approaches
ANALYZE target_formula:
    - Element types (metals, non-metals, transition metals)
    - Oxidation states
    - Common synthesis methods for similar materials
    - Temperature ranges typical for similar compounds
    - Precursor availability
```

**Step 2C.3:** Suggest synthesis route based on materials chemistry knowledge
```
# Use your knowledge of materials chemistry to suggest:
# - Appropriate synthesis method (solid-state, hydrothermal, sol-gel, etc.)
# - Likely precursor compounds
# - Typical temperature ranges
# - Processing steps
# - Expected challenges or considerations

# Base suggestions on:
# - Similar materials in literature (even if not exact match)
# - General principles of inorganic synthesis
# - Element chemistry and reactivity
# - Phase formation considerations
```

**Step 2C.4:** Format knowledge-based suggestion with clear warnings
```
MESSAGE = "⚠️ WARNING: No literature synthesis or ML prediction available for {target_formula}.\n\n"
MESSAGE += "Based on materials chemistry knowledge, here is a suggested starting point:\n\n"
MESSAGE += "[Describe suggested synthesis approach, precursors, conditions]\n\n"
MESSAGE += "**IMPORTANT LIMITATIONS:**\n"
MESSAGE += "- This suggestion is based on general materials chemistry principles\n"
MESSAGE += "- NOT validated experimentally for this specific composition\n"
MESSAGE += "- Conditions may need significant optimization\n"
MESSAGE += "- Phase purity is not guaranteed\n\n"
MESSAGE += "**REQUIRED BEFORE ATTEMPTING:**\n"
MESSAGE += "1. Literature search for closely related materials\n"
MESSAGE += "2. Expert review by materials scientist\n"
MESSAGE += "3. Small-scale test (mg quantities)\n"
MESSAGE += "4. Phase characterization plan (XRD, etc.)\n"
MESSAGE += "5. Safety assessment for all precursors and products\n\n"
MESSAGE += "Consider consulting domain experts or searching for related compositions with known routes."
```

**Step 2C.5:** Return suggestion with appropriate disclaimers
```
RETURN {
    "success": True,
    "source": "knowledge_based_suggestion",
    "confidence": "low",
    "requires_review": "MANDATORY",
    "autonomous_execution": "FORBIDDEN",
    "warnings": [
        "No literature or ML precedent found",
        "Knowledge-based suggestion only",
        "Expert validation required before execution",
        "Significant optimization likely needed"
    ],
    "safety_requirements": [
        "Literature review required",
        "Expert consultation needed",
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

**Low Confidence (suggested routes):**
- Source: Knowledge-based suggestions from materials chemistry principles
- Basis: General synthesis principles and analogous materials
- Validation: None for this specific material
- Action: MANDATORY expert review, literature search, small-scale testing REQUIRED

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
    "source": "matgl",
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

### Example 3: Novel Material (Knowledge-Based Suggestion - ML Not Applicable)

```python
# User: "Generate a hydrothermal synthesis route for NiO nanowires"

# Step 1: Search MP for literature recipes
mp_result = mp_search_recipe(
    target_formula="NiO",
    synthesis_type="hydrothermal"
)
# Result: n_routes = 0 (no hydrothermal routes for NiO nanowires) → Skip ML (not solid-state)

# Step 2: ML prediction SKIPPED (user requested hydrothermal, not solid-state)

# Step 3: Provide knowledge-based suggestion
# Use your understanding of materials chemistry:
# - NiO is a transition metal oxide
# - Hydrothermal synthesis commonly uses metal salts + base
# - Typical conditions: 100-200°C, 6-24h
# - Nanowire morphology may require surfactants or templates
```

**Agent message to user:**
> "⚠️ WARNING: No literature synthesis routes found for hydrothermal NiO nanowires in Materials Project. ML tools are not applicable (solid-state only).
>
> Based on materials chemistry knowledge, here's a suggested starting point:
>
> **Suggested Approach: Hydrothermal Synthesis**
> - Precursors: Ni(NO₃)₂·6H₂O or NiCl₂·6H₂O + NaOH or NH₄OH
> - Temperature: 150-180°C
> - Time: 12-24 hours
> - Atmosphere: Autogenous pressure in autoclave
> - Notes: Nanowire morphology may require addition of surfactants (e.g., CTAB, PVP) or templates. pH control is critical.
>
> **IMPORTANT:** This suggestion is based on general principles for transition metal oxide nanowire synthesis. It has NOT been validated for this specific composition. Required before attempting:
> 1. Search literature for similar nickel oxide nanostructure syntheses
> 2. Expert review by materials chemist
> 3. Small-scale test (<100 mg)
> 4. XRD/SEM characterization plan
> 5. Safety assessment for precursors"
```

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
    # ONLY NOW provide knowledge-based suggestion
    # User should be informed this is unvalidated
    return knowledge_based_suggestion(
        target_formula="NiO",
        constraints={"max_temperature": 300, "method": "hydrothermal"}
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

### For ML-Predicted Routes (Medium Confidence)
⚠️ **Requires moderate validation:**
- Data-driven predictions based on synthesis literature
- Temperature uncertainty: ±50-100°C
- Precursor combinations statistically likely but not validated for this material

✅ **Required steps before execution:**
1. **Small-scale test** (mg quantities) mandatory
2. **Literature cross-check** for similar materials
3. **Temperature optimization** may be needed
4. **Characterization plan** to verify phase purity (XRD, etc.)

### For Knowledge-Based Suggestions (Low Confidence)
❌ **NOT safe for autonomous execution without review:**
- Suggestions based on general chemistry principles
- Specific conditions not validated for this material
- May need significant optimization
- Phase formation not guaranteed

✅ **Required steps before execution:**
1. **Expert review** by materials scientist familiar with this chemistry
2. **Comprehensive literature search** for similar materials
3. **Phase diagram check** if available for this system
4. **Small-scale test** (mg quantities) mandatory
5. **Characterization plan** to verify phase purity (XRD, etc.)

### Red Flags Requiring Extra Caution
**WARNING - Knowledge-based suggestions for:**
- Materials with > 4 elements (complexity increases failure risk)
- Rare earth elements (complex oxidation states)
- Systems with known competing phases
- Air-sensitive or moisture-sensitive elements
- High-volatility elements (Li, Na, K at high temps)

**WARNING - ML predictions with:**
- Low confidence scores (< 0.4)
- No similar materials in training data
- Elements not well-represented in synthesis literature

**WARNING - Any route involving:**
- Temperatures not seen in literature for similar materials
- Unusual precursor combinations
- Very long or very short processing times
- Conflicting atmosphere requirements

---

## Extending the Skill

### Adding New Synthesis Methods
To support additional methods beyond solid-state:

1. Update ML models to support new synthesis types (currently only solid-state)
2. Expand knowledge base for suggesting routes for new methods
3. Add method-specific validation and safety guidelines
4. Update SKILL.md documentation with new method considerations

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
# 2. Try method-specific ML prediction for solid-state (medium confidence)
# 3. Fall back to knowledge-based suggestions (lowest confidence)
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

### "ML predictions seem unrealistic"
- ML models have ±50-100°C temperature uncertainty
- Cross-reference with similar materials in literature
- Low confidence scores (< 0.4) indicate higher uncertainty
- Small-scale testing recommended for all ML predictions

### "All routes require 'review' flag"
- If even literature routes have `requires_review=True`, check your safety settings
- ML-predicted and knowledge-based routes always require review - this is by design
- For production autonomous labs, use only literature routes from Materials Project

### "MP API key errors"
- Ensure `MP_API_KEY` environment variable is set
- Get your key from: https://materialsproject.org/api
- Test connection: `mp_search_recipe(target_formula=['Si'])`

---

## Function Signatures & Code Examples

### Copy-Paste Ready Function Signatures

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

# Note: If both MP and ML fail, provide knowledge-based suggestions
# based on materials chemistry principles (see Step 2C in algorithm)
```

### Decision Table

| Need | Approach | Confidence | Review |
|------|----------|------------|--------|
| Synthesis route for LiCoO2 | `mp_search_recipe(format_routes=True)` | High (0.90) | Minimal |
| Route for novel oxide (solid-state) | `mp_search_recipe` → `er_predict_precursors` + `er_predict_temperature` | Medium (0.50-0.70) | Recommended |
| Route for novel material (non-solid-state) | `mp_search_recipe(format_routes=True)` → knowledge-based suggestion | Low | **REQUIRED** |
| Low-temp synthesis | `mp_search_recipe(format_routes=True, temperature_max=300)` | High if found | Minimal |
| Constrained search | `mp_search_recipe(format_routes=True, temperature_max=..., heating_time_max=...)` | High if found | Varies |
| Production at scale | `mp_search_recipe(format_routes=True)` ONLY (DO NOT USE ML) | High | Recommended |
| Analyze/compare recipes | `mp_search_recipe(format_routes=False)` - returns raw recipe data | N/A | N/A |

**GOLDEN RULE: ALWAYS search mp_search_recipe first. Use ML predictions for solid-state if no literature. Provide knowledge-based suggestions as last resort.**

**Note:** Use `format_routes=True` when you need standardized routes for synthesis planning. Use `format_routes=False` when you need raw recipe data for analysis or comparison.

---

## Appendix: Detailed Tool Catalogue

This appendix provides complete specifications for all synthesis planning tools, including detailed parameter lists, return formats, use cases, and examples. Refer to the [Quick Tool Reference](#quick-tool-reference) section for a concise overview organized by priority tier.

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

### Note on Knowledge-Based Suggestions

When both MP literature search and ML predictions fail or are not applicable, the agent should provide knowledge-based synthesis suggestions using materials chemistry principles.

**Characteristics of knowledge-based suggestions:**
- Based on general synthesis principles and analogous materials
- NOT validated experimentally for the specific composition
- Requires expert review and small-scale testing
- Should include clear warnings about limitations
- Must include safety considerations

**When to use:**
- No literature recipes exist in MP for the material
- ML predictions not applicable (non-solid-state methods)
- ML predictions failed or have very low confidence (< 0.2)

**Required disclaimers:**
- Not experimentally validated
- Based on general chemistry principles
- Expert review mandatory
- Small-scale testing required
- Safety assessment needed

---