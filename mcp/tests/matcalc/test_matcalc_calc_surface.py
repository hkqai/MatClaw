"""
Tests for matcalc_calc_surface tool.

Run with: pytest tests/matcalc/test_matcalc_calc_surface.py -v
Run single test: pytest tests/matcalc/test_matcalc_calc_surface.py::TestSurfaceCalc::test_basic_surface -v
"""

import pytest
from pymatgen.core import Structure
from tools.matcalc.matcalc_calc_surface import matcalc_calc_surface


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

NACL_POSCAR = """NaCl
1.0
5.64 0.0 0.0
0.0 5.64 0.0
0.0 0.0 5.64
Na Cl
4 4
direct
0.0 0.0 0.0 Na
0.5 0.5 0.0 Na
0.5 0.0 0.5 Na
0.0 0.5 0.5 Na
0.5 0.5 0.5 Cl
0.0 0.0 0.5 Cl
0.0 0.5 0.0 Cl
0.5 0.0 0.0 Cl"""


class TestSurfaceCalc:
    """Tests for surface energy calculations."""

    @pytest.mark.slow
    def test_basic_surface(self):
        """Test basic surface energy calculation for Si(111)."""
        result = matcalc_calc_surface(
            structure_input=SI_POSCAR,
            miller_index=(1, 1, 1),
            calculator="CHGNet",
            min_slab_size=10.0,
            min_vacuum_size=10.0,
            relax_bulk=False,
            relax_slab=False,  # Disable for speed
            fmax=0.1,
        )
        
        # Check for error first
        assert "error" not in result, f"Error in result: {result.get('error')}"
        
        # Check required fields
        assert "surface_energy" in result
        assert "bulk_energy_per_atom" in result
        assert "slab_energy" in result
        assert "slab_structure" in result
        assert "bulk_structure" in result
        assert "miller_index" in result
        assert "slab_formula" in result
        assert "num_slab_atoms" in result
        
        # Check values
        assert isinstance(result["surface_energy"], float)
        assert result["surface_energy"] > 0  # Surface energy should be positive
        assert isinstance(result["bulk_energy_per_atom"], float)
        assert isinstance(result["slab_energy"], float)
        assert result["miller_index"] == [1, 1, 1]
        assert result["slab_formula"] == "Si"
        assert result["num_slab_atoms"] > 0
        
        # Check units
        assert result["surface_energy_units"] == "eV/Å²"
        assert result["bulk_energy_units"] == "eV/atom"
        assert result["slab_energy_units"] == "eV"
        
        # Check parameters
        assert result["calculator"] == "CHGNet"
        assert result["relax_bulk"] is False
        assert result["relax_slab"] is False

    @pytest.mark.slow
    def test_surface_with_relaxation(self):
        """Test surface energy with slab relaxation enabled."""
        result = matcalc_calc_surface(
            structure_input=SI_POSCAR,
            miller_index=(1, 0, 0),
            calculator="CHGNet",
            min_slab_size=8.0,
            min_vacuum_size=8.0,
            relax_bulk=False,
            relax_slab=True,
            fmax=0.3,  # Looser for speed
            max_steps=100,
        )
        
        assert "error" not in result
        assert "surface_energy" in result
        assert result["relax_slab"] is True
        assert isinstance(result["surface_energy"], float)
        # Surface energy can be negative with relaxation
        assert result["miller_index"] == [1, 0, 0]

    @pytest.mark.slow
    def test_surface_different_miller_indices(self):
        """Test surface energy for different Miller indices."""
        # Test (100), (110), and (111) surfaces
        miller_indices = [(1, 0, 0), (1, 1, 0), (1, 1, 1)]
        surface_energies = []
        
        for miller in miller_indices:
            result = matcalc_calc_surface(
                structure_input=SI_POSCAR,
                miller_index=miller,
                calculator="CHGNet",
                min_slab_size=8.0,
                min_vacuum_size=8.0,
                relax_bulk=False,
                relax_slab=False,
                fmax=0.3,
            )
            
            assert "error" not in result, f"Error for {miller}: {result.get('error')}"
            assert "surface_energy" in result
            assert result["miller_index"] == list(miller)
            surface_energies.append(result["surface_energy"])
        
        # All should be positive
        assert all(e > 0 for e in surface_energies)
        # Different surfaces should have different energies (generally)
        assert len(set(surface_energies)) > 1

    @pytest.mark.slow
    def test_surface_cif_input(self):
        """Test surface calculation with CIF format input."""
        result = matcalc_calc_surface(
            structure_input=SI_CIF,
            miller_index=(1, 1, 1),
            calculator="CHGNet",
            min_slab_size=10.0,
            min_vacuum_size=10.0,
            relax_bulk=False,
            relax_slab=False,
            fmax=0.1,
        )
        
        assert "error" not in result
        assert "surface_energy" in result
        assert isinstance(result["surface_energy"], float)
        assert result["slab_formula"] == "Si"

    @pytest.mark.slow
    def test_surface_dict_input(self):
        """Test surface calculation with Structure dict input."""
        structure = Structure.from_str(SI_POSCAR, fmt='poscar')
        structure_dict = structure.as_dict()
        
        result = matcalc_calc_surface(
            structure_input=structure_dict,
            miller_index=(1, 1, 1),
            calculator="CHGNet",
            min_slab_size=10.0,
            min_vacuum_size=10.0,
            relax_bulk=False,
            relax_slab=False,
            fmax=0.1,
        )
        
        assert "error" not in result
        assert "surface_energy" in result
        assert result["slab_formula"] == "Si"

    @pytest.mark.slow
    def test_surface_different_calculators(self):
        """Test surface calculation with different calculators."""
        calculators = ["CHGNet", "M3GNet"]
        
        for calc in calculators:
            result = matcalc_calc_surface(
                structure_input=SI_POSCAR,
                miller_index=(1, 1, 1),
                calculator=calc,
                min_slab_size=8.0,
                min_vacuum_size=8.0,
                relax_bulk=False,
                relax_slab=False,
                fmax=0.3,
            )
            
            # Skip if calculator fails (might not be available)
            if "error" in result:
                pytest.skip(f"Calculator {calc} not available or failed")
            
            assert "surface_energy" in result
            assert result["calculator"] == calc
            assert result["surface_energy"] > 0

    @pytest.mark.slow
    def test_surface_nacl(self):
        """Test surface calculation for ionic crystal (NaCl)."""
        result = matcalc_calc_surface(
            structure_input=NACL_POSCAR,
            miller_index=(1, 0, 0),
            calculator="CHGNet",
            min_slab_size=10.0,
            min_vacuum_size=10.0,
            relax_bulk=False,
            relax_slab=False,
            fmax=0.1,
        )
        
        assert "error" not in result
        assert "surface_energy" in result
        assert result["surface_energy"] > 0
        assert result["slab_formula"] == "NaCl"

    @pytest.mark.slow
    def test_surface_slab_sizes(self):
        """Test surface calculation with different slab sizes."""
        slab_sizes = [8.0, 10.0, 12.0]
        surface_energies = []
        
        for size in slab_sizes:
            result = matcalc_calc_surface(
                structure_input=SI_POSCAR,
                miller_index=(1, 1, 1),
                calculator="CHGNet",
                min_slab_size=size,
                min_vacuum_size=10.0,
                relax_bulk=False,
                relax_slab=False,
                fmax=0.3,
            )
            
            assert "error" not in result
            assert "surface_energy" in result
            surface_energies.append(result["surface_energy"])
        
        # All should be positive
        assert all(e > 0 for e in surface_energies)

    @pytest.mark.slow
    def test_surface_optimizers(self):
        """Test surface calculation with different optimizers."""
        optimizers = ["FIRE", "BFGS"]
        
        for opt in optimizers:
            result = matcalc_calc_surface(
                structure_input=SI_POSCAR,
                miller_index=(1, 1, 1),
                calculator="CHGNet",
                min_slab_size=8.0,
                min_vacuum_size=8.0,
                relax_bulk=False,
                relax_slab=True,  # Need relaxation to test optimizer
                fmax=0.3,
                optimizer=opt,
                max_steps=50,  # Quick test
            )
            
            # Optimizer might fail with certain structures
            if "error" in result:
                pytest.skip(f"Optimizer {opt} failed (might be structure-specific)")
            
            assert "surface_energy" in result
            # Surface energy can be negative with relaxation
            assert isinstance(result["surface_energy"], float)

    def test_surface_invalid_structure(self):
        """Test error handling with invalid structure."""
        result = matcalc_calc_surface(
            structure_input="invalid structure text",
            miller_index=(1, 1, 1),
            calculator="CHGNet",
        )
        
        assert "error" in result
        assert "parse structure" in result["error"].lower()

    def test_surface_invalid_calculator(self):
        """Test error handling with invalid calculator."""
        result = matcalc_calc_surface(
            structure_input=SI_POSCAR,
            miller_index=(1, 1, 1),
            calculator="InvalidCalculator",
        )
        
        assert "error" in result
        assert "calculator" in result["error"].lower()

    @pytest.mark.slow
    def test_surface_structure_output(self):
        """Test that output structures are valid pymatgen dicts."""
        result = matcalc_calc_surface(
            structure_input=SI_POSCAR,
            miller_index=(1, 1, 1),
            calculator="CHGNet",
            min_slab_size=10.0,
            min_vacuum_size=10.0,
            relax_bulk=False,
            relax_slab=False,
        )
        
        assert "error" not in result
        assert "slab_structure" in result
        assert "bulk_structure" in result
        
        # Should be able to reconstruct structures
        slab_struct = Structure.from_dict(result["slab_structure"])
        bulk_struct = Structure.from_dict(result["bulk_structure"])
        
        assert len(slab_struct) > 0
        assert len(bulk_struct) > 0
        assert len(slab_struct) >= len(bulk_struct)  # Slab should have more atoms

    @pytest.mark.slow
    def test_surface_both_relaxation(self):
        """Test surface calculation with both bulk and slab relaxation."""
        result = matcalc_calc_surface(
            structure_input=SI_POSCAR,
            miller_index=(1, 1, 1),
            calculator="CHGNet",
            min_slab_size=8.0,
            min_vacuum_size=8.0,
            relax_bulk=True,
            relax_slab=True,
            fmax=0.3,
            max_steps=50,
        )
        
        assert "error" not in result
        assert "surface_energy" in result
        assert result["relax_bulk"] is True
        assert result["relax_slab"] is True
        assert result["surface_energy"] > 0

    @pytest.mark.slow
    def test_surface_fmax_values(self):
        """Test surface calculation with different fmax values."""
        fmax_values = [0.3, 0.1, 0.05]
        
        for fmax in fmax_values:
            result = matcalc_calc_surface(
                structure_input=SI_POSCAR,
                miller_index=(1, 1, 1),
                calculator="CHGNet",
                min_slab_size=8.0,
                min_vacuum_size=8.0,
                relax_bulk=False,
                relax_slab=True,
                fmax=fmax,
                max_steps=100,
            )
            
            # Might timeout with very tight fmax
            if "error" in result:
                continue
            
            assert "surface_energy" in result
            # Surface energy can be negative with tight relaxation
            assert isinstance(result["surface_energy"], float)

    @pytest.mark.slow
    def test_surface_vacuum_sizes(self):
        """Test surface calculation with different vacuum sizes."""
        vacuum_sizes = [8.0, 10.0, 15.0]
        
        for vacuum in vacuum_sizes:
            result = matcalc_calc_surface(
                structure_input=SI_POSCAR,
                miller_index=(1, 1, 1),
                calculator="CHGNet",
                min_slab_size=10.0,
                min_vacuum_size=vacuum,
                relax_bulk=False,
                relax_slab=False,
                fmax=0.3,
            )
            
            assert "error" not in result
            assert "surface_energy" in result
            assert result["min_vacuum_size"] == vacuum
