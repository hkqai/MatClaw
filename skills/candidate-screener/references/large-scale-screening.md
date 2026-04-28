# Large-Scale Screening (>20 Candidates)

When screening **many candidates** (>20 structures), **ALWAYS create a screening tracking file FIRST** before executing the workflow. This enables:
- **Checkpointing** after each candidate (property retrieval can fail/timeout)
- **Resume capability** (ML relaxations take 5-10s per structure = 8-15 min for 100)
- **Progress monitoring** (track validation, property sources, screening results)
- **Iterative refinement** (adjust screening criteria based on partial results)
- **Audit trail** (which properties came from MP vs ASE vs ML)

## When to Use Screening Tracking

**Trigger conditions:**
- User provides >20 candidates for screening
- Screening requires expensive ML calculations (elasticity, phonons, surfaces)
- Screening criteria may need adjustment after initial results
- User requests comprehensive property enrichment

**Skip tracking for:**
- Quick screenings (<10 candidates)
- All properties available in Materials Project (fast lookups)
- Single-round screening with fixed criteria

---

## Screening Tracking Workflow

### Step 1: Create Screening Plan

Generate a structured JSON tracking file that records:
- Input candidates and screening criteria
- Per-candidate validation, property retrieval, and screening results
- Status tracking for resume capability
- Source attribution (MP/ASE/ML) for confidence assessment

**Template screening plan:**
```json
{
  "metadata": {
    "screening_date": "2026-04-28",
    "input_source": "lanthanide_niobate_candidates_100.json",
    "ase_database": "screening_ln_niobates_20260428.db",
    "total_candidates": 100,
    "status": "planning",
    "screening_criteria": {
      "essential": {
        "structure_valid": true,
        "composition_valid": true,
        "energy_above_hull_max": 0.3,
        "formation_energy_required": true
      },
      "application_specific": {
        "band_gap_min": 3.0,
        "band_gap_max": 5.0,
        "mechanical_stability_required": false,
        "phonon_stability_required": false
      }
    },
    "property_hierarchy": ["Materials_Project", "ASE_cached", "ML_calculated"],
    "ml_settings": {
      "relaxation_fmax": 0.1,
      "relaxation_max_steps": 500,
      "eform_model": "M3GNet-MP-2018.6.1-Eform",
      "bandgap_model": "MEGNet-MP-2019.4.1-BandGap-mfi"
    }
  },
  "candidates": [
    {
      "id": "CAND-001",
      "formula": "Sr0.95Eu0.05Nb2O6",
      "input_structure": {
        "cif": "...",
        "ase_db_source": "lanthanide_niobate_candidates.db",
        "ase_db_id": 1
      },
      "status": "not_started",
      "validation": {
        "structure_valid": null,
        "composition_valid": null,
        "validation_issues": [],
        "duplicate_of": null,
        "timestamp": null
      },
      "properties": {
        "formation_energy_per_atom": null,
        "energy_above_hull": null,
        "band_gap": null,
        "space_group": null,
        "is_stable": null,
        "property_sources": {},
        "timestamp": null
      },
      "screening_result": {
        "passed": null,
        "failed_criteria": [],
        "rejection_reason": null,
        "requires_dft": false
      },
      "ranking": {
        "rank": null,
        "composite_score": null,
        "objective_scores": {}
      }
    }
    // ... 99 more candidates
  ],
  "execution_log": [],
  "summary_statistics": {
    "not_started": 100,
    "validation_in_progress": 0,
    "validation_passed": 0,
    "validation_failed": 0,
    "properties_in_progress": 0,
    "properties_complete": 0,
    "properties_failed": 0,
    "screening_passed": 0,
    "screening_failed": 0,
    "ranked": 0,
    "property_source_breakdown": {
      "Materials_Project": 0,
      "ASE_cached": 0,
      "ML_calculated": 0
    }
  }
}
```

**Key tracking fields:**
- `status`: `"not_started"` → `"validating"` → `"validated"` → `"retrieving_properties"` → `"properties_complete"` → `"screening_complete"` → `"ranked"` (or `"rejected"` at any stage)
- `validation`: Structure and composition validation results
- `properties.property_sources`: Maps each property to its source (`{"formation_energy_per_atom": "Materials_Project", "band_gap": "ML_calculated"}`)
- `screening_result.failed_criteria`: List of criteria that failed (e.g., `["band_gap_too_low", "unstable"]`)
- `requires_dft`: Flag for high-priority candidates needing DFT verification
- `execution_log`: Timestamped events (validation failed, MP lookup timeout, ML prediction succeeded, etc.)

---

### Step 2: Present Screening Plan to User

**ALWAYS show the user:**
1. Total candidates and screening criteria
2. Expected property sources (estimate MP vs ML percentages)
3. Estimated runtime based on property retrieval needs
4. Option to adjust criteria before execution

**Example output:**
```
Generated screening tracking file: screening_ln_niobates_100.json

Screening Plan Summary:
───────────────────────────────────────────────────
Input: 100 lanthanide-doped niobate candidates
Database: screening_ln_niobates_20260428.db

Essential Criteria:
  ✓ Structure validation (reject invalid)
  ✓ Composition analysis (reject unbalanced)
  ✓ Energy above hull ≤ 0.3 eV/atom
  ✓ Formation energy required

Application-Specific Criteria (Phosphor Screening):
  ✓ Band gap: 3.0 - 5.0 eV (for UV excitation)
  ✗ Mechanical properties: not required
  ✗ Phonon stability: not required

Property Retrieval Strategy:
  1st priority: Materials Project (DFT quality)
     → Estimated: ~15% of candidates (common niobates)
  2nd priority: ASE cache (previous screenings)
     → Estimated: ~5% (if rerun)
  3rd priority: ML calculations (MatGL + matcalc)
     → Estimated: ~80% (novel doped compositions)

Estimated Runtime:
  - Validation (100 candidates): ~1 minute
  - MP lookups (15 hits): ~5 seconds
  - ML calculations (80 candidates):
    * Structure relaxation: ~10 minutes
    * Property predictions: ~2 minutes
  - Ranking: ~10 seconds
  TOTAL: ~15 minutes (with checkpointing enabled)

Review screening_ln_niobates_100.json and confirm to proceed.
Type 'proceed' to start screening.
```

**Wait for user approval.** User may:
- Approve as-is
- Adjust criteria (e.g., relax band gap range to 2.5-5.5 eV)
- Skip expensive calculations (e.g., disable phonon checks)
- Abort if criteria don't match application needs

---

### Step 3: Execute with Checkpointing

**Iterate through candidates with status tracking and checkpoint after EVERY candidate:**

```python
# Pseudocode for checkpointed screening execution
plan = load_json("screening_ln_niobates_100.json")
plan["metadata"]["status"] = "in_progress"
ase_db = plan["metadata"]["ase_database"]

# === PHASE 1: VALIDATION ===
print("Phase 1: Validation (100 candidates)")
for candidate in plan["candidates"]:
    if candidate["status"] in ["validated", "properties_complete", "screening_complete", "rejected"]:
        continue  # Already processed validation
    
    candidate["status"] = "validating"
    save_json(plan, "screening_ln_niobates_100.json")  # Checkpoint
    
    try:
        # Step 1.1: Structure validation
        val_result = structure_validator(input_structure=candidate["input_structure"]["cif"])
        candidate["validation"]["structure_valid"] = val_result["is_valid"]
        
        if not val_result["is_valid"]:
            candidate["status"] = "rejected"
            candidate["validation"]["validation_issues"] = val_result["issues"]
            candidate["screening_result"]["rejection_reason"] = f"Invalid structure: {val_result['issues']}"
            plan["execution_log"].append({
                "timestamp": now(),
                "candidate_id": candidate["id"],
                "event": "validation_failed",
                "reason": val_result["issues"]
            })
            plan["summary_statistics"]["validation_failed"] += 1
            save_json(plan, "screening_ln_niobates_100.json")  # Checkpoint
            print(f"  ✗ {candidate['id']}: REJECTED (invalid structure)")
            continue
        
        # Step 1.2: Composition analysis
        comp_result = composition_analyzer(input_structure=candidate["input_structure"]["cif"])
        candidate["validation"]["composition_valid"] = not comp_result.get("errors", False)
        candidate["properties"]["space_group"] = comp_result.get("spacegroup", "unknown")
        
        if comp_result.get("errors"):
            candidate["status"] = "rejected"
            candidate["validation"]["validation_issues"].append("composition_invalid")
            candidate["screening_result"]["rejection_reason"] = "Invalid composition"
            plan["summary_statistics"]["validation_failed"] += 1
            save_json(plan, "screening_ln_niobates_100.json")
            print(f"  ✗ {candidate['id']}: REJECTED (invalid composition)")
            continue
        
        # Validation passed
        candidate["status"] = "validated"
        candidate["validation"]["timestamp"] = now()
        plan["summary_statistics"]["validation_passed"] += 1
        plan["summary_statistics"]["not_started"] -= 1
        save_json(plan, "screening_ln_niobates_100.json")  # Checkpoint
        print(f"  ✓ {candidate['id']}: validated")
    
    except Exception as e:
        candidate["status"] = "rejected"
        candidate["screening_result"]["rejection_reason"] = f"Validation error: {str(e)}"
        plan["execution_log"].append({
            "timestamp": now(),
            "candidate_id": candidate["id"],
            "event": "error",
            "phase": "validation",
            "message": str(e)
        })
        plan["summary_statistics"]["validation_failed"] += 1
        save_json(plan, "screening_ln_niobates_100.json")
        print(f"  ✗ {candidate['id']}: ERROR - {e}")

# === PHASE 2: PROPERTY RETRIEVAL ===
print("\nPhase 2: Property Retrieval (hierarchical: MP → ASE → ML)")
for candidate in plan["candidates"]:
    if candidate["status"] == "rejected":
        continue  # Skip rejected candidates
    if candidate["status"] in ["properties_complete", "screening_complete"]:
        continue  # Already retrieved properties
    
    candidate["status"] = "retrieving_properties"
    save_json(plan, "screening_ln_niobates_100.json")  # Checkpoint
    
    try:
        # Step 2.1: Try Materials Project
        mp_result = mp_search_materials(formula=candidate["formula"], limit=5)
        
        if mp_result["success"] and mp_result["count"] > 0:
            # Found in MP - retrieve detailed properties
            mp_id = mp_result["materials"][0]["material_id"]
            props = mp_get_material_properties(
                material_id=mp_id,
                properties=["formation_energy_per_atom", "band_gap", "energy_above_hull", "is_stable"]
            )
            
            candidate["properties"]["formation_energy_per_atom"] = props["formation_energy_per_atom"]
            candidate["properties"]["band_gap"] = props["band_gap"]
            candidate["properties"]["energy_above_hull"] = props["energy_above_hull"]
            candidate["properties"]["is_stable"] = props["is_stable"]
            candidate["properties"]["property_sources"]["formation_energy_per_atom"] = "Materials_Project"
            candidate["properties"]["property_sources"]["band_gap"] = "Materials_Project"
            candidate["properties"]["property_sources"]["energy_above_hull"] = "Materials_Project"
            candidate["properties"]["timestamp"] = now()
            
            # Cache in ASE database
            ase_store_result(
                db_path=ase_db,
                atoms_dict=candidate["input_structure"],
                results={"energy": props["formation_energy_per_atom"], "band_gap": props["band_gap"]},
                key_value_pairs={"source": "Materials_Project", "mp_id": mp_id}
            )
            
            candidate["status"] = "properties_complete"
            plan["summary_statistics"]["properties_complete"] += 1
            plan["summary_statistics"]["property_source_breakdown"]["Materials_Project"] += 1
            save_json(plan, "screening_ln_niobates_100.json")
            print(f"  ✓ {candidate['id']}: MP (mp_id={mp_id})")
            continue
        
        # Step 2.2: Try ASE cache
        ase_result = ase_query(db_path=ase_db, formula=candidate["formula"])
        
        if ase_result["success"] and ase_result["count"] > 0:
            entry = ase_result["entries"][0]
            candidate["properties"]["formation_energy_per_atom"] = entry.get("energy")
            candidate["properties"]["band_gap"] = entry.get("band_gap")
            candidate["properties"]["property_sources"]["formation_energy_per_atom"] = "ASE_cached"
            candidate["properties"]["property_sources"]["band_gap"] = "ASE_cached"
            candidate["properties"]["timestamp"] = now()
            
            candidate["status"] = "properties_complete"
            plan["summary_statistics"]["properties_complete"] += 1
            plan["summary_statistics"]["property_source_breakdown"]["ASE_cached"] += 1
            save_json(plan, "screening_ln_niobates_100.json")
            print(f"  ✓ {candidate['id']}: ASE cache")
            continue
        
        # Step 2.3: ML-based calculation (last resort)
        # Relax structure (REQUIRED)
        relax_result = matgl_relax_structure(
            input_structure=candidate["input_structure"]["cif"],
            fmax=plan["metadata"]["ml_settings"]["relaxation_fmax"],
            max_steps=plan["metadata"]["ml_settings"]["relaxation_max_steps"]
        )
        
        if not relax_result["converged"]:
            raise Exception("Structure relaxation failed to converge")
        
        relaxed_structure = relax_result["final_structure"]
        
        # Formation energy prediction
        eform_result = matgl_predict_eform(
            input_structure=relaxed_structure,
            model=plan["metadata"]["ml_settings"]["eform_model"]
        )
        candidate["properties"]["formation_energy_per_atom"] = eform_result["formation_energy_eV_per_atom"]
        candidate["properties"]["property_sources"]["formation_energy_per_atom"] = "ML_calculated"
        
        # Band gap prediction
        bandgap_result = matgl_predict_bandgap(
            input_structure=relaxed_structure,
            model=plan["metadata"]["ml_settings"]["bandgap_model"]
        )
        candidate["properties"]["band_gap"] = bandgap_result["band_gap_eV"]
        candidate["properties"]["property_sources"]["band_gap"] = "ML_calculated"
        
        # Stability analysis (energy above hull via MP)
        stab_result = stability_analyzer(
            input_structure=relaxed_structure,
            hull_tolerance=0.1
        )
        candidate["properties"]["energy_above_hull"] = stab_result.get("energy_above_hull")
        candidate["properties"]["is_stable"] = stab_result["stability_category"] == "stable"
        
        candidate["properties"]["timestamp"] = now()
        
        # Cache in ASE database
        ase_store_result(
            db_path=ase_db,
            atoms_dict=relaxed_structure,
            results={"energy": eform_result["formation_energy_eV_per_atom"], 
                    "band_gap": bandgap_result["band_gap_eV"]},
            key_value_pairs={"source": "ML_calculated", "relaxed": True}
        )
        
        candidate["status"] = "properties_complete"
        candidate["screening_result"]["requires_dft"] = True  # Flag ML predictions for verification
        plan["summary_statistics"]["properties_complete"] += 1
        plan["summary_statistics"]["property_source_breakdown"]["ML_calculated"] += 1
        save_json(plan, "screening_ln_niobates_100.json")
        print(f"  ✓ {candidate['id']}: ML calculated (requires DFT verification)")
    
    except Exception as e:
        candidate["status"] = "properties_failed"
        candidate["screening_result"]["rejection_reason"] = f"Property retrieval failed: {str(e)}"
        plan["execution_log"].append({
            "timestamp": now(),
            "candidate_id": candidate["id"],
            "event": "error",
            "phase": "property_retrieval",
            "message": str(e)
        })
        plan["summary_statistics"]["properties_failed"] += 1
        save_json(plan, "screening_ln_niobates_100.json")
        print(f"  ✗ {candidate['id']}: FAILED - {e}")

# === PHASE 3: SCREENING (apply criteria) ===
print("\nPhase 3: Screening (applying criteria)")
for candidate in plan["candidates"]:
    if candidate["status"] != "properties_complete":
        continue  # Skip if properties not available
    
    try:
        failed_criteria = []
        
        # Essential criteria
        if candidate["properties"]["energy_above_hull"] is None:
            failed_criteria.append("energy_above_hull_missing")
        elif candidate["properties"]["energy_above_hull"] > plan["metadata"]["screening_criteria"]["essential"]["energy_above_hull_max"]:
            failed_criteria.append(f"energy_above_hull_too_high ({candidate['properties']['energy_above_hull']:.3f} > 0.3)")
        
        if candidate["properties"]["formation_energy_per_atom"] is None:
            failed_criteria.append("formation_energy_missing")
        
        # Application-specific criteria
        bg_min = plan["metadata"]["screening_criteria"]["application_specific"]["band_gap_min"]
        bg_max = plan["metadata"]["screening_criteria"]["application_specific"]["band_gap_max"]
        
        if candidate["properties"]["band_gap"] is None:
            failed_criteria.append("band_gap_missing")
        elif candidate["properties"]["band_gap"] < bg_min:
            failed_criteria.append(f"band_gap_too_low ({candidate['properties']['band_gap']:.2f} < {bg_min})")
        elif candidate["properties"]["band_gap"] > bg_max:
            failed_criteria.append(f"band_gap_too_high ({candidate['properties']['band_gap']:.2f} > {bg_max})")
        
        # Record screening result
        if len(failed_criteria) > 0:
            candidate["screening_result"]["passed"] = False
            candidate["screening_result"]["failed_criteria"] = failed_criteria
            candidate["screening_result"]["rejection_reason"] = "; ".join(failed_criteria)
            candidate["status"] = "rejected"
            plan["summary_statistics"]["screening_failed"] += 1
            print(f"  ✗ {candidate['id']}: FAILED screening - {failed_criteria[0]}")
        else:
            candidate["screening_result"]["passed"] = True
            candidate["status"] = "screening_complete"
            plan["summary_statistics"]["screening_passed"] += 1
            print(f"  ✓ {candidate['id']}: PASSED screening")
        
        save_json(plan, "screening_ln_niobates_100.json")  # Checkpoint
    
    except Exception as e:
        candidate["status"] = "rejected"
        candidate["screening_result"]["rejection_reason"] = f"Screening error: {str(e)}"
        plan["execution_log"].append({
            "timestamp": now(),
            "candidate_id": candidate["id"],
            "event": "error",
            "phase": "screening",
            "message": str(e)
        })
        save_json(plan, "screening_ln_niobates_100.json")
        print(f"  ✗ {candidate['id']}: ERROR - {e}")

# === PHASE 4: RANKING ===
print("\nPhase 4: Multi-Objective Ranking")
passed_candidates = [c for c in plan["candidates"] if c["screening_result"]["passed"]]

if len(passed_candidates) > 0:
    ranking_result = multi_objective_ranker(
        candidates=[
            {
                "id": c["id"],
                "formation_energy_per_atom": c["properties"]["formation_energy_per_atom"],
                "band_gap": c["properties"]["band_gap"],
                "energy_above_hull": c["properties"]["energy_above_hull"]
            }
            for c in passed_candidates
        ],
        objectives={
            "formation_energy_per_atom": {"weight": 0.3, "direction": "minimize"},
            "energy_above_hull": {"weight": 0.4, "direction": "minimize"},
            "band_gap_deviation": {"weight": 0.3, "direction": "minimize", "target": 4.0}
        }
    )
    
    for ranked_item in ranking_result["ranked_candidates"]:
        candidate = next(c for c in plan["candidates"] if c["id"] == ranked_item["id"])
        candidate["ranking"]["rank"] = ranked_item["rank"]
        candidate["ranking"]["composite_score"] = ranked_item["composite_score"]
        candidate["ranking"]["objective_scores"] = ranked_item["objective_scores"]
        candidate["status"] = "ranked"
    
    plan["summary_statistics"]["ranked"] = len(passed_candidates)
    save_json(plan, "screening_ln_niobates_100.json")
    print(f"  ✓ Ranked {len(passed_candidates)} candidates")
else:
    print("  ⚠ No candidates passed screening - cannot rank")

plan["metadata"]["status"] = "completed"
save_json(plan, "screening_ln_niobates_100.json")

print(f"\n{'='*60}")
print("Screening Complete!")
print(f"{'='*60}")
print(f"Input:            {plan['metadata']['total_candidates']}")
print(f"Validated:        {plan['summary_statistics']['validation_passed']}")
print(f"Properties retrieved: {plan['summary_statistics']['properties_complete']}")
print(f"  - From MP:      {plan['summary_statistics']['property_source_breakdown']['Materials_Project']}")
print(f"  - From ASE:     {plan['summary_statistics']['property_source_breakdown']['ASE_cached']}")
print(f"  - From ML:      {plan['summary_statistics']['property_source_breakdown']['ML_calculated']}")
print(f"Passed screening: {plan['summary_statistics']['screening_passed']}")
print(f"Failed screening: {plan['summary_statistics']['screening_failed']}")
print(f"Ranked:           {plan['summary_statistics']['ranked']}")
print(f"\nTop 10 candidates ranked in screening_ln_niobates_100.json")
```

**Critical checkpointing rules:**
- Save tracking file after **EVERY** candidate in each phase (not just at phase boundaries)
- Query ASE database before property retrieval to avoid duplicate calculations
- Log all errors with candidate ID, phase, and timestamp
- Update `summary_statistics` after each candidate for progress monitoring

---

### Step 4: Handling Interruptions and Resume

**If screening is interrupted:**

1. **Check tracking file status:**
   ```json
   "metadata": {"status": "in_progress"}
   "summary_statistics": {
     "validation_passed": 85,
     "properties_complete": 42,
     "screening_passed": 38,
     "ranked": 0
   }
   ```
   
   Status shows 85 validated, 42 with properties, 38 passed screening → resume at property retrieval for remaining candidates

2. **Resume from checkpoint:**
   ```python
   plan = load_json("screening_ln_niobates_100.json")
   
   # Phase 1: Validation - resume for candidates with status "not_started"
   # Phase 2: Property retrieval - resume for candidates with status "validated" (not "properties_complete")
   # Phase 3: Screening - resume for candidates with status "properties_complete" (not "screening_complete")
   # Phase 4: Ranking - run if any candidates have status "screening_complete"
   ```

3. **Verify ASE database consistency:**
   ```python
   # Cross-check tracking file vs ASE database
   tracked_complete = [c for c in plan["candidates"] if c["status"] == "properties_complete"]
   
   ase_entries = ase_query(
       db_path=plan["metadata"]["ase_database"],
       property_filters={"source": {"$exists": True}}
   )
   
   if len(tracked_complete) != ase_entries["count"]:
       print("WARNING: Tracking file and ASE database out of sync!")
       # Reconcile by querying ASE for each candidate
       for candidate in plan["candidates"]:
           if candidate["status"] == "retrieving_properties":
               ase_result = ase_query(db_path=ase_db, formula=candidate["formula"])
               if ase_result["count"] > 0:
                   # Found in ASE - mark as complete
                   candidate["status"] = "properties_complete"
   ```

---

### Step 5: Iterative Criteria Refinement

**Common workflow:**
1. Run screening with initial criteria (e.g., band gap 3.0-5.0 eV)
2. Review partial results after 50% completion
3. Adjust criteria if too strict/loose (e.g., relax to 2.5-5.5 eV)
4. Rerun screening phase (properties already cached - fast)

**Implementation:**
```python
# Modify criteria in tracking file
plan["metadata"]["screening_criteria"]["application_specific"]["band_gap_min"] = 2.5
plan["metadata"]["screening_criteria"]["application_specific"]["band_gap_max"] = 5.5

# Reset screening results
for candidate in plan["candidates"]:
    if candidate["status"] in ["screening_complete", "rejected"] and candidate["properties"]["formation_energy_per_atom"] is not None:
        candidate["status"] = "properties_complete"  # Revert to pre-screening state
        candidate["screening_result"] = { 
            "passed": null,
            "failed_criteria": [],
            "rejection_reason": null,
            "requires_dft": candidate["screening_result"].get("requires_dft", False)
        }

# Rerun Phase 3 and 4 (validation and property retrieval already done)
run_screening_phase(plan, phase=3)  # Screening
run_screening_phase(plan, phase=4)  # Ranking
```

---

## Best Practices for Screening Tracking

1. **Checkpoint aggressively:**
   - Save after every candidate (not batches) - property retrieval can timeout
   - Enables fine-grained resume

2. **Track property sources explicitly:**
   - Essential for confidence assessment (MP > ASE > ML)
   - Flags ML predictions for DFT verification

3. **Log all errors with context:**
   - Timestamp, candidate ID, phase, error message
   - Enables debugging property retrieval failures

4. **Estimate property sources realistically:**
   - Novel compositions → mostly ML calculations
   - Common materials → mostly MP lookups
   - Sets user expectations for runtime

5. **Enable iterative refinement:**
   - Preserve all properties even if screening fails
   - User can adjust criteria without rerunning expensive ML calculations

6. **Cross-reference ASE database:**
   - Verify tracking file matches cached results
   - Detect orphaned entries or missing checkpoints

7. **Mark ML predictions for verification:**
   - Set `requires_dft=True` for top-ranked candidates from ML
   - Prioritize DFT calculations for experimental validation
