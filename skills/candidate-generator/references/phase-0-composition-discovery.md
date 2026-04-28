# Phase 0: Composition Discovery

Detailed guide for entering the candidate generation pipeline with only elements (no composition known).

## When to Use Phase 0

**Use Phase 0 when:**
- You only know which elements to explore (e.g., "Li-Mn-P-O for battery cathodes")
- You don't know which compositions exist or are stable
- You want to discover new materials in a chemical system

**Skip Phase 0 if:**
- You already have a target composition → go to Phase 1
- You have an existing structure → go to Phase 2

---

## Strategy 1: Exhaustive Enumeration

**Best for:** Systematic exploration, no known analogues, exploratory discovery

**When to use:** 
- Truly novel systems
- No known analogues
- Want complete composition space

**Workflow:**

```python
# Step 1: Generate ALL charge-balanced compositions
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
    require_all_elements=True,  # Only quaternary Li-Mn-P-O
    sort_by='atoms',  # Simplest compositions first
    output_format='detailed'
)

# Result: ~12 compositions (LiMnPO₄, Li₃Mn(PO₄)₂, Mn₃(PO₄)₂, etc.)
compositions = result['compositions']

# Step 2: Filter by thermodynamic stability
stable_compositions = []
for comp in compositions:
    stability = stability_analyzer(input_structure=comp['formula'])
    
    if stability['is_stable'] or stability['energy_above_hull'] < 0.1:
        stable_compositions.append({
            'formula': comp['formula'],
            'num_atoms': comp['num_atoms'],
            'energy_above_hull': stability.get('energy_above_hull', 0.0)
        })

# Step 3: For each stable composition, check MP or build from prototype
```

**Adjusting parameters:**
- Increase `max_formula_units` for complex phases (spinels need 8-14 formula units)
- Decrease `anion_cation_ratio_max` for metal-rich compounds
- Set `require_all_elements=False` to include binaries/ternaries alongside quaternaries

---

## Strategy 2: Template-Based Discovery

**Best for:** Systems with known structural analogues

**When to use:**
- Known analogues exist (e.g., LiFePO₄ for Li-Mn-P-O)
- Well-studied chemical families (olivines, perovskites)
- Want to leverage existing structural knowledge

**Workflow:**

```python
# Step 1: Search for analogues with similar chemistry
# Try Fe instead of Mn (LiFePO₄ is well-known)
fe_templates = mp_search_materials(
    elements=['Li', 'Fe', 'P', 'O'],
    num_elements=4,
    is_stable=True,
    limit=50
)

if fe_templates['count'] == 0:
    # Try Na instead of Li
    na_templates = mp_search_materials(
        elements=['Na', 'Mn', 'P', 'O'],
        num_elements=4,
        is_stable=True
    )

# Step 2: Extract stoichiometric patterns
patterns = {}
for mat in fe_templates['materials']:
    formula = mat['composition_reduced']
    patterns[formula] = {
        'spacegroup': mat['spacegroup_number'],
        'mp_id': mat['material_id']
    }

print(f"Found patterns: {list(patterns.keys())}")
# Example: ['LiFePO4', 'Li3PO4', 'Fe3(PO4)2']

# Step 3: Use patterns to guide target compositions
if 'LiFePO4' in patterns:
    # Olivine pattern exists (AMPO₄)
    target_compositions = [{
        'formula': 'LiMnPO4',
        'template': 'LiFePO4',
        'spacegroup': patterns['LiFePO4']['spacegroup'],
        'confidence': 'high'
    }]

# Step 4: For each target, generate structure via substitution
for target in target_compositions:
    template_structure = mp_get_material_properties(
        material_ids=[patterns[target['template']]['mp_id']],
        properties=['structure']
    )
    
    # Use substitution_generator to swap Fe → Mn
    substituted = pymatgen_substitution_generator(
        input_structures=template_structure['properties'][0]['structure'],
        substitutions={'Fe': 'Mn'},
        n_structures=1,
        enforce_charge_neutrality=True
    )
```

**When no direct templates exist:**
1. Substitute one element at a time
2. Search broader family (alkali, transition metal)
3. Fall back to Strategy 1 (enumeration)

---

## Strategy 3: ICSD Substitution Patterns

**Best for:** Data-driven discovery from known materials

**When to use:**
- Starting from a known material
- Want statistically likely substitutions
- Leveraging database patterns

**Workflow:**

```python
# Starting from known composition
substitutions = pymatgen_substitution_predictor(
    composition='La2WO6',
    to_this_composition=False,  # What can La₂WO₆ become?
    threshold=0.01,
    group_by_probability=True
)

# Extract high-confidence suggestions
high_prob = substitutions['suggestions']['high']
target_formulas = [s['formula'] for s in high_prob]

# Check which ones exist in MP vs are novel
for formula in target_formulas:
    mp_result = mp_search_materials(formula=formula)
    
    if mp_result['count'] > 0:
        print(f"{formula}: exists in MP (mp-{mp_result['materials'][0]['material_id']})")
    else:
        print(f"{formula}: novel composition candidate!")
```

**Limitation:** Substitution predictor is conservative (only observed patterns). For truly novel compositions, use Strategy 1.

---

## Complete Example: Li-Mn-P-O Discovery

```python
# User request: "Discover battery cathode materials in Li-Mn-P-O system"

# Step 1: Enumerate all charge-balanced compositions
result = composition_enumerator(
    elements=['Li', 'Mn', 'P', 'O'],
    oxidation_states={'Li': [1], 'Mn': [2, 3], 'P': [5], 'O': [-2]},
    max_formula_units=10,
    require_all_elements=True,
    sort_by='atoms',
    output_format='detailed'
)

print(f"Generated {result['count']} compositions")
# Output: ~12 compositions

# Step 2: Filter by stability
stable_candidates = []
for comp in result['compositions']:
    stability = stability_analyzer(input_structure=comp['formula'])
    
    if stability['energy_above_hull'] < 0.1:
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
        candidate['mp_structure'] = mp_result['materials'][0]['structure']
        candidate['spacegroup'] = mp_result['materials'][0]['spacegroup_number']
    else:
        candidate['mp_structure'] = None

# Step 4: For novel compositions, find templates
novel_compositions = [c for c in stable_candidates if c['mp_structure'] is None]

if len(novel_compositions) > 0:
    # Search for Fe-based analogues (LiFePO₄ is well-known olivine)
    fe_templates = mp_search_materials(
        elements=['Li', 'Fe', 'P', 'O'],
        num_elements=4,
        is_stable=True
    )
    
    if fe_templates['count'] > 0:
        for novel in novel_compositions:
            # Match stoichiometry (e.g., LiMnPO₄ → LiFePO₄)
            fe_formula = novel['formula'].replace('Mn', 'Fe')
            
            for template in fe_templates['materials']:
                if template['composition_reduced'] == fe_formula:
                    novel['template_spacegroup'] = template['spacegroup_number']
                    novel['template_structure'] = template['structure']
                    break

# Step 5: Generate structures
for candidate in stable_candidates:
    if candidate.get('mp_structure'):
        # MP structure exists → go to Phase 2
        print(f"Using MP structure for {candidate['formula']}")
        
    elif candidate.get('template_structure'):
        # Template exists → use substitution_generator
        substituted = pymatgen_substitution_generator(
            input_structures=candidate['template_structure'],
            substitutions={'Fe': 'Mn'},
            n_structures=1,
            enforce_charge_neutrality=True
        )
        candidate['structure'] = substituted['structures'][0]
        
    else:
        # Build from prototype
        print(f"Need prototype for {candidate['formula']}")

print("\nPhase 0 complete. Discovered compositions:")
for i, c in enumerate(stable_candidates[:5]):
    print(f"{i+1}. {c['formula']} (ΔH={c.get('energy_above_hull', 0):.3f} eV/atom)")
```

**Expected output:**
```
Generated 12 compositions
Found 6 stable/metastable compositions
Phase 0 complete. Discovered compositions:
1. LiMnPO4 (ΔH=0.000 eV/atom)
2. Li3PO4 (ΔH=0.010 eV/atom)
3. Mn3(PO4)2 (ΔH=0.025 eV/atom)
```

---

## Filtering and Ranking

After composition discovery, always:

1. **Filter by stability** (ΔH < 0.1 eV/atom for metastable screening)
2. **Check MP for existing structures** (avoid reinventing the wheel)
3. **Rank by multiple criteria:**
   - Stability (most important)
   - Simplicity (fewer atoms preferred for initial screening)
   - Confidence (template-based > enumeration)

**Ranking algorithm:**

```python
for comp in discovered_compositions:
    score = 0
    
    # Stability (most important)
    if comp['is_stable']:
        score += 100
    elif comp['energy_above_hull'] < 0.05:
        score += 75
    elif comp['energy_above_hull'] < 0.1:
        score += 50
    
    # Confidence source
    if comp.get('template_spacegroup'):
        score += 50  # Template-based (high confidence)
    else:
        score += 25  # Enumeration-based
    
    # Simplicity (penalize complexity)
    score -= comp['num_atoms']
    
    comp['ranking_score'] = score

# Sort by ranking score
discovered_compositions.sort(key=lambda x: x['ranking_score'], reverse=True)
```

---

## Next Steps After Phase 0

**For each discovered composition:**

1. **MP structure exists:**
   - Use structure directly
   - GOTO Phase 2 (chemical exploration) if branching to variants
   - GOTO Phase 3 (disorder resolution) if exploring ordering

2. **Template structure exists:**
   - Use `substitution_generator` to adapt template
   - Store in ASE database
   - GOTO Phase 2 for further exploration

3. **No structure (novel composition):**
   - Identify prototype family (perovskite, spinel, etc.)
   - Use `prototype_builder` with appropriate spacegroup
   - GOTO Phase 2 for validation and variants
