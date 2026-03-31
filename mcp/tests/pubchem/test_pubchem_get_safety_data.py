"""
Tests for pubchem_get_safety_data tool.

These tests make real HTTP requests to PubChem. An internet connection is
required. Well-known compounds with documented safety data are used:
    - Ethanol       CID 702    (flammable, common safety data)
    - Aspirin       CID 2244   (drug, health hazard data)
    - Benzene       CID 241    (carcinogen, toxic)
    - Formaldehyde  CID 712    (carcinogen, high hazard)
    - Acetone       CID 180    (flammable, irritant)

Run with: pytest tests/pubchem/test_pubchem_get_safety_data.py -v
"""

import pytest
from tools.pubchem.pubchem_get_safety_data import (
    pubchem_get_safety_data,
)


# Basic single-CID retrieval
class TestBasicRetrieval:

    def test_single_cid_int_success(self):
        """Passing a single integer CID for ethanol returns success=True."""
        result = pubchem_get_safety_data(cids=702)
        assert result["success"] is True

    def test_single_cid_int_count_one(self):
        """Passing a single integer CID returns count=1."""
        result = pubchem_get_safety_data(cids=702)
        assert result["count"] == 1

    def test_single_cid_returns_one_safety_dict(self):
        """Safety_data list contains exactly one entry for a single CID."""
        result = pubchem_get_safety_data(cids=702)
        assert isinstance(result["safety_data"], list)
        assert len(result["safety_data"]) == 1

    def test_cid_echoed_in_safety_dict(self):
        """The CID field in the returned safety dict matches the requested CID."""
        result = pubchem_get_safety_data(cids=702)
        assert result["safety_data"][0]["CID"] == 702

    def test_ethanol_has_compound_name(self):
        """Ethanol (CID 702) returns a compound name."""
        result = pubchem_get_safety_data(cids=702)
        compound_name = result["safety_data"][0].get("compound_name", "")
        assert compound_name != "N/A"
        assert len(compound_name) > 0

    def test_multiple_cids_list_success(self):
        """Passing multiple CIDs as a list returns multiple safety entries."""
        result = pubchem_get_safety_data(cids=[702, 2244, 180])
        assert result["success"] is True
        assert result["count"] == 3
        assert len(result["safety_data"]) == 3


# Response structure
class TestResponseStructure:

    def test_success_key_present(self):
        """Result has a 'success' key."""
        result = pubchem_get_safety_data(cids=702)
        assert "success" in result

    def test_count_key_present(self):
        """Result has a 'count' key."""
        result = pubchem_get_safety_data(cids=702)
        assert "count" in result

    def test_safety_data_key_present(self):
        """Result has a 'safety_data' key."""
        result = pubchem_get_safety_data(cids=702)
        assert "safety_data" in result

    def test_requested_cids_key_present(self):
        """Result has a 'requested_cids' key."""
        result = pubchem_get_safety_data(cids=702)
        assert "requested_cids" in result

    def test_requested_sections_key_present(self):
        """Result has a 'requested_sections' key."""
        result = pubchem_get_safety_data(cids=702)
        assert "requested_sections" in result

    def test_safety_data_list_type(self):
        """The 'safety_data' value is a list."""
        result = pubchem_get_safety_data(cids=702)
        assert isinstance(result["safety_data"], list)

    def test_requested_cids_list_type(self):
        """The 'requested_cids' value is a list."""
        result = pubchem_get_safety_data(cids=702)
        assert isinstance(result["requested_cids"], list)

    def test_requested_sections_list_type(self):
        """The 'requested_sections' value is a list."""
        result = pubchem_get_safety_data(cids=702)
        assert isinstance(result["requested_sections"], list)


# GHS Classification tests
class TestGHSClassification:

    def test_ghs_section_present_ethanol(self):
        """Ethanol safety data includes GHS section."""
        result = pubchem_get_safety_data(cids=702, include_sections=["ghs"])
        safety_data = result["safety_data"][0]
        assert "ghs" in safety_data

    def test_ghs_has_hazard_codes_ethanol(self):
        """Ethanol GHS data includes hazard codes (flammable liquid)."""
        result = pubchem_get_safety_data(cids=702, include_sections=["ghs"])
        ghs = result["safety_data"][0]["ghs"]
        if ghs.get("available"):
            assert "hazard_codes" in ghs
            # Ethanol should have H225 (Highly flammable liquid)
            hazard_codes_str = " ".join(ghs.get("hazard_codes", []))
            assert "H2" in hazard_codes_str or len(ghs["hazard_codes"]) > 0

    def test_ghs_has_signal_word_ethanol(self):
        """Ethanol GHS data includes signal word."""
        result = pubchem_get_safety_data(cids=702, include_sections=["ghs"])
        ghs = result["safety_data"][0]["ghs"]
        if ghs.get("available"):
            assert "signal_word" in ghs
            signal = ghs["signal_word"]
            # Ethanol typically has "Danger" or "Warning"
            assert signal in ["Danger", "Warning", "N/A"]

    def test_benzene_has_carcinogen_codes(self):
        """Benzene (CID 241) should have carcinogenicity hazard codes."""
        result = pubchem_get_safety_data(cids=241, include_sections=["ghs"])
        ghs = result["safety_data"][0]["ghs"]
        if ghs.get("available"):
            hazard_codes = ghs.get("hazard_codes", [])
            # Benzene should have H350 (May cause cancer) or H340 (mutagenicity)
            hazard_str = " ".join([str(code).upper() for code in hazard_codes])
            assert "H3" in hazard_str  # H3xx codes are health hazards


# Toxicity tests
class TestToxicityData:

    def test_toxicity_section_present(self):
        """Safety data includes toxicity section when requested."""
        result = pubchem_get_safety_data(cids=702, include_sections=["toxicity"])
        safety_data = result["safety_data"][0]
        assert "toxicity" in safety_data

    def test_toxicity_has_expected_fields(self):
        """Toxicity section has expected fields (ld50_oral, etc.)."""
        result = pubchem_get_safety_data(cids=702, include_sections=["toxicity"])
        toxicity = result["safety_data"][0]["toxicity"]
        assert "ld50_oral" in toxicity
        assert "ld50_dermal" in toxicity
        assert "lc50_inhalation" in toxicity
        assert "other_toxicity" in toxicity

    def test_toxicity_fields_are_lists(self):
        """Toxicity fields are lists."""
        result = pubchem_get_safety_data(cids=702, include_sections=["toxicity"])
        toxicity = result["safety_data"][0]["toxicity"]
        assert isinstance(toxicity["ld50_oral"], list)
        assert isinstance(toxicity["ld50_dermal"], list)
        assert isinstance(toxicity["lc50_inhalation"], list)
        assert isinstance(toxicity["other_toxicity"], list)


# Physical hazards tests
class TestPhysicalHazards:

    def test_physical_hazards_section_present(self):
        """Safety data includes physical_hazards section when requested."""
        result = pubchem_get_safety_data(cids=702, include_sections=["physical_hazards"])
        safety_data = result["safety_data"][0]
        assert "physical_hazards" in safety_data

    def test_physical_hazards_has_expected_fields(self):
        """Physical hazards section has expected fields."""
        result = pubchem_get_safety_data(cids=702, include_sections=["physical_hazards"])
        hazards = result["safety_data"][0]["physical_hazards"]
        assert "flash_point" in hazards
        assert "autoignition_temperature" in hazards
        assert "flammability" in hazards
        assert "explosive_properties" in hazards
        assert "oxidizing_properties" in hazards


# Health hazards tests
class TestHealthHazards:

    def test_health_hazards_section_present(self):
        """Safety data includes health_hazards section when requested."""
        result = pubchem_get_safety_data(cids=702, include_sections=["health_hazards"])
        safety_data = result["safety_data"][0]
        assert "health_hazards" in safety_data

    def test_health_hazards_has_expected_fields(self):
        """Health hazards section has expected fields."""
        result = pubchem_get_safety_data(cids=702, include_sections=["health_hazards"])
        hazards = result["safety_data"][0]["health_hazards"]
        assert "carcinogenicity" in hazards
        assert "mutagenicity" in hazards
        assert "reproductive_toxicity" in hazards
        assert "specific_target_organ_toxicity" in hazards
        assert "other_health_effects" in hazards


# Environmental hazards tests
class TestEnvironmentalHazards:

    def test_environmental_hazards_section_present(self):
        """Safety data includes environmental_hazards section when requested."""
        result = pubchem_get_safety_data(cids=702, include_sections=["environmental_hazards"])
        safety_data = result["safety_data"][0]
        assert "environmental_hazards" in safety_data

    def test_environmental_hazards_has_expected_fields(self):
        """Environmental hazards section has expected fields."""
        result = pubchem_get_safety_data(cids=702, include_sections=["environmental_hazards"])
        hazards = result["safety_data"][0]["environmental_hazards"]
        assert "aquatic_toxicity" in hazards
        assert "bioaccumulation" in hazards
        assert "persistence" in hazards
        assert "other_environmental_effects" in hazards


# Exposure limits tests
class TestExposureLimits:

    def test_exposure_limits_section_present(self):
        """Safety data includes exposure_limits section when requested."""
        result = pubchem_get_safety_data(cids=702, include_sections=["exposure_limits"])
        safety_data = result["safety_data"][0]
        assert "exposure_limits" in safety_data

    def test_exposure_limits_has_expected_fields(self):
        """Exposure limits section has expected fields."""
        result = pubchem_get_safety_data(cids=702, include_sections=["exposure_limits"])
        limits = result["safety_data"][0]["exposure_limits"]
        assert "osha_pel" in limits
        assert "niosh_rel" in limits
        assert "acgih_tlv" in limits
        assert "other_limits" in limits


# Handling and storage tests
class TestHandlingStorage:

    def test_handling_storage_section_present(self):
        """Safety data includes handling_storage section when requested."""
        result = pubchem_get_safety_data(cids=702, include_sections=["handling_storage"])
        safety_data = result["safety_data"][0]
        assert "handling_storage" in safety_data

    def test_handling_storage_has_expected_fields(self):
        """Handling/storage section has expected fields."""
        result = pubchem_get_safety_data(cids=702, include_sections=["handling_storage"])
        handling = result["safety_data"][0]["handling_storage"]
        assert "handling" in handling
        assert "storage" in handling
        assert "disposal" in handling


# Multiple sections test
class TestMultipleSections:

    def test_multiple_sections_all_present(self):
        """Requesting multiple sections returns all of them."""
        result = pubchem_get_safety_data(
            cids=702,
            include_sections=["ghs", "toxicity", "physical_hazards"]
        )
        safety_data = result["safety_data"][0]
        assert "ghs" in safety_data
        assert "toxicity" in safety_data
        assert "physical_hazards" in safety_data

    def test_default_sections_include_all(self):
        """Not specifying sections returns all available sections."""
        result = pubchem_get_safety_data(cids=702)
        safety_data = result["safety_data"][0]
        assert "ghs" in safety_data
        assert "toxicity" in safety_data
        assert "physical_hazards" in safety_data
        assert "health_hazards" in safety_data
        assert "environmental_hazards" in safety_data
        assert "exposure_limits" in safety_data
        assert "handling_storage" in safety_data


# Error handling tests
class TestErrorHandling:

    def test_invalid_cid_partial_success(self):
        """Invalid CID in list of CIDs results in partial success with warnings."""
        result = pubchem_get_safety_data(cids=[702, 999999999])
        # Should succeed for at least the valid CID
        assert result["count"] >= 1
        # May have warnings for invalid CID (depends on PubChem response)

    def test_invalid_section_name_ignored(self):
        """Invalid section name is handled gracefully."""
        result = pubchem_get_safety_data(
            cids=702,
            include_sections=["ghs", "invalid_section"]
        )
        # Should succeed and return GHS data
        assert result["success"] is True
        safety_data = result["safety_data"][0]
        assert "ghs" in safety_data
        # Invalid section should be ignored
        assert "invalid_section" not in safety_data

