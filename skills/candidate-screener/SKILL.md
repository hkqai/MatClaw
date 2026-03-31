---
name: candidate-screener
description: Validate, enrich with properties, and rank candidate structures for materials discovery. Takes candidates from candidate-generator skill, validates structures, retrieves properties from Materials Project/ASE database/ML predictions hierarchically, applies screening criteria, and ranks by multi-objective optimization. Use this skill to transform raw candidate lists into ranked, property-enriched sets ready for synthesis or DFT calculations.
---

# Candidate Screening Skill

This skill orchestrates high-throughput screening of candidate structures using a strict hierarchical workflow:
1. **Structure validation & analysis** (filter invalid candidates early)
2. **Property retrieval** (MP -> ASE cache -> ML prediction, in that order)
3. **Criteria-based filtering** (apply hard constraints)
4. **Multi-objective ranking** (order by desirability)

## Core Philosophy

**Data Source Hierarchy = Quality × Speed optimization:**
- Materials Project first (DFT-quality, peer-reviewed)
- ASE database second (cached results, instant lookup)
- ML prediction last (fast fallback, reasonable accuracy)

**Always cache everything** in ASE database to avoid recomputation across screening runs.

---

## Tool Catalogue

### Phase 1: Validation & Analysis

#### 1. `structure_validator` — Structural Integrity Check
Validates crystal structures for physical correctness before expensive property calculations.

**Key parameters:**
- `structure`: pymatgen Structure dict or string (CIF/POSCAR)
- `check_composition`: verify valid stoichiometry (default `True`)
- `check_charge_neutrality`: ensure net charge = 0 (default `True`)
- `check_geometry`: validate atomic positions, distances (default `True`)
- `min_distance`: minimum allowed interatomic distance in Å (default 0.5)

**Returns:**
```python
{
  "success": True,
  "is_valid": True,  # False if any check fails
  "checks": {
    "composition_valid": True,
    "charge_neutral": True,
    "geometry_valid": True,
    "no_overlapping_atoms": True
  },
  "issues": [],  # List of validation errors if any
  "formula": "LiFePO4",
  "num_sites": 28
}
```

**Use first:** Filter out invalid structures before wasting time on property lookups.

---

#### 2. `composition_analyzer` — Chemical Composition Analysis
Analyzes elemental composition, oxidation states, and chemical properties.

**Key parameters:**
- `structure`: pymatgen Structure dict or string
- `analyze_oxidation`: compute oxidation states (default `True`)
- `compute_descriptors`: include electronegativity, atomic radius stats (default `True`)

**Returns:**
```python
{
  "success": True,
  "formula": "LiFePO4",
  "reduced_formula": "LiFePO4",
  "elements": ["Li", "Fe", "P", "O"],
  "element_count": 4,
  "oxidation_states": {"Li": 1, "Fe": 2, "P": 5, "O": -2},
  "composition_type": "ionic",
  "descriptors": {
    "avg_electronegativity": 2.85,
    "electronegativity_range": 2.44,
    "avg_atomic_radius": 1.12
  },
  "warnings": []  # e.g., "Contains radioactive elements"
}
```

**Use for:** Early flagging of exotic compositions, understanding chemistry before property prediction.

---

#### 3. `stability_analyzer` — Thermodynamic Stability Assessment
Predicts whether a composition is likely thermodynamically stable using Materials Project phase diagram.

**Key parameters:**
- `structure`: pymatgen Structure dict/string, or just `composition="LiFePO4"`
- `energy_tolerance`: eV/atom above convex hull to consider "metastable" (default 0.1)

**Returns:**
```python
{
  "success": True,
  "formula": "LiFePO4",
  "is_stable": True,
  "energy_above_hull": 0.0,  # eV/atom
  "stability_category": "stable",  # stable, metastable, unstable
  "decomposition_products": null,  # List if unstable
  "competing_phases": ["Li3PO4", "Fe2P", "FeO"],
  "recommendation": "Likely synthesizable - thermodynamically stable"
}
```

**Use as:** Pre-filter to remove obviously unstable candidates before expensive calculations.

---

#### 4. `structure_analyzer` — Detailed Structural Characterization
Computes lattice parameters, space group, coordination environments, and structural fingerprints.

**Key parameters:**
- `structure`: pymatgen Structure dict or string
- `compute_symmetry`: determine space group (default `True`)
- `analyze_coordination`: compute coordination numbers/polyhedra (default `True`)
- `compute_fingerprint`: generate structure fingerprint for similarity (default `False`)

**Returns:**
```python
{
  "success": True,
  "formula": "LiFePO4",
  "lattice_parameters": {"a": 10.33, "b": 6.01, "c": 4.69, "alpha": 90, "beta": 90, "gamma": 90},
  "volume": 291.4,
  "density": 3.60,
  "spacegroup": {"number": 62, "symbol": "Pnma"},
  "coordination_environments": {
    "Li": {"coordination": 6, "geometry": "octahedral"},
    "Fe": {"coordination": 6, "geometry": "octahedral"}
  }
}
```

**Use for:** Understanding structural features before screening, clustering similar candidates.

---

#### 5. `structure_fingerprinter` — Similarity & Duplicate Detection
Generates structural fingerprints for comparing and clustering candidates.

**Key parameters:**
- `structures`: list of pymatgen Structure dicts
- `fingerprint_type`: method (`'structure_matcher'`, `'xrd'`, `'composition'`, default `'structure_matcher'`)
- `similarity_threshold`: 0-1, structures with similarity > this are duplicates (default 0.9)
- `identify_duplicates`: return duplicate groups (default `True`)

**Returns:**
```python
{
  "success": True,
  "num_structures": 50,
  "num_unique": 42,
  "duplicate_groups": [
    {"representative": 0, "duplicates": [5, 12]},  # Indices
    {"representative": 3, "duplicates": [18]}
  ],
  "fingerprints": [...],  # One per structure
  "similarity_matrix": [[1.0, 0.95, ...], ...]  # Optional
}
```

**Use for:** Deduplication before property retrieval saves time and database space.

---

### Phase 2: Property Retrieval

#### 6. `mp_search_materials` — Find Materials Project Entries
Search MP database for matching materials by composition, formula, or crystal system.

**Key parameters:**
- `formula`: exact formula (`"LiFePO4"`) or chemsys (`"Li-Fe-P-O"`)
- `crystal_system`: filter by symmetry (`"orthorhombic"`)
- `exclude_elements`: list of elements to exclude
- `limit`: max results (default 100)

**Returns:**
```python
{
  "success": True,
  "count": 3,
  "materials": [
    {
      "material_id": "mp-19017",
      "formula": "LiFePO4",
      "spacegroup": "Pnma",
      "energy_per_atom": -5.234,
      "formation_energy_per_atom": -2.341,
      "is_stable": True
    }
  ]
}
```

**Use as:** First property source - check if candidate exists in MP database.

---

#### 7. `mp_get_material_properties` — Retrieve Detailed MP Properties
Get comprehensive DFT-computed properties for a Materials Project material_id.

**Key parameters:**
- `material_id`: e.g., `"mp-19017"`
- `properties`: list of properties to retrieve, e.g., `["formation_energy_per_atom", "band_gap", "energy_per_atom", "magnetism"]`

**Returns:**
```python
{
  "success": True,
  "material_id": "mp-19017",
  "formula": "LiFePO4",
  "properties": {
    "formation_energy_per_atom": -2.341,  # eV/atom
    "band_gap": 0.8,  # eV
    "energy_per_atom": -5.234,  # eV/atom
    "is_stable": True,
    "symmetry": {"spacegroup": "Pnma", "number": 62}
  },
  "data_source": "Materials Project DFT"
}
```

**Priority:** Try this immediately after `mp_search_materials` finds a match.

---

#### 8. `ase_connect_or_create_db` — Initialize ASE Database
Connect to existing ASE database or create new one for caching screening results.

**Key parameters:**
- `db_path`: path to database file (e.g., `"screening_run_2024.db"`)

**Returns:**
```python
{
  "success": True,
  "db_path": "/path/to/screening_run_2024.db",
  "exists": True,
  "num_entries": 142  # Existing cached results
}
```

**Call once:** At start of screening workflow to initialize cache.

---

#### 9. `ase_query` — Query Cached Results
Search ASE database for previously computed/cached properties.

**Key parameters:**
- `db_path`: path to ASE database
- `formula`: chemical formula to search
- `properties`: which properties to retrieve (default: all available)

**Returns:**
```python
{
  "success": True,
  "count": 1,
  "entries": [
    {
      "id": 42,
      "formula": "LiFePO4",
      "properties": {
        "formation_energy_per_atom": -2.35,
        "band_gap": 0.82,
        "calculator": "ML_M3GNet",
        "timestamp": "2024-03-26T10:30:00"
      },
      "structure": {...}  # pymatgen dict
    }
  ]
}
```

**Priority:** Check after MP search fails - instant local lookup.

---

#### 10. `ml_relax_structure` — ML-Based Structure Optimization
Relax crystal structure using machine learning potentials (TensorNet models, PYG backend).

**Key parameters:**
- `input_structure`: pymatgen Structure dict or CIF/POSCAR string
- `model`: TensorNet model name (default `"TensorNet-MatPES-PBE-v2025.1-PES"`)
- `relax_cell`: whether to relax lattice parameters (default `True`)
- `fmax`: force convergence in eV/Å (default 0.1)
- `max_steps`: max optimization steps (default 500)

**Returns:**
```python
{
  "success": True,
  "converged": True,
  "final_structure": {...},  # Relaxed pymatgen dict
  "initial_energy": -245.3,  # eV
  "final_energy": -247.8,  # eV
  "energy_change": -2.5,  # eV
  "steps_taken": 45,
  "volume_change": -2.3  # % change
}
```

**Use before property prediction:** Ensures structures are at local energy minimum for better ML predictions.

**IMPORTANT:** Uses PYG backend - cannot mix with property prediction tools in same Python session (MatGL limitation).

---

#### 11. `ml_predict_eform` — Formation Energy Prediction
Predict formation energy using M3GNet/MEGNet models (DGL backend).

**Key parameters:**
- `input_structure`: pymatgen Structure dict or CIF/POSCAR string
- `model`: model name (default `"M3GNet-MP-2018.6.1-Eform"`, alternative `"MEGNet-MP-2018.6.1-Eform"`)

**Returns:**
```python
{
  "success": True,
  "formation_energy_eV_per_atom": -2.35,
  "total_formation_energy_eV": -65.8,
  "model_used": "M3GNet-MP-2018.6.1-Eform",
  "formula": "LiFePO4",
  "num_sites": 28,
  "interpretation": "Stable (exothermic formation)",
  "structure_info": {...}
}
```

**Typical ranges:**
- < -1 eV/atom: Highly stable (oxides, nitrides)
- -1 to 0 eV/atom: Moderately stable
- 0 to +1 eV/atom: Metastable/unstable
- > +1 eV/atom: Highly unstable

---

#### 12. `ml_predict_bandgap` — Band Gap Prediction
Predict electronic band gap using MEGNet model (DGL backend).

**Key parameters:**
- `input_structure`: pymatgen Structure dict or CIF/POSCAR string
- `model`: model name (default `"MEGNet-MP-2019.4.1-BandGap-mfi"`)

**Returns:**
```python
{
  "success": True,
  "band_gap_eV": 0.82,
  "model_used": "MEGNet-MP-2019.4.1-BandGap-mfi",
  "formula": "LiFePO4",
  "material_class": "Narrow Band Gap Semiconductor",
  "interpretation": "Narrow gap semiconductor (IR-sensitive, suitable for IR detectors, thermoelectrics)"
}
```

**Material classification:**
- < 0.1 eV: Metal/Conductor
- 0.1-1.0 eV: Narrow gap semiconductor
- 1.0-2.0 eV: Semiconductor (visible light)
- 2.0-3.0 eV: Wide gap semiconductor
- > 3.0 eV: Very wide gap/Insulator

---

#### 13. `ase_store_result` — Cache Results in Database
Store computed/predicted properties in ASE database for future reuse.

**Key parameters:**
- `db_path`: path to ASE database
- `structure`: pymatgen Structure dict
- `properties`: dict of property name→value pairs
- `calculator`: name of calculator/method used (e.g., `"ML_M3GNet"`, `"Materials_Project"`)
- `metadata`: optional additional info

**Returns:**
```python
{
  "success": True,
  "entry_id": 143,
  "db_path": "/path/to/screening_run_2024.db",
  "formula": "LiFePO4"
}
```

**Call after:** Every property retrieval/prediction to build cache.

---

### Phase 3: Ranking & Selection

#### 14. `multi_objective_ranker` — Rank Candidates by Multiple Criteria
Rank candidates using multi-objective optimization (Pareto or weighted sum).

**Key parameters:**
- `candidates`: list of candidate dicts with properties
- `objectives`: list of objective dicts specifying optimization goals
- `method`: ranking method (`"pareto"`, `"weighted_sum"`, `"topsis"`, default `"pareto"`)
- `return_pareto_front`: if `True`, return only non-dominated solutions (default `False`)

**Objective specification:**
```python
objectives = [
  {
    "property": "formation_energy_per_atom",
    "direction": "minimize",  # or "maximize"
    "weight": 0.4  # For weighted_sum method
  },
  {
    "property": "band_gap",
    "target": 1.5,  # Target value (minimize distance to this)
    "weight": 0.3
  },
  {
    "property": "stability_score",
    "direction": "maximize",
    "weight": 0.3
  }
]
```

**Returns:**
```python
{
  "success": True,
  "method": "pareto",
  "num_candidates": 42,
  "pareto_front_size": 12,  # Non-dominated solutions
  "ranked_candidates": [
    {
      "rank": 1,
      "candidate_id": "cand_042",
      "formula": "LiFePO4",
      "properties": {...},
      "scores": {"formation_energy": 0.95, "band_gap": 0.88},
      "total_score": 0.92,
      "pareto_rank": 1
    }
  ]
}
```

---

## MANDATORY Workflow Algorithm

**Execute this exact sequence for every screening run. Follow each step precisely.**

### QUICK EXECUTION SUMMARY

**FOR LLMs: This is the complete execution order you MUST follow:**

1. **STEP 0 - INIT**: Initialize tracking structures and ASE database
2. **STEP 1 - VALIDATE** (Phase 1): For each candidate → validate → analyze → deduplicate
   - REJECT if invalid, CONTINUE to next
3. **STEP 2 - PROPERTIES** (Phase 2): For each validated candidate:
   - TRY Materials Project (best quality) → IF success, CACHE and CONTINUE to next
   - ELSE TRY ASE database (cached) → IF success, CONTINUE to next  
   - ELSE FALLBACK to ML prediction → predict, CACHE, CONTINUE to next
4. **STEP 3 - FILTER** (Phase 3): For each candidate with properties → check criteria → KEEP or REJECT
5. **STEP 4 - RANK** (Phase 4): Multi-objective ranking → confidence weighting
6. **STEP 5 - OUTPUT**: Generate comprehensive screening report

**CRITICAL RULES:**
- Never skip validation (Step 1)
- Always try data sources in order: MP → ASE → ML (never skip ahead)
- Always cache results in ASE database
- Never silently exclude - always log rejection reasons
- Mark ML predictions for DFT verification if high-scoring

---

### STEP 0: INITIALIZATION

**Input:** `candidates` = list of N candidate structures from candidate-generator skill

**Step 0.1:** Initialize tracking structures
```
validated_candidates = []
rejected_candidates = []
candidates_with_properties = []
filtered_candidates = []
```

**Step 0.2:** Initialize ASE database (execute once per screening run)
```
CALL ase_connect_or_create_db(db_path="screening_YYYYMMDD.db")
STORE db_path for subsequent calls
```

---

### STEP 1: VALIDATION AND ANALYSIS (Phase 1)

**Purpose:** Filter out invalid structures before expensive operations

**Step 1.0:** For each candidate in candidates:

**Step 1.1:** Validate structure integrity
```
CALL structure_validator(
    structure=candidate.structure,
    check_composition=True,
    check_charge_neutrality=True,
    check_geometry=True
)

IF result.is_valid == False:
    APPEND candidate to rejected_candidates
    SET candidate.rejection_reason = result.issues
    CONTINUE to next candidate  # Skip remaining steps for this candidate
ELSE:
    # Structure is valid, proceed
```

**Step 1.2:** Analyze chemical composition
```
CALL composition_analyzer(
    structure=candidate.structure,
    analyze_oxidation=True,
    compute_descriptors=True
)

STORE result.elements in candidate.elements
STORE result.oxidation_states in candidate.oxidation_states
STORE result.composition_type in candidate.composition_type

IF result.warnings contains critical issues (radioactive, exotic):
    FLAG candidate for manual review
```

**Step 1.3:** (OPTIONAL) Check thermodynamic stability
```
CALL stability_analyzer(
    structure=candidate.structure,
    energy_tolerance=0.1
)

IF result.stability_category == "unstable" AND result.energy_above_hull > 0.3:
    # Highly unstable - reject OR flag for review based on requirements
    OPTION A: APPEND to rejected_candidates, CONTINUE to next candidate
    OPTION B: FLAG candidate.requires_stability_review = True
```

**Step 1.4:** Extract structural features
```
CALL structure_analyzer(
    structure=candidate.structure,
    compute_symmetry=True,
    analyze_coordination=True
)

STORE result.spacegroup in candidate.spacegroup
STORE result.lattice_parameters in candidate.lattice
STORE result.coordination_environments in candidate.coordination
```

**Step 1.5:** (OPTIONAL) Deduplicate similar structures
```
# Run on entire candidate set, not individual structures
IF deduplication_enabled:
    CALL structure_fingerprinter(
        structures=[c.structure for c in candidates if c not in rejected_candidates],
        similarity_threshold=0.9,
        identify_duplicates=True
    )
    
    FOR each duplicate_group in result.duplicate_groups:
        KEEP duplicate_group.representative
        APPEND duplicate_group.duplicates to rejected_candidates
        SET rejection_reason = "Duplicate of candidate {representative_id}"
```

**Step 1.6:** Compile validated candidates
```
validated_candidates = [c for c in candidates if c not in rejected_candidates]
```

---

### STEP 2: HIERARCHICAL PROPERTY RETRIEVAL (Phase 2)

**Purpose:** Obtain properties using data source hierarchy: Materials Project → ASE cache → ML prediction

**Rule:** ALWAYS try sources in order. Do NOT skip to ML without checking MP and ASE first.

**Step 2.0:** For each candidate in validated_candidates:

**Step 2.1:** Attempt Materials Project lookup (FIRST PRIORITY)
```
SET candidate.property_source = None

CALL mp_search_materials(
    formula=candidate.formula,
    limit=10
)

IF result.success AND result.count > 0:
    # Found in Materials Project
    
    IF result.count == 1:
        SET mp_entry = result.materials[0]
    ELSE IF result.count > 1:
        # Multiple matches - select most stable
        SORT result.materials by energy_per_atom (ascending)
        SET mp_entry = result.materials[0]
    
    # Retrieve detailed properties
    CALL mp_get_material_properties(
        material_id=mp_entry.material_id,
        properties=["formation_energy_per_atom", "band_gap", "energy_per_atom", "is_stable"]
    )
    
    STORE result.properties in candidate.properties
    SET candidate.property_source = "Materials_Project"
    SET candidate.material_id = mp_entry.material_id
    SET candidate.confidence = "high"
    
    # Cache in ASE database for future runs
    CALL ase_store_result(
        db_path=db_path,
        structure=candidate.structure,
        properties=candidate.properties,
        calculator="Materials_Project",
        metadata={"material_id": mp_entry.material_id}
    )
    
    APPEND candidate to candidates_with_properties
    CONTINUE to next candidate  # Properties obtained, move to next
ELSE:
    # Not found in Materials Project, proceed to Step 2.2
```

**Step 2.2:** Attempt ASE database lookup (SECOND PRIORITY)
```
# Only reached if Step 2.1 failed

CALL ase_query(
    db_path=db_path,
    formula=candidate.formula
)

IF result.success AND result.count > 0:
    # Found in ASE cache
    
    SET ase_entry = result.entries[0]  # Most recent entry
    STORE ase_entry.properties in candidate.properties
    SET candidate.property_source = "ASE_cached"
    SET candidate.ase_id = ase_entry.id
    SET candidate.calculator = ase_entry.calculator
    
    # Set confidence based on original calculator
    IF ase_entry.calculator == "Materials_Project" OR ase_entry.calculator contains "DFT":
        SET candidate.confidence = "high"
    ELSE IF ase_entry.calculator contains "ML":
        SET candidate.confidence = "medium"
    ELSE:
        SET candidate.confidence = "medium-low"
    
    APPEND candidate to candidates_with_properties
    CONTINUE to next candidate  # Properties obtained, move to next
ELSE:
    # Not in cache either, proceed to Step 2.3
```

**Step 2.3:** ML Prediction (THIRD PRIORITY - FALLBACK)
```
# Only reached if Steps 2.1 and 2.2 both failed

SET candidate.property_source = "ML_prediction"

# Optional: Relax structure first (recommended for better accuracy)
IF relax_structures_enabled:
    TRY:
        CALL ml_relax_structure(
            input_structure=candidate.structure,
            fmax=0.1,
            max_steps=500
        )
        
        IF result.converged:
            SET candidate.structure = result.final_structure
            SET candidate.was_relaxed = True
        ELSE:
            # Use unrelaxed structure
            SET candidate.was_relaxed = False
    EXCEPT error:
        LOG "Relaxation failed for {candidate.formula}: {error}"
        SET candidate.was_relaxed = False
        # Continue with unrelaxed structure

# Predict formation energy
TRY:
    CALL ml_predict_eform(
        input_structure=candidate.structure,
        model="M3GNet-MP-2018.6.1-Eform"
    )
    SET candidate.properties.formation_energy_per_atom = result.formation_energy_eV_per_atom
    SET candidate.properties.eform_model = result.model_used
EXCEPT error:
    # Try alternative model
    TRY:
        CALL ml_predict_eform(
            input_structure=candidate.structure,
            model="MEGNet-MP-2018.6.1-Eform"
        )
        SET candidate.properties.formation_energy_per_atom = result.formation_energy_eV_per_atom
        SET candidate.properties.eform_model = result.model_used
    EXCEPT error2:
        LOG "Both ML eform models failed for {candidate.formula}"
        SET candidate.properties.formation_energy_per_atom = None
        SET candidate.requires_dft = True

# Predict band gap
TRY:
    CALL ml_predict_bandgap(
        input_structure=candidate.structure,
        model="MEGNet-MP-2019.4.1-BandGap-mfi"
    )
    SET candidate.properties.band_gap = result.band_gap_eV
    SET candidate.properties.material_class = result.material_class
    SET candidate.properties.bandgap_model = result.model_used
EXCEPT error:
    LOG "ML bandgap prediction failed for {candidate.formula}"
    SET candidate.properties.band_gap = None
    SET candidate.requires_dft = True

SET candidate.confidence = "medium"

# Cache results in ASE database for future runs
CALL ase_store_result(
    db_path=db_path,
    structure=candidate.structure,
    properties=candidate.properties,
    calculator="ML_M3GNet/MEGNet",
    metadata={"models": [properties.eform_model, properties.bandgap_model]}
)

APPEND candidate to candidates_with_properties
```

---

### STEP 3: CRITERIA-BASED FILTERING (Phase 3)

**Purpose:** Apply hard constraints to remove candidates that don't meet requirements

**Step 3.1:** Define screening criteria (application-specific)
```
# Example for battery cathodes:
screening_criteria = {
    "max_formation_energy": 0.0,  # eV/atom
    "min_band_gap": 0.5,          # eV
    "max_band_gap": 2.0,          # eV
    "min_stability_score": 0.7,   # if available
}
```

**Step 3.2:** For each candidate in candidates_with_properties:

**Step 3.2.1:** Check all criteria
```
SET all_criteria_met = True
SET failure_reasons = []

# Check formation energy
IF candidate.properties.formation_energy_per_atom is not None:
    IF candidate.properties.formation_energy_per_atom > screening_criteria.max_formation_energy:
        SET all_criteria_met = False
        APPEND "formation_energy too high: {value} > {threshold}" to failure_reasons

# Check band gap
IF candidate.properties.band_gap is not None:
    IF candidate.properties.band_gap < screening_criteria.min_band_gap:
        SET all_criteria_met = False
        APPEND "band_gap too low: {value} < {min}" to failure_reasons
    IF candidate.properties.band_gap > screening_criteria.max_band_gap:
        SET all_criteria_met = False
        APPEND "band_gap too high: {value} > {max}" to failure_reasons

# Check stability if available
IF candidate.properties.stability_score is not None:
    IF candidate.properties.stability_score < screening_criteria.min_stability_score:
        SET all_criteria_met = False
        APPEND "stability_score too low: {value} < {min}" to failure_reasons

# Add any other domain-specific criteria checks here
```

**Step 3.2.2:** Filter based on criteria
```
IF all_criteria_met:
    APPEND candidate to filtered_candidates
ELSE:
    APPEND candidate to rejected_candidates
    SET candidate.rejection_reason = ", ".join(failure_reasons)
    SET candidate.rejection_phase = "criteria_filtering"
```

---

### STEP 4: MULTI-OBJECTIVE RANKING (Phase 4)

**Purpose:** Order remaining candidates by desirability using multi-objective optimization

**Step 4.1:** Define optimization objectives (application-specific)
```
# Example for battery cathodes:
objectives = [
    {
        "property": "formation_energy_per_atom",
        "direction": "minimize",
        "weight": 0.4
    },
    {
        "property": "band_gap",
        "target": 1.0,  # Target value
        "weight": 0.3
    },
    {
        "property": "stability_score",
        "direction": "maximize",
        "weight": 0.3
    }
]
```

**Step 4.2:** Apply multi-objective ranking
```
CALL multi_objective_ranker(
    candidates=filtered_candidates,
    objectives=objectives,
    method="pareto",  # or "weighted_sum", "topsis"
    return_pareto_front=False
)

SET ranked_candidates = result.ranked_candidates
```

**Step 4.3:** Apply confidence-weighted scoring (optional but recommended)
```
confidence_weights = {
    "Materials_Project": 1.0,
    "ASE_cached": 0.9,  # Depends on original calculator
    "ML_prediction": 0.7
}

FOR each candidate in ranked_candidates:
    SET confidence_factor = confidence_weights[candidate.property_source]
    SET candidate.adjusted_score = candidate.total_score * confidence_factor
    
    # Flag high-scoring ML predictions for DFT verification
    IF candidate.total_score > 0.8 AND candidate.property_source == "ML_prediction":
        SET candidate.recommend_dft_verification = True
```

---

### STEP 5: OUTPUT GENERATION

**Step 5.1:** Generate comprehensive screening report
```
screening_report = {
    "screening_summary": {
        "total_input": len(candidates),
        "validated": len(validated_candidates),
        "with_properties": len(candidates_with_properties),
        "passed_filters": len(filtered_candidates),
        "ranked": len(ranked_candidates),
        "timestamp": current_timestamp,
        "screening_time_seconds": elapsed_time
    },
    
    "data_source_breakdown": {
        "materials_project": count where property_source == "Materials_Project",
        "ase_cached": count where property_source == "ASE_cached",
        "ml_predicted": count where property_source == "ML_prediction"
    },
    
    "top_candidates": ranked_candidates[:10],  # Top 10
    
    "rejected_candidates": [
        {
            "formula": c.formula,
            "reason": c.rejection_reason,
            "phase": c.rejection_phase
        }
        for c in rejected_candidates
    ],
    
    "property_distributions": compute_statistics(candidates_with_properties),
    
    "pareto_front": extract_pareto_front(ranked_candidates) if method == "pareto",
    
    "database_info": {
        "db_path": db_path,
        "total_entries": query_db_count(db_path),
        "new_entries": count_new_entries
    }
}

RETURN screening_report
```

---

## Critical Decision Algorithms

### DECISION 1: Structure Relaxation Before ML Prediction

**Logic:**
```
IF candidate.source in ["DFT", "Materials_Project", "experimental"]:
    # Already optimized/validated
    SET relax_structure = False
ELSE IF candidate.structure_type == "ionic_solid" AND candidate.symmetry == "high":
    # Simple ionic solids usually already at minimum
    SET relax_structure = False
ELSE:
    # Unvalidated or complex structure
    SET relax_structure = True

IF relax_structure:
    TRY:
        CALL ml_relax_structure(candidate.structure)
        USE relaxed_structure for predictions
    EXCEPT error:
        LOG "Relaxation failed: {error}"
        USE original_structure for predictions
```

**Reasoning:** ML models trained on DFT-optimized geometries. Relaxation takes 5-10s but improves prediction accuracy significantly for unoptimized structures.

---

### DECISION 2: ML Prediction Failure Handling

**Algorithm:**
```
TRY:
    result = ml_predict_eform(structure, model="M3GNet-MP-2018.6.1-Eform")
    SET candidate.properties.formation_energy = result.value
    RETURN success
EXCEPT error1:
    LOG "Primary model failed: {error1}"
    
    TRY:
        result = ml_predict_eform(structure, model="MEGNet-MP-2018.6.1-Eform")
        SET candidate.properties.formation_energy = result.value
        SET candidate.model_fallback = True
        RETURN success
    EXCEPT error2:
        LOG "Backup model failed: {error2}"
        
        # Final fallback: Materials Project similarity search
        TRY:
            similar_materials = mp_search_materials(
                elements=candidate.elements,
                crystal_system=candidate.crystal_system
            )
            IF similar_materials.count > 0:
                SET candidate.properties.formation_energy = estimate_from_similar(similar_materials)
                SET candidate.confidence = "low"
                SET candidate.estimated_from_similar = True
                RETURN partial_success
        EXCEPT error3:
            # All attempts failed
            SET candidate.properties.formation_energy = None
            SET candidate.requires_dft = True
            SET candidate.ml_prediction_failed = True
            SET candidate.errors = [error1, error2, error3]
            RETURN failure

# NEVER silently exclude - always include with failure flag
```

**Key Rule:** Never exclude candidates silently. Always log failure reasons and mark for DFT verification.

---

### DECISION 3: Multiple Materials Project Matches

**Algorithm:**
```
CALL mp_search_materials(formula=candidate.formula)

IF result.count == 0:
    RETURN no_match  # Proceed to ASE/ML

ELSE IF result.count == 1:
    SET mp_entry = result.materials[0]
    USE mp_entry for properties
    RETURN single_match

ELSE IF result.count > 1:
    # Multiple matches - need disambiguation
    
    # Check if exploring metastable phases
    IF screening_mode == "include_metastable":
        # Keep all polymorphs as separate candidates
        FOR each material in result.materials:
            CREATE new_candidate from material
            TAG new_candidate.polymorph = material.spacegroup
            TAG new_candidate.stability_rank = rank_by_energy
            ADD new_candidate to polymorph_list
        RETURN multiple_matches
    
    ELSE:
        # Default: take most stable
        SORT result.materials by energy_per_atom ascending
        SET mp_entry = result.materials[0]
        
        # Log alternative polymorphs
        SET candidate.alternative_polymorphs = [
            m.material_id for m in result.materials[1:]
        ]
        USE mp_entry for properties
        RETURN most_stable_match
```

---

### DECISION 4: Batching Strategy for Performance

**Algorithm:**
```
# Phase 1: Validation (no batching needed - fast and sequential)
FOR candidate in candidates:
    validate(candidate)  # ~0.1s each

# Phase 2: MP API calls (BATCH)
mp_candidates = [c for c in candidates if not c.rejected]
formulas = [c.formula for c in mp_candidates]

SET batch_size = 50  # API rate limit / performance balance
FOR formula_batch in chunks(formulas, batch_size):
    mp_results = mp_search_materials(formulas=formula_batch)
    PROCESS results in parallel
    APPLY rate limiting delay (0.1s between batches)

# Phase 3: ASE queries (no batching needed - instant local DB)
FOR candidate in mp_unmatched_candidates:
    ase_query(candidate.formula)  # ~0.01s each

# Phase 4: ML predictions (CONDITIONAL BATCHING)
ml_candidates = [c for c in candidates if needs_ml_prediction]

IF gpu_available AND gpu_memory > required_memory:
    # Parallel GPU inference
    SET batch_size = calculate_batch_size(gpu_memory, model_size)
    FOR structure_batch in chunks(ml_candidates, batch_size):
        results = ml_predict_batch(structure_batch)
ELSE:
    # Sequential CPU inference (lower memory, predictable)
    FOR candidate in ml_candidates:
        result = ml_predict(candidate.structure)
```

**Performance Guidelines:**
- MP API: Always batch (50 per batch)
- ASE: Never batch (instant anyway)
- ML: Batch only if GPU available and sufficient memory

---

### DECISION 5: Confidence-Weighted Ranking

**Algorithm:**
```
# Define confidence weights by data source
confidence_map = {
    "Materials_Project": 1.0,
    "ASE_cached_MP": 1.0,
    "ASE_cached_DFT": 1.0,
    "ASE_cached_ML_M3GNet": 0.8,
    "ASE_cached_ML_MEGNet": 0.7,
    "ML_M3GNet": 0.75,
    "ML_MEGNet": 0.65,
    "ML_estimated": 0.5
}

FOR candidate in ranked_candidates:
    # Get base score from multi-objective ranking
    base_score = candidate.total_score
    
    # Apply confidence weighting
    confidence = confidence_map.get(candidate.property_source, 0.5)
    adjusted_score = base_score * confidence
    
    SET candidate.confidence_factor = confidence
    SET candidate.adjusted_score = adjusted_score
    
    # Decision logic for DFT verification recommendation
    IF base_score > 0.8 AND confidence < 0.8:
        # High-scoring but low-confidence candidate
        SET candidate.recommend_dft_verification = True
        SET candidate.dft_priority = "high"
    ELSE IF base_score > 0.6 AND confidence < 0.7:
        SET candidate.recommend_dft_verification = True
        SET candidate.dft_priority = "medium"
    ELSE IF candidate.property_source contains "ML" AND base_score > 0.5:
        SET candidate.recommend_dft_verification = True
        SET candidate.dft_priority = "low"
    ELSE:
        SET candidate.recommend_dft_verification = False
    
    # Re-rank by adjusted score
    SORT candidates by adjusted_score descending
```

**Key Principle:** High scores with low confidence = priority for DFT verification. Don't discard, but flag appropriately.

---

## Error Handling Procedures

### ERROR TYPE 1: Network Failures (Materials Project API)

**Algorithm:**
```
FUNCTION mp_api_call_with_retry(api_function, params):
    SET max_retries = 3
    SET base_delay = 1.0  # seconds
    
    FOR attempt in range(0, max_retries):
        TRY:
            result = api_function(params)
            RETURN (success=True, result=result)
        
        EXCEPT NetworkError as e:
            LOG "MP API network error (attempt {attempt+1}/{max_retries}): {e}"
            
            IF attempt < max_retries - 1:
                # Exponential backoff
                delay = base_delay * (2 ** attempt)
                WAIT delay seconds
                CONTINUE
            ELSE:
                # All retries exhausted
                LOG "MP API failed after {max_retries} attempts for {params}"
                RETURN (success=False, error=e)
        
        EXCEPT AuthenticationError as e:
            # No point retrying
            LOG "MP API authentication failed: {e}"
            RETURN (success=False, error=e, no_retry=True)
        
        EXCEPT RateLimitError as e:
            LOG "MP API rate limit hit (attempt {attempt+1}/{max_retries})"
            
            IF attempt < max_retries - 1:
                # Longer wait for rate limiting
                delay = 60  # Wait 1 minute
                WAIT delay seconds
                CONTINUE
            ELSE:
                RETURN (success=False, error=e)

# Usage in workflow
result = mp_api_call_with_retry(mp_search_materials, {"formula": formula})
IF result.success:
    PROCESS result.data
ELSE:
    # Fall back to ASE/ML
    LOG "Skipping MP, proceeding to ASE cache"
    CONTINUE to Step 3.2
```

---

### ERROR TYPE 2: ML Model Failures

**Algorithm:**
```
FUNCTION ml_predict_with_fallback(structure, property_type):
    # Define model hierarchy (best to worst)
    IF property_type == "formation_energy":
        models = ["M3GNet-MP-2018.6.1-Eform", "MEGNet-MP-2018.6.1-Eform"]
    ELSE IF property_type == "band_gap":
        models = ["MEGNet-MP-2019.4.1-BandGap-mfi"]
    
    SET errors = []
    
    FOR model in models:
        TRY:
            result = ml_predict(structure, model=model, property=property_type)
            RETURN (success=True, value=result.value, model=model)
        
        EXCEPT ModelLoadError as e:
            LOG "Model {model} failed to load: {e}"
            APPEND e to errors
            CONTINUE  # Try next model
        
        EXCEPT PredictionError as e:
            LOG "Prediction failed with {model}: {e}"
            APPEND e to errors
            CONTINUE  # Try next model
        
        EXCEPT InsufficientMemoryError as e:
            LOG "Out of memory with {model}: {e}"
            # Try to clear memory and retry once
            CALL clear_model_cache()
            TRY:
                result = ml_predict(structure, model=model, property=property_type)
                RETURN (success=True, value=result.value, model=model)
            EXCEPT:
                APPEND e to errors
                CONTINUE
    
    # All models failed
    LOG "All ML models failed for {structure.formula}: {errors}"
    RETURN (
        success=False,
        value=None,
        errors=errors,
        requires_dft=True
    )

# Usage in workflow
result = ml_predict_with_fallback(candidate.structure, "formation_energy")
IF result.success:
    SET candidate.properties.formation_energy = result.value
    SET candidate.ml_model_used = result.model
ELSE:
    SET candidate.properties.formation_energy = None
    SET candidate.requires_dft = True
    SET candidate.ml_errors = result.errors
    # Continue with candidate but flag for DFT
```

---

### ERROR TYPE 3: Structure Validation Failures

**Algorithm:**
```
FUNCTION handle_validation_failure(candidate, validation_result):
    SET rejection_criteria = {
        "overlapping_atoms": True,        # Always reject
        "invalid_composition": True,      # Always reject
        "charge_not_neutral": True,       # Always reject
        "geometry_invalid": True,         # Always reject
        "unusual_distances": False,       # Flag but don't reject
        "exotic_elements": False          # Flag but don't reject
    }
    
    SET should_reject = False
    SET critical_issues = []
    SET warnings = []
    
    FOR issue in validation_result.issues:
        IF rejection_criteria[issue.type]:
            SET should_reject = True
            APPEND issue to critical_issues
        ELSE:
            APPEND issue to warnings
    
    IF should_reject:
        SET candidate.status = "rejected"
        SET candidate.rejection_reason = format_issues(critical_issues)
        SET candidate.rejection_phase = "validation"
        APPEND candidate to rejected_candidates
        LOG "Rejected {candidate.formula}: {critical_issues}"
        RETURN reject
    
    ELSE IF len(warnings) > 0:
        SET candidate.validation_warnings = warnings
        SET candidate.requires_manual_review = True
        LOG "Validated with warnings {candidate.formula}: {warnings}"
        RETURN accept_with_warnings
    
    ELSE:
        RETURN accept

# Usage in workflow
validation = structure_validator(candidate.structure)
IF NOT validation.is_valid:
    action = handle_validation_failure(candidate, validation)
    IF action == reject:
        CONTINUE to next candidate  # Skip this one
```

---

### ERROR TYPE 4: Database I/O Failures

**Algorithm:**
```
FUNCTION safe_database_operation(operation, db_path, data, max_retries=3):
    FOR attempt in range(0, max_retries):
        TRY:
            result = operation(db_path, data)
            RETURN (success=True, result=result)
        
        EXCEPT DatabaseLockError as e:
            # Database locked by another process
            LOG "Database locked (attempt {attempt+1}/{max_retries})"
            IF attempt < max_retries - 1:
                WAIT (0.5 * (attempt + 1)) seconds
                CONTINUE
            ELSE:
                LOG "Database lock timeout: {e}"
                RETURN (success=False, error=e, recoverable=True)
        
        EXCEPT DatabaseCorrupted as e:
            # Critical error - cannot recover
            LOG "Database corrupted: {e}"
            RETURN (success=False, error=e, recoverable=False)
        
        EXCEPT DiskFullError as e:
            LOG "Disk full: {e}"
            RETURN (success=False, error=e, recoverable=False)
        
        EXCEPT PermissionError as e:
            LOG "Permission denied: {e}"
            RETURN (success=False, error=e, recoverable=False)

# Usage for caching (non-critical)
result = safe_database_operation(ase_store_result, db_path, candidate_data)
IF NOT result.success:
    LOG "Failed to cache {candidate.formula}: {result.error}"
    # Continue anyway - caching is nice-to-have, not critical
    SET candidate.cached = False
ELSE:
    SET candidate.cached = True

# Usage for retrieval (critical)
result = safe_database_operation(ase_connect_or_create_db, db_path, None)
IF NOT result.success AND NOT result.recoverable:
    # Critical failure - cannot proceed
    RAISE "Cannot initialize database: {result.error}"
```

---

### ERROR TYPE 5: Memory Exhaustion

**Algorithm:**
```
FUNCTION handle_memory_exhaustion(current_operation, state):
    LOG "Memory exhaustion during {current_operation}"
    
    # Actions in order of preference
    ACTIONS = [
        "clear_model_cache",
        "reduce_batch_size",
        "switch_to_sequential",
        "skip_relaxation",
        "force_garbage_collection"
    ]
    
    FOR action in ACTIONS:
        IF action == "clear_model_cache":
            TRY:
                CALL unload_ml_models()
                CALL clear_torch_cache()
                LOG "Cleared model cache"
                RETURN retry
        
        ELSE IF action == "reduce_batch_size":
            IF current_batch_size > 1:
                SET current_batch_size = max(1, current_batch_size // 2)
                LOG "Reduced batch size to {current_batch_size}"
                RETURN retry
        
        ELSE IF action == "switch_to_sequential":
            IF parallel_processing_enabled:
                SET parallel_processing = False
                LOG "Switched to sequential processing"
                RETURN retry
        
        ELSE IF action == "skip_relaxation":
            IF relaxation_enabled:
                SET relaxation_enabled = False
                LOG "Disabled structure relaxation to save memory"
                RETURN retry
        
        ELSE IF action == "force_garbage_collection":
            CALL gc.collect()
            LOG "Forced garbage collection"
            RETURN retry
    
    # All recovery attempts failed
    LOG "Cannot recover from memory exhaustion"
    RETURN abort

# Usage
TRY:
    result = ml_relax_structure(structure)
EXCEPT MemoryError:
    action = handle_memory_exhaustion("ml_relax_structure", current_state)
    IF action == retry:
        TRY:
            result = ml_relax_structure(structure)
        EXCEPT MemoryError:
            # Still failing, skip relaxation for this candidate
            LOG "Skipping relaxation for {candidate.formula}"
            SET candidate.was_relaxed = False
    ELSE IF action == abort:
        RAISE "Cannot continue - insufficient memory"
```

---

### ERROR RECOVERY PRIORITY MATRIX

```
Operation Type       | Critical? | Retry? | Fallback                  | Abort?
---------------------|-----------|--------|---------------------------|-------
Structure validation | Yes       | No     | Reject candidate          | No
MP API lookup        | No        | Yes    | ASE cache → ML            | No
ASE DB connection    | Yes       | Yes    | Create new DB             | Yes if fails
ASE DB query         | No        | Yes    | ML prediction             | No
ASE DB store         | No        | Yes    | Continue without cache    | No
ML prediction        | No        | Yes    | Alternative model → DFT   | No
ML relaxation        | No        | Yes    | Skip relaxation           | No
Multi-obj ranking    | Yes       | No     | Simple weighted sum       | No
```

**Key Principle:** Never silently fail. Always log errors, attempt recovery, and mark candidates appropriately for manual review or DFT verification.

---

## Performance Optimization

### Estimated Times (100 candidates)

| Operation | Time per candidate | Total (100) | Bottleneck |
|-----------|-------------------|-------------|------------|
| Structure validation | 0.1s | 10s | CPU |
| Composition analysis | 0.05s | 5s | CPU |
| Stability analysis | 0.5s | 50s | MP API |
| MP property lookup | 0.3s | 30s | API rate limit |
| ASE database query | 0.01s | 1s | Disk I/O |
| ML structure relaxation | 5-10s | 8-15 min | GPU/CPU |
| ML property prediction | 0.5-2s | 1-3 min | Model inference |
| Multi-objective ranking | 0.1s | 10s | CPU |

**Total screening time:**
- **Best case** (80% in MP): ~2 minutes
- **Typical case** (50% in MP, 30% in ASE, 20% ML): ~5 minutes
- **Worst case** (all ML predictions with relaxation): ~20 minutes

### Optimization Tips

1. **Deduplicate early:** Use `structure_fingerprinter` before property retrieval
2. **Batch MP API calls:** Reduce network overhead
3. **Skip relaxation for ionic crystals:** Already at energy minimum
4. **Parallelize ML predictions:** If using GPU and have memory
5. **Cache aggressively:** Every property retrieval should go to ASE database
6. **Filter by stability first:** Eliminates unstable candidates before ML

---

## Output Report Structure

```python
{
  "screening_summary": {
    "total_input": 100,
    "validated": 85,
    "duplicates_removed": 8,
    "with_properties": 77,
    "passed_filters": 42,
    "top_candidates": 10,
    "timestamp": "2024-03-26T10:30:00",
    "screening_time_seconds": 325
  },
  
  "data_source_breakdown": {
    "materials_project": 38,  # High confidence
    "ase_cached": 24,          # Medium-high confidence
    "ml_predicted": 15         # Medium confidence
  },
  
  "top_candidates": [
    {
      "rank": 1,
      "formula": "LiFePO4",
      "structure": {...},
      "properties": {
        "formation_energy_per_atom": -2.341,
        "band_gap": 0.8,
        "stability_score": 0.95,
        "source": "Materials_Project",
        "confidence": "high"
      },
      "scores": {
        "formation_energy_score": 0.98,
        "band_gap_score": 0.87,
        "stability_score": 0.95,
        "total_score": 0.94
      },
      "recommendation": "Top priority - DFT-verified properties",
      "material_id": "mp-19017",
      "requires_dft": false
    },
    {
      "rank": 2,
      "formula": "LiMnPO4",
      "structure": {...},
      "properties": {
        "formation_energy_per_atom": -2.15,
        "band_gap": 1.2,
        "stability_score": 0.88,
        "source": "ML_M3GNet",
        "confidence": "medium"
      },
      "scores": {
        "formation_energy_score": 0.92,
        "band_gap_score": 0.95,
        "stability_score": 0.88,
        "total_score": 0.90
      },
      "recommendation": "High priority - consider DFT verification",
      "requires_dft": true
    }
  ],
  
  "rejected_candidates": [
    {"formula": "Li5FeO4", "reason": "Invalid structure - overlapping atoms"},
    {"formula": "Li3P", "reason": "Formation energy > 0 eV/atom (unstable)"},
    {"formula": "LiFeO2", "reason": "Band gap outside target range"}
  ],
  
  "property_distributions": {
    "formation_energy": {"min": -3.2, "max": -0.8, "mean": -2.1, "std": 0.6},
    "band_gap": {"min": 0.2, "max": 3.5, "mean": 1.4, "std": 0.8}
  },
  
  "pareto_front": {
    "size": 12,
    "candidates": [1, 2, 5, 7, 11, 15, 18, 23, 29, 34, 38, 41]  # Ranks
  },
  
  "database_info": {
    "db_path": "/workdir/screening_2024-03-26.db",
    "total_entries": 165,
    "new_entries": 23
  }
}
```

---

## Example Workflows

### Example 1: Battery Cathode Screening

```python
# Goal: Find stable olivine-structure cathodes with moderate band gap

objectives = [
  {"property": "formation_energy_per_atom", "direction": "minimize", "weight": 0.4},
  {"property": "band_gap", "target": 1.0, "weight": 0.3},
  {"property": "stability_score", "direction": "maximize", "weight": 0.3}
]

screening_criteria = {
  "max_formation_energy": 0.0,  # Must be thermodynamically stable
  "min_band_gap": 0.5,           # Semiconducting
  "max_band_gap": 2.0,
  "min_stability_score": 0.7
}

# Run screening with candidate-screener skill
```

### Example 2: Solar Absorber Discovery

```python
# Goal: Find materials with band gap ~1.5 eV (optimal for solar)

objectives = [
  {"property": "band_gap", "target": 1.5, "weight": 0.5},
  {"property": "formation_energy_per_atom", "direction": "minimize", "weight": 0.3},
  {"property": "absorption_coefficient", "direction": "maximize", "weight": 0.2}
]

screening_criteria = {
  "min_band_gap": 1.0,
  "max_band_gap": 2.0,
  "max_formation_energy": -0.5,  # Reasonably stable
  "min_stability_score": 0.6
}
```

### Example 3: Thermoelectric Material Search

```python
# Goal: Narrow band gap, high stability

objectives = [
  {"property": "band_gap", "direction": "minimize", "weight": 0.4},
  {"property": "formation_energy_per_atom", "direction": "minimize", "weight": 0.4},
  {"property": "effective_mass", "direction": "minimize", "weight": 0.2}
]

screening_criteria = {
  "max_band_gap": 0.5,  # Narrow gap semiconductor
  "max_formation_energy": 0.0,
  "min_stability_score": 0.8  # High stability required
}
```

---

## Integration with Other Skills

### Input from candidate-generator

```python
# candidate-generator outputs list of structures
candidates = [
  {"formula": "LiFePO4", "structure": {...}, "method": "substitution"},
  {"formula": "LiMnPO4", "structure": {...}, "method": "substitution"},
  ...
]

# Feed directly to candidate-screener
screened = candidate_screener(candidates=candidates, ...)
```

### Output to synthesis-planner

```python
# Top candidates from screening go to synthesis planning
top_10 = screening_result["top_candidates"][:10]

for candidate in top_10:
    synthesis_route = synthesis_planner(
        target_material=candidate["formula"],
        ...
    )
```

---