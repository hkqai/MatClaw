"""
Tests for matcalc_calc_neb tool.

Run with: pytest tests/matcalc/test_matcalc_calc_neb.py -v
Run single test: pytest tests/matcalc/test_matcalc_calc_neb.py::TestNEBCalc::test_basic_neb -v
"""

import pytest
from pymatgen.core import Structure, Lattice
from tools.matcalc.matcalc_calc_neb import matcalc_calc_neb


# Helper to create Si structures with slightly different positions (simulate a transition)
def get_si_structures():
    """Get initial and final Si structures for NEB."""
    lattice = Lattice.from_parameters(a=3.867, b=3.867, c=3.867, 
                                      alpha=60, beta=60, gamma=60)
    
    # Initial structure
    initial = Structure(
        lattice,
        ["Si", "Si"],
        [[0.75, 0.75, 0.75], [0.25, 0.25, 0.25]],
    )
    
    # Final structure (Si atom shifted slightly)
    final = Structure(
        lattice,
        ["Si", "Si"],
        [[0.80, 0.75, 0.75], [0.25, 0.25, 0.25]],
    )
    
    return initial, final


class TestNEBCalc:
    """Tests for NEB calculations."""

    @pytest.mark.slow
    def test_basic_neb(self):
        """Test basic NEB calculation with 2 images."""
        initial, final = get_si_structures()
        
        result = matcalc_calc_neb(
            images=[initial, final],
            calculator="M3GNet",
            n_images=3,  # Small number for fast testing
            climb=True,
            fmax=0.3,  # Loose convergence for speed
            max_steps=100,
        )
        
        assert result["success"] is True
        assert "barrier_eV" in result
        assert "reverse_barrier_eV" in result
        assert "max_force_eV_per_A" in result
        assert result["num_images"] >= 2
        assert "mep_energies" in result
        assert len(result["mep_energies"]) >= 2
        assert "ts_image_index" in result
        assert "initial_energy_eV" in result
        assert "final_energy_eV" in result
        assert "reaction_energy_eV" in result
        assert "units" in result

    @pytest.mark.slow
    def test_neb_with_dict_input(self):
        """Test NEB with dict input format."""
        initial, final = get_si_structures()
        
        images_dict = {
            'image0': initial.as_dict(),
            'image1': final.as_dict(),
        }
        
        result = matcalc_calc_neb(
            images=images_dict,
            calculator="M3GNet",
            n_images=3,
            fmax=0.3,
            max_steps=100,
        )
        
        assert result["success"] is True
        assert result["num_images"] >= 2

    @pytest.mark.slow
    def test_neb_different_n_images(self):
        """Test NEB with different numbers of images."""
        initial, final = get_si_structures()
        
        for n in [3, 5]:
            result = matcalc_calc_neb(
                images=[initial, final],
                calculator="M3GNet",
                n_images=n,
                fmax=0.3,
                max_steps=100,
            )
            
            assert result["success"] is True
            # Note: actual number of images may differ based on interpolation
            assert result["num_images"] >= 2

    @pytest.mark.slow
    def test_neb_no_climb(self):
        """Test NEB without climbing image."""
        initial, final = get_si_structures()
        
        result = matcalc_calc_neb(
            images=[initial, final],
            calculator="M3GNet",
            n_images=3,
            climb=False,
            fmax=0.3,
            max_steps=100,
        )
        
        assert result["success"] is True
        assert result["parameters"]["climb"] is False

    @pytest.mark.slow
    def test_neb_different_optimizers(self):
        """Test NEB with different optimizers."""
        initial, final = get_si_structures()
        
        for optimizer in ["BFGS", "FIRE"]:
            result = matcalc_calc_neb(
                images=[initial, final],
                calculator="M3GNet",
                n_images=3,
                optimizer=optimizer,
                fmax=0.3,
                max_steps=100,
            )
            
            assert result["success"] is True
            assert result["parameters"]["optimizer"] == optimizer

    @pytest.mark.slow
    def test_neb_with_calculator_variants(self):
        """Test NEB with different calculators."""
        initial, final = get_si_structures()
        
        for calc in ["M3GNet", "CHGNet"]:
            result = matcalc_calc_neb(
                images=[initial, final],
                calculator=calc,
                n_images=3,
                fmax=0.3,
                max_steps=50,
            )
            
            assert result["success"] is True
            assert result["parameters"]["calculator"] == calc

    @pytest.mark.slow
    def test_neb_convergence_parameters(self):
        """Test NEB convergence with different fmax."""
        initial, final = get_si_structures()
        
        result = matcalc_calc_neb(
            images=[initial, final],
            calculator="M3GNet",
            n_images=3,
            fmax=0.5,  # Very loose
            max_steps=50,
        )
        
        assert result["success"] is True
        assert "converged" in result
        assert result["max_force_eV_per_A"] is not None

    def test_neb_invalid_images_single(self):
        """Test NEB error handling with only 1 image."""
        initial, _ = get_si_structures()
        
        result = matcalc_calc_neb(
            images=[initial],
            calculator="M3GNet",
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "at least 2 images" in result["error"].lower()

    def test_neb_invalid_calculator(self):
        """Test NEB error handling with invalid calculator."""
        initial, final = get_si_structures()
        
        result = matcalc_calc_neb(
            images=[initial, final],
            calculator="InvalidCalculator123",
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "calculator" in result["error"].lower()

    @pytest.mark.slow
    def test_neb_mep_properties(self):
        """Test MEP (minimum energy path) properties."""
        initial, final = get_si_structures()
        
        result = matcalc_calc_neb(
            images=[initial, final],
            calculator="M3GNet",
            n_images=5,
            fmax=0.3,
            max_steps=100,
        )
        
        assert result["success"] is True
        assert len(result["mep_energies"]) == result["num_images"]
        
        # Check that barrier is the difference between TS and initial
        ts_energy = result["ts_energy_eV"]
        initial_energy = result["initial_energy_eV"]
        barrier = result["barrier_eV"]
        
        # Barrier should be approximately ts_energy - initial_energy
        assert abs(barrier - (ts_energy - initial_energy)) < 1e-6
        
        # Reaction energy should be final - initial
        reaction_energy = result["reaction_energy_eV"]
        final_energy = result["final_energy_eV"]
        assert abs(reaction_energy - (final_energy - initial_energy)) < 1e-6

    @pytest.mark.slow
    def test_neb_units_documentation(self):
        """Test that units are properly documented."""
        initial, final = get_si_structures()
        
        result = matcalc_calc_neb(
            images=[initial, final],
            calculator="M3GNet",
            n_images=3,
            fmax=0.3,
            max_steps=50,
        )
        
        assert result["success"] is True
        assert "units" in result
        units = result["units"]
        
        assert units["barrier"] == "eV"
        assert units["reverse_barrier"] == "eV"
        assert units["max_force"] == "eV/Angstrom"
        assert units["energy"] == "eV"
        assert units["distance"] == "Angstrom"

    @pytest.mark.slow
    def test_neb_calculation_time(self):
        """Test that calculation time is recorded."""
        initial, final = get_si_structures()
        
        result = matcalc_calc_neb(
            images=[initial, final],
            calculator="M3GNet",
            n_images=3,
            fmax=0.3,
            max_steps=50,
        )
        
        assert result["success"] is True
        assert "calculation_time_seconds" in result
        assert result["calculation_time_seconds"] > 0

    @pytest.mark.slow
    def test_neb_ts_index_valid(self):
        """Test that transition state index is valid."""
        initial, final = get_si_structures()
        
        result = matcalc_calc_neb(
            images=[initial, final],
            calculator="M3GNet",
            n_images=5,
            fmax=0.3,
            max_steps=100,
        )
        
        assert result["success"] is True
        ts_idx = result["ts_image_index"]
        
        # TS index should be within valid range
        assert 0 <= ts_idx < result["num_images"]
        
        # TS energy should be the maximum along the path
        ts_energy = result["ts_energy_eV"]
        assert ts_energy == max(result["mep_energies"])

    @pytest.mark.slow
    def test_neb_with_intermediate_images(self):
        """Test NEB when providing intermediate images."""
        lattice = Lattice.from_parameters(a=3.867, b=3.867, c=3.867, 
                                          alpha=60, beta=60, gamma=60)
        
        # Create 4 images with gradual position change
        images = []
        for x in [0.75, 0.77, 0.79, 0.81]:
            struct = Structure(
                lattice,
                ["Si", "Si"],
                [[x, 0.75, 0.75], [0.25, 0.25, 0.25]],
            )
            images.append(struct)
        
        result = matcalc_calc_neb(
            images=images,
            calculator="M3GNet",
            n_images=4,
            fmax=0.3,
            max_steps=100,
        )
        
        assert result["success"] is True
        assert result["num_images"] >= 4
