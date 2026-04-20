"""
Tool for calculating equation of state (EOS) and bulk modulus using matcalc.

Computes volume-energy relationships by evaluating the structure at different
volumes and fitting to standard EOS models (Birch-Murnaghan, Murnaghan, Vinet).

Use this tool to:
- Determine equilibrium volume and lattice constants
- Calculate bulk modulus and its pressure derivative
- Validate structure stability across volume range
- Compare different EOS model predictions
"""

from typing import Dict, Any, Optional, Union, Annotated, List
from pydantic import Field
import numpy as np


def matcalc_calc_eos(
    input_structure: Annotated[
        Union[Dict[str, Any], str],
        Field(
            description=(
                "Structure to calculate EOS for as a pymatgen Structure dict "
                "(from Structure.as_dict()), or a CIF/POSCAR string. Can be output from "
                "matgl_relax_structure or any pymatgen tool."
            )
        )
    ],
    calculator: Annotated[
        str,
        Field(
            default="TensorNet-MatPES-PBE-v2025.1-PES",
            description=(
                "Calculator/potential to use. Options:\n"
                "- 'TensorNet-MatPES-PBE-v2025.1-PES' or 'pbe' (default, fast and accurate)\n"
                "- 'TensorNet-MatPES-r2SCAN-v2025.1-PES' or 'r2scan' (higher accuracy)\n"
                "- 'M3GNet-MatPES-PBE-v2025.1-PES' or 'm3gnet'\n"
                "- 'CHGNet-MatPES-PBE-2025.2.10-2.7M-PES' or 'chgnet'\n"
                "Or any other matcalc-supported universal calculator."
            )
        )
    ] = "TensorNet-MatPES-PBE-v2025.1-PES",
    relax_structure: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True (default), relaxes the structure before EOS calculation. "
                "Set to False if structure is already at equilibrium."
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
                "Force convergence tolerance in eV/Å for structure relaxations (0.01-1.0). "
                "Lower values = more accurate but slower. Default: 0.1 eV/Å."
            )
        )
    ] = 0.1,
    n_points: Annotated[
        int,
        Field(
            default=11,
            ge=5,
            le=30,
            description=(
                "Number of volume points to sample for EOS fitting (5-30). "
                "More points = better fit but more calculations. Default: 11. "
                "Minimum 5 recommended for reliable fitting."
            )
        )
    ] = 11,
    max_abs_strain: Annotated[
        float,
        Field(
            default=0.1,
            ge=0.02,
            le=0.3,
            description=(
                "Maximum absolute volumetric strain for EOS sampling (0.02-0.3). "
                "Default: 0.1 (±10% volume change). Larger strains may cause instability."
            )
        )
    ] = 0.1,
    eos_models: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description=(
                "List of EOS models to fit. Options: 'birch_murnaghan', 'murnaghan', "
                "'vinet', 'birch', 'pourier_tarantola'. "
                "Default: ['birch_murnaghan', 'murnaghan', 'vinet'] (most common models)."
            )
        )
    ] = None,
) -> Dict[str, Any]:
    """
    Calculate equation of state and bulk modulus using matcalc.
    
    Computes energy as a function of volume by uniformly scaling the structure
    and fitting to analytical EOS models. Returns equilibrium volume, bulk modulus,
    and parameters for multiple EOS models.
    
    The calculation workflow:
    1. Optional: Relax input structure to equilibrium (if relax_structure=True)
    2. Generate n_points volumes spanning (1-max_abs_strain) to (1+max_abs_strain)
    3. For each volume: scale structure uniformly, compute energy
    4. Fit E-V data to analytical EOS models
    5. Extract equilibrium properties and bulk moduli
    
    Typical Use Cases:
        **Already relaxed structure:**
        matcalc_calc_eos(relaxed_structure, relax_structure=False)
        
        **Unrelaxed structure (one-shot calculation):**
        matcalc_calc_eos(structure, relax_structure=True)
        
        **High accuracy (more points, tighter convergence):**
        matcalc_calc_eos(structure, n_points=21, max_abs_strain=0.15, fmax=0.01)
        
        **Fast screening:**
        matcalc_calc_eos(structure, n_points=7, fmax=0.3)
    
    EOS Models:
        - Birch-Murnaghan: Most commonly used, accurate for wide range of materials
        - Murnaghan: Simpler model, good for small compressions
        - Vinet: Universal EOS, excellent for highly compressible materials
        - Birch: Linear approximation of Birch-Murnaghan
        - Pourier-Tarantola: Logarithmic strain formulation
    
    Args:
        input_structure: Structure to analyze (pymatgen dict, CIF, or POSCAR string)
        calculator: ML potential or calculator name
        relax_structure: Whether to relax structure before EOS calculation
        fmax: Force convergence tolerance for relaxations (eV/Å)
        n_points: Number of volume points for EOS sampling (5-30)
        max_abs_strain: Maximum volumetric strain magnitude (0.02-0.3)
        eos_models: List of EOS models to fit, or None for default set
    
    Returns:
        Dictionary containing:
            success                         (bool)      Whether calculation completed successfully
            structure                       (dict)      Input structure (pymatgen dict)
            final_structure                 (dict)      Relaxed structure if relax_structure=True
            volumes                         (list)      Volume points sampled (Å³)
            energies                        (list)      Energy at each volume (eV)
            num_points                      (int)       Number of E-V data points
            eos_fits                        (dict)      Fitted parameters for each EOS model:
                birch_murnaghan             (dict)      BM fit results (if requested)
                murnaghan                   (dict)      Murnaghan fit results (if requested)
                vinet                       (dict)      Vinet fit results (if requested)
            recommended_model               (str)       Best-fitting EOS model based on R²
            equilibrium_volume_A3           (float)     Equilibrium volume (Å³) from best fit
            equilibrium_energy_eV           (float)     Ground state energy (eV) from best fit
            bulk_modulus_GPa                (float)     Bulk modulus (GPa) from best fit
            bulk_modulus_derivative         (float)     Pressure derivative B' from best fit
            calculation_time_seconds        (float)     Total calculation time
            parameters                      (dict)      All calculation parameters used
            error                           (str)       Error message if calculation failed
            
        Each eos_fits[model] contains:
            model                           (str)       EOS model name
            equilibrium_volume_A3           (float)     V₀ (Å³)
            equilibrium_energy_eV           (float)     E₀ (eV)
            bulk_modulus_GPa                (float)     B₀ (GPa)
            bulk_modulus_derivative         (float)     B'₀ (dimensionless)
            r2_score                        (float)     R² goodness of fit (closer to 1.0 = better)
    """
    import time
    start_time = time.time()
    
    try:
        from pymatgen.core import Structure
        from pymatgen.io.cif import CifParser
        from pymatgen.io.vasp import Poscar
        from pymatgen.analysis.eos import EOS
        import matcalc as mtc
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import required libraries: {e}. "
                    f"Install with: pip install matcalc pymatgen"
        }
    
    try:
        # Parse input structure
        if isinstance(input_structure, dict):
            structure = Structure.from_dict(input_structure)
        elif isinstance(input_structure, str):
            if "data_" in input_structure or "_cell_" in input_structure:
                # CIF format
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(mode='w', suffix='.cif', delete=False) as f:
                    f.write(input_structure)
                    temp_path = f.name
                try:
                    parser = CifParser(temp_path)
                    structures = parser.get_structures()
                    if not structures:
                        return {"success": False, "error": "CIF file contains no valid structures"}
                    structure = structures[0]
                finally:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
            else:
                # POSCAR format
                poscar = Poscar.from_string(input_structure)
                structure = poscar.structure
        else:
            return {
                "success": False,
                "error": f"Unsupported input_structure type: {type(input_structure)}. "
                        f"Expected dict, CIF string, or POSCAR string."
            }
        
        initial_structure_dict = structure.as_dict()
        
        # Load calculator
        try:
            calc_obj = mtc.load_fp(calculator)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to load calculator '{calculator}': {e}"
            }
        
        # Initialize EOSCalc
        try:
            eos_calc = mtc.EOSCalc(
                calc_obj,
                fmax=fmax,
                n_points=n_points,
                max_abs_strain=max_abs_strain,
                relax_structure=relax_structure,
            )
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to initialize EOSCalc: {e}"
            }
        
        # Perform calculation
        try:
            results = eos_calc.calc(structure)
        except Exception as e:
            return {
                "success": False,
                "error": f"EOS calculation failed: {e}. "
                        f"Structure may be unstable or volume range inappropriate."
            }
        
        # Extract volumes and energies from matcalc results
        volumes = results["eos"]["volumes"]
        energies = results["eos"]["energies"]
        
        # Set default EOS models if not provided
        if eos_models is None:
            eos_models = ["birch_murnaghan", "murnaghan", "vinet"]
        
        # Conversion factor: eV/Å³ to GPa
        EV_A3_TO_GPA = 160.21766208
        
        # Fit multiple EOS models using pymatgen
        eos_fits = {}
        best_r2 = -np.inf
        best_model = None
        
        for model_name in eos_models:
            try:
                eos = EOS(model_name)
                eos_fit = eos.fit(volumes, energies)
                
                # Extract parameters
                # eos_fit attributes: e0 (energy), v0 (volume), b0 (bulk modulus in eV/Å³), b1 (derivative)
                r2 = 1.0 - np.sum((np.array(energies) - eos_fit.func(volumes))**2) / np.sum((np.array(energies) - np.mean(energies))**2)
                
                eos_fits[model_name] = {
                    "model": model_name,
                    "equilibrium_volume_A3": round(float(eos_fit.v0), 4),
                    "equilibrium_energy_eV": round(float(eos_fit.e0), 6),
                    "bulk_modulus_GPa": round(float(eos_fit.b0 * EV_A3_TO_GPA), 4),
                    "bulk_modulus_derivative": round(float(eos_fit.b1), 4),
                    "r2_score": round(float(r2), 6),
                }
                
                # Track best model
                if r2 > best_r2:
                    best_r2 = r2
                    best_model = model_name
                    
            except Exception as e:
                eos_fits[model_name] = {
                    "model": model_name,
                    "error": f"Failed to fit {model_name} EOS: {str(e)}"
                }
        
        # Get final structure
        final_structure = results.get("final_structure")
        if final_structure is not None:
            if hasattr(final_structure, 'as_dict'):
                final_structure_dict = final_structure.as_dict()
            else:
                # Convert ASE Atoms to pymatgen Structure
                from pymatgen.io.ase import AseAtomsAdaptor
                final_structure_dict = AseAtomsAdaptor.get_structure(final_structure).as_dict()
        else:
            final_structure_dict = initial_structure_dict
        
        calculation_time = time.time() - start_time
        
        # Build response
        response = {
            "success": True,
            "structure": initial_structure_dict,
            "final_structure": final_structure_dict,
            "volumes": [round(float(v), 4) for v in volumes],
            "energies": [round(float(e), 6) for e in energies],
            "num_points": len(volumes),
            "eos_fits": eos_fits,
            "recommended_model": best_model,
            "calculation_time_seconds": round(calculation_time, 2),
            "parameters": {
                "calculator": calculator,
                "relax_structure": relax_structure,
                "fmax": fmax,
                "n_points": n_points,
                "max_abs_strain": max_abs_strain,
                "eos_models": eos_models,
            },
        }
        
        # Add top-level properties from best fit
        if best_model and best_model in eos_fits and "error" not in eos_fits[best_model]:
            best_fit = eos_fits[best_model]
            response["equilibrium_volume_A3"] = best_fit["equilibrium_volume_A3"]
            response["equilibrium_energy_eV"] = best_fit["equilibrium_energy_eV"]
            response["bulk_modulus_GPa"] = best_fit["bulk_modulus_GPa"]
            response["bulk_modulus_derivative"] = best_fit["bulk_modulus_derivative"]
            
            response["message"] = (
                f"EOS calculated successfully using {n_points} volume points. "
                f"Best fit: {best_model} (R² = {best_r2:.4f}). "
                f"V₀ = {best_fit['equilibrium_volume_A3']:.2f} Å³, "
                f"B₀ = {best_fit['bulk_modulus_GPa']:.2f} GPa."
            )
        else:
            response["warning"] = "All EOS fits failed. Check volume range and data quality."
        
        return response
    
    except Exception as e:
        calculation_time = time.time() - start_time
        return {
            "success": False,
            "calculation_time_seconds": round(calculation_time, 2),
            "error": f"Unexpected error during EOS calculation: {str(e)}"
        }
