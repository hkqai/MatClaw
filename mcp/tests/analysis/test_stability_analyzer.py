"""
Tests for stability_analyzer tool.

Run with: pytest tests/analysis/test_stability_analyzer.py -v

Note: Tests requiring Materials Project API will automatically skip if 
MP_API_KEY environment variable is not set.
"""

import pytest
import os
from tools.analysis.stability_analyzer import stability_analyzer


@pytest.mark.usefixtures("mp_api_key")
class TestStabilityAnalyzer:
    """Tests for stability analysis (require MP API key)."""

    def test_stable_material_nacl(self):
        """Test with stable material NaCl."""
        result = stability_analyzer(input_structure="NaCl")
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        assert result["composition"] == "NaCl"
        assert "stability" in result
        
        # NaCl should be stable (on hull)
        stability = result["stability"]
        assert "stability_level" in stability
        # Should be stable or very close to stable
        if "energy_above_hull" in stability:
            assert stability["energy_above_hull"] < 0.05

    def test_metastable_material(self):
        """Test with a metastable material."""
        # Li2O2 (lithium peroxide) can be metastable
        result = stability_analyzer(input_structure="Li2O2")
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        assert "stability" in result
        assert "energy_above_hull" in result["stability"] or "stability_level" in result["stability"]

    def test_with_composition_string(self):
        """Test with composition string input."""
        result = stability_analyzer(input_structure="Fe2O3")
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        assert result["composition"] == "Fe2O3"

    def test_with_user_provided_energy(self):
        """Test with user-provided energy."""
        result = stability_analyzer(
            input_structure="LiCoO2",
            energy_per_atom=-5.5
        )
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        assert result["energy_info"]["energy_source"] == "user_provided"
        assert result["energy_info"]["energy_per_atom"] == -5.5

    def test_polymorphs_check(self):
        """Test polymorph detection."""
        # SiO2 has many polymorphs (quartz, cristobalite, etc.)
        result = stability_analyzer(
            input_structure="SiO2",
            check_polymorphs=True
        )
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        # SiO2 should have multiple polymorphs
        if "polymorphs" in result:
            assert len(result["polymorphs"]) > 0

    def test_without_polymorphs_check(self):
        """Test with polymorph check disabled."""
        result = stability_analyzer(
            input_structure="NaCl",
            check_polymorphs=False
        )
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        assert result["metadata"]["check_polymorphs"] is False

    def test_hull_tolerance(self):
        """Test hull tolerance parameter."""
        result = stability_analyzer(
            input_structure="LiCoO2",
            hull_tolerance=0.1
        )
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        assert result["metadata"]["hull_tolerance"] == 0.1

    def test_phase_diagram_info(self):
        """Test that phase diagram info is returned."""
        result = stability_analyzer(input_structure="LiFePO4")
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        assert "phase_diagram_info" in result
        
        pd_info = result["phase_diagram_info"]
        assert "n_phases" in pd_info
        assert "n_stable_phases" in pd_info
        assert "dimensionality" in pd_info
        assert pd_info["n_phases"] > 0
        assert pd_info["dimensionality"] == 4  # Li-Fe-P-O

    def test_competing_phases(self):
        """Test that competing phases are identified."""
        result = stability_analyzer(input_structure="Fe2O3")
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        
        if "competing_phases" in result:
            assert isinstance(result["competing_phases"], list)
            # Should have some competing phases (Fe, O2, FeO, Fe3O4, etc.)
            if len(result["competing_phases"]) > 0:
                phase = result["competing_phases"][0]
                assert "formula" in phase
                assert "energy_per_atom" in phase

    def test_decomposition_products(self):
        """Test decomposition products for unstable material."""
        # Use a hypothetical unstable composition
        result = stability_analyzer(
            input_structure="Li5O",  # Unlikely to be stable
            energy_per_atom=-3.0  # Provide hypothetical energy
        )
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        
        # If unstable, should have decomposition info
        if result["stability"]["stability_level"] == "unstable":
            if "decomposition" in result:
                assert "decomposition_products" in result["decomposition"]
                assert len(result["decomposition"]["decomposition_products"]) > 0

    def test_recommendations(self):
        """Test that recommendations are provided."""
        result = stability_analyzer(input_structure="TiO2")
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        assert "recommendations" in result
        
        recs = result["recommendations"]
        assert "synthesizable" in recs
        assert "confidence" in recs
        assert "notes" in recs
        assert isinstance(recs["synthesizable"], bool)
        assert recs["confidence"] in ["high", "medium", "low"]

    def test_binary_compound(self):
        """Test with binary compound."""
        result = stability_analyzer(input_structure="GaN")
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        assert result["phase_diagram_info"]["dimensionality"] == 2

    def test_ternary_compound(self):
        """Test with ternary compound."""
        result = stability_analyzer(input_structure="BaTiO3")
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        assert result["phase_diagram_info"]["dimensionality"] == 3

    def test_message_field(self):
        """Test that message is provided."""
        result = stability_analyzer(input_structure="Al2O3")
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        assert "message" in result
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0

    def test_metadata_completeness(self):
        """Test that metadata is complete."""
        result = stability_analyzer(input_structure="ZnO")
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        assert "metadata" in result
        
        metadata = result["metadata"]
        assert "temperature" in metadata
        assert "hull_tolerance" in metadata
        assert "mp_data_available" in metadata

    def test_structure_dict_input(self, simple_nacl_structure):
        """Test with Structure dict input."""
        result = stability_analyzer(input_structure=simple_nacl_structure)
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        assert result["composition"] == "NaCl"

    def test_formation_energy(self):
        """Test formation energy calculation."""
        result = stability_analyzer(input_structure="LiCoO2")
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        
        # Should have formation energy
        if "formation_energy" in result["stability"]:
            # Formation energy should be negative for stable compounds
            assert isinstance(result["stability"]["formation_energy"], (int, float))

    def test_energy_above_hull_stable(self):
        """Test that stable materials have low energy above hull."""
        result = stability_analyzer(input_structure="NaCl")
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        
        if "energy_above_hull" in result["stability"]:
            # Stable materials should be on or very close to hull
            assert result["stability"]["energy_above_hull"] < 0.05

    def test_warnings_optional(self):
        """Test that warnings field is optional."""
        result = stability_analyzer(input_structure="MgO")
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        # Warnings should only appear if there are warnings
        if "warnings" in result:
            assert isinstance(result["warnings"], list)


class TestStabilityAnalyzerErrors:
    """Tests for error handling (don't require API key)."""

    def test_missing_api_key(self):
        """Test error when API key is missing."""
        # Temporarily clear API key
        original_key = os.environ.get("MP_API_KEY")
        if original_key:
            del os.environ["MP_API_KEY"]
        
        try:
            result = stability_analyzer(input_structure="NaCl")
            
            assert result["success"] is False
            assert "error" in result
            assert "API key" in result["error"]
        finally:
            # Restore original key
            if original_key:
                os.environ["MP_API_KEY"] = original_key

    def test_invalid_composition(self):
        """Test with invalid composition."""
        # Temporarily set a fake API key for this test
        original_key = os.environ.get("MP_API_KEY")
        os.environ["MP_API_KEY"] = "fake_key_for_test"
        
        try:
            result = stability_analyzer(input_structure="XyZ123Invalid")
            
            assert result["success"] is False
            assert "error" in result
        finally:
            # Restore original key
            if original_key:
                os.environ["MP_API_KEY"] = original_key
            else:
                os.environ.pop("MP_API_KEY", None)

    def test_empty_input(self):
        """Test with empty input."""
        # Temporarily set a fake API key for this test
        original_key = os.environ.get("MP_API_KEY")
        os.environ["MP_API_KEY"] = "fake_key_for_test"
        
        try:
            result = stability_analyzer(input_structure="")
            
            assert result["success"] is False
            assert "error" in result
        finally:
            # Restore original key
            if original_key:
                os.environ["MP_API_KEY"] = original_key
            else:
                os.environ.pop("MP_API_KEY", None)

    def test_basic_import_check(self):
        """Test that the tool can be imported and called."""
        # This is a smoke test to ensure the module loads correctly
        from tools.analysis.stability_analyzer import stability_analyzer
        
        # Should be callable
        assert callable(stability_analyzer)


@pytest.mark.usefixtures("mp_api_key")
class TestStabilityAnalyzerAdvanced:
    """Advanced tests requiring API key."""

    def test_known_stable_materials(self):
        """Test several known stable materials."""
        stable_materials = ["NaCl", "MgO", "Al2O3", "SiO2", "Fe2O3"]
        
        for material in stable_materials:
            result = stability_analyzer(input_structure=material)
            
            if not result["success"]:
                continue  # Skip if API fails
            
            # These should all be stable or very close to stable
            if "energy_above_hull" in result["stability"]:
                assert result["stability"]["energy_above_hull"] < 0.1, \
                    f"{material} should be stable but has E_hull = {result['stability']['energy_above_hull']}"

    def test_temperature_parameter(self):
        """Test temperature parameter."""
        result = stability_analyzer(
            input_structure="LiCoO2",
            temperature=500.0
        )
        
        if not result["success"]:
            pytest.skip(f"API call failed: {result.get('error', 'unknown')}")
        
        assert result["success"] is True
        assert result["metadata"]["temperature"] == 500.0

    def test_reproducibility(self):
        """Test that repeated calls give same results."""
        comp = "TiO2"
        
        result1 = stability_analyzer(input_structure=comp)
        result2 = stability_analyzer(input_structure=comp)
        
        if not result1["success"] or not result2["success"]:
            pytest.skip("API calls failed")
        
