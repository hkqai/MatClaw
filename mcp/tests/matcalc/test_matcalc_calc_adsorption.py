"""
Tests for matcalc adsorption energy calculation tool.
"""

import pytest
from pymatgen.core import Structure, Lattice, Molecule
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer


def test_adsorption_basic_ontop():
    """Test basic adsorption calculation with ontop site."""
    from tools.matcalc.matcalc_calc_adsorption import matcalc_calc_adsorption
    
    # Create a simple Pt(111) slab
    lattice = Lattice.hexagonal(2.77, 20.0)  # Pt lattice with vacuum
    pt_slab = Structure(
        lattice,
        ["Pt", "Pt", "Pt", "Pt"],
        [[0, 0, 0.4], [0.333, 0.667, 0.45], [0.667, 0.333, 0.5], [0, 0, 0.55]]
    )
    
    result = matcalc_calc_adsorption(
        slab_structure=pt_slab.as_dict(),
        adsorbate="CO",
        adsorption_site="ontop",
        distance=2.0,
        calculator="CHGNet",
        relax_adsorbate=False,  # Faster
        relax_slab=False,
        max_steps=10
    )
    
    assert "error" not in result
    assert "adsorption_energy" in result
    assert isinstance(result["adsorption_energy"], float)
    assert "adslab_structure" in result
    assert "slab_structure" in result
    assert "adsorbate_structure" in result
    assert result["adsorption_site"] == "ontop"
    assert result["num_slab_atoms"] == 4
    assert result["num_adsorbate_atoms"] == 2


def test_adsorption_with_relaxation():
    """Test adsorption with structure relaxation enabled."""
    from tools.matcalc.matcalc_calc_adsorption import matcalc_calc_adsorption
    
    # Create Pt(111) slab
    lattice = Lattice.hexagonal(2.77, 20.0)
    pt_slab = Structure(
        lattice,
        ["Pt", "Pt", "Pt", "Pt"],
        [[0, 0, 0.4], [0.333, 0.667, 0.45], [0.667, 0.333, 0.5], [0, 0, 0.55]]
    )
    
    result = matcalc_calc_adsorption(
        slab_structure=pt_slab.as_dict(),
        adsorbate="O",
        adsorption_site="ontop",
        distance=2.0,
        calculator="CHGNet",
        relax_adsorbate=True,
        relax_slab=True,
        fmax=0.1,
        max_steps=100
    )
    
    assert "error" not in result
    assert "adsorption_energy" in result
    assert isinstance(result["adsorption_energy"], float)
    # Check that energies are present
    assert "adslab_energy" in result
    assert "slab_energy" in result
    assert "adsorbate_energy" in result
    assert result["num_adsorbate_atoms"] == 1


def test_adsorption_different_adsorbates():
    """Test with different adsorbate molecules."""
    from tools.matcalc.matcalc_calc_adsorption import matcalc_calc_adsorption
    
    # Create Pt(111) slab
    lattice = Lattice.hexagonal(2.77, 20.0)
    pt_slab = Structure(
        lattice,
        ["Pt", "Pt", "Pt", "Pt"],
        [[0, 0, 0.4], [0.333, 0.667, 0.45], [0.667, 0.333, 0.5], [0, 0, 0.55]]
    )
    
    adsorbates = ["CO", "O", "H", "OH", "H2O", "N2", "NO"]
    
    for ads in adsorbates:
        result = matcalc_calc_adsorption(
            slab_structure=pt_slab.as_dict(),
            adsorbate=ads,
            adsorption_site="ontop",
            distance=2.0,
            calculator="CHGNet",
            relax_adsorbate=False,
            relax_slab=False,
            max_steps=10
        )
        
        assert "error" not in result, f"Failed for adsorbate {ads}: {result.get('error')}"
        assert "adsorption_energy" in result
        assert isinstance(result["adsorption_energy"], float)


def test_adsorption_hollow_site():
    """Test adsorption at hollow site."""
    from tools.matcalc.matcalc_calc_adsorption import matcalc_calc_adsorption
    
    # Create larger Pt(111) slab to have hollow sites
    lattice = Lattice.hexagonal(2.77, 20.0)
    pt_slab = Structure(
        lattice,
        ["Pt", "Pt", "Pt", "Pt"],
        [[0, 0, 0.4], [0.333, 0.667, 0.45], [0.667, 0.333, 0.5], [0, 0, 0.55]]
    )
    pt_slab.make_supercell([2, 2, 1])
    
    result = matcalc_calc_adsorption(
        slab_structure=pt_slab.as_dict(),
        adsorbate="O",
        adsorption_site="hollow",
        distance=2.0,
        calculator="CHGNet",
        relax_adsorbate=False,
        relax_slab=False,
        max_steps=10
    )
    
    assert "error" not in result
    assert "adsorption_energy" in result
    assert result["adsorption_site"] == "hollow"


def test_adsorption_bridge_site():
    """Test adsorption at bridge site."""
    from tools.matcalc.matcalc_calc_adsorption import matcalc_calc_adsorption
    
    # Create Pt(111) slab
    lattice = Lattice.hexagonal(2.77, 20.0)
    pt_slab = Structure(
        lattice,
        ["Pt", "Pt", "Pt", "Pt"],
        [[0, 0, 0.4], [0.333, 0.667, 0.45], [0.667, 0.333, 0.5], [0, 0, 0.55]]
    )
    pt_slab.make_supercell([2, 2, 1])
    
    result = matcalc_calc_adsorption(
        slab_structure=pt_slab.as_dict(),
        adsorbate="CO",
        adsorption_site="bridge",
        distance=2.0,
        calculator="CHGNet",
        relax_adsorbate=False,
        relax_slab=False,
        max_steps=10
    )
    
    assert "error" not in result
    assert "adsorption_energy" in result
    assert result["adsorption_site"] == "bridge"


def test_adsorption_different_distances():
    """Test with different adsorbate-surface distances."""
    from tools.matcalc.matcalc_calc_adsorption import matcalc_calc_adsorption
    
    # Create Pt(111) slab
    lattice = Lattice.hexagonal(2.77, 20.0)
    pt_slab = Structure(
        lattice,
        ["Pt", "Pt", "Pt", "Pt"],
        [[0, 0, 0.4], [0.333, 0.667, 0.45], [0.667, 0.333, 0.5], [0, 0, 0.55]]
    )
    
    distances = [1.5, 2.0, 2.5, 3.0]
    energies = []
    
    for dist in distances:
        result = matcalc_calc_adsorption(
            slab_structure=pt_slab.as_dict(),
            adsorbate="O",
            adsorption_site="ontop",
            distance=dist,
            calculator="CHGNet",
            relax_adsorbate=False,
            relax_slab=False,
            max_steps=10
        )
        
        assert "error" not in result
        assert "adsorption_energy" in result
        energies.append(result["adsorption_energy"])
    
    # Energies should vary with distance
    assert len(set(energies)) > 1, "Energies should differ with distance"


def test_adsorption_string_input():
    """Test with structure as CIF string input."""
    from tools.matcalc.matcalc_calc_adsorption import matcalc_calc_adsorption
    
    # Create Pt(111) slab and convert to CIF
    lattice = Lattice.hexagonal(2.77, 20.0)
    pt_slab = Structure(
        lattice,
        ["Pt", "Pt", "Pt", "Pt"],
        [[0, 0, 0.4], [0.333, 0.667, 0.45], [0.667, 0.333, 0.5], [0, 0, 0.55]]
    )
    cif_string = pt_slab.to(fmt='cif')
    
    result = matcalc_calc_adsorption(
        slab_structure=cif_string,
        adsorbate="CO",
        adsorption_site="ontop",
        distance=2.0,
        calculator="CHGNet",
        relax_adsorbate=False,
        relax_slab=False,
        max_steps=10
    )
    
    assert "error" not in result
    assert "adsorption_energy" in result


def test_adsorption_molecule_dict():
    """Test with adsorbate as Molecule dict."""
    from tools.matcalc.matcalc_calc_adsorption import matcalc_calc_adsorption
    
    # Create Pt(111) slab
    lattice = Lattice.hexagonal(2.77, 20.0)
    pt_slab = Structure(
        lattice,
        ["Pt", "Pt", "Pt", "Pt"],
        [[0, 0, 0.4], [0.333, 0.667, 0.45], [0.667, 0.333, 0.5], [0, 0, 0.55]]
    )
    
    # Create custom CO molecule
    co_molecule = Molecule(["C", "O"], [[0, 0, 0], [0, 0, 1.128]])
    
    result = matcalc_calc_adsorption(
        slab_structure=pt_slab.as_dict(),
        adsorbate=co_molecule.as_dict(),
        adsorption_site="ontop",
        distance=2.0,
        calculator="CHGNet",
        relax_adsorbate=False,
        relax_slab=False,
        max_steps=10
    )
    
    assert "error" not in result
    assert "adsorption_energy" in result


def test_adsorption_different_optimizers():
    """Test with different optimizers."""
    from tools.matcalc.matcalc_calc_adsorption import matcalc_calc_adsorption
    
    # Create Pt(111) slab
    lattice = Lattice.hexagonal(2.77, 20.0)
    pt_slab = Structure(
        lattice,
        ["Pt", "Pt", "Pt", "Pt"],
        [[0, 0, 0.4], [0.333, 0.667, 0.45], [0.667, 0.333, 0.5], [0, 0, 0.55]]
    )
    
    optimizers = ["BFGS", "FIRE", "LBFGS"]
    
    for opt in optimizers:
        result = matcalc_calc_adsorption(
            slab_structure=pt_slab.as_dict(),
            adsorbate="O",
            adsorption_site="ontop",
            distance=2.0,
            calculator="CHGNet",
            relax_adsorbate=True,
            relax_slab=False,
            optimizer=opt,
            max_steps=50
        )
        
        assert "error" not in result, f"Failed with optimizer {opt}"
        assert "adsorption_energy" in result


def test_adsorption_different_fmax():
    """Test with different force convergence tolerances."""
    from tools.matcalc.matcalc_calc_adsorption import matcalc_calc_adsorption
    
    # Create Pt(111) slab
    lattice = Lattice.hexagonal(2.77, 20.0)
    pt_slab = Structure(
        lattice,
        ["Pt", "Pt", "Pt", "Pt"],
        [[0, 0, 0.4], [0.333, 0.667, 0.45], [0.667, 0.333, 0.5], [0, 0, 0.55]]
    )
    
    fmax_values = [0.5, 0.1, 0.05]
    
    for fmax in fmax_values:
        result = matcalc_calc_adsorption(
            slab_structure=pt_slab.as_dict(),
            adsorbate="O",
            adsorption_site="ontop",
            distance=2.0,
            calculator="CHGNet",
            relax_adsorbate=True,
            relax_slab=False,
            fmax=fmax,
            max_steps=100
        )
        
        assert "error" not in result
        assert "adsorption_energy" in result


def test_adsorption_energy_sign():
    """Test that adsorption energy has correct interpretation."""
    from tools.matcalc.matcalc_calc_adsorption import matcalc_calc_adsorption
    
    # Create Pt(111) slab
    lattice = Lattice.hexagonal(2.77, 20.0)
    pt_slab = Structure(
        lattice,
        ["Pt", "Pt", "Pt", "Pt"],
        [[0, 0, 0.4], [0.333, 0.667, 0.45], [0.667, 0.333, 0.5], [0, 0, 0.55]]
    )
    
    result = matcalc_calc_adsorption(
        slab_structure=pt_slab.as_dict(),
        adsorbate="O",
        adsorption_site="ontop",
        distance=2.0,
        calculator="CHGNet",
        relax_adsorbate=False,
        relax_slab=False,
        max_steps=10
    )
    
    assert "error" not in result
    assert "adsorption_energy" in result
    assert "adsorption_favorable" in result
    assert "interpretation" in result
    
    # Check interpretation logic
    if result["adsorption_energy"] < 0:
        assert result["adsorption_favorable"] is True
        assert "favorable" in result["interpretation"]
    else:
        assert result["adsorption_favorable"] is False
        assert "unfavorable" in result["interpretation"]


def test_adsorption_invalid_structure():
    """Test error handling for invalid slab structure."""
    from tools.matcalc.matcalc_calc_adsorption import matcalc_calc_adsorption
    
    result = matcalc_calc_adsorption(
        slab_structure={"invalid": "structure"},
        adsorbate="CO",
        adsorption_site="ontop",
        distance=2.0,
        calculator="CHGNet"
    )
    
    assert "error" in result


def test_adsorption_invalid_adsorbate():
    """Test error handling for invalid adsorbate."""
    from tools.matcalc.matcalc_calc_adsorption import matcalc_calc_adsorption
    
    # Create Pt(111) slab
    lattice = Lattice.hexagonal(2.77, 20.0)
    pt_slab = Structure(
        lattice,
        ["Pt", "Pt", "Pt", "Pt"],
        [[0, 0, 0.4], [0.333, 0.667, 0.45], [0.667, 0.333, 0.5], [0, 0, 0.55]]
    )
    
    result = matcalc_calc_adsorption(
        slab_structure=pt_slab.as_dict(),
        adsorbate={"invalid": "molecule"},
        adsorption_site="ontop",
        distance=2.0,
        calculator="CHGNet"
    )
    
    assert "error" in result


def test_adsorption_output_structure():
    """Test that output structures are valid."""
    from tools.matcalc.matcalc_calc_adsorption import matcalc_calc_adsorption
    
    # Create Pt(111) slab
    lattice = Lattice.hexagonal(2.77, 20.0)
    pt_slab = Structure(
        lattice,
        ["Pt", "Pt", "Pt", "Pt"],
        [[0, 0, 0.4], [0.333, 0.667, 0.45], [0.667, 0.333, 0.5], [0, 0, 0.55]]
    )
    
    result = matcalc_calc_adsorption(
        slab_structure=pt_slab.as_dict(),
        adsorbate="CO",
        adsorption_site="ontop",
        distance=2.0,
        calculator="CHGNet",
        relax_adsorbate=False,
        relax_slab=False,
        max_steps=10
    )
    
    assert "error" not in result
    assert "adslab_structure" in result
    assert "slab_structure" in result
    assert "adsorbate_structure" in result
    
    # Verify structures can be parsed
    adslab_struct = Structure.from_dict(result["adslab_structure"])
    slab_struct = Structure.from_dict(result["slab_structure"])
    ads_struct = Molecule.from_dict(result["adsorbate_structure"])
    
    # Check atom counts
    assert len(adslab_struct) == result["num_adslab_atoms"]
    assert len(slab_struct) == result["num_slab_atoms"]
    assert len(ads_struct) == result["num_adsorbate_atoms"]
    
    # Adslab should have more atoms than slab alone
    assert len(adslab_struct) == len(slab_struct) + len(ads_struct)
