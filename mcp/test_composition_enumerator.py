"""
Quick test of composition_enumerator for Pr-Mo-O system.
"""

import sys
sys.path.insert(0, '.')

from tools.composition_generation import composition_enumerator

# Test 1: Pr-Mo-O system (the motivating example)
print("=" * 80)
print("Test 1: Pr-Mo-O System (Pr4MoO9 Discovery)")
print("=" * 80)

result = composition_enumerator(
    elements=['Pr', 'Mo', 'O'],
    oxidation_states={'Pr': [3, 4], 'Mo': [6], 'O': [-2]},
    max_formula_units=6,
    max_atoms_per_formula=30,
    output_format='detailed'
)

print(f"\nSuccess: {result['success']}")
print(f"Total compositions: {result['count']}")
print(f"\nMessage: {result['message']}")

if result['success']:
    print(f"\nFirst 10 compositions:")
    for i, comp in enumerate(result['compositions'][:10], 1):
        print(f"{i:2d}. {comp['reduced_formula']:15s} "
              f"(atoms={comp['total_atoms']:2d}, "
              f"O/cation={comp['anion_cation_ratio']:.2f}, "
              f"oxidation: Pr={comp['oxidation_state_assignment']['Pr']}, "
              f"Mo={comp['oxidation_state_assignment']['Mo']})")
    
    # Check if Pr4MoO9 is in the results
    formulas = [c['reduced_formula'] for c in result['compositions']]
    if 'Pr4MoO9' in formulas:
        print(f"\n✅ SUCCESS: Pr4MoO9 found in results!")
        pr4moo9 = next(c for c in result['compositions'] if c['reduced_formula'] == 'Pr4MoO9')
        print(f"   Details: {pr4moo9}")
    else:
        print(f"\n❌ WARNING: Pr4MoO9 NOT found in results")
        print(f"   All formulas: {formulas}")
    
    print(f"\nMetadata:")
    print(f"  Cations: {result['metadata']['classification']['cations']}")
    print(f"  Anions: {result['metadata']['classification']['anions']}")
    print(f"  Atom count range: {result['metadata']['statistics']['complexity_range']}")

print("\n" + "=" * 80)
print("Test 2: Minimal Output Format")
print("=" * 80)

result2 = composition_enumerator(
    elements=['Pr', 'Mo', 'O'],
    oxidation_states={'Pr': [3, 4], 'Mo': [6], 'O': [-2]},
    max_formula_units=4,
    output_format='minimal'
)

if result2['success']:
    print(f"\nCompositions (minimal format):")
    for formula in result2['compositions']:
        print(f"  - {formula}")

print("\n" + "=" * 80)
print("Test 3: Cu-Cr-Se System (from literature)")
print("=" * 80)

result3 = composition_enumerator(
    elements=['Cu', 'Cr', 'Se'],
    oxidation_states={'Cu': [1, 2], 'Cr': [2, 3], 'Se': [-2]},
    max_formula_units=5,
    output_format='minimal'
)

if result3['success']:
    print(f"\nGenerated {result3['count']} Cu-Cr-Se compositions:")
    for formula in result3['compositions'][:15]:
        print(f"  - {formula}")

print("\n" + "=" * 80)
print("Test 4: Li-Fe-P-O (LiFePO4 battery cathode)")
print("=" * 80)

result4 = composition_enumerator(
    elements=['Li', 'Fe', 'P', 'O'],
    oxidation_states={'Li': [1], 'Fe': [2, 3], 'P': [5], 'O': [-2]},
    max_formula_units=4,
    output_format='minimal'
)

if result4['success']:
    print(f"\nGenerated {result4['count']} Li-Fe-P-O compositions:")
    for formula in result4['compositions'][:10]:
        print(f"  - {formula}")
    
    if 'LiFePO4' in result4['compositions']:
        print(f"\n✅ LiFePO4 found!")
    else:
        print(f"\n❌ LiFePO4 NOT found - check algorithm")

print("\n" + "=" * 80)
print("All tests complete!")
print("=" * 80)
