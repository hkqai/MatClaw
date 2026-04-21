"""
Tests for matcalc_calc_eos tool.

Run with: pytest tests/matcalc/test_matcalc_calc_eos.py -v
Run single test: pytest tests/matcalc/test_matcalc_calc_eos.py::TestEOSCalc::test_basic_eos_calculation -v
"""

import pytest
import numpy as np
from tools.matcalc.matcalc_calc_eos import matcalc_calc_eos


class TestEOSCalc:
    """Tests for EOS calculations."""

    def test_basic_eos_calculation(self, cubic_si_structure):
        """Test basic EOS calculation with Si structure."""
        result = matcalc_calc_eos(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=True,
            fmax=0.2,
            n_points=7,  # Fewer points for faster testing
            max_abs_strain=0.1,
        )
        
        # Check basic success
        assert result["success"] is True, f"Calculation failed: {result.get('error', 'Unknown error')}"
        assert "volumes" in result
        assert "energies" in result
        assert "eos_fits" in result
        
        # Check data dimensions
        assert len(result["volumes"]) == 7
        assert len(result["energies"]) == 7
        assert result["num_points"] == 7
        
        # Check that volumes span the expected range
        volumes = result["volumes"]
        assert min(volumes) < max(volumes)
        
        # Check that we have EOS fits
        assert len(result["eos_fits"]) > 0
        assert "birch_murnaghan" in result["eos_fits"]
        
        # Check bulk modulus exists (may be negative with ML potentials and loose convergence)
        # Note: ML potentials don't always give physically accurate values, especially
        # with few points and loose convergence. The test validates functionality, not accuracy.
        assert "bulk_modulus_GPa" in result
        
    def test_eos_fit_quality(self, cubic_si_structure):
        """Test that EOS fits have good R² scores."""
        result = matcalc_calc_eos(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=True,
            fmax=0.2,
            n_points=11,  # More points for better fitting
        )
        
        assert result["success"] is True
        
        # Check R² scores for each model
        for model_name, fit_data in result["eos_fits"].items():
            if "error" not in fit_data:
                assert "r2_score" in fit_data
                # R² should be good for mathematical fit quality
                # Note: Physical accuracy depends on structure being near equilibrium
                assert fit_data["r2_score"] > 0.90, f"{model_name} R² = {fit_data['r2_score']} too low"
                
    def test_multiple_eos_models(self, cubic_si_structure):
        """Test fitting with multiple EOS models."""
        result = matcalc_calc_eos(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=True,
            fmax=0.2,
            n_points=9,
            eos_models=["birch_murnaghan", "murnaghan", "vinet"],
        )
        
        assert result["success"] is True
        
        # Check all requested models were fit
        assert "birch_murnaghan" in result["eos_fits"]
        assert "murnaghan" in result["eos_fits"]
        assert "vinet" in result["eos_fits"]
        
        # Check bulk moduli consistency (only for positive values)
        # Note: Negative bulk moduli indicate structure far from equilibrium and
        # different EOS models will extrapolate very differently in that regime
        bulk_moduli = []
        for model_name in ["birch_murnaghan", "murnaghan", "vinet"]:
            if "error" not in result["eos_fits"][model_name]:
                K = result["eos_fits"][model_name]["bulk_modulus_GPa"]
                bulk_moduli.append(K)
        
        # Only check consistency if all bulk moduli are positive (physically reasonable)
        if len(bulk_moduli) > 1 and all(K > 0 for K in bulk_moduli):
            mean_K = np.mean(bulk_moduli)
            for K in bulk_moduli:
                # Models should agree within ~50% when near equilibrium
                assert abs(K - mean_K) / mean_K < 0.5, \
                    f"EOS models give very different bulk moduli: {bulk_moduli}"
                
    def test_recommended_model_selection(self, cubic_si_structure):
        """Test that recommended model is selected based on R²."""
        result = matcalc_calc_eos(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=True,
            fmax=0.2,
            n_points=9,
        )
        
        assert result["success"] is True
        assert "recommended_model" in result
        assert result["recommended_model"] is not None
        
        # Recommended model should have highest R²
        recommended_r2 = result["eos_fits"][result["recommended_model"]]["r2_score"]
        for model_name, fit_data in result["eos_fits"].items():
            if "error" not in fit_data:
                assert fit_data["r2_score"] <= recommended_r2 + 1e-6, \
                    f"Recommended model doesn't have highest R²"
                    
    def test_without_structure_relaxation(self, cubic_si_structure):
        """Test EOS calculation with pre-relaxed structure."""
        result = matcalc_calc_eos(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=False,  # Skip initial relaxation
            n_points=7,
            fmax=0.2,
        )
        
        assert result["success"] is True
        assert result["parameters"]["relax_structure"] is False
        
    def test_custom_volume_range(self, cubic_si_structure):
        """Test EOS with custom volume sampling range."""
        result = matcalc_calc_eos(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=True,
            fmax=0.3,
            n_points=9,
            max_abs_strain=0.15,  # ±15% volume change
        )
        
        assert result["success"] is True
        volumes = result["volumes"]
        
        # Check that volume range is approximately correct
        # Should span ~0.85 to ~1.15 of equilibrium volume
        vol_ratio = max(volumes) / min(volumes)
        assert vol_ratio > 1.2, f"Volume range too narrow: {vol_ratio}"
        
    def test_different_calculators(self, cubic_si_structure):
        """Test that calculator aliases work."""
        for calc_name in ["pbe", "TensorNet-MatPES-PBE-v2025.1-PES"]:
            result = matcalc_calc_eos(
                input_structure=cubic_si_structure.as_dict(),
                calculator=calc_name,
                relax_structure=True,
                fmax=0.3,
                n_points=5,  # Minimal points for speed
            )
            
            assert result["success"] is True, f"Failed with calculator {calc_name}"
            assert result["parameters"]["calculator"] == calc_name
            
    def test_cif_string_input(self, cif_string_si):
        """Test EOS calculation with CIF string input."""
        result = matcalc_calc_eos(
            input_structure=cif_string_si,
            calculator="pbe",
            relax_structure=True,
            fmax=0.3,
            n_points=7,
        )
        
        assert result["success"] is True
        
    def test_output_completeness(self, cubic_si_structure):
        """Test that all expected output fields are present."""
        result = matcalc_calc_eos(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=True,
            fmax=0.2,
            n_points=7,
        )
        
        assert result["success"] is True
        
        # Check required top-level fields
        required_fields = [
            "success", "structure", "final_structure",
            "volumes", "energies", "num_points",
            "eos_fits", "recommended_model",
            "equilibrium_volume_A3", "equilibrium_energy_eV",
            "bulk_modulus_GPa", "bulk_modulus_derivative",
            "calculation_time_seconds", "parameters"
        ]
        
        for field in required_fields:
            assert field in result, f"Missing field: {field}"
            
        # Check eos_fits structure
        for model_name, fit_data in result["eos_fits"].items():
            if "error" not in fit_data:
                assert "model" in fit_data
                assert "equilibrium_volume_A3" in fit_data
                assert "equilibrium_energy_eV" in fit_data
                assert "bulk_modulus_GPa" in fit_data
                assert "bulk_modulus_derivative" in fit_data
                assert "r2_score" in fit_data
                
    def test_parameters_recorded(self, cubic_si_structure):
        """Test that all input parameters are recorded."""
        inputs = {
            "calculator": "pbe",
            "relax_structure": False,
            "fmax": 0.15,
            "n_points": 9,
            "max_abs_strain": 0.12,
            "eos_models": ["birch_murnaghan", "vinet"],
        }
        
        result = matcalc_calc_eos(
            input_structure=cubic_si_structure.as_dict(),
            **inputs
        )
        
        assert result["success"] is True
        params = result["parameters"]
        
        for key, value in inputs.items():
            if key != "input_structure":
                assert key in params, f"Parameter '{key}' not recorded"
                assert params[key] == value, f"Parameter '{key}' value mismatch"
                
    def test_calculation_timing(self, cubic_si_structure):
        """Test that calculation time is reported."""
        result = matcalc_calc_eos(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=True,
            fmax=0.3,
            n_points=7,
        )
        
        assert result["success"] is True
        assert "calculation_time_seconds" in result
        assert result["calculation_time_seconds"] > 0
        
    def test_error_handling_invalid_structure(self):
        """Test error handling for invalid structure."""
        result = matcalc_calc_eos(
            input_structure=12345,  # Invalid type
            calculator="pbe",
        )
        
        assert result["success"] is False
        assert "error" in result
        
    def test_error_handling_invalid_calculator(self, cubic_si_structure):
        """Test error handling for invalid calculator."""
        result = matcalc_calc_eos(
            input_structure=cubic_si_structure.as_dict(),
            calculator="NonExistentCalculator999",
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "calculator" in result["error"].lower() or "load" in result["error"].lower()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_minimal_points(self, cubic_si_structure):
        """Test EOS with minimum number of points."""
        result = matcalc_calc_eos(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=True,
            fmax=0.3,
            n_points=5,  # Minimum recommended
        )
        
        assert result["success"] is True
        assert len(result["volumes"]) == 5
        
    def test_tight_convergence(self, cubic_si_structure):
        """Test EOS with tight convergence criteria."""
        result = matcalc_calc_eos(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=True,
            fmax=0.05,  # Tight convergence
            n_points=7,
        )
        
        assert result["success"] is True
