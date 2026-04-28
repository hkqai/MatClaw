---
name: candidate-generator
description: |
  Generate inorganic crystal structure candidates for computational materials discovery workflows.
  
  **TRIGGER THIS SKILL when user mentions:**
  - "generate candidates", "create structures", "build structures", "structure generation"
  - "screen materials", "explore compositions", "chemical substitution", "doping"
  - "isostructural analogues", "battery cathodes", "perovskites", "solid solutions"
  - "enumerate configurations", "SQS generation", "disorder", "defects"
  - "high-throughput", "DFT screening", "ML training set", "candidate pool"
  - Element lists like "Li-Mn-P-O system", "transition metal oxides"
  - Number requests: "generate 50 structures", "100 candidates"
  
  **Covers COMPLETE pipeline:**
  Elements-only entry → Composition discovery → Seed structures → Chemical space exploration → 
  Disorder/ordering → Defect generation → Perturbation → ASE database storage
    
  **Detailed references available in references/ directory**
---

# Inorganic Candidate Generation Skill

## Core Philosophy

Candidate generation is a **funnel process**: start broad (many compositions, chemistries, configurations), 
then narrow using physical filters (charge neutrality, Ewald energy, thermodynamic stability). 
The workflow is modular and nonlinear—skip phases that don't apply to your discovery goal.

**Workflow phases:**
```
Elements → Compositions → Seed Structures → Chemical Variants → Order/Disorder → Defects → Perturbation → Storage
```

**Entry points:**
- **Elements only** (Li-Mn-P-O) → Phase 0 (composition discovery)
- **Composition known** (LiMnPO₄) → Phase 1 (seed structure) or Phase 2 (if MP structure exists)
- **Structure exists** (from MP/CIF/ASE) → Phase 2 (chemical exploration) or later phases

**Critical rules:**
1. **Always use MCP tools** — Never write custom generators or formula-only scripts
2. **Store in ASE database** — Use `ase_store_result` with `output_format='ase'`
3. **Real structures required** — All outputs must have atomic positions, lattice, spacegroup
4. **Plan for large-scale** — If N > 20, create planning file first (see [references/large-scale-planning.md](references/large-scale-planning.md))

> **Why MCP tools matter:**
> - Generate real crystal structures (CIF/POSCAR) ready for DFT/ML
> - Provide thermodynamic validation (stability, energy above hull)
> - Compute structural properties (spacegroup, coordination, bonds)
> - Custom scripts produce formula strings without structures = scientifically invalid

---

## Quick Tool Reference

**For complete tool specifications with all parameters, see [references/tool-catalog.md](references/tool-catalog.md)**

### By Workflow Phase

| Phase | Tool | Purpose | Key Parameters |
|-------|------|---------|----------------|
| **Phase 0: Composition Discovery** | | | |
| | `composition_enumerator` | Generate charge-balanced compositions | `elements`, `oxidation_states`, `max_formula_units` |
| | `pymatgen_substitution_predictor` | ICSD-based element substitution | `composition`, `threshold` |
| | `mp_search_materials` | Find MP template structures | `elements`, `is_stable` |
| **Phase 1: Seed Structure** | | | |
| | `pymatgen_prototype_builder` | Build from spacegroup | `spacegroup`, `species`, `lattice_parameters` |
| **Phase 2: Chemical Exploration** | | | |
| | `pymatgen_substitution_generator` | **Ordered enumeration** (integer occupancy) | `substitutions`, `n_structures`, `max_attempts` |
| | `pymatgen_ion_exchange_generator` | Charge-neutral ion substitution | `replace_ion`, `with_ions`, `exchange_fraction` |
| **Phase 3: Disorder** | | | |
| | `pymatgen_disorder_generator` | **Fractional occupancy** (statistical disorder) | `site_substitutions` |
| | `pymatgen_enumeration_generator` | Exhaustive ordered configurations | `supercell_size`, `sort_by='ewald'` |
| | `pymatgen_sqs_generator` | Special quasirandom structures | `supercell_size`, `n_mc_steps` |
| **Phase 4: Defects** | | | |
| | `pymatgen_defect_generator` | Point defect supercells | `vacancy_species`, `substitution_species`, `interstitial_species` |
| **Phase 5: Perturbation** | | | |
| | `pymatgen_perturbation_generator` | Rattle atoms + strain lattice | `displacement_max`, `strain_percent` |

### Critical Tool Distinction

**`disorder_generator` vs `substitution_generator`:**

| Aspect | `disorder_generator` | `substitution_generator` |
|--------|---------------------|-------------------------|
| **Output** | Fractional occupancy | Integer occupancy (ordered) |
| **Site occupancy** | 80% Ni + 20% Mn on same site | Site 1: 100% Mn; Sites 2-5: 100% Ni |
| **Example** | Li₃[Ni₂.₄Mn₀.₆]O₆ (statistical) | LiNi₄MnO₁₀ (ordered variant) |
| **Output count** | 1 disordered structure | Multiple ordered configurations |
| **Use for** | SQS generation, VCA | Supercell enumeration, DFT screening |

**Rule:** For partial substitution like Li[Ni₀.₈Mn₀.₂]O₂:
- Want fractional occupancy (every site 80%Ni+20%Mn)? → `disorder_generator`
- Want ordered enumeration (1 specific Ni replaced)? → `substitution_generator`

---

## Workflow Phases Overview

### Phase 0: Composition Discovery (CONDITIONAL)

**When to use:** You only know elements (e.g., "Li-Mn-P-O"), not specific compositions

**Skip if:** You already have target composition or structure

**Three strategies:**
1. **Exhaustive enumeration** — Use `composition_enumerator` for systematic exploration
2. **Template-based** — Use `mp_search_materials` to find analogues, extract patterns
3. **ICSD substitution** — Use `pymatgen_substitution_predictor` from known material

**Decision tree:**
- Known analogue exists? → Template-based + ICSD substitution
- Well-studied system? → Template-based first, enumeration if gaps
- Exploratory discovery? → Exhaustive enumeration → filter by stability

**Output:** Ranked list of stable/metastable compositions

**Next:** For each composition, check MP for structures. If found → Phase 2; if not → Phase 1

**Detailed guidance:** See [references/phase-0-composition-discovery.md](references/phase-0-composition-discovery.md)

---

### Phase 1: Seed Structure (CONDITIONAL)

**When to use:** Need to build structure from scratch (no MP structure available)

**Skip if:** Structure already exists from MP, CIF, or ASE database

**Tool:** `pymatgen_prototype_builder`

**Common prototypes:**
- Rock-salt (225, Fm-3m): NaCl, LiF, MgO
- Perovskite (221, Pm-3m): BaTiO₃, SrTiO₃
- Spinel (227, Fd-3m): MgAl₂O₄, LiMn₂O₄
- Layered oxide (166, R-3m): LiCoO₂, LiNiO₂
- Olivine (62, Pnma): LiFePO₄, LiMnPO₄

**Example:**
```python
seed = pymatgen_prototype_builder(
    spacegroup=225,  # Rock-salt
    species=['Li', 'O'],
    lattice_parameters=[4.33]  # cubic
)
```

**Next:** Phase 2 (chemical exploration)

---

### Phase 2: Chemical Space Exploration (CONDITIONAL)

**When to use:** Want to explore different compositions/dopings while keeping structure

**Skip if:** Want to keep exact composition

**Branch A — Charge-neutral (ionic materials):**
- Tool: `pymatgen_ion_exchange_generator`
- Use for: Battery materials, ionic conductors, charge-balanced doping
- Automatically adjusts stoichiometry for charge neutrality

**Branch B — Exploratory (screening):**
- Tool: `pymatgen_substitution_generator`
- Use for: Isostructural analogues, ML training sets, exploratory screening
- Generates ordered structures with integer occupancy

**Decision:**
- Material is ionic + charge balance critical? → Branch A (ion_exchange)
- Exploratory screening / charge handled post-hoc? → Branch B (substitution)

**Examples:**
```python
# Branch A: Li → Na battery cathode analogue
ion_exchange_generator(
    replace_ion='Li',
    with_ions=['Na'],
    exchange_fraction=1.0
)

# Branch B: Screen B-site metals in perovskite
substitution_generator(
    substitutions={'Ti': ['Zr', 'Hf', 'Sn']},
    n_structures=1,
    enforce_charge_neutrality=False
)
```

**Next:** Phase 3 (if structures have disorder) or Phase 4 (defects) or Phase 5 (perturbation)

---

### Phase 3: Disorder Resolution (CONDITIONAL)

**When to use:** Structures have fractional site occupancies

**Skip if:** All structures fully ordered

**Creating disorder (order → disorder):**
- Tool: `pymatgen_disorder_generator`
- Use for: Li[Ni₀.₈Mn₀.₂]O₂-type fractional substitutions
- Creates statistical disorder (all sites get fractional occupancy)

**Resolving disorder (disorder → ordered):**

**Branch A — Ground-state search (complete enumeration):**
- Tool: `pymatgen_enumeration_generator`
- Use for: Find all low-energy orderings, cluster expansion training
- Keep `supercell_size ≤ 2` for ternary+ systems
- Sort by `'ewald'` for lowest energy first

**Branch B — Solid solution modeling (quasirandom):**
- Tool: `pymatgen_sqs_generator`
- Use for: Model random alloys, high-entropy materials (≥4 mixing species)
- Returns best quasirandom approximant
- Increase `n_mc_steps` for multicomponent systems

**Decision:**
- Need ALL orderings? → Enumeration (supercell_size ≤ 2)
- Modeling disorder itself? → SQS
- High-entropy (≥4 species)? → SQS (enumeration intractable)

**Next:** Phase 4 (defects) or Phase 5 (perturbation) or storage

---

### Phase 4: Defect Generation (OPTIONAL)

**When to use:** Need point defect supercells (vacancies, substitutions, interstitials)

**Skip if:** Only need perfect bulk structures

**Tool:** `pymatgen_defect_generator`

**Important:** Pass single, ordered, defect-free host structure (not multiple structures)

**Example:**
```python
defect_generator(
    input_structure=perfect_host,  # Single structure only!
    vacancy_species=['Li'],
    substitution_species={'Mn': ['Fe', 'Co']},
    supercell_min_atoms=64
)
```

**Outputs:** One supercell per symmetry-inequivalent defect site

**Next:** Phase 5 (perturbation recommended for defects) or storage

---

### Phase 5: Perturbation/Augmentation (OPTIONAL)

**When to use:**
- Break symmetry before DFT (avoid saddle points)
- ML dataset augmentation
- Probe elastic/thermal response

**Tool:** `pymatgen_perturbation_generator`

**Parameters by use case:**
- **DFT relaxation:** `displacement_max=0.05`, `strain_percent=None`, `n_structures=1`
- **ML augmentation:** `displacement_max=0.15`, `strain_percent=[-2, 2]`, `n_structures=10`
- **Defect relaxation:** `displacement_max=0.08`, `strain_percent=None`, `n_structures=3`

**Next:** Storage in ASE database

---

## Storage and Validation

### Store in ASE Database

**Critical:** Always use `output_format='ase'` when feeding to `ase_store_result`

```python
# Generate with ASE format
result = pymatgen_substitution_generator(
    input_structures=structure,
    substitutions={'Li': 'Na'},
    output_format='ase'  # REQUIRED for ASE database
)

# Store each structure
for s in result['structures']:
    ase_store_result(
        db_path='candidates.db',
        atoms_dict=s['structure'],
        key_value_pairs={
            'compound': s['formula'],  # NOT 'formula' (reserved)
            'generator': 'substitution',
            'campaign': 'cathode_screen_2026'
        }
    )
```

**ASE reserved keys to AVOID:**
`id`, `unique_id`, `formula`, `spacegroup`, `energy`, `forces`, `cell`, `natoms`, etc.

**Use instead:** `compound`, `sg_num`, `candidate_id`, etc.

### Optional MP Stability Check

```python
# Filter by thermodynamic stability
for structure in final_structures:
    mp_result = mp_search_materials(formula=structure['formula'])
    
    if mp_result['count'] > 0:
        # Composition exists in MP and likely stable
        structure['mp_stable'] = True
    else:
        # Novel or metastable
        structure['requires_dft'] = True
```

---

## Decision Algorithm

**For complete decision trees and parameter calculation rules, see [references/decision-trees.md](references/decision-trees.md)**

### Quick Workflow Decision

```
1. Have existing structure? 
   → YES: use it | NO: pymatgen_prototype_builder
   
2. Want new chemistries?
   → YES: Ionic + charge critical? 
      → YES: ion_exchange_generator
      → NO: substitution_generator
   
3. Structures have partial occupancies?
   → NO: skip | YES: Need ALL orderings?
      → YES: enumeration_generator (supercell_size ≤ 2)
      → NO: Modeling disorder? 
         → YES: sqs_generator
         
4. Need defects?
   → YES: defect_generator (single structure)
   
5. Need perturbations?
   → YES: perturbation_generator
   
6. Store with ase_store_result (output_format='ase')
```

### Large-Scale Generation (>20 structures)

**If user requests >20 structures:**
1. **Create planning file FIRST** (don't execute immediately)
2. Organize into scientific batches
3. Present plan to user for approval
4. Execute with checkpointing
5. Export final results

**See:** [references/large-scale-planning.md](references/large-scale-planning.md) for complete planning workflow

---

## Common Patterns

**Brief examples showing typical workflows**

### Isostructural Analogue Screen

```python
# 1. Build rock-salt seed
seed = pymatgen_prototype_builder(
    spacegroup=225, 
    species=['Li','O'], 
    lattice_parameters=[4.33]
)

# 2. Swap elements: Li → Na,K,Rb; O → S,Se
variants = pymatgen_substitution_generator(
    input_structures=seed['structures'][0],
    substitutions={'Li': ['Na', 'K', 'Rb'], 'O': ['S', 'Se']},
    n_structures=1,  # Deterministic swaps
    max_attempts=6,
    output_format='ase'
)

# 3. Store in ASE database
for s in variants['structures']:
    ase_store_result(
        db_path='screen.db',
        atoms_dict=s,
        key_value_pairs={'compound': s['formula'], 'campaign': 'rocksalt'}
    )
```

### Battery Cathode Analogue (Li → Na)

```python
# Get LiCoO2 from MP
licoo2 = mp_get_material_properties(material_ids=['mp-24850'])

# Exchange Li → Na with charge neutrality
exchanged = pymatgen_ion_exchange_generator(
    input_structures=licoo2['properties'][0]['structure'],
    replace_ion='Li',
    with_ions=['Na'],
    exchange_fraction=1.0,
    output_format='ase'
)
```

### High-Entropy Oxide SQS

```python
# Starting from disordered structure with 5-component cation mixing
# Input has fractional occupancies: {Mg:0.2, Co:0.2, Ni:0.2, Cu:0.2, Zn:0.2}
sqs = pymatgen_sqs_generator(
    input_structures=disordered_structure,
    supercell_size=20,
    n_structures=5,
    n_mc_steps=500000,  # High for 5 components
    output_format='ase'
)
# Best SQS is sqs['structures'][0] (sorted by sqs_error)
```

### Ground-State Ordering Search

```python
# Li₀.₅CoO₂ with partial Li occupancy
ordered = pymatgen_enumeration_generator(
    input_structures=disordered_licoo2,
    supercell_size=2,
    n_structures=100,
    sort_by='ewald',
    output_format='ase'
)
# Top 10 by Ewald energy are most plausible ground states
```

---

## Common Pitfalls

**For complete troubleshooting guide, see [references/gotchas.md](references/gotchas.md)**

### Critical Errors to Avoid

1. **Using wrong output_format for ASE** → Always `output_format='ase'` for `ase_store_result`
2. **Using ASE reserved keys** → Never use `formula`, `spacegroup`, `id`, `energy`, etc. in metadata
3. **`substitution_generator` hangs** → Set `max_attempts = n_structures × num_combinations`
4. **`enumeration_generator` hangs** → Keep `supercell_size ≤ 2` for ternary+ systems
5. **Expecting fractional occupancy from `substitution_generator`** → Use `disorder_generator` instead
6. **`ion_exchange_generator` returns 0** → Try different `exchange_fraction` values

### Quick Debugging

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Missing required keys: ['numbers']" | Wrong output_format | Set `output_format='ase'` |
| "Bad key" error | ASE reserved name | Use `compound` not `formula` |
| Tool hangs | supercell_size too large | Reduce to 1-2 or switch to SQS |
| count: 0 in result | max_attempts too low | Calculate explicitly |
| High sqs_error | Poor convergence | Increase n_mc_steps |

---

## Connecting to Downstream Workflows

### To candidate-screener Skill

After generating candidates and storing in ASE database:

```python
# Query ASE database for all candidates
candidates = ase_query_db(
    db_path='candidates.db',
    property_filters={'campaign': 'cathode_screen_2026'}
)

# Pass to candidate-screener for property enrichment, filtering, ranking
# The candidate-screener will:
# 1. Validate structures
# 2. Retrieve properties (MP → ASE → ML hierarchy)
# 3. Apply screening criteria
# 4. Rank by multi-objective optimization
```

### To VASP/DFT Calculations

```python
# Generate candidates with POSCAR format for VASP
result = pymatgen_substitution_generator(
    input_structures=structure,
    substitutions={'Li': 'Na'},
    output_format='poscar'  # For VASP
)

# Each structure can be written directly to POSCAR file
for i, s in enumerate(result['structures']):
    with open(f'POSCAR_{i}', 'w') as f:
        f.write(s['structure'])
```

---

## Reference Files

Complete detailed documentation available in `references/` directory:

1. **[tool-catalog.md](references/tool-catalog.md)** — Complete tool specifications with all parameters, returns, examples
2. **[decision-trees.md](references/decision-trees.md)** — Detailed decision logic and parameter calculation rules
3. **[phase-0-composition-discovery.md](references/phase-0-composition-discovery.md)** — Complete Phase 0 strategies and examples  
4. **[gotchas.md](references/gotchas.md)** — Troubleshooting guide with common errors and solutions
5. **[large-scale-planning.md](references/large-scale-planning.md)** — Planning workflow for >20 structures with checkpointing

---

## Summary

**This skill provides guidance on:**
- **WHAT** tool to use for each generation scenario
- **WHY** certain approaches are appropriate
- **HOW** to connect tools into multi-phase workflows
- **WHEN** to use planning for large-scale generation

**Key principles:**
1. Always use MCP tools (never write custom generators)
2. Start broad, narrow with physical filters
3. Store everything in ASE database
4. Use `output_format='ase'` for ASE storage
5. Plan first for >20 structures

**Entry point decision:**
- Elements only? → Phase 0 (composition discovery)
- Composition known? → Phase 1 (seed) or Phase 2 (if MP exists)
- Structure exists? → Phase 2+ (exploration, disorder, defects, perturbation)

**For complete details, algorithms, and troubleshooting:** See reference files in `references/` directory.
