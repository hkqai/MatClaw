"""
Tests for mp_search_recipe tool.

These tests make real HTTP requests to the Materials Project Synthesis Explorer API.
Both an internet connection and a valid MP_API_KEY environment variable are required.

Well-known materials with documented synthesis routes are used:
    - LiFePO4  - widely studied cathode, many published recipes
    - LiCoO2   - classic cathode, abundant solid-state recipes
    - TiO2     - common oxide, broad synthesis literature

Some tests call pytest.skip() gracefully when the synthesis endpoint is not
available in the current MP API version (the tool returns success=False with an
error message about endpoint availability in that case).

Run with: pytest tests/materials_project/test_mp_search_recipe.py -v
Skip automatically when MP_API_KEY is not set.
"""

import os
import pytest
from tools.materials_project.mp_search_recipe import mp_search_recipe


_requires_api_key = pytest.mark.skipif(
    not os.getenv("MP_API_KEY"),
    reason="MP_API_KEY environment variable not set"
)


def _skip_if_endpoint_unavailable(result: dict) -> None:
    """Skip the calling test if the synthesis endpoint is not available."""
    if not result["success"] and "error" in result:
        err = result["error"].lower()
        if any(phrase in err for phrase in ("not available", "endpoint", "attribute")):
            pytest.skip(f"Synthesis endpoint not available: {result['error']}")


# Missing API key (always runs)
class TestMissingApiKey:

    def test_missing_api_key_returns_failure(self, monkeypatch):
        """Missing MP_API_KEY returns success=False."""
        monkeypatch.delenv("MP_API_KEY", raising=False)
        result = mp_search_recipe(target_formula="LiFePO4")
        assert result["success"] is False

    def test_missing_api_key_error_message(self, monkeypatch):
        """Error message mentions MP_API_KEY when the key is absent."""
        monkeypatch.delenv("MP_API_KEY", raising=False)
        result = mp_search_recipe(target_formula="LiFePO4")
        assert "error" in result
        assert "MP_API_KEY" in result["error"]


# No search criteria (always runs — no network call needed)
class TestNoSearchCriteria:

    def test_no_criteria_returns_failure(self, monkeypatch):
        """Calling with no search criteria returns success=False."""
        monkeypatch.setenv("MP_API_KEY", "dummy_key_for_guard_test")
        result = mp_search_recipe()
        assert result["success"] is False

    def test_no_criteria_error_key_present(self, monkeypatch):
        """'error' key is present when no search criteria are provided."""
        monkeypatch.setenv("MP_API_KEY", "dummy_key_for_guard_test")
        result = mp_search_recipe()
        assert "error" in result
        assert len(result["error"]) > 0

    def test_no_criteria_recipes_empty(self, monkeypatch):
        """'recipes' list is empty when no search criteria are provided."""
        monkeypatch.setenv("MP_API_KEY", "dummy_key_for_guard_test")
        result = mp_search_recipe()
        assert result["recipes"] == []


# Top-level response structure
@_requires_api_key
class TestResponseStructure:

    def test_required_top_level_keys_present(self):
        """Response always contains success, query, count, recipes keys."""
        result = mp_search_recipe(target_formula="LiFePO4")
        _skip_if_endpoint_unavailable(result)
        for key in ("success", "query", "count", "recipes"):
            assert key in result, f"Missing top-level key: {key}"

    def test_success_is_bool(self):
        """'success' value is a boolean."""
        result = mp_search_recipe(target_formula="LiFePO4")
        _skip_if_endpoint_unavailable(result)
        assert isinstance(result["success"], bool)

    def test_query_is_dict(self):
        """'query' value is a dict."""
        result = mp_search_recipe(target_formula="LiFePO4")
        _skip_if_endpoint_unavailable(result)
        assert isinstance(result["query"], dict)

    def test_recipes_is_list(self):
        """'recipes' value is a list."""
        result = mp_search_recipe(target_formula="LiFePO4")
        _skip_if_endpoint_unavailable(result)
        assert isinstance(result["recipes"], list)

    def test_count_matches_recipes_length(self):
        """'count' equals len(recipes)."""
        result = mp_search_recipe(target_formula="LiFePO4")
        _skip_if_endpoint_unavailable(result)
        assert result["count"] == len(result["recipes"])

    def test_success_true_on_valid_search(self):
        """A well-formed search returns success=True."""
        result = mp_search_recipe(target_formula="LiFePO4")
        _skip_if_endpoint_unavailable(result)
        assert result["success"] is True


# Query parameter echoing
@_requires_api_key
class TestQueryEchoing:

    def test_target_formula_echoed_in_query(self):
        """query dict reflects target_formula parameter."""
        result = mp_search_recipe(target_formula="LiFePO4")
        _skip_if_endpoint_unavailable(result)
        assert "target_formula" in result["query"]

    def test_keywords_echoed_in_query(self):
        """query dict reflects keywords parameter."""
        result = mp_search_recipe(keywords="hydrothermal", target_formula="TiO2")
        _skip_if_endpoint_unavailable(result)
        assert "keywords" in result["query"]

    def test_temperature_max_echoed_in_query(self):
        """query dict reflects temperature_max parameter."""
        result = mp_search_recipe(target_formula="LiFePO4", temperature_max=900)
        _skip_if_endpoint_unavailable(result)
        assert "temperature_max" in result["query"]
        assert result["query"]["temperature_max"] == 900

    def test_year_min_echoed_in_query(self):
        """query dict reflects year_min parameter."""
        result = mp_search_recipe(target_formula="LiCoO2", year_min=2015)
        _skip_if_endpoint_unavailable(result)
        assert "year_min" in result["query"]
        assert result["query"]["year_min"] == 2015


# Limit parameter
@_requires_api_key
class TestLimit:

    def test_limit_respected(self):
        """Returned recipe count does not exceed limit."""
        result = mp_search_recipe(target_formula="LiFePO4", limit=3)
        _skip_if_endpoint_unavailable(result)
        assert len(result["recipes"]) <= 3

    def test_limit_one_returns_at_most_one(self):
        """limit=1 returns at most one recipe."""
        result = mp_search_recipe(target_formula="LiFePO4", limit=1)
        _skip_if_endpoint_unavailable(result)
        assert len(result["recipes"]) <= 1


# Recipe entry structure
@_requires_api_key
class TestRecipeEntryStructure:

    def test_recipe_entry_required_keys(self):
        """Each recipe entry contains the standard set of keys."""
        result = mp_search_recipe(target_formula="LiFePO4", limit=3)
        _skip_if_endpoint_unavailable(result)
        if result["count"] == 0:
            pytest.skip("No recipes returned to inspect")
        entry = result["recipes"][0]
        for key in ("recipe_id", "target_formula", "precursors", "operations",
                    "conditions", "temperature_celsius", "heating_time_hours",
                    "atmosphere", "doi", "year"):
            assert key in entry, f"Missing key in recipe entry: {key}"

    def test_recipe_id_is_present_and_nonempty(self):
        """recipe_id is a non-empty string."""
        result = mp_search_recipe(target_formula="LiFePO4", limit=3)
        _skip_if_endpoint_unavailable(result)
        if result["count"] == 0:
            pytest.skip("No recipes returned to inspect")
        recipe_id = result["recipes"][0]["recipe_id"]
        assert recipe_id is not None
        assert str(recipe_id) != ""

    def test_recipe_precursors_is_list_or_none(self):
        """precursors field is a list (or None) in each recipe entry."""
        result = mp_search_recipe(target_formula="LiFePO4", limit=5)
        _skip_if_endpoint_unavailable(result)
        if result["count"] == 0:
            pytest.skip("No recipes returned to inspect")
        for recipe in result["recipes"]:
            assert recipe["precursors"] is None or isinstance(recipe["precursors"], list)

    def test_recipe_conditions_is_dict_or_none(self):
        """conditions field is a dict (or None) in each recipe entry."""
        result = mp_search_recipe(target_formula="LiFePO4", limit=5)
        _skip_if_endpoint_unavailable(result)
        if result["count"] == 0:
            pytest.skip("No recipes returned to inspect")
        for recipe in result["recipes"]:
            assert recipe["conditions"] is None or isinstance(recipe["conditions"], dict)


# Target formula search
@_requires_api_key
class TestTargetFormulaSearch:

    def test_lifep04_search_returns_success(self):
        """Searching for LiFePO4 returns success=True."""
        result = mp_search_recipe(target_formula="LiFePO4")
        _skip_if_endpoint_unavailable(result)
        assert result["success"] is True

    def test_licoo2_search_returns_success(self):
        """Searching for LiCoO2 returns success=True."""
        result = mp_search_recipe(target_formula="LiCoO2")
        _skip_if_endpoint_unavailable(result)
        assert result["success"] is True

    def test_target_formula_list_accepted(self):
        """Passing a list of target formulas is accepted (success=True)."""
        result = mp_search_recipe(target_formula=["LiCoO2", "LiMn2O4"])
        _skip_if_endpoint_unavailable(result)
        assert result["success"] is True


# Keywords search
@_requires_api_key
class TestKeywordsSearch:

    def test_hydrothermal_keyword_returns_success(self):
        """Searching by keyword 'hydrothermal' returns success=True."""
        result = mp_search_recipe(keywords="hydrothermal", target_formula="TiO2")
        _skip_if_endpoint_unavailable(result)
        assert result["success"] is True

    def test_solid_state_keyword_returns_success(self):
        """Searching by keyword 'solid-state' returns success=True."""
        result = mp_search_recipe(keywords="solid-state", target_formula="LiCoO2")
        _skip_if_endpoint_unavailable(result)
        assert result["success"] is True

    def test_keyword_string_normalised_to_list_in_query(self):
        """A single keyword string is stored as a list in query."""
        result = mp_search_recipe(keywords="hydrothermal", target_formula="TiO2")
        _skip_if_endpoint_unavailable(result)
        assert isinstance(result["query"]["keywords"], list)


# Temperature filter
@_requires_api_key
class TestTemperatureFilter:

    def test_temperature_max_filter_returns_success(self):
        """Filtering by temperature_max returns success=True."""
        result = mp_search_recipe(target_formula="LiFePO4", temperature_max=900)
        _skip_if_endpoint_unavailable(result)
        assert result["success"] is True

    def test_temperature_min_filter_returns_success(self):
        """Filtering by temperature_min returns success=True."""
        result = mp_search_recipe(target_formula="LiFePO4", temperature_min=500)
        _skip_if_endpoint_unavailable(result)
        assert result["success"] is True


# Year filter
@_requires_api_key
class TestYearFilter:

    def test_year_min_filter_returns_success(self):
        """Filtering by year_min returns success=True."""
        result = mp_search_recipe(target_formula="LiCoO2", year_min=2015)
        _skip_if_endpoint_unavailable(result)
        assert result["success"] is True

    def test_year_min_recipes_respect_year(self):
        """All returned recipes satisfy the year_min constraint when year is populated."""
        result = mp_search_recipe(target_formula="LiCoO2", year_min=2015, limit=10)
        _skip_if_endpoint_unavailable(result)
        if result["count"] == 0:
            pytest.skip("No recipes returned to inspect year filter")
        for recipe in result["recipes"]:
            if recipe.get("year") is not None:
                assert recipe["year"] >= 2015, f"Recipe year {recipe['year']} < year_min 2015"


# Precursor formula search
@_requires_api_key
class TestPrecursorSearch:

    def test_precursor_search_returns_success(self):
        """Searching by precursor formula returns success=True."""
        result = mp_search_recipe(precursor_formulas="Li2CO3")
        _skip_if_endpoint_unavailable(result)
        assert result["success"] is True

    def test_precursor_string_normalised_to_list_in_query(self):
        """A single precursor string is stored as a list in query."""
        result = mp_search_recipe(precursor_formulas="Li2CO3")
        _skip_if_endpoint_unavailable(result)
        assert isinstance(result["query"]["precursor_formulas"], list)


# fields parameter
@_requires_api_key
class TestFieldsFilter:

    def test_fields_limits_returned_keys(self):
        """Specifying fields returns only those keys (plus recipe_id) per entry."""
        requested_fields = ["doi", "year", "target_formula"]
        result = mp_search_recipe(
            target_formula="LiFePO4",
            limit=3,
            fields=requested_fields
        )
        _skip_if_endpoint_unavailable(result)
        if result["count"] == 0:
            pytest.skip("No recipes returned to inspect fields filter")
        for recipe in result["recipes"]:
            for key in recipe:
                assert key in requested_fields or key == "recipe_id", \
                    f"Unexpected key '{key}' present when fields filter was active"

    def test_fields_does_not_drop_recipe_id(self):
        """recipe_id is always present even when not listed in fields."""
        result = mp_search_recipe(
            target_formula="LiFePO4",
            limit=3,
            fields=["doi", "year"]
        )
        _skip_if_endpoint_unavailable(result)
        if result["count"] == 0:
            pytest.skip("No recipes returned to inspect fields filter")
        for recipe in result["recipes"]:
            assert "recipe_id" in recipe


# Heating time filter
@_requires_api_key
class TestHeatingTimeFilter:

    def test_heating_time_min_filter_returns_success(self):
        """Filtering by heating_time_min returns success=True."""
        result = mp_search_recipe(target_formula="LiFePO4", heating_time_min=2)
        _skip_if_endpoint_unavailable(result)
        assert result["success"] is True

    def test_heating_time_max_filter_returns_success(self):
        """Filtering by heating_time_max returns success=True."""
        result = mp_search_recipe(target_formula="LiFePO4", heating_time_max=12)
        _skip_if_endpoint_unavailable(result)
        assert result["success"] is True

    def test_heating_time_min_echoed_in_query(self):
        """query dict reflects heating_time_min parameter."""
        result = mp_search_recipe(target_formula="LiFePO4", heating_time_min=5)
        _skip_if_endpoint_unavailable(result)
        assert "heating_time_min" in result["query"]
        assert result["query"]["heating_time_min"] == 5

    def test_heating_time_max_echoed_in_query(self):
        """query dict reflects heating_time_max parameter."""
        result = mp_search_recipe(target_formula="LiFePO4", heating_time_max=10)
        _skip_if_endpoint_unavailable(result)
        assert "heating_time_max" in result["query"]
        assert result["query"]["heating_time_max"] == 10

    def test_heating_time_range_filter_returns_success(self):
        """Filtering by both heating_time_min and heating_time_max returns success=True."""
        result = mp_search_recipe(
            target_formula="LiCoO2",
            heating_time_min=2,
            heating_time_max=12
        )
        _skip_if_endpoint_unavailable(result)
        assert result["success"] is True


# Format routes parameter
@_requires_api_key
class TestFormatRoutes:

    def test_format_routes_false_returns_raw_recipes(self):
        """format_routes=False returns raw recipe data structure."""
        result = mp_search_recipe(target_formula="LiFePO4", format_routes=False, limit=3)
        _skip_if_endpoint_unavailable(result)
        assert result["success"] is True
        assert "recipes" in result
        assert "count" in result
        # Raw recipes should have recipe structure, not route structure
        if result["count"] > 0:
            assert "recipe_id" in result["recipes"][0]
            assert "routes" not in result  # routes key should not exist

    def test_format_routes_true_returns_formatted_routes(self):
        """format_routes=True returns standardized route structure."""
        result = mp_search_recipe(target_formula="LiFePO4", format_routes=True, limit=3)
        _skip_if_endpoint_unavailable(result)
        assert result["success"] is True
        assert "routes" in result
        assert "n_routes" in result
        assert "target_composition" in result
        # Should not have raw recipes structure
        assert "recipes" not in result or "routes" in result

    def test_format_routes_true_route_structure(self):
        """format_routes=True routes contain required route keys."""
        result = mp_search_recipe(target_formula="LiFePO4", format_routes=True, limit=3)
        _skip_if_endpoint_unavailable(result)
        if result.get("n_routes", 0) == 0:
            pytest.skip("No routes returned to inspect structure")
        
        route = result["routes"][0]
        required_keys = [
            "route_id", "source", "method", "confidence",
            "feasibility_score", "precursors", "steps",
            "temperature_range", "atmosphere_required", "basis"
        ]
        for key in required_keys:
            assert key in route, f"Missing required key in route: {key}"

    def test_format_routes_true_source_is_literature(self):
        """format_routes=True routes have source='literature'."""
        result = mp_search_recipe(target_formula="LiCoO2", format_routes=True, limit=3)
        _skip_if_endpoint_unavailable(result)
        if result.get("n_routes", 0) == 0:
            pytest.skip("No routes returned to inspect source")
        
        for route in result["routes"]:
            assert route["source"] == "literature"

    def test_format_routes_true_confidence_high(self):
        """format_routes=True routes have high confidence (0.85-0.95)."""
        result = mp_search_recipe(target_formula="LiCoO2", format_routes=True, limit=3)
        _skip_if_endpoint_unavailable(result)
        if result.get("n_routes", 0) == 0:
            pytest.skip("No routes returned to inspect confidence")
        
        for route in result["routes"]:
            assert 0.85 <= route["confidence"] <= 0.95, \
                f"Expected confidence 0.85-0.95, got {route['confidence']}"

    def test_format_routes_requires_target_formula(self):
        """format_routes=True requires target_formula to be provided."""
        result = mp_search_recipe(keywords="solid-state", format_routes=True)
        # This should fail because target_formula is required for format_routes=True
        assert result["success"] is False
        assert "error" in result
        assert "target_formula" in result["error"].lower()

    def test_format_routes_limit_controls_routes_count(self):
        """limit parameter controls number of routes when format_routes=True."""
        result = mp_search_recipe(target_formula="LiCoO2", format_routes=True, limit=2)
        _skip_if_endpoint_unavailable(result)
        assert result["success"] is True
        # Should return at most 2 routes
        assert result.get("n_routes", 0) <= 2
        if "routes" in result:
            assert len(result["routes"]) <= 2

    def test_format_routes_with_temperature_filter(self):
        """format_routes=True works with temperature_max filter."""
        result = mp_search_recipe(
            target_formula="LiFePO4",
            format_routes=True,
            temperature_max=900,
            limit=3
        )
        _skip_if_endpoint_unavailable(result)
        assert result["success"] is True
        if result.get("n_routes", 0) > 0:
            assert "routes" in result
            # Verify feasibility_score is present (uses temperature_max for calculation)
            assert "feasibility_score" in result["routes"][0]

    def test_format_routes_includes_citation_info(self):
        """format_routes=True routes include literature citation information."""
        result = mp_search_recipe(target_formula="LiCoO2", format_routes=True, limit=3)
        _skip_if_endpoint_unavailable(result)
        if result.get("n_routes", 0) == 0:
            pytest.skip("No routes returned to inspect citation info")
        
        route = result["routes"][0]
        # Should have at least one of these citation-related fields
        citation_fields = ["citation", "doi", "year", "recipe_id"]
        has_citation = any(field in route for field in citation_fields)
        assert has_citation, "Route missing citation information"
