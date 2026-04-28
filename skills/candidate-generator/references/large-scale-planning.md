# Large-Scale Generation Planning

Planning workflow for generating >20 structures with checkpointing and progress tracking.

## When to Use Planning Workflow

### Trigger Conditions

Use planning workflow when:
- User requests N > 20 structures explicitly ("generate 100 candidates")
- User requests "all possible" or "comprehensive" screening
- Multi-batch generation involving different tools/templates
- Generation across multiple chemical systems

### Skip Planning For

- Quick explorations (<10 structures)
- Single-batch generation with one tool call
- User explicitly requests immediate generation

---

## Planning Workflow Steps

### Step 1: Create Generation Plan

Generate structured JSON that specifies:
- Total target count
- Batch organization (by tool, template, composition)
- Per-candidate metadata (formula, tool, parameters)
- Status tracking fields

**Plan template structure:**

```json
{
  "metadata": {
    "request_summary": "100 lanthanide-doped niobate phosphors for PC-LED",
    "total_planned": 100,
    "status": "planning",
    "created": "2026-04-28",
    "ase_database": "candidates.db"
  },
  "batches": [
    {
      "batch_id": "batch_1",
      "description": "5% single Ln doping in SrNb2O6",
      "tool": "pymatgen_disorder_generator",
      "base_structure": {
        "mp_id": "mp-4591",
        "formula": "SrNb2O6"
      },
      "target_count": 14,
      "status": "not_started",
      "completed_count": 0,
      "candidates": [
        {
          "id": "CAND-001",
          "formula": "Sr0.95Eu0.05Nb2O6",
          "status": "not_started",
          "ase_db_id": null,
          "tool_parameters": {
            "site_substitutions": {"Sr": {"Eu": 0.05, "Sr": 0.95}},
            "output_format": "ase"
          },
          "notes": "5% Eu3+ doping on Sr2+ site"
        }
      ]
    }
  ],
  "execution_log": []
}
```

**Key fields:**
- `status`: `"planning"` → `"in_progress"` → `"completed"` (or `"paused"`)
- `batch_id`: Organize by tool, template, or scientific category
- `candidate.status`: `"not_started"` → `"completed"` → `"failed"`
- `ase_db_id`: Cross-reference with ASE database
- `tool_parameters`: Exact parameters for reproducibility
- `execution_log`: Timestamped events

---

### Step 2: Present Plan to User

**ALWAYS show:**
1. Total candidate count and batch breakdown
2. Scientific rationale for each batch
3. Which MCP tools will be used
4. Estimated resource requirements

**Example presentation:**

```
Generated planning file: generation_plan.json

Plan Summary:
─────────────────────────────────────────────────
Total candidates: 100
ASE database: lanthanide_niobate_candidates.db
Batches: 7

Batch breakdown:
  1. Single Ln doping (SrNb₂O₆):    20 structures [disorder_generator]
  2. Single Ln doping (BaNb₂O₆):    15 structures [disorder_generator]
  3. Double perovskites (A₂LnNbO₆): 20 structures [substitution_generator]
  4. Co-doping (Ln₁+Ln₂):           15 structures [disorder_generator]
  5. Varied doping levels:          10 structures [disorder_generator]
  6. ZnNb₂O₆ host:                  10 structures [disorder_generator]
  7. Alternative hosts:             10 structures [disorder_generator]

Estimated: ~110 MCP tool calls, 15-30 minutes runtime

Review generation_plan.json and confirm to proceed.
```

**Wait for user approval** before proceeding. User may:
- Approve as-is
- Request modifications (change doping, skip batches, add compositions)
- Abort if plan doesn't match intent

---

### Step 3: Execute with Checkpointing

**Critical checkpointing rules:**
- Save plan after EVERY candidate (not just batches)
- Query ASE database before generating to detect existing structures
- Log all errors with timestamps
- Never silently skip failed candidates

**Execution pseudocode:**

```python
plan = load_json("generation_plan.json")
plan["metadata"]["status"] = "in_progress"

for batch in plan["batches"]:
    if batch["status"] == "completed":
        continue  # Skip completed batches
    
    batch["status"] = "in_progress"
    print(f"Starting {batch['batch_id']}: {batch['description']}")
    
    for candidate in batch["candidates"]:
        if candidate["status"] == "completed":
            continue  # Resume from checkpoint
        
        try:
            # Generate structure
            if batch["tool"] == "pymatgen_disorder_generator":
                result = pymatgen_disorder_generator(
                    input_structures=[{"material_id": batch["base_structure"]["mp_id"]}],
                    site_substitutions=candidate["tool_parameters"]["site_substitutions"],
                    output_format="ase"
                )
                structure = result["structures"][0]
            
            # Store in ASE database
            db_result = ase_store_result(
                db_path=plan["metadata"]["ase_database"],
                atoms_dict=structure,
                key_value_pairs={
                    "candidate_id": candidate["id"],
                    "batch_id": batch["batch_id"],
                    "compound": candidate["formula"]
                }
            )
            
            # Update plan
            candidate["status"] = "completed"
            candidate["ase_db_id"] = db_result["id"]
            batch["completed_count"] += 1
            
            # CHECKPOINT: Save after every structure
            save_json(plan, "generation_plan.json")
            
            print(f"  ✓ {candidate['id']}: {candidate['formula']} (db_id={db_result['id']})")
        
        except Exception as e:
            # Log failure
            candidate["status"] = "failed"
            candidate["error"] = str(e)
            plan["execution_log"].append({
                "timestamp": datetime.now().isoformat(),
                "candidate_id": candidate["id"],
                "event": "error",
                "message": str(e)
            })
            
            save_json(plan, "generation_plan.json")
            print(f"  ✗ {candidate['id']}: FAILED - {e}")
    
    batch["status"] = "completed"
    save_json(plan, "generation_plan.json")

plan["metadata"]["status"] = "completed"
save_json(plan, "generation_plan.json")
```

---

### Step 4: Export Final Results

Generate user-facing JSON with embedded structures:

```python
candidates_output = []

for batch in plan["batches"]:
    for candidate in batch["candidates"]:
        if candidate["status"] != "completed":
            continue
        
        # Retrieve from ASE DB
        ase_result = ase_query_db(
            db_path=plan["metadata"]["ase_database"],
            id=candidate["ase_db_id"]
        )
        
        # Export as CIF
        structure_cif = atoms_to_cif(ase_result["atoms"])
        
        candidates_output.append({
            "id": candidate["id"],
            "formula": candidate["formula"],
            "structure": {
                "cif": structure_cif,
                "lattice_parameters": extract_lattice(ase_result["atoms"]),
                "natoms": ase_result["natoms"]
            },
            "provenance": {
                "mp_template": batch["base_structure"]["mp_id"],
                "tool": batch["tool"],
                "generation_date": plan["metadata"]["created"]
            }
        })

output = {
    "metadata": {
        "total_candidates": len(candidates_output),
        "ase_database": plan["metadata"]["ase_database"]
    },
    "generated_candidates": candidates_output
}

save_json(output, "final_candidates.json")
```

---

## Handling Interruptions

### Resume from Checkpoint

When execution is interrupted:

1. **Check plan status:**
```json
"metadata": {"status": "in_progress"}
"batches[0]": {"status": "completed", "completed_count": 20}
"batches[1]": {"status": "in_progress", "completed_count": 8}
```

2. **Resume from last checkpoint:**
- Batch 0 complete → skip
- Batch 1 has 8/15 done → resume at candidate 9
- `candidate["status"] == "completed"` → skip in loop

3. **Verify database consistency:**
```python
# Cross-check plan vs database
plan_completed = [c for batch in plan["batches"]
                  for c in batch["candidates"]
                  if c["status"] == "completed"]

db_entries = ase_query_db(
    db_path=plan["metadata"]["ase_database"],
    property_filters={"batch_id": {"$exists": True}}
)

if len(plan_completed) != db_entries["count"]:
    print("WARNING: Plan and database out of sync!")
    # Reconcile: mark candidates with ase_db_id as completed
```

---

## Best Practices

### 1. Organize Batches Scientifically

**Good organization:**
- "Single Ln doping in Sr host"
- "Double perovskites A₂LnNbO₆"
- "Co-doping pairs for energy transfer"

**Bad organization:**
- "disorder_generator batch 1"
- "disorder_generator batch 2"
- "batch_3"

### 2. Include Scientific Rationale

Add `description` and `notes` explaining:
- Chemical logic
- Scientific hypothesis
- Expected properties

**Example:**
```json
{
  "description": "Co-doped SrNb₂O₆ with Sm+Eu pairs",
  "notes": "Sm→Eu energy transfer for white light emission"
}
```

### 3. Validate Before Execution

Check:
- Charge neutrality for ionic materials
- MP templates exist
- Site labels match structure
- No duplicate formulas

### 4. Size Batches Reasonably

**Good batch sizes:** 10-20 candidates
- Easy to review progress
- Logical checkpoints
- Clear error isolation

**Avoid:** >50 candidates per batch (hides issues)

### 5. Cross-Check Existing Structures

Before creating plan:
```python
existing = ase_query_db(property_filters={"compound": target_formula})
if existing["count"] > 0:
    print(f"WARNING: {target_formula} already exists in database")
```

### 6. Estimate Resources Honestly

**Timing estimates:**
- 1-2 seconds per `disorder_generator` call
- 2-5 seconds per `substitution_generator` call
- Add 20% buffer for API latency

**Example:**
```
90 disorder_generator calls × 1.5 sec = 135 seconds
25 substitution_generator calls × 3 sec = 75 seconds
Total: 210 seconds + 20% buffer = 252 seconds (~4 minutes)
```

---

## Example: 100 Lanthanide-Doped Niobates

**User request:**
> "Generate 100 lanthanide-doped niobate phosphor candidates based on MNb₂O₆ structure"

**Step 1: Create plan**

```python
plan = {
    "metadata": {
        "request_summary": "100 lanthanide-doped niobate phosphors for PC-LED",
        "total_planned": 100,
        "status": "planning",
        "ase_database": "lanthanide_niobate_100.db"
    },
    "batches": [
        {
            "batch_id": "batch_1_sr_single_ln",
            "description": "5% single Ln³⁺ doping in SrNb₂O₆",
            "base_structure": {"mp_id": "mp-4591"},
            "lanthanides": ["La", "Ce", "Pr", "Nd", "Sm", "Eu", "Gd", 
                           "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu"],
            "target_count": 14
        },
        {
            "batch_id": "batch_2_ba_single_ln",
            "description": "5% single Ln³⁺ doping in BaNb₂O₆",
            "base_structure": {"mp_id": "mp-28150"},
            "target_count": 14
        },
        {
            "batch_id": "batch_3_double_perovskite",
            "description": "Double perovskite Ba₂LnNbO₆",
            "tool": "pymatgen_substitution_generator",
            "base_structure": {"mp_id": "mp-553281", "formula": "Ba2LaNbO6"},
            "target_count": 10
        }
        # ... more batches to reach 100
    ]
}
```

**Step 2: Present to user**

```
Plan Summary:
─────────────────────────────────────────────────
Total candidates: 100 structures
Batches: 7

Scientific strategy:
  1. Single Ln doping (Sr, Ba, Ca hosts): 40 structures
     → Systematic screening of all Ln³⁺ dopants
  
  2. Double perovskites (A₂LnNbO₆): 20 structures
     → Ln on ordered B-site for higher concentrations
  
  3. Co-doping (energy transfer pairs): 15 structures
     → Sm+Eu, Nd+Yb pairs for tunable emission

Estimated: ~115 MCP tool calls, 20-35 minutes

Review and confirm to proceed.
```

**Step 3: Execute with checkpointing**

(See pseudocode in Step 3 above)

**Step 4: Export results**

```json
{
  "metadata": {
    "total_candidates": 100,
    "ase_database": "lanthanide_niobate_100.db"
  },
  "generated_candidates": [
    {
      "id": "LNP-001",
      "formula": "Sr0.95La0.05Nb2O6",
      "structure": {
        "cif": "...",
        "natoms": 45
      }
    }
    // ... 99 more
  ]
}
```

---

## Troubleshooting

### Plan and Database Out of Sync

**Symptom:** `completed_count` doesn't match actual database entries

**Cause:** Checkpoint saved before database insert, or database insert failed

**Solution:**
```python
# Reconcile from database
for batch in plan["batches"]:
    for candidate in batch["candidates"]:
        # Check if structure exists in database
        db_check = ase_query_db(
            db_path=db_path,
            property_filters={"candidate_id": candidate["id"]}
        )
        
        if db_check["count"] > 0 and candidate["status"] != "completed":
            # Found in DB but not marked complete
            candidate["status"] = "completed"
            candidate["ase_db_id"] = db_check["results"][0]["id"]
        
        elif db_check["count"] == 0 and candidate["status"] == "completed":
            # Marked complete but not in DB
            candidate["status"] = "not_started"
            candidate["ase_db_id"] = None

save_json(plan, "generation_plan.json")
```

### Batch Stuck in Progress

**Symptom:** Batch shows "in_progress" but all candidates complete

**Cause:** Final batch status update didn't save

**Solution:**
```python
# Recount completed candidates
for batch in plan["batches"]:
    completed = sum(1 for c in batch["candidates"] if c["status"] == "completed")
    batch["completed_count"] = completed
    
    if completed == batch["target_count"]:
        batch["status"] = "completed"

save_json(plan, "generation_plan.json")
```

### High Failure Rate

**Symptom:** Many candidates have `status: "failed"`

**Cause:** Systematic issue with tool parameters or input structures

**Solution:**
1. Check first failure in `execution_log`
2. Fix root cause (bad MP ID, invalid parameters)
3. Reset failed candidates: `status: "not_started"`
4. Re-run with corrected parameters
