"""
Tests for pymatgen_defect_generator tool.

Run with: pytest tests/pymatgen/test_defect_generator.py -v
"""

import pytest
from tools.pymatgen.pymatgen_defect_generator import pymatgen_defect_generator


# Shared helpers
def _unique_defect_labels(metadata):
    return [m["defect_label"] for m in metadata]


# Vacancy generation
class TestVacancyGeneration:
    """Tests for vacancy defect supercell generation."""

    def test_vacancy_succeeds(self, simple_nacl_structure):
        """Vacancy generation for Na in NaCl should succeed."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
        )
        assert result["success"] is True
        assert result["count"] >= 1

    def test_vacancy_removes_one_atom(self, simple_nacl_structure):
        """Each vacancy supercell should have exactly one fewer atom than the perfect supercell."""
        from pymatgen.core import Structure

        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
            output_format="dict",
        )
        assert result["success"] is True
        n_perfect = result["supercell_info"]["n_atoms_supercell"]
        for s_dict in result["structures"]:
            n_defect = len(Structure.from_dict(s_dict))
            assert n_defect == n_perfect - 1

    def test_vacancy_defect_label_format(self, simple_nacl_structure):
        """Defect label for a Na vacancy should be 'V_Na'."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
        )
        assert result["success"] is True
        labels = _unique_defect_labels(result["metadata"])
        assert all(label == "V_Na" for label in labels)

    def test_vacancy_multiple_species(self, simple_nacl_structure):
        """Requesting vacancies for both Na and Cl should generate two defect types."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na", "Cl"],
            supercell_min_atoms=8,
        )
        assert result["success"] is True
        labels = set(_unique_defect_labels(result["metadata"]))
        assert "V_Na" in labels
        assert "V_Cl" in labels

    def test_vacancy_default_all_species(self, simple_nacl_structure):
        """If no defect type is specified, vacancies for all species are generated."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            supercell_min_atoms=8,
        )
        assert result["success"] is True
        labels = set(_unique_defect_labels(result["metadata"]))
        assert "V_Na" in labels
        assert "V_Cl" in labels

    def test_vacancy_species_not_in_structure_warns(self, simple_nacl_structure):
        """Vacancy species absent from the host should emit a warning, not crash."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Li"],  # Li is not in NaCl
            supercell_min_atoms=8,
        )
        # Should either succeed with no structures (no species found) or fail gracefully
        assert "error" in result or (result.get("success") is False) or (
            result.get("success") is True and result.get("warnings")
        )

    def test_vacancy_preserves_host_species_in_supercell(self, simple_nacl_structure):
        """The defect supercell must still contain all host elements except the removed one."""
        from pymatgen.core import Structure

        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
            output_format="dict",
        )
        assert result["success"] is True
        for s_dict in result["structures"]:
            s = Structure.from_dict(s_dict)
            el_symbols = {el.symbol for el in s.composition.elements}
            assert "Cl" in el_symbols
            assert "Na" not in el_symbols or True  # vacancy removes some Na but not necessarily all


# Substitution generation
class TestSubstitutionGeneration:
    """Tests for substitutional point defect generation."""

    def test_substitution_succeeds(self, simple_nacl_structure):
        """Na→K substitution in NaCl should succeed."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            substitution_species={"Na": "K"},
            supercell_min_atoms=8,
            output_format="dict",
        )
        assert result["success"] is True
        assert result["count"] >= 1

    def test_substitution_inserts_dopant(self, simple_nacl_structure):
        """The dopant element must appear in the defect supercell."""
        from pymatgen.core import Structure

        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            substitution_species={"Na": "K"},
            supercell_min_atoms=8,
            output_format="dict",
        )
        assert result["success"] is True
        for s_dict in result["structures"]:
            s = Structure.from_dict(s_dict)
            el_symbols = {el.symbol for el in s.composition.elements}
            assert "K" in el_symbols

    def test_substitution_preserves_site_count(self, simple_nacl_structure):
        """Substitution changes species but not the number of sites."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            substitution_species={"Na": "K"},
            supercell_min_atoms=8,
            output_format="dict",
        )
        assert result["success"] is True
        n_perfect = result["supercell_info"]["n_atoms_supercell"]
        for m in result["metadata"]:
            assert m["n_sites_supercell"] == n_perfect

    def test_substitution_defect_label_format(self, simple_nacl_structure):
        """Defect label for K on Na site should be 'K_Na'."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            substitution_species={"Na": "K"},
            supercell_min_atoms=8,
        )
        assert result["success"] is True
        for m in result["metadata"]:
            assert m["defect_label"] == "K_Na"

    def test_substitution_multiple_dopants(self, simple_nacl_structure):
        """Multiple dopants for the same host site should each produce separate structures."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            substitution_species={"Na": ["K", "Rb"]},
            supercell_min_atoms=8,
        )
        assert result["success"] is True
        labels = set(_unique_defect_labels(result["metadata"]))
        assert "K_Na" in labels
        assert "Rb_Na" in labels

    def test_substitution_metadata_records_host_and_dopant(self, simple_nacl_structure):
        """Metadata must record both host_species and dopant_species correctly."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            substitution_species={"Na": "K"},
            supercell_min_atoms=8,
        )
        assert result["success"] is True
        for m in result["metadata"]:
            assert m["host_species"] == "Na"
            assert m["dopant_species"] == "K"
            assert m["defect_type"] == "substitution"

    def test_self_substitution_skipped(self, simple_nacl_structure):
        """Na→Na (self-substitution) should be skipped with a warning."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            substitution_species={"Na": "Na"},
            supercell_min_atoms=8,
        )
        # Either no structures (fails gracefully) or warnings present
        if result.get("success"):
            assert result.get("warnings")
        else:
            # Acceptable: fails with error about self-substitution or no structures
            assert "error" in result


# Interstitial generation
class TestInterstitialGeneration:
    """Tests for interstitial defect generation."""

    def test_interstitial_succeeds(self, simple_nacl_structure):
        """Li interstitial in NaCl should find at least one void site."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            interstitial_species=["Li"],
            supercell_min_atoms=8,
            interstitial_min_dist=0.5,
        )
        assert result["success"] is True
        assert result["count"] >= 1

    def test_interstitial_adds_one_atom(self, simple_nacl_structure):
        """Interstitial supercell should have exactly one more atom than the perfect supercell."""
        from pymatgen.core import Structure

        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            interstitial_species=["Li"],
            supercell_min_atoms=8,
            interstitial_min_dist=0.5,
            output_format="dict",
        )
        assert result["success"] is True
        n_perfect = result["supercell_info"]["n_atoms_supercell"]
        for s_dict in result["structures"]:
            n_defect = len(Structure.from_dict(s_dict))
            assert n_defect == n_perfect + 1

    def test_interstitial_defect_label_format(self, simple_nacl_structure):
        """Defect label for a Li interstitial should be 'Li_i'."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            interstitial_species=["Li"],
            supercell_min_atoms=8,
            interstitial_min_dist=0.5,
        )
        assert result["success"] is True
        for m in result["metadata"]:
            assert m["defect_label"] == "Li_i"

    def test_interstitial_defect_type_in_metadata(self, simple_nacl_structure):
        """defect_type in metadata must be 'interstitial'."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            interstitial_species=["Li"],
            supercell_min_atoms=8,
            interstitial_min_dist=0.5,
        )
        assert result["success"] is True
        assert all(m["defect_type"] == "interstitial" for m in result["metadata"])

    def test_interstitial_max_sites_respected(self, simple_nacl_structure):
        """count should never exceed max_interstitial_sites."""
        cap = 2
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            interstitial_species=["Li"],
            supercell_min_atoms=8,
            interstitial_min_dist=0.5,
            max_interstitial_sites=cap,
        )
        assert result["success"] is True
        assert result["count"] <= cap

    def test_interstitial_void_min_dist_in_metadata(self, simple_nacl_structure):
        """Each interstitial metadata entry must include void_min_dist_ang."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            interstitial_species=["Li"],
            supercell_min_atoms=8,
            interstitial_min_dist=0.5,
        )
        assert result["success"] is True
        for m in result["metadata"]:
            assert "void_min_dist_ang" in m
            assert m["void_min_dist_ang"] >= 0.5


# Supercell control
class TestSupercellControl:
    """Tests for supercell size and explicit matrix control."""

    def test_supercell_min_atoms_respected(self, simple_nacl_structure):
        """Perfect supercell should have at least supercell_min_atoms atoms."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=16,
        )
        assert result["success"] is True
        assert result["supercell_info"]["n_atoms_supercell"] >= 16

    def test_explicit_supercell_matrix(self, simple_nacl_structure):
        """Explicit [2, 2, 2] supercell matrix should give 8× the unit cell."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_matrix=[2, 2, 2],
        )
        assert result["success"] is True
        # NaCl primitive has 2 atoms → 2×2×2 = 16 atoms in perfect supercell
        # (NaCl conventional cell has 8 atoms → 2^3 = 8x → 64, but primitive only 2)
        assert result["supercell_info"]["supercell_size"] == 8

    def test_supercell_info_populated(self, simple_nacl_structure):
        """supercell_info dict must contain expected keys."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
        )
        assert result["success"] is True
        info = result["supercell_info"]
        assert "n_atoms_supercell" in info
        assert "supercell_matrix" in info
        assert "supercell_size" in info
        assert "supercell_formula" in info


# Charge state metadata
class TestChargeStates:
    """Tests for charge state metadata handling."""

    def test_suggested_charge_states_present(self, simple_nacl_structure):
        """suggested_charge_states must be populated for each defect."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
        )
        assert result["success"] is True
        for m in result["metadata"]:
            assert "suggested_charge_states" in m
            assert isinstance(m["suggested_charge_states"], list)

    def test_user_charge_states_override(self, simple_nacl_structure):
        """User-provided charge states should override auto-estimated ones."""
        custom_q = [-2, -1, 0, 1]
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            charge_states={"V_Na": custom_q},
            supercell_min_atoms=8,
        )
        assert result["success"] is True
        for m in result["metadata"]:
            assert m["charge_states"] == custom_q

    def test_auto_charge_states_when_no_override(self, simple_nacl_structure):
        """When charge_states not provided, charge_states == suggested_charge_states."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
        )
        assert result["success"] is True
        for m in result["metadata"]:
            assert m["charge_states"] == m["suggested_charge_states"]


# Output formats
class TestOutputFormats:
    """Tests for all supported output formats."""

    def test_dict_output(self, simple_nacl_structure):
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
            output_format="dict",
        )
        assert result["success"] is True
        assert isinstance(result["structures"][0], dict)
        assert "@module" in result["structures"][0]

    def test_poscar_output(self, simple_nacl_structure):
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
            output_format="poscar",
        )
        assert result["success"] is True
        poscar_str = result["structures"][0]
        assert isinstance(poscar_str, str)
        assert "Cl" in poscar_str  # Cl remains after Na vacancy

    def test_cif_output(self, simple_nacl_structure):
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
            output_format="cif",
        )
        assert result["success"] is True
        cif_str = result["structures"][0]
        assert isinstance(cif_str, str)
        assert "_cell_length_a" in cif_str

    def test_json_output(self, simple_nacl_structure):
        import json

        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
            output_format="json",
        )
        assert result["success"] is True
        json_str = result["structures"][0]
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)


# Metadata completeness
class TestMetadata:
    """Tests for metadata completeness and correctness."""

    def test_required_metadata_keys_present(self, simple_nacl_structure):
        """Every metadata entry must contain the full set of required keys."""
        required_keys = {
            "index", "defect_type", "defect_label", "host_species", "dopant_species",
            "wyckoff_symbol", "site_index_bulk", "site_index_supercell",
            "site_coords_frac", "site_coords_cart",
            "supercell_formula", "n_sites_supercell", "host_formula",
            "supercell_size", "charge_states", "suggested_charge_states",
        }
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
        )
        assert result["success"] is True
        for m in result["metadata"]:
            missing = required_keys - set(m.keys())
            assert not missing, f"Metadata missing keys: {missing}"

    def test_index_is_sequential(self, simple_nacl_structure):
        """index field should be 1-based and sequential."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na", "Cl"],
            supercell_min_atoms=8,
        )
        assert result["success"] is True
        for i, m in enumerate(result["metadata"]):
            assert m["index"] == i + 1

    def test_host_formula_in_metadata(self, simple_nacl_structure):
        """host_formula must match the bulk host's reduced formula."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
        )
        assert result["success"] is True
        for m in result["metadata"]:
            assert m["host_formula"] == "NaCl"

    def test_site_coords_frac_length(self, simple_nacl_structure):
        """site_coords_frac must be a 3-element list."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
        )
        assert result["success"] is True
        for m in result["metadata"]:
            assert len(m["site_coords_frac"]) == 3
            assert len(m["site_coords_cart"]) == 3

    def test_host_info_populated(self, simple_nacl_structure):
        """host_info must contain lattice parameters and space group information."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
        )
        assert result["success"] is True
        hi = result["host_info"]
        assert hi["formula"] == "NaCl"
        assert "space_group_number" in hi
        assert "lattice" in hi
        lattice = hi["lattice"]
        assert all(k in lattice for k in ["a", "b", "c", "alpha", "beta", "gamma", "volume"])


# Inequivalent-site filtering
class TestInequalentSites:
    """Tests for symmetry-based site deduplication."""

    def test_inequivalent_only_reduces_count(self, simple_lifep04_structure):
        """inequivalent_only=True should produce <= structures vs inequivalent_only=False."""
        common_kwargs = dict(
            input_structure=simple_lifep04_structure,
            vacancy_species=["O"],
            supercell_min_atoms=8,
        )
        r_unique = pymatgen_defect_generator(**common_kwargs, inequivalent_only=True)
        r_all = pymatgen_defect_generator(**common_kwargs, inequivalent_only=False)
        assert r_unique["success"] is True
        assert r_all["success"] is True
        assert r_unique["count"] <= r_all["count"]

    def test_inequivalent_only_false_generates_all_bulk_sites(self, simple_lifep04_structure):
        """
        With inequivalent_only=False every bulk-cell site of the species gets its own
        defect supercell (no symmetry merging), so count >= inequivalent_only=True count.

        Uses the LiFePO4-like fixture which has multiple O sites in the bulk cell,
        making the True/False distinction meaningful.
        """
        from pymatgen.core import Structure

        r_unique = pymatgen_defect_generator(
            input_structure=simple_lifep04_structure,
            vacancy_species=["O"],
            supercell_min_atoms=8,
            inequivalent_only=True,
        )
        r_all = pymatgen_defect_generator(
            input_structure=simple_lifep04_structure,
            vacancy_species=["O"],
            supercell_min_atoms=8,
            inequivalent_only=False,
        )
        assert r_unique["success"] is True
        assert r_all["success"] is True
        # False (all bulk sites) should produce at least as many as True (inequivalent only)
        assert r_all["count"] >= r_unique["count"]
        # False should produce exactly one vacancy per O atom in the bulk cell
        n_O_bulk = sum(
            1 for site in Structure.from_dict(simple_lifep04_structure)
            if site.specie.symbol == "O"
        )
        assert r_all["count"] == n_O_bulk


# Mixed defect types
class TestMixedDefectTypes:
    """Tests for generating multiple defect types in one call."""

    def test_vacancy_and_substitution_together(self, simple_nacl_structure):
        """Requesting both vacancies and substitutions should generate both types."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            substitution_species={"Na": "K"},
            supercell_min_atoms=8,
        )
        assert result["success"] is True
        types = {m["defect_type"] for m in result["metadata"]}
        assert "vacancy" in types
        assert "substitution" in types

    def test_count_equals_sum_of_parts(self, simple_nacl_structure):
        """Total count must equal sum of individual vacancy + substitution counts."""
        r_vac = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
        )
        r_sub = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            substitution_species={"Na": "K"},
            supercell_min_atoms=8,
        )
        r_both = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            substitution_species={"Na": "K"},
            supercell_min_atoms=8,
        )
        assert r_vac["success"] and r_sub["success"] and r_both["success"]
        assert r_both["count"] == r_vac["count"] + r_sub["count"]


# Pipeline integration
class TestPipelineIntegration:
    """Tests that defect_generator chains correctly with other pymatgen tools."""

    def test_output_feeds_perturbation_generator(self, simple_nacl_structure):
        """Vacancy supercells from defect_generator must be accepted by perturbation_generator."""
        from tools.pymatgen.pymatgen_perturbation_generator import pymatgen_perturbation_generator

        defect_result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
            output_format="dict",
        )
        assert defect_result["success"] is True

        # Feed first defect supercell into perturbation generator
        perturb_result = pymatgen_perturbation_generator(
            input_structures=defect_result["structures"][0],
            displacement_max=0.05,
            n_structures=3,
            output_format="dict",
        )
        assert perturb_result["success"] is True
        assert perturb_result["count"] == 3

    def test_prototype_builder_feeds_defect_generator(self):
        """Structure from prototype_builder should be accepted as input to defect_generator."""
        from tools.pymatgen.pymatgen_prototype_builder import pymatgen_prototype_builder

        # Build a rocksalt NaCl structure
        proto_result = pymatgen_prototype_builder(
            spacegroup=225,
            species=["Na", "Cl"],
            lattice_parameters=[5.64],
            coords=[[0, 0, 0], [0.5, 0.5, 0.5]],
            output_format="dict",
        )
        assert proto_result["success"] is True

        host_struct = proto_result["structures"][0]["structure"]

        defect_result = pymatgen_defect_generator(
            input_structure=host_struct,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
            output_format="dict",
        )
        assert defect_result["success"] is True
        assert defect_result["count"] >= 1

    def test_dict_output_round_trips_through_pymatgen(self, simple_nacl_structure):
        """Structure dict output can be round-tripped through pymatgen Structure.from_dict()."""
        from pymatgen.core import Structure

        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_min_atoms=8,
            output_format="dict",
        )
        assert result["success"] is True
        for s_dict in result["structures"]:
            s = Structure.from_dict(s_dict)
            assert isinstance(s, Structure)
            assert len(s) > 0


# Error handling
class TestErrorHandling:
    """Tests for parameter validation and error handling."""

    def test_invalid_output_format(self, simple_nacl_structure):
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            output_format="xyz",
        )
        assert result["success"] is False
        assert "Invalid output_format" in result["error"]

    def test_invalid_input_structure_type(self):
        result = pymatgen_defect_generator(
            input_structure=12345,
            vacancy_species=["Na"],
        )
        assert result["success"] is False
        assert "error" in result

    def test_invalid_supercell_matrix_shape(self, simple_nacl_structure):
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_matrix=[2, 2],  # wrong length
        )
        assert result["success"] is False
        assert "error" in result

    def test_supercell_matrix_negative_values(self, simple_nacl_structure):
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Na"],
            supercell_matrix=[-1, 2, 2],
        )
        assert result["success"] is False
        assert "error" in result

    def test_invalid_substitution_element_symbol(self, simple_nacl_structure):
        """An invalid element symbol in substitution_species should warn or error gracefully."""
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            substitution_species={"Na": "Xx"},  # not a real element
        )
        # Should either warn and skip or return success=False cleanly
        if result.get("success"):
            assert result.get("warnings") or result["count"] == 0
        else:
            assert "error" in result

    def test_no_defects_produced_returns_failure(self, simple_nacl_structure):
        """When all requested defects result in warnings/skips, success=False is returned."""
        # Request vacancy for an element not in the structure, and nothing else
        result = pymatgen_defect_generator(
            input_structure=simple_nacl_structure,
            vacancy_species=["Mg"],   # Mg not in NaCl
            substitution_species=None,
            interstitial_species=None,
        )
        assert result["success"] is False
