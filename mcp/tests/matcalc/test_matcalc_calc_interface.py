"""
Tests for matcalc interface energy calculation tool.
"""

import pytest
from pymatgen.core import Structure, Lattice
from pymatgen.analysis.interfaces.coherent_interfaces import CoherentInterfaceBuilder


def test_interface_basic():
    """Test basic interface energy calculation with simple structure."""
    from tools.matcalc.matcalc_calc_interface import matcalc_calc_interface
    
    # Create interface structure (Al on top of Cu)
    lattice = Lattice.cubic(4.0)
    interface = Structure(
        lattice,
        ["Al", "Al", "Al", "Al", "Cu", "Cu", "Cu", "Cu"],
        [
            [0, 0, 0.1], [0.5, 0.5, 0.1], [0, 0.5, 0.15], [0.5, 0, 0.15],
            [0, 0, 0.85], [0.5, 0.5, 0.85], [0, 0.5, 0.9], [0.5, 0, 0.9]
        ]
    )
    
    # Create film bulk (Al)
    film = Structure.from_spacegroup("Fm-3m", Lattice.cubic(4.05), ["Al"], [[0, 0, 0]])
    
    # Create substrate bulk (Cu)
    substrate = Structure.from_spacegroup("Fm-3m", Lattice.cubic(3.61), ["Cu"], [[0, 0, 0]])
    
    result = matcalc_calc_interface(
        interface_structure=interface.as_dict(),
        film_bulk=film.as_dict(),
        substrate_bulk=substrate.as_dict(),
        calculator="CHGNet",
        relax_bulk=False,  # Faster for testing
        relax_interface=False,
        max_steps=10
    )
    
    assert "error" not in result
    assert "interface_energy" in result
    assert isinstance(result["interface_energy"], float)
    assert "interface_structure" in result
    assert result["num_atoms"] == 8


def test_interface_with_relaxation():
    """Test interface calculation with structure relaxation."""
    from tools.matcalc.matcalc_calc_interface import matcalc_calc_interface
    
    # Simple test structure
    lattice = Lattice.cubic(4.0)
    interface = Structure(
        lattice,
        ["Fe", "Fe", "Fe", "Fe", "Ni", "Ni", "Ni", "Ni"],
        [
            [0, 0, 0.1], [0.5, 0.5, 0.1], [0, 0.5, 0.15], [0.5, 0, 0.15],
            [0, 0, 0.85], [0.5, 0.5, 0.85], [0, 0.5, 0.9], [0.5, 0, 0.9]
        ]
    )
    
    film = Structure.from_spacegroup("Im-3m", Lattice.cubic(2.87), ["Fe"], [[0, 0, 0]])
    substrate = Structure.from_spacegroup("Fm-3m", Lattice.cubic(3.52), ["Ni"], [[0, 0, 0]])
    
    result = matcalc_calc_interface(
        interface_structure=interface.as_dict(),
        film_bulk=film.as_dict(),
        substrate_bulk=substrate.as_dict(),
        calculator="CHGNet",
        relax_bulk=True,
        relax_interface=True,
        fmax=0.1,
        max_steps=100
    )
    
    assert "error" not in result
    assert "interface_energy" in result
    assert isinstance(result["interface_energy"], float)
    assert "interface_structure" in result


def test_interface_string_input():
    """Test with structure as CIF string input."""
    from tools.matcalc.matcalc_calc_interface import matcalc_calc_interface
    
    # Create structure and convert to CIF
    lattice = Lattice.cubic(4.0)
    interface = Structure(
        lattice,
        ["Al", "Al", "Cu", "Cu"],
        [[0, 0, 0.2], [0.5, 0.5, 0.2], [0, 0, 0.8], [0.5, 0.5, 0.8]]
    )
    cif_string = interface.to(fmt='cif')
    
    film = Structure.from_spacegroup("Fm-3m", Lattice.cubic(4.05), ["Al"], [[0, 0, 0]])
    substrate = Structure.from_spacegroup("Fm-3m", Lattice.cubic(3.61), ["Cu"], [[0, 0, 0]])
    
    result = matcalc_calc_interface(
        interface_structure=cif_string,
        film_bulk=film.to(fmt='cif'),
        substrate_bulk=substrate.to(fmt='cif'),
        calculator="CHGNet",
        relax_bulk=False,
        relax_interface=False,
        max_steps=10
    )
    
    assert "error" not in result
    assert "interface_energy" in result


def test_interface_different_optimizers():
    """Test with different optimizers."""
    from tools.matcalc.matcalc_calc_interface import matcalc_calc_interface
    
    lattice = Lattice.cubic(4.0)
    interface = Structure(
        lattice,
        ["Al", "Al", "Cu", "Cu"],
        [[0, 0, 0.2], [0.5, 0.5, 0.2], [0, 0, 0.8], [0.5, 0.5, 0.8]]
    )
    
    film = Structure.from_spacegroup("Fm-3m", Lattice.cubic(4.05), ["Al"], [[0, 0, 0]])
    substrate = Structure.from_spacegroup("Fm-3m", Lattice.cubic(3.61), ["Cu"], [[0, 0, 0]])
    
    optimizers = ["BFGS", "FIRE", "LBFGS"]
    
    for opt in optimizers:
        result = matcalc_calc_interface(
            interface_structure=interface.as_dict(),
            film_bulk=film.as_dict(),
            substrate_bulk=substrate.as_dict(),
            calculator="CHGNet",
            relax_bulk=False,
            relax_interface=True,
            optimizer=opt,
            max_steps=50
        )
        
        assert "error" not in result, f"Failed with optimizer {opt}"
        assert "interface_energy" in result


def test_interface_different_fmax():
    """Test with different force convergence tolerances."""
    from tools.matcalc.matcalc_calc_interface import matcalc_calc_interface
    
    lattice = Lattice.cubic(4.0)
    interface = Structure(
        lattice,
        ["Al", "Al", "Cu", "Cu"],
        [[0, 0, 0.2], [0.5, 0.5, 0.2], [0, 0, 0.8], [0.5, 0.5, 0.8]]
    )
    
    film = Structure.from_spacegroup("Fm-3m", Lattice.cubic(4.05), ["Al"], [[0, 0, 0]])
    substrate = Structure.from_spacegroup("Fm-3m", Lattice.cubic(3.61), ["Cu"], [[0, 0, 0]])
    
    fmax_values = [0.5, 0.1, 0.05]
    
    for fmax in fmax_values:
        result = matcalc_calc_interface(
            interface_structure=interface.as_dict(),
            film_bulk=film.as_dict(),
            substrate_bulk=substrate.as_dict(),
            calculator="CHGNet",
            relax_bulk=False,
            relax_interface=True,
            fmax=fmax,
            max_steps=100
        )
        
        assert "error" not in result
        assert "interface_energy" in result


def test_interface_stability_interpretation():
    """Test that stability interpretation is included."""
    from tools.matcalc.matcalc_calc_interface import matcalc_calc_interface
    
    lattice = Lattice.cubic(4.0)
    interface = Structure(
        lattice,
        ["Al", "Al", "Cu", "Cu"],
        [[0, 0, 0.2], [0.5, 0.5, 0.2], [0, 0, 0.8], [0.5, 0.5, 0.8]]
    )
    
    film = Structure.from_spacegroup("Fm-3m", Lattice.cubic(4.05), ["Al"], [[0, 0, 0]])
    substrate = Structure.from_spacegroup("Fm-3m", Lattice.cubic(3.61), ["Cu"], [[0, 0, 0]])
    
    result = matcalc_calc_interface(
        interface_structure=interface.as_dict(),
        film_bulk=film.as_dict(),
        substrate_bulk=substrate.as_dict(),
        calculator="CHGNet",
        relax_bulk=False,
        relax_interface=False,
        max_steps=10
    )
    
    assert "error" not in result
    assert "interface_energy" in result
    assert "stability" in result
    assert isinstance(result["stability"], str)


def test_interface_output_structure():
    """Test that output structure is valid."""
    from tools.matcalc.matcalc_calc_interface import matcalc_calc_interface
    
    lattice = Lattice.cubic(4.0)
    interface = Structure(
        lattice,
        ["Al", "Al", "Cu", "Cu"],
        [[0, 0, 0.2], [0.5, 0.5, 0.2], [0, 0, 0.8], [0.5, 0.5, 0.8]]
    )
    
    film = Structure.from_spacegroup("Fm-3m", Lattice.cubic(4.05), ["Al"], [[0, 0, 0]])
    substrate = Structure.from_spacegroup("Fm-3m", Lattice.cubic(3.61), ["Cu"], [[0, 0, 0]])
    
    result = matcalc_calc_interface(
        interface_structure=interface.as_dict(),
        film_bulk=film.as_dict(),
        substrate_bulk=substrate.as_dict(),
        calculator="CHGNet",
        relax_bulk=False,
        relax_interface=False,
        max_steps=10
    )
    
    assert "error" not in result
    assert "interface_structure" in result
    assert "num_atoms" in result
    assert "formula" in result
    
    # Verify structure can be parsed
    final_struct = Structure.from_dict(result["interface_structure"])
    assert len(final_struct) == result["num_atoms"]


def test_interface_invalid_structure():
    """Test error handling for invalid interface structure."""
    from tools.matcalc.matcalc_calc_interface import matcalc_calc_interface
    
    film = Structure.from_spacegroup("Fm-3m", Lattice.cubic(4.05), ["Al"], [[0, 0, 0]])
    substrate = Structure.from_spacegroup("Fm-3m", Lattice.cubic(3.61), ["Cu"], [[0, 0, 0]])
    
    result = matcalc_calc_interface(
        interface_structure={"invalid": "structure"},
        film_bulk=film.as_dict(),
        substrate_bulk=substrate.as_dict(),
        calculator="CHGNet"
    )
    
    assert "error" in result


def test_interface_poscar_input():
    """Test with POSCAR format input."""
    from tools.matcalc.matcalc_calc_interface import matcalc_calc_interface
    
    poscar_string = """Al2Cu2
1.0
4.0 0.0 0.0
0.0 4.0 0.0
0.0 0.0 4.0
Al Cu
2 2
direct
0.0 0.0 0.2
0.5 0.5 0.2
0.0 0.0 0.8
0.5 0.5 0.8"""
    
    film = Structure.from_spacegroup("Fm-3m", Lattice.cubic(4.05), ["Al"], [[0, 0, 0]])
    substrate = Structure.from_spacegroup("Fm-3m", Lattice.cubic(3.61), ["Cu"], [[0, 0, 0]])
    
    result = matcalc_calc_interface(
        interface_structure=poscar_string,
        film_bulk=film.as_dict(),
        substrate_bulk=substrate.as_dict(),
        calculator="CHGNet",
        relax_bulk=False,
        relax_interface=False,
        max_steps=10
    )
    
    assert "error" not in result
    assert "interface_energy" in result


def test_interface_larger_system():
    """Test with a larger interface system."""
    from tools.matcalc.matcalc_calc_interface import matcalc_calc_interface
    
    # Create larger system
    lattice = Lattice.cubic(4.0)
    interface = Structure(
        lattice,
        ["Al"] * 8 + ["Cu"] * 8,
        [
            # Al layer
            [0, 0, 0.1], [0.5, 0, 0.1], [0, 0.5, 0.1], [0.5, 0.5, 0.1],
            [0, 0, 0.2], [0.5, 0, 0.2], [0, 0.5, 0.2], [0.5, 0.5, 0.2],
            # Cu layer
            [0, 0, 0.8], [0.5, 0, 0.8], [0, 0.5, 0.8], [0.5, 0.5, 0.8],
            [0, 0, 0.9], [0.5, 0, 0.9], [0, 0.5, 0.9], [0.5, 0.5, 0.9],
        ]
    )
    
    film = Structure.from_spacegroup("Fm-3m", Lattice.cubic(4.05), ["Al"], [[0, 0, 0]])
    substrate = Structure.from_spacegroup("Fm-3m", Lattice.cubic(3.61), ["Cu"], [[0, 0, 0]])
    
    result = matcalc_calc_interface(
        interface_structure=interface.as_dict(),
        film_bulk=film.as_dict(),
        substrate_bulk=substrate.as_dict(),
        calculator="CHGNet",
        relax_bulk=False,
        relax_interface=False,
        max_steps=10
    )
    
    assert "error" not in result
    assert "interface_energy" in result
    assert result["num_atoms"] == 16


def test_interface_with_both_relaxations():
    """Test with both bulk and interface relaxation enabled."""
    from tools.matcalc.matcalc_calc_interface import matcalc_calc_interface
    
    lattice = Lattice.cubic(4.0)
    interface = Structure(
        lattice,
        ["Al", "Al", "Cu", "Cu"],
        [[0, 0, 0.2], [0.5, 0.5, 0.2], [0, 0, 0.8], [0.5, 0.5, 0.8]]
    )
    
    film = Structure.from_spacegroup("Fm-3m", Lattice.cubic(4.05), ["Al"], [[0, 0, 0]])
    substrate = Structure.from_spacegroup("Fm-3m", Lattice.cubic(3.61), ["Cu"], [[0, 0, 0]])
    
    result = matcalc_calc_interface(
        interface_structure=interface.as_dict(),
        film_bulk=film.as_dict(),
        substrate_bulk=substrate.as_dict(),
        calculator="CHGNet",
        relax_bulk=True,
        relax_interface=True,
        max_steps=100
    )
    
    assert "error" not in result
    assert "interface_energy" in result
    assert result["relax_bulk"] is True
    assert result["relax_interface"] is True


def test_interface_metadata():
    """Test that all expected metadata is included."""
    from tools.matcalc.matcalc_calc_interface import matcalc_calc_interface
    
    lattice = Lattice.cubic(4.0)
    interface = Structure(
        lattice,
        ["Al", "Al", "Cu", "Cu"],
        [[0, 0, 0.2], [0.5, 0.5, 0.2], [0, 0, 0.8], [0.5, 0.5, 0.8]]
    )
    
    film = Structure.from_spacegroup("Fm-3m", Lattice.cubic(4.05), ["Al"], [[0, 0, 0]])
    substrate = Structure.from_spacegroup("Fm-3m", Lattice.cubic(3.61), ["Cu"], [[0, 0, 0]])
    
    result = matcalc_calc_interface(
        interface_structure=interface.as_dict(),
        film_bulk=film.as_dict(),
        substrate_bulk=substrate.as_dict(),
        calculator="CHGNet",
        relax_bulk=False,
        relax_interface=False,
        max_steps=10
    )
    
    assert "error" not in result
    assert "calculator" in result
    assert result["calculator"] == "CHGNet"
    assert "relax_bulk" in result
    assert "relax_interface" in result
    assert "num_atoms" in result
    assert "formula" in result
