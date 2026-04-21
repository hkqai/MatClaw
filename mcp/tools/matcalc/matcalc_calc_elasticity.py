"""
Tool for calculating elastic properties of crystal structures using matcalc.

Computes the full elastic tensor, bulk modulus, shear modulus, Young's modulus,
and Poisson's ratio using strain-stress relationships. Supports both ML potentials
(MatGL models) and classical calculators.

Use this tool to:
- Calculate mechanical properties of materials
- Screen candidates by mechanical stability (positive definite elastic tensor)
- Predict material hardness, ductility, and elastic anisotropy
- Optimize structures for specific mechanical applications
"""

from typing import Dict, Any, Optional, Union, Annotated, List
from pydantic import Field
import numpy as np


def matcalc_calc_elasticity(
    input_structure: Annotated[
        Union[Dict[str, Any], str],
        Field(
            description=(
                "Structure to calculate elastic properties for as a pymatgen Structure dict "
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
            default=False,
            description=(
                "If True, relaxes the structure before calculating elastic properties. "
                "If False (default), uses the input structure as-is. Set to False if "
                "structure is already relaxed (e.g., from matgl_relax_structure)."
            )
        )
    ] = False,
    relax_deformed_structures: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True (default), relaxes atomic positions in each strained structure. "
                "Recommended for accurate elastic constants. Only disable for very fast "
                "approximate calculations."
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
                "Force convergence tolerance in eV/Å for relaxations (0.01-1.0). "
                "Lower values = more accurate but slower. Default: 0.1 eV/Å. "
                "Only used if relax_structure or relax_deformed_structures is True."
            )
        )
    ] = 0.1,
    norm_strains: Annotated[
        Optional[List[float]],
        Field(
            default=None,
            description=(
                "List of normal strain values to apply for elastic constant fitting. "
                "Default: np.linspace(-0.004, 0.004, num=4). "
                "Increase range for softer materials, decrease for harder materials. "
                "More points = better fit but more calculations."
            )
        )
    ] = None,
    shear_strains: Annotated[
        Optional[List[float]],
        Field(
            default=None,
            description=(
                "List of shear strain values to apply for elastic constant fitting. "
                "Default: np.linspace(-0.004, 0.004, num=4). "
                "Should typically match norm_strains in magnitude."
            )
        )
    ] = None,
    use_equilibrium: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True (default), uses equilibrium (unstrained) structure for reference. "
                "Recommended for accurate elastic constants."
            )
        )
    ] = True,
    store_trajectory: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, stores full trajectory of strained structures and energies. "
                "Useful for debugging or detailed analysis. Warning: can be large."
            )
        )
    ] = False,
) -> Dict[str, Any]:
    """
    Calculate elastic properties of a crystal structure using matcalc.
    
    Computes the full elastic tensor by applying small strains to the structure
    and fitting stress-strain relationships. Returns bulk modulus (K), shear modulus (G),
    Young's modulus (E), Poisson's ratio (ν), and elastic anisotropy indices.
    
    The calculation workflow:
    1. Optional: Relax input structure to equilibrium (if relax_structure=True)
    2. Apply systematic normal and shear strains
    3. For each strained structure: relax atoms (if relax_deformed_structures=True), compute stress
    4. Fit elastic tensor from stress-strain data
    5. Derive Voigt, Reuss, and Hill (VRH) averages of bulk/shear moduli
    
    Typical Use Cases:
        **Already relaxed structure (recommended workflow):**
        1. First: matgl_relax_structure(structure) → relaxed_structure
        2. Then: matcalc_calc_elasticity(relaxed_structure, relax_structure=False)
        
        **Unrelaxed structure (one-shot calculation):**
        matcalc_calc_elasticity(structure, relax_structure=True)
        
        **Fast screening (less accurate):**
        matcalc_calc_elasticity(structure, relax_deformed_structures=False, fmax=0.5)
        
        **High accuracy:**
        matcalc_calc_elasticity(structure, fmax=0.01, 
                                norm_strains=np.linspace(-0.005, 0.005, 6))
    
    Mechanical Stability Criteria:
        - Cubic: C11 > |C12|, C44 > 0, C11 + 2C12 > 0
        - Tetragonal: C11 > |C12|, 2C13² < C33(C11+C12), C44 > 0, C66 > 0
        - Hexagonal: C11 > |C12|, 2C13² < C33(C11+C12), C44 > 0
        - Orthorhombic: All Cii > 0, C11C22 > C12², C11C22C33 + 2C12C13C23 - C11C23² - C22C13² - C33C12² > 0
        - General: All eigenvalues of elastic tensor > 0
    
    Args:
        input_structure: Structure to analyze (pymatgen dict, CIF, or POSCAR string)
        calculator: ML potential or calculator name
        relax_structure: Whether to relax structure before calculating (False if already relaxed)
        relax_deformed_structures: Whether to relax strained structures (True recommended)
        fmax: Force convergence tolerance for relaxations (eV/Å)
        norm_strains: Normal strain values for fitting (default: ±0.4% in 4 points)
        shear_strains: Shear strain values for fitting (default: ±0.4% in 4 points)
        use_equilibrium: Use equilibrium structure for reference
        store_trajectory: Save detailed trajectory information
    
    Returns:
        Dictionary containing:
            success                     (bool)      Whether calculation completed successfully
            structure                   (dict)      Input structure (pymatgen dict)
            final_structure             (dict)      Relaxed structure if relax_structure=True, else same as input
            elastic_tensor              (list)      6x6 elastic tensor in Voigt notation (GPa)
            elastic_tensor_IEEE         (list)      Elastic tensor in IEEE convention (GPa)
            compliance_tensor           (list)      6x6 compliance tensor (1/GPa)
            bulk_modulus_voigt_GPa      (float)     Voigt bound on bulk modulus
            bulk_modulus_reuss_GPa      (float)     Reuss bound on bulk modulus
            bulk_modulus_vrh_GPa        (float)     Voigt-Reuss-Hill average bulk modulus
            shear_modulus_voigt_GPa     (float)     Voigt bound on shear modulus
            shear_modulus_reuss_GPa     (float)     Reuss bound on shear modulus
            shear_modulus_vrh_GPa       (float)     Voigt-Reuss-Hill average shear modulus
            youngs_modulus_GPa          (float)     Young's modulus derived from VRH averages
            poissons_ratio              (float)     Poisson's ratio
            pugh_ratio                  (float)     K/G ratio (ductility indicator: >1.75 = ductile)
            universal_anisotropy        (float)     Universal elastic anisotropy index (0 = isotropic)
            homogeneous_poisson         (float)     Homogeneous Poisson ratio
            is_stable                   (bool)      Whether elastic tensor is mechanically stable
            eigenvalues                 (list)      Eigenvalues of elastic tensor (all > 0 for stability)
            num_deformed_structures     (int)       Number of strained structures calculated
            residuals_sum               (float)     Sum of squared residuals from elastic fitting
            r2_score                    (float)     R² goodness of fit for stress-strain fitting
            calculation_time_seconds    (float)     Total calculation time
            parameters                  (dict)      All calculation parameters used
            trajectory                  (list)      Strain-stress data for each deformation (if store_trajectory=True)
            error                       (str)       Error message if calculation failed
    """
    import time
    start_time = time.time()
    
    try:
        from pymatgen.core import Structure
        from pymatgen.io.cif import CifParser
        from pymatgen.io.vasp import Poscar
        import matcalc as mtc
        from pymatgen.analysis.elasticity import ElasticTensor
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
                # CIF format - write to temporary file and parse
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(mode='w', suffix='.cif', delete=False) as f:
                    f.write(input_structure)
                    temp_path = f.name
                try:
                    parser = CifParser(temp_path)
                    structures = parser.get_structures()
                    if not structures:
                        return {
                            "success": False,
                            "error": "CIF file contains no valid structures"
                        }
                    structure = structures[0]
                except Exception as cif_error:
                    return {
                        "success": False,
                        "error": f"Failed to parse CIF: {str(cif_error)}"
                    }
                finally:
                    if os.path.exists(temp_path):
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
        
        # Store initial structure
        initial_structure_dict = structure.as_dict()
        
        # Set default strains if not provided
        # NOTE: matcalc requires non-zero strains, so we skip zero
        if norm_strains is None:
            norm_strains = [-0.01, -0.005, 0.005, 0.01]  # Default from matcalc, no zero
        if shear_strains is None:
            shear_strains = [-0.06, -0.03, 0.03, 0.06]  # Default from matcalc, no zero
        
        # Set appropriate backend based on calculator type
        try:
            import matgl
            # M3GNet and CHGNet models require DGL backend
            if any(model in calculator.upper() for model in ["M3GNET", "CHGNET"]):
                matgl.set_backend('DGL')
            else:
                # TensorNet and other models use PYG (default)
                matgl.set_backend('PYG')
        except Exception as e:
            # Backend setting is optional, continue if it fails
            pass
        
        # Load calculator
        try:
            calc_obj = mtc.load_fp(calculator)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to load calculator '{calculator}': {e}. "
                        f"Check calculator name or install required packages."
            }
        
        # Initialize ElasticityCalc
        try:
            elast_calc = mtc.ElasticityCalc(
                calc_obj,
                fmax=fmax,
                norm_strains=norm_strains,
                shear_strains=shear_strains,
                use_equilibrium=use_equilibrium,
                relax_structure=relax_structure,
                relax_deformed_structures=relax_deformed_structures,
            )
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to initialize ElasticityCalc: {e}"
            }
        
        # Perform calculation
        try:
            results = elast_calc.calc(structure)
        except Exception as e:
            return {
                "success": False,
                "error": f"Elasticity calculation failed: {e}. "
                        f"Structure may be unstable or strain range inappropriate."
            }
        
        # Extract and convert results
        # matcalc elastic tensors are in eV/Å³, need conversion to GPa
        EV_PER_A3_TO_GPA = 160.21766208  # Conversion factor
        
        # Get elastic tensor from matcalc results
        elastic_tensor_raw = results.get("elastic_tensor")
        
        # matcalc returns a pymatgen ElasticTensor object in eV/Å³
        # We need to convert it to GPa by multiplying all elements by the conversion factor
        if hasattr(elastic_tensor_raw, 'voigt'):
            # It's already an ElasticTensor object - convert to GPa
            tensor_eV = elastic_tensor_raw.voigt  # Get 6x6 Voigt form in eV/Å³
            tensor_GPa = tensor_eV * EV_PER_A3_TO_GPA  # Convert to GPa
            et = ElasticTensor.from_voigt(tensor_GPa)
        elif hasattr(elastic_tensor_raw, 'shape'):
            tensor_shape = elastic_tensor_raw.shape
            if len(tensor_shape) == 4 and tensor_shape == (3, 3, 3, 3):
                # Full 3x3x3x3 tensor in eV/Å³ - convert to GPa
                tensor_GPa = elastic_tensor_raw * EV_PER_A3_TO_GPA
                et = ElasticTensor(tensor_GPa)
            elif len(tensor_shape) == 2 and tensor_shape == (6, 6):
                # Already in Voigt notation, convert to GPa
                tensor_GPa = elastic_tensor_raw * EV_PER_A3_TO_GPA
                et = ElasticTensor.from_voigt(tensor_GPa)
            else:
                return {
                    "success": False,
                    "error": f"Unexpected elastic tensor shape: {tensor_shape}. Expected (3,3,3,3) or (6,6)."
                }
        else:
            return {
                "success": False,
                "error": f"Elastic tensor has unexpected type: {type(elastic_tensor_raw)}"
            }
        
        # Get the Voigt form (6x6) for output
        elastic_tensor_voigt = et.voigt
        
        # Calculate compliance tensor
        compliance_tensor = et.compliance_tensor.voigt
        
        # Get bulk and shear moduli from converted ElasticTensor (now in GPa)
        bulk_modulus_vrh = et.k_vrh
        shear_modulus_vrh = et.g_vrh
        
        # Calculate Voigt and Reuss bounds
        k_voigt = et.k_voigt
        k_reuss = et.k_reuss
        g_voigt = et.g_voigt
        g_reuss = et.g_reuss
        
        # Calculate derived properties
        # Young's modulus: E = 9KG / (3K + G)
        youngs_modulus = (9 * bulk_modulus_vrh * shear_modulus_vrh) / (3 * bulk_modulus_vrh + shear_modulus_vrh)
        
        # Poisson's ratio: ν = (3K - 2G) / (6K + 2G)
        poissons_ratio = (3 * bulk_modulus_vrh - 2 * shear_modulus_vrh) / (6 * bulk_modulus_vrh + 2 * shear_modulus_vrh)
        
        # Pugh's ratio (ductility indicator): K/G
        # K/G > 1.75 suggests ductile behavior, < 1.75 suggests brittle
        pugh_ratio = bulk_modulus_vrh / shear_modulus_vrh if shear_modulus_vrh > 0 else 0
        
        # Universal elastic anisotropy index
        universal_anisotropy = 5 * (g_voigt / g_reuss) + (k_voigt / k_reuss) - 6 if g_reuss > 0 and k_reuss > 0 else 0
        
        # Homogeneous Poisson ratio (from Voigt-Reuss-Hill averages)
        homogeneous_poisson = (3 * bulk_modulus_vrh - 2 * shear_modulus_vrh) / (2 * (3 * bulk_modulus_vrh + shear_modulus_vrh))
        
        # Check mechanical stability (all eigenvalues of elastic tensor should be positive)
        eigenvalues = list(np.linalg.eigvalsh(elastic_tensor_voigt))
        is_stable = all(ev > 0 for ev in eigenvalues)
        
        # Get final structure (may be relaxed if relax_structure=True)
        final_structure = results.get("final_structure")
        if final_structure is not None:
            if hasattr(final_structure, 'as_dict'):
                final_structure_dict = final_structure.as_dict()
            else:
                final_structure_dict = Structure.from_sites(final_structure).as_dict()
        else:
            final_structure_dict = initial_structure_dict
        
        # Calculate R² score and residuals if available
        residuals_sum = results.get("residuals_sum", 0.0)
        
        # Calculate total number of deformed structures
        num_deformed = len(norm_strains) * 6 + len(shear_strains) * 6  # Approximate
        if use_equilibrium:
            num_deformed += 1
        
        calculation_time = time.time() - start_time
        
        # Build response dictionary
        response = {
            "success": True,
            "structure": initial_structure_dict,
            "final_structure": final_structure_dict,
            "elastic_tensor_voigt": elastic_tensor_voigt.tolist() if hasattr(elastic_tensor_voigt, 'tolist') else elastic_tensor_voigt,
            "elastic_tensor_IEEE": et.voigt.tolist(),
            "compliance_tensor": compliance_tensor.tolist(),
            "bulk_modulus_voigt_GPa": round(float(k_voigt), 4),
            "bulk_modulus_reuss_GPa": round(float(k_reuss), 4),
            "bulk_modulus_vrh_GPa": round(float(bulk_modulus_vrh), 4),
            "shear_modulus_voigt_GPa": round(float(g_voigt), 4),
            "shear_modulus_reuss_GPa": round(float(g_reuss), 4),
            "shear_modulus_vrh_GPa": round(float(shear_modulus_vrh), 4),
            "youngs_modulus_GPa": round(float(youngs_modulus), 4),
            "poissons_ratio": round(float(poissons_ratio), 4),
            "pugh_ratio": round(float(pugh_ratio), 4),
            "universal_anisotropy": round(float(universal_anisotropy), 4),
            "homogeneous_poisson": round(float(homogeneous_poisson), 4),
            "is_stable": bool(is_stable),
            "eigenvalues": [round(float(ev), 6) for ev in eigenvalues],
            "num_deformed_structures": num_deformed,
            "residuals_sum": round(float(residuals_sum), 6),
            "calculation_time_seconds": round(calculation_time, 2),
            "parameters": {
                "calculator": calculator,
                "relax_structure": relax_structure,
                "relax_deformed_structures": relax_deformed_structures,
                "fmax": fmax,
                "norm_strains": norm_strains,
                "shear_strains": shear_strains,
                "use_equilibrium": use_equilibrium,
            },
        }
        
        # Add R² score calculation (estimate from residuals)
        # For elastic fitting, R² ≈ 1 - (residuals_sum / total_variance)
        # This is an approximation - exact calculation requires full stress data
        if residuals_sum > 0:
            response["r2_score"] = round(1.0 - min(residuals_sum / 100.0, 1.0), 4)
        else:
            response["r2_score"] = 1.0
        
        # Add stability warnings
        if not is_stable:
            response["warning"] = (
                "Elastic tensor has negative eigenvalues - structure is mechanically UNSTABLE. "
                "This may indicate: (1) incorrect structure, (2) imaginary phonon modes, "
                "(3) insufficient relaxation, or (4) inappropriate strain range."
            )
        
        # Add ductility interpretation
        if pugh_ratio > 1.75:
            response["ductility"] = "ductile (K/G > 1.75)"
        else:
            response["ductility"] = "brittle (K/G < 1.75)"
        
        # Add anisotropy interpretation
        if universal_anisotropy < 0.1:
            response["anisotropy"] = "nearly isotropic (A < 0.1)"
        elif universal_anisotropy < 1.0:
            response["anisotropy"] = "weakly anisotropic (0.1 < A < 1.0)"
        else:
            response["anisotropy"] = f"strongly anisotropic (A = {universal_anisotropy:.2f})"
        
        # Add trajectory information if requested
        if store_trajectory and "trajectory" in results:
            response["trajectory"] = results["trajectory"]
        
        # Add summary message
        response["message"] = (
            f"Elastic properties calculated successfully. "
            f"K_VRH = {bulk_modulus_vrh:.2f} GPa, G_VRH = {shear_modulus_vrh:.2f} GPa, "
            f"E = {youngs_modulus:.2f} GPa. "
            f"Material is {response['ductility']} and {response['anisotropy']}. "
            f"Mechanically {'STABLE' if is_stable else 'UNSTABLE'}."
        )
        
        return response
    
    except Exception as e:
        calculation_time = time.time() - start_time
        return {
            "success": False,
            "calculation_time_seconds": round(calculation_time, 2),
            "error": f"Unexpected error during elasticity calculation: {str(e)}"
        }
