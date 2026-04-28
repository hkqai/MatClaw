---
name: candidate-screener
description: >
  Validate, enrich with properties, and rank candidate structures for materials discovery. Takes candidates from candidate-generator skill, validates structures, retrieves properties from Materials Project/ASE database/ML calculations hierarchically, applies screening criteria, and ranks by multi-objective optimization. ML calculations use MatGL for formation energy and band gap predictions, and matcalc for mechanical (elasticity), vibrational (phonons), surface, thermal, and reaction properties. Use this skill to transform raw candidate lists into ranked, property-enriched sets ready for synthesis or DFT calculations. Trigger keywords: screen candidates, validate structures, property retrieval, rank materials, filter candidates, battery screening, catalyst discovery, thermoelectric materials, phosphor screening, mechanical properties, phonon stability, surface energies.
applyTo:
  - "**/screening*.py"
  - "**/screen_*.py"
  - "**/candidate_screening*.py"
---

# Candidate Screener Skill

Validates and enriches candidate structures with properties using hierarchical data retrieval (Materials Project → ASE cache → ML prediction), applies application-specific screening criteria, and ranks by multi-objective optimization.

**Input:** List of candidate structures from candidate-generator skill  
**Output:** Ranked list of property-enriched candidates ready for synthesis/DFT validation

---

## Core Philosophy

**This skill implements a property enrichment pipeline, NOT a blind filter:**

1. **Hierarchical property retrieval** (MP → ASE cache → ML calculation)
   - Try high-quality DFT data first (Materials Project)
   - Fall back to cached results (ASE database)
   - Only run ML calculations if necessary (MatGL + matcalc)

2. **Never silently exclude** - always log rejection reasons
   - Invalid structures: rejected with cause
   - ML prediction failures: flagged for DFT verification
   - Failed criteria: recorded with specific thresholds

3. **Confidence-aware ranking**
   - MP (DFT) properties: confidence = 1.0
   - ASE cached: confidence = 0.8-1.0 (depends on source)
   - ML predictions: confidence = 0.65-0.75
   - High-scoring ML predictions flagged for DFT verification

4. **Two ML ecosystems:**
   - **MatGL** (direct predictions): Fast formation energy + band gap (~0.5-1s each)
   - **matcalc** (structure-based calculations): Mechanical, vibrational, surface, thermal properties (~20-60s each)
   - Always relax structures first (5-10s)

---

## Quick Tool Reference

### Phase 1: Validation & Analysis
| Tool | Purpose | Speed |
|------|---------|-------|
| `structure_validator` | Check structure integrity | 0.1s |
| `composition_analyzer` | Analyze composition, oxidation states | 0.05s |
| `stability_analyzer` | Predict thermodynamic stability (MP hull) | 0.5s |
| `structure_analyzer` | Compute symmetry, coordination | 0.1s |
| `structure_fingerprinter` | Detect duplicates | 0.5s |

### Phase 2A: Property Retrieval (Hierarchical)
| Source | Tools | Priority | Confidence |
|--------|-------|----------|------------|
| Materials Project | `mp_search_materials`, `mp_get_material_properties` | 1st (best) | 1.0 (DFT) |
| ASE cache | `ase_query`, `ase_connect_or_create_db` | 2nd | 0.8-1.0 |
| ML calculation | MatGL + matcalc | 3rd | 0.65-0.75 |

### Phase 2B: ML Calculations
| Ecosystem | Tools | Properties | Speed |
|-----------|-------|------------|-------|
| **MatGL** | `matgl_predict_eform`, `matgl_predict_bandgap` | Formation energy, band gap | 0.5-1s |
| **matcalc** | `matcalc_calc_elasticity`, `matcalc_calc_phonon`, `matcalc_calc_surface`, etc. | Mechanical, vibrational, surface, thermal | 20-60s |
| **Relaxation** | `matgl_relax_structure` | MANDATORY before all predictions | 5-10s |

**MatGL tools (fast screening):**
- `matgl_predict_eform`: Formation energy (M3GNet/MEGNet 2018 models)
- `matgl_predict_bandgap`: Electronic band gap (MEGNet 2019 model)

**matcalc tools (detailed calculations, 2025 ML potentials):**
- `matcalc_calc_elasticity`: Elastic tensor, bulk/shear/Young's modulus
- `matcalc_calc_phonon`: Phonon dispersion, dynamic stability
- `matcalc_calc_surface`: Surface energies (catalyst screening)
- `matcalc_calc_eos`: Equation of state, bulk modulus
- `matcalc_calc_adsorption`: Adsorption energies
- `matcalc_calc_md`: Molecular dynamics
- `matcalc_calc_neb`: Reaction barriers, diffusion paths
- `matcalc_calc_phonon3`: Thermal conductivity (expensive!)
- `matcalc_calc_qha`: Thermal expansion
- `matcalc_calc_energetics`: Formation + cohesive energy (use MatGL for screening instead)
- `matcalc_calc_interface`: Grain boundary / heterostructure energies

### Phase 3: Ranking & Selection
| Tool | Purpose | Speed |
|------|---------|-------|
| `multi_objective_ranker` | Rank by multiple criteria (Pareto/weighted sum) | 10s |

**Storage:**
- `ase_store_result`: Cache results in ASE database for future runs

**For complete tool specifications, see [references/tool-catalog.md](references/tool-catalog.md)**

---

## Universal Essential Properties

**ALL materials screenings must retrieve these minimum properties (regardless of application):**

### 1. Validation (Phase 1)
- ✅ **Structure valid**: No overlapping atoms, valid geometry
- ✅ **Composition valid**: Charge-neutral, reasonable oxidation states
- ⚠️ **Thermodynamic stability**: Energy above hull (optional pre-filter)

### 2. Basic Properties (Phase 2)
- ✅ **Formation energy** (REQUIRED): Thermodynamic stability indicator
  - **Source priority:** MP → ASE → `matgl_predict_eform` (fast)
  - **NOT** `matcalc_calc_energetics` (20× slower, use only for cohesive energy)

- ⚠️ **Band gap** (optional): Electronic properties
  - **Source priority:** MP → ASE → `matgl_predict_bandgap` (only tool)

### 3. Application-Specific Properties (Phase 2, conditional)
Choose based on application:

**Battery cathodes:** Band gap, mechanical stability  
**Catalysts:** Surface energies, adsorption energies  
**Thermoelectrics:** Band gap, thermal conductivity  
**Structural materials:** Mechanical properties (elasticity, hardness)  
**Phosphors:** Band gap, optical properties

---

## MANDATORY Workflow Algorithm

**Execute this exact sequence for every screening run. For detailed pseudocode, see [references/workflow-algorithm.md](references/workflow-algorithm.md)**

### Step-by-Step Overview

**STEP 0: INITIALIZATION**
```
Initialize: validated_candidates, rejected_candidates, candidates_with_properties
Create ASE database: ase_connect_or_create_db(db_path="screening_YYYYMMDD.db")
```

**STEP 1: VALIDATION & ANALYSIS (Phase 1)**

For each candidate:
```
1. structure_validator → REJECT if invalid, CONTINUE if valid
2. composition_analyzer → Store elements, oxidation states
3. (Optional) stability_analyzer → Flag if highly unstable
4. (Optional) structure_fingerprinter → Deduplicate similar structures

Result: validated_candidates
```

**STEP 2: HIERARCHICAL PROPERTY RETRIEVAL (Phase 2)**

For each validated candidate, try sources in order:
```
2.1 Materials Project (1st priority):
    mp_search_materials → IF found → mp_get_material_properties
    → Cache in ASE, CONTINUE to next candidate

2.2 ASE cache (2nd priority):
    ase_query → IF found → CONTINUE to next candidate

2.3 ML calculation (3rd priority - ONLY if 2.1 and 2.2 failed):
    a. matgl_relax_structure (REQUIRED first!)
    b. matgl_predict_eform (formation energy - fast)
    c. matgl_predict_bandgap (band gap - fast)
    d. (Optional) matcalc_calc_elasticity (mechanical - if needed)
    e. (Optional) matcalc_calc_phonon (vibrational - if needed)
    f. (Optional) matcalc_calc_surface (surface - if catalyst)
    g. (Optional) Other matcalc tools as needed
    → Cache in ASE, FLAG for DFT verification

Result: candidates_with_properties
```

**CRITICAL RULES:**
- NEVER skip ahead in hierarchy (always try MP → ASE → ML)
- ALWAYS relax structures before ML predictions
- MatGL for formation energy/band gap, matcalc for everything else
- ALWAYS cache results in ASE database

**STEP 3: CRITERIA-BASED FILTERING (Phase 3)**

For each candidate with properties:
```
Define screening_criteria (application-specific)
Check all criteria:
  - Formation energy within range?
  - Band gap within range?
  - Stability above threshold?
  - Mechanical properties acceptable?
IF all criteria met → KEEP
ELSE → REJECT with specific failure reasons

Result: filtered_candidates
```

**STEP 4: MULTI-OBJECTIVE RANKING (Phase 4)**

For filtered candidates:
```
Define objectives (property, direction, weight)
Apply multi_objective_ranker(method="pareto" or "weighted_sum")
Apply confidence weighting:
  - MP: 1.0 × score
  - ASE cached: 0.8-1.0 × score
  - ML: 0.65-0.75 × score
Flag high-scoring ML predictions for DFT verification

Result: ranked_candidates
```

**STEP 5: OUTPUT GENERATION**
```
Generate screening_report:
  - Summary statistics (input, validated, with_properties, passed, ranked)
  - Data source breakdown (MP, ASE, ML counts)
  - Top N candidates
  - Rejected candidates with reasons
  - Property distributions
  - Database info
```

---

## Hierarchical Property Retrieval Logic

**Key decision: Which property source to use?**

```
FOR each candidate:
    TRY Materials Project (best quality):
        mp_search_materials(formula)
        IF found → mp_get_material_properties → DONE ✓
    
    ELSE TRY ASE cache (instant):
        ase_query(formula)
        IF found → DONE ✓
    
    ELSE ML calculation (last resort):
        1. matgl_relax_structure (REQUIRED!)
        2. matgl_predict_eform (formation energy, fast)
        3. matgl_predict_bandgap (band gap, fast)
        4. matcalc_calc_* (mechanical/phonons/surfaces, slower, conditional)
        FLAG for DFT verification → DONE ⚠️
```

**Never skip ahead.** Always try MP first, even if slow. DFT-quality properties worth the wait.

---

## MatGL vs matcalc: Quick Decision Guide

**Use MatGL for:**
- ✅ High-throughput formation energy screening (~0.5s per structure)
- ✅ Band gap screening (~0.5s per structure)
- ✅ Initial rapid filtering of 100+ candidates

**Use matcalc for:**
- ✅ Mechanical properties (elasticity, bulk modulus)
- ✅ Vibrational properties (phonon stability)
- ✅ Surface properties (catalyst screening)
- ✅ Thermal properties (expansion, conductivity)
- ✅ Reaction barriers (NEB)
- ✅ Detailed calculations for top 10-20 candidates after MatGL screening

**Hierarchical screening strategy (recommended):**
```
Phase 1: MatGL screening (minutes)
  100 candidates → relax → eform+bandgap → filter → 42 passed

Phase 2: matcalc calculations (hours)
  42 passed → elasticity+phonons for top 20 → 8 high-priority

Phase 3: DFT verification (days)
  8 high-priority → full DFT calculations → 3 for synthesis
```

**For detailed usage guidelines, see [references/ml-calculations-guide.md](references/ml-calculations-guide.md)**

---

## Large-Scale Screening (>20 Candidates)

**When screening >20 candidates, ALWAYS:**

1. **Create screening tracking file FIRST** (before execution)
   - JSON file with per-candidate status tracking
   - Enables checkpointing after each candidate
   - Allows resume after interruptions (ML relaxations take 5-10s × 100 = 8-15 min)

2. **Present screening plan to user** (wait for approval)
   - Total candidates + criteria
   - Expected MP vs ML percentages
   - Estimated runtime
   - Option to adjust criteria

3. **Execute with checkpointing** (save after EVERY candidate)
   - Validation → save
   - Property retrieval → save
   - Screening → save
   - Ranking → save

4. **Support iterative refinement**
   - Preserve all properties even if screening fails
   - User can adjust criteria without rerunning expensive ML
   - Example: Relax band gap 3.0-5.0 eV → 2.5-5.5 eV, rerun Phase 3 only (cached properties, instant)

**For complete tracking workflow, see [references/large-scale-screening.md](references/large-scale-screening.md)**

---

## Critical Decision Algorithms

**For detailed logic, see [references/decision-trees-errors.md](references/decision-trees-errors.md)**

### Decision 1: Structure Relaxation

```
IF source in ["DFT", "MP", "experimental"] → skip relaxation (already optimized)
ELSE IF ionic solid with high symmetry → skip (already at minimum)
ELSE → MUST relax before predictions
```

### Decision 2: ML Prediction Failure

```
TRY primary model (M3GNet)
EXCEPT → TRY backup model (MEGNet)
EXCEPT → TRY MP similarity search → estimate from similar
EXCEPT → SET requires_dft=True, CONTINUE (never silently exclude!)
```

### Decision 3: Multiple MP Matches

```
IF 1 match → use it
IF >1 match AND exploring metastable → keep all polymorphs
ELSE → take most stable (lowest energy_per_atom)
```

### Decision 4: Confidence-Weighted Ranking

```
confidence_weights = {MP: 1.0, ASE_cached: 0.8-1.0, ML: 0.65-0.75}
adjusted_score = base_score × confidence
IF base_score > 0.8 AND confidence < 0.8 → recommend_dft=True (high priority)
```

---

## Example Workflows

### Example 1: Battery Cathode Screening

**Goal:** Stable materials with moderate band gap

```python
# Phase 1: MatGL screening (15 min for 100 candidates)
FOR each candidate:
    relax → matgl_predict_eform → matgl_predict_bandgap
    FILTER: formation_energy < 0.0 AND band_gap 0.5-2.0 eV

# Phase 2: matcalc (40 min for top 20)
FOR top 20:
    matcalc_calc_elasticity  # Mechanical stability
    matcalc_calc_phonon      # Dynamic stability

# Result: 100 → 42 (MatGL) → 20 (matcalc) → 8 for DFT
```

### Example 2: Catalyst Screening

**Goal:** Stable surfaces with favorable adsorption

```python
# Phase 1: MatGL screening (15 min for 100 candidates)
FOR each candidate:
    relax → matgl_predict_eform → stability_analyzer
    FILTER: formation_energy < 0.0 AND thermodynamically_stable

# Phase 2: Surface screening (90 min for top 30)
FOR top 30:
    matcalc_calc_surface([1,0,0])
    matcalc_calc_surface([1,1,0])
    matcalc_calc_surface([1,1,1])
    FILTER: surface_energy < threshold

# Phase 3: Adsorption (40 min for top 10)
FOR top 10:
    matcalc_calc_adsorption("CO", "ontop")
    matcalc_calc_adsorption("OH", "ontop")

# Result: 100 → 68 (stable) → 30 (surfaces) → 10 (adsorption) → 5 for DFT
```

### Example 3: Thermoelectric Screening

**Goal:** Narrow band gap, mechanically stable, low thermal conductivity

```python
# Phase 1: MatGL screening (15 min for 100 candidates)
FOR each candidate:
    relax → matgl_predict_bandgap
    FILTER: band_gap < 0.5 eV

# Phase 2: Mechanical (20 min for top 40)
FOR top 40:
    matcalc_calc_elasticity
    FILTER: is_mechanically_stable

# Phase 3: Thermal conductivity (20-30 hours for top 15!)
FOR top 15:
    matcalc_calc_phonon3  # VERY expensive
    FILTER: thermal_conductivity_300K < threshold

# Result: 100 → 52 (narrow gap) → 40 (stable) → 15 (κ) → 8 for DFT
```

---

## Output Report Structure

```json
{
  "screening_summary": {
    "total_input": 100,
    "validated": 85,
    "with_properties": 77,
    "passed_filters": 42,
    "ranked": 42,
    "screening_time_seconds": 325
  },
  "data_source_breakdown": {
    "materials_project": 38,
    "ase_cached": 24,
    "ml_calculated": 15
  },
  "top_candidates": [
    {
      "rank": 1,
      "formula": "LiFePO4",
      "properties": {
        "formation_energy_per_atom": -2.341,
        "band_gap": 0.8,
        "source": "Materials_Project",
        "confidence": "high"
      },
      "scores": {"total_score": 0.94},
      "recommendation": "Top priority - DFT-verified",
      "requires_dft": false
    }
  ],
  "rejected_candidates": [
    {"formula": "Li5FeO4", "reason": "Invalid structure - overlapping atoms"},
    {"formula": "Li3P", "reason": "Formation energy > 0 eV/atom (unstable)"}
  ],
  "property_distributions": {
    "formation_energy": {"min": -3.2, "max": -0.8, "mean": -2.1}
  }
}
```

---

## Performance Estimates

**Screening 100 candidates:**

| Scenario | Time | Description |
|----------|------|-------------|
| Best case (80% in MP) | ~2 min | Mostly DFT data lookups |
| Typical (50% MP, 30% ASE, 20% ML) | ~5 min | Balanced sources |
| Worst case (all ML) | ~20 min | All relaxation + predictions |

**Operation breakdown:**
- Validation: ~0.1s per candidate
- MP lookup: ~0.3s per candidate
- ASE query: ~0.01s per candidate (instant)
- ML relaxation: ~5-10s per structure
- MatGL prediction: ~0.5-1s per property
- matcalc calculation: ~20-60s per property (depends on type)
- Ranking: ~10s for 100 candidates

---

## Integration with Other Skills

### Input from candidate-generator

```python
# candidate-generator outputs structures
candidates = load_json("lanthanide_niobate_candidates_100.json")

# Feed directly to candidate-screener
screening_report = candidate_screener_workflow(
    candidates=candidates,
    screening_criteria={...},
    objectives=[...]
)
```

### Output to synthesis-planner

```python
# Top candidates go to synthesis planning
top_10 = screening_report["top_candidates"][:10]

for candidate in top_10:
    synthesis_route = synthesis_planner(
        target_material=candidate["formula"]
    )
```

---

## Common Pitfalls

### ❌ WRONG: Skip relaxation before ML prediction

```python
eform = matgl_predict_eform(candidate.structure)  # Unrelaxed → inaccurate!
```

### ✅ CORRECT: Always relax first

```python
relaxed = matgl_relax_structure(candidate.structure, fmax=0.1)
eform = matgl_predict_eform(relaxed["final_structure"])  # Accurate ✓
```

---

### ❌ WRONG: Use matcalc for formation energy screening

```python
FOR 100 candidates:
    eform = matcalc_calc_energetics(candidate)  # 30s × 100 = 50 minutes!
```

### ✅ CORRECT: Use MatGL for screening

```python
FOR 100 candidates:
    eform = matgl_predict_eform(candidate)  # 0.5s × 100 = 1 minute ✓
```

---

### ❌ WRONG: Skip hierarchy (jump to ML)

```python
# BAD: Skip MP/ASE, always use ML
FOR candidate:
    eform = matgl_predict_eform(candidate)  # Ignoring DFT data!
```

### ✅ CORRECT: Try hierarchy in order

```python
# GOOD: MP → ASE → ML
FOR candidate:
    TRY mp_search_materials → IF found, DONE
    ELSE TRY ase_query → IF found, DONE
    ELSE matgl_predict_eform  # Last resort ✓
```

---

### ❌ WRONG: Silently exclude failed predictions

```python
TRY:
    eform = matgl_predict_eform(structure)
EXCEPT:
    CONTINUE  # Skip candidate silently - BAD!
```

### ✅ CORRECT: Flag for DFT verification

```python
TRY:
    eform = matgl_predict_eform(structure)
EXCEPT:
    candidate.requires_dft = True
    candidate.ml_errors = [...]
    CONTINUE  # Include with flag ✓
```

---

## Reference Documentation

**Detailed documentation in `references/` directory:**

1. **[workflow-algorithm.md](references/workflow-algorithm.md)** - Complete step-by-step execution pseudocode with all branching logic
2. **[decision-trees-errors.md](references/decision-trees-errors.md)** - Critical decision algorithms and comprehensive error handling procedures
3. **[ml-calculations-guide.md](references/ml-calculations-guide.md)** - MatGL vs matcalc usage guide, model selection, parameter tuning
4. **[large-scale-screening.md](references/large-scale-screening.md)** - Checkpoint-based tracking for >20 candidates, resume capability
5. **[tool-catalog.md](references/tool-catalog.md)** - Complete specifications for all 25 tools

**Read these references when:**
- Implementing screening workflow (workflow-algorithm.md)
- Debugging errors or handling edge cases (decision-trees-errors.md)
- Choosing between MatGL and matcalc (ml-calculations-guide.md)
- Screening >20 candidates (large-scale-screening.md)
- Looking up tool parameters (tool-catalog.md)

---

**Last updated:** 2025-01-28  
**Skill version:** 2.0 (refactored with progressive disclosure)
