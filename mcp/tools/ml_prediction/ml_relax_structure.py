"""
Tool for relaxing crystal structures using machine learning potentials (MatGL).

Uses pre-trained TensorNet universal ML potentials to relax crystal structures
by minimizing energy through geometry optimization. Much faster than DFT while
maintaining reasonable accuracy for screening purposes.

Use this tool to:
- Relax candidate structures before expensive DFT calculations
- Optimize distorted or strained structures
- Find equilibrium geometries for structure prototypes
- Refine structures after manual modifications or substitutions
"""

from typing import Dict, Any, Optional, Union, Annotated, Literal
from pydantic import Field


def ml_relax_structure(
    input_structure: Annotated[
        Union[Dict[str, Any], str],
        Field(
            description=(
                "Structure to relax as a pymatgen Structure dict (from Structure.as_dict()), "
                "or a CIF/POSCAR string. Can be output from any pymatgen tool or Materials Project API."
            )
        )
    ],
    model: Annotated[
        Literal[
            "TensorNet-MatPES-PBE-v2025.1-PES",
            "TensorNet-MatPES-r2SCAN-v2025.1-PES"
        ],
        Field(
            default="TensorNet-MatPES-PBE-v2025.1-PES",
            description=(
                "ML potential model to use for relaxation. Options:\n"
                "- TensorNet-MatPES-PBE-v2025.1-PES (default, PBE functional, fast and accurate)\n"
                "- TensorNet-MatPES-r2SCAN-v2025.1-PES (r2SCAN functional, higher accuracy for complex systems)"
            )
        )
    ] = "TensorNet-MatPES-PBE-v2025.1-PES",
    relax_cell: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True (default), relaxes both atomic positions and lattice parameters (full relaxation). "
                "If False, only atomic positions are relaxed while cell is fixed (constant-volume relaxation)."
            )
        )
    ] = True,
    optimizer: Annotated[
        Literal["LBFGS", "BFGS", "FIRE"],
        Field(
            default="LBFGS",
            description=(
                "Optimization algorithm. Options:\n"
                "- LBFGS (default, most efficient for most cases)\n"
                "- BFGS (alternative quasi-Newton method)\n"
                "- FIRE (Fast Inertial Relaxation Engine, good for large distortions)"
            )
        )
    ] = "LBFGS",
    fmax: Annotated[
        float,
        Field(
            default=0.01,
            ge=0.001,
            le=0.5,
            description=(
                "Maximum force tolerance in eV/Å for convergence (0.001-0.5). "
                "Lower values = tighter convergence but more steps. "
                "Default: 0.01 eV/Å (good balance of accuracy and speed)."
            )
        )
    ] = 0.01,
    max_steps: Annotated[
        int,
        Field(
            default=500,
            ge=50,
            le=2000,
            description=(
                "Maximum optimization steps (50-2000). "
                "Relaxation stops if convergence is reached or max_steps is exceeded. "
                "Default: 500 (sufficient for most structures)."
            )
        )
    ] = 500,
    verbose: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, includes detailed trajectory information (energy, forces at each step). "
                "If False (default), only returns final structure and summary. "
                "Warning: Verbose output can be large for long relaxations."
            )
        )
    ] = False,
) -> Dict[str, Any]:
    """
    Relax a crystal structure using machine learning potentials.
    
    Performs geometry optimization to find the minimum energy configuration using
    universal ML potentials trained on large DFT databases. Returns the relaxed
    structure, final energy, and convergence information.
    
    Common Use Cases:
        1. Full relaxation (default): relax_cell=True
           - Optimizes both atomic positions and lattice parameters
           - Use for finding equilibrium structures
        
        2. Fixed-cell relaxation: relax_cell=False
           - Only relaxes atomic positions, cell is fixed
           - Use for structures constrained by substrate/experimental conditions
        
        3. Tight convergence: fmax=0.001
           - For structures needing high accuracy before DFT
        
        4. Quick pre-relaxation: fmax=0.05, max_steps=200
           - Fast screening of many candidates
    
    Model Selection Guide:
        - TensorNet-MatPES-PBE-v2025.1-PES: Best for general use, PBE functional (default)
        - TensorNet-MatPES-r2SCAN-v2025.1-PES: Higher accuracy with r2SCAN functional,
          better for complex bonding and strongly correlated materials
    
    Args:
        input_structure: Structure to relax (pymatgen dict, CIF, or POSCAR string)
        model: ML potential model name
        relax_cell: Whether to relax lattice parameters (True) or fix cell (False)
        optimizer: Optimization algorithm (LBFGS recommended)
        fmax: Force convergence criterion in eV/Å
        max_steps: Maximum optimization steps
        verbose: Include detailed trajectory information
    
    Returns:
        Dictionary containing:
            success             (bool)      Whether relaxation completed successfully
            converged           (bool)      Whether force convergence was achieved
            initial_structure   (dict)      Input structure (pymatgen dict)
            final_structure     (dict)      Relaxed structure (pymatgen dict)
            initial_energy      (float)     Initial energy (eV)
            final_energy        (float)     Final energy (eV)
            energy_change       (float)     Energy difference (eV)
            steps_taken         (int)       Number of optimization steps
            final_max_force     (float)     Maximum force in final structure (eV/Å)
            volume_change       (float)     % change in cell volume (if relax_cell=True)
            lattice_change      (dict)      % change in a, b, c, alpha, beta, gamma
            parameters          (dict)      All relaxation parameters used
            trajectory          (list)      Step-by-step energies/forces (if verbose=True)
            error               (str)       Error message if relaxation failed
    """
    try:
        from pymatgen.core import Structure
        from pymatgen.io.cif import CifParser
        from pymatgen.io.vasp import Poscar
        import matgl
        from matgl.ext.ase import Relaxer
        import numpy as np
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import required libraries: {e}. "
                    f"Install with: pip install matgl pymatgen ase"
        }
    
    # Check if PYG (PyTorch Geometric) is available (required for TensorNet models)
    try:
        import torch_geometric
    except Exception as e:
        return {
            "success": False,
            "error": f"PYG (PyTorch Geometric) backend not available: {e}. "
                    f"Structure relaxation with TensorNet models requires PYG. "
                    f"Install with: pip install torch-geometric"
        }
    
    try:
        # Parse input structure
        if isinstance(input_structure, dict):
            structure = Structure.from_dict(input_structure)
        elif isinstance(input_structure, str):
            if "data_" in input_structure or "_cell_" in input_structure:
                # CIF format - write to temporary file and parse
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(mode='w', suffix='.cif', delete=False) as f:
                    f.write(input_structure)
                    temp_path = f.name
                try:
                    parser = CifParser(temp_path)
                    structure = parser.get_structures()[0]
                finally:
                    os.unlink(temp_path)
            else:
                # Assume POSCAR format
                poscar = Poscar.from_string(input_structure)
                structure = poscar.structure
        else:
            return {
                "success": False,
                "error": f"Unsupported input_structure type: {type(input_structure)}. "
                        f"Expected dict, CIF string, or POSCAR string."
            }
        
        # Store initial structure info
        initial_structure_dict = structure.as_dict()
        initial_lattice = structure.lattice
        initial_volume = initial_lattice.volume
        
        # Set backend for MatGL (TensorNet models require PYG backend)
        matgl.set_backend('PYG')
        
        # Load ML potential model
        try:
            pot = matgl.load_model(model)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to load model '{model}': {e}. "
                        f"Check model name or network connection."
            }
        
        # Initialize relaxer
        try:
            relaxer = Relaxer(
                potential=pot,
                optimizer=optimizer,
                relax_cell=relax_cell
            )
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to initialize Relaxer: {e}"
            }
        
        # Perform relaxation
        try:
            struct_copy = structure.copy()
            results = relaxer.relax(struct_copy, fmax=fmax, steps=max_steps)
        except Exception as e:
            return {
                "success": False,
                "error": f"Relaxation failed: {e}. "
                        f"Structure may be unstable or contain unphysical geometries."
            }
        
        # Extract results
        final_structure = results["final_structure"]
        trajectory = results["trajectory"]
        
        # Calculate energies
        initial_energy = float(trajectory.energies[0])
        final_energy = float(trajectory.energies[-1])
        energy_change = final_energy - initial_energy
        
        # Calculate final forces
        final_forces = trajectory.forces[-1]
        final_max_force = float(np.max(np.abs(final_forces)))
        
        # Check convergence
        converged = final_max_force <= fmax
        steps_taken = len(trajectory.energies)
        
        # Calculate lattice changes
        final_lattice = final_structure.lattice
        final_volume = final_lattice.volume
        volume_change_percent = ((final_volume - initial_volume) / initial_volume) * 100
        
        lattice_change = {
            "a_percent": ((final_lattice.a - initial_lattice.a) / initial_lattice.a) * 100,
            "b_percent": ((final_lattice.b - initial_lattice.b) / initial_lattice.b) * 100,
            "c_percent": ((final_lattice.c - initial_lattice.c) / initial_lattice.c) * 100,
            "alpha_change": final_lattice.alpha - initial_lattice.alpha,
            "beta_change": final_lattice.beta - initial_lattice.beta,
            "gamma_change": final_lattice.gamma - initial_lattice.gamma,
        }
        
        # Build response
        response = {
            "success": True,
            "converged": converged,
            "initial_structure": initial_structure_dict,
            "final_structure": final_structure.as_dict(),
            "initial_energy_eV": round(initial_energy, 6),
            "final_energy_eV": round(final_energy, 6),
            "energy_change_eV": round(energy_change, 6),
            "steps_taken": steps_taken,
            "max_steps": max_steps,
            "final_max_force_eV_per_A": round(final_max_force, 6),
            "force_tolerance_eV_per_A": fmax,
            "volume_change_percent": round(volume_change_percent, 3),
            "lattice_change": {k: round(v, 3) for k, v in lattice_change.items()},
            "parameters": {
                "model": model,
                "relax_cell": relax_cell,
                "optimizer": optimizer,
                "fmax": fmax,
                "max_steps": max_steps,
            },
        }
        
        # Add warnings if not converged
        if not converged:
            response["warning"] = (
                f"Relaxation did not converge within {max_steps} steps. "
                f"Final max force ({final_max_force:.4f} eV/Å) > tolerance ({fmax} eV/Å). "
                f"Consider increasing max_steps or relaxing fmax."
            )
        
        # Add trajectory info if verbose
        if verbose:
            trajectory_data = []
            for i, (energy, forces) in enumerate(zip(trajectory.energies, trajectory.forces)):
                max_force = float(np.max(np.abs(forces)))
                trajectory_data.append({
                    "step": i,
                    "energy_eV": round(float(energy), 6),
                    "max_force_eV_per_A": round(max_force, 6),
                })
            response["trajectory"] = trajectory_data
        
        # Add convergence message
        if converged:
            response["message"] = (
                f"Structure successfully relaxed in {steps_taken} steps. "
                f"Final energy: {final_energy:.4f} eV. "
                f"Energy change: {energy_change:.4f} eV. "
                f"Volume change: {volume_change_percent:+.2f}%."
            )
        else:
            response["message"] = (
                f"Relaxation incomplete after {steps_taken} steps (not converged). "
                f"Final energy: {final_energy:.4f} eV. "
                f"Consider re-running with increased max_steps."
            )
        
        return response
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error during relaxation: {str(e)}"
        }
