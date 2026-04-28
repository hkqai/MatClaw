# Workflow Algorithm: Complete Execution Sequence

**This is the MANDATORY execution sequence for candidate screening. Follow every step precisely.**

## Quick Execution Summary

**FOR LLMs: This is the complete execution order you MUST follow:**

1. **STEP 0 - INIT**: Initialize tracking structures and ASE database
2. **STEP 1 - VALIDATE** (Phase 1): For each candidate → validate → analyze → deduplicate
   - REJECT if invalid, CONTINUE to next
3. **STEP 2 - PROPERTIES** (Phase 2): For each validated candidate:
   - TRY Materials Project (best quality) → IF success, CACHE and CONTINUE to next
   - ELSE TRY ASE database (cached) → IF success, CONTINUE to next  
   - ELSE ML-based calculation: Relax structure → MatGL predictions (formation energy, band gap) + matcalc calculations (mechanical, vibrational, surface properties as needed) → CACHE and CONTINUE
4. **STEP 3 - FILTER** (Phase 3): For each candidate with properties → check criteria → KEEP or REJECT
5. **STEP 4 - RANK** (Phase 4): Multi-objective ranking → confidence weighting
6. **STEP 5 - OUTPUT**: Generate comprehensive screening report

**CRITICAL RULES:**
- Never skip validation (Step 1)
- Always try data sources in order: MP → ASE → ML calculation (never skip ahead)
- Always relax structures before ML calculations (matcalc/MatGL)
- MatGL for formation energy/band gap; matcalc for mechanical, vibrational, surface, thermal properties
- Always cache results in ASE database
- Never silently exclude - always log rejection reasons
- Mark ML predictions for DFT verification if high-scoring

---

## STEP 0: INITIALIZATION

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

## STEP 1: VALIDATION AND ANALYSIS (Phase 1)

**Purpose:** Filter out invalid structures before expensive operations

**Step 1.0:** For each candidate in candidates:

**Step 1.1:** Validate structure integrity
```
CALL structure_validator(
    input_structure=candidate.structure,
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
    input_structure=candidate.structure,
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
    input_structure=candidate.structure,
    hull_tolerance=0.1
)

IF result.stability_category == "unstable" AND result.energy_above_hull > 0.3:
    # Highly unstable - reject OR flag for review based on requirements
    OPTION A: APPEND to rejected_candidates, CONTINUE to next candidate
    OPTION B: FLAG candidate.requires_stability_review = True
```

**Step 1.4:** Extract structural features
```
CALL structure_analyzer(
    input_structure=candidate.structure,
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

## STEP 2: HIERARCHICAL PROPERTY RETRIEVAL (Phase 2)

**Purpose:** Obtain properties using data source hierarchy: Materials Project → ASE cache → ML calculation (matcalc + MatGL)

**Rule:** ALWAYS try sources in order. Do NOT skip ahead in the hierarchy (MP → ASE → ML).

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
        atoms_dict=candidate.structure,  # Must be ASE atoms dict format
        results=candidate.properties,  # Energy, forces, etc. if available
        key_value_pairs={
            "material_id": mp_entry.material_id,
            "source": "Materials_Project",
            "formula": candidate.formula
        }
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

**Step 2.3:** ML-Based Property Calculation (THIRD PRIORITY)
```
# Only reached if Steps 2.1 and 2.2 both failed

SET candidate.property_source = "ML_calculated"

# REQUIRED: Relax structure before ANY ML calculations (matcalc/MatGL)
TRY:
    CALL matgl_relax_structure(
        input_structure=candidate.structure,
        fmax=0.1,
        max_steps=500
    )
    
    IF result.converged:
        SET candidate.structure = result.final_structure
        SET candidate.was_relaxed = True
    ELSE:
        LOG "Relaxation failed to converge for {candidate.formula}"
        SET candidate.requires_dft = True
        CONTINUE to next candidate  # Skip - cannot proceed without relaxation
EXCEPT error:
    LOG "Relaxation failed for {candidate.formula}: {error}"
    SET candidate.requires_dft = True
    CONTINUE to next candidate  # Skip - cannot proceed without relaxation

# === FORMATION ENERGY: Use MatGL direct prediction (fast) ===
TRY:
    CALL matgl_predict_eform(
        input_structure=candidate.structure,  # Now relaxed
        model="M3GNet-MP-2018.6.1-Eform"
    )
    SET candidate.properties.formation_energy_per_atom = result.formation_energy_eV_per_atom
    SET candidate.properties.eform_model = result.model_used
    SET candidate.properties.eform_source = "MatGL_prediction"
EXCEPT error:
    # Try alternative MatGL model
    TRY:
        CALL matgl_predict_eform(
            input_structure=candidate.structure,
            model="MEGNet-MP-2018.6.1-Eform"
        )
        SET candidate.properties.formation_energy_per_atom = result.formation_energy_eV_per_atom
        SET candidate.properties.eform_model = result.model_used
        SET candidate.properties.eform_source = "MatGL_prediction"
    EXCEPT error2:
        LOG "Both MatGL eform models failed for {candidate.formula}"
        SET candidate.properties.formation_energy_per_atom = None
        SET candidate.requires_dft = True

# === BAND GAP: Use MatGL direct prediction (fast) ===
TRY:
    CALL matgl_predict_bandgap(
        input_structure=candidate.structure,  # Now relaxed
        model="MEGNet-MP-2019.4.1-BandGap-mfi"
    )
    SET candidate.properties.band_gap = result.band_gap_eV
    SET candidate.properties.material_class = result.material_class
    SET candidate.properties.bandgap_model = result.model_used
    SET candidate.properties.bandgap_source = "MatGL_prediction"
EXCEPT error:
    LOG "MatGL bandgap prediction failed for {candidate.formula}"
    SET candidate.properties.band_gap = None
    SET candidate.requires_dft = True

# === MECHANICAL PROPERTIES: Use matcalc calculations (if required) ===
IF screening_requires_mechanical_properties:
    TRY:
        CALL matcalc_calc_elasticity(
            input_structure=candidate.structure,  # Relaxed
            calculator="TensorNet-MatPES-PBE-v2025.1-PES",
            relax_structure=False,  # Already relaxed
            relax_deformed_structures=True
        )
        SET candidate.properties.bulk_modulus = result.bulk_modulus
        SET candidate.properties.shear_modulus = result.shear_modulus
        SET candidate.properties.youngs_modulus = result.youngs_modulus
        SET candidate.properties.poissons_ratio = result.poissons_ratio
        SET candidate.properties.is_mechanically_stable = result.is_stable
        SET candidate.properties.mechanical_source = "matcalc_2025"
    EXCEPT error:
        LOG "matcalc elasticity failed for {candidate.formula}: {error}"
        SET candidate.requires_dft = True

# === PHONON PROPERTIES: Use matcalc calculations (if required) ===
IF screening_requires_phonon_stability:
    TRY:
        CALL matcalc_calc_phonon(
            structure_input=candidate.structure,  # Relaxed
            calculator="TensorNet-MatPES-PBE",
            relax_structure=False,  # Already relaxed
            supercell_matrix=[[2,0,0],[0,2,0],[0,0,2]]
        )
        SET candidate.properties.has_imaginary_modes = result.has_imaginary_modes
        SET candidate.properties.zero_point_energy = result.zero_point_energy
        SET candidate.properties.phonon_source = "matcalc_2025"
        
        IF result.has_imaginary_modes:
            FLAG candidate.dynamically_unstable = True
    EXCEPT error:
        LOG "matcalc phonon failed for {candidate.formula}: {error}"
        SET candidate.requires_dft = True

# === SURFACE PROPERTIES: Use matcalc calculations (if required) ===
IF screening_requires_surface_properties:
    FOR each miller_index in required_surfaces:  # e.g., [[1,0,0], [1,1,0], [1,1,1]]
        TRY:
            CALL matcalc_calc_surface(
                structure_input=candidate.structure,  # Relaxed
                miller_index=miller_index,
                calculator="CHGNet",
                relax_slab=True
            )
            STORE result.surface_energy in candidate.properties.surface_energies[miller_index]
            SET candidate.properties.surface_source = "matcalc_2025"
        EXCEPT error:
            LOG "matcalc surface calculation failed for {candidate.formula} {miller_index}: {error}"

# Add other matcalc calculations as needed:
# - matcalc_calc_eos: for bulk modulus validation
# - matcalc_calc_adsorption: for catalyst screening
# - matcalc_calc_md: for thermal stability
# - matcalc_calc_neb: for diffusion barriers
# etc.

SET candidate.confidence = "medium"  # ML-based properties

# Cache all results in ASE database for future runs
CALL ase_store_result(
    db_path=db_path,
    atoms_dict=candidate.structure,  # Must be ASE atoms dict format
    results=candidate.properties,
    key_value_pairs={
        "source": "ML_hybrid",  # MatGL predictions + matcalc calculations
        "formula": candidate.formula,
        "eform_model": candidate.properties.eform_model,
        "bandgap_model": candidate.properties.bandgap_model,
        "matcalc_calculator": "TensorNet-MatPES-PBE-v2025.1-PES"  # Primary calculator used
    }
)

APPEND candidate to candidates_with_properties
```

---

## STEP 3: CRITERIA-BASED FILTERING (Phase 3)

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

## STEP 4: MULTI-OBJECTIVE RANKING (Phase 4)

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
    "Materials_Project": 1.0,     # DFT-quality reference data
    "ASE_cached": 0.9,            # Depends on original calculator quality
    "ML_calculated": 0.75         # MatGL predictions + matcalc calculations
}

FOR each candidate in ranked_candidates:
    SET confidence_factor = confidence_weights[candidate.property_source]
    SET candidate.adjusted_score = candidate.total_score * confidence_factor
    
    # Flag high-scoring ML-calculated predictions for DFT verification
    IF candidate.total_score > 0.8 AND candidate.property_source == "ML_calculated":
        SET candidate.recommend_dft_verification = True
```

---

## STEP 5: OUTPUT GENERATION

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
        "ml_calculated": count where property_source == "ML_calculated"  # MatGL predictions + matcalc calculations
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
