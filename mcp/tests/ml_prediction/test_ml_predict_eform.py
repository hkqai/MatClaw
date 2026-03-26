"""
Tests for ml_predict_eform tool.

Run with: pytest tests/ml_prediction/test_ml_predict_eform.py -v
"""

import pytest
from tools.ml_prediction.ml_predict_eform import ml_predict_eform


# Check if DGL is available
try:
    import dgl
    DGL_AVAILABLE = True
except:
    DGL_AVAILABLE = False

skip_if_no_dgl = pytest.mark.skipif(not DGL_AVAILABLE, reason="DGL backend not available")


class TestMLPredictEform:
    """Tests for ML formation energy prediction."""

    @skip_if_no_dgl
    def test_basic_prediction_with_dict_input(self):
        """Test basic formation energy prediction with dict input."""
        from pymatgen.core import Lattice, Structure
        
        # Create a simple CsCl structure
        struct = Structure.from_spacegroup(
            "Pm-3m",
            Lattice.cubic(4.1437),
            ["Cs", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        
        result = ml_predict_eform(
            input_structure=struct.as_dict(),
            model="M3GNet-MP-2018.6.1-Eform"
        )
        
        # Check basic success
        assert result["success"] is True
        assert "formation_energy_eV_per_atom" in result
        assert "model_used" in result
        assert result["model_used"] == "M3GNet-MP-2018.6.1-Eform"
        
        # Check that we got a reasonable formation energy value
        eform = result["formation_energy_eV_per_atom"]
        assert isinstance(eform, float)
        # CsCl should be stable (negative formation energy)
        assert eform < 0, "CsCl should have negative formation energy (stable)"
        assert eform > -5, "Formation energy should be reasonable"
        
        # Check metadata
        assert result["formula"] == "CsCl"
        assert result["num_sites"] == 2

    @skip_if_no_dgl
    def test_megnet_model(self):
        """Test with MEGNet model."""
        from pymatgen.core import Lattice, Structure
        
        struct = Structure.from_spacegroup(
            "Pm-3m",
            Lattice.cubic(4.1437),
            ["Cs", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        
        result = ml_predict_eform(
            input_structure=struct.as_dict(),
            model="MEGNet-MP-2018.6.1-Eform"
        )
        
        assert result["success"] is True
        assert result["model_used"] == "MEGNet-MP-2018.6.1-Eform"
        assert "formation_energy_eV_per_atom" in result

    @skip_if_no_dgl
    def test_different_structures(self):
        """Test prediction for different structure types."""
        from pymatgen.core import Lattice, Structure
        
        structures = [
            # NaCl - stable ionic compound
            Structure.from_spacegroup(
                "Fm-3m",
                Lattice.cubic(5.64),
                ["Na", "Cl"],
                [[0, 0, 0], [0.5, 0.5, 0.5]]
            ),
            # Si - element (should have near-zero formation energy)
            Structure.from_spacegroup(
                "Fd-3m",
                Lattice.cubic(5.43),
                ["Si"],
                [[0, 0, 0]]
            ),
        ]
        
        for struct in structures:
            result = ml_predict_eform(
                input_structure=struct.as_dict(),
                model="M3GNet-MP-2018.6.1-Eform"
            )
            
            assert result["success"] is True
            assert "formation_energy_eV_per_atom" in result
            print(f"{struct.composition.reduced_formula}: {result['formation_energy_eV_per_atom']:.4f} eV/atom")

    @skip_if_no_dgl
    def test_cif_string_input(self):
        """Test prediction with CIF string input."""
        cif_string = """data_CsCl
_cell_length_a 4.1437
_cell_length_b 4.1437
_cell_length_c 4.1437
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
        
        result = ml_predict_eform(
            input_structure=cif_string,
            model="M3GNet-MP-2018.6.1-Eform"
        )
        
        assert result["success"] is True
        assert "formation_energy_eV_per_atom" in result

    @skip_if_no_dgl
    def test_interpretation_field(self):
        """Test that interpretation field is provided."""
        from pymatgen.core import Lattice, Structure
        
        struct = Structure.from_spacegroup(
            "Pm-3m",
            Lattice.cubic(4.1437),
            ["Cs", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        
        result = ml_predict_eform(
            input_structure=struct.as_dict(),
            model="M3GNet-MP-2018.6.1-Eform"
        )
        
        assert result["success"] is True
        assert "interpretation" in result
        assert isinstance(result["interpretation"], str)
        assert len(result["interpretation"]) > 0

    @skip_if_no_dgl
    def test_total_formation_energy(self):
        """Test that total formation energy is calculated correctly."""
        from pymatgen.core import Lattice, Structure
        
        # Create a structure with 4 atoms
        struct = Structure.from_spacegroup(
            "Fm-3m",
            Lattice.cubic(5.64),
            ["Na", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        
        result = ml_predict_eform(
            input_structure=struct.as_dict(),
            model="M3GNet-MP-2018.6.1-Eform"
        )
        
        assert result["success"] is True
        assert "total_formation_energy_eV" in result
        
        # Check that total = per_atom * num_sites
        expected_total = result["formation_energy_eV_per_atom"] * result["num_sites"]
        assert abs(result["total_formation_energy_eV"] - expected_total) < 1e-5

    @skip_if_no_dgl
    def test_structure_info_included(self):
        """Test that structure info is included in response."""
        from pymatgen.core import Lattice, Structure
        
        struct = Structure.from_spacegroup(
            "Pm-3m",
            Lattice.cubic(4.1437),
            ["Cs", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        
        result = ml_predict_eform(
            input_structure=struct.as_dict(),
            model="M3GNet-MP-2018.6.1-Eform"
        )
        
        assert result["success"] is True
        assert "structure_info" in result
        assert "formula" in result["structure_info"]
        assert "num_sites" in result["structure_info"]
        assert "volume" in result["structure_info"]
        assert "density_g_per_cm3" in result["structure_info"]

    def test_invalid_structure_handling(self):
        """Test that invalid structures are handled gracefully."""
        result = ml_predict_eform(
            input_structure="not a valid structure",
            model="M3GNet-MP-2018.6.1-Eform"
        )
        
        assert result["success"] is False
        assert "error" in result

    def test_dgl_unavailable_error(self):
        """Test that helpful error is returned when DGL is not available."""
        if DGL_AVAILABLE:
            pytest.skip("DGL is available, skipping DGL unavailability test")
        
        from pymatgen.core import Lattice, Structure
        
        struct = Structure.from_spacegroup(
            "Pm-3m",
            Lattice.cubic(4.1437),
            ["Cs", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        
        result = ml_predict_eform(
            input_structure=struct.as_dict(),
            model="M3GNet-MP-2018.6.1-Eform"
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "DGL" in result["error"]

    @skip_if_no_dgl
    def test_model_comparison(self):
        """Compare predictions from both M3GNet and MEGNet models."""
        from pymatgen.core import Lattice, Structure
        
        struct = Structure.from_spacegroup(
            "Pm-3m",
            Lattice.cubic(4.1437),
            ["Cs", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        
        result_m3gnet = ml_predict_eform(
            input_structure=struct.as_dict(),
            model="M3GNet-MP-2018.6.1-Eform"
        )
        
        result_megnet = ml_predict_eform(
            input_structure=struct.as_dict(),
            model="MEGNet-MP-2018.6.1-Eform"
        )
        
        assert result_m3gnet["success"] is True
        assert result_megnet["success"] is True
        
        # Both should predict negative (stable) formation energy for CsCl
        assert result_m3gnet["formation_energy_eV_per_atom"] < 0
        assert result_megnet["formation_energy_eV_per_atom"] < 0
        
        # Predictions should be reasonably close (within 1 eV/atom)
        diff = abs(result_m3gnet["formation_energy_eV_per_atom"] - 
                   result_megnet["formation_energy_eV_per_atom"])
        assert diff < 1.0, "Model predictions should be reasonably consistent"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
