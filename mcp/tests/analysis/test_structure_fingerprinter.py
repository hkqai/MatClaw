"""
Tests for structure_fingerprinter tool.

Run with:
  pytest tests/analysis/test_structure_fingerprinter.py -v

All tests use local computation (dscribe) and do NOT require an API key.
"""

import pytest
import math
from tools.analysis.structure_fingerprinter import structure_fingerprinter

def _is_finite_list(obj) -> bool:
    """Return True if obj is a non-empty list of finite floats."""
    if not isinstance(obj, list) or len(obj) == 0:
        return False
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in obj)


def _cosine_similarity(a, b) -> float:
    """Cosine similarity between two flat lists."""
    import math
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class TestSOAP:
    """Tests for SOAP representation."""

    def test_soap_basic_output(self, simple_nacl_structure):
        """SOAP produces a valid dict with a 1-D fingerprint vector."""
        result = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            representations=["soap"],
        )

        assert result["success"] is True
        assert "soap" in result["representations"]
        soap = result["representations"]["soap"]
        assert "vector" in soap
        assert "length" in soap
        assert "n_features" in soap
        assert "species" in soap

    def test_soap_vector_finite(self, simple_nacl_structure):
        """SOAP vector contains only finite floats (no NaN / inf)."""
        result = structure_fingerprinter(input_structure=simple_nacl_structure)
        vec = result["representations"]["soap"]["vector"]
        assert _is_finite_list(vec)

    def test_soap_vector_length_matches(self, simple_nacl_structure):
        """Reported length matches actual vector length."""
        result = structure_fingerprinter(input_structure=simple_nacl_structure)
        soap = result["representations"]["soap"]
        assert soap["length"] == len(soap["vector"])

    def test_soap_inferred_species(self, simple_nacl_structure):
        """Species are correctly inferred from the structure."""
        result = structure_fingerprinter(input_structure=simple_nacl_structure)
        species = result["representations"]["soap"]["species"]
        assert "Na" in species
        assert "Cl" in species

    def test_soap_per_site_mode(self, simple_nacl_structure):
        """soap_average='off' returns per-site vectors."""
        result = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            soap_average="off",
        )
        assert result["success"] is True
        soap = result["representations"]["soap"]
        # length should be a list [n_sites, n_features]
        assert isinstance(soap["length"], list)
        assert len(soap["length"]) == 2
        n_sites, n_feat = soap["length"]
        assert n_sites == result["n_sites"]
        assert len(soap["vector"]) == n_sites
        # Each row has n_feat values
        assert all(len(row) == n_feat for row in soap["vector"])

    def test_soap_hyperparameter_effect(self, simple_nacl_structure):
        """Changing n_max / l_max changes the feature vector length."""
        result_small = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            soap_n_max=3,
            soap_l_max=2,
        )
        result_large = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            soap_n_max=8,
            soap_l_max=6,
        )
        len_small = result_small["representations"]["soap"]["length"]
        len_large = result_large["representations"]["soap"]["length"]
        assert len_large > len_small

    def test_soap_deterministic(self, simple_nacl_structure):
        """Same input produces identical output on repeated calls."""
        r1 = structure_fingerprinter(input_structure=simple_nacl_structure)
        r2 = structure_fingerprinter(input_structure=simple_nacl_structure)
        assert r1["representations"]["soap"]["vector"] == r2["representations"]["soap"]["vector"]

    def test_soap_different_structures_differ(self, simple_nacl_structure, valid_licoo2_structure):
        """Different structures produce different SOAP fingerprints."""
        r1 = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            species=["Na", "Cl", "Li", "Co", "O"],
        )
        r2 = structure_fingerprinter(
            input_structure=valid_licoo2_structure,
            species=["Na", "Cl", "Li", "Co", "O"],
        )
        assert r1["representations"]["soap"]["vector"] != r2["representations"]["soap"]["vector"]

    def test_soap_same_structure_high_cosine_similarity(self, simple_nacl_structure):
        """Same structure with identical fingerprint should have cosine sim ≈ 1."""
        result = structure_fingerprinter(
            input_structure=simple_nacl_structure, normalize=True
        )
        vec = result["representations"]["soap"]["vector"]
        sim = _cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 1e-6

    def test_soap_explicit_species(self, simple_nacl_structure, valid_licoo2_structure):
        """Explicit species produce consistent-length vectors across structures."""
        shared = ["Li", "Na", "Cl", "Co", "O"]
        r1 = structure_fingerprinter(input_structure=simple_nacl_structure, species=shared)
        r2 = structure_fingerprinter(input_structure=valid_licoo2_structure, species=shared)
        assert r1["representations"]["soap"]["length"] == r2["representations"]["soap"]["length"]

    def test_soap_normalize(self, simple_nacl_structure):
        """Normalized SOAP vector has unit L2 norm."""
        result = structure_fingerprinter(
            input_structure=simple_nacl_structure, normalize=True
        )
        vec = result["representations"]["soap"]["vector"]
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 1e-5
        assert result["normalized"] is True


class TestMBTR:
    """Tests for MBTR representation."""

    def test_mbtr_basic_output(self, simple_nacl_structure):
        """MBTR produces a valid 1-D fingerprint."""
        result = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            representations=["mbtr"],
        )
        assert result["success"] is True
        mbtr = result["representations"]["mbtr"]
        assert "vector" in mbtr
        assert "length" in mbtr
        assert "species" in mbtr
        assert _is_finite_list(mbtr["vector"])

    def test_mbtr_vector_length_matches(self, simple_nacl_structure):
        """Reported length matches actual vector length."""
        result = structure_fingerprinter(
            input_structure=simple_nacl_structure, representations=["mbtr"]
        )
        mbtr = result["representations"]["mbtr"]
        assert mbtr["length"] == len(mbtr["vector"])

    def test_mbtr_k_subset(self, simple_nacl_structure):
        """Using fewer k-terms produces a shorter vector."""
        r123 = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            representations=["mbtr"],
            mbtr_k=[1, 2, 3],
        )
        r1 = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            representations=["mbtr"],
            mbtr_k=[1],
        )
        assert r1["representations"]["mbtr"]["length"] < r123["representations"]["mbtr"]["length"]

    def test_mbtr_grid_n_effect(self, simple_nacl_structure):
        """Larger grid_n produces longer MBTR vector."""
        r_s = structure_fingerprinter(
            input_structure=simple_nacl_structure, representations=["mbtr"], mbtr_grid_n=20
        )
        r_l = structure_fingerprinter(
            input_structure=simple_nacl_structure, representations=["mbtr"], mbtr_grid_n=80
        )
        assert r_l["representations"]["mbtr"]["length"] > r_s["representations"]["mbtr"]["length"]


class TestSineMatrix:
    """Tests for Sine Matrix (periodic Coulomb eigenspectrum)."""

    def test_sine_matrix_basic_output(self, simple_nacl_structure):
        """Sine Matrix produces a valid eigenspectrum vector."""
        result = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            representations=["sine_matrix"],
        )
        assert result["success"] is True
        sm = result["representations"]["sine_matrix"]
        assert "vector" in sm
        assert "length" in sm
        assert _is_finite_list(sm["vector"])

    def test_sine_matrix_length_equals_n_atoms(self, simple_nacl_structure):
        """Eigenspectrum length equals n_atoms_max (auto)."""
        result = structure_fingerprinter(
            input_structure=simple_nacl_structure, representations=["sine_matrix"]
        )
        n_sites = result["n_sites"]
        sm_len = result["representations"]["sine_matrix"]["length"]
        assert sm_len == n_sites

    def test_sine_matrix_explicit_n_atoms_max(self, simple_nacl_structure):
        """Explicit matrix_n_atoms_max is respected."""
        result = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            representations=["sine_matrix"],
            matrix_n_atoms_max=10,
        )
        assert result["representations"]["sine_matrix"]["length"] == 10

    def test_sine_matrix_consistent_length_padded(self, simple_nacl_structure, valid_licoo2_structure):
        """With shared n_atoms_max both structures get same-length vectors."""
        max_n = 10
        r1 = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            representations=["sine_matrix"],
            matrix_n_atoms_max=max_n,
        )
        r2 = structure_fingerprinter(
            input_structure=valid_licoo2_structure,
            representations=["sine_matrix"],
            matrix_n_atoms_max=max_n,
        )
        assert r1["representations"]["sine_matrix"]["length"] == max_n
        assert r2["representations"]["sine_matrix"]["length"] == max_n


class TestCoulombMatrix:
    """Tests for Coulomb Matrix eigenspectrum."""

    def test_coulomb_matrix_basic_output(self, simple_nacl_structure):
        """Coulomb Matrix produces a valid eigenspectrum vector."""
        result = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            representations=["coulomb_matrix"],
        )
        assert result["success"] is True
        cm = result["representations"]["coulomb_matrix"]
        assert "vector" in cm
        assert _is_finite_list(cm["vector"])

    def test_coulomb_matrix_explicit_n_atoms_max(self, simple_nacl_structure):
        """Explicit matrix_n_atoms_max is respected."""
        result = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            representations=["coulomb_matrix"],
            matrix_n_atoms_max=8,
        )
        assert result["representations"]["coulomb_matrix"]["length"] == 8


class TestMultiRepresentation:
    """Tests for computing multiple representations at once."""

    def test_soap_and_mbtr_together(self, simple_nacl_structure):
        """SOAP and MBTR can be computed in a single call."""
        result = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            representations=["soap", "mbtr"],
        )
        assert result["success"] is True
        assert "soap" in result["representations"]
        assert "mbtr" in result["representations"]
        assert "vector" in result["representations"]["soap"]
        assert "vector" in result["representations"]["mbtr"]

    def test_all_representations(self, simple_nacl_structure):
        """All four representations computed simultaneously."""
        result = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            representations=["soap", "mbtr", "sine_matrix", "coulomb_matrix"],
        )
        assert result["success"] is True
        reps = result["representations"]
        for name in ("soap", "mbtr", "sine_matrix", "coulomb_matrix"):
            assert name in reps
            assert "vector" in reps[name], f"{name} has no 'vector' key"

    def test_metadata_tracks_successful_reps(self, simple_nacl_structure):
        """metadata.successful_representations lists what was computed."""
        result = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            representations=["soap", "mbtr"],
        )
        assert "soap" in result["metadata"]["successful_representations"]
        assert "mbtr" in result["metadata"]["successful_representations"]


class TestInputParsing:
    """Tests for various input format handling."""

    def test_structure_dict_input(self, simple_nacl_structure):
        """Pymatgen Structure dict is accepted."""
        result = structure_fingerprinter(input_structure=simple_nacl_structure)
        assert result["success"] is True
        assert result["composition"] == "NaCl"

    def test_cif_string_input(self):
        """CIF string input is accepted."""
        cif_nacl = """data_NaCl
_cell_length_a   5.6402
_cell_length_b   5.6402
_cell_length_c   5.6402
_cell_angle_alpha   90.0
_cell_angle_beta    90.0
_cell_angle_gamma   90.0
_symmetry_space_group_name_H-M   'F m -3 m'

loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Na1 Na 0.0 0.0 0.0
Cl1 Cl 0.5 0.5 0.5
"""
        result = structure_fingerprinter(input_structure=cif_nacl)
        assert result["success"] is True
        assert "Na" in result["species_used"] or "Cl" in result["species_used"]

    def test_invalid_dict_type(self):
        """Non-Structure dict returns error."""
        result = structure_fingerprinter(
            input_structure={"foo": "bar", "@module": "some.other.module", "@class": "SomeClass"}
        )
        assert result["success"] is False
        assert "error" in result

    def test_empty_string_input(self):
        """Empty string returns error."""
        result = structure_fingerprinter(input_structure="")
        assert result["success"] is False
        assert "error" in result

    def test_invalid_representation_name(self, simple_nacl_structure):
        """Unknown representation names return error."""
        result = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            representations=["unknown_rep"],
        )
        assert result["success"] is False
        assert "error" in result

    def test_empty_representations_list(self, simple_nacl_structure):
        """Empty representations list returns error."""
        result = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            representations=[],
        )
        assert result["success"] is False
        assert "error" in result

    def test_invalid_soap_average(self, simple_nacl_structure):
        """Invalid soap_average value returns error."""
        result = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            soap_average="invalid",
        )
        assert result["success"] is False
        assert "soap_average" in result["error"]


class TestOutputStructure:
    """Tests for response object structure and top-level fields."""

    def test_top_level_fields(self, simple_nacl_structure):
        """Required top-level keys are present on success."""
        result = structure_fingerprinter(input_structure=simple_nacl_structure)
        for key in ("success", "composition", "n_sites", "species_used",
                    "representations", "normalized", "metadata", "message"):
            assert key in result, f"Missing key: {key}"

    def test_composition_field(self, simple_nacl_structure):
        """Composition is reduced formula string."""
        result = structure_fingerprinter(input_structure=simple_nacl_structure)
        assert result["composition"] == "NaCl"

    def test_n_sites_field(self, simple_nacl_structure):
        """n_sites matches actual atom count."""
        result = structure_fingerprinter(input_structure=simple_nacl_structure)
        assert result["n_sites"] == 2

    def test_message_is_string(self, simple_nacl_structure):
        """message field is a non-empty string."""
        result = structure_fingerprinter(input_structure=simple_nacl_structure)
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0

    def test_normalized_false_by_default(self, simple_nacl_structure):
        """normalized field defaults to False."""
        result = structure_fingerprinter(input_structure=simple_nacl_structure)
        assert result["normalized"] is False

    def test_metadata_fields(self, simple_nacl_structure):
        """metadata contains expected fields."""
        result = structure_fingerprinter(input_structure=simple_nacl_structure)
        meta = result["metadata"]
        for key in ("n_atoms_max", "requested_representations",
                    "successful_representations", "failed_representations"):
            assert key in meta, f"Missing metadata key: {key}"

    def test_vectors_json_serializable(self, simple_nacl_structure):
        """All output vectors are JSON-serializable (plain Python lists)."""
        import json
        result = structure_fingerprinter(
            input_structure=simple_nacl_structure,
            representations=["soap", "sine_matrix", "coulomb_matrix"],
        )
        # Should not raise
        json.dumps(result)
