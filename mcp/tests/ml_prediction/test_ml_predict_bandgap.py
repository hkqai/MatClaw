"""
Tests for ml_predict_bandgap tool.

Run with: pytest tests/ml_prediction/test_ml_predict_bandgap.py -v
"""

import pytest
from tools.ml_prediction.ml_predict_bandgap import ml_predict_bandgap


# Check if DGL is available
try:
    import dgl
    DGL_AVAILABLE = True
except:
    DGL_AVAILABLE = False

skip_if_no_dgl = pytest.mark.skipif(not DGL_AVAILABLE, reason="DGL backend not available")


class TestMLPredictBandgap:
    """Tests for ML band gap prediction."""

    @skip_if_no_dgl
    def test_basic_prediction_with_dict_input(self):
        """Test basic band gap prediction with dict input."""
        from pymatgen.core import Lattice, Structure
        
        # Create a simple CsCl structure (should be wide band gap)
        struct = Structure.from_spacegroup(
            "Pm-3m",
            Lattice.cubic(4.1437),
            ["Cs", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        
        result = ml_predict_bandgap(
            input_structure=struct.as_dict(),
            model="MEGNet-MP-2019.4.1-BandGap-mfi"
        )
        
        # Check basic success
        assert result["success"] is True
        assert "band_gap_eV" in result
        assert "model_used" in result
        assert result["model_used"] == "MEGNet-MP-2019.4.1-BandGap-mfi"
        
        # Check that we got a reasonable band gap value
        bandgap = result["band_gap_eV"]
        assert isinstance(bandgap, float)
        assert bandgap >= 0, "Band gap should be non-negative"
        # CsCl should be an insulator with large band gap
        assert bandgap > 2.0, "CsCl should have a wide band gap"
        
        # Check metadata
        assert result["formula"] == "CsCl"
        assert result["num_sites"] == 2
        assert "material_class" in result

    @skip_if_no_dgl
    def test_metallic_structure(self):
        """Test with a metallic structure (zero band gap)."""
        from pymatgen.core import Lattice, Structure
        
        # Create a simple Cu structure (FCC metal)
        struct = Structure.from_spacegroup(
            "Fm-3m",
            Lattice.cubic(3.61),
            ["Cu"],
            [[0, 0, 0]]
        )
        
        result = ml_predict_bandgap(
            input_structure=struct.as_dict()
        )
        
        assert result["success"] is True
        bandgap = result["band_gap_eV"]
        # Metals should have very small or zero band gap
        assert bandgap < 0.5, "Cu should be metallic with small/zero band gap"
        assert "Metal" in result["material_class"] or "Narrow" in result["material_class"]

    @skip_if_no_dgl
    def test_semiconductor_structure(self):
        """Test with a semiconductor structure."""
        from pymatgen.core import Lattice, Structure
        
        # Create a simple GaAs structure (zinc blende semiconductor)
        # Using GaAs instead of Si as it's better predicted by DFT-based models
        struct = Structure.from_spacegroup(
            "F-43m",
            Lattice.cubic(5.65),
            ["Ga", "As"],
            [[0, 0, 0], [0.25, 0.25, 0.25]]
        )
        
        result = ml_predict_bandgap(
            input_structure=struct.as_dict()
        )
        
        assert result["success"] is True
        bandgap = result["band_gap_eV"]
        # GaAs has a direct band gap, typically better predicted than Si
        assert bandgap >= 0, f"GaAs should have non-negative band gap, got {bandgap}"
        assert bandgap < 3.0, f"GaAs band gap should be reasonable, got {bandgap}"
        # Check it's classified as some type of semiconductor (not insulator)
        assert "Semiconductor" in result["material_class"] or "gap" in result["material_class"].lower()

    @skip_if_no_dgl
    def test_different_structures(self):
        """Test prediction for different structure types with various band gaps."""
        from pymatgen.core import Lattice, Structure
        
        structures = [
            # NaCl - wide band gap insulator
            Structure.from_spacegroup(
                "Fm-3m",
                Lattice.cubic(5.64),
                ["Na", "Cl"],
                [[0, 0, 0], [0.5, 0.5, 0.5]]
            ),
            # GaAs - narrow/medium band gap semiconductor
            Structure.from_spacegroup(
                "F-43m",
                Lattice.cubic(5.65),
                ["Ga", "As"],
                [[0, 0, 0], [0.25, 0.25, 0.25]]
            ),
        ]
        
        for struct in structures:
            result = ml_predict_bandgap(input_structure=struct.as_dict())
            assert result["success"] is True
            assert "band_gap_eV" in result
            assert result["band_gap_eV"] >= 0
            print(f"{result['formula']}: {result['band_gap_eV']:.3f} eV ({result['material_class']})")

    @skip_if_no_dgl
    def test_cif_string_input(self):
        """Test with CIF string input."""
        from pymatgen.core import Lattice, Structure
        
        # Create structure and export as CIF
        struct = Structure.from_spacegroup(
            "Pm-3m",
            Lattice.cubic(4.1437),
            ["Cs", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        cif_string = struct.to(fmt="cif")
        
        result = ml_predict_bandgap(input_structure=cif_string)
        
        assert result["success"] is True
        assert "band_gap_eV" in result
        assert result["formula"] == "CsCl"

    @skip_if_no_dgl
    def test_material_classification(self):
        """Test that material classification is provided."""
        from pymatgen.core import Lattice, Structure
        
        struct = Structure.from_spacegroup(
            "Pm-3m",
            Lattice.cubic(4.1437),
            ["Cs", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        
        result = ml_predict_bandgap(input_structure=struct.as_dict())
        
        assert result["success"] is True
        assert "material_class" in result
        assert "interpretation" in result
        # Verify classification is one of the expected types
        valid_classes = [
            "Metal/Conductor",
            "Narrow Band Gap Semiconductor",
            "Semiconductor",
            "Wide Band Gap Semiconductor",
            "Very Wide Band Gap Semiconductor/Insulator"
        ]
        assert result["material_class"] in valid_classes

    @skip_if_no_dgl
    def test_structure_info_included(self):
        """Test that structure information is included in result."""
        from pymatgen.core import Lattice, Structure
        
        struct = Structure.from_spacegroup(
            "Pm-3m",
            Lattice.cubic(4.1437),
            ["Cs", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        
        result = ml_predict_bandgap(input_structure=struct.as_dict())
        
        assert result["success"] is True
        assert "structure_info" in result
        info = result["structure_info"]
        assert "formula" in info
        assert "num_sites" in info
        assert "volume" in info
        assert "density_g_per_cm3" in info
        assert info["num_sites"] == 2
        assert info["formula"] == "CsCl"

    def test_invalid_structure_handling(self):
        """Test handling of invalid structure input."""
        result = ml_predict_bandgap(
            input_structure={"invalid": "structure"}
        )
        
        assert result["success"] is False
        assert "error" in result

    def test_dgl_unavailable_error(self):
        """Test that helpful error is returned when DGL is not available."""
        if DGL_AVAILABLE:
            pytest.skip("DGL is available, cannot test unavailability error")
        
        from pymatgen.core import Lattice, Structure
        
        struct = Structure.from_spacegroup(
            "Pm-3m",
            Lattice.cubic(4.1437),
            ["Cs", "Cl"],
            [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        
        result = ml_predict_bandgap(input_structure=struct.as_dict())
        
        assert result["success"] is False
        assert "error" in result
        assert "DGL" in result["error"]

    @skip_if_no_dgl
    def test_band_gap_ranges(self):
        """Test that different materials fall into expected band gap ranges."""
        from pymatgen.core import Lattice, Structure
        
        # Test well-known materials that DFT-based models predict accurately
        test_cases = [
            # (structure, expected_range_min, expected_range_max, description)
            (
                Structure.from_spacegroup("F-43m", Lattice.cubic(5.65), ["Ga", "As"], [[0, 0, 0], [0.25, 0.25, 0.25]]),
                0.0, 2.5, "GaAs semiconductor"
            ),
            (
                Structure.from_spacegroup("Pm-3m", Lattice.cubic(4.1437), ["Cs", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]]),
                2.0, 10.0, "CsCl wide gap insulator"
            ),
        ]
        
        for struct, min_gap, max_gap, description in test_cases:
            result = ml_predict_bandgap(input_structure=struct.as_dict())
            assert result["success"] is True
            bandgap = result["band_gap_eV"]
            assert min_gap <= bandgap <= max_gap, (
                f"{description}: expected band gap between {min_gap}-{max_gap} eV, "
                f"got {bandgap:.3f} eV"
            )
            print(f"{description}: {bandgap:.3f} eV - {result['material_class']}")
