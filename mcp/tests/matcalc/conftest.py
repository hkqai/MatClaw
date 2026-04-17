"""
Shared fixtures for matcalc tests.
"""

import pytest
from pymatgen.core import Lattice, Structure


@pytest.fixture
def cubic_si_structure():
    """Fixture providing a simple cubic Si structure for testing."""
    # Diamond cubic Si structure (slightly compressed for testing)
    lattice = Lattice.cubic(5.43)  # Si lattice constant in Angstroms
    return Structure(
        lattice,
        ["Si", "Si"],
        [[0, 0, 0], [0.25, 0.25, 0.25]],
    )


@pytest.fixture
def cubic_cscl_structure():
    """Fixture providing a simple CsCl structure for testing."""
    # CsCl structure (Pm-3m)
    return Structure.from_spacegroup(
        "Pm-3m",
        Lattice.cubic(4.2),
        ["Cs", "Cl"],
        [[0, 0, 0], [0.5, 0.5, 0.5]]
    )


@pytest.fixture
def cubic_nacl_structure():
    """Fixture providing a simple NaCl structure for testing."""
    # NaCl structure (Fm-3m, rocksalt)
    lattice = Lattice.cubic(5.64)
    return Structure(
        lattice,
        ["Na", "Cl"],
        [[0, 0, 0], [0.5, 0.5, 0.5]],
    )


@pytest.fixture
def stressed_structure():
    """Fixture providing a stressed structure (needs relaxation)."""
    # CsCl with intentionally wrong lattice constant
    return Structure.from_spacegroup(
        "Pm-3m",
        Lattice.cubic(4.5),  # Too large
        ["Cs", "Cl"],
        [[0, 0, 0], [0.5, 0.5, 0.5]]
    )


@pytest.fixture
def cif_string_si():
    """Fixture providing a Si structure as CIF string."""
    # Simple cubic primitive cell with P1 symmetry (no symmetry operations)
    return """data_Si
_cell_length_a 5.43
_cell_length_b 5.43
_cell_length_c 5.43
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_symmetry_space_group_name_H-M 'P 1'
_symmetry_Int_Tables_number 1
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Si1 Si 0.0 0.0 0.0 1.0
Si2 Si 0.25 0.25 0.25 1.0
"""
