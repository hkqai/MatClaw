"""
Tests for mp_get_detailed_property_data tool.

These tests make real HTTP requests to the Materials Project API. Both an internet
connection and a valid MP_API_KEY environment variable are required.

Well-known stable materials are used for consistent results:
    - Silicon     mp-149    Si    - band structure, DOS, elastic tensor, EOS, XAS
    - BaTiO3      mp-5020         - dielectric and piezoelectric data

Data-type availability varies by material. Tests for data types that may not be
present for a given material accept either a populated result or the "no data"
success=False response grace-fully; structural assertions are skipped only in
those cases via pytest.skip().

Run with: pytest tests/test_mp/test_mp_get_detailed_property_data.py -v
Skip automatically when MP_API_KEY is not set.
"""

import os
import pytest
from tools.materials_project.mp_get_detailed_property_data import mp_get_detailed_property_data


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
        result = mp_get_detailed_property_data("mp-149", "band_structure")
        assert result["success"] is False
        assert "error" in result
        assert "MP_API_KEY" in result["error"]


# ---------------------------------------------------------------------------
# Invalid / unknown data type
# ---------------------------------------------------------------------------

@_requires_api_key
class TestInvalidDataType:

    def test_unknown_data_type_returns_failure(self):
        """An unrecognised data_type returns success=False."""
        result = mp_get_detailed_property_data("mp-149", "totally_invalid_type")
        assert result["success"] is False

    def test_unknown_data_type_error_message(self):
        """Error message mentions the unrecognised data_type."""
        result = mp_get_detailed_property_data("mp-149", "totally_invalid_type")
        assert "error" in result
        assert "totally_invalid_type" in result["error"]

    def test_xas_without_element_returns_failure(self):
        """Requesting xas_spectrum without providing element returns success=False."""
        result = mp_get_detailed_property_data("mp-149", "xas_spectrum")
        assert result["success"] is False
        assert "error" in result
        assert "element" in result["error"].lower()


# ---------------------------------------------------------------------------
# Band structure  (mp-149 – Si)
# ---------------------------------------------------------------------------

@_requires_api_key
class TestBandStructure:

    def test_band_structure_success(self):
        """mp-149 returns success=True for band_structure."""
        result = mp_get_detailed_property_data("mp-149", "band_structure")
        assert result["success"] is True

    def test_band_structure_required_keys(self):
        """Band structure result contains all expected top-level keys."""
        result = mp_get_detailed_property_data("mp-149", "band_structure")
        for key in ("material_id", "kpoints", "labels", "branches", "bands",
                    "efermi", "is_spin_polarized", "is_metal", "plot_config"):
            assert key in result, f"Missing key: {key}"

    def test_band_structure_material_id_echoed(self):
        """material_id in response matches the requested ID."""
        result = mp_get_detailed_property_data("mp-149", "band_structure")
        assert result["material_id"] == "mp-149"

    def test_silicon_is_not_metal(self):
        """mp-149 is_metal is False in band structure result."""
        result = mp_get_detailed_property_data("mp-149", "band_structure")
        assert result["is_metal"] is False

    def test_band_structure_kpoints_is_list(self):
        """kpoints is a non-empty list."""
        result = mp_get_detailed_property_data("mp-149", "band_structure")
        assert isinstance(result["kpoints"], list)
        assert len(result["kpoints"]) > 0

    def test_band_structure_bands_is_dict(self):
        """bands is a non-empty dict (keyed by spin)."""
        result = mp_get_detailed_property_data("mp-149", "band_structure")
        assert isinstance(result["bands"], dict)
        assert len(result["bands"]) > 0

    def test_band_structure_plot_config_type(self):
        """plot_config.plot_type is 'line'."""
        result = mp_get_detailed_property_data("mp-149", "band_structure")
        assert result["plot_config"]["plot_type"] == "line"


# ---------------------------------------------------------------------------
# Density of states  (mp-149 – Si)
# ---------------------------------------------------------------------------

@_requires_api_key
class TestDos:

    def test_dos_success(self):
        """mp-149 returns success=True for dos."""
        result = mp_get_detailed_property_data("mp-149", "dos")
        assert result["success"] is True

    def test_dos_required_keys(self):
        """DOS result contains all expected top-level keys."""
        result = mp_get_detailed_property_data("mp-149", "dos")
        for key in ("material_id", "energies", "total_dos", "efermi",
                    "num_energy_points", "plot_config"):
            assert key in result, f"Missing key: {key}"

    def test_dos_energies_is_list(self):
        """energies is a non-empty list of numbers."""
        result = mp_get_detailed_property_data("mp-149", "dos")
        assert isinstance(result["energies"], list)
        assert len(result["energies"]) > 0

    def test_dos_num_energy_points_matches_list(self):
        """num_energy_points equals len(energies)."""
        result = mp_get_detailed_property_data("mp-149", "dos")
        assert result["num_energy_points"] == len(result["energies"])

    def test_dos_total_dos_is_dict(self):
        """total_dos is a dict keyed by spin."""
        result = mp_get_detailed_property_data("mp-149", "dos")
        assert isinstance(result["total_dos"], dict)
        assert len(result["total_dos"]) > 0

    def test_dos_plot_config_type(self):
        """plot_config.plot_type is 'area'."""
        result = mp_get_detailed_property_data("mp-149", "dos")
        assert result["plot_config"]["plot_type"] == "area"


# ---------------------------------------------------------------------------
# Elastic tensor  (mp-149 – Si)
# ---------------------------------------------------------------------------

@_requires_api_key
class TestElasticTensor:

    def test_elastic_tensor_success(self):
        """mp-149 returns success=True for elastic_tensor."""
        result = mp_get_detailed_property_data("mp-149", "elastic_tensor")
        assert result["success"] is True

    def test_elastic_tensor_required_keys(self):
        """Elastic tensor result contains all expected top-level keys."""
        result = mp_get_detailed_property_data("mp-149", "elastic_tensor")
        for key in ("material_id", "elastic_tensor", "units", "plot_config"):
            assert key in result, f"Missing key: {key}"

    def test_elastic_tensor_units(self):
        """Units are reported as GPa."""
        result = mp_get_detailed_property_data("mp-149", "elastic_tensor")
        assert result["units"] == "GPa"

    def test_elastic_tensor_is_6x6(self):
        """Elastic tensor is a 6×6 matrix when available."""
        result = mp_get_detailed_property_data("mp-149", "elastic_tensor")
        tensor = result["elastic_tensor"]
        if tensor is not None:
            assert len(tensor) == 6
            for row in tensor:
                assert len(row) == 6

    def test_elastic_tensor_plot_config_type(self):
        """plot_config.plot_type is 'heatmap'."""
        result = mp_get_detailed_property_data("mp-149", "elastic_tensor")
        assert result["plot_config"]["plot_type"] == "heatmap"


# ---------------------------------------------------------------------------
# EOS data  (mp-149 – Si)
# ---------------------------------------------------------------------------

@_requires_api_key
class TestEosData:

    def test_eos_data_success(self):
        """mp-149 returns success=True for eos_data."""
        result = mp_get_detailed_property_data("mp-149", "eos_data")
        assert result["success"] is True

    def test_eos_required_keys(self):
        """EOS result contains all expected top-level keys."""
        result = mp_get_detailed_property_data("mp-149", "eos_data")
        for key in ("material_id", "volumes", "energies", "num_points",
                    "units", "plot_config"):
            assert key in result, f"Missing key: {key}"

    def test_eos_volumes_is_list(self):
        """volumes is a non-empty list."""
        result = mp_get_detailed_property_data("mp-149", "eos_data")
        assert isinstance(result["volumes"], list)
        assert len(result["volumes"]) > 0

    def test_eos_energies_length_matches_volumes(self):
        """energies and volumes have the same length."""
        result = mp_get_detailed_property_data("mp-149", "eos_data")
        assert len(result["energies"]) == len(result["volumes"])

    def test_eos_num_points_matches_list(self):
        """num_points equals len(volumes)."""
        result = mp_get_detailed_property_data("mp-149", "eos_data")
        assert result["num_points"] == len(result["volumes"])

    def test_eos_plot_config_type(self):
        """plot_config.plot_type is 'scatter'."""
        result = mp_get_detailed_property_data("mp-149", "eos_data")
        assert result["plot_config"]["plot_type"] == "scatter"


# ---------------------------------------------------------------------------
# XAS spectrum  (mp-149 – Si K-edge XANES)
# ---------------------------------------------------------------------------

@_requires_api_key
class TestXasSpectrum:

    def test_xas_spectrum_success(self):
        """mp-149 Si K-edge XANES returns success=True."""
        result = mp_get_detailed_property_data(
            "mp-149", "xas_spectrum", element="Si", edge="K", spectrum_type="XANES"
        )
        assert result["success"] is True

    def test_xas_required_keys(self):
        """XAS result contains all expected top-level keys."""
        result = mp_get_detailed_property_data(
            "mp-149", "xas_spectrum", element="Si", edge="K", spectrum_type="XANES"
        )
        for key in ("material_id", "element", "edge", "spectrum_type",
                    "energy", "intensity", "units", "plot_config"):
            assert key in result, f"Missing key: {key}"

    def test_xas_element_echoed(self):
        """element in response matches the requested element."""
        result = mp_get_detailed_property_data(
            "mp-149", "xas_spectrum", element="Si", edge="K", spectrum_type="XANES"
        )
        assert result["element"] == "Si"

    def test_xas_edge_echoed(self):
        """edge in response matches the requested edge."""
        result = mp_get_detailed_property_data(
            "mp-149", "xas_spectrum", element="Si", edge="K", spectrum_type="XANES"
        )
        assert result["edge"] == "K"

    def test_xas_energy_is_list(self):
        """energy is a non-empty list."""
        result = mp_get_detailed_property_data(
            "mp-149", "xas_spectrum", element="Si", edge="K", spectrum_type="XANES"
        )
        assert isinstance(result["energy"], list)
        assert len(result["energy"]) > 0

    def test_xas_intensity_length_matches_energy(self):
        """intensity and energy arrays have the same length."""
        result = mp_get_detailed_property_data(
            "mp-149", "xas_spectrum", element="Si", edge="K", spectrum_type="XANES"
        )
        assert len(result["intensity"]) == len(result["energy"])

    def test_xas_wrong_element_returns_failure(self):
        """Requesting XAS for a non-existent element in a material returns success=False."""
        result = mp_get_detailed_property_data(
            "mp-149", "xas_spectrum", element="Au", edge="K", spectrum_type="XANES"
        )
        assert result["success"] is False
        assert "error" in result


# ---------------------------------------------------------------------------
# Dielectric tensor  (mp-5020 – BaTiO3, known to have dielectric data)
# ---------------------------------------------------------------------------

@_requires_api_key
class TestDielectricTensor:

    def test_dielectric_tensor_required_keys_when_available(self):
        """Dielectric tensor result has expected keys when data is present."""
        result = mp_get_detailed_property_data("mp-5020", "dielectric_tensor")
        if not result["success"]:
            pytest.skip("No dielectric data available for mp-5020")
        for key in ("material_id", "units"):
            assert key in result, f"Missing key: {key}"

    def test_dielectric_tensor_units(self):
        """Units for dielectric tensor are 'dimensionless'."""
        result = mp_get_detailed_property_data("mp-5020", "dielectric_tensor")
        if not result["success"]:
            pytest.skip("No dielectric data available for mp-5020")
        assert result["units"] == "dimensionless"

    def test_dielectric_total_tensor_is_3x3_when_available(self):
        """total_tensor is 3×3 when present."""
        result = mp_get_detailed_property_data("mp-5020", "dielectric_tensor")
        if not result["success"]:
            pytest.skip("No dielectric data available for mp-5020")
        tensor = result.get("total_tensor")
        if tensor is not None:
            assert len(tensor) == 3
            for row in tensor:
                assert len(row) == 3


# ---------------------------------------------------------------------------
# Phonon band structure & DOS  (data may not be available for all materials)
# ---------------------------------------------------------------------------

@_requires_api_key
class TestPhononData:

    def test_phonon_bandstructure_response_has_success_key(self):
        """Phonon band structure response always contains 'success' key."""
        result = mp_get_detailed_property_data("mp-149", "phonon_bandstructure")
        assert "success" in result

    def test_phonon_bandstructure_keys_when_available(self):
        """Phonon band structure result has expected keys when data is present."""
        result = mp_get_detailed_property_data("mp-149", "phonon_bandstructure")
        if not result["success"]:
            pytest.skip("No phonon band structure data for mp-149")
        for key in ("material_id", "qpoints", "frequencies", "units", "plot_config"):
            assert key in result, f"Missing key: {key}"

    def test_phonon_dos_response_has_success_key(self):
        """Phonon DOS response always contains 'success' key."""
        result = mp_get_detailed_property_data("mp-149", "phonon_dos")
        assert "success" in result

    def test_phonon_dos_keys_when_available(self):
        """Phonon DOS result has expected keys when data is present."""
        result = mp_get_detailed_property_data("mp-149", "phonon_dos")
        if not result["success"]:
            pytest.skip("No phonon DOS data for mp-149")
        for key in ("material_id", "frequencies", "densities", "units"):
            assert key in result, f"Missing key: {key}"
        assert len(result["frequencies"]) == len(result["densities"])
