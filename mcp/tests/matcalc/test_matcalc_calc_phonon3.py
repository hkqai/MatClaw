"""
Tests for matcalc_calc_phonon3 tool.

Run with: pytest tests/matcalc/test_matcalc_calc_phonon3.py -v
Run single test: pytest tests/matcalc/test_matcalc_calc_phonon3.py::TestPhonon3Calc::test_basic_phonon3_calculation -v

Note: These tests are slower than regular phonon tests due to third-order force constant calculations.
"""

import pytest
import numpy as np
from tools.matcalc.matcalc_calc_phonon3 import matcalc_calc_phonon3


class TestPhonon3Calc:
    """Tests for thermal conductivity calculations using phonon3."""

    def test_basic_phonon3_calculation(self, cubic_si_structure):
        """Test basic phonon3 calculation with Si structure."""
        result = matcalc_calc_phonon3(
            structure_input=cubic_si_structure.as_dict(),
            calculator="pbe",
            fc2_supercell=[2, 2, 2],
            fc3_supercell=[2, 2, 2],
            mesh_numbers=[10, 10, 10],  # Small mesh for faster testing
            t_min=100.0,
            t_max=300.0,
            t_step=100.0,
            relax_structure=False,  # Skip relaxation for faster testing
        )
        
        # Check basic success
        assert result["success"] is True, f"Calculation failed: {result.get('error', 'Unknown error')}"
        
        # Check thermal conductivity structure
        assert "thermal_conductivity" in result
        assert "temperatures" in result
        
        kappa = result["thermal_conductivity"]
        temps = result["temperatures"]
        
        # Check temperature array
        assert len(temps) > 0
        assert min(temps) >= 100.0
        assert max(temps) <= 300.0
        
        # Check arrays have same length
        assert len(kappa) == len(temps)
        
        # Check thermal conductivity values (should be positive or None)
        for k in kappa:
            if k is not None:
                assert k >= 0, f"Thermal conductivity should be non-negative, got {k}"
        
    def test_phonon3_with_relaxation(self, cubic_si_structure):
        """Test phonon3 calculation with structure relaxation."""
        result = matcalc_calc_phonon3(
            structure_input=cubic_si_structure.as_dict(),
            calculator="pbe",
            fc2_supercell=[2, 2, 2],
            fc3_supercell=[2, 2, 2],
            mesh_numbers=[8, 8, 8],
            t_min=200.0,
            t_max=400.0,
            t_step=200.0,
            relax_structure=True,
            fmax=0.3,
        )
        
        assert result["success"] is True
        assert result["relaxed"] is True
        assert "structure" in result
        
    def test_different_supercells(self, cubic_si_structure):
        """Test with different fc2 and fc3 supercells."""
        result = matcalc_calc_phonon3(
            structure_input=cubic_si_structure.as_dict(),
            calculator="pbe",
            fc2_supercell=[2, 2, 2],
            fc3_supercell=[2, 2, 2],  # Can be different from fc2
            mesh_numbers=[8, 8, 8],
            t_max=200.0,
            t_step=100.0,
            relax_structure=False,
        )
        
        assert result["success"] is True
        assert result["parameters"]["fc2_supercell"] == [[2, 0, 0], [0, 2, 0], [0, 0, 2]]
        assert result["parameters"]["fc3_supercell"] == [[2, 0, 0], [0, 2, 0], [0, 0, 2]]
        
    def test_mesh_density(self, cubic_si_structure):
        """Test different mesh densities."""
        meshes = [[8, 8, 8], [10, 10, 10]]
        
        for mesh in meshes:
            result = matcalc_calc_phonon3(
                structure_input=cubic_si_structure.as_dict(),
                calculator="pbe",
                fc2_supercell=[2, 2, 2],
                fc3_supercell=[2, 2, 2],
                mesh_numbers=mesh,
                t_max=200.0,
                relax_structure=False,
            )
            assert result["success"] is True, f"Failed with mesh {mesh}: {result.get('error')}"
            assert result["parameters"]["mesh_numbers"] == mesh
            
    def test_temperature_range(self, cubic_si_structure):
        """Test different temperature ranges."""
        result = matcalc_calc_phonon3(
            structure_input=cubic_si_structure.as_dict(),
            calculator="pbe",
            fc2_supercell=[2, 2, 2],
            fc3_supercell=[2, 2, 2],
            mesh_numbers=[8, 8, 8],
            t_min=200.0,
            t_max=600.0,
            t_step=200.0,
            relax_structure=False,
        )
        
        assert result["success"] is True
        
        temps = result["temperatures"]
        assert min(temps) >= 200.0
        assert max(temps) <= 600.0
        
    def test_cif_string_input(self, cubic_si_structure):
        """Test phonon3 calculation with CIF string input."""
        # Generate CIF string
        cif_str = cubic_si_structure.to(fmt="cif")
        
        result = matcalc_calc_phonon3(
            structure_input=cif_str,
            calculator="pbe",
            fc2_supercell=[2, 2, 2],
            fc3_supercell=[2, 2, 2],
            mesh_numbers=[8, 8, 8],
            t_max=200.0,
            relax_structure=False,
        )
        
        assert result["success"] is True
        
    def test_poscar_string_input(self, cubic_si_structure):
        """Test phonon3 calculation with POSCAR string input."""
        # Generate POSCAR string
        poscar_str = cubic_si_structure.to(fmt="poscar")
        
        result = matcalc_calc_phonon3(
            structure_input=poscar_str,
            calculator="pbe",
            fc2_supercell=[2, 2, 2],
            fc3_supercell=[2, 2, 2],
            mesh_numbers=[8, 8, 8],
            t_max=200.0,
            relax_structure=False,
        )
        
        assert result["success"] is True
        
    def test_invalid_structure_input(self):
        """Test error handling for invalid structure input."""
        result = matcalc_calc_phonon3(
            structure_input="invalid structure",
            calculator="pbe",
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "parse" in result["error"].lower()
        
    def test_invalid_calculator(self, cubic_si_structure):
        """Test error handling for invalid calculator."""
        result = matcalc_calc_phonon3(
            structure_input=cubic_si_structure.as_dict(),
            calculator="invalid_calculator_xyz",
            fc2_supercell=[2, 2, 2],
        )
        
        assert result["success"] is False
        assert "error" in result
        
    def test_units_documentation(self, cubic_si_structure):
        """Test that units are properly documented in output."""
        result = matcalc_calc_phonon3(
            structure_input=cubic_si_structure.as_dict(),
            calculator="pbe",
            fc2_supercell=[2, 2, 2],
            fc3_supercell=[2, 2, 2],
            mesh_numbers=[8, 8, 8],
            t_max=200.0,
            relax_structure=False,
        )
        
        assert result["success"] is True
        assert "units" in result
        
        units = result["units"]
        assert units["temperature"] == "K"
        assert units["thermal_conductivity"] == "W/m·K"
        
    def test_supercell_format_conversion(self, cubic_si_structure):
        """Test conversion of [a,b,c] format to matrix format."""
        result = matcalc_calc_phonon3(
            structure_input=cubic_si_structure.as_dict(),
            calculator="pbe",
            fc2_supercell=[2, 2, 2],  # Simple list format
            fc3_supercell=[[2, 0, 0], [0, 2, 0], [0, 0, 2]],  # Matrix format
            mesh_numbers=[8, 8, 8],
            t_max=200.0,
            relax_structure=False,
        )
        
        assert result["success"] is True
        # Both should be converted to matrix format
        assert result["parameters"]["fc2_supercell"] == [[2, 0, 0], [0, 2, 0], [0, 0, 2]]
        assert result["parameters"]["fc3_supercell"] == [[2, 0, 0], [0, 2, 0], [0, 0, 2]]
        
    def test_pymatgen_structure_input(self, cubic_si_structure):
        """Test phonon3 calculation with pymatgen Structure object."""
        result = matcalc_calc_phonon3(
            structure_input=cubic_si_structure,
            calculator="pbe",
            fc2_supercell=[2, 2, 2],
            fc3_supercell=[2, 2, 2],
            mesh_numbers=[8, 8, 8],
            t_max=200.0,
            relax_structure=False,
        )
        
        assert result["success"] is True
        
    def test_nan_handling(self, cubic_si_structure):
        """Test that NaN values in thermal conductivity are handled gracefully."""
        result = matcalc_calc_phonon3(
            structure_input=cubic_si_structure.as_dict(),
            calculator="pbe",
            fc2_supercell=[2, 2, 2],
            fc3_supercell=[2, 2, 2],
            mesh_numbers=[8, 8, 8],
            t_max=200.0,
            relax_structure=False,
        )
        
        assert result["success"] is True
        
        # Check that NaN values are converted to None
        kappa = result["thermal_conductivity"]
        for k in kappa:
            assert k is None or isinstance(k, (int, float))
            if k is not None:
                assert not np.isnan(k)
