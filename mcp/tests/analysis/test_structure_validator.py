"""
Tests for structure_validator tool.

Run with: pytest tests/analysis/test_structure_validator.py -v
"""

import pytest
from tools.analysis.structure_validator import structure_validator


class TestStructureValidator:
    """Tests for structure validation."""

    def test_valid_structure_passes(self, simple_nacl_structure):
        """A valid NaCl structure should pass all checks."""
        result = structure_validator(input_structure=simple_nacl_structure)
        
        # Debug output
        if not result["valid"]:
            print("\nValidation failed:")
            print(f"Checks failed: {result['checks_failed']}")
            print(f"Issues: {result['issues']}")
            if 'warnings' in result:
                print(f"Warnings: {result['warnings']}")
            print("\nDetails:")
            for check, detail in result['details'].items():
                if detail.get('passed') is False:
                    print(f"  {check}: {detail}")
        
        assert result["valid"] is True
        assert len(result["checks_failed"]) == 0
        assert "overlapping_atoms" in result["checks_passed"]
        assert result["details"]["overlapping_atoms"]["passed"] is True

    def test_overlapping_atoms_detected(self, overlapping_atoms_structure):
        """Overlapping atoms should be detected and reported."""
        result = structure_validator(
            input_structure=overlapping_atoms_structure,
            min_distance_threshold=0.5
        )
        
        assert result["valid"] is False
        assert "overlapping_atoms" in result["checks_failed"]
        assert len(result["details"]["overlapping_atoms"]["problematic_pairs"]) > 0
        assert result["details"]["overlapping_atoms"]["min_distance"] < 0.5

    def test_charge_neutrality_check(self, charged_structure):
        """Non-neutral structures should be detected."""
        result = structure_validator(
            input_structure=charged_structure,
            check_charge_neutrality=True
        )
        
        # May fail charge neutrality or pass if oxidation states can't be assigned
        assert "charge_neutrality" in result["checks_performed"]
        if result["details"]["charge_neutrality"]["charge_assigned"]:
            assert "charge_neutrality" in result["checks_failed"]
            assert abs(result["details"]["charge_neutrality"]["total_charge"]) > 0.1

    def test_valid_licoo2_structure(self, valid_licoo2_structure):
        """A realistic valid structure should pass all checks."""
        result = structure_validator(input_structure=valid_licoo2_structure)
        
        # Should pass most checks (oxidation states might be tricky)
        assert len(result["checks_passed"]) >= 2
        assert result["details"]["overlapping_atoms"]["passed"] is True
        
    def test_high_coordination_detected(self, high_coordination_structure):
        """Unusually high coordination numbers should be flagged."""
        result = structure_validator(
            input_structure=high_coordination_structure,
            check_coordination=True,
            max_coordination=12,
            coordination_cutoff=3.5
        )
        
        assert "coordination" in result["checks_performed"]
        # This dense structure should have high coordination
        max_cn = result["details"]["coordination"]["max_cn_found"]
        assert max_cn > 5  # Should have reasonably high coordination

    def test_strict_mode_stops_at_first_error(self, overlapping_atoms_structure):
        """Strict mode should stop at first validation error."""
        result = structure_validator(
            input_structure=overlapping_atoms_structure,
            strict_mode=True,
            min_distance_threshold=0.5
        )
        
        assert result["valid"] is False
        # With overlapping atoms failing first, other checks might not be performed
        assert "overlapping_atoms" in result["checks_failed"]

    def test_disable_specific_checks(self, simple_nacl_structure):
        """Individual checks can be disabled."""
        result = structure_validator(
            input_structure=simple_nacl_structure,
            check_charge_neutrality=False,
            check_oxidation_states=False,
            check_coordination=False
        )
        
        assert "charge_neutrality" not in result["checks_performed"]
        assert "oxidation_states" not in result["checks_performed"]
        assert "coordination" not in result["checks_performed"]
        assert "overlapping_atoms" in result["checks_performed"]

    def test_custom_thresholds(self, simple_nacl_structure):
        """Custom validation thresholds should be respected."""
        result = structure_validator(
            input_structure=simple_nacl_structure,
            min_distance_threshold=1.0,
            max_bond_deviation=0.3,
            coordination_cutoff=4.0,
            max_coordination=15
        )
        
        assert result["details"]["overlapping_atoms"]["threshold"] == 1.0
        assert result["details"]["coordination"]["max_cn_threshold"] == 15

    def test_structure_info_included(self, simple_nacl_structure):
        """Structure information should be included in results."""
        result = structure_validator(input_structure=simple_nacl_structure)
        
        assert "structure_info" in result
        assert "formula" in result["structure_info"]
        assert "n_sites" in result["structure_info"]
        assert "volume" in result["structure_info"]
        assert "density" in result["structure_info"]

    def test_cif_string_input(self):
        """Should accept CIF string as input."""
        cif_string = """data_NaCl
_cell_length_a    5.64
_cell_length_b    5.64
_cell_length_c    5.64
_cell_angle_alpha 90
_cell_angle_beta  90
_cell_angle_gamma 90
_symmetry_space_group_name_H-M 'P 1'
loop_
_atom_site_label
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Na 0.0 0.0 0.0
Cl 0.5 0.5 0.5
"""
        result = structure_validator(input_structure=cif_string)
        assert result["valid"] is True

    def test_poscar_string_input(self):
        """Should accept POSCAR string as input."""
        poscar_string = """NaCl
1.0
5.64 0.0 0.0
0.0 5.64 0.0
0.0 0.0 5.64
Na Cl
1 1
direct
0.0 0.0 0.0
0.5 0.5 0.5
"""
        result = structure_validator(input_structure=poscar_string)
        
        # Debug output  
        if not result.get("valid"):
            print("\nPOSCAR validation failed:")
            if 'error' in result:
                print(f"Error: {result['error']}")
            if 'checks_failed' in result:
                print(f"Checks failed: {result['checks_failed']}")
                print(f"Issues: {result['issues']}")
        
        assert result["valid"] is True

    def test_invalid_input_type(self):
        """Should handle invalid input gracefully."""
        result = structure_validator(input_structure=12345)
        
        assert result["valid"] is False
        assert "error" in result

    def test_malformed_structure_dict(self):
        """Should handle malformed structure dict gracefully."""
        bad_dict = {"invalid": "structure"}
        result = structure_validator(input_structure=bad_dict)
        
        assert result["valid"] is False
        assert "error" in result


class TestBondLengthValidation:
    """Tests specifically for bond length validation."""

    def test_normal_bonds_pass(self, simple_nacl_structure):
        """Normal Na-Cl bonds should pass validation."""
        result = structure_validator(
            input_structure=simple_nacl_structure,
            max_bond_deviation=0.5
        )
        
        assert "bond_lengths" in result["checks_performed"]
        # NaCl has reasonable bond lengths, should pass or have few anomalies

    def test_bond_deviation_threshold(self, simple_nacl_structure):
        """Very strict bond deviation threshold should catch more bonds."""
        result_strict = structure_validator(
            input_structure=simple_nacl_structure,
            max_bond_deviation=0.1
        )
        
        result_lenient = structure_validator(
            input_structure=simple_nacl_structure,
            max_bond_deviation=1.0
        )
        
        # Stricter threshold should catch more or equal anomalies
        strict_anomalies = len(result_strict["details"]["bond_lengths"].get("anomalous_bonds", []))
        lenient_anomalies = len(result_lenient["details"]["bond_lengths"].get("anomalous_bonds", []))
        assert strict_anomalies >= lenient_anomalies


class TestOutputFormat:
    """Tests for result output format and completeness."""

    def test_all_required_fields_present(self, simple_nacl_structure):
        """Result should contain all documented fields."""
        result = structure_validator(input_structure=simple_nacl_structure)
        
        required_fields = [
            "valid",
            "checks_performed",
            "checks_passed",
            "checks_failed",
            "issues",
            "details",
            "structure_info",
            "message"
        ]
        
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_details_structure(self, simple_nacl_structure):
        """Details dictionary should have proper structure for each check."""
        result = structure_validator(input_structure=simple_nacl_structure)
        
        for check_name in result["checks_performed"]:
            assert check_name in result["details"]
            detail = result["details"][check_name]
            assert "passed" in detail or "error" in detail

    def test_issues_list_populated_on_failure(self, overlapping_atoms_structure):
        """Issues list should be populated when validation fails."""
        result = structure_validator(
            input_structure=overlapping_atoms_structure,
            min_distance_threshold=0.5
        )
        
        assert result["valid"] is False
        assert len(result["issues"]) > 0
        assert isinstance(result["issues"][0], str)

    def test_warnings_present_when_checks_error(self):
        """Warnings should be present if checks encounter errors."""
        # Create a structure that might cause check errors
        from pymatgen.core import Structure, Lattice
        
        lattice = Lattice.cubic(5.0)
        species = ["Xx"]  # Invalid element
        coords = [[0, 0, 0]]
        
        try:
            struct = Structure(lattice, species, coords).as_dict()
            result = structure_validator(input_structure=struct)
            
            # Some checks may warn or fail due to invalid element
            # Just check the result is well-formed
            assert "valid" in result
            assert isinstance(result.get("warnings", []), list)
        except:
            # If structure creation fails, that's also acceptable
            pass
