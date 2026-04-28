# Decision Trees and Algorithms

Complete decision logic for tool selection in candidate generation workflows.

## Entry Point Decision

```
ANALYZE user request
    ↓
IF user provides ONLY elements (e.g., "Li-Mn-P-O"):
    → GOTO Phase 0 (Composition Discovery)
    
ELSE IF user has existing structure (from MP, CIF, ASE database):
    → SET starting_structure = existing_structure
    → GOTO Phase 2 (Chemical Space Exploration)
    
ELSE IF user specifies composition + spacegroup:
    → GOTO Phase 1 (Seed Structure Generation)
    
ELSE IF user specifies composition only (e.g., "LiMnPO4"):
    → TRY mp_search_materials(formula=user_composition)
    → IF mp_result['count'] > 0:
        → SET starting_structure = mp_result['materials'][0]['structure']
        → GOTO Phase 2
      ELSE:
        → GOTO Phase 1 (need to build from prototype)
```

---

## Phase 0: Composition Discovery Strategy

**Decision tree for composition discovery:**

```
START: Have elements, need compositions
│
├─ Known analogue exists? (e.g., LiFePO₄ for Li-Mn-P-O)
│  ├─ YES → Template-based + Substitution predictor
│  │        1. mp_search_materials with analogous elements
│  │        2. pymatgen_substitution_predictor from known analogue
│  │        3. Extract stoichiometric patterns
│  │
│  └─ NO → Enumeration-based
│           composition_enumerator with all elements
│
├─ Chemical system well-studied? (battery, perovskite)
│  ├─ YES → Template-based first, enumeration if gaps
│  └─ NO → Enumeration-based (exhaustive)
│
└─ Exploratory discovery?
   └─ Enumeration → filter by stability_analyzer
```

**After composition discovery:**
1. Filter by `stability_analyzer` (keep ΔH < 0.1 eV/atom)
2. Check MP for existing structures
3. For novel compositions without MP structures, use templates or prototypes
4. GOTO Phase 1 or Phase 2

---

## Phase 1: Prototype Selection

```
IF user mentions "perovskite":
    → spacegroup=221 (Pm-3m)
ELSE IF user mentions "rock-salt" or "NaCl-type":
    → spacegroup=225 (Fm-3m)
ELSE IF user mentions "spinel":
    → spacegroup=227 (Fd-3m)
ELSE IF user mentions "layered oxide" or "LiCoO2-type":
    → spacegroup=166 (R-3m)
ELSE IF user mentions "olivine" or "LiFePO4-type":
    → spacegroup=62 (Pnma)
ELSE IF user mentions "rutile":
    → spacegroup=136 (P4₂/mnm)
ELSE IF user mentions "wurtzite":
    → spacegroup=186 (P6₃mc)
ELSE:
    → REQUEST spacegroup number from user
```

---

## Phase 2: Chemical Exploration Strategy

```
IF user wants to keep exact composition:
    → SKIP Phase 2, GOTO Phase 3
    
ELSE IF user requests chemical substitutions or doping:
    ↓
    IF material is ionic AND charge balance is critical:
        → pymatgen_ion_exchange_generator
        → Use when: Battery materials, ionic conductors
        
    ELSE IF exploratory screening OR charge balance not enforced:
        → pymatgen_substitution_generator
        → Use when: Isostructural analogues, ML training sets
        
    ELSE:
        → Default to ion_exchange_generator (safer for ionic materials)
```

---

## Phase 3: Disorder Resolution Strategy

```
IF any structure has fractional site occupancies:
    ↓
    IF need ALL possible orderings (ground-state search):
        ↓
        SET num_mixing_species = count(species with partial occupancy)
        
        IF num_mixing_species == 1:
            → pymatgen_enumeration_generator
            → supercell_size = 4
            
        ELSE IF num_mixing_species == 2:
            → pymatgen_enumeration_generator
            → supercell_size = 2
            
        ELSE IF num_mixing_species >= 3:
            → pymatgen_enumeration_generator
            → supercell_size = 1
            → OR consider pymatgen_sqs_generator (if ≥4 species)
    
    ELSE IF modeling disorder itself (solid solution):
        ↓
        IF num_mixing_species <= 2:
            → pymatgen_sqs_generator
            → supercell_size = 12
            
        ELSE IF num_mixing_species == 3:
            → pymatgen_sqs_generator
            → supercell_size = 16
            
        ELSE (high-entropy, ≥4 species):
            → pymatgen_sqs_generator
            → supercell_size = 20
            → n_mc_steps = 50000 × num_mixing_species

ELSE (fully ordered structures):
    → SKIP Phase 3, GOTO Phase 4
```

---

## Tool Selection: disorder_generator vs substitution_generator

**Critical distinction flowchart:**

```
Do you need partial substitution like Li[Ni₀.₈Mn₀.₂]O₂?
├─ YES: Do you want fractional occupancy (every site has 80%Ni+20%Mn)?
│  │
│  ├─ YES → pymatgen_disorder_generator
│  │        site_substitutions={'Ni': {'Ni': 0.8, 'Mn': 0.2}}
│  │        Output: 1 structure with fractional occupancy
│  │        Then: pymatgen_sqs_generator for quasirandom supercells
│  │
│  └─ NO: Want ordered enumeration (1 specific Ni replaced per structure)?
│     └─ YES → pymatgen_substitution_generator
│               substitutions={'Ni': {'replace_with': 'Mn', 'fraction': 0.2}}
│               Output: 5 structures, each with different Ni site replaced
│               Then: Run DFT on each ordered configuration
│
└─ NO: Complete substitution (all Li → Na)?
   └─ pymatgen_substitution_generator
      substitutions={'Li': 'Na'}
      Output: 1 structure with all Li replaced by Na
```

---

## Perturbation Decision

```
IF user requests perturbation OR rattling OR strain:
    → GOTO apply_perturbations
    
ELSE IF structures going to DFT relaxation:
    → ASK "Apply small perturbations to break symmetry? (Recommended for DFT)"
    → IF yes:
        → displacement_max = 0.05 (subtle)
        → strain_percent = None
        → n_structures = 1

IF use_case == "DFT_relaxation":
    → displacement_max = 0.05
    → strain_percent = None
    → n_structures = 1
    
ELSE IF use_case == "ML_augmentation":
    → displacement_max = 0.15
    → strain_percent = [-2.0, 2.0]
    → n_structures = 10
    
ELSE IF use_case == "defect_relaxation":
    → displacement_max = 0.08
    → strain_percent = None
    → n_structures = 3
```

---

## Complete Workflow Flowchart

```
ANALYZE user request
    ↓
Has existing structure? → YES: use it | NO: pymatgen_prototype_builder
    ↓
Want new chemistries? → YES: continue | NO: skip to disorder check
    ↓
Ionic + charge balance critical? → YES: pymatgen_ion_exchange_generator
                                 → NO: pymatgen_substitution_generator
    ↓
Structures have partial occupancies? → NO: skip to defects
                                     → YES: continue
    ↓
Need ALL orderings? → YES: pymatgen_enumeration_generator (supercell_size ≤ 2)
                   → NO: Modeling disorder? → YES: pymatgen_sqs_generator
                                            → NO: skip
    ↓
Need defects? → YES: pymatgen_defect_generator (single ordered structure)
             → NO: skip
    ↓
Need perturbations? → YES: pymatgen_perturbation_generator
                   → NO: skip
    ↓
Store in ASE database with ase_store_result (output_format='ase' required!)
    ↓
DONE
```

---

## Parameter Calculation Rules

### `n_structures` for substitution_generator

```
IF all substitutions have fraction=1.0:
    # Deterministic full swaps
    SET n_structures = 1
ELSE:
    # Fractional doping
    SET n_structures = 10
```

### `max_attempts` for substitution_generator

```
SET num_combinations = calculate_substitution_combinations(substitutions)
SET max_attempts = n_structures × num_combinations × 1.2  # 20% buffer

# Example: 8 B-site metals with n_structures=1
# max_attempts = 1 × 8 × 1.2 = 10 (rounded up)
```

### `supercell_size` for enumeration

```
SET num_mixing_species = count_mixing_species(disordered_structures)

IF num_mixing_species == 1:
    SET supercell_size = 4  # Single species ordering
ELSE IF num_mixing_species == 2:
    SET supercell_size = 2  # Binary mixing
ELSE IF num_mixing_species >= 3:
    SET supercell_size = 1  # Ternary+ mixing
ELSE:
    SET supercell_size = 2  # Default
```

### `supercell_size` for SQS

```
SET num_mixing_species = count_mixing_species(disordered_structures)

IF num_mixing_species <= 2:
    SET supercell_size = 12  # Binary
ELSE IF num_mixing_species == 3:
    SET supercell_size = 16  # Ternary
ELSE:
    SET supercell_size = 20  # High-entropy (4+ species)

SET n_mc_steps = 50000 × num_mixing_species
```

---

## Output Format Routing

```
IF downstream tool is pymatgen tool:
    → output_format = 'dict' (default)
    
ELSE IF downstream tool is ase_store_result:
    → output_format = 'ase' (REQUIRED)
    
ELSE IF downstream is VASP/CP2K/QE:
    → output_format = 'poscar' or 'cif'
    
ELSE IF archiving/visualization:
    → output_format = 'cif'
```

---

## Large-Scale Generation Decision (>20 structures)

```
IF N_requested > 20 OR "comprehensive" OR "all possible":
    ↓
    1. CREATE generation_plan.json FIRST
    2. Organize into scientific batches
    3. PRESENT plan to user
    4. WAIT for approval
    5. Execute with checkpointing
    6. Export final results
    
ELSE (N ≤ 20 OR quick exploration):
    → Execute directly without planning file
```
