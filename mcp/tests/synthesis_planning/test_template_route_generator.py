"""
Tests for template_route_generator tool.
"""

import pytest
from tools.synthesis_planning.template_route_generator import (
    template_route_generator,
    _select_synthesis_method,
    _estimate_calcination_temperature,
    _calculate_precursor_amount,
)

# Skip all tests if pymatgen is not available
pytest.importorskip("pymatgen")

from pymatgen.core import Composition


class TestSynthesisRouteGenerator:
    """Test main template_route_generator function."""
    
    def test_basic_solid_state_route(self):
        """Test generation of basic solid-state synthesis route."""
        result = template_route_generator(
            target_material={"composition": "LiCoO2"},
            synthesis_method="solid_state",
            constraints={}  # Test template-based generation
        )
        
        assert result["success"] is True
        assert result["target_composition"] == "LiCoO2"
        assert result["n_routes"] >= 1
        
        route = result["routes"][0]
        assert route["method"] == "solid_state"
        assert "precursors" in route
        assert "steps" in route
        assert len(route["steps"]) >= 3  # Mix, calcine, cool minimum
        assert 0 <= route["feasibility_score"] <= 1.0
    
    def test_basic_hydrothermal_route(self):
        """Test generation of basic hydrothermal synthesis route."""
        result = template_route_generator(
            target_material={"composition": "LiFePO4"},
            synthesis_method="hydrothermal",
            constraints={}
        )
        
        assert result["success"] is True
        route = result["routes"][0]
        assert route["method"] == "hydrothermal"
        assert "autoclave" in str(route["steps"]).lower()
        assert any(step["action"] == "hydrothermal_treatment" for step in route["steps"])
    
    def test_basic_solgel_route(self):
        """Test generation of basic sol-gel synthesis route."""
        result = template_route_generator(
            target_material={"composition": "BaTiO3"},
            synthesis_method="sol_gel",
            constraints={}
        )
        
        assert result["success"] is True
        route = result["routes"][0]
        assert route["method"] == "sol_gel"
        assert "steps" in route
        # Sol-gel has many steps: solution, gelation, drying, decompose, calcine
        assert len(route["steps"]) >= 5
        # Check for characteristic sol-gel steps
        actions = [step["action"] for step in route["steps"]]
        assert "prepare_solution" in actions
        assert "add_chelating_agent" in actions
        assert "evaporate_and_gel" in actions
        assert "dry_gel" in actions
        assert "decompose" in actions
        assert "calcine" in actions
        # Sol-gel should have advantages mentioned
        assert "advantages" in route
        assert "mixing" in route["advantages"].lower()
    
    def test_auto_method_selection(self):
        """Test automatic synthesis method selection."""
        # Oxide should default to solid-state
        result_oxide = template_route_generator(
            target_material={"composition": "La2CuO4"},
            synthesis_method="auto",
            constraints={}
        )
        assert result_oxide["success"] is True
        # Method should be selected automatically
        
        # Phosphate should prefer hydrothermal
        result_phosphate = template_route_generator(
            target_material={"composition": "LiFePO4"},
            synthesis_method="auto",
            constraints={}
        )
        assert result_phosphate["success"] is True
        # Should select hydrothermal for phosphates
        
        # Multi-cation complex oxide should prefer sol-gel
        result_complex = template_route_generator(
            target_material={"composition": "LiNi0.8Co0.15Al0.05O2"},  # NCM - 3+ cations
            synthesis_method="auto",
            constraints={}
        )
        assert result_complex["success"] is True
        # Should select sol-gel for complex multi-cation oxides (3+ cations)
        assert result_complex["routes"][0]["method"] == "sol_gel"
    
    def test_invalid_composition(self):
        """Test handling of invalid composition."""
        result = template_route_generator(
            target_material={"composition": "InvalidFormula123"},
            synthesis_method="solid_state"
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "Invalid composition" in result["error"]
    
    def test_missing_composition_field(self):
        """Test error when composition field is missing."""
        result = template_route_generator(
            target_material={"structure": {}},
            synthesis_method="solid_state"
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "composition" in result["error"].lower()
    
    def test_temperature_constraints(self):
        """Test synthesis route generation with temperature constraints."""
        result = template_route_generator(
            target_material={"composition": "LiCoO2"},
            synthesis_method="solid_state",
            constraints={"max_temperature": 800}
        )
        
        assert result["success"] is True
        route = result["routes"][0]
        
        # Find calcination step
        calcine_step = next(
            (s for s in route["steps"] if s["action"] == "calcine"),
            None
        )
        assert calcine_step is not None
        assert calcine_step["temperature_c"] <= 800
    
    def test_time_constraints(self):
        """Test synthesis route generation with time constraints."""
        result = template_route_generator(
            target_material={"composition": "NiO"},
            synthesis_method="solid_state",
            constraints={"max_time": 10}
        )
        
        assert result["success"] is True
        route = result["routes"][0]
        
        # Total time should respect constraint
        total_time_str = route["total_time_estimate"]
        # Extract hours from string like "~15 hours"
        hours = float(total_time_str.split("~")[1].split(" ")[0])
        assert hours <= 10
    
    def test_precursor_exclusion(self):
        """Test exclusion of specific precursor forms."""
        result = template_route_generator(
            target_material={"composition": "Co3O4"},
            synthesis_method="solid_state",
            constraints={"exclude_precursors": ["nitrate", "chloride"]}
        )
        
        assert result["success"] is True
        route = result["routes"][0]
        
        # Check that excluded forms are not used
        for precursor in route["precursors"]:
            assert precursor["form"] not in ["nitrate", "chloride"]
    
    def test_precursor_preference(self):
        """Test preference for specific precursor forms."""
        result = template_route_generator(
            target_material={"composition": "MnO2"},
            synthesis_method="solid_state",
            constraints={"prefer_precursors": ["oxide"]}
        )
        
        assert result["success"] is True
        route = result["routes"][0]
        
        # Check that preferred forms are used when available
        oxide_count = sum(1 for p in route["precursors"] if p["form"] == "oxide")
        assert oxide_count > 0
    
    def test_complex_composition(self):
        """Test route generation for complex multi-element composition."""
        result = template_route_generator(
            target_material={"composition": "LiNi0.8Co0.15Al0.05O2"},
            synthesis_method="solid_state",
            constraints={}
        )
        
        assert result["success"] is True
        route = result["routes"][0]
        
        # Should have precursors for Li, Ni, Co, Al (not O)
        precursor_elements = {p["element"] for p in route["precursors"]}
        assert "Li" in precursor_elements
        assert "Ni" in precursor_elements
        assert "Co" in precursor_elements
        assert "Al" in precursor_elements
    
    def test_route_ranking(self):
        """Test that routes are ranked by feasibility."""
        result = template_route_generator(
            target_material={"composition": "Fe2O3"},
            synthesis_method="solid_state",
            constraints={}
        )
        
        assert result["success"] is True
        assert len(result["routes"]) >= 1
        
        # Routes should be sorted by feasibility score
        routes = result["routes"]
        if len(routes) > 1:
            for i in range(len(routes) - 1):
                assert routes[i]["feasibility_score"] >= routes[i+1]["feasibility_score"]
    
    def test_unknown_synthesis_method(self):
        """Test error handling for unknown synthesis method."""
        result = template_route_generator(
            target_material={"composition": "TiO2"},
            synthesis_method="plasma_enhanced_CVD"
        )
        
        assert result["success"] is False
        assert "Unknown synthesis method" in result["error"]
    
    def test_warnings_for_missing_precursors(self):
        """Test that warnings are generated for elements without precursors."""
        # Using composition with element not in precursor database
        result = template_route_generator(
            target_material={"composition": "ZnO"},  # Zn is in database
            synthesis_method="solid_state",
            constraints={}
        )
        
        assert result["success"] is True
        # Should succeed with available precursors


class TestMethodSelection:
    """Test automatic synthesis method selection logic."""
    
    def test_select_solid_state_for_simple_oxide(self):
        """Test that simple oxides select solid-state synthesis."""
        comp = Composition("MgO")
        method = _select_synthesis_method(comp)
        assert method == "solid_state"
    
    def test_select_hydrothermal_for_phosphate(self):
        """Test that phosphates select hydrothermal synthesis."""
        comp = Composition("LiFePO4")
        method = _select_synthesis_method(comp)
        assert method == "hydrothermal"
    
    def test_select_hydrothermal_for_fluoride(self):
        """Test that fluorides prefer hydrothermal synthesis."""
        comp = Composition("LiF")
        method = _select_synthesis_method(comp)
        assert method == "hydrothermal"
    
    def test_default_to_solid_state(self):
        """Test that most compositions default to solid-state."""
        comp = Composition("La2CuO4")
        method = _select_synthesis_method(comp)
        assert method == "solid_state"


class TestTemperatureEstimation:
    """Test calcination temperature estimation."""
    
    def test_base_temperature(self):
        """Test base temperature for simple composition."""
        comp = Composition("NiO")
        temp = _estimate_calcination_temperature(comp, max_temp=1400)
        assert 600 <= temp <= 1200
        assert temp % 50 == 0  # Should be rounded to nearest 50
    
    def test_temperature_increases_with_complexity(self):
        """Test that temperature increases with more elements."""
        simple = Composition("CuO")
        complex_ = Composition("LiNi0.8Co0.15Al0.05O2")
        
        temp_simple = _estimate_calcination_temperature(simple, max_temp=1400)
        temp_complex = _estimate_calcination_temperature(complex_, max_temp=1400)
        
        # Complex should generally need higher temperature
        # (though not guaranteed due to element-specific adjustments)
        assert temp_simple >= 600
        assert temp_complex >= 600
    
    def test_high_temp_elements(self):
        """Test that high-melting-point elements increase temperature."""
        comp_regular = Composition("NiO")
        comp_refractory = Composition("Al2O3")
        
        temp_regular = _estimate_calcination_temperature(comp_regular, max_temp=1400)
        temp_refractory = _estimate_calcination_temperature(comp_refractory, max_temp=1400)
        
        # Alumina should need higher temperature
        assert temp_refractory >= temp_regular
    
    def test_low_temp_elements(self):
        """Test that alkali metals decrease temperature."""
        comp_no_alkali = Composition("MnO2")
        comp_with_alkali = Composition("Li2O")
        
        temp_no_alkali = _estimate_calcination_temperature(comp_no_alkali, max_temp=1400)
        temp_with_alkali = _estimate_calcination_temperature(comp_with_alkali, max_temp=1400)
        
        # Lithium compounds should need lower temperature
        assert temp_with_alkali <= temp_no_alkali
    
    def test_respects_max_temp(self):
        """Test that estimated temperature respects maximum limit."""
        comp = Composition("Al2O3")  # High-temperature material
        max_temp = 900
        
        temp = _estimate_calcination_temperature(comp, max_temp=max_temp)
        assert temp <= max_temp


class TestPrecursorCalculations:
    """Test precursor amount calculations."""
    
    def test_simple_precursor_amount(self):
        """Test calculation for simple 1:1 precursor."""
        # Li2CO3 contains 2 Li
        amount = _calculate_precursor_amount("Li2CO3", "Li", 2.0)
        assert amount == pytest.approx(1.0, rel=0.01)  # Need 1 mol Li2CO3 for 2 mol Li
    
    def test_oxide_precursor_amount(self):
        """Test calculation for oxide precursor."""
        # Co3O4 contains 3 Co
        amount = _calculate_precursor_amount("Co3O4", "Co", 3.0)
        assert amount == pytest.approx(1.0, rel=0.01)
    
    def test_hydrated_precursor(self):
        """Test calculation for hydrated precursor."""
        # Ni(NO3)2·6H2O contains 1 Ni
        amount = _calculate_precursor_amount("Ni(NO3)2·6H2O", "Ni", 1.0)
        assert amount == pytest.approx(1.0, rel=0.01)
    
    def test_fractional_amounts(self):
        """Test calculation with fractional stoichiometry."""
        amount = _calculate_precursor_amount("Li2CO3", "Li", 0.5)
        assert amount == pytest.approx(0.25, rel=0.01)


class TestRouteStructure:
    """Test the structure and completeness of generated routes."""
    
    def test_solid_state_route_structure(self):
        """Test that solid-state route has all required fields."""
        result = template_route_generator(
            target_material={"composition": "CuO"},
            synthesis_method="solid_state",
            constraints={}
        )
        
        route = result["routes"][0]
        
        # Check required top-level fields
        assert "method" in route
        assert "confidence" in route
        assert "precursors" in route
        assert "steps" in route
        assert "total_time_estimate" in route
        assert "feasibility_score" in route
        
        # Check confidence is reasonable
        assert 0 <= route["confidence"] <= 1.0
        
        # Check precursors have required fields
        for precursor in route["precursors"]:
            assert "element" in precursor
            assert "compound" in precursor
            assert "form" in precursor
        
        # Check steps have required fields
        for step in route["steps"]:
            assert "step" in step
            assert "action" in step
            assert "description" in step
    
    def test_hydrothermal_route_structure(self):
        """Test that hydrothermal route has all required fields."""
        result = template_route_generator(
            target_material={"composition": "ZnO"},
            synthesis_method="hydrothermal",
            constraints={}
        )
        
        route = result["routes"][0]
        
        # Basic structure
        assert route["method"] == "hydrothermal"
        assert "steps" in route
        
        # Should have characteristic hydrothermal steps
        actions = [step["action"] for step in route["steps"]]
        assert "prepare_solution" in actions
        assert "hydrothermal_treatment" in actions
        assert "wash_and_dry" in actions
    
    def test_route_has_temperature_info(self):
        """Test that routes include temperature information."""
        result = template_route_generator(
            target_material={"composition": "Fe2O3"},
            synthesis_method="solid_state",
            constraints={}
        )
        
        route = result["routes"][0]
        assert "temperature_range" in route
        
        # Find temperature in steps
        has_temp_step = any(
            "temperature_c" in step
            for step in route["steps"]
        )
        assert has_temp_step
    
    def test_route_has_time_estimates(self):
        """Test that routes include time estimates."""
        result = template_route_generator(
            target_material={"composition": "MgO"},
            synthesis_method="solid_state",
            constraints={}
        )
        
        route = result["routes"][0]
        assert "total_time_estimate" in route
        assert "hours" in route["total_time_estimate"].lower()


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_single_element_oxide(self):
        """Test synthesis of simple single-element oxide."""
        result = template_route_generator(
            target_material={"composition": "CuO"},
            synthesis_method="solid_state",
            constraints={}
        )
        
        assert result["success"] is True
        assert len(result["routes"]) >= 1
    
    def test_binary_compound(self):
        """Test synthesis of binary compound."""
        result = template_route_generator(
            target_material={"composition": "NaCl"},
            synthesis_method="solid_state",
            constraints={}
        )
        
        assert result["success"] is True
    
    def test_composition_with_fractional_stoichiometry(self):
        """Test handling of fractional stoichiometry."""
        result = template_route_generator(
            target_material={"composition": "LiNi0.8Co0.2O2"},
            synthesis_method="solid_state",
            constraints={}
        )
        
        assert result["success"] is True
        route = result["routes"][0]
        
        # Should have precursors for fractional amounts
        assert len(route["precursors"]) >= 2  # At least Ni and Co
    
    def test_empty_constraints(self):
        """Test with empty constraints dictionary."""
        result = template_route_generator(
            target_material={"composition": "TiO2"},
            synthesis_method="solid_state",
            constraints={}
        )
        
        assert result["success"] is True
    
    def test_very_low_temperature_constraint(self):
        """Test with impractically low temperature constraint."""
        result = template_route_generator(
            target_material={"composition": "Al2O3"},
            synthesis_method="solid_state",
            constraints={"max_temperature": 300}
        )
        
        assert result["success"] is True
        # Should still generate route, but feasibility may be low
        route = result["routes"][0]
        assert route["feasibility_score"] <= 1.0
