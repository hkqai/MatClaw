---
name: candidate-generator
description: Generate inorganic crystal structure candidates for computational materials discovery workflows. Use this skill whenever the user wants to build, explore, or diversify a pool of inorganic structures for DFT screening, high-throughput calculations, machine learning dataset construction, or property-guided search. This skill covers the COMPLETE candidate generation pipeline from elements to structures - composition discovery (elements-only entry) -> seed structure creation -> chemical space exploration -> configurational ordering -> defect generation -> ensemble augmentation.
---

# Inorganic Candidate Generation

This skill guides the systematic generation of inorganic crystal structure candidates using
a suite of ten tools (3 composition discovery + 7 structure generation). The methodology is:
**discover compositions → prototype → explore chemistry → resolve disorder → add defects → augment**,
selecting the appropriate branch(es) for the discovery goal.

The core philosophy: candidate generation is a funnel. Start broad (many compositions,
many chemistries, many configurations), then narrow using physical filters (charge neutrality,
Ewald energy, thermodynamic stability from MP). Always track structures in the ASE database
using `ase_store_result` so nothing is recomputed.

**Entry Points:**
- **Elements only** (Li-Mn-P-O) → Phase 0 (composition discovery)
- **Composition known** (LiMnPO₄) → Phase 1 (seed structure)
- **Structure exists** (from MP/CIF) → Phase 2 (chemical exploration)

---

## Tool Catalogue

### Phase 0 Tools: Composition Discovery

### 0A. `composition_enumerator` — Oxidation-Balanced Enumeration
Generates all charge-balanced compositions from element lists and oxidation state constraints.
Use when you know which elements to explore but not which compositions exist.

**Key parameters:**
- `elements`: list of element symbols, e.g. `['Li', 'Mn', 'P', 'O']`
- `oxidation_states`: dict mapping elements to allowed oxidation states, e.g. `{'Li': [1], 'Mn': [2, 3], 'P': [5], 'O': [-2]}`
- `max_formula_units`: cap on formula unit count (default 6, increase for complex compositions)
- `max_atoms_per_formula`: hard limit on total atoms (default 30, prevents combinatorial explosion)
- `anion_cation_ratio_max`: maximum anion:cation ratio (default 4.0, excludes Li₁Mn₁₀P₁₀O₅₀-type nonsense)
- `min_cation_fraction`: minimum cation fraction (default 0.05, excludes Li₀.₀₁O₀.₉₉-type nonsense)
- `require_all_elements`: if True, only returns compositions containing ALL specified elements (default True)
- `allow_mixed_valence`: if True, allows mixed oxidation states (e.g., Mn²⁺/Mn³⁺ in mixed-valence manganates) (default True)
- `sort_by`: `'atoms'` (fewest atoms first), `'anion_ratio'` (lowest O/cation ratio), `'alphabetical'`
- `output_format`: `'minimal'` (formula strings) or `'detailed'` (full metadata)

**Returns:**
```python
{
  "success": True,
  "count": 12,
  "compositions": [
    "Li3PO4",
    "LiMnPO4",  # Target composition! (olivine battery cathode)
    "LiFePO4",  # If Fe added to oxidation_states
    ...
  ],
  # OR with output_format='detailed':
  "compositions": [
    {
      "formula": "LiMnPO4",
      "reduced_formula": "LiMnPO4",
      "num_atoms": 7,
      "cation_count": 3,
      "anion_count": 4,
      "anion_cation_ratio": 1.33,
      "oxidation_states": {"Li": 1, "Mn": 2, "P": 5, "O": -2},
      "charge": 0
    },
    ...
  ]
}
```

**Chemical filters explained:**
- `max_atoms_per_formula=30`: Prevents unrealistically large formulas (e.g., Li₁₀Mn₁₀P₁₀O₄₀ with 70 atoms)
- `anion_cation_ratio_max=4.0`: Prevents anion-heavy compositions (e.g., LiMn₁₀P₁₀O₅₀ with ratio ≈ 2.4)
- `min_cation_fraction=0.05`: Prevents trace cation compositions (e.g., Li₀.₀₁Mn₀.₉₉O unphysical)

**When to adjust defaults:**
- Increase `max_formula_units` for complex phases (spinels, Ruddlesden-Popper)
- Decrease `anion_cation_ratio_max` for metal-rich compounds
- Set `require_all_elements=False` to include binaries (e.g., Li₂O, Mn₃O₄) alongside ternaries/quaternaries

**Workflow:**
1. Call `composition_enumerator` with target elements
2. Filter results by `stability_analyzer` (eliminate compositions far above convex hull)
3. For each stable composition, proceed to Phase 1 (prototype_builder) or query MP for existing structures

---

### 0B. `pymatgen_substitution_predictor` — ICSD-Based Substitution
Predicts likely element substitutions using data mining from 100k+ ICSD structures.
Use when you have a known composition and want to find chemically reasonable analogues.

**Key parameters:**
- `composition`: starting composition, e.g. `'LiFePO4'`
- `to_this_composition`: if False (default), finds what this composition can become; if True, finds what can transform INTO this composition
- `threshold`: probability cutoff (0.001 = permissive, 0.1 = strict)
- `max_suggestions`: limit number of suggestions (default None = unlimited)
- `group_by_probability`: if True, returns {high: [...], medium: [...], low: [...]}

**Returns:**
```python
{
  "success": True,
  "original_composition": "LiFePO4",
  "direction": "from_this_composition",
  "suggestions": {
    "high": [{"formula": "LiMnPO4", "probability": 0.85}, ...],
    "medium": [{"formula": "LiCoPO4", "probability": 0.45}, ...],
    "low": [{"formula": "LiNiPO4", "probability": 0.02}, ...]
  }
}
```

**Use case: Template-based discovery**
```python
# Find what LiFePO₄ can transform into
result = pymatgen_substitution_predictor('LiFePO4', threshold=0.01)

# Extract high-confidence suggestions
target_formulas = [s['formula'] for s in result['suggestions']['high']]

# For each, check MP for structures
for formula in target_formulas:
    mp_result = mp_search_materials(formula=formula)
    if mp_result['count'] > 0:
        # Structure exists in MP, can use directly
```

**Limitation:** ICSD substitution patterns are conservative (based on existing materials).
For truly novel compositions (e.g., where no close analogues exist in the database),
use `composition_enumerator` instead.

---

### 0C. `mp_search_materials` — Template Structure Search
Queries Materials Project for structures matching composition/chemistry constraints.
Use to find structural templates for target element systems.

**Key parameters for template search:**
- `elements`: list of elements, e.g. `['Li', 'Fe', 'P', 'O']` (finds all Li-Fe-P-O compounds)
- `num_elements`: constrain to binary (2), ternary (3), quaternary (4), etc.
- `crystal_system`: `'cubic'`, `'tetragonal'`, `'orthorhombic'`, etc. (omit for all)
- `spacegroup_number`: specific space group (e.g., 225 for fluorite)
- `is_stable`: True (only thermodynamically stable), False (include metastable)
- `limit`: max results (default 100)

**Template discovery workflow:**
```python
# Step 1: Find analogues with similar chemistry (Fe instead of Mn)
li_fe_p_o = mp_search_materials(
    elements=['Li', 'Fe', 'P', 'O'],
    num_elements=4,
    is_stable=True,
    limit=50
)

# Step 2: Extract stoichiometric patterns
patterns = set()
for mat in li_fe_p_o['materials']:
    # Identify pattern: LiMPO₄, Li₃M₂(PO₄)₃, etc.
    patterns.add(mat['composition_reduced'])

# Step 3: Use patterns to constrain composition_enumerator
if 'NaMnPO4' in patterns:
    # Found olivine pattern (AMPO₄)! Prioritize compositions around 7 atoms
    result = composition_enumerator(
        elements=['Li', 'Mn', 'P', 'O'],
        oxidation_states={'Li': [1], 'Mn': [2], 'P': [5], 'O': [-2]},
        max_formula_units=8  # Allows LiMnPO₄ (7 atoms)
    )
```

**When no direct templates exist:**
If `mp_search_materials(['Li', 'Mn', 'P', 'O'])` returns 0 results, try:
1. Substitute one element: `['Na', 'Mn', 'P', 'O']` or `['Li', 'Fe', 'P', 'O']`
2. Search broader family: `['alkali', 'TM', 'P', 'O']` where TM = transition metal
3. Fall back to `composition_enumerator` (exhaustive enumeration)

---

### Phase 1-5 Tools: Structure Generation

### 1. `pymatgen_prototype_builder` — Seed Structure
Builds an ideal crystal from a spacegroup number/symbol, species list, and lattice parameters.
This is the **entry point** for any workflow that starts from scratch rather than an existing structure.

**Key parameters:**
- `spacegroup`: int (1–230) or Hermann-Mauguin symbol, e.g. `225` or `"Fm-3m"`
- `species`: list of element symbols (`['La', 'Mn', 'O', 'O', 'O']`) or Wyckoff dict
- `lattice_parameters`: `[a, b, c, alpha, beta, gamma]` in Å and degrees; `[a]` works for cubic
- `wyckoff_positions`: optional dict mapping Wyckoff labels to species/coords
- `output_format`: `'dict'` (default, pass to other tools), `'poscar'`, `'cif'`, `'ase'`

**Returns:** `structures[i].structure` — pass directly to substitution, enumeration, or defect tools.

**`wyckoff_positions` proximity gotcha:** Passing a Wyckoff dict (e.g. `{'1a': 'Ba', '1b': 'Ti', '3c': 'O'}`) can raise
"sites less than 0.01 Å apart" for multi-species prototypes where pymatgen auto-generates
overlapping fractional coords. **Preferred approach:** supply explicit `species` and `coords` lists
instead, and use `validate_proximity=False` when debugging a new prototype before finalising
lattice parameters.

---

### 2. `pymatgen_substitution_generator` — Chemical Space Exploration
Replaces elements in existing structures. Best for isostructural analogue screening across
a fixed lattice topology when **charge balance is not strictly required**.

**Key parameters:**
- `substitutions`: `{'Li': 'Na'}` (full swap), `{'Li': ['Na', 'K']}` (one variant per replacement),
  `{'Li': {'replace_with': 'Na', 'fraction': 0.5}}` (50 % doping)
- `n_structures`: variants to generate **per substitution combination** (default 5).
  For deterministic full swaps (`fraction=1.0`) set this to **1** — higher values only
  produce identical duplicates. Total output = `n_structures × num_combinations`,
  capped by `max_attempts`.
- `max_attempts`: **hard cap on total output count** (default 50). If you supply N
  substitution options with n_structures=k, set `max_attempts ≥ N × k` or outputs
  will be silently truncated. Example: 8 B-site metals with n_structures=1 needs
  `max_attempts=8` (or higher); with n_structures=3 needs `max_attempts=24`.
- `enforce_charge_neutrality`: set `True` for ionic materials
- `site_selector`: `'all'`, `'wyckoff_4a'`, `'coordination_6'`, etc.

**When to use over `ion_exchange_generator`:** when you want exploratory doping without
strict stoichiometry adjustment and charge neutrality is handled manually or checked post-hoc.

---

### 3. `pymatgen_ion_exchange_generator` — Charge-Neutral Substitution
Replaces a mobile ion (e.g. Li⁺) with one or more ions, **automatically adjusting stoichiometry**
so that total ionic charge is conserved. Only charge-neutral structures are returned by default.

**Key parameters:**
- `replace_ion`: element to replace, e.g. `'Li'`
- `with_ions`: `['Na', 'K']` (equal weight) or `{'Na': 0.6, 'Mg': 0.4}` (weighted split)
- `exchange_fraction`: fraction of sites to exchange (0–1), default `1.0`
- `allow_oxidation_state_change`: `False` (default) = only neutral structures returned
- `max_structures`: cap on returned structures per input (default 10)

**Prototypical use cases:** Li → Na/K battery cathode analogues, Ca²⁺ → La³⁺ doping in oxides.

---

### 4. `pymatgen_enumeration_generator` — Exhaustive Ordering of Disordered Structures
Takes structures with **fractional site occupancies** and returns all symmetry-inequivalent
ordered supercell approximants, ranked by Ewald energy or cell size.

**Key parameters:**
- `supercell_size`: supercell multiplier (1–4, default 2); creates a supercell of size
  `[supercell_size, supercell_size, 1]` to accommodate fractional occupancies. Keep ≤ 2
  for ternaries to avoid combinatorial explosion
- `n_structures`: max ordered structures returned per input (default 20, max 500)
- `sort_by`: `'ewald'` (default, lowest energy first), `'num_sites'`, `'random'`
- `add_oxidation_states`: auto-assign oxidation states for Ewald ranking (default `True`)
- `refine_structure`: re-symmetrize before enumeration (recommended, default `True`)


**When to use over `sqs_generator`:** when you need the complete ordered-configuration pool,
want to identify the ground-state ordering, or are building a cluster expansion training set.

---

### 5. `pymatgen_sqs_generator` — Special Quasirandom Structures
Finds a small ordered supercell whose Warren-Cowley pair correlations best mimic a
perfectly random alloy. Returns the **single best quasirandom approximant** per input,
not the full ordered-configuration space.

**Key parameters:**
- `supercell_size`: target formula units in SQS cell (default 8; use 8–16 for binary, 12–24 for ternary)
- `supercell_matrix`: explicit `[nx, ny, nz]` or 3×3 matrix (overrides `supercell_size`)
- `n_structures`: independent SQS candidates per input (default 3); ranked by `sqs_error`
- `n_mc_steps`: Monte Carlo steps per candidate (default 50 000; increase for multicomponent)
- `n_shells`: correlation shells in objective function (default 4)
- `seed`: set for reproducibility
- `use_mcsqs`: use ATAT `mcsqs` binary if available (better quality for large systems)

**When to use over `enumeration_generator`:** target system is a solid solution / high-entropy
material where disorder is the physical state being modelled, not a defect to be minimised.

---

### 6. `pymatgen_defect_generator` — Point Defect Supercells
Takes a **perfect bulk host structure** and generates one supercell per symmetry-inequivalent
defect site. Supports vacancies, substitutional dopants, and interstitials.

**Key parameters:**
- `vacancy_species`: `['Li', 'O']` — generate V_Li, V_O defects
- `substitution_species`: `{'Fe': ['Mn', 'Co']}` — Mn_Fe and Co_Fe substitutionals
- `interstitial_species`: `['Li']` — find void sites and insert Li
- `charge_states`: `{'V_Li': [-1, 0, 1]}` — metadata only; structures are always neutral geometry
- `supercell_min_atoms`: target atoms in defect supercell (default 64; 64–128 for plane-wave DFT)
- `inequivalent_only`: `True` (default) — generate only symmetry-distinct defects

**Downstream:** feed outputs to `pymatgen_perturbation_generator` to rattle defect geometries,
or save directly to the ASE database via `ase_store_result`.

---

### 7. `pymatgen_perturbation_generator` — Structural Ensemble / Augmentation
Applies random atomic displacements ("rattling") and/or lattice strain to create ensembles
of perturbed structures. Does **not** change composition.

**Key parameters:**
- `displacement_max`: max displacement per atom in Å (default 0.1; typical range 0.05–0.2)
- `strain_percent`: `None` (off), scalar (uniform), `[min, max]` (random range), or
  6-element Voigt tensor `[e_xx, e_yy, e_zz, e_xy, e_xz, e_yz]`
- `n_structures`: perturbed copies per input (default 10, max 200)
- `seed`: for reproducibility

**Primary uses:**
- Provide DFT starting geometries that are not stuck at a symmetry saddle point
- Augment ML training datasets with off-equilibrium configurations
- Generate strained cells for elastic property screening

---

## Workflow Phases

### Phase 0: Composition Discovery (CONDITIONAL)

**When to use this phase:**
- You only know which elements to explore (e.g., Li-Mn-P-O for battery cathodes)
- You don't know which compositions exist or are stable
- You want to discover new materials in a chemical system

**Skip this phase if:**
- You already have a target composition (go to Phase 1)
- You have an existing structure (go to Phase 2)

---

#### Strategy 1: Exhaustive Enumeration (Fast, Systematic)

Use `composition_enumerator` to generate ALL charge-balanced compositions:

```python
# Example: Discover Li-Mn-P-O battery cathode compositions
result = composition_enumerator(
    elements=['Li', 'Mn', 'P', 'O'],
    oxidation_states={
        'Li': [1],       # Li⁺
        'Mn': [2, 3],    # Mn²⁺, Mn³⁺
        'P': [5],        # P⁵⁺ (phosphate)
        'O': [-2]        # O²⁻
    },
    max_formula_units=6,
    max_atoms_per_formula=30,
    require_all_elements=True,  # Only quaternary Li-Mn-P-O, not ternaries
    sort_by='atoms',  # Simplest compositions first
    output_format='detailed'
)

# Result: ~12 compositions including LiMnPO₄, Li₃Mn(PO₄)₂, Mn₃(PO₄)₂, etc.
compositions = result['compositions']
```

**Next step:** Filter by stability
```python
stable_compositions = []
for comp in compositions:
    stability = stability_analyzer(composition=comp['formula'])
    if stability['is_stable'] or stability['energy_above_hull'] < 0.1:
        stable_compositions.append(comp['formula'])

# Feed to Phase 1 or query MP for existing structures
```

---

#### Strategy 2: Template-Based Discovery (Structural Analogues)

Find Materials Project structures with similar chemistry, extract patterns:

```python
# Step 1: Search for analogues (Na or Fe instead of Li/Mn)
na_templates = mp_search_materials(
    elements=['Na', 'Mn', 'P', 'O'],
    num_elements=4,
    is_stable=True
)

if na_templates['count'] == 0:
    # Try Fe instead of Mn (well-known LiFePO4)
    fe_templates = mp_search_materials(
        elements=['Li', 'Fe', 'P', 'O'],
        num_elements=4,
        is_stable=True
    )

# Step 2: Extract stoichiometric patterns
patterns = {}
for mat in fe_templates['materials']:
    formula = mat['composition_reduced']
    patterns[formula] = mat['spacegroup_number']

print(f"Found patterns: {patterns}")
# Example output: {'LiFePO4': 62, 'Li3PO4': 61, ...}

# Step 3: Use patterns to guide composition_enumerator
if 'LiFePO4' in patterns:
    # Olivine pattern exists (AMPO₄) → prioritize LiMnPO₄
    target_formulas = ['LiMnPO4']
    
if 'Li3PO4' in patterns:
    # Phosphate pattern exists → Li₃PO₄ likely!
    target_formulas.append('Li3PO4')

# Proceed to Phase 1 with these target compositions
```

---

#### Strategy 3: ICSD Substitution Patterns (Data-Driven)

Find statistically likely substitutions from known materials:

```python
# Starting from known La₂WO₆ structure
substitutions = pymatgen_substitution_predictor(
    composition='La2WO6',
    to_this_composition=False,  # What can La₂WO₆ become?
    threshold=0.01,
    group_by_probability=True
)

# Extract high-confidence suggestions
high_prob = substitutions['suggestions']['high']
target_formulas = [s['formula'] for s in high_prob]

# Check which ones exist in MP
for formula in target_formulas:
    mp_result = mp_search_materials(formula=formula)
    if mp_result['count'] > 0:
        print(f"{formula}: exists in MP (mp-id: {mp_result['materials'][0]['material_id']})")
    else:
        print(f"{formula}: novel composition candidate!")
```

**Limitation:** Substitution predictor is conservative (only suggests observed patterns).
For truly novel compositions, use Strategy 1 (enumeration).

---

#### Decision Tree for Phase 0

```
START: Have elements, need compositions
│
├─ Known analogue exists? (e.g., LiFePO₄ for Li-Mn-P-O)
│  ├─ YES → Strategy 3 (substitution_predictor) + Strategy 2 (MP templates)
│  └─ NO → Strategy 1 (composition_enumerator)
│
├─ Chemical system well-studied? (battery cathodes, perovskites)
│  ├─ YES → Strategy 2 (MP templates) first, then Strategy 1 if gaps
│  └─ NO → Strategy 1 (composition_enumerator)
│
└─ Exploratory discovery? (don't know what to expect)
   └─ Strategy 1 (composition_enumerator) → filter by stability
```

**Output of Phase 0:** Ranked list of compositions
**Next phase:** For each composition, go to Phase 1 (build structure) or Phase 2 (if MP structure exists)

---

### Phase 1: Seed Structure

Start here if no structure exists yet.

```
pymatgen_prototype_builder(
    spacegroup=225,           # Fm-3m (rock-salt)
    species=['Li', 'O'],
    lattice_parameters=[4.33] # cubic: [a]
)
```

If a known structure already exists (from `mp_get_material_properties`, a CIF file, or the
ASE database), skip this step and pass that structure directly.

**Common prototypes:**

| Prototype | SG # | Symbol | Example |
|-----------|------|--------|---------|
| Rock-salt | 225 | Fm-3m | NaCl, LiF, MgO |
| Perovskite | 221 | Pm-3m | BaTiO₃, SrTiO₃ |
| Spinel | 227 | Fd-3m | MgAl₂O₄, LiMn₂O₄ |
| Layered oxide (α-NaFeO₂) | 166 | R-3m | LiCoO₂, LiNiO₂ |
| Olivine | 62 | Pnma | LiFePO₄, LiMnPO₄ |
| Rutile | 136 | P4₂/mnm | TiO₂, SnO₂ |
| Wurtzite | 186 | P6₃mc | ZnO, GaN |
| Fluorite | 225 | Fm-3m | CaF₂, CeO₂ |

---

### Phase 2: Chemical Space Exploration

Choose the branch based on whether charge-neutrality must be enforced:

**Branch A — Exploratory (charge balance not enforced):**
```
pymatgen_substitution_generator(
    input_structures=seed_structure,
    substitutions={'Li': ['Na', 'K', 'Rb'], 'Fe': ['Mn', 'Co', 'Ni']},
    n_structures=10,
    enforce_charge_neutrality=False
)
```
Use when: screening isostructural analogues, building diverse training sets.

**Branch B — Charge-neutral (ionic materials):**
```
pymatgen_ion_exchange_generator(
    input_structures=seed_structure,
    replace_ion='Li',
    with_ions={'Na': 0.5, 'Mg': 0.5},
    exchange_fraction=1.0,
    max_structures=20
)
```
Use when: battery cathode analogues, any case where the oxidation-state bookkeeping must be exact.

Both branches accept lists of input structures — pipe multiple seeds through in one call.

---

### Phase 3: Resolve Disorder (if structures have partial occupancies)

If Phase 2 produced or if you started from a disordered structure:

**Ground-state search (small cells, complete enumeration):**
```
pymatgen_enumeration_generator(
    input_structures=disordered_structs,
    supercell_size=2,
    n_structures=50,
    sort_by='ewald'
)
```

**Solid-solution modelling (large / high-entropy systems):**
```
pymatgen_sqs_generator(
    input_structures=disordered_struct,
    supercell_size=16,
    n_structures=5,
    n_mc_steps=200000,
    seed=42
)
```

Decision rule:
- **Enumeration** when you need all low-energy orderings or a CE training set.
- **SQS** when disorder is the target state (e.g. (Li,Na)₀.₅CoO₂ solid solution).
- For high-entropy systems (≥ 4 mixing species), prefer SQS; enumeration becomes
  intractable above `supercell_size=2`.

---

### Phase 4: Defect Generation (optional branch)

Fork off from any ordered structure to study point defects:

```
pymatgen_defect_generator(
    input_structure=ordered_structure,
    vacancy_species=['Li'],
    substitution_species={'Fe': ['Mn', 'Co']},
    interstitial_species=['Li'],
    charge_states={'V_Li': [-1, 0, 1]},
    supercell_min_atoms=128
)
```

**Important:** Pass only a single, ordered, defect-free host structure. The tool generates
one supercell per inequivalent defect site automatically — do not pre-expand the cell.

---

### Phase 5: Perturbation / Augmentation

Apply to any structure from Phases 1–4 to:
- Break symmetry before DFT relaxation (avoid false saddle-point convergence)
- Augment ML training datasets
- Probe elastic and thermal response

```
pymatgen_perturbation_generator(
    input_structures=ordered_or_defect_structures,
    displacement_max=0.1,
    strain_percent=[-2.0, 2.0],
    n_structures=20,
    seed=0
)
```

For defect geometries, use `displacement_max=0.05–0.1` Å (subtle rattling). For
ML data augmentation, `0.1–0.2` Å with random strain is typical.

---

## Connecting to the Rest of the Workflow

### Saving to the ASE Database

Always store generated structures so they can be queried later without regeneration:

```
ase_store_result(
    db_path='candidates.db',
    atoms_dict=structure['structure'],   # MUST use output_format='ase' — see note below
    key_value_pairs={
        'generator': 'substitution',
        'compound': structure['formula'],   # NOT 'formula' — see reserved keys below
        'campaign': 'cathode_screen_2026',
        'source_structure': 'LiCoO2_mp-24850'
    }
)
```

**`output_format` must be `'ase'` when feeding into `ase_store_result`:**
`ase_store_result` requires ASE-native keys (`numbers`, `positions`, `cell`, `pbc`), which
are only produced when the upstream pymatgen tool is called with `output_format='ase'`.
Using the default `output_format='dict'` produces a pymatgen `Structure.as_dict()` object
(with `@module`, `@class`, `sites`, `lattice`, etc.) that will be rejected with:
`"atoms_dict missing required keys: ['numbers']"`.
Always set `output_format='ase'` on any pymatgen tool whose result goes directly to `ase_store_result`.

**ASE reserved key names — never use these in `key_value_pairs`:**
ASE's `db.write()` will raise `ValueError: Bad key` for any of the following built-in column
names: `id`, `unique_id`, `ctime`, `mtime`, `user`, `calculator`, `energy`, `forces`,
`stress`, `magmoms`, `charges`, `cell`, `pbc`, `natoms`, `formula`, `mass`, `volume`,
`spacegroup`. Use unambiguous alternatives e.g. `compound` instead of `formula`,
`sg_num` instead of `spacegroup`, `uid` instead of `unique_id`.

Query existing candidates before generating new ones to avoid duplication:
```
ase_query_db(db_path='candidates.db', property_filters={'campaign': 'cathode_screen_2026'})
```

### Filtering with Materials Project

After chemical space exploration, cross-check compositions against the MP convex hull
before running expensive DFT:

```
mp_search_materials(
    formula='NaCoO2',
    is_stable=True
)
```

Discard compositions that are far above the hull (energy_above_hull > 0.1 eV/atom)
unless the target is metastable phases.

### Output Format Routing

| Downstream tool | Recommended `output_format` |
|---|---|
| Another pymatgen tool | `'dict'` (default) |
| VASP / CP2K / Quantum ESPRESSO | `'poscar'` or `'cif'` |
| ASE database (`ase_store_result`) | `'ase'` |
| CIF archive / visualisation | `'cif'` |

---

## Common Patterns

### Isostructural Analogue Screen

```
# 1. Build rock-salt seed
seed = pymatgen_prototype_builder(spacegroup=225, species=['Li','O'], lattice_parameters=[4.33])

# 2. Swap Li site: Li → Na, K, Rb; O site: O → S, Se
variants = pymatgen_substitution_generator(
    input_structures=seed['structures'][0]['structure'],
    substitutions={'Li': ['Na', 'K', 'Rb'], 'O': ['S', 'Se', 'O']},
    n_structures=15
)

# 3. Filter by MP stability and store survivors
for s in variants['structures']:
    mp_results = mp_search_materials(formula=s['formula'])
    if mp_results['count'] > 0:
        ase_store_result(db_path='screen.db', atoms_dict=s['structure'],
                         key_value_pairs={'formula': s['formula'], 'campaign': 'rocksalt_screen'})
```

### Li → Na Battery Analogue

```
licoo2 = mp_get_material_properties('mp-24850')  # LiCoO2
struct_dict = licoo2['properties'][0]['structure']

exchanged = pymatgen_ion_exchange_generator(
    input_structures=struct_dict,
    replace_ion='Li',
    with_ions=['Na'],
    exchange_fraction=1.0,
    max_structures=5
)
```

### High-Entropy Oxide SQS

```
# Build a rocksalt with 5-component mixing on the cation sublattice
# Input: disordered structure with occupancies {Mg:0.2, Co:0.2, Ni:0.2, Cu:0.2, Zn:0.2}
sqs = pymatgen_sqs_generator(
    input_structures=disordered_cif,
    supercell_size=20,
    n_structures=5,
    n_mc_steps=500000,
    seed=7
)
# Best SQS is sqs['structures'][0] (sorted by sqs_error)
```

### Ground-State Ordering Search

```
# Li₀.₅CoO₂ starting from partially delithiated structure with site occupancies
ordered_candidates = pymatgen_enumeration_generator(
    input_structures=disordered_struct,
    supercell_size=2,
    n_structures=100,
    sort_by='ewald'
)
# Top 10 by Ewald energy are the most plausible ground-state orderings
top10 = ordered_candidates['structures'][:10]
```

### Defect-Engineered Cathode

```
# Start from a relaxed ordered LiMnO2 structure
defect_cells = pymatgen_defect_generator(
    input_structure=limno2_dict,
    vacancy_species=['Li'],
    substitution_species={'Mn': ['Fe', 'Ni', 'Co']},
    supercell_min_atoms=96
)

# Rattle each defect cell before DFT relaxation
for dc in defect_cells['structures']:
    perturbed = pymatgen_perturbation_generator(
        input_structures=dc,
        displacement_max=0.08,
        n_structures=3,
        seed=1
    )
    for p in perturbed['structures']:
        ase_store_result(db_path='defects.db', atoms_dict=p,
                         key_value_pairs={'defect_label': dc['metadata']['defect_label']})
```

### Phase 0: Li-Mn-P-O Battery Cathode Discovery (Elements-Only Entry)

```python
# User request: "Discover battery cathode materials in the Li-Mn-P-O system"
# Entry point: Elements only (no composition known)

# Step 1: Enumerate all charge-balanced Li-Mn-P-O compositions
result = composition_enumerator(
    elements=['Li', 'Mn', 'P', 'O'],
    oxidation_states={'Li': [1], 'Mn': [2, 3], 'P': [5], 'O': [-2]},
    max_formula_units=10,
    require_all_elements=True,  # Only quaternary Li-Mn-P-O
    sort_by='atoms',
    output_format='detailed'
)

print(f"Generated {result['count']} compositions")
# Output: ~12 compositions (LiMnPO4, Li3Mn(PO4)2, Mn3(PO4)2, etc.)

# Step 2: Filter by thermodynamic stability
stable_candidates = []
for comp in result['compositions']:
    stability = stability_analyzer(composition=comp['formula'])
    if stability['energy_above_hull'] < 0.1:  # Within 100 meV/atom
        stable_candidates.append({
            'formula': comp['formula'],
            'num_atoms': comp['num_atoms'],
            'energy_above_hull': stability['energy_above_hull']
        })
        
print(f"Found {len(stable_candidates)} stable/metastable compositions")

# Step 3: Check MP for existing structures
for candidate in stable_candidates:
    mp_result = mp_search_materials(formula=candidate['formula'])
    
    if mp_result['count'] > 0:
        # Structure exists in MP - use directly
        print(f"{candidate['formula']}: Found in MP (mp-{mp_result['materials'][0]['material_id']})")
        candidate['mp_structure'] = mp_result['materials'][0]['structure']
        candidate['spacegroup'] = mp_result['materials'][0]['spacegroup_number']
    else:
        # Novel composition - need to build from prototype
        print(f"{candidate['formula']}: Novel! Need to propose prototype.")
        candidate['mp_structure'] = None
        
# Step 4: For compositions without MP structures, try template-based
novel_compositions = [c for c in stable_candidates if c['mp_structure'] is None]

if len(novel_compositions) > 0:
    # Search for Fe-based analogues (LiFePO4 is well-known olivine cathode)
    fe_templates = mp_search_materials(
        elements=['Li', 'Fe', 'P', 'O'],
        num_elements=4,
        is_stable=True
    )
    
    if fe_templates['count'] > 0:
        # Found templates!
        print(f"Found {fe_templates['count']} Li-Fe-P-O templates")
        
        # Match stoichiometry patterns
        for novel in novel_compositions:
            # Look for matching stoichiometry (e.g., LiMnPO4 → LiFePO4)
            fe_formula = novel['formula'].replace('Mn', 'Fe')
            
            for template in fe_templates['materials']:
                if template['composition_reduced'] == fe_formula:
                    print(f"  {novel['formula']}: Use {fe_formula} as template (SG {template['spacegroup_number']})")
                    novel['template_spacegroup'] = template['spacegroup_number']
                    novel['template_structure'] = template['structure']
                    break

# Step 5: Feed to Phase 1 (structure generation)
for candidate in stable_candidates:
    if candidate.get('mp_structure'):
        # MP structure exists → go to Phase 2 (chemical exploration)
        print(f"Processing {candidate['formula']} with MP structure...")
        # GOTO Phase 2
        
    elif candidate.get('template_structure'):
        # Template exists → use substitution_generator
        print(f"Generating {candidate['formula']} from {candidate.get('template_formula')} template...")
        
        substituted = pymatgen_substitution_generator(
            input_structures=candidate['template_structure'],
            substitutions={'Fe': 'Mn'},  # Mn replaces Fe
            n_structures=1,
            enforce_charge_neutrality=True
        )
        candidate['structure'] = substituted['structures'][0]
        
    else:
        # No template → need to build from common prototype
        print(f"Building {candidate['formula']} from common prototype...")
        # User would specify prototype or use heuristics
        # GOTO Phase 1 (prototype_builder)

print("\nPhase 0 complete. Discovered compositions:")
for i, c in enumerate(stable_candidates[:5]):
    print(f"{i+1}. {c['formula']} (ΔH={c['energy_above_hull']:.3f} eV/atom, {c['num_atoms']} atoms)")
```

**Output example:**
```
Generated 12 compositions
Found 6 stable/metastable compositions
LiMnPO4: Found in MP (mp-19017)
Li3PO4: Found in MP (mp-13725)
Mn3(PO4)2: Found in MP (mp-7654)
Li2MnP2O7: Novel! Need to propose prototype.
...
Found 8 Li-Fe-P-O templates
  LiMnPO4: Use LiFePO4 as template (SG 62 - olivine)
  
Phase 0 complete. Discovered compositions:
1. LiMnPO4 (ΔH=0.000 eV/atom, 7 atoms)
2. Li3PO4 (ΔH=0.010 eV/atom, 8 atoms)
3. Mn3(PO4)2 (ΔH=0.025 eV/atom, 13 atoms)
...
```

---

## Candidate Generation Decision Algorithm

**Execute this algorithm to select the correct tool(s) for your candidate generation task.**

### STEP 0: Analyze User Request

**Step 0.1:** Identify starting point and entry phase
```
IF user provides ONLY elements (e.g., "Li-Mn-P-O", "Cu-Zn-Sn-S"):
    # Elements-only entry point
    GOTO STEP 0A (Phase 0: Composition Discovery)
    
ELSE IF user has existing structure (from MP, CIF, ASE database):
    # Structure exists
    SET starting_structure = existing_structure
    GOTO STEP 2 (Phase 2: Chemical Space Exploration)
    
ELSE IF user specifies composition + spacegroup:
    # Composition known, need to build structure
    GOTO STEP 1 (Phase 1: Seed Structure Generation)
    
ELSE IF user specifies composition only (e.g., "LiMnPO4"):
    # Try to find structure in MP first
    CALL mp_search_materials(formula=user_composition)
    IF mp_result['count'] > 0:
        SET starting_structure = mp_result['materials'][0]['structure']
        GOTO STEP 2 (Phase 2: Chemical Space Exploration)
    ELSE:
        # No MP structure, need to build from prototype
        REQUEST spacegroup/prototype from user OR use common prototype heuristics
        GOTO STEP 1 (Phase 1: Seed Structure Generation)
        
ELSE:
    REQUEST clarification from user
```

---

### STEP 0A: Phase 0 — Composition Discovery (CONDITIONAL)

**Condition:** Only execute if user provides elements without composition

**Step 0A.1:** Determine discovery strategy
```
IF user mentions known analogue (e.g., "like LiFePO4 but with Mn"):
    SET strategy = "template_based"
    SET analogue_composition = extract_analogue_from_request()
    GOTO Step 0A.2 (template-based discovery)
    
ELSE IF chemical system is well-studied (battery, perovskite, etc.):
    SET strategy = "hybrid"  # Templates + enumeration
    GOTO Step 0A.3 (hybrid approach)
    
ELSE:
    SET strategy = "enumeration"  # Exhaustive
    GOTO Step 0A.4 (enumeration-based discovery)
```

---

**Step 0A.2:** Template-based discovery
```
# Strategy: Find structural analogues in MP, extract patterns, substitute target elements

SET target_elements = user_specified_elements  # e.g., ['Li', 'Mn', 'P', 'O']
SET num_target_elements = len(target_elements)

# Find chemical analogues (same group, similar oxidation states)
SET analogue_elements = find_chemical_analogues(target_elements)
# Example: Li → Na, K; Mn → Fe, Co, Ni

# Search MP for analogue structures
FOR EACH analogue_set IN analogue_elements:
    CALL mp_search_materials(
        elements=analogue_set,
        num_elements=num_target_elements,
        is_stable=True,
        limit=50
    )
    
    IF mp_result['count'] > 0:
        # Found templates!
        SET template_structures = mp_result['materials']
        BREAK  # Use first successful analogue system

IF template_structures is empty:
    # No templates found, fall back to enumeration
    GOTO Step 0A.4

# Extract stoichiometric patterns from templates
SET patterns = {}
FOR EACH structure IN template_structures:
    SET formula = structure['composition_reduced']
    SET sg = structure['spacegroup_number']
    patterns[formula] = sg

# Generate target compositions matching patterns
SET target_compositions = []
FOR EACH pattern_formula IN patterns.keys():
    # Substitute target elements into pattern
    SET target_formula = substitute_elements(pattern_formula, analogue_elements, target_elements)
    target_compositions.append({
        'formula': target_formula,
        'template_spacegroup': patterns[pattern_formula],
        'template_formula': pattern_formula,
        'confidence': 'high'  # Based on MP template
    })

# Verify compositions are charge-balanced
SET valid_compositions = []
FOR EACH comp IN target_compositions:
    IF is_charge_balanced(comp['formula']):
        valid_compositions.append(comp)

SET discovered_compositions = valid_compositions
GOTO Step 0A.5 (filter and rank)
```

---

**Step 0A.3:** Hybrid approach (templates + enumeration)
```
# First try template-based (Step 0A.2)
EXECUTE Step 0A.2

IF len(discovered_compositions) < 5:
    # Insufficient templates, supplement with enumeration
    EXECUTE Step 0A.4 (enumeration)
    
    # Merge results, prioritizing template-based
    FOR EACH enum_comp IN enumeration_results:
        IF enum_comp NOT IN discovered_compositions:
            discovered_compositions.append({
                'formula': enum_comp,
                'confidence': 'medium'  # From enumeration, not template
            })

GOTO Step 0A.5 (filter and rank)
```

---

**Step 0A.4:** Enumeration-based discovery
```
# Strategy: Generate ALL charge-balanced compositions, filter by stability

SET elements = user_specified_elements

# Determine oxidation states
IF user_specified_oxidation_states:
    SET oxidation_states = user_specified_oxidation_states
ELSE:
    # Use common oxidation states from periodic table
    SET oxidation_states = get_common_oxidation_states(elements)
    # Example: {'Li': [1], 'Mn': [2, 3], 'P': [5], 'O': [-2]}

# Call composition_enumerator
CALL composition_enumerator(
    elements=elements,
    oxidation_states=oxidation_states,
    max_formula_units=6,  # Adjust based on system complexity
    max_atoms_per_formula=30,
    require_all_elements=True,  # Only return compositions with ALL elements
    allow_mixed_valence=True,  # Allow Pr³⁺/Pr⁴⁺ mixing
    sort_by='atoms',  # Simplest first
    output_format='detailed'
)

SET discovered_compositions = result['compositions']

# Add confidence metadata
FOR EACH comp IN discovered_compositions:
    comp['confidence'] = 'enumeration'  # Not template-based
    comp['template_spacegroup'] = None

GOTO Step 0A.5 (filter and rank)
```

---

**Step 0A.5:** Filter by stability and rank
```
# Filter out compositions far above convex hull
SET stable_compositions = []

FOR EACH comp IN discovered_compositions:
    # Check thermodynamic stability
    CALL stability_analyzer(composition=comp['formula'])
    
    IF stability_result['is_stable']:
        comp['energy_above_hull'] = 0.0
        comp['stability_tier'] = 'stable'
        stable_compositions.append(comp)
    ELSE IF stability_result['energy_above_hull'] < 0.1:
        comp['energy_above_hull'] = stability_result['energy_above_hull']
        comp['stability_tier'] = 'metastable'
        stable_compositions.append(comp)
    # Else: discard (too unstable)

# Rank by multiple criteria
SET ranking_score = []
FOR EACH comp IN stable_compositions:
    score = 0
    
    # Criterion 1: Stability (most important)
    IF comp['stability_tier'] == 'stable':
        score += 100
    ELSE:
        score += 50
    
    # Criterion 2: Confidence (template-based > enumeration)
    IF comp['confidence'] == 'high':  # From MP template
        score += 50
    ELSE IF comp['confidence'] == 'medium':
        score += 25
    
    # Criterion 3: Simplicity (fewer atoms preferred)
    score -= comp['num_atoms']  # Penalize complexity
    
    comp['ranking_score'] = score

# Sort by ranking score (highest first)
SORT stable_compositions BY ranking_score DESCENDING

# Present top candidates to user
SET top_candidates = stable_compositions[:10]  # Top 10

OUTPUT: "Phase 0 discovered {len(stable_compositions)} stable/metastable compositions:"
FOR i, comp IN ENUMERATE(top_candidates):
    OUTPUT: "{i+1}. {comp['formula']} (ΔH={comp['energy_above_hull']} eV/atom, {comp['num_atoms']} atoms, {comp['stability_tier']})"

SET target_compositions = top_candidates
GOTO STEP 1 (Phase 1: Build structures for these compositions)
```

---

### STEP 1: Seed Structure Generation (CONDITIONAL)

**Condition:** Only execute if no existing structure available

**Decision Logic:**
```
IF starting_structure exists:
    SKIP this step, GOTO STEP 2
ELSE:
    # Need to build structure from scratch
    CALL pymatgen_prototype_builder(
        spacegroup=user_specified_sg,
        species=user_specified_elements,
        lattice_parameters=user_specified_params
    )
    SET starting_structure = result.structures[0]
    GOTO STEP 2
```

**Common prototype reference:**
```
IF user mentions "perovskite":
    USE spacegroup=221
ELSE IF user mentions "rock-salt" or "NaCl-type":
    USE spacegroup=225
ELSE IF user mentions "spinel":
    USE spacegroup=227
ELSE IF user mentions "layered oxide" or "LiCoO2-type":
    USE spacegroup=166
ELSE IF user mentions "olivine" or "LiFePO4-type":
    USE spacegroup=62
ELSE IF user mentions "rutile":
    USE spacegroup=136
ELSE IF user mentions "wurtzite":
    USE spacegroup=186
ELSE:
    REQUEST spacegroup number from user
```

---

### STEP 2: Chemical Space Exploration (CONDITIONAL)

**Condition:** Execute if user wants to explore different compositions

**Decision Logic:**
```
IF user wants to keep exact composition:
    SKIP this step, GOTO STEP 3
ELSE IF user requests chemical substitutions or doping:
    GOTO Step 2.1 (determine substitution type)
```

**Step 2.1:** Determine substitution type
```
IF material is ionic AND charge balance is critical:
    # Examples: Battery materials, ionic conductors
    GOTO Step 2A (charge-neutral ion exchange)
ELSE IF exploratory screening OR charge balance not enforced:
    # Examples: Isostructural analogues, ML training sets
    GOTO Step 2B (substitution generator)
ELSE:
    # Default to charge-neutral for safety
    GOTO Step 2A
```

---

### STEP 2A: Charge-Neutral Ion Exchange

**When to use:**
- Material is ionic (oxides, sulfides, halides)
- Charge neutrality must be maintained
- Battery cathode analogues (Li → Na)
- Doping with different oxidation states

**Algorithm:**
```
CALL pymatgen_ion_exchange_generator(
    input_structures=starting_structure,
    replace_ion=user_specified_ion,
    with_ions=user_specified_replacements,
    exchange_fraction=1.0,  # Or user-specified
    allow_oxidation_state_change=False,  # Enforce charge neutrality
    max_structures=20
)

SET candidate_structures = result.structures
GOTO STEP 3
```

**Example decision:**
```
IF user says "Li → Na in LiCoO2":
    USE replace_ion='Li', with_ions=['Na']
IF user says "partial Mg doping on Li site":
    USE replace_ion='Li', with_ions={'Li': 0.7, 'Mg': 0.3}
```

---

### STEP 2B: Exploratory Substitution

**When to use:**
- Isostructural analogue screening
- Charge balance handled post-hoc
- Building diverse training sets
- Exploring many chemical variations

**Algorithm:**
```
CALL pymatgen_substitution_generator(
    input_structures=starting_structure,
    substitutions=user_specified_substitutions,
    n_structures=determine_n_structures(),
    max_attempts=calculate_max_attempts(),
    enforce_charge_neutrality=False
)

SET candidate_structures = result.structures
GOTO STEP 3
```

**Step 2B.1:** Calculate appropriate parameters
```
# Determine n_structures based on substitution mode
IF all substitutions have fraction=1.0:
    # Deterministic full swaps - only need 1 copy each
    SET n_structures = 1
ELSE:
    # Fractional doping - generate multiple variants
    SET n_structures = 10

# Ensure max_attempts is sufficient
SET num_combinations = calculate_substitution_combinations(substitutions)
SET max_attempts = n_structures * num_combinations * 1.2  # 20% buffer
```

---

### STEP 3: Disorder Resolution (CONDITIONAL)

**Condition:** Execute if structures have partial occupancies

**Step 3.1:** Check for disorder
```
IF any candidate_structure has fractional site occupancies:
    GOTO Step 3.2 (determine resolution method)
ELSE:
    # Fully ordered structures
    GOTO STEP 4
```

**Step 3.2:** Determine resolution method
```
IF need ALL possible orderings (ground-state search, cluster expansion):
    GOTO Step 3A (enumeration)
ELSE IF modeling disorder itself (solid solution, high-entropy):
    GOTO Step 3B (SQS generation)
ELSE IF unsure:
    # Default decision based on system complexity
    SET num_mixing_species = count(species with partial occupancy)
    IF num_mixing_species <= 2:
        GOTO Step 3A (enumeration tractable)
    ELSE:
        GOTO Step 3B (SQS more appropriate)
```

---

### STEP 3A: Complete Enumeration (Ground-State Search)

**When to use:**
- Need complete ordered-configuration space
- Searching for ground-state ordering
- Building cluster expansion training set
- System has ≤ 2 mixing species

**Algorithm:**
```
# Determine supercell_size based on system complexity
SET num_mixing_species = count_mixing_species(disordered_structures)

IF num_mixing_species == 1:
    SET supercell_size = 4  # Single species ordering (e.g., vacancies)
ELSE IF num_mixing_species == 2:
    SET supercell_size = 2  # Binary mixing (e.g., Li/vacancy)
ELSE IF num_mixing_species >= 3:
    SET supercell_size = 1  # Ternary+ mixing (combinatorial explosion)
ELSE:
    SET supercell_size = 2  # Default

CALL pymatgen_enumeration_generator(
    input_structures=disordered_structures,
    supercell_size=supercell_size,
    n_structures=100,  # Or user-specified
    sort_by='ewald',  # Lowest energy orderings first
    add_oxidation_states=True,
    refine_structure=True
)

SET ordered_structures = result.structures
GOTO STEP 4
```

---

### STEP 3B: SQS Generation (Disorder Modeling)

**When to use:**
- Modeling solid solutions (disorder is physical state)
- High-entropy materials (≥ 4 mixing species)
- Large systems where enumeration is intractable
- Random alloy approximation needed

**Algorithm:**
```
# Determine supercell size based on system
SET num_mixing_species = count_mixing_species(disordered_structures)

IF num_mixing_species <= 2:
    SET supercell_size = 12  # Binary
ELSE IF num_mixing_species == 3:
    SET supercell_size = 16  # Ternary
ELSE:
    SET supercell_size = 20  # High-entropy (4+ species)

# Adjust MC steps based on complexity
SET n_mc_steps = 50000 * num_mixing_species

CALL pymatgen_sqs_generator(
    input_structures=disordered_structures,
    supercell_size=supercell_size,
    n_structures=5,  # Multiple independent SQS candidates
    n_mc_steps=n_mc_steps,
    n_shells=4,
    seed=user_seed OR 42
)

SET ordered_structures = result.structures  # Best SQS structures
GOTO STEP 4
```

---

### STEP 4: Defect Generation (OPTIONAL BRANCH)

**Condition:** Only execute if user needs point defect supercells

**Decision Logic:**
```
IF user requests defects OR vacancies OR doping:
    GOTO Step 4.1 (defect generation)
ELSE:
    GOTO STEP 5
```

**Step 4.1:** Defect generation
```
# IMPORTANT: Start from single, ordered, defect-free host structure
SET host_structure = select_one_ordered_structure(candidate_structures)

# Determine defect types from user request
SET vacancy_species = extract_vacancy_species_from_request()
SET substitution_species = extract_substitution_species_from_request()
SET interstitial_species = extract_interstitial_species_from_request()

CALL pymatgen_defect_generator(
    input_structure=host_structure,  # Single structure only!
    vacancy_species=vacancy_species,
    substitution_species=substitution_species,
    interstitial_species=interstitial_species,
    charge_states=user_specified_charges OR default_charges,
    supercell_min_atoms=64,  # Adjust based on DFT setup
    inequivalent_only=True
)

SET defect_structures = result.structures
GOTO STEP 5
```

---

### STEP 5: Perturbation/Augmentation (OPTIONAL)

**Condition:** Execute if user needs:
- Symmetry breaking before DFT
- ML dataset augmentation
- Structural ensembles

**Decision Logic:**
```
IF user requests perturbation OR rattling OR strain OR augmentation:
    GOTO Step 5.1 (perturbation)
ELSE IF structures going to DFT relaxation:
    # Recommend subtle perturbation to avoid symmetry saddle points
    ASK user "Apply small perturbations to break symmetry? (Recommended for DFT)"
    IF yes:
        GOTO Step 5.1 with displacement_max=0.05
ELSE:
    GOTO STEP 6 (finalize)
```

**Step 5.1:** Apply perturbations
```
# Determine perturbation parameters based on use case
IF use_case == "DFT_relaxation":
    SET displacement_max = 0.05  # Subtle rattling
    SET strain_percent = None  # No strain
    SET n_structures = 1  # One perturbed copy per structure
ELSE IF use_case == "ML_augmentation":
    SET displacement_max = 0.15  # Moderate rattling
    SET strain_percent = [-2.0, 2.0]  # Random strain
    SET n_structures = 10  # Many perturbed copies
ELSE IF use_case == "defect_relaxation":
    SET displacement_max = 0.08  # Gentle rattling around defect
    SET strain_percent = None
    SET n_structures = 3
ELSE:
    # User-specified or defaults
    SET displacement_max = user_value OR 0.1
    SET strain_percent = user_value OR None
    SET n_structures = user_value OR 10

CALL pymatgen_perturbation_generator(
    input_structures=structures_to_perturb,
    displacement_max=displacement_max,
    strain_percent=strain_percent,
    n_structures=n_structures,
    seed=user_seed OR None
)

SET final_structures = result.structures
GOTO STEP 6
```

---

### STEP 6: Storage and Validation

**Step 6.1:** Store in ASE database
```
# Connect to or create database
CALL ase_connect_or_create_db(
    db_path=user_specified_path OR "candidates.db"
)

# Store each structure
FOR each structure in final_structures:
    # IMPORTANT: Ensure output_format='ase' was used in generation
    IF structure format is not ASE:
        CONVERT to ASE format
    
    # Prepare metadata (avoid ASE reserved keys!)
    SET metadata = {
        'generator': tool_used,
        'compound': structure.formula,  # NOT 'formula'!
        'campaign': user_campaign_name,
        'source_structure': parent_structure_id,
        'creation_date': current_date
    }
    
    CALL ase_store_result(
        db_path=db_path,
        atoms_dict=structure,
        key_value_pairs=metadata
    )
```

**Step 6.2:** Optional MP stability check
```
IF user wants stability filtering:
    FOR each structure in final_structures:
        CALL mp_search_materials(
            formula=structure.formula,
            is_stable=True
        )
        
        IF result.count > 0:
            # Composition exists in MP and is stable
            FLAG structure.likely_stable = True
        ELSE:
            # May be unstable or not in MP
            FLAG structure.requires_stability_check = True
```

**Step 6.3:** Generate summary report
```
RETURN {
    "total_candidates_generated": count(final_structures),
    "generation_path": [list of steps executed],
    "database_location": db_path,
    "metadata": {
        "starting_structure": starting_structure_info,
        "chemical_substitutions": substitutions_applied,
        "disorder_resolution": method_used,
        "defects_generated": defect_count,
        "perturbations_applied": perturbation_params
    },
    "next_steps": [
        "Query database: ase_query_db(...)",
        "Screen with MP: mp_search_materials(...)",
        "Pass to candidate-screener for property enrichment"
    ]
}
```

---

### QUICK DECISION FLOWCHART FOR LLMs

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

## Pitfalls and Gotchas

**`enumeration_generator` hangs or never returns**
Cause: `supercell_size` too large for the number of mixing species. Combinatorial explosion.
Fix: reduce `supercell_size` to 1–2, or switch to `sqs_generator` for multicomponent systems.

**Never bypass MCP tools by calling pymatgen directly in scripts**
Cause: Writing script code that calls pymatgen transformation classes (e.g.
`EnumerateStructureTransformation`) directly risks passing incorrect kwargs as the internal
API evolves (e.g. `check_ordered_structures` vs `check_ordered_symmetry`), and it loses
the error handling and platform abstraction that the MCP tools provide.
Fix: Always use the designated MCP tool (`pymatgen_enumeration_generator`,
`pymatgen_substitution_generator`, etc.). Only drop to direct pymatgen code when an MCP
tool explicitly cannot accomplish the task (e.g. manual supercell construction).

**`substitution_generator` silently truncates output when many options are given**
Cause: `max_attempts` (default 50) is a hard cap on total output. With a list of N
substitution options and n_structures=k, the tool attempts N×k structures but stops at
`max_attempts`, silently dropping the remainder with no error.
Symptom: `count` in the result is less than N×k; some substitution options are missing.
Fix: Always set `max_attempts = n_structures × len(substitution_options)` explicitly.
Also set `n_structures=1` for deterministic full swaps (fraction=1.0) — higher values
just add identical duplicates and inflate the attempt count unnecessarily.

**`substitution_generator` fractional doping silently becomes a full swap on single-site cells**
Cause: `fraction=0.5` on a sublattice with only one site cannot produce a partial occupancy
(you cannot remove half an atom). The tool falls back to replacing the whole site, returning
the same result as `fraction=1.0` with no warning.
Symptom: The output formula shows a complete element swap even though `fraction < 1.0` was
requested; the output is an ordered structure, not a disordered one.
Fix: Ensure the input cell has **≥ 2 sites of the target species** before using fractional
substitution. For a single-site primitive cell (e.g. a 5-atom perovskite with one B-site),
either (a) build a supercell first so multiple target sites exist, or (b) manually construct
the disordered structure dict with explicit partial occupancies
(`{"element": "Fe", "occu": 0.5}, {"element": "Co", "occu": 0.5}` on the same site)
and pass it directly to `sqs_generator` or `enumeration_generator`.

**`ion_exchange_generator` returns zero structures**
Cause: No charge-neutral solution exists at the requested stoichiometry.
Fix: Try different `exchange_fraction` values, use `allow_oxidation_state_change=True` to debug,
or verify oxidation state assumptions with `mp_get_material_properties`.

**`defect_generator` creates excessively large supercells**
Cause: `supercell_min_atoms` is high (default 64) relative to a primitive cell with few atoms.
Fix: Lower `supercell_min_atoms` (e.g. 32 for quick tests), or supply an explicit `supercell_matrix`.

**`prototype_builder` raises proximity error**
Cause: The chosen lattice parameters place atoms too close together.
Fix: Check against experimental / MP values. Temporarily set `validate_proximity=False` to
retrieve the structure and inspect it before adjusting parameters.

**Duplicate structures in candidate pool**
Cause: Multiple generation paths converge on the same composition and topology.
Fix: Query `ase_query_db` and use `unique_key` in `ase_store_result` to deduplicate on
formula + source_structure hash before running DFT.

**`sqs_generator` produces poor SQS quality (high `sqs_error`)**
Cause: Too few MC steps or too small a supercell for the target composition.
Fix: Increase `n_mc_steps` (try 200 000–500 000) and `supercell_size` (16–24), or install
ATAT and set `use_mcsqs=True`.

---

## Quick Reference

| Task | Tool | Critical parameters |
|------|------|---------------------|
| Build from spacegroup | `prototype_builder` | `spacegroup`, `species`, `lattice_parameters` |
| Isostructural analogues | `substitution_generator` | `substitutions`, `n_structures` |
| Charge-neutral ion swap | `ion_exchange_generator` | `replace_ion`, `with_ions`, `exchange_fraction` |
| Enumerate all orderings | `enumeration_generator` | `supercell_size ≤ 2`, `sort_by='ewald'` |
| Best quasirandom cell | `sqs_generator` | `supercell_size`, `n_mc_steps`, `n_structures` |
| Point defect supercells | `defect_generator` | `vacancy/substitution/interstitial_species`, `supercell_min_atoms` |
| Rattle / strain ensemble | `perturbation_generator` | `displacement_max`, `strain_percent`, `n_structures` |
