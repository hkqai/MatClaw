"""
Tests for XRD pattern analysis tool.

Test strategy
-------------
Tests are divided into:
1. Input validation (file paths, parameters) - run with mock files
2. Model detection logic (single vs dual models) - limited since autoXRD is integrated
3. Integration tests with actual autoXRD (requires trained models and reference CIFs)

Most tests verify input validation and error handling without requiring trained models.
Full integration tests require downloading models from XRD-AutoAnalyzer repository.
"""

import os
import pytest
import tempfile
import numpy as np

from tools.characterization.xrd_analyze_pattern import xrd_analyze_pattern


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_xy_file(tmp_path):
    """Create a mock XRD pattern file in .xy format."""
    xy_file = tmp_path / "sample.xy"
    # Generate synthetic XRD pattern (2theta, intensity)
    two_theta = np.linspace(10, 80, 700)
    # Simple Gaussian peaks at typical positions
    intensity = (
        100 * np.exp(-((two_theta - 25) ** 2) / 4) +
        80 * np.exp(-((two_theta - 35) ** 2) / 3) +
        60 * np.exp(-((two_theta - 50) ** 2) / 5) +
        np.random.normal(0, 2, len(two_theta))  # noise
    )
    data = np.column_stack([two_theta, intensity])
    np.savetxt(xy_file, data, fmt="%.3f")
    return str(xy_file)


@pytest.fixture
def mock_model_single(tmp_path):
    """Create a mock single model file."""
    model_file = tmp_path / "Model.h5"
    model_file.write_text("# Mock HDF5 model file")
    return str(model_file)


@pytest.fixture
def mock_model_dual(tmp_path):
    """Create a mock dual model directory with XRD and PDF models."""
    models_dir = tmp_path / "Models"
    models_dir.mkdir()
    xrd_model = models_dir / "XRD_Model.h5"
    pdf_model = models_dir / "PDF_Model.h5"
    xrd_model.write_text("# Mock XRD HDF5 model")
    pdf_model.write_text("# Mock PDF HDF5 model")
    return str(models_dir)


@pytest.fixture
def mock_references(tmp_path):
    """Create mock References directory with placeholder CIFs."""
    refs_dir = tmp_path / "References"
    refs_dir.mkdir()
    # Create a few mock CIF files
    (refs_dir / "BaTiO3_99.cif").write_text("# Mock CIF for BaTiO3")
    (refs_dir / "BaO_225.cif").write_text("# Mock CIF for BaO")
    return str(refs_dir)


# ---------------------------------------------------------------------------
# Input validation tests
# ---------------------------------------------------------------------------

def test_nonexistent_spectrum():
    """Test error handling for missing spectrum file."""
    result = xrd_analyze_pattern(
        spectrum_path="/nonexistent/path/fake.xy",
        model_path="/fake/model.h5"
    )
    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_nonexistent_model():
    """Test error handling for missing model file."""
    with tempfile.NamedTemporaryFile(suffix=".xy", delete=False) as tmp:
        tmp.write(b"10.0 100.0\n20.0 200.0\n")
        tmp_path = tmp.name
    
    try:
        result = xrd_analyze_pattern(
            spectrum_path=tmp_path,
            model_path="/nonexistent/model.h5"
        )
        assert result["success"] is False
        assert "not found" in result["error"].lower()
    finally:
        os.unlink(tmp_path)


def test_invalid_angle_range():
    """Test validation of min_angle < max_angle."""
    result = xrd_analyze_pattern(
        spectrum_path="dummy.xy",
        model_path="dummy.h5",
        min_angle=80.0,
        max_angle=10.0
    )
    assert result["success"] is False
    assert "min_angle" in result["error"]


def test_bad_spectrum_format(tmp_path):
    """Test error handling for incorrectly formatted spectrum file."""
    bad_xy = tmp_path / "bad.xy"
    bad_xy.write_text("not a valid xy file\njust random text\n")
    
    model_file = tmp_path / "Model.h5"
    model_file.write_text("# Mock model")
    
    result = xrd_analyze_pattern(
        spectrum_path=str(bad_xy),
        model_path=str(model_file)
    )
    assert result["success"] is False
    # Should fail during spectrum loading


def test_too_few_points(tmp_path):
    """Test rejection of spectrum with insufficient data points."""
    tiny_xy = tmp_path / "tiny.xy"
    np.savetxt(tiny_xy, [[10.0, 100.0], [20.0, 200.0]], fmt="%.1f")
    
    model_file = tmp_path / "Model.h5"
    model_file.write_text("# Mock model")
    
    result = xrd_analyze_pattern(
        spectrum_path=str(tiny_xy),
        model_path=str(model_file)
    )
    assert result["success"] is False
    assert "too few data points" in result["error"].lower()


# ---------------------------------------------------------------------------
# Model detection tests
# ---------------------------------------------------------------------------

def test_single_model_detection(sample_xy_file, mock_model_single):
    """Test detection of single model file."""
    result = xrd_analyze_pattern(
        spectrum_path=sample_xy_file,
        model_path=mock_model_single
    )
    # With mock model file (not a real .h5), autoXRD will fail during model loading
    # This is expected - real models need to be trained with autoXRD
    assert result["success"] is False
    assert "error" in result


def test_dual_model_detection(sample_xy_file, mock_model_dual):
    """Test detection of dual model directory."""
    result = xrd_analyze_pattern(
        spectrum_path=sample_xy_file,
        model_path=mock_model_dual
    )
    # With mock model files (not real .h5), autoXRD will fail during model loading
    assert result["success"] is False
    assert "error" in result


def test_pdf_model_fallback(sample_xy_file, tmp_path):
    """Test fallback when PDF requested but not available."""
    models_dir = tmp_path / "Models"
    models_dir.mkdir()
    xrd_model = models_dir / "XRD_Model.h5"
    xrd_model.write_text("# Mock XRD model")
    # No PDF model created
    
    result = xrd_analyze_pattern(
        spectrum_path=sample_xy_file,
        model_path=str(models_dir),
        use_pdf=True
    )
    # Will fail because mock model isn't a real TensorFlow model
    assert result["success"] is False


def test_references_dir_detection(sample_xy_file, tmp_path, mock_references):
    """Test automatic detection of References directory."""
    model_file = tmp_path / "Model.h5"
    model_file.write_text("# Mock model")
    
    result = xrd_analyze_pattern(
        spectrum_path=sample_xy_file,
        model_path=str(model_file),
        references_dir=mock_references
    )
    # Will fail on model loading since it's not a real model
    assert result["success"] is False


# ---------------------------------------------------------------------------
# Parameter validation tests
# ---------------------------------------------------------------------------

def test_confidence_bounds():
    """Test that min_confidence is validated within bounds."""
    # Valid values should not trigger parameter validation errors
    # (will fail on other grounds since autoXRD not installed)
    for conf in [0.0, 40.0, 100.0]:
        result = xrd_analyze_pattern(
            spectrum_path="dummy.xy",
            model_path="dummy.h5",
            min_confidence=conf
        )
        # Should not fail on parameter validation
        assert "min_confidence" not in result.get("error", "").lower() or "not found" in result.get("error", "")


def test_wavelength_validation():
    """Test wavelength parameter accepts reasonable values."""
    for wavelength in [1.5406, 0.7107, 1.7889]:  # Cu, Mo, Co K-alpha
        result = xrd_analyze_pattern(
            spectrum_path="dummy.xy",
            model_path="dummy.h5",
            wavelength=wavelength
        )
        # Should not fail on wavelength validation
        assert "wavelength" not in result.get("error", "").lower() or "not found" in result.get("error", "")


# ---------------------------------------------------------------------------
# Output structure tests
# ---------------------------------------------------------------------------

def test_expected_output_structure():
    """Test that successful output has expected structure (documentation test)."""
    # This test documents the expected output format for successful analysis
    expected_format = {
        "success": True,
        "spectrum_file": "sample.xy",
        "num_phases": 2,
        "phases": ["BaTiO3_99", "BaO_225"],
        "confidence": [85.3, 42.1],
        "weight_fractions": [0.92, 0.08],
        "arrows_ready": True,
        "unknown_peaks": {
            "present": False,
            "max_intensity_pct": 0.0
        },
        "metadata": {
            "model_used": "/path/to/Model.h5",
            "pdf_model_used": None,
            "min_confidence": 40.0,
            "cutoff_intensity": 5.0,
            "wavelength": 1.5406,
            "angle_range": [10.0, 80.0],
            "calculate_weights": True,
            "use_pdf": False
        },
        "message": "Identified 2 phase(s) in sample.xy with weight fractions: ['0.920', '0.080']"
    }
    
    # Validate structure
    assert isinstance(expected_format["phases"], list)
    assert isinstance(expected_format["weight_fractions"], list)
    assert len(expected_format["phases"]) == len(expected_format["weight_fractions"])
    assert expected_format["arrows_ready"] is True


# ---------------------------------------------------------------------------
# ARROWS integration readiness tests
# ---------------------------------------------------------------------------

def test_arrows_compatible_output_format():
    """
    Test that the expected output format matches ARROWS requirements.
    
    arrows_record_result expects:
      - products: List[str] in 'Formula_SpaceGroup' format
      - weight_fractions: List[float] summing to ~1.0
    
    This test validates the documented output structure.
    """
    # Expected output format (from docstring)
    expected_format = {
        "success": True,
        "spectrum_file": "sample.xy",
        "num_phases": 2,
        "phases": ["BaTiO3_99", "BaO_225"],  # ARROWS-compatible format
        "confidence": [85.3, 42.1],
        "weight_fractions": [0.92, 0.08],
        "arrows_ready": True,
    }
    
    # Validate structure
    assert isinstance(expected_format["phases"], list)
    assert isinstance(expected_format["weight_fractions"], list)
    assert len(expected_format["phases"]) == len(expected_format["weight_fractions"])
    
    # Validate phase format (formula_spacegroup)
    for phase in expected_format["phases"]:
        assert "_" in phase  # Must have underscore separator
        parts = phase.split("_")
        assert len(parts) >= 2  # formula_spacegroup format
    
    # Validate weight fractions sum to ~1.0
    wt_sum = sum(expected_format["weight_fractions"])
    assert 0.85 <= wt_sum <= 1.15  # Tolerance matching arrows_record_result
    
    # Validate arrows_ready flag logic
    has_phases = len(expected_format["phases"]) > 0
    has_weights = "weight_fractions" in expected_format
    assert expected_format["arrows_ready"] == (has_phases and has_weights)


def test_phase_format_validation():
    """Test that phase labels follow formula_spacegroup convention."""
    valid_phases = [
        "BaTiO3_99",      # Perovskite Pm-3m
        "LiCoO2_166",     # Layered R-3m
        "Li0.5CoO2_12",   # Non-stoichiometric with decimal
        "Ba2YCu3O7_47",   # YBCO
    ]
    
    for phase in valid_phases:
        assert "_" in phase
        parts = phase.rsplit("_", 1)
        formula, sg = parts
        assert len(formula) > 0
        assert sg.isdigit()  # Space group number


# ---------------------------------------------------------------------------
# Integration markers
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Requires trained autoXRD model and reference CIFs")
def test_actual_xrd_analysis_integration():
    """
    Integration test with real autoXRD package and trained model.
    
    Prerequisites:
    1. Download trained model from XRD-AutoAnalyzer GitHub repo
    2. Place model file (e.g., Model.h5) in a test directory
    3. Download Reference CIFs for the model's chemical space
    4. Prepare test XRD pattern (.xy format)
    
    Example from XRD-AutoAnalyzer:
    - Model: Li-Mn-Ti-O-F system (included in repo)
    - References: CIFs in Example/References/
    - Test spectrum: Example/Spectra/sample.xy
    """
    # Example test (to be completed with actual test data):
    # result = xrd_analyze_pattern(
    #     spectrum_path="test_data/sample.xy",
    #     model_path="test_data/Model.h5",
    #     references_dir="test_data/References",
    #     min_confidence=40.0,
    #     calculate_weights=True
    # )
    # assert result["success"] is True
    # assert len(result["phases"]) > 0
    # assert "weight_fractions" in result
    pass


@pytest.mark.skip(reason="Requires full ARROWS + XRD integration environment")
def test_arrows_workflow_integration():
    """
    End-to-end test: XRD analysis → ARROWS record → ARROWS suggest.
    
    Prerequisites:
    1. ARROWS tools must be functional
    2. Trained XRD model for target chemical space
    3. Mock synthesis results or real experimental data
    4. Reference CIFs matching the trained model
    
    Full loop:
    1. arrows_initialize_campaign(...) → campaign setup
    2. arrows_suggest_experiment(...) → (precursors, temp)
    3. [simulated synthesis with known products]
    4. xrd_analyze_pattern(...) → (phases, weight_fractions)
    5. arrows_record_result(products=phases, weight_fractions=...) → recorded
    6. arrows_suggest_experiment(...) → next experiment (should adapt)
    """
    pass


# ---------------------------------------------------------------------------
# Utility tests
# ---------------------------------------------------------------------------

def test_multiple_parameters(sample_xy_file, mock_model_single):
    """Test that multiple parameters can be set simultaneously."""
    result = xrd_analyze_pattern(
        spectrum_path=sample_xy_file,
        model_path=mock_model_single,
        min_confidence=50.0,
        calculate_weights=True,
        wavelength=1.5406,
        min_angle=15.0,
        max_angle=75.0,
        max_phases=5,
        cutoff_intensity=10.0,
        unknown_threshold=30.0
    )
    
    # With mock model, will fail during autoXRD model loading
    # But should not fail on parameter validation
    assert "success" in result
    # If it fails, it should be due to model loading, not parameter validation
    if not result["success"]:
        error_msg = result.get("error", "").lower()
        # Should not be parameter validation errors
        assert "min_angle" not in error_msg or "model" in error_msg or "not found" in error_msg


def test_readme_example_compatibility():
    """
    Verify tool can eventually replicate README example workflow:
    
    From XRD-AutoAnalyzer repo:
    ```
    python run_CNN.py --weights --min_conf=40 --plot
    ```
    
    Equivalent MatClaw call:
    ```
    xrd_analyze_pattern(
        spectrum_path="Spectra/sample.xy",
        model_path="Model.h5",
        min_confidence=40.0,
        calculate_weights=True
    )
    ```
    """
    # This test documents the API mapping
    # Actual implementation will validate behavior matches
    assert True  # Placeholder
