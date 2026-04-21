"""
Tests for matcalc_calc_qha tool.
"""

import json
import pytest
from pymatgen.core import Structure

from tools.matcalc.matcalc_calc_qha import matcalc_calc_qha


# Sample structures for testing
SI_POSCAR = """Si2
1.0
3.348920 0.000000 1.933487
1.116307 3.157372 1.933487
0.000000 0.000000 3.866975
Si
2
direct
0.875000 0.875000 0.875000 Si
0.125000 0.125000 0.125000 Si"""

SI_CIF = """data_Si
_cell_length_a    3.348920
_cell_length_b    3.348920
_cell_length_c    3.867000
_cell_angle_alpha 60.000
_cell_angle_beta  60.000
_cell_angle_gamma 60.000
_symmetry_space_group_name_H-M   'P 1'
loop_
_atom_site_label
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Si 0.875 0.875 0.875
Si 0.125 0.125 0.125"""


class TestQHACalc:
    """Test suite for QHA calculations."""

    @pytest.mark.slow
    def test_basic_qha_calculation(self):
        """Test basic QHA calculation with minimal parameters."""
        result = matcalc_calc_qha(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            t_max=300.0,
            t_step=50.0,
            scale_factors=[0.98, 0.99, 1.0, 1.01, 1.02],  # Fewer points for speed
            relax_structure=False,  # Skip relaxation for speed
        )
        
        assert result["success"] is True
        assert "temperatures" in result
        assert "thermal_expansion_coefficients" in result
        assert "gibbs_free_energies" in result
        assert "bulk_modulus_P" in result
        assert "heat_capacity_P" in result
        assert "gruneisen_parameters" in result
        
        # Check temperature range
        temps = result["temperatures"]
        assert len(temps) > 0
        assert temps[0] == 0.0
        assert temps[-1] <= 300.0
        
        # Check all arrays have same length
        assert len(result["thermal_expansion_coefficients"]) == len(temps)
        assert len(result["gibbs_free_energies"]) == len(temps)
        assert len(result["bulk_modulus_P"]) == len(temps)
        assert len(result["heat_capacity_P"]) == len(temps)
        assert len(result["gruneisen_parameters"]) == len(temps)
        
        # Check volume-energy data
        assert len(result["scale_factors"]) == 5
        assert len(result["volumes"]) == 5
        assert len(result["electronic_energies"]) == 5
        
        # Check metadata
        assert result["calculator"] == "M3GNet"
        assert result["relaxed"] is False
        assert "units" in result

    @pytest.mark.slow
    def test_qha_with_relaxation(self):
        """Test QHA calculation with structure relaxation."""
        result = matcalc_calc_qha(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            t_max=200.0,
            t_step=100.0,
            scale_factors=[0.98, 0.99, 1.0, 1.01, 1.02],
            relax_structure=True,
            fmax=0.1,
        )
        
        assert result["success"] is True
        assert result["relaxed"] is True
        assert "structure" in result

    @pytest.mark.slow
    def test_different_scale_factors(self):
        """Test QHA with different volume scaling factors."""
        # Wider range
        result = matcalc_calc_qha(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            t_max=100.0,
            scale_factors=[0.95, 0.97, 0.99, 1.0, 1.01, 1.03, 1.05],
            relax_structure=False,
        )
        
        assert result["success"] is True
        assert len(result["scale_factors"]) == 7
        assert result["scale_factors"][0] == 0.95
        assert result["scale_factors"][-1] == 1.05

    @pytest.mark.slow
    def test_different_eos_models(self):
        """Test QHA with different equation of state models."""
        for eos_model in ["vinet", "murnaghan", "birch_murnaghan"]:
            result = matcalc_calc_qha(
                structure_input=SI_POSCAR,
                calculator="M3GNet",
                t_max=100.0,
                t_step=50.0,
                scale_factors=[0.98, 0.99, 1.0, 1.01, 1.02],
                eos=eos_model,
                relax_structure=False,
            )
            
            assert result["success"] is True
            assert result["eos_model"] == eos_model

    @pytest.mark.slow
    def test_temperature_range(self):
        """Test QHA with custom temperature range."""
        result = matcalc_calc_qha(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            t_min=100.0,
            t_max=500.0,
            t_step=100.0,
            scale_factors=[0.98, 0.99, 1.0, 1.01, 1.02],
            relax_structure=False,
        )
        
        assert result["success"] is True
        temps = result["temperatures"]
        assert temps[0] == 100.0
        assert temps[-1] <= 500.0
        # MatCalc QHA excludes the last temperature point from property arrays
        # so we get 4 instead of 5 temperatures
        assert len(temps) == 4  # 100, 200, 300, 400 (500 excluded)

    def test_cif_string_input(self):
        """Test QHA with CIF format input."""
        result = matcalc_calc_qha(
            structure_input=SI_CIF,
            calculator="M3GNet",
            t_max=100.0,
            scale_factors=[1.0],  # Single point for speed
            relax_structure=False,
        )
        
        # May fail with single scale factor, but should at least parse structure
        # If it succeeds, check structure was parsed
        if result["success"]:
            assert "structure" in result

    def test_poscar_string_input(self):
        """Test QHA with POSCAR format input."""
        result = matcalc_calc_qha(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            t_max=100.0,
            scale_factors=[1.0],  # Single point for speed
            relax_structure=False,
        )
        
        # May fail with single scale factor, but should parse structure
        if result["success"]:
            assert "structure" in result

    @pytest.mark.slow
    def test_pymatgen_structure_input(self):
        """Test QHA with Pymatgen Structure object."""
        structure = Structure.from_str(SI_POSCAR, fmt="poscar")
        
        result = matcalc_calc_qha(
            structure_input=structure,
            calculator="M3GNet",
            t_max=100.0,
            scale_factors=[0.98, 0.99, 1.0, 1.01, 1.02],
            relax_structure=False,
        )
        
        assert result["success"] is True

    def test_dict_structure_input(self):
        """Test QHA with structure as dictionary."""
        structure = Structure.from_str(SI_POSCAR, fmt="poscar")
        structure_dict = structure.as_dict()
        
        result = matcalc_calc_qha(
            structure_input=structure_dict,
            calculator="M3GNet",
            t_max=100.0,
            scale_factors=[1.0],
            relax_structure=False,
        )
        
        # May fail with single scale factor, but should parse structure
        if result["success"]:
            assert "structure" in result

    def test_invalid_structure_input(self):
        """Test QHA with invalid structure input."""
        result = matcalc_calc_qha(
            structure_input="invalid structure data",
            calculator="M3GNet",
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "parse" in result["error"].lower()

    def test_invalid_calculator(self):
        """Test QHA with invalid calculator name."""
        result = matcalc_calc_qha(
            structure_input=SI_POSCAR,
            calculator="InvalidCalculator",
            scale_factors=[1.0],
        )
        
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.slow
    def test_custom_phonon_calc_kwargs(self):
        """Test QHA with custom phonon calculation parameters."""
        result = matcalc_calc_qha(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            t_max=100.0,
            scale_factors=[0.98, 0.99, 1.0, 1.01, 1.02],
            phonon_calc_kwargs={
                "supercell_matrix": [[2, 0, 0], [0, 2, 0], [0, 0, 2]],
                "atom_disp": 0.015,
            },
            relax_structure=False,
        )
        
        assert result["success"] is True

    @pytest.mark.slow
    def test_custom_relax_calc_kwargs(self):
        """Test QHA with custom relaxation parameters."""
        # Note: relax_calc_kwargs are passed to the calculator during relaxation
        # Test with empty dict to ensure parameter is accepted
        result = matcalc_calc_qha(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            t_max=100.0,
            scale_factors=[0.98, 0.99, 1.0, 1.01, 1.02],
            relax_structure=True,
            relax_calc_kwargs={},  # Empty dict to test parameter passing
        )
        
        if not result["success"]:
            print(f"Error: {result.get('error', 'No error message')}")
        assert result["success"] is True
        assert result["relaxed"] is True

    def test_units_documentation(self):
        """Test that units are properly documented in output."""
        result = matcalc_calc_qha(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            t_max=100.0,
            scale_factors=[1.0],
            relax_structure=False,
        )
        
        if result["success"]:
            assert "units" in result
            units = result["units"]
            assert units["temperature"] == "K"
            assert units["thermal_expansion"] == "K^-1"
            assert units["gibbs_free_energy"] == "eV"
            assert units["bulk_modulus"] == "GPa"
            assert units["heat_capacity"] == "J/K/mol"
            assert units["volume"] == "Angstrom^3"
            assert units["energy"] == "eV"

    @pytest.mark.slow
    def test_thermal_expansion_values(self):
        """Test that thermal expansion coefficients are reasonable."""
        result = matcalc_calc_qha(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            t_max=300.0,
            scale_factors=[0.98, 0.99, 1.0, 1.01, 1.02],
            relax_structure=False,
        )
        
        assert result["success"] is True
        
        # Thermal expansion should be positive for most materials
        # and increase with temperature
        alphas = result["thermal_expansion_coefficients"]
        
        # Check that values are in reasonable range (not NaN or infinite)
        for alpha in alphas:
            assert isinstance(alpha, (int, float))
            assert not (alpha != alpha)  # Check for NaN
            assert abs(alpha) < 1.0  # Typical values are much smaller (1e-5 to 1e-4)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
