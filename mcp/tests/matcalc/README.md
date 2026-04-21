# MatCalc Tests

This directory contains comprehensive tests for the matcalc tools in MatClaw.

## Running Tests

### Run all matcalc tests:
```bash
pytest tests/matcalc/ -v
```

### Run specific test file:
```bash
pytest tests/matcalc/test_matcalc_calc_elasticity.py -v
```

### Run specific test class:
```bash
pytest tests/matcalc/test_matcalc_calc_elasticity.py::TestElasticityCalc -v
```

### Run specific test:
```bash
pytest tests/matcalc/test_matcalc_calc_elasticity.py::TestElasticityCalc::test_basic_elasticity_calculation -v
```

### Run with coverage:
```bash
pytest tests/matcalc/ --cov=tools.matcalc --cov-report=html
```

### Run slow tests (integration tests):
```bash
pytest tests/matcalc/ -v -m slow
```

### Skip slow tests:
```bash
pytest tests/matcalc/ -v -m "not slow"
```

## Test Structure

### test_matcalc_calc_elasticity.py

Comprehensive tests for elastic property calculations:

**TestElasticityCalc class:**
- `test_basic_elasticity_calculation` - Basic functionality with Si structure
- `test_elastic_tensor_structure` - Validates tensor dimensions and symmetry
- `test_mechanical_stability` - Tests stability analysis and eigenvalue checks
- `test_voigt_reuss_hill_averages` - Validates VRH averaging formulas
- `test_derived_properties` - Tests Young's modulus, Poisson's ratio calculations
- `test_ductility_classification` - Tests Pugh ratio and ductility interpretation
- `test_anisotropy_classification` - Tests anisotropy index calculations
- `test_with_structure_relaxation` - Tests integrated relaxation workflow
- `test_without_deformed_structure_relaxation` - Fast calculation mode
- `test_custom_strain_ranges` - Tests custom strain parameters
- `test_different_calculators` - Tests multiple ML potentials
- `test_cif_string_input` - Tests CIF format input parsing
- `test_output_completeness` - Validates all output fields are present
- `test_parameters_recorded` - Checks parameter tracking in output
- `test_calculation_timing` - Validates timing information
- `test_error_handling_invalid_structure` - Tests error handling for bad input
- `test_error_handling_invalid_calculator` - Tests error handling for bad calculator
- `test_full_workflow_with_relaxation` - Full integration test (marked slow)

**TestEdgeCases class:**
- `test_very_tight_convergence` - Tests with strict convergence criteria
- `test_minimal_strain_points` - Tests minimum strain sampling
- `test_single_calculator_invocation` - Tests repeatability

## Test Fixtures

The `conftest.py` file provides shared test fixtures:

- `cubic_si_structure` - Simple Si diamond cubic structure
- `cubic_cscl_structure` - CsCl structure (Pm-3m)
- `cubic_nacl_structure` - NaCl rocksalt structure
- `stressed_structure` - Intentionally stressed structure for relaxation tests
- `cif_string_si` - Si structure as CIF string

## Test Coverage

The tests cover:

✅ **Input formats**: Dict, CIF string, POSCAR string  
✅ **Calculators**: TensorNet-MatPES-PBE, aliases  
✅ **Relaxation modes**: With/without structure relaxation  
✅ **Deformation handling**: With/without deformed structure relaxation  
✅ **Strain parameters**: Default and custom strain ranges  
✅ **Output validation**: All required fields, correct dimensions  
✅ **Physical correctness**: Moduli formulas, stability criteria  
✅ **Classifications**: Ductility (Pugh ratio), anisotropy  
✅ **Error handling**: Invalid inputs, missing dependencies  
✅ **Performance**: Timing, repeatability  
✅ **Integration**: Full relaxation + elasticity workflow  

## Expected Test Results

### Si (Diamond Cubic)
- Bulk modulus: ~80-120 GPa (experimental ~98 GPa)
- Shear modulus: ~40-70 GPa (experimental ~52 GPa)
- Pugh ratio (K/G): ~1.4-1.9 (brittle, <1.75)
- Mechanically stable (all eigenvalues > 0)

### NaCl (Rocksalt)
- Bulk modulus: ~20-35 GPa (experimental ~24 GPa)
- More ductile than Si (higher K/G ratio)
- Cubic symmetry maintained

### CsCl
- Bulk modulus: ~15-25 GPa
- Simple cubic structure
- Should be mechanically stable when relaxed

## Known Limitations

1. **Calculator availability**: Tests will skip gracefully if matcalc not installed
2. **Slow tests**: Full integration tests marked with `@pytest.mark.slow`
3. **Numerical precision**: Results may vary slightly between runs due to optimization
4. **Model accuracy**: ML potential results differ from DFT (expected ~10-20% variance)

## Troubleshooting

### Import errors:
```bash
pip install matcalc[matgl] pymatgen pytest
```

### Tests timing out:
Increase timeout or use faster convergence criteria (higher fmax)

### Inconsistent results:
ML potentials have some stochasticity; small variations are expected

### Memory errors:
Reduce number of strain points or use smaller structures

## Adding New Tests

When adding tests for new matcalc tools:

1. Create test file: `test_matcalc_calc_<property>.py`
2. Add fixtures to `conftest.py` if reusable
3. Follow naming convention: `test_<functionality>`
4. Use pytest markers for slow/integration tests
5. Include error handling tests
6. Validate output completeness
7. Check physical correctness of results

## References

- pytest documentation: https://docs.pytest.org/
- MatCalc documentation: https://matcalc.ai/
- Pymatgen testing guide: https://pymatgen.org/
