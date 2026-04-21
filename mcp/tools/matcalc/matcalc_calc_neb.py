"""
Tool for calculating energy barriers using Nudged Elastic Band (NEB) method with matcalc.

Computes minimum energy paths (MEP) and activation barriers between initial and 
final structures, useful for understanding reaction mechanisms and diffusion pathways.

Use this tool to:
- Calculate energy barriers for chemical reactions
- Find transition states between crystal structures
- Study diffusion pathways in materials
- Analyze phase transformation mechanisms
"""

from typing import Dict, Any, Optional, Union, Annotated, List
from pydantic import Field


def matcalc_calc_neb(
    images: Annotated[
        Union[Dict[str, Any], List[Union[Dict[str, Any], str]]],
        Field(
            description=(
                "NEB images as either:\n"
                "1. Dict with keys 'image0', 'image1', etc. containing structure dicts/strings\n"
                "2. List of structures (dicts, CIF strings, or POSCAR strings)\n"
                "Must have at least 2 images (initial and final). Intermediate images\n"
                "can be provided or will be interpolated automatically."
            )
        )
    ],
    calculator: Annotated[
        str,
        Field(
            default="M3GNet",
            description=(
                "Calculator/potential to use. Options:\n"
                "- 'M3GNet' or 'M3GNet-MatPES-PBE-v2025.1-PES' (default, good for NEB)\n"
                "- 'CHGNet' or 'CHGNet-MatPES-PBE-2025.2.10-2.7M-PES'\n"
                "- 'TensorNet-MatPES-PBE-v2025.1-PES' or 'pbe'\n"
                "- 'TensorNet-MatPES-r2SCAN-v2025.1-PES' or 'r2scan'\n"
                "Or any other matcalc-supported universal calculator."
            )
        )
    ] = "M3GNet",
    n_images: Annotated[
        Optional[int],
        Field(
            default=5,
            ge=2,
            le=20,
            description=(
                "Number of images for NEB calculation (2-20). If input has fewer images,\n"
                "intermediate structures will be interpolated. More images = better MEP\n"
                "resolution but more computation. Default: 5 images."
            )
        )
    ] = 5,
    climb: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "Use climbing image NEB (CI-NEB). When True, the highest energy image\n"
                "climbs to the saddle point for accurate barrier calculation. Recommended\n"
                "for most applications. Default: True."
            )
        )
    ] = True,
    fmax: Annotated[
        float,
        Field(
            default=0.1,
            ge=0.01,
            le=1.0,
            description=(
                "Force convergence tolerance in eV/Å (0.01-1.0). Optimization stops when\n"
                "maximum force on any atom falls below this value. Lower = more accurate\n"
                "but slower. Default: 0.1 eV/Å."
            )
        )
    ] = 0.1,
    max_steps: Annotated[
        int,
        Field(
            default=1000,
            ge=100,
            le=10000,
            description=(
                "Maximum optimization steps (100-10000). NEB can require many iterations.\n"
                "Default: 1000 steps. Increase for difficult pathways."
            )
        )
    ] = 1000,
    optimizer: Annotated[
        str,
        Field(
            default="BFGS",
            description=(
                "Optimization algorithm. Options:\n"
                "- 'BFGS' (default, quasi-Newton method, generally fastest)\n"
                "- 'FIRE' (Fast Inertial Relaxation Engine, robust)\n"
                "- 'LBFGS' (Limited-memory BFGS, good for large systems)\n"
                "- 'MDMin' (Molecular dynamics based minimizer)"
            )
        )
    ] = "BFGS",
    interval: Annotated[
        int,
        Field(
            default=1,
            ge=1,
            le=100,
            description=(
                "Trajectory save interval. Save structure every N steps. Default: 1\n"
                "(save every step). Increase to reduce file size for long calculations."
            )
        )
    ] = 1,
    traj_folder: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "Folder path to save trajectory files. If None, trajectories not saved.\n"
                "Useful for visualization and analysis of NEB pathway evolution."
            )
        )
    ] = None,
) -> Dict[str, Any]:
    """
    Calculate energy barrier using Nudged Elastic Band (NEB) method.
    
    NEB finds the minimum energy path (MEP) between initial and final structures
    by optimizing a chain of images connected by spring forces. The climbing image
    variant (CI-NEB) allows accurate determination of transition state geometries.
    
    Typical Use Cases:
        **Simple barrier calculation (2 endpoints):**
        matcalc_calc_neb([initial_structure, final_structure])
        
        **With provided intermediate images:**
        matcalc_calc_neb([image0, image1, image2, image3, image4])
        
        **Dict input format:**
        matcalc_calc_neb({'image0': initial, 'image1': final})
        
        **High accuracy NEB:**
        matcalc_calc_neb(images, n_images=11, fmax=0.05, max_steps=2000)
        
        **Fast screening:**
        matcalc_calc_neb(images, n_images=3, fmax=0.3, max_steps=500)
    
    NEB Method Notes:
        - Requires at least 2 structures (initial and final states)
        - More images = better MEP resolution but higher cost
        - CI-NEB (climb=True) recommended for accurate barriers
        - Convergence can be slow for complex pathways
        - BFGS optimizer generally fastest for NEB
        
    Args:
        images: Initial/final structures (and optionally intermediates) as dict or list
        calculator: ML potential or calculator name
        n_images: Total number of images for NEB chain
        climb: Use climbing image NEB for accurate transition states
        fmax: Force convergence tolerance (eV/Å)
        max_steps: Maximum optimization steps
        optimizer: Optimization algorithm (BFGS, FIRE, LBFGS, MDMin)
        interval: Trajectory save interval (steps)
        traj_folder: Folder to save trajectory files (optional)
    
    Returns:
        Dictionary containing:
            success                         (bool)      Whether calculation completed successfully
            barrier_eV                      (float)     Forward energy barrier (eV)
            reverse_barrier_eV              (float)     Reverse energy barrier (eV)
            max_force_eV_per_A              (float)     Maximum force at convergence (eV/Å)
            converged                       (bool)      Whether optimization converged (max_force < fmax)
            num_images                      (int)       Number of images in NEB chain
            mep_energies                    (list)      Energy of each image along MEP (eV)
            mep_distances                   (list)      Cumulative distance along reaction coordinate
            ts_image_index                  (int)       Index of transition state (highest energy) image
            ts_energy_eV                    (float)     Transition state energy (eV)
            initial_energy_eV               (float)     Initial structure energy (eV)
            final_energy_eV                 (float)     Final structure energy (eV)
            reaction_energy_eV              (float)     Reaction energy (final - initial)
            calculation_time_seconds        (float)     Total calculation time
            parameters                      (dict)      All calculation parameters used
            units                           (dict)      Units for all quantities
            error                           (str)       Error message if calculation failed
    """
    import time
    start_time = time.time()
    
    try:
        from pymatgen.core import Structure
        from pymatgen.io.cif import CifParser
        from pymatgen.io.vasp import Poscar
        import matcalc as mtc
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import required libraries: {e}. "
                    f"Install with: pip install matcalc pymatgen"
        }
    
    # Parse images input
    try:
        parsed_images = _parse_images(images, n_images)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse images: {e}",
        }
    
    # Set appropriate backend based on calculator type
    try:
        import matgl
        if any(model in calculator.upper() for model in ["M3GNET", "CHGNET"]):
            matgl.set_backend('DGL')
        else:
            matgl.set_backend('PYG')
    except Exception:
        pass  # Backend setting is optional
    
    # Load calculator
    try:
        calc = mtc.load_fp(calculator)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load calculator '{calculator}': {e}",
        }
    
    # Initialize NEBCalc
    try:
        neb_calc = mtc.NEBCalc(
            calculator=calc,
            optimizer=optimizer,
            climb=climb,
            fmax=fmax,
            max_steps=max_steps,
            interval=interval,
            traj_folder=traj_folder,
        )
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to initialize NEBCalc: {e}",
        }
    
    # Run NEB calculation
    try:
        results = neb_calc.calc(parsed_images)
    except Exception as e:
        return {
            "success": False,
            "error": f"NEB calculation failed: {e}. Check that images are valid and "
                    f"represent a reasonable transition pathway.",
        }
    
    # Extract results
    try:
        barrier = results.get("barrier", 0.0)
        max_force = results.get("force", 0.0)
        mep = results.get("mep")
        
        # Extract MEP details
        if mep:
            mep_energies = [float(e) for e in mep.energies] if hasattr(mep, 'energies') else []
            mep_distances = [float(d) for d in mep.distances] if hasattr(mep, 'distances') else []
        else:
            mep_energies = []
            mep_distances = []
        
        # Calculate additional properties
        if mep_energies:
            initial_energy = mep_energies[0]
            final_energy = mep_energies[-1]
            ts_image_index = int(mep_energies.index(max(mep_energies)))
            ts_energy = mep_energies[ts_image_index]
            reaction_energy = final_energy - initial_energy
            reverse_barrier = ts_energy - final_energy
        else:
            initial_energy = 0.0
            final_energy = 0.0
            ts_image_index = 0
            ts_energy = 0.0
            reaction_energy = 0.0
            reverse_barrier = 0.0
        
        converged = bool(max_force < fmax)
        calculation_time = time.time() - start_time
        
        return {
            "success": True,
            "barrier_eV": float(barrier),
            "reverse_barrier_eV": float(reverse_barrier),
            "max_force_eV_per_A": float(max_force),
            "converged": converged,
            "num_images": int(len(mep_energies)),
            "mep_energies": mep_energies,
            "mep_distances": mep_distances,
            "ts_image_index": ts_image_index,
            "ts_energy_eV": float(ts_energy),
            "initial_energy_eV": float(initial_energy),
            "final_energy_eV": float(final_energy),
            "reaction_energy_eV": float(reaction_energy),
            "calculation_time_seconds": float(calculation_time),
            "parameters": {
                "calculator": calculator,
                "n_images": n_images,
                "climb": climb,
                "fmax": fmax,
                "max_steps": max_steps,
                "optimizer": optimizer,
                "interval": interval,
                "traj_folder": traj_folder,
            },
            "units": {
                "barrier": "eV",
                "reverse_barrier": "eV",
                "max_force": "eV/Angstrom",
                "energy": "eV",
                "distance": "Angstrom",
            },
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to extract NEB results: {e}",
        }


def _parse_images(
    images: Union[Dict[str, Any], List[Union[Dict[str, Any], str]]],
    n_images: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Parse images input into dict format expected by NEBCalc.
    
    Args:
        images: Dict with 'imageN' keys or list of structures
        n_images: Target number of images (for interpolation)
    
    Returns:
        Dict with 'image0', 'image1', etc. keys containing Structure objects
    """
    from pymatgen.core import Structure
    from pymatgen.io.cif import CifParser
    from pymatgen.io.vasp import Poscar
    import tempfile
    import os
    
    # Helper to parse a single structure
    def parse_structure(struct_input):
        if isinstance(struct_input, Structure):
            return struct_input
        elif isinstance(struct_input, dict):
            return Structure.from_dict(struct_input)
        elif isinstance(struct_input, str):
            if "data_" in struct_input or "_cell_" in struct_input:
                # CIF format
                with tempfile.NamedTemporaryFile(mode='w', suffix='.cif', delete=False) as f:
                    f.write(struct_input)
                    temp_path = f.name
                try:
                    parser = CifParser(temp_path)
                    structures = parser.get_structures()
                    if not structures:
                        raise ValueError("CIF contains no valid structures")
                    return structures[0]
                finally:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
            else:
                # POSCAR format
                poscar = Poscar.from_string(struct_input)
                return poscar.structure
        else:
            raise ValueError(f"Unsupported structure type: {type(struct_input)}")
    
    # Convert input to dict format
    if isinstance(images, dict):
        # Already in dict format, parse each structure
        image_dict = {}
        for key, value in images.items():
            if not key.startswith('image'):
                raise ValueError(f"Dict keys must be 'image0', 'image1', etc. Got: {key}")
            image_dict[key] = parse_structure(value)
    elif isinstance(images, list):
        # Convert list to dict
        if len(images) < 2:
            raise ValueError(f"Need at least 2 images (initial and final). Got {len(images)}")
        image_dict = {f'image{i}': parse_structure(img) for i, img in enumerate(images)}
    else:
        raise ValueError(f"images must be dict or list, got {type(images)}")
    
    # If n_images specified and different from current count, interpolate
    current_n = len(image_dict)
    if n_images and n_images != current_n:
        # Get sorted image keys
        sorted_keys = sorted(image_dict.keys(), key=lambda k: int(k.replace('image', '')))
        
        if n_images < current_n:
            # Use subset of images
            indices = [int(i * (current_n - 1) / (n_images - 1)) for i in range(n_images)]
            new_dict = {}
            for new_idx, old_idx in enumerate(indices):
                old_key = sorted_keys[old_idx]
                new_dict[f'image{new_idx}'] = image_dict[old_key]
            image_dict = new_dict
        elif n_images > current_n:
            # Need to interpolate more images
            # Get initial and final structures
            initial_struct = image_dict[sorted_keys[0]]
            final_struct = image_dict[sorted_keys[-1]]
            
            # Use pymatgen's interpolate method
            interpolated = initial_struct.interpolate(final_struct, nimages=n_images, 
                                                     autosort_tol=0.5)
            
            # Create new dict with interpolated structures
            image_dict = {f'image{i}': struct for i, struct in enumerate(interpolated)}
    
    return image_dict
