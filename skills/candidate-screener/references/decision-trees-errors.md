# Decision Algorithms & Error Handling

This reference provides critical decision logic and error recovery procedures for the screening workflow.

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
        CALL matgl_relax_structure(candidate.structure)
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
    result = matgl_predict_eform(structure, model="M3GNet-MP-2018.6.1-Eform")
    SET candidate.properties.formation_energy = result.value
    RETURN success
EXCEPT error1:
    LOG "Primary model failed: {error1}"
    
    TRY:
        result = matgl_predict_eform(structure, model="MEGNet-MP-2018.6.1-Eform")
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
    CONTINUE to Step 2.2
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
    result = matgl_relax_structure(structure)
EXCEPT MemoryError:
    action = handle_memory_exhaustion("matgl_relax_structure", current_state)
    IF action == retry:
        TRY:
            result = matgl_relax_structure(structure)
        EXCEPT MemoryError:
            # Still failing, skip relaxation for this candidate
            LOG "Skipping relaxation for {candidate.formula}"
            SET candidate.was_relaxed = False
    ELSE IF action == abort:
        RAISE "Cannot continue - insufficient memory"
```

---

## Error Recovery Priority Matrix

```
Operation Type       | Critical? | Retry? | Fallback                  | Abort?
---------------------|-----------|--------|---------------------------|-------
Structure validation | Yes       | No     | Reject candidate          | No
MP API lookup        | No        | Yes    | ASE cache → ML            | No
ASE DB connection    | Yes       | Yes    | Create new DB             | Yes if fails
ASE DB query         | No        | Yes    | ML prediction             | No
ASE DB store         | No        | Yes    | Continue without cache    | No
ML prediction        | No        | Yes    | Alternative model → DFT   | No
ML relaxation        | Yes       | Yes    | Reject/flag for DFT       | No (skip candidate)
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
