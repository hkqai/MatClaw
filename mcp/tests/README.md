# MatClaw MCP Tests

This directory contains tests for the MatClaw MCP tools.

## Running Tests

### Run all tests
```bash
pytest
```

### Run with verbose output
```bash
pytest -v
```

### Run specific test file
```bash
pytest tests/pymatgen/test_substitution_generator.py
```

### Run specific test class
```bash
pytest tests/pymatgen/test_substitution_generator.py::TestSimpleSubstitution
```

### Run specific test
```bash
pytest tests/pymatgen/test_substitution_generator.py::TestSimpleSubstitution::test_simple_substitution_success
```

### Run tests matching pattern
```bash
pytest -k "substitution"
```

### Run with coverage (requires pytest-cov)
```bash
pytest --cov=tools --cov-report=html
```

## Important Notes

### ML Prediction Tests - Backend Limitation

**IMPORTANT**: The ML prediction tests cannot be run all together in the same pytest session due to a MatGL backend limitation.

**Background**: 
- Structure relaxation tools (`ml_relax_structure`) use TensorNet models which require the **PYG** (PyTorch Geometric) backend
- Property prediction tools (`ml_predict_eform`, `ml_predict_bandgap`) use M3GNet/MEGNet models which require the **DGL** backend
- MatGL can only use **one backend per Python process** and cannot switch backends once initialized

**Problem**: Running `pytest tests/ml_prediction/ -v` will cause tests to fail because:
1. Whichever backend is set first will be locked for the entire test session
2. Tests requiring the other backend will fail with backend-related errors

**Solution**: Run each ML prediction test file separately:
```bash
# Run relaxation tests (PYG backend)
pytest tests/ml_prediction/test_ml_relax_structure.py -v

# Run formation energy prediction tests (DGL backend)  
pytest tests/ml_prediction/test_ml_predict_eform.py -v

# Run band gap prediction tests (DGL backend)
pytest tests/ml_prediction/test_ml_predict_bandgap.py -v
```

**Note**: This is NOT a functional issue. In production (MCP server usage), each tool call runs independently and works correctly. The limitation only affects running all tests together in the same Python process.

## Writing Tests

### Using Fixtures

Shared fixtures are defined in `conftest.py`. Use them in your tests:

```python
def test_my_feature(simple_lifep04_structure):
    result = my_function(simple_lifep04_structure)
    assert result["success"] is True
```

### Test Organization

Organize tests into classes by feature:

```python
class TestFeatureName:
    """Tests for specific feature."""
    
    def test_basic_case(self, fixture_name):
        """Test description."""
        # Test code
        assert condition
    
    def test_edge_case(self, fixture_name):
        """Test edge case."""
        # Test code
        assert condition
```

### Assertions

Use clear, specific assertions:
- `assert result["success"] is True`
- `assert "expected" in result["message"]`
- `assert result["count"] == 5`
- `assert result["value"] == pytest.approx(1.23, abs=0.01)`

## CI/CD Integration

These tests can be integrated into GitHub Actions or other CI/CD pipelines:

```yaml
- name: Run tests
  run: |
    pip install pytest pytest-cov pymatgen
    pytest tests/ -v
```
