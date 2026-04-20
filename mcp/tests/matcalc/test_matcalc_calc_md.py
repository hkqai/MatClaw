"""
Tests for matcalc_calc_md tool.

Run with: pytest tests/matcalc/test_matcalc_calc_md.py -v
Run single test: pytest tests/matcalc/test_matcalc_calc_md.py::TestMDCalc::test_basic_md_simulation -v
"""

import pytest
from pymatgen.core import Structure
from tools.matcalc.matcalc_calc_md import matcalc_calc_md


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


class TestMDCalc:
    """Tests for MD simulations."""

    @pytest.mark.slow
    def test_basic_md_simulation(self):
        """Test basic NVT MD simulation."""
        result = matcalc_calc_md(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            ensemble="nvt",
            temperature=300.0,
            timestep=1.0,
            steps=10,  # Very short for testing
            relax_structure=True,
            fmax=0.1,
        )
        
        assert result["success"] is True
        assert result["energy"] is not None
        assert "structure" in result
        assert result["relaxed"] is True
        assert result["ensemble"] == "nvt"
        assert result["temperature"] == 300.0
        assert result["steps"] == 10
        assert result["timestep"] == 1.0
        assert result["total_time"] == 0.01  # 10 steps * 1.0 fs / 1000 = 0.01 ps
        assert "units" in result

    @pytest.mark.slow
    def test_nve_ensemble(self):
        """Test NVE (microcanonical) ensemble."""
        result = matcalc_calc_md(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            ensemble="nve",
            temperature=300.0,
            timestep=0.5,
            steps=10,
            relax_structure=False,  # Skip relaxation for speed
        )
        
        assert result["success"] is True
        assert result["ensemble"] == "nve"
        assert result["timestep"] == 0.5
        assert result["total_time"] == 0.005  # 10 * 0.5 / 1000

    @pytest.mark.slow
    def test_different_temperatures(self):
        """Test MD at different temperatures."""
        for temp in [100.0, 300.0, 600.0]:
            result = matcalc_calc_md(
                structure_input=SI_POSCAR,
                calculator="M3GNet",
                ensemble="nvt",
                temperature=temp,
                steps=10,
                relax_structure=False,
            )
            
            assert result["success"] is True
            assert result["temperature"] == temp

    @pytest.mark.slow
    def test_different_timesteps(self):
        """Test MD with different timesteps."""
        for dt in [0.5, 1.0, 2.0]:
            result = matcalc_calc_md(
                structure_input=SI_POSCAR,
                calculator="M3GNet",
                ensemble="nvt",
                temperature=300.0,
                timestep=dt,
                steps=10,
                relax_structure=False,
            )
            
            assert result["success"] is True
            assert result["timestep"] == dt
            expected_time = 10 * dt / 1000.0
            assert abs(result["total_time"] - expected_time) < 1e-6

    def test_cif_string_input(self):
        """Test MD with CIF format input."""
        result = matcalc_calc_md(
            structure_input=SI_CIF,
            calculator="M3GNet",
            ensemble="nvt",
            temperature=300.0,
            steps=5,
            relax_structure=False,
        )
        
        assert result["success"] is True

    def test_poscar_string_input(self):
        """Test MD with POSCAR format input."""
        result = matcalc_calc_md(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            ensemble="nvt",
            temperature=300.0,
            steps=5,
            relax_structure=False,
        )
        
        assert result["success"] is True

    def test_pymatgen_structure_input(self):
        """Test MD with pymatgen Structure object."""
        structure = Structure.from_str(SI_POSCAR, fmt="poscar")
        
        result = matcalc_calc_md(
            structure_input=structure,
            calculator="M3GNet",
            ensemble="nvt",
            temperature=300.0,
            steps=5,
            relax_structure=False,
        )
        
        assert result["success"] is True

    def test_dict_structure_input(self):
        """Test MD with structure as dictionary."""
        structure = Structure.from_str(SI_POSCAR, fmt="poscar")
        structure_dict = structure.as_dict()
        
        result = matcalc_calc_md(
            structure_input=structure_dict,
            calculator="M3GNet",
            ensemble="nvt",
            temperature=300.0,
            steps=5,
            relax_structure=False,
        )
        
        assert result["success"] is True

    def test_invalid_structure_input(self):
        """Test that invalid structure input returns error."""
        result = matcalc_calc_md(
            structure_input="invalid structure data",
            calculator="M3GNet",
            ensemble="nvt",
            temperature=300.0,
            steps=5,
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "parse structure" in result["error"].lower()

    def test_invalid_calculator(self):
        """Test that invalid calculator returns error."""
        result = matcalc_calc_md(
            structure_input=SI_POSCAR,
            calculator="NonexistentCalculator",
            ensemble="nvt",
            temperature=300.0,
            steps=5,
        )
        
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.slow
    def test_md_with_relaxation(self):
        """Test MD with initial structure relaxation."""
        result = matcalc_calc_md(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            ensemble="nvt",
            temperature=300.0,
            steps=10,
            relax_structure=True,
            fmax=0.1,
        )
        
        assert result["success"] is True
        assert result["relaxed"] is True

    @pytest.mark.slow
    def test_md_without_relaxation(self):
        """Test MD without initial structure relaxation."""
        result = matcalc_calc_md(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            ensemble="nvt",
            temperature=300.0,
            steps=10,
            relax_structure=False,
        )
        
        assert result["success"] is True
        assert result["relaxed"] is False

    @pytest.mark.slow
    def test_different_calculators(self):
        """Test MD with different ML calculators."""
        for calc in ["M3GNet", "CHGNet"]:
            result = matcalc_calc_md(
                structure_input=SI_POSCAR,
                calculator=calc,
                ensemble="nvt",
                temperature=300.0,
                steps=5,
                relax_structure=False,
            )
            
            assert result["success"] is True
            assert calc.upper() in result["calculator"].upper()

    def test_units_documentation(self):
        """Test that units are properly documented in output."""
        result = matcalc_calc_md(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            ensemble="nvt",
            temperature=300.0,
            steps=5,
            relax_structure=False,
        )
        
        assert result["success"] is True
        assert "units" in result
        units = result["units"]
        assert units["energy"] == "eV"
        assert units["temperature"] == "K"
        assert units["pressure"] == "GPa"
        assert units["timestep"] == "fs"
        assert units["time"] == "ps"

    @pytest.mark.slow
    def test_pressure_parameter(self):
        """Test that pressure parameter is passed correctly."""
        result = matcalc_calc_md(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            ensemble="npt",
            temperature=300.0,
            pressure=1.0,  # 1 GPa
            steps=10,
            relax_structure=False,
        )
        
        assert result["success"] is True
        assert result["pressure"] == 1.0

    @pytest.mark.slow
    def test_total_time_calculation(self):
        """Test that total simulation time is calculated correctly."""
        steps = 100
        timestep = 2.0  # fs
        expected_time = (steps * timestep) / 1000.0  # ps
        
        result = matcalc_calc_md(
            structure_input=SI_POSCAR,
            calculator="M3GNet",
            ensemble="nvt",
            temperature=300.0,
            timestep=timestep,
            steps=steps,
            relax_structure=False,
        )
        
        assert result["success"] is True
        assert abs(result["total_time"] - expected_time) < 1e-6
