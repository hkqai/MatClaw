---
name: active-learning
description: Autonomous optimization using ARROWS (thermodynamically-guided synthesis) or Bayesian Optimization (generic process optimization). Orchestrates closed-loop experimentation from campaign setup through iterative learning to convergence.
---

# Active Learning Skill

This skill orchestrates autonomous optimization for materials discovery and process optimization using two complementary approaches:

1. **ARROWS** — Domain-specific synthesis optimization using thermodynamic guidance and pairwise reaction learning
2. **Bayesian Optimization** — Generic optimization framework for any multi-parameter process

**Complete autonomous loop:**
1. **Campaign setup** → Define parameter space and objectives
2. **Suggest experiments** → Intelligently sample parameter space
3. **Execute & characterize** → Run experiments and collect measurements
4. **Record results** → Update surrogate model or knowledge base
5. **Iterate** → Repeat until objective achieved or space explored

**Key advantage:** Closes the experimental → computational feedback loop with automated decision-making, enabling truly autonomous materials optimization.

---

## When to Use ARROWS vs Bayesian Optimization

### Use ARROWS When:
✅ **Optimizing solid-state synthesis routes** (ceramic, oxide, chalcogenide materials)  
✅ **Target phase is known** (e.g., "synthesize high-purity BaTiO₃")  
✅ **Precursors are well-defined chemicals** (oxides, carbonates, hydroxides, etc.)  
✅ **Thermodynamic data is available** (Materials Project has entries for target and precursors)  
✅ **XRD characterization** is your primary measurement technique  
✅ **You want to learn generalizable chemistry knowledge** (pairwise reaction rules)

**ARROWS strengths:**
- Leverages thermodynamic driving force to guide search
- Learns transferable reaction knowledge across experiments
- Efficient for high-dimensional synthesis spaces (many precursors)
- Automatically enumerates balanced chemical reactions
- Integrates with automated XRD phase identification

**ARROWS limitations:**
- Specific to equilibrium synthesis (solid-state reactions)
- Requires Materials Project thermodynamic data
- Limited to categorical precursor selection + discrete temperatures
- Less effective for non-equilibrium or kinetically-controlled processes

---

### Use Bayesian Optimization When:
✅ **Optimizing any continuous or mixed parameter space** (temperature, pressure, concentration, time, etc.)  
✅ **Goal is to maximize/minimize a measured property** (yield, purity, conductivity, bandgap, etc.)  
✅ **No thermodynamic guidance available** (novel chemistries, non-equilibrium processes)  
✅ **Parameters are numerical or have unknown relationships**  
✅ **You have diverse characterization techniques** (XRD, SEM, electrochemistry, spectroscopy, etc.)  
✅ **Process optimization** rather than phase discovery (e.g., optimize thin film deposition, maximize battery performance)

**BO strengths:**
- Works with any parameter types (continuous, discrete, categorical)
- No domain knowledge required (model-free learning)
- Handles noisy measurements robustly
- Efficient for expensive experiments (surrogate modeling)
- Supports any objective metric (not limited to phase purity)
- Flexible measurement integration (any characterization technique)

**BO limitations:**
- Doesn't learn transferable chemistry knowledge
- Requires sufficient observations to build good surrogate model (typically 5-10 per parameter)
- Less interpretable than physics-guided ARROWS
- No automatic chemical reaction balancing

---

### Decision Matrix

| Scenario | Recommended Approach | Rationale |
|----------|---------------------|-----------|
| Synthesize high-purity LiCoO₂ from Li₂CO₃, CoO, Co₃O₄ | **ARROWS** | Known target phase, precursor selection, thermodynamic guidance available |
| Optimize thin film deposition temperature, pressure, and deposition rate | **Bayesian Optimization** | Continuous parameters, process optimization, no thermodynamic model |
| Discover new ternary oxide in Li-Mn-O system | **ARROWS** | Systematic phase space exploration, thermodynamic ranking, XRD characterization |
| Maximize conductivity of doped material (varying dopant type and concentration) | **Bayesian Optimization** | Property optimization, mixed categorical/continuous parameters |
| Find synthesis route for computationally-predicted phase | **ARROWS** | Target structure known, classical synthesis routes, equilibrium assumption valid |
| Optimize battery electrolyte composition (solvent ratios, salt concentration, additives) | **Bayesian Optimization** | High-dimensional continuous space, performance metric (not phase purity) |
| Screen 100+ precursor combinations for target perovskite | **ARROWS** | Large combinatorial space, thermodynamic pre-ranking efficient |
| Tune annealing profile (heating rate, hold time, cooling rate) | **Bayesian Optimization** | Continuous process parameters, kinetic effects important |

---

## Hybrid Strategies

For complex optimization problems, consider combining both approaches:

**Strategy 1: ARROWS → BO Refinement**
```
1. Use ARROWS to find conditions that synthesize target phase
2. Switch to BO to optimize continuous parameters around success:
   - Fine-tune temperature (continuous rather than discrete)
   - Optimize heating/cooling rates
   - Optimize precursor ratios (continuous)
   - Maximize purity or other properties
```

**Strategy 2: BO → ARROWS Validation**
```
1. Use BO for initial exploration of novel parameter space
2. Once promising chemistries identified, use ARROWS to:
   - Systematically explore precursor variations
   - Learn transferable reaction knowledge
   - Build robust synthesis protocols
```

**Strategy 3: Parallel Campaigns**
```
Run both simultaneously:
- ARROWS optimizes precursor selection + discrete temperatures
- BO optimizes continuous processing parameters (ramp rates, hold times, atmosphere)
- Combine insights from both to find global optimum
```

---

## Tool Catalogue

### ARROWS Tools (Thermodynamically-Guided Synthesis)

#### Campaign Preparation Tools

##### `arrows_initialize_campaign` — Initialize Active Learning Campaign
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

#### Experiment Loop Tools

##### `arrows_suggest_experiment` — Get Next Experiment
Suggests the next experiment(s) based on thermodynamic favorability and learned pairwise reactions.

**Key parameters:**
- `campaign_dir`: Path to campaign initialized by `arrows_initialize_campaign`
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

##### `xrd_analyze_pattern` — Automated Phase Identification
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

##### `arrows_record_result` — Record Experimental Outcome
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

#### Results Analysis Tools

Tools for analyzing campaign outcomes and visualizing learned knowledge.

*(To be added: trajectory analysis, success metrics, knowledge visualization)*

---

### Bayesian Optimization Tools (Generic Process Optimization)

#### Campaign Setup Tools

##### `bo_initialize_campaign` — Initialize Bayesian Optimization Campaign
Sets up BO campaign directory with parameter space definition and optimization objectives.

**Key parameters:**
- `campaign_dir`: Working directory for campaign state files
- `parameter_space`: List of parameter definitions (continuous, discrete, categorical)
- `objective_config`: Optimization objective (single or multi-objective)
- `n_initial_random`: Number of random samples before GP modeling (default 5)
- `campaign_name`: Optional descriptive name
- `metadata`: Optional experiment metadata

**Parameter space format:**
```python
parameter_space = [
    {
        "name": "temperature",
        "type": "continuous",
        "bounds": [400, 1200],
        "unit": "C"
    },
    {
        "name": "pressure",
        "type": "continuous",
        "bounds": [0.1, 10],
        "unit": "atm",
        "log_scale": True  # Optional: search in log space
    },
    {
        "name": "precursor",
        "type": "categorical",
        "choices": ["Li2CO3", "LiOH", "Li2O"]
    },
    {
        "name": "stirring_speed",
        "type": "discrete",
        "values": [100, 200, 500, 1000],
        "unit": "rpm"
    }
]
```

**Objective configuration:**
```python
# Single objective (maximize or minimize)
objective_config = {
    "type": "single_objective",
    "metrics": ["phase_purity"],  # or ["yield"], ["conductivity"], etc.
    "direction": "maximize"  # or "minimize"
}

# Multi-objective (future support)
objective_config = {
    "type": "multi_objective",
    "metrics": ["purity", "cost"],
    "directions": ["maximize", "minimize"],
    "scalarization": "weighted_sum",
    "weights": [0.7, 0.3]
}
```

**Returns:**
```python
{
  "success": True,
  "campaign_dir": "./bo_campaigns/process_opt_001",
  "campaign_name": "Thin film deposition optimization",
  "n_parameters": 4,
  "n_initial_random": 5,
  "initial_suggestions": [
    {"temperature": 750, "pressure": 2.3, "precursor": "LiOH", "stirring_speed": 500},
    # ... 4 more random suggestions
  ],
  "state_file": "./bo_campaigns/process_opt_001/bo_state.json",
  "observations_file": "./bo_campaigns/process_opt_001/bo_observations.json"
}
```

**What it does:**
- Validates parameter space and objective configuration
- Initializes campaign state (status: "initial_sampling")
- Generates initial random suggestions for exploration
- Creates campaign directory and state files

---

#### Experiment Loop Tools

##### `bo_record_observation` — Record Experimental Observation
Updates campaign with experimental result and associated measurements.

**Key parameters:**
- `campaign_dir`: Campaign directory
- `parameters`: Dictionary of parameter values used (must match parameter space)
- `observations`: Dictionary of measured metrics
- `observation_id`: Optional unique identifier
- `metadata`: Optional experiment metadata (timestamp, operator, notes, file paths, etc.)

**Example:**
```python
bo_record_observation(
    campaign_dir="./bo_campaigns/process_opt_001",
    parameters={
        "temperature": 800.0,
        "pressure": 1.0,
        "precursor": "Li2CO3",
        "stirring_speed": 500
    },
    observations={
        "phase_purity": 0.85,
        "grain_size_nm": 45.2,
        "synthesis_time_min": 120
    },
    observation_id="exp_023",
    metadata={
        "xrd_file": "/data/xrd/exp_023.xy",
        "operator": "robot_arm_1",
        "timestamp": "2026-04-13T14:23:00"
    }
)
```

**Returns:**
```python
{
  "success": True,
  "observation_id": "exp_023",
  "n_observations": 8,
  "objective_value": 0.85,
  "initial_phase": True,  # Still in random sampling phase
  "initial_phase_complete": False,
  "best_observed_value": 0.92,
  "files_updated": ["bo_state.json", "bo_observations.json"]
}
```

**What it does:**
- Validates parameters against campaign parameter space
- Validates that required objective metrics are present
- Appends observation to campaign database
- Updates campaign state (observation count, best value, status)
- Transitions from "initial_sampling" to "optimizing" after n_initial_random observations

---

##### `bo_suggest_experiment` — Generate Next Experiment Suggestions
Suggests next experiment(s) using Gaussian Process surrogate model and acquisition function.

**Key parameters:**
- `campaign_dir`: Campaign directory
- `batch_size`: Number of experiments to suggest (default 1)
- `acquisition_function`: Strategy for selecting next experiments
  - `"ei"` (Expected Improvement) — Balance exploration/exploitation (default)
  - `"ucb"` (Upper Confidence Bound) — Configurable exploration
  - `"pi"` (Probability of Improvement) — Conservative optimization
  - `"random"` — Pure exploration (ignore model)
- `exploration_weight`: Control exploration vs exploitation
  - For EI/PI: xi parameter (default 0.01, larger = more exploration)
  - For UCB: beta parameter (default 2.0, larger = more exploration)
- `n_candidates`: Number of candidate points to evaluate (default 10000)
- `random_seed`: Random seed for reproducibility

**Returns during initial phase (random sampling):**
```python
{
  "success": True,
  "using_gp_model": False,
  "n_suggestions": 1,
  "suggestions": [
    {"temperature": 650, "pressure": 5.2, "precursor": "Li2O", "stirring_speed": 200}
  ],
  "n_observations": 3,
  "initial_phase": True,
  "acquisition_function": "random",
  "rationale": "Initial random exploration (3/5 complete)"
}
```

**Returns during optimization phase (GP-guided):**
```python
{
  "success": True,
  "using_gp_model": True,
  "n_suggestions": 2,
  "suggestions": [
    {"temperature": 815, "pressure": 1.2, "precursor": "LiOH", "stirring_speed": 500},
    {"temperature": 780, "pressure": 0.8, "precursor": "Li2CO3", "stirring_speed": 1000}
  ],
  "n_observations": 12,
  "best_observed_value": 0.94,
  "best_parameters": {"temperature": 800, "pressure": 1.0, ...},
  "gp_model_score": 0.87,  # R² score of GP fit
  "acquisition_function": "ei",
  "exploration_weight": 0.01,
  "warnings": []
}
```

**What it does:**
- **Initial phase**: Samples random points for exploration (first n_initial_random observations)
- **Optimization phase**: Builds Gaussian Process surrogate model from observations
- Evaluates acquisition function across candidate points
- Selects batch of experiments with highest acquisition values
- For batch suggestions, uses greedy sequential selection to promote diversity

---

#### Results Analysis Tools

Tools for analyzing BO campaign outcomes.

*(To be added: convergence plots, parameter importance, model diagnostics)*

---

## MANDATORY Active Learning Workflows

### Choosing Your Workflow

**Use ARROWS workflow if:**
- Optimizing solid-state synthesis
- Target phase known, thermodynamic data available
- Primary characterization is XRD

**Use Bayesian Optimization workflow if:**
- Generic process optimization
- Continuous/mixed parameter space
- Any measurement modality

---

## ARROWS Workflow (Thermodynamically-Guided Synthesis)

### WORKFLOW SUMMARY FOR LLMs

**Standard ARROWS loop (manual XRD analysis):**
```
1. arrows_initialize_campaign → campaign initialized
2. arrows_suggest_experiment → (precursors, temp)
3. [Robot synthesis]
4. [User analyzes XRD manually] → phases, weights
5. arrows_record_result → knowledge updated
6. Repeat 2-5 until campaign_complete
```

**Enhanced loop (automated XRD):**
```
1. arrows_initialize_campaign → campaign initialized
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
CALL arrows_initialize_campaign(
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

## Bayesian Optimization Workflow (Generic Process Optimization)

### WORKFLOW SUMMARY FOR LLMs

**Standard BO loop:**
```
1. bo_initialize_campaign → campaign initialized, initial random suggestions
2. bo_suggest_experiment → parameters to try
3. [Execute experiment with suggested parameters]
4. [Measure objective metric(s)]
5. bo_record_observation → update surrogate model
6. Repeat 2-5 until objective achieved or budget exhausted
```

**Key difference from ARROWS:** BO is measurement-agnostic. You define what to measure and optimize - could be XRD purity, conductivity, yield, cost, or any quantifiable metric.

---

### PHASE 0: CAMPAIGN INITIALIZATION

**Input:** User wants to optimize a process or material property

**Step 0.1:** Extract campaign parameters from user request
```
SET objective = extract_optimization_goal(user_request)
# Examples:
#   - "maximize phase purity"
#   - "minimize synthesis time"
#   - "maximize conductivity"
#   - "optimize yield while minimizing cost"

SET parameters = extract_tunable_parameters(user_request)
# Examples:
#   - Continuous: temperature (400-1200°C), pressure (0.1-10 atm)
#   - Discrete: annealing time (30, 60, 120, 240 min)
#   - Categorical: precursor choice, atmosphere, substrate

SET campaign_dir = generate_campaign_dir_name(objective)

# Validate and format parameter space
FOR each parameter:
    IF type is continuous:
        REQUIRE bounds [min, max]
        OPTIONAL log_scale flag (for exponential ranges)
    ELSE IF type is discrete:
        REQUIRE list of allowed values
    ELSE IF type is categorical:
        REQUIRE list of choices
```

**Step 0.2:** Define parameter space
```
SET parameter_space = []

FOR each tunable parameter:
    CREATE parameter definition:
    {
        "name": parameter_name,
        "type": parameter_type,  # "continuous", "discrete", "categorical"
        "bounds": [min, max]  # for continuous
        OR "values": [v1, v2, ...]  # for discrete
        OR "choices": [c1, c2, ...]  # for categorical
        "unit": unit_string  # optional
    }
    APPEND to parameter_space
```

**Step 0.3:** Define objective configuration
```
SET objective_config = {
    "type": "single_objective",  # multi-objective support coming
    "metrics": [primary_metric_name],  # e.g., ["phase_purity"], ["yield"]
    "direction": "maximize" OR "minimize"
}

# For multi-objective (future):
# "metrics": ["purity", "cost"],
# "directions": ["maximize", "minimize"],
# "scalarization": "weighted_sum",
# "weights": [0.7, 0.3]
```

**Step 0.4:** Call campaign initialization
```
CALL bo_initialize_campaign(
    campaign_dir=campaign_dir,
    parameter_space=parameter_space,
    objective_config=objective_config,
    n_initial_random=5,  # Good default: 5-10 random samples per parameter
    campaign_name=descriptive_name,
    metadata={
        "project": project_name,
        "operator": user_name,
        "start_date": current_date
    }
)

STORE result in campaign_result

IF NOT campaign_result.success:
    REPORT error to user
    STOP
```

**Step 0.5:** Report campaign scope
```
REPORT to user:
  - Objective: {direction} {metrics}
  - Parameters: {list parameter names and ranges}
  - Initial random samples: {n_initial_random}
  - Campaign directory: {campaign_dir}
  - Status: "Ready for initial exploration"

REPORT initial suggestions:
  "Please run these {n_initial_random} experiments first (random sampling):"
  FOR each suggestion:
      DISPLAY parameters
```

**Proceed to PHASE 1**

---

### PHASE 1: ITERATIVE OPTIMIZATION

**This phase repeats until objective achieved, budget exhausted, or user stops.**

**Step 1.1:** Get next experiment suggestion(s)
```
# Determine batch size
IF user_can_parallelize:
    SET batch_size = user_parallel_capacity  # e.g., 4 parallel reactors
ELSE:
    SET batch_size = 1

# Choose acquisition function
IF early in campaign (< 10 observations):
    SET acquisition_function = "random"  # Pure exploration
    SET rationale = "Initial random sampling for GP model training"
ELSE IF moderate data (10-50 observations):
    SET acquisition_function = "ei"  # Expected Improvement (balanced)
    SET exploration_weight = 0.01  # Standard value
    SET rationale = "GP-guided optimization using Expected Improvement"
ELSE:
    # Many observations - can try different strategies
    IF user_wants_exploration:
        SET acquisition_function = "ucb"  # Upper Confidence Bound
        SET exploration_weight = 3.0  # High beta for exploration
        SET rationale = "Exploring uncertain regions"
    ELSE:
        SET acquisition_function = "ei"  # Stick with EI
        SET exploration_weight = 0.01
        SET rationale = "Exploiting learned model"

CALL bo_suggest_experiment(
    campaign_dir=campaign_dir,
    batch_size=batch_size,
    acquisition_function=acquisition_function,
    exploration_weight=exploration_weight,
    random_seed=None  # Set for reproducibility if needed
)

STORE result in suggestion

IF NOT suggestion.success:
    REPORT error
    STOP
```

**Step 1.2:** Communicate experiment to user/robot
```
FOR each experiment in suggestion.suggestions:
    REPORT to user:
      - Parameter values: {parameters}
      - Acquisition strategy: {acquisition_function}
      - Model status: {using_gp_model ? "GP-guided" : "Random exploration"}
      
    IF using_gp_model:
        REPORT additional context:
          - Current best: {best_observed_value} at {best_parameters}
          - GP model quality: R² = {gp_model_score}
      
    IF robot_available:
        DISPATCH_TO_ROBOT(experiment)
        WAIT for execution completion
    ELSE:
        ASK user to execute experiment manually
        WAIT for user confirmation
```

**Step 1.3:** Collect measurements
```
# User executes experiment and collects data
ASK user: "What measurements did you collect?"

# BO is flexible - accept any measurements
SET observations = {}

FOR each measured metric:
    ASK user for metric_name and metric_value
    observations[metric_name] = metric_value

# Validate that objective metric(s) are present
FOR each required_metric in objective_config.metrics:
    IF required_metric NOT IN observations:
        WARN user: "Missing required objective metric: {required_metric}"
        ASK user to provide value
        observations[required_metric] = user_input

# Optional metadata
OFFER to attach metadata:
  - File paths (XRD, SEM, raw data, etc.)
  - Timestamps
  - Operator notes
  - Experimental conditions not in parameter space

IF user_provides_metadata:
    SET metadata = user_metadata
ELSE:
    SET metadata = None
```

**Step 1.4:** Record observation
```
CALL bo_record_observation(
    campaign_dir=campaign_dir,
    parameters=experiment.parameters,  # From suggestion
    observations=observations,
    observation_id=generate_id(experiment_number),
    metadata=metadata
)

STORE result in record_result

IF NOT record_result.success:
    REPORT error
    ASK user for correction
    RETRY

IF record_result.success:
    REPORT to user:
      - Observation recorded: {observation_id}
      - Objective value: {objective_value}
      - Total observations: {n_observations}
      - Current best: {best_observed_value}
      
    IF record_result.initial_phase_complete:
        REPORT: "✓ Initial exploration complete. 
                 Switching to GP-guided optimization."
```

**Step 1.5:** Check convergence
```
# Check if objective achieved
SET current_best = record_result.best_observed_value
SET improvement = current_best - previous_best

IF objective achieved according to user criteria:
    REPORT: "🎯 OBJECTIVE ACHIEVED!
             Best value: {current_best}
             Optimal parameters: {best_parameters}"
    
    ASK user: "Continue optimizing or stop?"
    IF user_wants_stop:
        GOTO PHASE 2 (Analysis)

# Check for convergence (no improvement)
IF last N observations show no improvement:
    WARN user: "No improvement in last {N} experiments.
                Possible reasons:
                1. Near optimum (success!)
                2. Poor GP model fit
                3. Need more exploration
                
                Suggestions:
                1. Stop and analyze results
                2. Switch to exploration (UCB with high beta)
                3. Increase batch size for diversity"
    
    ASK user: "Continue, switch strategy, or stop?"
    IF user_wants_stop:
        GOTO PHASE 2

# Check budget constraints
IF observations >= max_budget:
    REPORT: "Budget exhausted ({max_budget} experiments).
             Best result: {current_best} at {best_parameters}"
    GOTO PHASE 2

# Otherwise, continue loop
GOTO Step 1.1 (next iteration)
```

---

### PHASE 2: RESULTS ANALYSIS

**Once campaign completes or user stops:**

**Step 2.1:** Load and summarize data
```
LOAD campaign state from bo_state.json
LOAD all observations from bo_observations.json

ANALYZE:
  - Total experiments: {count}
  - Objective achieved: {yes/no}
  - Best observed value: {max/min value}
  - Optimal parameters: {parameter values at optimum}
  - Improvement over initial: {best - initial_mean}

REPORT summary to user
```

**Step 2.2:** Model diagnostics
```
IF campaign used GP model:
    REPORT model quality:
      - Final R² score: {gp_score}
      - Cross-validation score: (if available)
      - Prediction uncertainty at optimum: {sigma at best point}
    
    IF gp_score < 0.5:
        WARN: "Poor model fit - results may not be reliable.
               Possible issues:
               1. Insufficient data
               2. High noise in measurements
               3. Complex parameter interactions
               Recommendation: Perform validation experiments"
```

**Step 2.3:** Parameter importance (future)
```
# To be added: Sensitivity analysis
# Which parameters have strongest effect on objective?
```

**Step 2.4:** Export and recommendations
```
OFFER to export:
  - Campaign summary (JSON)
  - Observations database (CSV)
  - Optimal protocol (parameters + expected performance)
  - Convergence plots (objective vs iteration)

RECOMMEND next steps:
  IF objective achieved:
    - Validate optimal conditions with replicate experiments
    - Explore robustness (sensitivity to parameter variations)
    - Document final protocol
    
  ELSE:
    - Analyze parameter trends
    - Consider different parameter ranges
    - Check for experimental errors or bias
```

---

## Common Patterns

### Pattern 1: Standard ARROWS Optimization Loop

**Use case:** User has robot synthesis + XRD characterization

```python
# Phase 0: Initialize
campaign = arrows_initialize_campaign(
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
campaign = arrows_initialize_campaign(...)

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

### Pattern 3: Bayesian Optimization for Continuous Parameters

**Use case:** Optimize deposition process with continuous temperature and pressure

```python
# Initialize campaign with continuous parameters
campaign = bo_initialize_campaign(
    campaign_dir="./bo_campaigns/deposition_opt",
    parameter_space=[
        {
            "name": "temperature",
            "type": "continuous",
            "bounds": [400, 1000],
            "unit": "C"
        },
        {
            "name": "pressure",
            "type": "continuous",
            "bounds": [0.01, 10],
            "unit": "torr",
            "log_scale": True  # Exponential range
        },
        {
            "name": "deposition_time",
            "type": "continuous",
            "bounds": [5, 120],
            "unit": "min"
        }
    ],
    objective_config={
        "type": "single_objective",
        "metrics": ["film_quality"],
        "direction": "maximize"
    },
    n_initial_random=10,  # 3-4x number of parameters
    campaign_name="Thin film deposition optimization"
)

# Run initial random experiments
for i in range(campaign['n_initial_random']):
    suggestion = bo_suggest_experiment(
        campaign_dir="./bo_campaigns/deposition_opt"
    )
    
    params = suggestion['suggestions'][0]
    
    # Execute deposition
    film = deposition_system.run(
        temperature=params['temperature'],
        pressure=params['pressure'],
        time=params['deposition_time']
    )
    
    # Measure quality (XRD, SEM, electrical, etc.)
    quality_score = characterize_film(film)
    
    # Record result
    bo_record_observation(
        campaign_dir="./bo_campaigns/deposition_opt",
        parameters=params,
        observations={"film_quality": quality_score},
        metadata={"film_id": f"film_{i:03d}"}
    )

# GP-guided optimization
while True:
    suggestion = bo_suggest_experiment(
        campaign_dir="./bo_campaigns/deposition_opt",
        acquisition_function="ei"
    )
    
    if suggestion['n_observations'] >= 50:  # Budget limit
        break
    
    params = suggestion['suggestions'][0]
    film = deposition_system.run(**params)
    quality = characterize_film(film)
    
    result = bo_record_observation(
        campaign_dir="./bo_campaigns/deposition_opt",
        parameters=params,
        observations={"film_quality": quality}
    )
    
    # Check if goal achieved
    if result['best_observed_value'] > 0.95:  # 95% quality threshold
        print(f"✓ Target quality achieved!")
        print(f"Optimal conditions: {suggestion['best_parameters']}")
        break
```

---

### Pattern 4: Mixed Parameter Types with Bayesian Optimization

**Use case:** Optimize synthesis with both categorical and continuous parameters

```python
campaign = bo_initialize_campaign(
    campaign_dir="./bo_campaigns/battery_opt",
    parameter_space=[
        {
            "name": "cathode_material",
            "type": "categorical",
            "choices": ["LiCoO2", "LiMn2O4", "LiFePO4", "NMC111", "NMC811"]
        },
        {
            "name": "electrolyte_concentration",
            "type": "continuous",
            "bounds": [0.5, 2.0],
            "unit": "M"
        },
        {
            "name": "cycling_temperature",
            "type": "discrete",
            "values": [25, 40, 55, 70],
            "unit": "C"
        },
        {
            "name": "additive",
            "type": "categorical",
            "choices": ["none", "VC", "FEC", "LiBOB"]
        }
    ],
    objective_config={
        "type": "single_objective",
        "metrics": ["capacity_retention"],
        "direction": "maximize"
    },
    n_initial_random=16  # 4× number of parameters
)

# Optimization loop
for iteration in range(100):
    suggestion = bo_suggest_experiment(
        campaign_dir="./bo_campaigns/battery_opt",
        acquisition_function="ei" if iteration >= 16 else "random"
    )
    
    params = suggestion['suggestions'][0]
    
    # Build and test battery cell
    cell = assemble_cell(
        cathode=params['cathode_material'],
        electrolyte_conc=params['electrolyte_concentration'],
        additive=params['additive']
    )
    
    capacity_retention = cycle_cell(
        cell,
        temperature=params['cycling_temperature'],
        cycles=100
    )
    
    bo_record_observation(
        campaign_dir="./bo_campaigns/battery_opt",
        parameters=params,
        observations={
            "capacity_retention": capacity_retention,
            "initial_capacity": cell.capacity_mAh,  # Track additional metrics
            "impedance": cell.impedance_ohm
        }
    )
```

---

### Pattern 5: Hybrid ARROWS → BO Refinement

**Use case:** Find synthesis route with ARROWS, then optimize with BO

```python
# Phase 1: Use ARROWS to find working synthesis route
arrows_campaign = arrows_initialize_campaign(
    target="BaTiO3",
    precursors=["BaO", "BaCO3", "TiO2"],
    temperatures=[700, 800, 900, 1000],
    campaign_dir="./campaigns/BaTiO3_discovery"
)

# Run ARROWS until target synthesized
# ... (ARROWS loop as in Pattern 1) ...
# Result: Target forms at 800°C using BaCO3 + TiO2

# Phase 2: Use BO to optimize around successful conditions
bo_campaign = bo_initialize_campaign(
    campaign_dir="./bo_campaigns/BaTiO3_refinement",
    parameter_space=[
        {
            "name": "temperature",
            "type": "continuous",
            "bounds": [750, 850],  # Narrow range around 800°C
            "unit": "C"
        },
        {
            "name": "heating_rate",
            "type": "continuous",
            "bounds": [1, 20],
            "unit": "C/min"
        },
        {
            "name": "hold_time",
            "type": "continuous",
            "bounds": [0.5, 12],
            "unit": "hours"
        },
        {
            "name": "BaCO3_excess",
            "type": "continuous",
            "bounds": [0.9, 1.1],  # Stoichiometry ratio
            "unit": "equiv"
        }
    ],
    objective_config={
        "type": "single_objective",
        "metrics": ["BaTiO3_purity"],
        "direction": "maximize"
    },
    n_initial_random=8
)

# Optimization loop
for iteration in range(50):
    suggestion = bo_suggest_experiment(
        campaign_dir="./bo_campaigns/BaTiO3_refinement",
        acquisition_function="ei"
    )
    
    params = suggestion['suggestions'][0]
    
    # Synthesize with optimized conditions
    product_xrd_file = synthesize(
        precursors={"BaCO3": params['BaCO3_excess'], "TiO2": 1.0},
        profile={
            "ramp_rate": params['heating_rate'],
            "hold_temp": params['temperature'],
            "hold_time": params['hold_time']
        }
    )
    
    # Analyze purity
    xrd_result = xrd_analyze_pattern(
        spectrum_path=product_xrd_file,
        model_path="./models/Ba-Ti-O/Models/"
    )
    
    purity = xrd_result['weight_fractions'][
        xrd_result['phases'].index("BaTiO3_99")
    ] if "BaTiO3_99" in xrd_result['phases'] else 0.0
    
    bo_record_observation(
        campaign_dir="./bo_campaigns/BaTiO3_refinement",
        parameters=params,
        observations={"BaTiO3_purity": purity}
    )
    
    if purity > 0.98:
        print(f"✓ High purity achieved: {purity*100:.1f}%")
        break
```

---

## Critical Decision Points

### DECISION 1: When to Use Exploration vs Exploitation

**For ARROWS:**
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

**For Bayesian Optimization:**
```
IF n_observations < n_initial_random:
    # Still in initial random phase
    SET acquisition_function = "random"
    
ELSE IF n_observations < 3 × n_parameters:
    # Limited data - balanced approach
    SET acquisition_function = "ei"
    SET exploration_weight = 0.01  # Standard value
    
ELSE IF converging (no recent improvement):
    # Explore more to escape local optimum
    SET acquisition_function = "ucb"
    SET exploration_weight = 3.0  # High exploration
    
ELSE:
    # Sufficient data - exploit learned model
    SET acquisition_function = "ei"
    SET exploration_weight = 0.001  # Low exploration
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

### DECISION 3: Choosing Initial Random Samples for BO

```
SET n_parameters = len(parameter_space)

# General rule: 3-5× number of parameters
IF parameter_space is simple (mostly continuous):
    SET n_initial_random = 3 × n_parameters
    
ELSE IF parameter_space has many categorical parameters:
    SET n_initial_random = 5 × n_parameters
    # Categorical variables need more samples to cover combinations
    
ELSE IF measurements are very expensive:
    SET n_initial_random = max(5, 2 × n_parameters)
    # Minimum viable for GP, but accept lower model quality
    
ELSE IF measurements are cheap:
    SET n_initial_random = 10 × n_parameters
    # Oversampling gives better GP model

# Sanity bounds
SET n_initial_random = max(5, min(n_initial_random, 50))
```

---

### DECISION 4: XRD Model Selection


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
3. arrows_initialize_campaign using those as starting point
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
