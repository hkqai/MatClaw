"""
Pytest fixtures shared across pymatgen tool tests.
"""

import pytest


@pytest.fixture
def simple_lifep04_structure():
    """
    Fixture providing a simple LiFePO4-like structure for testing.
    
    Returns:
        dict: Structure dictionary compatible with pymatgen Structure.from_dict()
    """
    from pymatgen.core import Structure, Lattice
    
    lattice = Lattice.orthorhombic(10.3, 6.0, 4.7)
    structure = Structure(
        lattice,
        ["Li", "Li", "Fe", "Fe", "P", "P", "O", "O", "O", "O"],
        [
            [0.0, 0.0, 0.0],
            [0.5, 0.5, 0.5],
            [0.25, 0.25, 0.0],
            [0.75, 0.75, 0.5],
            [0.1, 0.4, 0.25],
            [0.9, 0.6, 0.75],
            [0.1, 0.2, 0.25],
            [0.9, 0.8, 0.75],
            [0.3, 0.25, 0.0],
            [0.7, 0.75, 0.5]
        ]
    )
    return structure.as_dict()


@pytest.fixture
def simple_lifep04_structure_obj():
    """
    Fixture providing a simple LiFePO4-like structure as a Structure object.
    
    Returns:
        Structure: Pymatgen Structure object
    """
    from pymatgen.core import Structure, Lattice
    
    lattice = Lattice.orthorhombic(10.3, 6.0, 4.7)
    structure = Structure(
        lattice,
        ["Li", "Li", "Fe", "Fe", "P", "P", "O", "O", "O", "O"],
        [
            [0.0, 0.0, 0.0],
            [0.5, 0.5, 0.5],
            [0.25, 0.25, 0.0],
            [0.75, 0.75, 0.5],
            [0.1, 0.4, 0.25],
            [0.9, 0.6, 0.75],
            [0.1, 0.2, 0.25],
            [0.9, 0.8, 0.75],
            [0.3, 0.25, 0.0],
            [0.7, 0.75, 0.5]
        ]
    )
    return structure


@pytest.fixture
def simple_nacl_structure():
    """
    Fixture providing a simple NaCl structure for testing.
    
    Returns:
        dict: Structure dictionary compatible with pymatgen Structure.from_dict()
    """
    from pymatgen.core import Structure, Lattice
    
    lattice = Lattice.cubic(5.64)
    structure = Structure(
        lattice,
        ["Na", "Cl"],
        [[0, 0, 0], [0.5, 0.5, 0.5]]
    )
    return structure.as_dict()


@pytest.fixture
def simple_nacl_structure_obj():
    """
    Fixture providing a simple NaCl structure as a Structure object.
    
    Returns:
        Structure: Pymatgen Structure object
    """
    from pymatgen.core import Structure, Lattice
    
    lattice = Lattice.cubic(5.64)
    structure = Structure(
        lattice,
        ["Na", "Cl"],
        [[0, 0, 0], [0.5, 0.5, 0.5]]
    )
    return structure


@pytest.fixture
def disordered_li_na_cl():
    """
    2-atom Li₀.₅/Na₀.₅ cation-disordered rocksalt structure (dict).

    The cation site carries 50% Li and 50% Na occupancy; the anion site is
    fully occupied by Cl.  Enumerating up to max_cell_size=2 produces a small,
    predictable set of ordered LiNaCl₂ / Li₂Cl₂ / Na₂Cl₂ approximants.

    Returns:
        dict: Structure.as_dict() with partial occupancy on the cation site.
    """
    from pymatgen.core import Structure, Lattice

    lattice = Lattice.cubic(4.0)
    structure = Structure(
        lattice,
        [{"Li": 0.5, "Na": 0.5}, "Cl"],
        [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
    )
    return structure.as_dict()


@pytest.fixture
def disordered_li_na_cl_obj():
    """
    Same as disordered_li_na_cl but returns the pymatgen Structure object.

    Returns:
        Structure: Pymatgen Structure object with partial cation occupancy.
    """
    from pymatgen.core import Structure, Lattice

    lattice = Lattice.cubic(4.0)
    return Structure(
        lattice,
        [{"Li": 0.5, "Na": 0.5}, "Cl"],
        [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
    )
