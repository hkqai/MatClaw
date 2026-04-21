"""
Tests for matcalc_calc_energetics tool.

Run with: pytest tests/matcalc/test_matcalc_calc_energetics.py -v
Run single test: pytest tests/matcalc/test_matcalc_calc_energetics.py::TestEnergeticsCalc::test_basic_energetics -v
"""

import pytest
from pymatgen.core import Structure
from tools.matcalc.matcalc_calc_energetics import matcalc_calc_energetics


# Test structures
SI_POSCAR = """Si2
1.0
3.348898 0.000000 1.933487
1.116299 3.157372 1.933487
0.000000 0.000000 3.866975
Si
2
direct
0.750000 0.750000 0.750000 Si
0.250000 0.250000 0.250000 Si"""

SI_CIF = """data_Si
_cell_length_a    3.866975
_cell_length_b    3.866975
_cell_length_c    3.866975
_cell_angle_alpha 60.0
_cell_angle_beta  60.0
_cell_angle_gamma 60.0
_symmetry_space_group_name_H-M    'P 1'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Si1 Si 0.75 0.75 0.75
Si2 Si 0.25 0.25 0.25"""


class TestEnergeticsCalc:
    """Tests for energetics calculations."""

    @pytest.mark.slow
    def test_basic_energetics(self):
        """Test basic formation and cohesive energy calculation."""
        result = matcalc_calc_energetics(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            elemental_refs="MatPES-PBE",
            relax_structure=True,
            fmax=0.1,
        )
        
        assert result["success"] is True
        assert "formation_energy_per_atom_eV" in result
        assert "cohesive_energy_per_atom_eV" in result
        assert "total_energy_eV" in result
        assert "energy_per_atom_eV" in result
        assert result["num_atoms"] == 2
        assert "structure" in result
        assert "final_structure" in result
        assert result["relaxed"] is True
        assert "formation_stable" in result
        assert isinstance(result["formation_stable"], bool)
        
        # Cohesive energy should be a valid float
        assert isinstance(result["cohesive_energy_per_atom_eV"], float)
        
        # Units should be documented
        assert "units" in result
        assert result["units"]["formation_energy"] == "eV/atom"
        assert result["units"]["cohesive_energy"] == "eV/atom"

    @pytest.mark.slow
    def test_energetics_without_relaxation(self):
        """Test energetics without structure relaxation."""
        result = matcalc_calc_energetics(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            relax_structure=False,
        )
        
        assert result["success"] is True
        assert result["relaxed"] is False
        # Structure and final_structure should be the same when not relaxed
        assert "formation_energy_per_atom_eV" in result
        assert "cohesive_energy_per_atom_eV" in result

    @pytest.mark.slow
    def test_energetics_different_refs(self):
        """Test energetics with different elemental references."""
        # Test MatPES-PBE (works with ML force fields)
        result = matcalc_calc_energetics(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            elemental_refs="MatPES-PBE",
            relax_structure=False,
            fmax=0.3,
        )
        assert result["success"] is True
        assert result["parameters"]["elemental_refs"] == "MatPES-PBE"
        assert "formation_energy_per_atom_eV" in result
        
        # Test MatPES-r2SCAN
        result = matcalc_calc_energetics(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            elemental_refs="MatPES-r2SCAN",
            relax_structure=False,
            fmax=0.3,
        )
        assert result["success"] is True
        assert result["parameters"]["elemental_refs"] == "MatPES-r2SCAN"
        assert "formation_energy_per_atom_eV" in result

    @pytest.mark.slow
    def test_energetics_different_calculators(self):
        """Test energetics with different calculators."""
        for calc in ["M3GNet", "CHGNet"]:
            result = matcalc_calc_energetics(
                structure_input=SI_POSCAR,
                calculator=calc,
                elemental_refs="MatPES-PBE",
                relax_structure=False,
            )
            
            assert result["success"] is True
            assert result["parameters"]["calculator"] == calc

    @pytest.mark.slow
    def test_energetics_different_optimizers(self):
        """Test energetics with different optimizers."""
        for optimizer in ["FIRE", "BFGS"]:
            result = matcalc_calc_energetics(
                structure_input=SI_POSCAR,
                calculator="M3GNet",
                optimizer=optimizer,
                relax_structure=True,
                fmax=0.3,
            )
            
            assert result["success"] is True
            assert result["parameters"]["optimizer"] == optimizer

    @pytest.mark.slow
    def test_energetics_cif_input(self):
        """Test energetics with CIF string input."""
        result = matcalc_calc_energetics(
            structure_input=SI_CIF,
            calculator="M3GNet",
            relax_structure=False,
        )
        
        assert result["success"] is True
        assert result["num_atoms"] == 2

    @pytest.mark.slow
    def test_energetics_poscar_input(self):
        """Test energetics with POSCAR string input."""
        result = matcalc_calc_energetics(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            relax_structure=False,
        )
        
        assert result["success"] is True
        assert result["num_atoms"] == 2

    @pytest.mark.slow
    def test_energetics_dict_input(self):
        """Test energetics with structure dict input."""
        structure = Structure.from_str(SI_POSCAR, fmt='poscar')
        struct_dict = structure.as_dict()
        
        result = matcalc_calc_energetics(
            structure_input=struct_dict,
            calculator="M3GNet",
            relax_structure=False,
        )
        
        assert result["success"] is True
        assert result["num_atoms"] == 2

    @pytest.mark.slow
    def test_energetics_pymatgen_structure_input(self):
        """Test energetics with pymatgen Structure object input."""
        structure = Structure.from_str(SI_POSCAR, fmt='poscar')
        
        result = matcalc_calc_energetics(
            structure_input=structure,
            calculator="M3GNet",
            relax_structure=False,
        )
        
        assert result["success"] is True
        assert result["num_atoms"] == 2

    def test_energetics_invalid_structure(self):
        """Test energetics error handling with invalid structure."""
        result = matcalc_calc_energetics(
            structure_input="invalid structure data",
            calculator="M3GNet",
        )
        
        assert result["success"] is False
        assert "error" in result

    def test_energetics_invalid_calculator(self):
        """Test energetics error handling with invalid calculator."""
        result = matcalc_calc_energetics(
            structure_input=SI_POSCAR,
            calculator="InvalidCalculator123",
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "calculator" in result["error"].lower()

    @pytest.mark.slow
    def test_energetics_formation_stability(self):
        """Test that formation_stable flag is set correctly."""
        result = matcalc_calc_energetics(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            relax_structure=False,
        )
        
        assert result["success"] is True
        
        # formation_stable should be True if formation_energy < 0
        if result["formation_energy_per_atom_eV"] < 0:
            assert result["formation_stable"] is True
        else:
            assert result["formation_stable"] is False

    @pytest.mark.slow
    def test_energetics_cohesive_energy(self):
        """Test that cohesive energy is calculated."""
        result = matcalc_calc_energetics(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            relax_structure=False,
        )
        
        assert result["success"] is True
        # Cohesive energy should be a valid float
        assert isinstance(result["cohesive_energy_per_atom_eV"], float)
        # For most stable materials, cohesive energy is negative (energy released)
        # but we just check it's reported
        assert "cohesive_energy_per_atom_eV" in result

    @pytest.mark.slow
    def test_energetics_energy_consistency(self):
        """Test energy calculation consistency."""
        result = matcalc_calc_energetics(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            relax_structure=False,
        )
        
        assert result["success"] is True
        
        # energy_per_atom should be total_energy / num_atoms
        expected_energy_per_atom = result["total_energy_eV"] / result["num_atoms"]
        assert abs(result["energy_per_atom_eV"] - expected_energy_per_atom) < 1e-6

    @pytest.mark.slow
    def test_energetics_units_documentation(self):
        """Test that units are properly documented."""
        result = matcalc_calc_energetics(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            relax_structure=False,
        )
        
        assert result["success"] is True
        assert "units" in result
        units = result["units"]
        
        assert units["formation_energy"] == "eV/atom"
        assert units["cohesive_energy"] == "eV/atom"
        assert units["total_energy"] == "eV"
        assert units["energy"] == "eV/atom"
        assert units["force"] == "eV/Angstrom"

    @pytest.mark.slow
    def test_energetics_calculation_time(self):
        """Test that calculation time is recorded."""
        result = matcalc_calc_energetics(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            relax_structure=False,
        )
        
        assert result["success"] is True
        assert "calculation_time_seconds" in result
        assert result["calculation_time_seconds"] > 0

    @pytest.mark.slow
    def test_energetics_parameters_recorded(self):
        """Test that all parameters are recorded in output."""
        result = matcalc_calc_energetics(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            elemental_refs="MatPES-PBE",
            relax_structure=True,
            fmax=0.2,
            optimizer="FIRE",
            use_gs_reference=False,
        )
        
        assert result["success"] is True
        params = result["parameters"]
        
        assert params["calculator"] == "M3GNet"
        assert params["elemental_refs"] == "MatPES-PBE"
        assert params["relax_structure"] is True
        assert params["fmax"] == 0.2
        assert params["optimizer"] == "FIRE"
        assert params["use_gs_reference"] is False

    @pytest.mark.slow
    def test_energetics_fmax_values(self):
        """Test energetics with different fmax values."""
        for fmax in [0.05, 0.1, 0.3]:
            result = matcalc_calc_energetics(
                structure_input=SI_POSCAR,
                calculator="M3GNet",
                relax_structure=True,
                fmax=fmax,
            )
            
            assert result["success"] is True
            assert result["parameters"]["fmax"] == fmax

    @pytest.mark.slow
    def test_energetics_use_gs_reference(self):
        """Test energetics with ground state reference."""
        result = matcalc_calc_energetics(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            use_gs_reference=True,
            relax_structure=False,
        )
        
        assert result["success"] is True
        assert result["parameters"]["use_gs_reference"] is True
