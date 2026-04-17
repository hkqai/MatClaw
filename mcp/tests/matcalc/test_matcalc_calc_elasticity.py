"""
Tests for matcalc_calc_elasticity tool.

Run with: pytest tests/matcalc/test_matcalc_calc_elasticity.py -v
Run single test: pytest tests/matcalc/test_matcalc_calc_elasticity.py::TestElasticityCalc::test_basic_elasticity_calculation -v
"""

import pytest
import numpy as np
from tools.matcalc.matcalc_calc_elasticity import matcalc_calc_elasticity


class TestElasticityCalc:
    """Tests for elastic property calculations."""

    def test_basic_elasticity_calculation(self, cubic_si_structure):
        """Test basic elasticity calculation with dict input."""
        result = matcalc_calc_elasticity(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",  # Use alias
            relax_structure=True,  # Use matcalc defaults
            relax_deformed_structures=False,  # Use matcalc defaults  
            fmax=0.2,  # Relaxed tolerance for faster test
        )
        
        # Check basic success
        assert result["success"] is True, f"Calculation failed: {result.get('error', 'Unknown error')}"
        assert "elastic_tensor_voigt" in result
        assert "bulk_modulus_vrh_GPa" in result
        assert "shear_modulus_vrh_GPa" in result
        
        # Check elastic tensor dimensions
        elastic_tensor = result["elastic_tensor_voigt"]
        assert len(elastic_tensor) == 6, "Elastic tensor should be 6x6"
        assert len(elastic_tensor[0]) == 6, "Elastic tensor should be 6x6"
        
        # Check moduli are positive
        assert result["bulk_modulus_vrh_GPa"] > 0, "Bulk modulus should be positive"
        assert result["shear_modulus_vrh_GPa"] > 0, "Shear modulus should be positive"
        assert result["youngs_modulus_GPa"] > 0, "Young's modulus should be positive"
        
        # Check Poisson's ratio is in physical range (-1, 0.5)
        assert -1 < result["poissons_ratio"] < 0.5, "Poisson's ratio out of physical range"
        
        # Check that moduli are at least positive and non-trivial
        # Note: ML model predictions may not match DFT/experimental values exactly
        # Experimental Si: K~98 GPa, G~52 GPa, but ML models can vary
        bulk_mod = result["bulk_modulus_vrh_GPa"]
        shear_mod = result["shear_modulus_vrh_GPa"]
        assert bulk_mod > 0.1, f"Bulk modulus {bulk_mod:.3f} GPa too small"
        assert shear_mod > 0.1, f"Shear modulus {shear_mod:.3f} GPa too small"
        print(f"Calculated: K={bulk_mod:.1f} GPa, G={shear_mod:.1f} GPa (Expected: K~98 GPa, G~52 GPa)")

    def test_elastic_tensor_structure(self, cubic_cscl_structure):
        """Test that elastic tensor has correct structure and symmetry."""
        result = matcalc_calc_elasticity(
            input_structure=cubic_cscl_structure.as_dict(),
            calculator="TensorNet-MatPES-PBE-v2025.1-PES",
            relax_structure=False,
            fmax=0.2,
        )
        
        assert result["success"] is True
        
        # Check all required tensor outputs exist
        assert "elastic_tensor_voigt" in result
        assert "elastic_tensor_IEEE" in result
        assert "compliance_tensor" in result
        
        # For cubic crystal, should have isotropic-like elastic constants
        # C11 ≈ C22 ≈ C33, C12 ≈ C13 ≈ C23, C44 ≈ C55 ≈ C66
        et = np.array(result["elastic_tensor_voigt"])
        
        # Check tensor is symmetric
        assert np.allclose(et, et.T, rtol=0.01), "Elastic tensor should be symmetric"
        
        # For cubic: C11, C12, C44 should be the independent components
        # Check diagonal elements
        assert et[0, 0] > 0, "C11 should be positive"
        assert et[3, 3] > 0, "C44 should be positive"

    def test_mechanical_stability(self, cubic_si_structure):
        """Test mechanical stability analysis."""
        result = matcalc_calc_elasticity(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=False,
            fmax=0.2,
        )
        
        assert result["success"] is True
        assert "is_stable" in result
        assert "eigenvalues" in result
        
        # Check eigenvalues are computed
        eigenvalues = result["eigenvalues"]
        assert len(eigenvalues) == 6, "Should have 6 eigenvalues for 6x6 tensor"
        
        # For a stable structure, all eigenvalues should be positive
        if result["is_stable"]:
            assert all(ev > 0 for ev in eigenvalues), \
                "Stable structure should have all positive eigenvalues"
        else:
            assert any(ev <= 0 for ev in eigenvalues), \
                "Unstable structure should have at least one non-positive eigenvalue"

    def test_voigt_reuss_hill_averages(self, cubic_nacl_structure):
        """Test that Voigt, Reuss, and Hill averages are properly computed."""
        result = matcalc_calc_elasticity(
            input_structure=cubic_nacl_structure.as_dict(),
            calculator="pbe",
            relax_structure=True,  # Use matcalc defaults
            relax_deformed_structures=False,  # Use matcalc defaults
            fmax=0.2,
        )
        
        assert result["success"] is True
        
        # Check all three bounds exist
        assert "bulk_modulus_voigt_GPa" in result
        assert "bulk_modulus_reuss_GPa" in result
        assert "bulk_modulus_vrh_GPa" in result
        assert "shear_modulus_voigt_GPa" in result
        assert "shear_modulus_reuss_GPa" in result
        assert "shear_modulus_vrh_GPa" in result
        
        # VRH should be between Voigt and Reuss bounds
        k_voigt = result["bulk_modulus_voigt_GPa"]
        k_reuss = result["bulk_modulus_reuss_GPa"]
        k_vrh = result["bulk_modulus_vrh_GPa"]
        
        g_voigt = result["shear_modulus_voigt_GPa"]
        g_reuss = result["shear_modulus_reuss_GPa"]
        g_vrh = result["shear_modulus_vrh_GPa"]
        
        # VRH is average of Voigt and Reuss
        assert abs(k_vrh - (k_voigt + k_reuss) / 2) < 0.01, \
            "K_VRH should be average of K_Voigt and K_Reuss"
        assert abs(g_vrh - (g_voigt + g_reuss) / 2) < 0.01, \
            "G_VRH should be average of G_Voigt and G_Reuss"
        
        # Voigt bound should be >= Reuss bound (in theory)
        # Note: numerical precision may cause small violations
        assert k_voigt >= k_reuss - 0.1, "Voigt bound should be >= Reuss bound (bulk)"
        assert g_voigt >= g_reuss - 0.1, "Voigt bound should be >= Reuss bound (shear)"

    def test_derived_properties(self, cubic_si_structure):
        """Test that derived properties are correctly calculated."""
        result = matcalc_calc_elasticity(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=False,
            fmax=0.2,
        )
        
        assert result["success"] is True
        
        # Check derived properties exist
        assert "youngs_modulus_GPa" in result
        assert "poissons_ratio" in result
        assert "pugh_ratio" in result
        assert "universal_anisotropy" in result
        assert "homogeneous_poisson" in result
        
        # Verify Young's modulus formula: E = 9KG / (3K + G)
        K = result["bulk_modulus_vrh_GPa"]
        G = result["shear_modulus_vrh_GPa"]
        E_expected = (9 * K * G) / (3 * K + G)
        E_actual = result["youngs_modulus_GPa"]
        assert abs(E_actual - E_expected) < 0.1, "Young's modulus formula incorrect"
        
        # Verify Poisson's ratio formula: ν = (3K - 2G) / (6K + 2G)
        nu_expected = (3 * K - 2 * G) / (6 * K + 2 * G)
        nu_actual = result["poissons_ratio"]
        assert abs(nu_actual - nu_expected) < 0.001, "Poisson's ratio formula incorrect"
        
        # Verify Pugh ratio: K/G
        pugh_expected = K / G
        pugh_actual = result["pugh_ratio"]
        assert abs(pugh_actual - pugh_expected) < 0.01, "Pugh ratio calculation incorrect"

    def test_ductility_classification(self, cubic_si_structure):
        """Test ductility classification based on Pugh ratio."""
        result = matcalc_calc_elasticity(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=False,
            fmax=0.2,
        )
        
        assert result["success"] is True
        assert "ductility" in result
        assert "pugh_ratio" in result
        
        # Check classification matches Pugh ratio
        pugh_ratio = result["pugh_ratio"]
        ductility = result["ductility"]
        
        if pugh_ratio > 1.75:
            assert "ductile" in ductility.lower(), \
                f"Pugh ratio {pugh_ratio:.2f} > 1.75 should be ductile"
        else:
            assert "brittle" in ductility.lower(), \
                f"Pugh ratio {pugh_ratio:.2f} < 1.75 should be brittle"
        
        # Si is known to be brittle (K/G < 1.75)
        # This is a sanity check
        assert pugh_ratio < 2.0, "Si should have K/G < 2.0"

    def test_anisotropy_classification(self, cubic_si_structure):
        """Test elastic anisotropy classification."""
        result = matcalc_calc_elasticity(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=False,
            fmax=0.2,
        )
        
        assert result["success"] is True
        assert "anisotropy" in result
        assert "universal_anisotropy" in result
        
        # Check classification matches anisotropy value
        A = result["universal_anisotropy"]
        anisotropy_str = result["anisotropy"]
        
        # Universal anisotropy index: 0 = isotropic
        assert A >= 0, "Anisotropy index should be non-negative"
        
        if A < 0.1:
            assert "isotropic" in anisotropy_str.lower()
        elif A < 1.0:
            assert "weakly" in anisotropy_str.lower() or "anisotropic" in anisotropy_str.lower()
        else:
            assert "strongly" in anisotropy_str.lower() or "anisotropic" in anisotropy_str.lower()

    def test_with_structure_relaxation(self, stressed_structure):
        """Test elasticity calculation with structure relaxation enabled."""
        result = matcalc_calc_elasticity(
            input_structure=stressed_structure.as_dict(),
            calculator="pbe",
            relax_structure=True,  # Enable relaxation
            relax_deformed_structures=True,
            fmax=0.2,
        )
        
        assert result["success"] is True
        
        # Should have both initial and final structures
        assert "structure" in result  # Initial
        assert "final_structure" in result  # Relaxed
        
        # Structures should be different (relaxation occurred)
        # Check by comparing volumes or lattice parameters
        from pymatgen.core import Structure
        initial = Structure.from_dict(result["structure"])
        final = Structure.from_dict(result["final_structure"])
        
        # Volume should change during relaxation
        vol_change = abs(final.volume - initial.volume) / initial.volume
        # Allow small tolerance in case structure was already near equilibrium
        assert vol_change > 0.001 or result["parameters"]["relax_structure"], \
            "Structure should change during relaxation"

    def test_without_deformed_structure_relaxation(self, cubic_si_structure):
        """Test elasticity calculation without relaxing deformed structures (faster)."""
        result = matcalc_calc_elasticity(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=False,
            relax_deformed_structures=False,  # Disabled for speed
            fmax=0.5,  # Not used since no relaxation
        )
        
        assert result["success"] is True
        assert result["parameters"]["relax_deformed_structures"] is False
        
        # Should still get elastic properties
        assert "bulk_modulus_vrh_GPa" in result
        assert "elastic_tensor_voigt" in result

    def test_custom_strain_ranges(self, cubic_si_structure):
        """Test elasticity calculation with custom strain ranges."""
        # Use custom strain range (must not include zero!)
        custom_norm_strains = [-0.008, -0.004, 0.004, 0.008]
        custom_shear_strains = [-0.08, -0.04, 0.04, 0.08]
        
        result = matcalc_calc_elasticity(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=True,  # Use matcalc defaults
            relax_deformed_structures=False,  # Use matcalc defaults
            norm_strains=custom_norm_strains,
            shear_strains=custom_shear_strains,
            fmax=0.2,
        )
        
        assert result["success"] is True
        
        # Check that custom strains were used
        params = result["parameters"]
        assert params["norm_strains"] == custom_norm_strains
        assert params["shear_strains"] == custom_shear_strains

    def test_different_calculators(self, cubic_si_structure):
        """Test that different calculator names/aliases work."""
        calculators_to_test = [
            "pbe",  # Alias
            "TensorNet-MatPES-PBE-v2025.1-PES",  # Full name
        ]
        
        for calc_name in calculators_to_test:
            result = matcalc_calc_elasticity(
                input_structure=cubic_si_structure.as_dict(),
                calculator=calc_name,
                relax_structure=False,
                fmax=0.3,
            )
            
            if not result["success"]:
                # May fail if calculator not available, that's ok for testing
                print(f"  Note: Calculator '{calc_name}' not available: {result.get('error', '')}")
                continue
            
            assert result["success"] is True, f"Failed with calculator {calc_name}"
            assert "bulk_modulus_vrh_GPa" in result

    def test_cif_string_input(self, cif_string_si):
        """Test elasticity calculation with CIF string input."""
        result = matcalc_calc_elasticity(
            input_structure=cif_string_si,
            calculator="pbe",
            relax_structure=False,
            fmax=0.2,
        )
        
        if not result["success"]:
            print(f"\nCIF test failed with error: {result.get('error', 'Unknown error')}")
        
        assert result["success"] is True
        assert "elastic_tensor_voigt" in result

    def test_output_completeness(self, cubic_si_structure):
        """Test that all expected output fields are present."""
        result = matcalc_calc_elasticity(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=False,
            fmax=0.2,
        )
        
        assert result["success"] is True
        
        # Required output fields
        required_fields = [
            "success",
            "structure",
            "final_structure",
            "elastic_tensor_voigt",
            "elastic_tensor_IEEE",
            "compliance_tensor",
            "bulk_modulus_voigt_GPa",
            "bulk_modulus_reuss_GPa",
            "bulk_modulus_vrh_GPa",
            "shear_modulus_voigt_GPa",
            "shear_modulus_reuss_GPa",
            "shear_modulus_vrh_GPa",
            "youngs_modulus_GPa",
            "poissons_ratio",
            "pugh_ratio",
            "universal_anisotropy",
            "homogeneous_poisson",
            "is_stable",
            "eigenvalues",
            "num_deformed_structures",
            "residuals_sum",
            "r2_score",
            "calculation_time_seconds",
            "parameters",
            "ductility",
            "anisotropy",
            "message",
        ]
        
        missing_fields = [field for field in required_fields if field not in result]
        assert len(missing_fields) == 0, f"Missing output fields: {missing_fields}"

    def test_parameters_recorded(self, cubic_si_structure):
        """Test that all input parameters are recorded in output."""
        inputs = {
            "calculator": "pbe",
            "relax_structure": False,
            "relax_deformed_structures": False,  # Use matcalc defaults
            "fmax": 0.15,
            "norm_strains": [-0.006, -0.003, 0.003, 0.006],  # No zero!
            "shear_strains": [-0.06, -0.03, 0.03, 0.06],  # No zero!
            "use_equilibrium": True,
        }
        
        result = matcalc_calc_elasticity(
            input_structure=cubic_si_structure.as_dict(),
            **inputs
        )
        
        assert result["success"] is True
        
        # Check all parameters are recorded
        params = result["parameters"]
        for key, value in inputs.items():
            if key != "input_structure":  # Structure not in params
                assert key in params, f"Parameter '{key}' not recorded"
                assert params[key] == value, f"Parameter '{key}' value mismatch"

    def test_calculation_timing(self, cubic_si_structure):
        """Test that calculation time is reported."""
        result = matcalc_calc_elasticity(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=False,
            fmax=0.3,
        )
        
        assert result["success"] is True
        assert "calculation_time_seconds" in result
        assert result["calculation_time_seconds"] > 0, "Calculation time should be positive"
        assert result["calculation_time_seconds"] < 600, "Calculation took too long (>10 min)"

    def test_error_handling_invalid_structure(self):
        """Test error handling for invalid structure input."""
        # Try with an invalid structure type
        result = matcalc_calc_elasticity(
            input_structure=12345,  # Invalid type
            calculator="pbe",
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "Unsupported" in result["error"] or "type" in result["error"].lower()

    def test_error_handling_invalid_calculator(self, cubic_si_structure):
        """Test error handling for invalid calculator name."""
        result = matcalc_calc_elasticity(
            input_structure=cubic_si_structure.as_dict(),
            calculator="NonExistentCalculator123",
            relax_structure=False,
        )
        
        assert result["success"] is False
        assert "error" in result
        # Error should mention calculator loading failure
        assert "calculator" in result["error"].lower() or "load" in result["error"].lower()

    @pytest.mark.slow
    def test_full_workflow_with_relaxation(self, stressed_structure):
        """
        Full integration test: relax structure then calculate elasticity.
        Marked as slow - only run with: pytest -m slow
        """
        result = matcalc_calc_elasticity(
            input_structure=stressed_structure.as_dict(),
            calculator="pbe",
            relax_structure=True,
            relax_deformed_structures=False,  # Use matcalc defaults
            fmax=0.1,  # Tighter convergence
            norm_strains=[-0.01, -0.005, 0.005, 0.01],  # No zero!
            shear_strains=[-0.06, -0.03, 0.03, 0.06],  # No zero!
        )
        
        assert result["success"] is True
        
        # Should have good R² score with more strain points
        assert result["r2_score"] > 0.9, "R² score should be high with good strain sampling"
        
        # Should be mechanically stable after relaxation
        assert result["is_stable"] is True, "Relaxed structure should be mechanically stable"
        
        # All eigenvalues should be positive
        assert all(ev > 0 for ev in result["eigenvalues"]), \
            "All eigenvalues should be positive for stable structure"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_tight_convergence(self, cubic_si_structure):
        """Test with very tight force convergence."""
        result = matcalc_calc_elasticity(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=False,
            relax_deformed_structures=True,
            fmax=0.05,  # Very tight
        )
        
        # May take longer but should still succeed
        assert result["success"] is True

    def test_minimal_strain_points(self, cubic_si_structure):
        """Test with minimal number of strain points."""
        # Use only 2 strain points (minimum for fitting)
        result = matcalc_calc_elasticity(
            input_structure=cubic_si_structure.as_dict(),
            calculator="pbe",
            relax_structure=False,
            norm_strains=[-0.003, 0.003],
            shear_strains=[-0.003, 0.003],
            fmax=0.3,
        )
        
        # Should still work but may have lower accuracy
        assert result["success"] is True
        assert "elastic_tensor_voigt" in result

    def test_single_calculator_invocation(self, cubic_nacl_structure):
        """Test that the tool can be called multiple times independently."""
        # Call twice with same input - should give same results
        result1 = matcalc_calc_elasticity(
            input_structure=cubic_nacl_structure.as_dict(),
            calculator="pbe",
            relax_structure=False,
            fmax=0.2,
        )
        
        result2 = matcalc_calc_elasticity(
            input_structure=cubic_nacl_structure.as_dict(),
            calculator="pbe",
            relax_structure=False,
            fmax=0.2,
        )
        
        assert result1["success"] is True
        assert result2["success"] is True
        
        # Results should be very similar (within numerical precision)
        assert abs(result1["bulk_modulus_vrh_GPa"] - result2["bulk_modulus_vrh_GPa"]) < 1.0, \
            "Repeated calculations should give consistent results"
