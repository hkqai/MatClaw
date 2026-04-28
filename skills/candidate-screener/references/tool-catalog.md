# Tool Catalog: Complete Specifications

Comprehensive documentation for all tools used in candidate screening. For a quick overview, see the main SKILL.md Quick Tool Reference section.

## Phase 1: Validation & Analysis Tools

### 1. `structure_validator` — Structural Integrity Check

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

### 2. `composition_analyzer` — Chemical Composition Analysis

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

### 3. `stability_analyzer` — Thermodynamic Stability Assessment

Predicts whether a composition is likely thermodynamically stable using Materials Project phase diagram.

**Key parameters:**
- `input_structure`: pymatgen Structure dict/string, or just composition string (e.g., "LiFePO4")
- `hull_tolerance`: eV/atom above convex hull to consider "metastable" (default 0.1)

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

### 4. `structure_analyzer` — Detailed Structural Characterization

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

### 5. `structure_fingerprinter` — Similarity & Duplicate Detection

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

## Phase 2: Property Retrieval Tools

### Materials Project Tools

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

### ASE Database Tools

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

#### 10. `ase_store_result` — Cache Results in Database

Store computed/predicted properties in ASE database for future reuse.

**Key parameters:**
- `db_path`: path to ASE database
- `atoms_dict`: serialized ASE Atoms object (dict with 'numbers', 'positions', 'cell' keys)
- `results`: (optional) calculator results dict with energy, forces, stress, etc.
- `key_value_pairs`: (optional) metadata dict for campaign_id, method, formula, properties, etc.
- `unique_key`: (optional) unique identifier to avoid duplicates
- `data`: (optional) additional arbitrary data

**Returns:**
```python
{
  "success": True,
  "row_id": 143,
  "db_path": "/path/to/screening_run_2024.db",
  "formula": "LiFePO4",
  "updated": False
}
```

**Call after:** Every property retrieval/prediction to build cache.

---

### MatGL Tools (Direct ML Predictions)

#### 11. `matgl_relax_structure` — ML-Based Structure Optimization

Relax crystal structure using ML potentials from MatGL (TensorNet models, PYG backend).

**⚠️ MANDATORY:** Must be called before ALL ML predictions (MatGL and matcalc).

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

#### 12. `matgl_predict_eform` — Formation Energy Prediction

Predict formation energy using M3GNet/MEGNet models (DGL backend). **PRIMARY TOOL for formation energy screening.**

**⚠️ PREREQUISITE:** Structure must be relaxed with `matgl_relax_structure`.

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

**Speed:** ~0.5-1s per structure (fast screening)

---

#### 13. `matgl_predict_bandgap` — Band Gap Prediction

Predict electronic band gap using MEGNet model (DGL backend). **ONLY TOOL for band gap prediction.**

**⚠️ PREREQUISITE:** Structure must be relaxed with `matgl_relax_structure`.

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
  "interpretation": "Narrow gap semiconductor (IR-sensitive)"
}
```

**Material classification:**
- < 0.1 eV: Metal/Conductor
- 0.1-1.0 eV: Narrow gap semiconductor
- 1.0-2.0 eV: Semiconductor (visible light)
- 2.0-3.0 eV: Wide gap semiconductor
- > 3.0 eV: Very wide gap/Insulator

**Speed:** ~0.5-1s per structure (fast screening)

---

### matcalc Tools (Structure-Based Calculations)

All matcalc tools require relaxed structures (`matgl_relax_structure` first).

#### 14. `matcalc_calc_elasticity` — Mechanical Properties

Calculate full elastic tensor, bulk/shear/Young's modulus, Poisson's ratio.

**Key parameters:**
- `input_structure`: pymatgen Structure dict or CIF/POSCAR string
- `calculator`: ML potential (default `"TensorNet-MatPES-PBE-v2025.1-PES"`)
- `relax_structure`: relax before calculation (default `False`, already relaxed)
- `relax_deformed_structures`: relax atoms in strained structures (default `True`)
- `fmax`: force tolerance (default 0.1 eV/Å)
- `norm_strains`: strain magnitudes for fitting (default 0.01)

**Returns:**
```python
{
  "success": True,
  "formula": "LiFePO4",
  "elastic_tensor": [[...], ...],  # 6x6 matrix in GPa
  "bulk_modulus": 120.5,  # GPa (Voigt average)
  "shear_modulus": 55.3,  # GPa
  "youngs_modulus": 145.2,  # GPa
  "poissons_ratio": 0.31,
  "universal_anisotropy": 1.05,
  "is_stable": True  # Positive definite elastic tensor
}
```

**Speed:** ~20s per structure

---

#### 15. `matcalc_calc_phonon` — Vibrational Properties

Calculate phonon dispersion, density of states, and temperature-dependent thermodynamics.

**Key parameters:**
- `structure_input`: pymatgen Structure dict or CIF/POSCAR string
- `calculator`: ML potential (default `"TensorNet-MatPES-PBE"`)
- `atom_disp`: atomic displacement for force constants (default 0.015 Å)
- `supercell_matrix`: phonon supercell (default `[[2,0,0],[0,2,0],[0,0,2]]`)
- `t_min`, `t_max`, `t_step`: temperature range for thermodynamics (default 0-1000 K, step 10 K)
- `relax_structure`: relax before calculation (default `False`, already relaxed)

**Returns:**
```python
{
  "success": True,
  "formula": "LiFePO4",
  "has_imaginary_modes": False,  # False = dynamically stable
  "free_energy": {...},  # Dict with temperatures as keys
  "entropy": {...},
  "heat_capacity": {...},
  "zero_point_energy": 0.45,  # eV/atom
  "phonon_band_structure": {...},
  "phonon_dos": {...}
}
```

**Speed:** ~60s per structure

---

#### 16. `matcalc_calc_surface` — Surface Energies

Calculate surface energy for specific Miller indices by comparing slab and bulk energies.

**Key parameters:**
- `structure_input`: bulk structure (pymatgen dict or CIF/POSCAR)
- `miller_index`: surface plane as list `[h,k,l]` (e.g., `[1,1,1]`)
- `calculator`: ML potential (default `"CHGNet"`)
- `min_slab_size`: slab thickness in Å (default 10.0)
- `min_vacuum_size`: vacuum gap in Å (default 10.0)
- `symmetrize`: ensure symmetric slab (default `True`)
- `relax_slab`: relax slab structure (default `True`)

**Returns:**
```python
{
  "success": True,
  "formula": "LiFePO4",
  "miller_index": [1, 1, 1],
  "surface_energy": 1.25,  # J/m²
  "slab_energy": -1240.5,  # eV
  "bulk_energy_per_atom": -5.12,  # eV/atom
  "slab_structure": {...}  # Relaxed slab
}
```

**Speed:** ~30s per surface

---

#### 17. `matcalc_calc_eos` — Equation of State

Compute volume-energy relationship, equilibrium volume, and bulk modulus by fitting EOS models.

**Key parameters:**
- `input_structure`: pymatgen Structure dict or CIF/POSCAR string
- `calculator`: ML potential (default `"TensorNet-MatPES-PBE-v2025.1-PES"`)
- `relax_structure`: relax before calculation (default `False`, already relaxed)
- `n_points`: number of volume points (default 11)
- `max_abs_strain`: maximum volume strain (default 0.1, ±10%)
- `eos_type`: fitting model (default `"vinet"`)

**Returns:**
```python
{
  "success": True,
  "formula": "LiFePO4",
  "equilibrium_volume": 291.4,  # Å³
  "bulk_modulus": 120.5,  # GPa
  "bulk_modulus_derivative": 4.2,
  "equilibrium_energy": -247.8,  # eV
  "eos_type": "vinet",
  "volumes": [...],
  "energies": [...]
}
```

**Speed:** ~30s per structure

---

#### 18. `matcalc_calc_adsorption` — Adsorption Energies

Compute adsorption energy by comparing adsorbate-slab system to clean slab and isolated adsorbate.

**Key parameters:**
- `slab_structure`: slab with vacuum (pymatgen dict or CIF/POSCAR)
- `adsorbate`: molecule formula (e.g., `"CO"`, `"H2O"`)
- `adsorption_site`: site type (default `"ontop"`)
- `distance`: adsorbate-surface distance in Å (default 2.0)
- `calculator`: ML potential (default `"CHGNet"`)
- `relax_adsorbate_slab`: relax adsorbate+slab system (default `True`)

**Returns:**
```python
{
  "success": True,
  "adsorbate": "CO",
  "adsorption_site": "ontop",
  "adsorption_energy": -1.35,  # eV (negative = favorable)
  "adsorbate_slab_energy": -1255.8,  # eV
  "clean_slab_energy": -1240.5,  # eV
  "adsorbate_energy": -13.8,  # eV
  "relaxed_structure": {...}
}
```

**Speed:** ~40s per adsorbate

---

#### 19. `matcalc_calc_md` — Molecular Dynamics

Run MD simulations to calculate thermodynamic properties and sample phase space.

**Key parameters:**
- `structure_input`: pymatgen Structure dict or CIF/POSCAR string
- `calculator`: ML potential (default `"TensorNet-MatPES-PBE"`)
- `ensemble`: MD ensemble (default `"nvt"`)
- `temperature`: temperature in K (default 300.0)
- `timestep`: timestep in fs (default 1.0)
- `steps`: MD steps (default 100)
- `pressure`: pressure in GPa (default `None`, used for NPT)
- `relax_structure`: relax before MD (default `False`, already relaxed)

**Returns:**
```python
{
  "success": True,
  "formula": "LiFePO4",
  "ensemble": "nvt",
  "average_temperature": 300.2,  # K
  "average_energy": -247.5,  # eV
  "energy_std": 0.15,  # eV
  "final_structure": {...},
  "trajectory": [...]  # List of structures
}
```

**Speed:** Variable (~1-10 min depending on steps)

---

#### 20. `matcalc_calc_neb` — Reaction Barriers

Calculate minimum energy path and activation barrier between initial and final structures using NEB.

**Key parameters:**
- `images`: initial and final structures (list or dict)
- `calculator`: ML potential (default `"M3GNet"`)
- `n_images`: number of NEB images (default 5)
- `climb`: use climbing image NEB for accurate barriers (default `True`)
- `fmax`: force convergence in eV/Å (default 0.1)
- `optimizer`: NEB optimizer (default `"FIRE"`)

**Returns:**
```python
{
  "success": True,
  "activation_barrier_forward": 0.82,  # eV
  "activation_barrier_reverse": 1.15,  # eV
  "transition_state_energy": -245.8,  # eV
  "reaction_energy": -0.33,  # eV (final - initial)
  "converged": True,
  "energies": [...],
  "images": [...]
}
```

**Speed:** ~5-30 min depending on n_images

---

#### 21. `matcalc_calc_phonon3` — Thermal Conductivity

Calculate lattice thermal conductivity using third-order force constants and BTE.

**Key parameters:**
- `structure_input`: pymatgen Structure dict or CIF/POSCAR string
- `calculator`: ML potential (default `"TensorNet-MatPES-PBE"`)
- `fc2_supercell`: 2nd-order force constant supercell (default `[[2,0,0],[0,2,0],[0,0,2]]`)
- `fc3_supercell`: 3rd-order force constant supercell (default `[[2,0,0],[0,2,0],[0,0,2]]`)
- `mesh_numbers`: q-point mesh (default `[20,20,20]`)
- `t_min`, `t_max`, `t_step`: temperature range (default 0-1000 K)
- `relax_structure`: relax before calculation (default `False`, already relaxed)

**Returns:**
```python
{
  "success": True,
  "formula": "LiFePO4",
  "thermal_conductivity": {...},  # Dict with temperatures as keys, W/(m·K)
  "kappa_300K": 5.2,  # W/(m·K) at 300 K
  "mean_free_path": {...}  # Temperature-dependent
}
```

**Speed:** ~1-2 hours per structure (very expensive!)

---

#### 22. `matcalc_calc_qha` — Thermal Expansion

Calculate temperature-dependent thermodynamics using quasi-harmonic approximation.

**Key parameters:**
- `structure_input`: pymatgen Structure dict or CIF/POSCAR string
- `calculator`: ML potential (default `"TensorNet-MatPES-PBE"`)
- `t_min`, `t_max`, `t_step`: temperature range (default 0-1000 K)
- `scale_factors`: volume scaling factors (default `[0.95, ..., 1.05]`)
- `eos`: EOS model (default `"vinet"`)
- `relax_structure`: relax before calculation (default `False`, already relaxed)

**Returns:**
```python
{
  "success": True,
  "formula": "LiFePO4",
  "thermal_expansion_coefficient": {...},  # Dict with temps, 1/K
  "gibbs_free_energy": {...},  # Temperature-dependent, eV
  "bulk_modulus_p": {...},  # Temperature-dependent, GPa
  "heat_capacity_p": {...},  # Cp, J/(mol·K)
  "gruneisen_parameter": {...}
}
```

**Speed:** ~2-5 min per structure

---

#### 23. `matcalc_calc_energetics` — Formation & Cohesive Energy

Compute formation energy (relative to elemental references) and cohesive energy.

**Key parameters:**
- `structure_input`: pymatgen Structure dict or CIF/POSCAR string
- `calculator`: ML potential (default `"M3GNet"`)
- `elemental_refs`: reference data (default `"MatPES-PBE"`)
- `relax_structure`: relax before calculation (default `False`, already relaxed)
- `fmax`: force convergence tolerance in eV/Å (default 0.1)

**Returns:**
```python
{
  "success": True,
  "formula": "LiFePO4",
  "formation_energy_per_atom": -2.35,  # eV/atom
  "cohesive_energy_per_atom": -5.12,  # eV/atom
  "total_energy": -247.8,  # eV
  "calculator": "M3GNet-MatPES-PBE-v2025.1-PES",
  "confidence": "medium-high"
}
```

**NOTE:** For formation energy screening, prefer `matgl_predict_eform` (20× faster). Use this tool only when cohesive energy is needed.

**Speed:** ~30s per structure

---

#### 24. `matcalc_calc_interface` — Interface Energies

Calculate grain boundary or heterostructure interface energy.

**Key parameters:**
- `interface_structure`: combined interface structure (pymatgen dict or CIF/POSCAR)
- `film_bulk`: bulk structure of film/top layer
- `substrate_bulk`: bulk structure of substrate/bottom layer
- `calculator`: ML potential (default `"CHGNet"`)
- `relax_bulk`: relax bulk references (default `True`)
- `relax_interface`: relax interface structure (default `True`)

**Returns:**
```python
{
  "success": True,
  "interface_energy": 0.85,  # J/m²
  "interface_total_energy": -2480.5,  # eV
  "film_bulk_energy_per_atom": -5.12,  # eV/atom
  "substrate_bulk_energy_per_atom": -6.23  # eV/atom
}
```

**Speed:** ~1-2 min per interface

---

## Phase 3: Ranking & Selection Tools

### 25. `multi_objective_ranker` — Rank Candidates by Multiple Criteria

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

**Speed:** ~10s for 100 candidates
