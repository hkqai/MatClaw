"""
Tests for matcalc_calc_phonon tool.
Run with: pytest tests/matcalc/test_matcalc_calc_phonon.py -v
Run single test: pytest tests/matcalc/test_matcalc_calc_phonon.py::TestPhononCalc::test_basic_phonon_calculation -v"""

import pytest
import numpy as np
from tools.matcalc.matcalc_calc_phonon import matcalc_calc_phonon


class TestPhononCalc:
    """Tests for phonon calculations."""

    def test_basic_phonon_calculation(self, cubic_si_structure):
        """Test basic phonon calculation with Si structure."""
        result = matcalc_calc_phonon(
            structure_input=cubic_si_structure.as_dict(),
            calculator="pbe",
            supercell_matrix=[2, 2, 2],
            t_min=0.0,
            t_max=500.0,
            t_step=50.0,
            relax_structure=False,  # Skip relaxation for faster testing
        )
        
        # Check basic success
        assert result["success"] is True, f"Calculation failed: {result.get('error', 'Unknown error')}"
        
        # Check thermal properties structure
        assert "thermal_properties" in result
        thermal = result["thermal_properties"]
        assert "temperatures" in thermal
        assert "free_energy" in thermal
        assert "entropy" in thermal
        assert "heat_capacity" in thermal
        
        # Check temperature array
        temps = thermal["temperatures"]
        assert len(temps) > 0
        assert min(temps) >= 0.0
        assert max(temps) <= 500.0
        
        # Check all arrays have same length
        assert len(thermal["free_energy"]) == len(temps)
        assert len(thermal["entropy"]) == len(temps)
        assert len(thermal["heat_capacity"]) == len(temps)
        
        # Check stability analysis
        assert "stability" in result
        assert "is_stable" in result["stability"]
        assert "num_imaginary_modes" in result["stability"]
        
        # Check Debye temperature
        assert "debye_temperature" in result
        if result["debye_temperature"] is not None:
            assert result["debye_temperature"] > 0
            
    def test_phonon_with_relaxation(self, cubic_si_structure):
        """Test phonon calculation with structure relaxation."""
        result = matcalc_calc_phonon(
            structure_input=cubic_si_structure.as_dict(),
            calculator="pbe",
            supercell_matrix=[2, 2, 2],
            t_max=300.0,
            t_step=100.0,
            relax_structure=True,
            fmax=0.3,
        )
        
        assert result["success"] is True
        assert result["relaxed"] is True
        assert "structure" in result
        
    def test_thermodynamic_trends(self, cubic_si_structure):
        """Test that thermodynamic properties follow expected trends."""
        result = matcalc_calc_phonon(
            structure_input=cubic_si_structure.as_dict(),
            calculator="pbe",
            supercell_matrix=[2, 2, 2],
            t_min=10.0,  # Start above 0 to avoid quantum effects
            t_max=500.0,
            t_step=50.0,
            relax_structure=False,
        )
        
        assert result["success"] is True
        
        thermal = result["thermal_properties"]
        temps = np.array(thermal["temperatures"])
        entropy = np.array(thermal["entropy"])
        cv = np.array(thermal["heat_capacity"])
        
        # Entropy should generally increase with temperature
        # (allow some noise at low T due to numerical effects)
        if len(temps) > 2:
            # Check that entropy increases from low to high T
            assert entropy[-1] > entropy[0], "Entropy should increase with temperature"
        
        # Heat capacity should be positive and generally increase with T
        assert all(cv >= 0), "Heat capacity should be non-negative"
        
    def test_different_calculators(self, cubic_si_structure):
        """Test phonon calculation with different ML potentials."""
        calculators = ["pbe", "r2scan"]  # Use reliable calculators
        
        results = {}
        for calc in calculators:
            result = matcalc_calc_phonon(
                structure_input=cubic_si_structure.as_dict(),
                calculator=calc,
                supercell_matrix=[2, 2, 2],
                t_max=300.0,
                t_step=100.0,
                relax_structure=False,
            )
            results[calc] = result
            assert result["success"] is True, f"Failed with {calc}: {result.get('error')}"
            
        # Both should return valid results
        for calc in calculators:
            assert "debye_temperature" in results[calc]
            assert "thermal_properties" in results[calc]
            
    def test_supercell_sizes(self, cubic_si_structure):
        """Test different supercell sizes."""
        supercells = [
            [2, 2, 2],
            [3, 3, 3],
            [[2, 0, 0], [0, 2, 0], [0, 0, 2]],  # Matrix format
        ]
        
        for sc in supercells:
            result = matcalc_calc_phonon(
                structure_input=cubic_si_structure.as_dict(),
                calculator="pbe",
                supercell_matrix=sc,
                t_max=300.0,
                relax_structure=False,
            )
            assert result["success"] is True, f"Failed with supercell {sc}: {result.get('error')}"
            
    def test_temperature_range(self, cubic_si_structure):
        """Test different temperature ranges."""
        result = matcalc_calc_phonon(
            structure_input=cubic_si_structure.as_dict(),
            calculator="pbe",
            supercell_matrix=[2, 2, 2],
            t_min=100.0,
            t_max=800.0,
            t_step=100.0,
            relax_structure=False,
        )
        
        assert result["success"] is True
        
        temps = result["thermal_properties"]["temperatures"]
        assert min(temps) >= 100.0
        assert max(temps) <= 800.0
        
    def test_cif_string_input(self, cubic_si_structure):
        """Test phonon calculation with CIF string input."""
        # Generate CIF string
        cif_str = cubic_si_structure.to(fmt="cif")
        
        result = matcalc_calc_phonon(
            structure_input=cif_str,
            calculator="pbe",
            supercell_matrix=[2, 2, 2],
            t_max=300.0,
            relax_structure=False,
        )
        
        assert result["success"] is True
        
    def test_poscar_string_input(self, cubic_si_structure):
        """Test phonon calculation with POSCAR string input."""
        # Generate POSCAR string
        poscar_str = cubic_si_structure.to(fmt="poscar")
        
        result = matcalc_calc_phonon(
            structure_input=poscar_str,
            calculator="pbe",
            supercell_matrix=[2, 2, 2],
            t_max=300.0,
            relax_structure=False,
        )
        
        assert result["success"] is True
        
    def test_invalid_structure_input(self):
        """Test error handling for invalid structure input."""
        result = matcalc_calc_phonon(
            structure_input="invalid structure",
            calculator="pbe",
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "parse" in result["error"].lower()
        
    def test_invalid_calculator(self, cubic_si_structure):
        """Test error handling for invalid calculator."""
        result = matcalc_calc_phonon(
            structure_input=cubic_si_structure.as_dict(),
            calculator="invalid_calculator_xyz",
            supercell_matrix=[2, 2, 2],
        )
        
        assert result["success"] is False
        assert "error" in result
        
    def test_units_documentation(self, cubic_si_structure):
        """Test that units are properly documented in output."""
        result = matcalc_calc_phonon(
            structure_input=cubic_si_structure.as_dict(),
            calculator="pbe",
            supercell_matrix=[2, 2, 2],
            t_max=300.0,
            relax_structure=False,
        )
        
        assert result["success"] is True
        assert "units" in result
        
        units = result["units"]
        assert units["temperature"] == "K"
        assert units["free_energy"] == "kJ/mol"
        assert units["entropy"] == "J/K/mol"
        assert units["heat_capacity"] == "J/K/mol"
        assert units["frequency"] == "THz"
        assert units["debye_temperature"] == "K"
        
    def test_atom_displacement_parameter(self, cubic_si_structure):
        """Test different atomic displacement values."""
        displacements = [0.01, 0.015, 0.02]
        
        for disp in displacements:
            result = matcalc_calc_phonon(
                structure_input=cubic_si_structure.as_dict(),
                calculator="pbe",
                supercell_matrix=[2, 2, 2],
                atom_disp=disp,
                t_max=300.0,
                relax_structure=False,
            )
            assert result["success"] is True, f"Failed with atom_disp={disp}: {result.get('error')}"
            
    def test_stability_detection(self, cubic_si_structure):
        """Test phonon stability analysis."""
        result = matcalc_calc_phonon(
            structure_input=cubic_si_structure.as_dict(),
            calculator="pbe",
            supercell_matrix=[2, 2, 2],
            t_max=300.0,
            relax_structure=False,
        )
        
        assert result["success"] is True
        
        stability = result["stability"]
        assert isinstance(stability["is_stable"], bool) or stability["is_stable"] is None
        assert isinstance(stability["num_imaginary_modes"], int) or stability["num_imaginary_modes"] is None
        
        # If unstable, should have max_imaginary_frequency
        if stability["is_stable"] is False:
            assert stability["max_imaginary_frequency"] is not None
            assert stability["max_imaginary_frequency"] < 0  # Should be negative
            
    def test_pymatgen_structure_input(self, cubic_si_structure):
        """Test phonon calculation with pymatgen Structure object."""
        result = matcalc_calc_phonon(
            structure_input=cubic_si_structure,
            calculator="pbe",
            supercell_matrix=[2, 2, 2],
            t_max=300.0,
            relax_structure=False,
        )
        
        assert result["success"] is True
