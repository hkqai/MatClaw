# ML Calculations Guide: MatGL vs matcalc

This guide explains when and how to use MatGL (direct predictions) vs matcalc (structure-based calculations) for property retrieval.

## Quick Decision Tree

```
NEED formation energy or band gap ONLY?
  → Use MatGL (matgl_predict_eform, matgl_predict_bandgap)
    Fast direct predictions (~0.5-2s per structure)

NEED mechanical, vibrational, surface, or thermal properties?
  → Use matcalc (matcalc_calc_elasticity, matcalc_calc_phonon, etc.)
    Structure-based calculations with 2025 ML potentials (~10-60s per property)

NEED to relax structures?
  → Use matgl_relax_structure (REQUIRED before all predictions)
    PYG backend, cannot mix with MatGL predictions in same session
```

---

## Tool Categories

### MatGL Tools (Direct Property Predictions)

**Backend:** DGL (Deep Graph Library) for predictions, PYG (PyTorch Geometric) for relaxation  
**Models:** M3GNet (2018), MEGNet (2018-2019) - trained on Materials Project DFT data  
**Speed:** Fast (~0.5-2s per structure)  
**Use case:** High-throughput screening for formation energy and band gap

#### Available MatGL Tools:

1. **`matgl_relax_structure`** (PYG backend)
   - Relaxes structures using TensorNet-MatPES-PBE-v2025.1-PES
   - **MANDATORY** before ALL ML predictions (MatGL and matcalc)
   - ~5-10s per structure
   - **IMPORTANT:** Cannot call MatGL prediction tools in same Python session after this (backend conflict)

2. **`matgl_predict_eform`** (DGL backend)
   - Predicts formation energy directly
   - Models: M3GNet-MP-2018.6.1-Eform (primary), MEGNet-MP-2018.6.1-Eform (fallback)
   - ~0.5-1s per structure
   - **PRIMARY TOOL for formation energy screening**

3. **`matgl_predict_bandgap`** (DGL backend)
   - Predicts electronic band gap directly
   - Model: MEGNet-MP-2019.4.1-BandGap-mfi
   - ~0.5-1s per structure
   - **ONLY TOOL for band gap prediction**

---

### matcalc Tools (Structure-Based Calculations)

**Backend:** ASE + ML potentials (TensorNet, CHGNet, M3GNet)  
**Models:** TensorNet-MatPES-PBE-v2025.1-PES (primary), CHGNet, M3GNet  
**Speed:** Slower (~10-60s per property depending on complexity)  
**Use case:** Detailed property calculations beyond formation energy/band gap

#### Available matcalc Tools:

**Mechanical Properties:**
- `matcalc_calc_elasticity` - Full elastic tensor, bulk/shear/Young's modulus
- `matcalc_calc_eos` - Equation of state, equilibrium volume, bulk modulus

**Vibrational Properties:**
- `matcalc_calc_phonon` - Phonon dispersion, DOS, thermodynamics, stability
- `matcalc_calc_phonon3` - Third-order force constants, thermal conductivity

**Thermal Properties:**
- `matcalc_calc_qha` - Quasi-harmonic approximation, thermal expansion
- `matcalc_calc_md` - Molecular dynamics, thermodynamic sampling

**Surface & Interface:**
- `matcalc_calc_surface` - Surface energies for specific Miller indices
- `matcalc_calc_interface` - Grain boundary / heterostructure energies
- `matcalc_calc_adsorption` - Adsorption energies on surfaces

**Reaction Energetics:**
- `matcalc_calc_neb` - Minimum energy path, activation barriers
- `matcalc_calc_energetics` - Formation & cohesive energy (use MatGL for formation energy screening instead)

---

## When to Use Each

### Use MatGL for:

✅ **High-throughput formation energy screening**
- Fast direct predictions (~0.5s vs ~30s for matcalc)
- Trained specifically for formation energy prediction
- Example: Screen 100 candidates by formation energy → use `matgl_predict_eform`

✅ **Band gap screening**
- Only available tool for band gap prediction
- Example: Filter candidates by band gap 1.0-2.0 eV → use `matgl_predict_bandgap`

✅ **Initial rapid screening**
- Get formation energy + band gap for all candidates in minutes
- Use these properties to filter before expensive matcalc calculations

---

### Use matcalc for:

✅ **Application-specific properties beyond formation energy/band gap**
- Mechanical properties (elasticity, hardness)
- Vibrational properties (phonon stability, thermodynamics)
- Surface properties (catalyst screening)
- Thermal properties (thermal expansion, conductivity)

✅ **Detailed calculations for top candidates**
- After MatGL screening, use matcalc for top 10-20 candidates
- Example: MatGL identifies 42 stable candidates → matcalc calculates mechanical properties for top 20

✅ **When you need 2025 ML potentials**
- TensorNet-MatPES-PBE-v2025.1-PES (state-of-the-art)
- CHGNet (magnetic materials)

---

## Hierarchical Screening Strategy (Recommended)

**Step 1: Fast MatGL screening (minutes)**
```
FOR each candidate in candidates:
    1. Relax with matgl_relax_structure
    2. Predict formation energy with matgl_predict_eform
    3. Predict band gap with matgl_predict_bandgap
    4. Filter by criteria (formation energy < 0, band gap 1-2 eV)

Result: 100 candidates → 42 passed MatGL screening
```

**Step 2: Detailed matcalc calculations (hours)**
```
FOR each candidate in top_candidates[:20]:
    1. Calculate mechanical properties with matcalc_calc_elasticity
    2. Calculate phonon properties with matcalc_calc_phonon
    3. Calculate surface energies with matcalc_calc_surface (if catalyst)

Result: 42 passed → 20 with detailed properties → 8 high-priority for DFT
```

**Step 3: DFT verification (days)**
```
Run DFT calculations for top 8 candidates with ML-predicted properties
Validate formation energy, band gap, mechanical properties
```

---

## Formation Energy: MatGL vs matcalc

**Both tools can predict formation energy, but use cases differ:**

### matgl_predict_eform (PREFERRED for screening)
- **Speed:** ~0.5s per structure
- **Method:** Direct ML prediction (M3GNet/MEGNet trained on MP formation energies)
- **Output:** Formation energy per atom (eV/atom)
- **Use when:** High-throughput screening, need formation energy ONLY
- **Example:** Screen 100 candidates by formation energy

### matcalc_calc_energetics (use for cohesive energy)
- **Speed:** ~30s per structure
- **Method:** Total energy calculation + elemental reference subtraction
- **Output:** Formation energy AND cohesive energy (eV/atom)
- **Use when:** Need cohesive energy, detailed energetics analysis
- **Example:** Analyze bonding strength, compare to elemental phases

**Rule of thumb:** Use MatGL for screening, matcalc for detailed analysis.

---

## Mandatory Relaxation Workflow

**ALL ML predictions require relaxed structures. Always follow this sequence:**

```
# WRONG: Skip relaxation
structure_unrelaxed = candidate.structure
eform = matgl_predict_eform(structure_unrelaxed)  # Inaccurate!

# CORRECT: Relax first
structure_unrelaxed = candidate.structure
relaxed = matgl_relax_structure(structure_unrelaxed, fmax=0.1, max_steps=500)
structure_relaxed = relaxed["final_structure"]

# THEN predict properties
eform = matgl_predict_eform(structure_relaxed)  # Accurate
bandgap = matgl_predict_bandgap(structure_relaxed)  # Accurate

# OR calculate with matcalc
elasticity = matcalc_calc_elasticity(
    structure_relaxed,
    relax_structure=False  # Already relaxed!
)
```

**Exception:** If structures come from DFT, Materials Project, or experimental data, they are already optimized → set `relax_structure=False` or skip relaxation tool.

---

### ML Model Selection Guide

**Formation Energy:**
- Primary: `M3GNet-MP-2018.6.1-Eform` (matgl_predict_eform)
- Fallback: `MEGNet-MP-2018.6.1-Eform` (matgl_predict_eform)
- Alternative: `TensorNet-MatPES-PBE-v2025.1-PES` via matcalc_calc_energetics (slower)

**Band Gap:**
- Only option: `MEGNet-MP-2019.4.1-BandGap-mfi` (matgl_predict_bandgap)

**Mechanical Properties:**
- Primary: `TensorNet-MatPES-PBE-v2025.1-PES` (matcalc_calc_elasticity)
- Alternative: `CHGNet` for magnetic materials

**Vibrational Properties:**
- Primary: `TensorNet-MatPES-PBE` (matcalc_calc_phonon)
- Alternative: `M3GNet` for faster (less accurate) calculations

**Surface Properties:**
- Primary: `CHGNet` (matcalc_calc_surface)
- Alternative: `TensorNet-MatPES-PBE-v2025.1-PES`

**Rule:** Use TensorNet-MatPES-PBE-v2025.1-PES for most matcalc calculations (state-of-the-art 2025 model). Use CHGNet for magnetic materials and surfaces.

---

## Parameter Guidelines

### Relaxation Parameters

**fmax (force convergence tolerance):**
- Screening: 0.1 eV/Å (fast, sufficient for trends)
- Detailed: 0.05 eV/Å (slower, more accurate)
- Critical: 0.01 eV/Å (very slow, DFT-quality)

**max_steps:**
- Simple structures: 200 steps
- Complex structures: 500 steps
- Difficult relaxations: 1000 steps

**relax_cell:**
- Always `True` unless comparing isostructural series

---

### Phonon Parameters

**supercell_matrix:**
- Screening: `[[2,0,0],[0,2,0],[0,0,2]]` (fast, 8× primitive cell)
- Detailed: `[[3,0,0],[0,3,0],[0,0,3]]` (27× primitive cell)
- Small primitive cells: Increase to ensure ~20-30 atoms

**atom_disp:**
- Default: 0.015 Å (good compromise)
- Hard materials: 0.01 Å (stiffer bonds)
- Soft materials: 0.02 Å (softer bonds)

---

### Elasticity Parameters

**norm_strains:**
- Default: 0.01 (1% strain)
- Hard materials: 0.005 (0.5% strain, smaller deformations)
- Soft materials: 0.02 (2% strain)

**relax_deformed_structures:**
- Always `True` (allow atomic relaxation in strained structures)
- Improves accuracy significantly

---

### Surface Parameters

**min_slab_size:**
- Screening: 10 Å (fast)
- Detailed: 15 Å (more accurate)
- Converged: 20+ Å (publication-quality)

**min_vacuum_size:**
- Default: 10 Å (sufficient for most materials)
- Polar surfaces: 15 Å (avoid spurious interactions)

**relax_slab:**
- Always `True` (surface reconstruction common)

---

## Common Screening Workflows

### Workflow 1: Battery Cathode Screening

**Goal:** Find stable materials with moderate band gap and low formation energy

```
# Phase 1: MatGL screening (fast)
FOR each candidate:
    relax → matgl_predict_eform → matgl_predict_bandgap
    FILTER: formation_energy < 0.0 AND band_gap 0.5-2.0 eV

# Phase 2: matcalc calculations (top 20)
FOR each top_candidate:
    matcalc_calc_elasticity  # Mechanical stability
    matcalc_calc_phonon      # Dynamic stability

# Result: 100 → 42 passed MatGL → 20 with detailed props → 8 for DFT
```

**Estimated time:**
- Phase 1 (100 candidates): ~15 minutes (relaxation 10 min, predictions 2 min)
- Phase 2 (20 candidates): ~40 minutes (elasticity 10 min, phonons 30 min)
- Total: ~55 minutes

---

### Workflow 2: Catalyst Screening

**Goal:** Find materials with stable surfaces and good adsorption properties

```
# Phase 1: MatGL screening (fast)
FOR each candidate:
    relax → matgl_predict_eform → stability_analyzer
    FILTER: formation_energy < 0.0 AND thermodynamically_stable

# Phase 2: Surface calculations (top 30)
FOR each top_candidate:
    matcalc_calc_surface(miller_index=[1,0,0])
    matcalc_calc_surface(miller_index=[1,1,0])
    matcalc_calc_surface(miller_index=[1,1,1])
    FILTER: surface_energy < threshold

# Phase 3: Adsorption calculations (top 10)
FOR each top_surface:
    matcalc_calc_adsorption(adsorbate="CO", site="ontop")
    matcalc_calc_adsorption(adsorbate="OH", site="ontop")

# Result: 100 → 68 stable → 30 with surfaces → 10 with adsorption → 5 for DFT
```

**Estimated time:**
- Phase 1: ~15 minutes
- Phase 2: ~90 minutes (3 surfaces × 30 candidates)
- Phase 3: ~40 minutes (2 adsorbates × 10 candidates)
- Total: ~2.5 hours

---

### Workflow 3: Thermoelectric Screening

**Goal:** Narrow band gap, mechanical stability, low thermal conductivity

```
# Phase 1: MatGL screening (fast)
FOR each candidate:
    relax → matgl_predict_bandgap
    FILTER: band_gap < 0.5 eV (narrow gap)

# Phase 2: Mechanical properties (top 40)
FOR each candidate:
    matcalc_calc_elasticity
    FILTER: is_mechanically_stable

# Phase 3: Thermal conductivity (top 15)
FOR each top_candidate:
    matcalc_calc_phonon3  # Expensive! ~1-2 hours per candidate
    FILTER: thermal_conductivity_300K < threshold

# Result: 100 → 52 narrow gap → 40 stable → 15 with κ → 8 for DFT
```

**Estimated time:**
- Phase 1: ~15 minutes
- Phase 2: ~20 minutes
- Phase 3: ~20-30 hours (phonon3 very expensive)
- Total: ~21-31 hours

**Note:** Thermal conductivity calculations are extremely expensive. Only run for top candidates after all other screening.

---

## Confidence Levels

**Source confidence hierarchy:**

1. **Materials Project (DFT):** Confidence = 1.0
   - Gold standard reference data

2. **ASE cached (MP/DFT):** Confidence = 1.0
   - Cached from previous Materials Project / DFT calculations

3. **ASE cached (ML matcalc 2025):** Confidence = 0.8
   - TensorNet-MatPES-PBE-v2025.1-PES calculations

4. **MatGL M3GNet predictions:** Confidence = 0.75
   - M3GNet-MP-2018.6.1-Eform for formation energy

5. **MatGL MEGNet predictions:** Confidence = 0.65-0.7
   - MEGNet-MP-2018.6.1-Eform for formation energy
   - MEGNet-MP-2019.4.1-BandGap-mfi for band gap

6. **Estimated from similar materials:** Confidence = 0.5
   - Last resort fallback

**Apply confidence weighting in ranking:**
```
adjusted_score = base_score × confidence_factor

IF base_score > 0.8 AND confidence < 0.8:
    recommend_dft_verification = True
    dft_priority = "high"
```

---

## Common Pitfalls

### ❌ WRONG: Skip relaxation

```python
# BAD: Unrelaxed structures → inaccurate predictions
eform = matgl_predict_eform(candidate.structure)
```

### ✅ CORRECT: Always relax first

```python
# GOOD: Relax → predict
relaxed = matgl_relax_structure(candidate.structure, fmax=0.1)
eform = matgl_predict_eform(relaxed["final_structure"])
```

---

### ❌ WRONG: Use matcalc for formation energy screening

```python
# BAD: Slow (~30s per candidate)
FOR candidate in 100_candidates:
    eform = matcalc_calc_energetics(candidate.structure)
# Total: 50 minutes
```

### ✅ CORRECT: Use MatGL for screening

```python
# GOOD: Fast (~0.5s per candidate)
FOR candidate in 100_candidates:
    eform = matgl_predict_eform(candidate.structure)
# Total: 1-2 minutes
```

---

### ❌ WRONG: Mix MatGL backends

```python
# BAD: PYG backend conflict
relaxed = matgl_relax_structure(structure)  # PYG
eform = matgl_predict_eform(relaxed["final_structure"])  # DGL - CRASH!
```

### ✅ CORRECT: Use MCP tools (backend isolated)

```python
# GOOD: MCP server handles backend switching
relaxed = matgl_relax_structure(structure)  # MCP isolates PYG
eform = matgl_predict_eform(relaxed["final_structure"])  # MCP isolates DGL
```

---

### ❌ WRONG: Over-relax structures

```python
# BAD: Waste time on tiny force convergence
relaxed = matgl_relax_structure(structure, fmax=0.001, max_steps=5000)
# ~5 minutes per structure for 0.1% accuracy improvement
```

### ✅ CORRECT: Use appropriate fmax

```python
# GOOD: fmax=0.1 for screening (sufficient accuracy, 10× faster)
relaxed = matgl_relax_structure(structure, fmax=0.1, max_steps=500)
# ~30s per structure
```

---

## Summary

**Quick reference:**

| Property | Tool | Speed | When to Use |
|----------|------|-------|-------------|
| Formation energy | `matgl_predict_eform` | Fast (0.5s) | Screening |
| Band gap | `matgl_predict_bandgap` | Fast (0.5s) | Screening |
| Mechanical | `matcalc_calc_elasticity` | Medium (20s) | Top candidates |
| Vibrational | `matcalc_calc_phonon` | Slow (60s) | Top candidates |
| Surface | `matcalc_calc_surface` | Medium (30s) | Catalysts |
| Thermal conductivity | `matcalc_calc_phonon3` | Very slow (1-2h) | Final validation |

**Strategy:** MatGL screening first (minutes) → matcalc detailed calculations second (hours) → DFT verification third (days)
