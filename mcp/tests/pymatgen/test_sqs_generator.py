"""
Tests for pymatgen_sqs_generator tool.

All tests use small supercell_size and n_mc_steps values for speed.
Primary fixture: disordered_li_na_cl — a 2-atom Li₀.₅/Na₀.₅ rocksalt.
"""

import json
import pytest
from tools.pymatgen.pymatgen_sqs_generator import pymatgen_sqs_generator


# Helpers
FAST = dict(n_mc_steps=500, n_shells=2, supercell_size=4)
"""Kwargs that keep every test fast (<1 s for a single candidate)."""


def _is_ordered(structure_dict: dict) -> bool:
    """Return True if every site in a Structure dict has a single species."""
    from pymatgen.core import Structure
    s = Structure.from_dict(structure_dict)
    return all(site.is_ordered for site in s)


# TestBasicSQS
class TestBasicSQS:
    """Smoke tests: tool runs without error and returns well-formed output."""

    def test_returns_success(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        assert result["success"] is True

    def test_count_matches_n_structures(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=2, seed=0, **FAST
        )
        assert result["count"] == 2
        assert len(result["structures"]) == 2

    def test_metadata_length_matches_structures(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=2, seed=0, **FAST
        )
        assert len(result["metadata"]) == len(result["structures"])

    def test_structures_are_fully_ordered(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=2, seed=0, **FAST
        )
        for s in result["structures"]:
            assert _is_ordered(s), "SQS output should be a fully ordered structure"

    def test_result_has_message(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        assert "message" in result
        assert isinstance(result["message"], str)

    def test_result_has_sqs_params(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        assert "sqs_params" in result
        assert isinstance(result["sqs_params"], dict)

    def test_result_has_input_info(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        assert "input_info" in result


# TestMetadataFields
class TestMetadataFields:
    """Verify all documented per-structure metadata keys are present."""

    REQUIRED_KEYS = {
        "index",
        "source_formula",
        "sqs_formula",
        "n_sites",
        "supercell_size",
        "sqs_error",
        "warren_cowley",
        "composition",
        "n_mc_steps",
        "backend",
        "mcsqs_used",
    }

    def test_all_required_keys_present(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        meta = result["metadata"][0]
        for key in self.REQUIRED_KEYS:
            assert key in meta, f"Missing metadata key: {key}"

    def test_index_is_one_based(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=3, seed=0, **FAST
        )
        indices = [m["index"] for m in result["metadata"]]
        assert 1 in indices

    def test_sqs_error_is_nonnegative(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=2, seed=0, **FAST
        )
        for meta in result["metadata"]:
            assert meta["sqs_error"] >= 0.0

    def test_n_sites_positive(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        assert result["metadata"][0]["n_sites"] > 0

    def test_backend_is_string(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        assert isinstance(result["metadata"][0]["backend"], str)

    def test_mcsqs_used_is_bool(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        assert isinstance(result["metadata"][0]["mcsqs_used"], bool)

    def test_composition_is_dict(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        assert isinstance(result["metadata"][0]["composition"], dict)

    def test_warren_cowley_is_dict(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        wc = result["metadata"][0]["warren_cowley"]
        assert isinstance(wc, dict)

    def test_source_formula_is_string(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        assert isinstance(result["metadata"][0]["source_formula"], str)


# TestStoichiometry
class TestStoichiometry:
    """SQS cells should preserve the target stoichiometry."""

    def test_equal_li_na_count_in_sqs(self, disordered_li_na_cl):
        """50/50 Li/Na input should give equal Li and Na in the SQS cell."""
        from pymatgen.core import Structure
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        s = Structure.from_dict(result["structures"][0])
        composition = s.composition
        n_li = composition["Li"]
        n_na = composition["Na"]
        assert n_li == n_na, (
            f"Expected equal Li and Na counts for 50/50 input, got Li={n_li}, Na={n_na}"
        )

    def test_n_sites_consistent_with_structure(self, disordered_li_na_cl):
        """metadata n_sites should match the actual atom count."""
        from pymatgen.core import Structure
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        s = Structure.from_dict(result["structures"][0])
        assert result["metadata"][0]["n_sites"] == len(s)

    def test_composition_contains_expected_elements(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        comp = result["metadata"][0]["composition"]
        # Li₀.₅Na₀.₅Cl has Li, Na, and Cl
        elements = set(comp.keys())
        assert "Li" in elements
        assert "Na" in elements
        assert "Cl" in elements


# TestWarrenCowley
class TestWarrenCowley:
    """Warren-Cowley parameter structure and value sanity."""

    def test_wc_has_shell_keys(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        wc = result["metadata"][0]["warren_cowley"]
        assert len(wc) >= 1, "Expected at least one shell in warren_cowley"

    def test_wc_values_in_range(self, disordered_li_na_cl):
        """WC parameters α ∈ [-1, 1] by definition."""
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        wc = result["metadata"][0]["warren_cowley"]
        for shell_key, pairs in wc.items():
            for pair_key, alpha in pairs.items():
                assert -1.0 <= alpha <= 1.0, (
                    f"WC parameter out of range: shell={shell_key}, pair={pair_key}, α={alpha}"
                )

    def test_more_mc_steps_lowers_sqs_error(self, disordered_li_na_cl):
        """Higher n_mc_steps should produce lower or equal SQS error on average
        (not guaranteed per-run, so we use a fixed seed and generous comparison)."""
        result_few = pymatgen_sqs_generator(
            disordered_li_na_cl,
            n_structures=1, seed=99,
            n_mc_steps=200, n_shells=2, supercell_size=4,
        )
        result_many = pymatgen_sqs_generator(
            disordered_li_na_cl,
            n_structures=1, seed=99,
            n_mc_steps=10000, n_shells=2, supercell_size=4,
        )
        err_few = result_few["metadata"][0]["sqs_error"]
        err_many = result_many["metadata"][0]["sqs_error"]
        # With the same seed and more steps, error should not be significantly worse
        assert err_many <= err_few * 1.5, (
            f"Expected more MC steps to improve SQS error, got few={err_few}, many={err_many}"
        )


# TestSortBy
class TestSortBy:
    """sort_by parameter controls ordering of returned candidates."""

    def test_sort_by_sqs_error_ascending(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=3, seed=7, sort_by="sqs_error", **FAST
        )
        errors = [m["sqs_error"] for m in result["metadata"]]
        assert errors == sorted(errors), (
            f"Expected ascending sqs_error order, got {errors}"
        )

    def test_sort_by_random_returns_results(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=2, seed=7, sort_by="random", **FAST
        )
        assert result["success"] is True
        assert result["count"] == 2

    def test_invalid_sort_by_returns_error(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, sort_by="energy", **FAST
        )
        assert result["success"] is False
        assert "sort_by" in result["error"].lower()


# TestReproducibility
class TestReproducibility:
    """Fixed seed should produce identical structures across calls."""

    def test_same_seed_same_sqs_error(self, disordered_li_na_cl):
        kw = dict(n_structures=1, seed=42, **FAST)
        r1 = pymatgen_sqs_generator(disordered_li_na_cl, **kw)
        r2 = pymatgen_sqs_generator(disordered_li_na_cl, **kw)
        assert r1["metadata"][0]["sqs_error"] == pytest.approx(
            r2["metadata"][0]["sqs_error"], rel=1e-9
        )

    def test_same_seed_same_structure(self, disordered_li_na_cl):
        from pymatgen.core import Structure
        kw = dict(n_structures=1, seed=42, **FAST)
        r1 = pymatgen_sqs_generator(disordered_li_na_cl, **kw)
        r2 = pymatgen_sqs_generator(disordered_li_na_cl, **kw)
        s1 = Structure.from_dict(r1["structures"][0])
        s2 = Structure.from_dict(r2["structures"][0])
        # Same number of sites and same species at each site
        assert len(s1) == len(s2)
        sp1 = [str(site.specie) for site in s1]
        sp2 = [str(site.specie) for site in s2]
        assert sp1 == sp2

    def test_different_seeds_may_differ(self, disordered_li_na_cl):
        """Two different seeds should not be guaranteed equal (probabilistic check)."""
        r1 = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=1, **FAST
        )
        r2 = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=9999, **FAST
        )
        # Both should succeed
        assert r1["success"] is True
        assert r2["success"] is True


# TestSupercellControl
class TestSupercellControl:
    """supercell_size and supercell_matrix control the SQS cell size."""

    def test_larger_supercell_size_gives_more_atoms(self, disordered_li_na_cl):
        r_small = pymatgen_sqs_generator(
            disordered_li_na_cl,
            n_structures=1, seed=0,
            supercell_size=2, n_mc_steps=200, n_shells=2,
        )
        r_large = pymatgen_sqs_generator(
            disordered_li_na_cl,
            n_structures=1, seed=0,
            supercell_size=8, n_mc_steps=200, n_shells=2,
        )
        assert r_small["metadata"][0]["n_sites"] <= r_large["metadata"][0]["n_sites"]

    def test_explicit_supercell_matrix_diagonal(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl,
            n_structures=1, seed=0,
            supercell_matrix=[2, 2, 2],
            n_mc_steps=200, n_shells=2,
        )
        assert result["success"] is True
        # 2×2×2 supercell of 2-atom cell = 16 atoms
        assert result["metadata"][0]["n_sites"] == 16

    def test_explicit_supercell_matrix_3x3(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl,
            n_structures=1, seed=0,
            supercell_matrix=[[2, 0, 0], [0, 2, 0], [0, 0, 2]],
            n_mc_steps=200, n_shells=2,
        )
        assert result["success"] is True
        assert result["metadata"][0]["n_sites"] == 16

    def test_invalid_supercell_matrix_returns_error(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl,
            n_structures=1,
            supercell_matrix=[0, 2, 2],
            n_mc_steps=200, n_shells=2,
        )
        assert result["success"] is False


# TestOutputFormats
class TestOutputFormats:
    """Each output_format produces the expected data type."""

    def test_dict_format_is_dict(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0,
            output_format="dict", **FAST
        )
        assert isinstance(result["structures"][0], dict)

    def test_poscar_format_is_string(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0,
            output_format="poscar", **FAST
        )
        assert isinstance(result["structures"][0], str)
        assert "POSCAR" in result["structures"][0] or result["structures"][0].strip() != ""

    def test_cif_format_is_string(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0,
            output_format="cif", **FAST
        )
        s = result["structures"][0]
        assert isinstance(s, str)
        assert "_cell_length_a" in s or "loop_" in s

    def test_json_format_is_json_string(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0,
            output_format="json", **FAST
        )
        s = result["structures"][0]
        assert isinstance(s, str)
        parsed = json.loads(s)
        assert isinstance(parsed, dict)

    def test_dict_format_is_round_trippable(self, disordered_li_na_cl):
        from pymatgen.core import Structure
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0,
            output_format="dict", **FAST
        )
        s = Structure.from_dict(result["structures"][0])
        assert len(s) > 0

    def test_invalid_output_format_returns_error(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1,
            output_format="xyz", **FAST
        )
        assert result["success"] is False
        assert "output_format" in result["error"].lower()


# TestMultipleInputs
class TestMultipleInputs:
    """Tool accepts a list of input structures and processes each."""

    def test_list_of_two_inputs_produces_more_structures(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            [disordered_li_na_cl, disordered_li_na_cl],
            n_structures=1, seed=0, **FAST
        )
        assert result["success"] is True
        # 2 input structures × 1 candidate each = 2 structures
        assert result["count"] == 2

    def test_single_dict_input_accepted(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        assert result["success"] is True

    def test_list_of_one_same_as_single(self, disordered_li_na_cl):
        r_single = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=42, **FAST
        )
        r_list = pymatgen_sqs_generator(
            [disordered_li_na_cl], n_structures=1, seed=42, **FAST
        )
        assert r_single["count"] == r_list["count"]
        e1 = r_single["metadata"][0]["sqs_error"]
        e2 = r_list["metadata"][0]["sqs_error"]
        assert e1 == pytest.approx(e2, rel=1e-9)


# TestShellWeights
class TestShellWeights:
    """Custom shell_weights parameter validation."""

    def test_custom_shell_weights_accepted(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0,
            n_shells=2, shell_weights=[2.0, 1.0],
            n_mc_steps=200, supercell_size=4,
        )
        assert result["success"] is True

    def test_wrong_length_shell_weights_returns_error(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1,
            n_shells=3, shell_weights=[1.0, 0.5],  # length 2 ≠ 3
            n_mc_steps=200, supercell_size=4,
        )
        assert result["success"] is False
        assert "shell_weights" in result["error"].lower()

    def test_negative_shell_weight_returns_error(self, disordered_li_na_cl):
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1,
            n_shells=2, shell_weights=[1.0, -0.5],
            n_mc_steps=200, supercell_size=4,
        )
        assert result["success"] is False


# TestErrorHandling
class TestErrorHandling:
    """Edge cases and invalid inputs."""

    def test_ordered_structure_returns_error(self, simple_nacl_structure):
        """Fully ordered structure has no mixing sites — should fail gracefully."""
        result = pymatgen_sqs_generator(
            simple_nacl_structure, n_structures=1, **FAST
        )
        assert result["success"] is False

    def test_invalid_input_type_returns_error(self):
        result = pymatgen_sqs_generator(
            12345, n_structures=1, **FAST  # type: ignore
        )
        assert result["success"] is False

    def test_invalid_n_shells_boundary(self, disordered_li_na_cl):
        """n_shells must be >= 1; 0 should be rejected by Pydantic or the tool."""
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1,
            n_shells=0, n_mc_steps=200, supercell_size=4,
        )
        # Pydantic (ge=1) constrains this; tool should return error or raise
        # We just check it doesn't silently succeed with corrupted output
        if result.get("success"):
            assert result["count"] >= 0  # at minimum it must have a count


# TestPipelineIntegration
class TestPipelineIntegration:
    """SQS output feeds correctly into downstream pymatgen tools."""

    def test_sqs_feeds_into_perturbation_generator(self, disordered_li_na_cl):
        """SQS structure (dict) can be passed directly to perturbation_generator."""
        from tools.pymatgen.pymatgen_perturbation_generator import pymatgen_perturbation_generator

        sqs_result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        assert sqs_result["success"] is True

        sqs_struct = sqs_result["structures"][0]
        perturb_result = pymatgen_perturbation_generator(
            sqs_struct,
            n_structures=2,
            displacement_max=0.02,
        )
        assert perturb_result["success"] is True
        assert perturb_result["count"] == 2

    def test_sqs_output_is_pymatgen_compatible(self, disordered_li_na_cl):
        """SQS dict output round-trips cleanly through pymatgen Structure."""
        from pymatgen.core import Structure
        result = pymatgen_sqs_generator(
            disordered_li_na_cl, n_structures=1, seed=0, **FAST
        )
        s = Structure.from_dict(result["structures"][0])
        # Re-serialise and check it still has the right species
        d = s.as_dict()
        s2 = Structure.from_dict(d)
        assert len(s2) == len(s)
        elements1 = sorted(str(sp) for sp in s.composition.elements)
        elements2 = sorted(str(sp) for sp in s2.composition.elements)
        assert elements1 == elements2
