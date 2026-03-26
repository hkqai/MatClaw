"""
Tests for ml_relax_structure tool.

Run with: pytest tests/ml_prediction/test_ml_relax_structure.py -v
"""

import pytest
from tools.ml_prediction.ml_relax_structure import ml_relax_structure


class TestMLRelaxStructure:
    """Tests for ML structure relaxation."""

    def test_basic_relaxation_with_dict_input(self):
        """Test basic structure relaxation with dict input."""
        from pymatgen.core import Lattice, Structure
        
        # Create a stressed CsCl structure
        struct = Structure.from_spacegroup(
            "Pm-3m",
            Lattice.cubic(4.5),  # Intentionally wrong lattice constant
            ["Cs", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        
        result = ml_relax_structure(
            input_structure=struct.as_dict(),
            model="TensorNet-MatPES-PBE-v2025.1-PES",
            relax_cell=True,
            fmax=0.05,  # Relaxed tolerance for faster test
            max_steps=200,
            verbose=False
        )
        
        # Check basic success
        assert result["success"] is True
        assert "final_structure" in result
        assert "initial_energy_eV" in result
        assert "final_energy_eV" in result
        
        # Energy should decrease
        assert result["energy_change_eV"] < 0, "Energy should decrease during relaxation"
        
        # Check structure changed
        assert abs(result["volume_change_percent"]) > 0.1, "Volume should change"

    def test_fixed_cell_relaxation(self):
        """Test relaxation with fixed cell (only atoms move)."""
        from pymatgen.core import Lattice, Structure
        
        # Create a structure with slightly displaced atoms
        struct = Structure.from_spacegroup(
            "Pm-3m",
            Lattice.cubic(4.2),
            ["Cs", "Cl"],
            [[0.01, 0.01, 0.01], [0.51, 0.51, 0.51]]  # Slightly displaced
        )
        
        result = ml_relax_structure(
            input_structure=struct.as_dict(),
            model="TensorNet-MatPES-PBE-v2025.1-PES",
            relax_cell=False,  # Fixed cell
            fmax=0.05,
            max_steps=200
        )
        
        assert result["success"] is True
        assert result["parameters"]["relax_cell"] is False
        
        # Volume should not change (or change minimally due to numerical precision)
        assert abs(result["volume_change_percent"]) < 0.01, \
            "Volume should remain constant in fixed-cell relaxation"

    def test_cif_string_input(self):
        """Test relaxation with CIF string input."""
        # Use a simple cubic CsCl CIF structure
        cif_string = """data_CsCl
_cell_length_a 4.2
_cell_length_b 4.2
_cell_length_c 4.2
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_symmetry_space_group_name_H-M 'P m -3 m'
_space_group_IT_number 221
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Cs1 Cs 0.0 0.0 0.0 1.0
Cl1 Cl 0.5 0.5 0.5 1.0
"""
        
        result = ml_relax_structure(
            input_structure=cif_string,
            model="TensorNet-MatPES-PBE-v2025.1-PES",
            fmax=0.05,
            max_steps=200
        )
        
        if not result["success"]:
            print(f"\nCIF test failed with error: {result.get('error', 'Unknown error')}")
        
        assert result["success"] is True
        assert "final_structure" in result

    def test_verbose_output(self):
        """Test that verbose mode includes trajectory information."""
        from pymatgen.core import Lattice, Structure
        
        struct = Structure.from_spacegroup(
            "Pm-3m",
            Lattice.cubic(4.3),
            ["Cs", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        
        result = ml_relax_structure(
            input_structure=struct.as_dict(),
            model="TensorNet-MatPES-PBE-v2025.1-PES",
            fmax=0.05,
            max_steps=100,
            verbose=True
        )
        
        assert result["success"] is True
        assert "trajectory" in result
        assert len(result["trajectory"]) > 0
        assert "energy_eV" in result["trajectory"][0]
        assert "max_force_eV_per_A" in result["trajectory"][0]

    def test_convergence_detection(self):
        """Test that convergence is properly detected."""
        from pymatgen.core import Lattice, Structure
        
        # Use a simple structure that should converge easily
        struct = Structure.from_spacegroup(
            "Pm-3m",
            Lattice.cubic(4.2),
            ["Cs", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        
        result = ml_relax_structure(
            input_structure=struct.as_dict(),
            model="TensorNet-MatPES-PBE-v2025.1-PES",
            fmax=0.05,
            max_steps=500
        )
        
        assert result["success"] is True
        
        # If converged, final force should be below tolerance
        if result["converged"]:
            assert result["final_max_force_eV_per_A"] <= result["force_tolerance_eV_per_A"]
            assert "warning" not in result
        else:
            # If not converged, should have warning
            assert "warning" in result

    def test_different_models(self):
        """Test that different TensorNet models work."""
        from pymatgen.core import Lattice, Structure
        
        struct = Structure.from_spacegroup(
            "Pm-3m",
            Lattice.cubic(4.3),
            ["Cs", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        
        for model in ["TensorNet-MatPES-PBE-v2025.1-PES", "TensorNet-MatPES-r2SCAN-v2025.1-PES"]:
            result = ml_relax_structure(
                input_structure=struct.as_dict(),
                model=model,
                fmax=0.05,
                max_steps=200
            )
            
            assert result["success"] is True, f"Failed with model {model}"
            assert result["parameters"]["model"] == model

    def test_lattice_change_tracking(self):
        """Test that lattice parameter changes are tracked."""
        from pymatgen.core import Lattice, Structure
        
        struct = Structure.from_spacegroup(
            "Pm-3m",
            Lattice.cubic(4.5),
            ["Cs", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        
        result = ml_relax_structure(
            input_structure=struct.as_dict(),
            model="TensorNet-MatPES-PBE-v2025.1-PES",
            relax_cell=True,
            fmax=0.05,
            max_steps=200
        )
        
        assert result["success"] is True
        assert "lattice_change" in result
        assert "a_percent" in result["lattice_change"]
        assert "b_percent" in result["lattice_change"]
        assert "c_percent" in result["lattice_change"]
        assert "alpha_change" in result["lattice_change"]
        assert "beta_change" in result["lattice_change"]
        assert "gamma_change" in result["lattice_change"]

    def test_invalid_structure_handling(self):
        """Test that invalid structures are handled gracefully."""
        result = ml_relax_structure(
            input_structure="not a valid structure",
            model="TensorNet-MatPES-PBE-v2025.1-PES"
        )
        
        assert result["success"] is False
        assert "error" in result

    def test_tensornet_model(self):
        """Test with the latest TensorNet model."""
        from pymatgen.core import Lattice, Structure
        
        struct = Structure.from_spacegroup(
            "Pm-3m",
            Lattice.cubic(4.3),
            ["Cs", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        
        result = ml_relax_structure(
            input_structure=struct.as_dict(),
            model="TensorNet-MatPES-PBE-v2025.1-PES",
            fmax=0.05,
            max_steps=200
        )
        
        # This test might fail if model download fails, so check both cases
        if result["success"]:
            assert "final_structure" in result
        else:
            # Model download might fail in CI environment
            assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
