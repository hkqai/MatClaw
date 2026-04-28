# Common Pitfalls and Gotchas

Error handling, debugging, and common mistakes in candidate generation workflows.

## Critical Rule: Always Use MCP Tools

**NEVER bypass MCP tools by calling pymatgen directly OR writing custom generators**

**Problem:** Writing script code that either:
1. Calls pymatgen transformation classes directly (e.g. `EnumerateStructureTransformation`)
2. Generates formula strings without structure generation

**Risk:**
- Direct pymatgen calls risk incorrect kwargs as internal API evolves
- Lose error handling and platform abstraction that MCP tools provide
- Custom formula generators produce scientifically invalid outputs with no structures

**Solution:** Always use designated MCP tool (`composition_enumerator`, `pymatgen_enumeration_generator`, etc.)

**Exception:** Only drop to direct pymatgen when MCP tool cannot accomplish task AND you document why.

---

## Tool-Specific Pitfalls

### `substitution_generator` Issues

#### Problem: Silent Output Truncation

**Symptom:** `count` in result is less than expected; some substitution options missing

**Cause:** `max_attempts` (default 50) is a hard cap. With N substitution options and n_structures=k, tool attempts N×k structures but stops at `max_attempts`.

**Solution:**
```python
# Calculate required max_attempts
num_combinations = len(substitution_options)
required_max_attempts = n_structures * num_combinations

# Set explicitly
pymatgen_substitution_generator(
    substitutions=options,
    n_structures=n_structures,
    max_attempts=required_max_attempts * 1.2  # 20% buffer
)
```

**Example:**
```python
# ❌ WRONG: Will silently truncate
pymatgen_substitution_generator(
    substitutions={'B': ['Ti', 'Zr', 'Hf', 'Sn', 'Ge', 'Pb', 'Ce', 'Th']},  # 8 options
    n_structures=1
    # max_attempts defaults to 50, but only needs 8
)

# ✅ CORRECT
pymatgen_substitution_generator(
    substitutions={'B': ['Ti', 'Zr', 'Hf', 'Sn', 'Ge', 'Pb', 'Ce', 'Th']},
    n_structures=1,
    max_attempts=10  # 8 × 1 × 1.25 = 10
)
```

#### Problem: Creates Ordered Structures, Not Disorder

**Symptom:** Output has integer occupancy (occu=1) on all sites; formula shows ordered composition (e.g., LiNi₄MnO₁₀) not fractional (e.g., Li₃[Ni₂.₄Mn₀.₆]O₆)

**Cause:** `substitution_generator` is for ORDERED enumeration, not creating statistical disorder. Using `fraction=0.5` fully replaces 50% of specific sites (integer occupancy), not 50% partial occupancy on each site.

**Solution:** Use `pymatgen_disorder_generator` for fractional occupancy

```python
# ❌ WRONG: Creates ordered structures with specific sites replaced
substitution_generator(
    substitutions={'Ni': {'replace_with': 'Mn', 'fraction': 0.2}}
)
# Output: 5 structures, each with 1 different Ni site fully replaced by Mn

# ✅ CORRECT: Creates fractional occupancy on ALL Ni sites
disorder_generator(
    site_substitutions={'Ni': {'Ni': 0.8, 'Mn': 0.2}}
)
# Output: 1 structure where every Ni site has 80% Ni + 20% Mn occupancy
```

#### Problem: Unnecessary Duplicates

**Symptom:** `n_structures > 1` for deterministic full swaps produces identical structures

**Cause:** When `fraction=1.0` (full replacement), substitution is deterministic. Higher `n_structures` just duplicates.

**Solution:** Set `n_structures=1` for deterministic full swaps

```python
# ❌ INEFFICIENT: n_structures=5 produces 5 identical copies
pymatgen_substitution_generator(
    substitutions={'Li': 'Na'},  # fraction=1.0 implicit
    n_structures=5  # Wasted computation
)

# ✅ EFFICIENT
pymatgen_substitution_generator(
    substitutions={'Li': 'Na'},
    n_structures=1  # Only need one for deterministic swap
)
```

---

### `enumeration_generator` Issues

#### Problem: Hangs or Never Returns

**Symptom:** Tool runs indefinitely without returning

**Cause:** `supercell_size` too large for number of mixing species. Combinatorial explosion.

**Solution:** Keep `supercell_size ≤ 2` for ternary+ systems; switch to `sqs_generator` for high-entropy

```python
# ❌ WRONG: Will hang with ternary disorder
pymatgen_enumeration_generator(
    input_structures=disordered_structure,  # Has 3 mixing species
    supercell_size=4  # Combinatorial explosion!
)

# ✅ CORRECT
pymatgen_enumeration_generator(
    input_structures=disordered_structure,
    supercell_size=1  # Or 2 maximum for ternary
)

# OR switch to SQS for high-entropy systems
pymatgen_sqs_generator(
    input_structures=disordered_structure,
    supercell_size=16
)
```

**Supercell size guidelines:**
- 1 mixing species: supercell_size = 4
- 2 mixing species: supercell_size = 2
- 3+ mixing species: supercell_size = 1 OR use SQS

---

### `ion_exchange_generator` Issues

#### Problem: Returns Zero Structures

**Symptom:** `count: 0` in result, no structures generated

**Cause:** No charge-neutral solution exists at requested stoichiometry

**Solution techniques:**

1. **Try different exchange fractions:**
```python
# ❌ May fail
pymatgen_ion_exchange_generator(
    replace_ion='Li',
    with_ions=['Mg'],  # Li⁺ → Mg²⁺ requires stoichiometry change
    exchange_fraction=1.0  # May not have charge-neutral solution
)

# ✅ Try fractional exchange
pymatgen_ion_exchange_generator(
    replace_ion='Li',
    with_ions=['Mg'],
    exchange_fraction=0.5  # Partial exchange more flexible
)
```

2. **Debug with `allow_oxidation_state_change=True`:**
```python
# Relaxes charge neutrality temporarily to see what's happening
pymatgen_ion_exchange_generator(
    replace_ion='Li',
    with_ions=['Mg'],
    allow_oxidation_state_change=True  # For debugging only
)
```

3. **Verify oxidation states:**
```python
# Check oxidation states in input structure
mp_result = mp_get_material_properties(material_ids=['mp-xxx'])
# Verify Li oxidation state is correct
```

---

### `defect_generator` Issues

#### Problem: Excessively Large Supercells

**Symptom:** Defect supercells have >200 atoms, DFT becomes intractable

**Cause:** `supercell_min_atoms` (default 64) is high relative to small primitive cell

**Solution:** Lower `supercell_min_atoms` or provide explicit supercell matrix

```python
# ❌ May create huge supercell
pymatgen_defect_generator(
    input_structure=small_primitive_cell,  # 4 atoms
    vacancy_species=['Li'],
    # supercell_min_atoms defaults to 64 → 16× supercell!
)

# ✅ Control supercell size explicitly
pymatgen_defect_generator(
    input_structure=small_primitive_cell,
    vacancy_species=['Li'],
    supercell_min_atoms=32  # Smaller supercell for testing
)
```

---

### `prototype_builder` Issues

#### Problem: Proximity Error

**Symptom:** `ValueError: Sites less than 0.01 Å apart`

**Cause:** Chosen lattice parameters place atoms too close

**Solution:** 
1. Check against experimental/MP values
2. Temporarily disable validation to inspect

```python
# ❌ Wrong lattice parameters
pymatgen_prototype_builder(
    spacegroup=225,
    species=['Li', 'O'],
    lattice_parameters=[2.0]  # Too small!
)

# ✅ Check MP for correct parameters first
mp_result = mp_search_materials(formula='Li2O')
correct_lattice = mp_result['materials'][0]['lattice']['a']

pymatgen_prototype_builder(
    spacegroup=225,
    species=['Li', 'O'],
    lattice_parameters=[correct_lattice]
)
```

---

### `sqs_generator` Issues

#### Problem: Poor SQS Quality (High sqs_error)

**Symptom:** `sqs_error > 0.1`, pair correlations don't match random alloy well

**Cause:** Too few MC steps or too small supercell

**Solution:** Increase `n_mc_steps` and `supercell_size`

```python
# ❌ Poor quality SQS
pymatgen_sqs_generator(
    input_structures=disordered_structure,
    supercell_size=8,
    n_mc_steps=10000  # Too few for convergence
)

# ✅ High quality SQS
pymatgen_sqs_generator(
    input_structures=disordered_structure,
    supercell_size=16,  # Larger cell
    n_mc_steps=200000,  # More MC steps
    use_mcsqs=True  # Use ATAT if available
)
```

**Quality guidelines:**
- Binary alloys: 50,000–100,000 MC steps
- Ternary alloys: 100,000–200,000 MC steps
- High-entropy (4+ species): 200,000–500,000 MC steps

---

## ASE Database Issues

### Problem: Missing Required Keys Error

**Symptom:** `"atoms_dict missing required keys: ['numbers']"`

**Cause:** Using wrong `output_format` — `ase_store_result` requires ASE-native keys

**Solution:** Always set `output_format='ase'` when feeding to ASE database

```python
# ❌ WRONG: output_format='dict' produces pymatgen dict
result = pymatgen_substitution_generator(
    input_structures=structure,
    substitutions={'Li': 'Na'},
    output_format='dict'  # Default, but wrong for ASE
)

ase_store_result(
    db_path='candidates.db',
    atoms_dict=result['structures'][0]['structure']  # FAILS!
)

# ✅ CORRECT
result = pymatgen_substitution_generator(
    input_structures=structure,
    substitutions={'Li': 'Na'},
    output_format='ase'  # ASE-compatible format
)

ase_store_result(
    db_path='candidates.db',
    atoms_dict=result['structures'][0]['structure']  # Works!
)
```

### Problem: Reserved Key Name Error

**Symptom:** `ValueError: Bad key` when calling `ase_store_result`

**Cause:** Using ASE reserved column names in `key_value_pairs`

**Reserved names (NEVER use):**
- `id`, `unique_id`, `ctime`, `mtime`, `user`
- `calculator`, `energy`, `forces`, `stress`, `magmoms`, `charges`
- `cell`, `pbc`, `natoms`, `formula`, `mass`, `volume`, `spacegroup`

**Solution:** Use unambiguous alternatives

```python
# ❌ WRONG: Uses reserved names
ase_store_result(
    db_path='candidates.db',
    atoms_dict=structure,
    key_value_pairs={
        'formula': 'LiCoO2',  # RESERVED!
        'spacegroup': 166,     # RESERVED!
        'unique_id': 'LCO_001' # RESERVED!
    }
)

# ✅ CORRECT: Use alternative names
ase_store_result(
    db_path='candidates.db',
    atoms_dict=structure,
    key_value_pairs={
        'compound': 'LiCoO2',      # Not 'formula'
        'sg_num': 166,              # Not 'spacegroup'
        'candidate_id': 'LCO_001'   # Not 'unique_id'
    }
)
```

---

## Duplicate Structures

### Problem: Same Structure Generated Multiple Times

**Symptom:** ASE database contains duplicate structures with different IDs

**Cause:** Multiple generation paths converge on same composition/topology

**Solution:** Query before generating; use hash-based deduplication

```python
# Before generating new structures
existing = ase_query_db(
    db_path='candidates.db',
    property_filters={'compound': target_formula}
)

if existing['count'] > 0:
    print(f"{target_formula} already exists (ID: {existing['results'][0]['id']})")
    # Skip generation
else:
    # Generate new structure
    pass
```

**Hash-based deduplication:**
```python
import hashlib

def structure_hash(atoms_dict):
    """Create hash from composition + cell parameters"""
    formula = atoms_dict.get('formula', '')
    cell = str(atoms_dict.get('cell', []))
    return hashlib.md5((formula + cell).encode()).hexdigest()

# Store with hash
structure_id = structure_hash(structure)
ase_store_result(
    db_path='candidates.db',
    atoms_dict=structure,
    key_value_pairs={'structure_hash': structure_id}
)
```

---

## Debugging Checklist

When generation fails or produces unexpected results:

1. **Check input structure validity:**
   - Is composition charge-balanced?
   - Are lattice parameters reasonable?
   - Does structure have expected symmetry?

2. **Verify tool parameters:**
   - Is `output_format` correct for downstream tool?
   - Are `max_attempts` and `n_structures` consistent?
   - Is `supercell_size` appropriate for system complexity?

3. **Check for silent failures:**
   - Is `count` in result less than expected? (truncation)
   - Are warning messages in tool output? (read them!)
   - Are structures too similar? (variations not working)

4. **Validate chemical logic:**
   - Does charge neutrality hold after substitution?
   - Are oxidation states physically reasonable?
   - Is disorder configuration chemically plausible?

5. **Test with simplified parameters:**
   - Reduce `n_structures` to 1 for faster debugging
   - Use smaller `supercell_size` for enumeration
   - Set `limit=5` for MP queries during testing

---

## Error Message Reference

| Error Message | Likely Cause | Solution |
|---------------|--------------|----------|
| "atoms_dict missing required keys" | Wrong output_format | Set `output_format='ase'` |
| "ValueError: Bad key" | ASE reserved name | Use alternative key names |
| "Sites less than 0.01 Å apart" | Bad lattice parameters | Check against MP/experimental values |
| "No charge-neutral solution" | Impossible stoichiometry | Adjust exchange_fraction or ion selection |
| Tool hangs indefinitely | Combinatorial explosion | Reduce supercell_size or switch to SQS |
| `count: 0` in substitution result | max_attempts too low | Calculate and set explicitly |
| High `sqs_error` | Poor SQS convergence | Increase n_mc_steps and supercell_size |
