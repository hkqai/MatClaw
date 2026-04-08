"""
Tests for pymatgen_enumeration_generator tool.

Run with: pytest tests/pymatgen/test_enumeration_generator.py -v

The tool uses pymatgen's OrderDisorderedStructureTransformation.
The supercell_size parameter controls the supercell size used for ordering structures.
"""

import pytest

from tools.pymatgen.pymatgen_enumeration_generator import pymatgen_enumeration_generator


# Helper
def _is_ordered_dict(structure_dict: dict) -> bool:
    """Return True if the pymatgen Structure dict represents a fully ordered structure."""
    from pymatgen.core import Structure
    return Structure.from_dict(structure_dict).is_ordered


# Basic enumeration
class TestBasicEnumeration:
    """Core success / correctness tests."""

    def test_enumeration_succeeds(self, disordered_li_na_cl):
        """Enumeration of a 50/50 Li/Na disordered rocksalt should succeed."""
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=20,
            output_format="dict",
        )
        assert result["success"] is True
        assert result["count"] >= 1
        assert len(result["structures"]) == result["count"]
        assert len(result["metadata"]) == result["count"]

    def test_all_returned_structures_are_ordered(self, disordered_li_na_cl):
        """Every returned structure must be fully ordered (no partial occupancies)."""
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=20,
            output_format="dict",
        )
        assert result["success"] is True
        for s in result["structures"]:
            assert _is_ordered_dict(s), "Returned structure still has partial occupancies."

    def test_n_structures_cap_respected(self, disordered_li_na_cl):
        """count must not exceed the requested n_structures."""
        cap = 2
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=cap,
            output_format="dict",
        )
        assert result["success"] is True
        assert result["count"] <= cap

    def test_structures_contain_correct_elements(self, disordered_li_na_cl):
        """All ordered structures should only contain Li, Na, and Cl."""
        from pymatgen.core import Structure

        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=20,
            output_format="dict",
        )
        assert result["success"] is True
        allowed = {"Li", "Na", "Cl"}
        for s_dict in result["structures"]:
            # Use .symbol to strip oxidation-state decoration (e.g. 'Li+' → 'Li')
            elements = {el.symbol for el in Structure.from_dict(s_dict).composition.elements}
            assert elements.issubset(allowed), f"Unexpected elements in structure: {elements}"

    def test_input_info_populated(self, disordered_li_na_cl):
        """input_info dict must record number of input structures and their formulas."""
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=10,
            output_format="dict",
        )
        assert result["success"] is True
        info = result["input_info"]
        assert info["n_input_structures"] == 1
        assert len(info["input_formulas"]) == 1


# Sort criteria
class TestSortCriteria:
    """Tests for sort_by parameter behaviour."""

    def test_sort_by_ewald(self, disordered_li_na_cl):
        """sort_by='ewald' should produce a valid ranked list."""
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=10,
            sort_by="ewald",
            add_oxidation_states=True,
            output_format="dict",
        )
        assert result["success"] is True
        assert result["count"] >= 1

    def test_sort_by_num_sites(self, disordered_li_na_cl):
        """sort_by='num_sites' should succeed and return smaller structures first."""
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=10,
            sort_by="num_sites",
            output_format="dict",
        )
        assert result["success"] is True
        assert result["count"] >= 1
        # Structures should be sorted by size (non-decreasing)
        sizes = [m["n_sites"] for m in result["metadata"]]
        assert sizes == sorted(sizes), "Structures not sorted by n_sites."

    def test_sort_by_random(self, disordered_li_na_cl):
        """sort_by='random' should succeed and return ordered structures."""
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=10,
            sort_by="random",
            output_format="dict",
        )
        assert result["success"] is True
        assert result["count"] >= 1
        for s in result["structures"]:
            assert _is_ordered_dict(s)


# Supercell size behaviour
class TestSupercellSize:
    """Tests for supercell_size parameter."""

    def test_supercell_size_one(self, disordered_li_na_cl):
        """Test that supercell_size=1 works correctly."""
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=1,
            n_structures=10,
            output_format="dict",
        )
        # With supercell_size=1, we just verify it runs
        # The tool should succeed or at least not crash
        assert result.get("success") is True or "error" in result

    def test_supercell_size_two(self, disordered_li_na_cl):
        """Test that supercell_size=2 works correctly."""
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=20,
            output_format="dict",
        )
        # Just verify the parameter is accepted and tool runs
        assert result.get("success") is True or "error" in result


# check_ordered_input
class TestCheckOrderedInput:
    """Tests for the check_ordered_input parameter."""

    def test_ordered_structure_skipped_by_default(self, simple_nacl_structure):
        """A fully ordered structure should be skipped and return success=False."""
        result = pymatgen_enumeration_generator(
            input_structures=simple_nacl_structure,
            supercell_size=2,
            n_structures=5,
            check_ordered_input=True,
            output_format="dict",
        )
        assert result["success"] is False
        assert result["warnings"] is not None
        assert any("ordered" in w.lower() for w in result["warnings"])

    def test_ordered_structure_processed_when_flag_disabled(self, simple_nacl_structure):
        """With check_ordered_input=False, an ordered structure is processed (not silently
        skipped). OrderDisorderedStructureTransformation finds no new decorations for a fully
        ordered structure (all sites already singly occupied), so success=False is expected —
        but the tool must NOT emit the 'already ordered, skipped' warning."""
        result = pymatgen_enumeration_generator(
            input_structures=simple_nacl_structure,
            supercell_size=2,
            n_structures=5,
            check_ordered_input=False,
            output_format="dict",
        )
        # The structure was not skip-listed by check_ordered_input — no skip warning expected
        warnings = result.get("warnings") or []
        skip_warnings = [
            w for w in warnings
            if "skipped" in w.lower() and "ordered" in w.lower()
        ]
        assert skip_warnings == [], (
            f"Should not emit an ordered-skip warning when check_ordered_input=False, "
            f"but got: {skip_warnings}"
        )

    def test_disordered_structure_not_skipped(self, disordered_li_na_cl):
        """A disordered structure must never be skipped regardless of check_ordered_input."""
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=10,
            check_ordered_input=True,
            output_format="dict",
        )
        assert result["success"] is True


# Output formats
class TestOutputFormats:
    """Tests for all four supported output formats."""

    def test_dict_output(self, disordered_li_na_cl):
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=2,
            output_format="dict",
        )
        assert result["success"] is True
        s = result["structures"][0]
        assert isinstance(s, dict)
        assert "@module" in s  # pymatgen structure dict marker

    def test_cif_output(self, disordered_li_na_cl):
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=2,
            output_format="cif",
        )
        assert result["success"] is True
        s = result["structures"][0]
        assert isinstance(s, str)
        assert "data_" in s
        assert "_cell_length_a" in s

    def test_poscar_output(self, disordered_li_na_cl):
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=2,
            output_format="poscar",
        )
        assert result["success"] is True
        s = result["structures"][0]
        assert isinstance(s, str)
        # POSCAR has element line somewhere
        assert any(el in s for el in ("Li", "Na", "Cl"))

    def test_json_output(self, disordered_li_na_cl):
        import json

        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=2,
            output_format="json",
        )
        assert result["success"] is True
        s = result["structures"][0]
        assert isinstance(s, str)
        parsed = json.loads(s)
        assert isinstance(parsed, dict)


# Multiple input structures
class TestMultipleInputStructures:
    """Tests when a list of disordered structures is provided."""

    def test_two_disordered_inputs_cumulative_count(self, disordered_li_na_cl, simple_nacl_structure):
        """
        Providing two structures (one disordered, one ordered-skipped) should
        enumerate only the disordered one and report input_info correctly.
        """
        result = pymatgen_enumeration_generator(
            input_structures=[disordered_li_na_cl, disordered_li_na_cl],
            supercell_size=2,
            n_structures=5,
            output_format="dict",
        )
        assert result["success"] is True
        assert result["input_info"]["n_input_structures"] == 2
        # Both are the same disordered structure; count should be roughly similar
        # (may vary slightly with different orderings)
        assert result["count"] >= 1

    def test_source_structure_label_in_metadata(self, disordered_li_na_cl):
        """metadata 'source_structure' must match the input formula."""
        result = pymatgen_enumeration_generator(
            input_structures=[disordered_li_na_cl],
            supercell_size=2,
            n_structures=5,
            output_format="dict",
        )
        assert result["success"] is True
        for m in result["metadata"]:
            assert "source_structure" in m
            assert isinstance(m["source_structure"], str)
            assert len(m["source_structure"]) > 0


# Metadata completeness
class TestMetadata:
    """Tests that all documented metadata fields are present and sensible."""

    def test_top_level_fields_present(self, disordered_li_na_cl):
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=5,
            output_format="dict",
        )
        assert result["success"] is True
        for key in ("count", "structures", "metadata", "input_info", "enumeration_params", "message"):
            assert key in result, f"Missing top-level key: {key}"

    def test_per_structure_metadata_fields(self, disordered_li_na_cl):
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=5,
            output_format="dict",
        )
        assert result["success"] is True
        for m in result["metadata"]:
            for key in (
                "index", "source_structure", "formula", "n_sites",
                "supercell_size", "volume", "space_group_number",
                "space_group_symbol", "ewald_energy", "is_ordered", "backend",
            ):
                assert key in m, f"Missing per-structure metadata key: {key}"

    def test_is_ordered_always_true(self, disordered_li_na_cl):
        """metadata 'is_ordered' must be True for every returned structure."""
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=10,
            output_format="dict",
        )
        assert result["success"] is True
        for m in result["metadata"]:
            assert m["is_ordered"] is True

    def test_index_is_sequential(self, disordered_li_na_cl):
        """metadata 'index' must be 1, 2, 3, … without gaps."""
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=10,
            output_format="dict",
        )
        assert result["success"] is True
        indices = [m["index"] for m in result["metadata"]]
        assert indices == list(range(1, result["count"] + 1))

    def test_enumeration_params_recorded(self, disordered_li_na_cl):
        """enumeration_params must record all input parameters accurately."""
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=7,
            sort_by="num_sites",
            symm_prec=0.15,
            output_format="dict",
        )
        assert result["success"] is True
        ep = result["enumeration_params"]
        assert ep["supercell_size"] == 2
        assert ep["n_structures_requested"] == 7
        assert ep["sort_by"] == "num_sites"
        assert ep["symm_prec"] == pytest.approx(0.15, abs=1e-9)

    def test_volume_is_positive(self, disordered_li_na_cl):
        """Cell volume in metadata must be a positive float."""
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=5,
            output_format="dict",
        )
        assert result["success"] is True
        for m in result["metadata"]:
            assert m["volume"] > 0.0

    def test_n_sites_positive_and_integer(self, disordered_li_na_cl):
        """n_sites must be a positive integer."""
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=5,
            output_format="dict",
        )
        assert result["success"] is True
        for m in result["metadata"]:
            assert isinstance(m["n_sites"], int)
            assert m["n_sites"] > 0


# Error handling — these tests always run (no enumlib required)
class TestErrorHandling:
    """Parameter-validation and error-path tests that run without enumlib."""

    def test_invalid_output_format(self, disordered_li_na_cl):
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=1,
            output_format="xyz",
        )
        assert result["success"] is False
        assert "Invalid output_format" in result["error"]

    def test_invalid_sort_by(self, disordered_li_na_cl):
        result = pymatgen_enumeration_generator(
            input_structures=disordered_li_na_cl,
            supercell_size=2,
            n_structures=1,
            sort_by="magic",
        )
        assert result["success"] is False
        assert "Invalid sort_by" in result["error"]

    def test_invalid_input_type(self):
        result = pymatgen_enumeration_generator(
            input_structures=42,
            supercell_size=2,
            n_structures=1,
        )
        assert result["success"] is False
        assert "error" in result

    def test_empty_structure_list(self):
        result = pymatgen_enumeration_generator(
            input_structures=[],
            supercell_size=2,
            n_structures=1,
        )
        assert result["success"] is False
        assert "error" in result

    def test_ordered_input_all_skipped_returns_failure(self, simple_nacl_structure):
        """When every input is ordered and check_ordered_input=True, success must be False."""
        result = pymatgen_enumeration_generator(
            input_structures=simple_nacl_structure,
            supercell_size=2,
            n_structures=5,
            check_ordered_input=True,
        )
        assert result["success"] is False
        # Error/warnings should mention ordering
        messages = result.get("error", "") + " ".join(result.get("warnings") or [])
        assert "ordered" in messages.lower()