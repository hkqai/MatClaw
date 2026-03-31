---
name: active-learning
description: Autonomous synthesis optimization using ARROWS active learning with automated XRD characterization. Orchestrates the complete loop from campaign setup through iterative experimentation to convergence.
---

# Active Learning Skill (ARROWS + XRD)

This skill orchestrates autonomous synthesis optimization using the ARROWS (Autonomous Rapid Reconfigurable Optimization Workshop for Synthesis) framework, enhanced with automated XRD phase identification.

**Complete autonomous loop:**
1. **Campaign setup** → Plan thermodynamically-guided experiments
2. **Suggest experiments** → Intelligently sample reaction space
3. **Characterize products** → Automated XRD phase identification
4. **Record results** → Update pairwise reaction knowledge
5. **Iterate** → Repeat until target synthesized or space explored

**Key advantage:** Closes the experimental → computational feedback loop with automated characterization, enabling truly autonomous materials optimization.

---

## Tool Catalogue

### Campaign Preparation Tools

#### `arrows_prepare_campaign` — Initialize Active Learning Campaign
Sets up ARROWS campaign directory with thermodynamic data and ranked precursor sets.

**Key parameters:**
- `target`: Target material formula (e.g., `'Ba2YCu3O7'`, `'LiCoO2'`)
- `precursors`: Available precursor chemicals (e.g., `['Y2O3', 'BaO', 'CuO', 'BaCO3']`)
- `temperatures`: Synthesis temperatures to explore (°C, e.g., `[600, 700, 800, 900]`)
- `campaign_dir`: Working directory for campaign state files
- `allow_oxidation`: Whether O₂ can participate as reactant (default `True`)
- `open_system`: Whether gases can escape (default `True`)

**Returns:**
```python
{
  "success": True,
  "campaign_dir": "./campaigns/Ba2YCu3O7_run1",
  "target": "Ba2YCu3O7",
  "num_precursor_sets": 24,
  "num_experiments": 96,  # Sets × temperatures
  "files_created": ["Settings.json", "Rxn_TD.csv"]
}
```

**What it does:**
- Queries Materials Project for thermodynamic data
- Enumerates all balanced precursor combinations
- Calculates ΔG for each reaction at each temperature
- Ranks sets by thermodynamic driving force
- Saves campaign state to disk

---

### Experiment Loop Tools

#### `arrows_suggest_experiment` — Get Next Experiment
Suggests the next experiment(s) based on thermodynamic favorability and learned pairwise reactions.

**Key parameters:**
- `campaign_dir`: Path to campaign initialized by `arrows_prepare_campaign`
- `batch_size`: Number of parallel experiments to suggest (1-50, default 1)
- `explore`: If `True`, prioritize information gain over thermodynamics (default `False`)
- `enforce_thermo`: If `True`, only use thermodynamically favorable pairwise reactions (default `False`)

**Returns:**
```python
{
  "success": True,
  "campaign_complete": False,
  "suggestions": [
    {
      "experiment_id": 1,
      "precursors": ["BaO", "Y2O3", "CuO"],
      "temperature_C": 700,
      "rationale": "Highest ΔG (most favorable), no prior data"
    }
  ],
  "experiments_remaining": 95
}
```

**Decision logic:**
- Ranks precursor sets by thermodynamic favorability
- Re-ranks using learned pairwise reaction knowledge (if available)
- Suggests untested (precursors, temperature) combinations
- Returns `campaign_complete=True` when search space exhausted

---

#### `xrd_analyze_pattern` — Automated Phase Identification
Analyzes experimental XRD pattern using CNN-based phase identification with automated Rietveld refinement.

**Key parameters:**
- `spectrum_path`: Path to .xy XRD pattern file
- `model_path`: Path to trained model (e.g., `'Models/'` or `'Model.h5'`)
- `min_confidence`: Confidence threshold for phase reporting (0-100%, default 40)
- `calculate_weights`: Whether to perform Rietveld refinement (default `True`)
- `wavelength`: X-ray wavelength in Å (default 1.5406 for Cu Kα)

**Returns:**
```python
{
  "success": True,
  "spectrum_file": "exp_001.xy",
  "num_phases": 2,
  "phases": ["BaTiO3_99", "BaO_225"],  # formula_spacegroup format
  "confidence": [85.3, 42.1],
  "weight_fractions": [0.92, 0.08],
  "arrows_ready": True,  # Can pass directly to arrows_record_result
  "unknown_peaks": {"present": False}
}
```

**CRITICAL:** Output format is designed for direct compatibility with `arrows_record_result`:
- `phases` → `products` parameter
- `weight_fractions` → `weight_fractions` parameter

---

#### `arrows_record_result` — Record Experimental Outcome
Updates campaign with experimental result, extracting pairwise reaction knowledge.

**Key parameters:**
- `campaign_dir`: Campaign directory
- `precursors`: Precursors used (must match suggestion)
- `temperature_C`: Synthesis temperature
- `products`: Observed phases in `formula_spacegroup` format (from XRD)
- `weight_fractions`: Weight fractions of products (from Rietveld)

**Returns:**
```python
{
  "success": True,
  "experiment_recorded": 1,
  "pairwise_reactions_learned": 3,
  "files_updated": ["Exp.json", "PairwiseRxns.csv"]
}
```

**What it does:**
- Stores experimental result in `Exp.json`
- Uses pairwise retroanalysis to infer reaction knowledge
- Updates `PairwiseRxns.csv` with learned reactions
- Enables subsequent suggestions to leverage new knowledge

---

### Results Analysis Tools

Tools for analyzing campaign outcomes and visualizing learned knowledge.

*(To be added: trajectory analysis, success metrics, knowledge visualization)*

---

## MANDATORY Active Learning Workflow

### WORKFLOW SUMMARY FOR LLMs

**Standard ARROWS loop (manual XRD analysis):**
```
1. arrows_prepare_campaign → campaign initialized
2. arrows_suggest_experiment → (precursors, temp)
3. [Robot synthesis]
4. [User analyzes XRD manually] → phases, weights
5. arrows_record_result → knowledge updated
6. Repeat 2-5 until campaign_complete
```

**Enhanced loop (automated XRD):**
```
1. arrows_prepare_campaign → campaign initialized
2. arrows_suggest_experiment → (precursors, temp)
3. [Robot synthesis]
4. xrd_analyze_pattern → phases, weights
5. arrows_record_result → knowledge updated
6. Repeat 2-5 until campaign_complete
```

**Key difference:** Step 4 is fully automated, enabling autonomous optimization.

---

### PHASE 0: CAMPAIGN INITIALIZATION

**Input:** User wants to optimize synthesis of material X

**Step 0.1:** Extract campaign parameters from user request
```
SET target = extract_target_formula(user_request)
SET precursors = extract_available_precursors(user_request)
SET temperatures = extract_temperature_range(user_request)
SET campaign_dir = generate_campaign_dir_name(target)

# Validate inputs
IF precursors is None OR len(precursors) < 2:
    ASK user for available precursor list
IF temperatures is None:
    # Reasonable defaults based on target class
    IF target is oxide:
        SET temperatures = [600, 700, 800, 900]
    ELSE IF target is nitride:
        SET temperatures = [700, 800, 900, 1000]
    ELSE:
        ASK user for temperature range
```

**Step 0.2:** Call campaign preparation
```
CALL arrows_prepare_campaign(
    target=target,
    precursors=precursors,
    temperatures=temperatures,
    campaign_dir=campaign_dir,
    allow_oxidation=True,      # Unless user specifies reducing atmosphere
    open_system=True            # Unless user specifies closed vessel
)

STORE result in campaign_result

IF NOT campaign_result.success:
    REPORT error to user
    STOP
```

**Step 0.3:** Report campaign scope
```
REPORT to user:
  - Target: {target}
  - Precursors: {precursors}
  - Temperatures: {temperatures}
  - Total experiments: {num_precursor_sets × len(temperatures)}
  - Campaign directory: {campaign_dir}
  - Status: "Ready for iterative optimization"
```

**Proceed to PHASE 1**

---

### PHASE 1: ITERATIVE EXPERIMENTATION

**This phase repeats until `campaign_complete=True` or user stops.**

**Step 1.1:** Request next experiment(s)
```
CALL arrows_suggest_experiment(
    campaign_dir=campaign_dir,
    batch_size=1,              # Or user-specified parallel capacity
    explore=False,             # Exploit by default (thermodynamics first)
    enforce_thermo=False       # Allow all learned reactions
)

STORE result in suggestion

IF suggestion.campaign_complete:
    GOTO PHASE 2 (Analysis)
```

**Step 1.2:** Communicate experiment to user/robot
```
FOR each experiment in suggestion.suggestions:
    REPORT to user:
      - Experiment ID: {experiment_id}
      - Mix precursors: {precursors} (ratios from Rxn_TD.csv)
      - Heat to: {temperature_C}°C
      - Rationale: {rationale}
      
    IF robot_available:
        DISPATCH_TO_ROBOT(experiment)
        WAIT for synthesis completion
    ELSE:
        ASK user to perform synthesis manually
        WAIT for user confirmation
```

**Step 1.3:** Automated XRD characterization
```
# User provides path to XRD pattern from synthesis
ASK user for XRD pattern file path OR 
    auto-detect if robot provides standard file name

SET xrd_file = get_xrd_file_path(experiment_id)

# Check if XRD model exists for this chemical space
IF NOT model_exists_for_chemistry(target, precursors):
    WARN user: "No pre-trained XRD model available for this chemistry. 
                Options:
                1. Manually analyze XRD and provide phases/weights
                2. Train new model using construct_xrd_model.py
                3. Use general model (may have lower accuracy)"
    
    IF user_chooses_manual:
        ASK user for phases and weight_fractions
        GOTO Step 1.4
    ELSE IF user_trains_model:
        PROVIDE instructions for model training
        WAIT for model training completion
        # Continue with automated analysis
    ELSE:
        # Attempt with general model, warn about uncertainty
        SET model_path = "general_oxides/Models/"
        WARN user: "Using general model - verify results carefully"

SET model_path = get_model_for_chemistry(target, precursors)

CALL xrd_analyze_pattern(
    spectrum_path=xrd_file,
    model_path=model_path,
    min_confidence=40.0,       # Recommended threshold from literature
    calculate_weights=True,    # Required for ARROWS
    wavelength=1.5406          # Cu Kα (or detect from metadata)
)

STORE result in xrd_result

IF NOT xrd_result.success:
    REPORT error to user
    ASK user for manual phase identification
    WAIT for manual input
    GOTO Step 1.4

# Validate XRD results
IF NOT xrd_result.arrows_ready:
    WARN user: "XRD analysis incomplete - missing weight fractions"
    IF xrd_result.phases exists:
        # Attempt manual Rietveld or ask user
        OFFER manual_rietveld_refinement
    ELSE:
        ASK user for manual phase/weight input
    GOTO Step 1.4

# Check for high-quality results
IF any confidence < 50:
    WARN user: "Low confidence phases detected - verify results:
                {list phases with confidence < 50}"
    ASK user: "Proceed with these results? (y/n)"
    IF user_says_no:
        ASK for manual correction
        GOTO Step 1.4

IF xrd_result.unknown_peaks.present:
    WARN user: "Unknown peaks detected ({max_intensity_pct}% intensity)
                - May indicate:
                  1. Phases not in training set
                  2. Novel phase formation
                  3. Amorphous content
                Recommendation: Manual verification"
```

**Step 1.4:** Record result in ARROWS
```
CALL arrows_record_result(
    campaign_dir=campaign_dir,
    precursors=experiment.precursors,
    temperature_C=experiment.temperature_C,
    products=xrd_result.phases,           # Direct from XRD
    weight_fractions=xrd_result.weight_fractions  # Direct from Rietveld
)

STORE result in record_result

IF record_result.success:
    REPORT to user:
      - Experiment {experiment_id} recorded
      - Products: {products}
      - Weights: {weight_fractions}
      - New pairwise reactions learned: {pairwise_reactions_learned}
ELSE:
    REPORT error and ask for correction
```

**Step 1.5:** Check convergence
```
IF target in xrd_result.phases:
    # Found target phase!
    SET target_purity = get_weight_fraction_of_target(xrd_result)
    
    REPORT to user:
      "🎯 TARGET SYNTHESIZED!
       Purity: {target_purity * 100}%
       Conditions: {precursors} at {temperature_C}°C"
    
    IF target_purity > 0.90:
        ASK user: "High purity achieved. Continue optimization or stop?"
        IF user_wants_stop:
            GOTO PHASE 2 (Analysis)
    ELSE:
        REPORT: "Target present but impure. Continuing optimization..."

# Check if campaign exhausted
IF suggestion.experiments_remaining == 0:
    REPORT: "All experiments completed. Target not synthesized."
    GOTO PHASE 2 (Analysis)

# Otherwise, continue loop
GOTO Step 1.1 (next iteration)
```

---

### PHASE 2: RESULTS ANALYSIS

**Once campaign completes or user stops:**

**Step 2.1:** Summarize campaign results
```
LOAD all experiments from Exp.json
LOAD all learned reactions from PairwiseRxns.csv

ANALYZE:
  - Total experiments run: {count}
  - Experiments where target appeared: {successful_count}
  - Best purity achieved: {max_purity}
  - Optimal conditions: {best_precursors} at {best_temperature}°C
  - Total pairwise reactions learned: {num_reactions}

REPORT summary to user
```

**Step 2.2:** Knowledge extraction
```
IDENTIFY promising pairwise reactions:
  - Reactions that consistently produce target
  - Reactions that reliably form intermediates
  - Reactions to avoid (produce undesired phases)

REPORT key learnings:
  - "Successful pathways: ..."
  - "Avoid combinations: ..."
  - "Recommended synthesis route: ..."
```

**Step 2.3:** Export results
```
OFFER to export:
  - Campaign summary report (JSON/PDF)
  - Learned reaction database (CSV)
  - Optimal synthesis protocol (text)
  - Visualization of search trajectory (plot)

IF user_wants_export:
    GENERATE requested outputs
```

---

## Common Patterns

### Pattern 1: Standard ARROWS Optimization Loop

**Use case:** User has robot synthesis + XRD characterization

```python
# Phase 0: Initialize
campaign = arrows_prepare_campaign(
    target="BaTiO3",
    precursors=["BaO", "BaCO3", "TiO2"],
    temperatures=[700, 800, 900],
    campaign_dir="./campaigns/BaTiO3_opt"
)

# Phase 1: Iterate until target found or campaign complete
while True:
    # Get next experiment
    suggestion = arrows_suggest_experiment(
        campaign_dir="./campaigns/BaTiO3_opt",
        batch_size=1
    )
    
    if suggestion['campaign_complete']:
        break
    
    experiment = suggestion['suggestions'][0]
    
    # Robot performs synthesis at experiment conditions
    robot.synthesize(
        precursors=experiment['precursors'],
        temperature=experiment['temperature_C']
    )
    
    # XRD measurement
    xrd_file = robot.collect_xrd()
    
    # Automated analysis
    xrd_result = xrd_analyze_pattern(
        spectrum_path=xrd_file,
        model_path="./models/Ba-Ti-O/Models/",
        calculate_weights=True
    )
    
    # Record in ARROWS
    arrows_record_result(
        campaign_dir="./campaigns/BaTiO3_opt",
        precursors=experiment['precursors'],
        temperature_C=experiment['temperature_C'],
        products=xrd_result['phases'],
        weight_fractions=xrd_result['weight_fractions']
    )
    
    # Check if target synthesized
    if "BaTiO3_99" in xrd_result['phases']:
        purity = xrd_result['weight_fractions'][
            xrd_result['phases'].index("BaTiO3_99")
        ]
        if purity > 0.9:
            print(f"✓ BaTiO3 synthesized at {purity*100}% purity!")
            break

# Phase 2: Analyze results
print(f"Campaign complete. Review {campaign_dir}/Exp.json for results.")
```

---

### Pattern 2: Batch Parallel Experiments

**Use case:** Robot can run multiple syntheses in parallel

```python
campaign = arrows_prepare_campaign(...)

while True:
    # Request 5 parallel experiments
    suggestion = arrows_suggest_experiment(
        campaign_dir="./campaigns/LiCoO2_opt",
        batch_size=5
    )
    
    if suggestion['campaign_complete']:
        break
    
    # Dispatch all to robot in parallel
    xrd_files = []
    for experiment in suggestion['suggestions']:
        xrd_file = robot.synthesize_parallel(
            precursors=experiment['precursors'],
            temperature=experiment['temperature_C']
        )
        xrd_files.append((experiment, xrd_file))
    
    # Wait for completion
    robot.wait_for_batch_completion()
    
    # Analyze and record all results
    for experiment, xrd_file in xrd_files:
        xrd_result = xrd_analyze_pattern(
            spectrum_path=xrd_file,
            model_path="./models/Li-Co-O/Models/"
        )
        
        arrows_record_result(
            campaign_dir="./campaigns/LiCoO2_opt",
            precursors=experiment['precursors'],
            temperature_C=experiment['temperature_C'],
            products=xrd_result['phases'],
            weight_fractions=xrd_result['weight_fractions']
        )
```

---

## Critical Decision Points

### DECISION 1: When to Use Exploration vs Exploitation

```
IF early in campaign (< 20% experiments done):
    # Exploit thermodynamics - find best conditions quickly
    SET explore = False
    
ELSE IF target not yet synthesized AND > 50% experiments done:
    # Switch to exploration - maybe we're missing something
    SET explore = True
    REPORT: "Switching to exploration mode - sampling diverse chemistry"
    
ELSE IF target synthesized at low purity:
    # Stay in exploit mode - refine around successful conditions
    SET explore = False
    # Could manually add constraints to search near success
```

---

### DECISION 2: Handling Low-Confidence XRD Results

```
IF max(xrd_result.confidence) < 50:
    OFFER options:
      1. Accept results anyway (not recommended)
      2. Re-measure XRD with better statistics
      3. Manual phase identification
      4. Skip this experiment (mark as "inconclusive")
      
RECOMMEND option 3 (manual verification) for critical experiments
RECOMMEND option 2 for early-campaign low-stakes experiments
```

---

### DECISION 3: XRD Model Selection

```
SET target_elements = extract_elements(target)
SET precursor_elements = extract_all_elements(precursors)
SET chemistry = normalize_composition_space(target_elements + precursor_elements)

IF model_exists_exact(chemistry):
    # Perfect match - use trained model
    SET model = load_model(chemistry)
    SET confidence_multiplier = 1.0
    
ELSE IF model_exists_superset(chemistry):
    # Trained on broader composition space that includes ours
    SET model = load_model(find_superset(chemistry))
    SET confidence_multiplier = 0.9
    WARN: "Using model trained on broader chemistry"
    
ELSE IF model_exists_similar(chemistry):
    # Similar elements (e.g., Li-Ni-O model for Li-Co-O)
    SET model = load_model(find_most_similar(chemistry))
    SET confidence_multiplier = 0.7
    WARN: "Using model for similar chemistry - verify results"
    
ELSE:
    # No suitable model exists
    OFFER:
      1. Train new model (requires CIF library + 4+ hours)
      2. Use general oxides model (low confidence)
      3. Manual XRD analysis
    
    IF user_chooses_train:
        PROVIDE model training instructions
    ELSE:
        FALL BACK to manual analysis workflow
```

---

## Integration with Other Skills

### with `synthesis-planner`

ARROWS optimizes *existing* syntheses. Use `synthesis-planner` to bootstrap:

```
1. synthesis-planner → literature route for target
2. Extract precursors and temperatures from route
3. arrows_prepare_campaign using those as starting point
4. ARROWS refines/optimizes from there
```

### with `candidate-screener`

Screen candidates before active learning:

```
1. candidate-generator → structure candidates
2. candidate-screener → filter by stability/bandgap/etc.
3. For top candidates: launch ARROWS campaigns
4. Parallel optimization of multiple targets
```

---

## XRD Model Management

### Model Requirements

Each chemical space needs a trained XRD model. Model training requires:

1. **CIF library**: All possible phases in composition space
2. **Computational resources**: ~4 hours for 255 phases (single core)
3. **Storage**: ~100 MB per model

### Common Pre-trained Models

*(To be built as use cases emerge)*

Suggested priority models:
- **Li-transition metal oxides** (Li-ion cathodes): Li-Mn-Ti-O-F, Li-Co-O, Li-Ni-Mn-Co-O
- **Perovskite oxides**: Ba-Ti-O, Ba-Sr-Ti-O, La-Sr-Mn-O
- **Simple binary oxides**: General model for common oxides

### Training New Models

When no suitable model exists:

```bash
# 1. Collect all relevant CIFs for composition space
mkdir Novel_Space/All_CIFs
# Add CIFs from Materials Project, ICSD, or computations

# 2. Navigate to training directory
cd Novel_Space/

# 3. Train model
python construct_xrd_model.py \
    --oxi_filter \              # Remove unusual oxidation states
    --min_angle=10.0 \
    --max_angle=80.0 \
    --max_strain=0.03 \         # Data augmentation bounds
    --num_epochs=50

# 4. Model.h5 will be created (use in xrd_analyze_pattern)
```

---

## Troubleshooting

### Issue 1: XRD analysis returns no phases

**Cause**: Spectrum quality too low, or phases not in training set

**Solution:**
1. Check XRD pattern quality (peak signal-to-noise ratio)
2. Verify model covers expected phases
3. Lower `min_confidence` threshold (with caution)
4. Manual analysis

### Issue 2: Target never synthesized despite thorough search

**Cause**: Target may not be thermodynamically accessible under conditions

**Solution:**
1. Review thermodynamic data: `Rxn_TD.csv` shows all precursor set ΔG values
2. Check if ΔG is positive for all sets (unfavorable)
3. Consider alternative precursors or synthesis methods
4. May need non-equilibrium synthesis (ARROWS assumes equilibrium)

### Issue 3: Pairwise reactions not being learned

**Cause**: Phase identification inconsistent or weight fractions unreliable

**Solution:**
1. Verify XRD confidence scores are high (> 60%)
2. Check Rietveld refinement quality
3. Ensure phases are correctly formatted (formula_spacegroup)
4. May need to manually verify critical experiments

---

## References

**ARROWS framework:**
- Paper: https://doi.org/10.1038/s41467-023-42329-9
- Code: https://github.com/njszym/ARROWS

**XRD-AutoAnalyzer:**
- XRD paper: https://doi.org/10.1021/acs.chemmater.1c01071
- PDF paper: https://doi.org/10.1038/s41524-024-01230-9
- Code: https://github.com/njszym/XRD-AutoAnalyzer

**Integration philosophy:**
Both tools developed by Nathan Szymanski - designed to work together for autonomous synthesis optimization.
