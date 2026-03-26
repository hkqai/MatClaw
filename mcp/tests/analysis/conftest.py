"""
Analysis tools test fixtures.
"""

import pytest
import os


@pytest.fixture
def simple_nacl_structure():
    """Simple NaCl rock salt structure for testing."""
    from pymatgen.core import Structure, Lattice
    
    lattice = Lattice.cubic(5.64)
    species = ["Na", "Cl"]
    coords = [[0, 0, 0], [0.5, 0.5, 0.5]]
    return Structure(lattice, species, coords).as_dict()


@pytest.fixture
def overlapping_atoms_structure():
    """Structure with two atoms too close together."""
    from pymatgen.core import Structure, Lattice
    
    lattice = Lattice.cubic(5.0)
    species = ["Na", "Na"]
    coords = [[0, 0, 0], [0.05, 0, 0]]  # Only 0.25 Å apart
    return Structure(lattice, species, coords).as_dict()


@pytest.fixture
def charged_structure():
    """Structure that is not charge neutral."""
    from pymatgen.core import Structure, Lattice, Species
    
    lattice = Lattice.cubic(5.0)
    # Two Na+ and no anion = net +2 charge
    species = [Species("Na", 1), Species("Na", 1)]
    coords = [[0, 0, 0], [0.5, 0.5, 0.5]]
    return Structure(lattice, species, coords).as_dict()


@pytest.fixture
def valid_licoo2_structure():
    """Valid LiCoO2 structure."""
    from pymatgen.core import Structure, Lattice
    
    # Layered LiCoO2 structure
    lattice = Lattice.from_parameters(2.82, 2.82, 14.05, 90, 90, 120)
    species = ["Li", "Co", "O", "O", "O", "O"]
    coords = [
        [0, 0, 0],
        [0, 0, 0.5],
        [0, 0, 0.25],
        [0, 0, 0.75],
        [0.333, 0.667, 0.25],
        [0.667, 0.333, 0.75],
    ]
    return Structure(lattice, species, coords).as_dict()


@pytest.fixture
def high_coordination_structure():
    """Structure with unusually high coordination number."""
    from pymatgen.core import Structure, Lattice
    
    # Small lattice with many atoms = high coordination
    lattice = Lattice.cubic(3.0)
    species = ["Fe"] * 10
    coords = [
        [0, 0, 0],
        [0.3, 0, 0],
        [0, 0.3, 0],
        [0, 0, 0.3],
        [0.3, 0.3, 0],
        [0.3, 0, 0.3],
        [0, 0.3, 0.3],
        [0.3, 0.3, 0.3],
        [0.15, 0.15, 0.15],
        [0.45, 0.45, 0.45],
    ]
    return Structure(lattice, species, coords).as_dict()


# Materials Project API key fixtures
@pytest.fixture
def mp_api_key():
    """Materials Project API key from environment variable."""
    api_key = os.environ.get("MP_API_KEY")
    if not api_key:
        pytest.skip("MP_API_KEY environment variable not set")
    return api_key


@pytest.fixture
def mp_api_key_available():
    """Check if Materials Project API key is available."""
    return bool(os.environ.get("MP_API_KEY"))
