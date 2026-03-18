"""
Tests for mp_get_material_properties tool.

These tests make real HTTP requests to the Materials Project API. Both an internet
connection and a valid MP_API_KEY environment variable are required.

Well-known stable materials are used for consistent results:
    - Silicon     mp-149    Si         cubic,        band gap ~1.1 eV
    - NaCl        mp-22862  NaCl       cubic,        insulator
    - LiFePO4     mp-19017  LiFePO4    orthorhombic, stable cathode

Run with: pytest tests/test_mp/test_mp_get_material_properties.py -v
Skip automatically when MP_API_KEY is not set.
"""

import os
import pytest
from tools.materials_project.mp_get_material_properties import mp_get_material_properties


# Reusable skip marker applied to every class that needs a live API key
_requires_api_key = pytest.mark.skipif(
    not os.getenv("MP_API_KEY"),
    reason="MP_API_KEY environment variable not set"
)


# ---------------------------------------------------------------------------
# Missing API key (always runs)
# ---------------------------------------------------------------------------

class TestMissingApiKey:

    def test_missing_api_key_returns_error(self, monkeypatch):
        """Missing MP_API_KEY returns success=False with an informative error."""
        monkeypatch.delenv("MP_API_KEY", raising=False)
        result = mp_get_material_properties(material_ids="mp-149")
        assert result["success"] is False
        assert "error" in result
        assert "MP_API_KEY" in result["error"]


# ---------------------------------------------------------------------------
# Top-level response structure
# ---------------------------------------------------------------------------

@_requires_api_key
class TestResponseStructure:

    def test_success_key_present(self):
        """Response always contains 'success' key."""
        result = mp_get_material_properties(material_ids="mp-149")
        assert "success" in result

    def test_count_key_present(self):
        """Response always contains 'count' key."""
        result = mp_get_material_properties(material_ids="mp-149")
        assert "count" in result

    def test_properties_key_is_list(self):
        """Response always contains 'properties' as a list."""
        result = mp_get_material_properties(material_ids="mp-149")
        assert "properties" in result
        assert isinstance(result["properties"], list)

    def test_requested_material_ids_echoed(self):
        """requested_material_ids reflects the IDs passed in."""
        result = mp_get_material_properties(material_ids="mp-149")
        assert "requested_material_ids" in result
        assert "mp-149" in result["requested_material_ids"]

    def test_requested_property_categories_echoed(self):
        """requested_property_categories reflects the categories passed in."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["basic", "electronic"]
        )
        assert "requested_property_categories" in result
        assert set(result["requested_property_categories"]) == {"basic", "electronic"}

    def test_single_material_count_is_one(self):
        """Fetching one material ID returns count == 1."""
        result = mp_get_material_properties(material_ids="mp-149")
        assert result["count"] == 1
        assert len(result["properties"]) == 1

    def test_count_matches_properties_length(self):
        """count equals the length of the properties list."""
        result = mp_get_material_properties(
            material_ids=["mp-149", "mp-22862"]
        )
        assert result["count"] == len(result["properties"])


# ---------------------------------------------------------------------------
# Default property categories
# ---------------------------------------------------------------------------

@_requires_api_key
class TestDefaultProperties:

    def test_default_returns_success(self):
        """Calling with no properties argument returns success=True."""
        result = mp_get_material_properties(material_ids="mp-149")
        assert result["success"] is True

    def test_default_includes_basic_category(self):
        """Default call populates the 'basic' sub-dict."""
        result = mp_get_material_properties(material_ids="mp-149")
        entry = result["properties"][0]
        assert "basic" in entry

    def test_default_includes_electronic_category(self):
        """Default call populates the 'electronic' sub-dict."""
        result = mp_get_material_properties(material_ids="mp-149")
        entry = result["properties"][0]
        assert "electronic" in entry

    def test_default_includes_thermodynamic_category(self):
        """Default call populates the 'thermodynamic' sub-dict."""
        result = mp_get_material_properties(material_ids="mp-149")
        entry = result["properties"][0]
        assert "thermodynamic" in entry


# ---------------------------------------------------------------------------
# Basic properties category
# ---------------------------------------------------------------------------

@_requires_api_key
class TestBasicProperties:

    def test_silicon_formula(self):
        """mp-149 'basic' sub-dict reports formula as 'Si'."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["basic"]
        )
        basic = result["properties"][0]["basic"]
        assert basic["formula"] == "Si"

    def test_basic_required_keys(self):
        """'basic' sub-dict contains all expected keys."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["basic"]
        )
        basic = result["properties"][0]["basic"]
        for key in ("formula", "elements", "nelements", "nsites", "density",
                    "volume", "theoretical"):
            assert key in basic, f"Missing key in basic: {key}"

    def test_silicon_element_list(self):
        """mp-149 'basic' reports elements as ['Si']."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["basic"]
        )
        basic = result["properties"][0]["basic"]
        assert basic["elements"] == ["Si"]

    def test_silicon_nelements_is_one(self):
        """mp-149 has nelements == 1."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["basic"]
        )
        assert result["properties"][0]["basic"]["nelements"] == 1


# ---------------------------------------------------------------------------
# Structure properties category
# ---------------------------------------------------------------------------

@_requires_api_key
class TestStructureProperties:

    def test_silicon_crystal_system(self):
        """mp-149 reports crystal_system as 'cubic'."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["structure"]
        )
        structure = result["properties"][0]["structure"]
        assert structure["crystal_system"].lower() == "cubic"

    def test_structure_required_keys(self):
        """'structure' sub-dict contains all expected keys."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["structure"]
        )
        structure = result["properties"][0]["structure"]
        for key in ("crystal_system", "space_group_symbol", "space_group_number",
                    "lattice_parameters", "sites"):
            assert key in structure, f"Missing key in structure: {key}"

    def test_lattice_parameters_keys(self):
        """lattice_parameters contains a, b, c, alpha, beta, gamma, volume."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["structure"]
        )
        lp = result["properties"][0]["structure"]["lattice_parameters"]
        for key in ("a", "b", "c", "alpha", "beta", "gamma", "volume"):
            assert key in lp, f"Missing lattice key: {key}"

    def test_silicon_sites_is_list(self):
        """mp-149 sites is a non-empty list."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["structure"]
        )
        sites = result["properties"][0]["structure"]["sites"]
        assert isinstance(sites, list)
        assert len(sites) > 0


# ---------------------------------------------------------------------------
# Electronic properties category
# ---------------------------------------------------------------------------

@_requires_api_key
class TestElectronicProperties:

    def test_silicon_band_gap_positive(self):
        """mp-149 has a positive band gap (semiconductor)."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["electronic"]
        )
        electronic = result["properties"][0]["electronic"]
        assert electronic["band_gap"] is not None
        assert electronic["band_gap"] > 0

    def test_silicon_is_not_metal(self):
        """mp-149 is_metal is False."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["electronic"]
        )
        assert result["properties"][0]["electronic"]["is_metal"] is False

    def test_electronic_required_keys(self):
        """'electronic' sub-dict contains the expected keys."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["electronic"]
        )
        electronic = result["properties"][0]["electronic"]
        for key in ("band_gap", "is_gap_direct", "is_metal"):
            assert key in electronic, f"Missing key in electronic: {key}"


# ---------------------------------------------------------------------------
# Thermodynamic properties category
# ---------------------------------------------------------------------------

@_requires_api_key
class TestThermodynamicProperties:

    def test_silicon_is_stable(self):
        """mp-149 silicon is thermodynamically stable."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["thermodynamic"]
        )
        thermo = result["properties"][0]["thermodynamic"]
        assert thermo.get("is_stable") is True

    def test_silicon_energy_above_hull_is_zero(self):
        """mp-149 energy_above_hull is 0.0 eV/atom (on the hull)."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["thermodynamic"]
        )
        thermo = result["properties"][0]["thermodynamic"]
        assert thermo.get("energy_above_hull") == 0.0

    def test_thermodynamic_required_keys(self):
        """'thermodynamic' sub-dict contains the expected keys."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["thermodynamic"]
        )
        thermo = result["properties"][0]["thermodynamic"]
        for key in ("formation_energy_per_atom", "energy_above_hull",
                    "is_stable", "functional"):
            assert key in thermo, f"Missing key in thermodynamic: {key}"


# ---------------------------------------------------------------------------
# Mechanical properties category
# ---------------------------------------------------------------------------

@_requires_api_key
class TestMechanicalProperties:

    def test_silicon_bulk_modulus_positive(self):
        """mp-149 bulk_modulus_vrh is a positive number (GPa)."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["mechanical"]
        )
        mech = result["properties"][0]["mechanical"]
        # Data may not always be available; skip gracefully if absent
        if "info" not in mech:
            assert mech["bulk_modulus_vrh"] is not None
            assert mech["bulk_modulus_vrh"] > 0

    def test_mechanical_required_keys_when_available(self):
        """'mechanical' sub-dict contains expected keys when data exists."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["mechanical"]
        )
        mech = result["properties"][0]["mechanical"]
        if "info" not in mech:
            for key in ("bulk_modulus_vrh", "shear_modulus_vrh",
                        "poisson_ratio", "elastic_tensor_available"):
                assert key in mech, f"Missing key in mechanical: {key}"


# ---------------------------------------------------------------------------
# 'all' properties keyword
# ---------------------------------------------------------------------------

@_requires_api_key
class TestAllProperties:

    def test_all_keyword_returns_success(self):
        """properties=['all'] returns success=True."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["all"]
        )
        assert result["success"] is True

    def test_all_keyword_includes_extended_categories(self):
        """properties=['all'] expands to include dielectric, phonon, etc."""
        result = mp_get_material_properties(
            material_ids="mp-149", properties=["all"]
        )
        cats = result["requested_property_categories"]
        for cat in ("dielectric", "surface", "phonon", "eos", "xas"):
            assert cat in cats, f"Expected category '{cat}' missing from 'all' expansion"


# ---------------------------------------------------------------------------
# Multiple material IDs
# ---------------------------------------------------------------------------

@_requires_api_key
class TestMultipleMaterials:

    def test_two_materials_returns_two_entries(self):
        """Passing two material IDs returns exactly two property dicts."""
        result = mp_get_material_properties(
            material_ids=["mp-149", "mp-22862"]
        )
        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["properties"]) == 2

    def test_two_materials_correct_ids(self):
        """Each returned entry carries its own material_id."""
        result = mp_get_material_properties(
            material_ids=["mp-149", "mp-22862"]
        )
        returned_ids = {entry["material_id"] for entry in result["properties"]}
        assert "mp-149" in returned_ids
        assert "mp-22862" in returned_ids

    def test_lifep04_basic_formula(self):
        """mp-19017 'basic' sub-dict reports formula as 'LiFePO4'."""
        result = mp_get_material_properties(
            material_ids="mp-19017", properties=["basic"]
        )
        basic = result["properties"][0]["basic"]
        assert basic["formula"] == "LiFePO4"
