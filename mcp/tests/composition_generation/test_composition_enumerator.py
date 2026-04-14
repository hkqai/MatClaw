"""
Tests for composition_enumerator tool.

Run with: pytest tests/composition_generation/test_composition_enumerator.py -v
"""

import pytest
from tools.composition_generation import composition_enumerator


class TestBasicEnumeration:
    """Core functionality tests."""
    
    def test_pr_mo_o_finds_pr4moo9(self):
        """Pr-Mo-O system should generate Pr4MoO9 (motivating example)."""
        result = composition_enumerator(
            elements=['Pr', 'Mo', 'O'],
            oxidation_states={'Pr': [3, 4], 'Mo': [6], 'O': [-2]},
            max_formula_units=6
        )
        
        assert result['success'] is True
        assert result['count'] > 0
        
        formulas = [c['reduced_formula'] for c in result['compositions']]
        assert 'Pr4MoO9' in formulas, f"Pr4MoO9 not found. Generated: {formulas}"
    
    def test_lifepo4_battery_cathode(self):
        """Should generate LiFePO4 battery cathode composition."""
        result = composition_enumerator(
            elements=['Li', 'Fe', 'P', 'O'],
            oxidation_states={'Li': [1], 'Fe': [2], 'P': [5], 'O': [-2]},
            max_formula_units=4
        )
        
        assert result['success'] is True
        formulas = [c['reduced_formula'] for c in result['compositions']]
        assert 'LiFePO4' in formulas
    
    def test_cu_cr_se_semiconductor(self):
        """Cu-Cr-Se system (from literature)."""
        result = composition_enumerator(
            elements=['Cu', 'Cr', 'Se'],
            oxidation_states={'Cu': [1, 2], 'Cr': [3], 'Se': [-2]},
            max_formula_units=5
        )
        
        assert result['success'] is True
        assert result['count'] > 5  # Should generate multiple candidates
        
        # Check charge balance for all compositions
        for comp in result['compositions']:
            assert comp['charge_balanced'] is True


class TestOutputFormats:
    """Test different output format options."""
    
    def test_minimal_format_returns_strings(self):
        """Minimal format should return list of formula strings."""
        result = composition_enumerator(
            elements=['Li', 'O'],
            oxidation_states={'Li': [1], 'O': [-2]},
            max_formula_units=3,
            output_format='minimal'
        )
        
        assert result['success'] is True
        assert isinstance(result['compositions'], list)
        assert all(isinstance(f, str) for f in result['compositions'])
        assert 'Li2O' in result['compositions']
    
    def test_detailed_format_returns_dicts(self):
        """Detailed format should return list of dicts with metadata."""
        result = composition_enumerator(
            elements=['Li', 'O'],
            oxidation_states={'Li': [1], 'O': [-2]},
            max_formula_units=3,
            output_format='detailed'
        )
        
        assert result['success'] is True
        assert isinstance(result['compositions'], list)
        assert all(isinstance(c, dict) for c in result['compositions'])
        
        # Check required fields
        for comp in result['compositions']:
            assert 'formula' in comp
            assert 'reduced_formula' in comp
            assert 'total_atoms' in comp
            assert 'oxidation_state_assignment' in comp
            assert 'charge_balanced' in comp


class TestChemicalConstraints:
    """Test chemical filtering parameters."""
    
    def test_max_atoms_filter(self):
        """max_atoms_per_formula should limit composition size."""
        result = composition_enumerator(
            elements=['Fe', 'O'],
            oxidation_states={'Fe': [2, 3], 'O': [-2]},
            max_formula_units=10,
            max_atoms_per_formula=10
        )
        
        assert result['success'] is True
        for comp in result['compositions']:
            assert comp['total_atoms'] <= 10
    
    def test_anion_cation_ratio_filter(self):
        """anion_cation_ratio_max should exclude high-oxygen compositions."""
        result = composition_enumerator(
            elements=['Ti', 'O'],
            oxidation_states={'Ti': [4], 'O': [-2]},
            max_formula_units=5,
            anion_cation_ratio_max=2.5
        )
        
        assert result['success'] is True
        for comp in result['compositions']:
            assert comp['anion_cation_ratio'] <= 2.5
    
    def test_min_cation_fraction(self):
        """min_cation_fraction should prevent nearly-pure oxides."""
        result = composition_enumerator(
            elements=['Mg', 'O'],
            oxidation_states={'Mg': [2], 'O': [-2]},
            max_formula_units=5,
            min_cation_fraction=0.2
        )
        
        assert result['success'] is True
        for comp in result['compositions']:
            assert comp['cation_fraction'] >= 0.2


class TestRequireAllElements:
    """Test require_all_elements parameter."""
    
    def test_require_all_elements_true(self):
        """With require_all_elements=True, all elements must be present."""
        result = composition_enumerator(
            elements=['La', 'Ni', 'O'],
            oxidation_states={'La': [3], 'Ni': [2], 'O': [-2]},
            max_formula_units=3,
            require_all_elements=True
        )
        
        assert result['success'] is True
        for comp in result['compositions']:
            # All three elements should be present
            present_elements = set(comp['elements'].keys())
            assert present_elements == {'La', 'Ni', 'O'}
    
    def test_require_all_elements_false(self):
        """With require_all_elements=False, allows binary subsets."""
        result = composition_enumerator(
            elements=['La', 'Ni', 'O'],
            oxidation_states={'La': [3], 'Ni': [2], 'O': [-2]},
            max_formula_units=3,
            require_all_elements=False
        )
        
        assert result['success'] is True
        # Should find binary La-O and Ni-O compositions
        formulas = [c['reduced_formula'] for c in result['compositions']]
        # La2O3 and NiO should be present
        assert any('La' in f and 'Ni' not in f for f in formulas)  # La-O binaries
        assert any('Ni' in f and 'La' not in f for f in formulas)  # Ni-O binaries


class TestSorting:
    """Test sorting options."""
    
    def test_sort_by_atoms(self):
        """sort_by='atoms' should sort by total atom count."""
        result = composition_enumerator(
            elements=['Fe', 'O'],
            oxidation_states={'Fe': [2, 3], 'O': [-2]},
            max_formula_units=5,
            sort_by='atoms'
        )
        
        assert result['success'] is True
        atom_counts = [c['total_atoms'] for c in result['compositions']]
        assert atom_counts == sorted(atom_counts)
    
    def test_sort_by_anion_ratio(self):
        """sort_by='anion_ratio' should sort by O/cation ratio."""
        result = composition_enumerator(
            elements=['Fe', 'O'],
            oxidation_states={'Fe': [2, 3], 'O': [-2]},
            max_formula_units=5,
            sort_by='anion_ratio'
        )
        
        assert result['success'] is True
        ratios = [c['anion_cation_ratio'] for c in result['compositions']]
        assert ratios == sorted(ratios)


class TestDeduplication:
    """Test deduplication behavior."""
    
    def test_deduplicate_true_removes_duplicates(self):
        """With deduplicate=True, should have no duplicate reduced formulas."""
        result = composition_enumerator(
            elements=['Fe', 'O'],
            oxidation_states={'Fe': [2, 3], 'O': [-2]},
            max_formula_units=6,
            deduplicate=True
        )
        
        assert result['success'] is True
        formulas = [c['reduced_formula'] for c in result['compositions']]
        assert len(formulas) == len(set(formulas)), "Found duplicate formulas"


class TestErrorHandling:
    """Test error cases and validation."""
    
    def test_missing_oxidation_states(self):
        """Should error if oxidation states not provided for all elements."""
        result = composition_enumerator(
            elements=['La', 'Mo', 'O'],
            oxidation_states={'La': [3], 'O': [-2]}  # Missing Mo
        )
        
        assert result['success'] is False
        assert 'Missing oxidation states' in result['error']
    
    def test_no_cations(self):
        """Should error if no cations (all negative oxidation states)."""
        result = composition_enumerator(
            elements=['O', 'F'],
            oxidation_states={'O': [-2], 'F': [-1]}
        )
        
        assert result['success'] is False
        assert 'cation' in result['error'].lower()
    
    def test_no_anions(self):
        """Should error if no anions (all positive oxidation states)."""
        result = composition_enumerator(
            elements=['Li', 'Na'],
            oxidation_states={'Li': [1], 'Na': [1]}
        )
        
        assert result['success'] is False
        assert 'anion' in result['error'].lower()
    
    def test_single_element(self):
        """Should error if only one element provided."""
        result = composition_enumerator(
            elements=['O'],
            oxidation_states={'O': [-2]}
        )
        
        assert result['success'] is False
        assert 'at least 2 elements' in result['error'].lower()


class TestMixedValence:
    """Test mixed-valence handling."""
    
    def test_allow_mixed_valence_true(self):
        """With allow_mixed_valence=True, should generate Pr4MoO9 type compositions."""
        result = composition_enumerator(
            elements=['Pr', 'Mo', 'O'],
            oxidation_states={'Pr': [3, 4], 'Mo': [6], 'O': [-2]},
            max_formula_units=6,
            allow_mixed_valence=True
        )
        
        assert result['success'] is True
        # Pr4MoO9: 4(+3) + 1(+6) + 9(-2) = 0 ✓
        formulas = [c['reduced_formula'] for c in result['compositions']]
        assert 'Pr4MoO9' in formulas


class TestMetadata:
    """Test metadata output."""
    
    def test_metadata_includes_parameters(self):
        """Metadata should include enumeration parameters."""
        result = composition_enumerator(
            elements=['Li', 'O'],
            oxidation_states={'Li': [1], 'O': [-2]},
            max_formula_units=3
        )
        
        assert result['success'] is True
        assert 'metadata' in result
        assert 'enumeration_params' in result['metadata']
        assert result['metadata']['enumeration_params']['elements'] == ['Li', 'O']
    
    def test_metadata_classification(self):
        """Metadata should classify cations and anions."""
        result = composition_enumerator(
            elements=['Pr', 'Mo', 'O'],
            oxidation_states={'Pr': [3, 4], 'Mo': [6], 'O': [-2]},
            max_formula_units=3
        )
        
        assert result['success'] is True
        assert 'classification' in result['metadata']
        assert set(result['metadata']['classification']['cations']) == {'Pr', 'Mo'}
        assert set(result['metadata']['classification']['anions']) == {'O'}


class TestRealWorldExamples:
    """Test real materials discovery scenarios."""
    
    def test_perovskite_discovery(self):
        """Should generate perovskite-type ABO3 compositions."""
        result = composition_enumerator(
            elements=['Ca', 'Ti', 'O'],
            oxidation_states={'Ca': [2], 'Ti': [4], 'O': [-2]},
            max_formula_units=4
        )
        
        assert result['success'] is True
        formulas = [c['reduced_formula'] for c in result['compositions']]
        assert 'CaTiO3' in formulas  # Perovskite
    
    def test_spinel_discovery(self):
        """Should generate spinel-type AB2O4 compositions."""
        result = composition_enumerator(
            elements=['Mg', 'Al', 'O'],
            oxidation_states={'Mg': [2], 'Al': [3], 'O': [-2]},
            max_formula_units=5
        )
        
        assert result['success'] is True
        formulas = [c['reduced_formula'] for c in result['compositions']]
        assert 'MgAl2O4' in formulas  # Spinel
