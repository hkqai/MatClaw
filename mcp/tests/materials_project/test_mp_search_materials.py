"""
Tests for mp_search_materials tool.

These tests make real HTTP requests to the Materials Project API. Both an internet
connection and a valid MP_API_KEY environment variable are required.

Well-known stable materials are used for consistent results:
    - Silicon     mp-149    Si         cubic
    - NaCl        mp-22862  NaCl       cubic
    - LiFePO4     mp-19017  LiFePO4    orthorhombic

Run with: pytest tests/materials_project/test_mp_search_materials.py -v
Skip automatically when MP_API_KEY is not set.
"""

import os
import pytest
from tools.materials_project.mp_search_materials import mp_search_materials


# Reusable skip marker applied to every class that needs a live API key
_requires_api_key = pytest.mark.skipif(
    not os.getenv("MP_API_KEY"),
    reason="MP_API_KEY environment variable not set"
)


# Basic formula search
@_requires_api_key
class TestFormulaSearch:

    def test_silicon_formula_success(self):
        """Searching for 'Si' by formula returns success=True."""
        result = mp_search_materials(formula="Si")
        assert result["success"] is True

    def test_silicon_formula_count_nonzero(self):
        """Searching for 'Si' returns at least one material."""
        result = mp_search_materials(formula="Si")
        assert result["count"] >= 1

    def test_silicon_mp149_present(self):
        """The canonical silicon entry mp-149 is present in results."""
        result = mp_search_materials(formula="Si", max_results=50)
        material_ids = [str(m["material_id"]) for m in result["materials"]]
        assert "mp-149" in material_ids

    def test_silicon_formula_field(self):
        """mp-149 entry reports formula as 'Si'."""
        result = mp_search_materials(formula="Si", max_results=50)
        si = next(m for m in result["materials"] if str(m["material_id"]) == "mp-149")
        assert si["formula"] == "Si"

    def test_silicon_cubic_crystal_system(self):
        """mp-149 silicon has a cubic crystal system."""
        result = mp_search_materials(formula="Si", max_results=50)
        si = next(m for m in result["materials"] if str(m["material_id"]) == "mp-149")
        assert si["crystal_system"].lower() == "cubic"

    def test_lifep04_formula_success(self):
        """Searching for 'LiFePO4' returns success=True."""
        result = mp_search_materials(formula="LiFePO4")
        assert result["success"] is True

    def test_nacl_formula_success(self):
        """Searching for 'NaCl' returns success=True."""
        result = mp_search_materials(formula="NaCl")
        assert result["success"] is True


# Response structure
@_requires_api_key
class TestResponseStructure:

    def test_success_key_present(self):
        """Response always contains 'success' key."""
        result = mp_search_materials(formula="Si")
        assert "success" in result

    def test_count_key_present(self):
        """Response always contains 'count' key."""
        result = mp_search_materials(formula="Si")
        assert "count" in result

    def test_materials_key_is_list(self):
        """Response always contains 'materials' as a list."""
        result = mp_search_materials(formula="Si")
        assert "materials" in result
        assert isinstance(result["materials"], list)

    def test_query_dict_present(self):
        """Response always contains 'query' dict."""
        result = mp_search_materials(formula="Si")
        assert "query" in result
        assert isinstance(result["query"], dict)

    def test_query_echoes_formula(self):
        """query.formula reflects the search term passed in."""
        result = mp_search_materials(formula="Si")
        assert result["query"]["formula"] == "Si"

    def test_query_echoes_max_results(self):
        """query.max_results reflects the limit passed in."""
        result = mp_search_materials(formula="Si", max_results=3)
        assert result["query"]["max_results"] == 3

    def test_material_entry_has_required_keys(self):
        """Each material entry contains the expected core keys."""
        result = mp_search_materials(formula="Si", max_results=1)
        entry = result["materials"][0]
        for key in ("material_id", "formula", "crystal_system", "band_gap",
                    "is_metal", "is_stable", "energy_above_hull",
                    "formation_energy_per_atom", "elements"):
            assert key in entry, f"Missing key: {key}"

    def test_count_matches_materials_length(self):
        """count equals the length of the materials list."""
        result = mp_search_materials(formula="Si", max_results=5)
        assert result["count"] == len(result["materials"])


# max_results limit
@_requires_api_key
class TestMaxResults:

    def test_max_results_respected(self):
        """Materials list length does not exceed max_results."""
        result = mp_search_materials(formula="TiO2", max_results=3)
        assert len(result["materials"]) <= 3

    def test_max_results_one(self):
        """max_results=1 returns exactly one material."""
        result = mp_search_materials(formula="Si", max_results=1)
        assert result["count"] == 1
        assert len(result["materials"]) == 1


# Filters
@_requires_api_key
class TestFilters:

    def test_is_stable_filter(self):
        """is_stable=True returns only thermodynamically stable materials."""
        result = mp_search_materials(formula="TiO2", is_stable=True, max_results=10)
        assert result["success"] is True
        for m in result["materials"]:
            assert m["is_stable"] is True

    def test_crystal_system_filter_cubic(self):
        """crystal_system='cubic' returns only cubic materials."""
        result = mp_search_materials(
            formula="NaCl", crystal_system="cubic", max_results=10
        )
        assert result["success"] is True
        for m in result["materials"]:
            assert m["crystal_system"].lower() == "cubic"

    def test_elements_filter(self):
        """elements filter returns materials containing all specified elements."""
        result = mp_search_materials(
            elements=["Li", "Fe", "P", "O"], max_results=5
        )
        assert result["success"] is True
        for m in result["materials"]:
            element_set = set(m["elements"])
            for el in ("Li", "Fe", "P", "O"):
                assert el in element_set

    def test_chemsys_filter(self):
        """chemsys='Na-Cl' returns NaCl-system materials."""
        result = mp_search_materials(chemsys="Na-Cl", max_results=10)
        assert result["success"] is True
        for m in result["materials"]:
            element_set = set(m["elements"])
            assert element_set <= {"Na", "Cl"}

    def test_band_gap_range_filter(self):
        """band_gap_min/max filter returns materials within that range."""
        result = mp_search_materials(
            band_gap_min=1.0, band_gap_max=2.0, max_results=10
        )
        assert result["success"] is True
        for m in result["materials"]:
            bg = m["band_gap"]
            if bg != "N/A":
                assert 1.0 <= float(bg) <= 2.0


# No results (requires API key)
@_requires_api_key
class TestNoResults:

    def test_no_results_success_false(self):
        """A search that matches nothing returns success=False."""
        result = mp_search_materials(
            formula="XeRnAuPt",  # nonsensical formula
        )
        assert result["success"] is False

    def test_no_results_error_key(self):
        """A search that matches nothing includes an 'error' key."""
        result = mp_search_materials(formula="XeRnAuPt")
        assert "error" in result
        assert isinstance(result["error"], str)
        assert len(result["error"]) > 0


# Missing API key (always runs)
class TestMissingApiKey:

    def test_missing_api_key_returns_error(self, monkeypatch):
        """Missing MP_API_KEY returns success=False with an informative error."""
        monkeypatch.delenv("MP_API_KEY", raising=False)
        result = mp_search_materials(formula="Si")
        assert result["success"] is False
        assert "error" in result
        assert "MP_API_KEY" in result["error"]
