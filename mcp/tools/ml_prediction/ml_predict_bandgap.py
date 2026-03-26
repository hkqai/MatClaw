"""
Tool for predicting electronic band gap of crystal structures using machine learning models.

Uses pre-trained MEGNet property prediction models to estimate electronic band gap
(eV) of crystal structures. Much faster than DFT calculations while providing
reasonable accuracy for high-throughput screening.

Use this tool to:
- Screen large sets of candidate structures by electronic properties
- Identify semiconductors vs. metals/insulators before expensive DFT calculations
- Filter materials by target band gap ranges for specific applications
- Rank materials by predicted optoelectronic properties
"""

from typing import Dict, Any, Optional, Union, Annotated, Literal
from pydantic import Field


def ml_predict_bandgap(
    input_structure: Annotated[
        Union[Dict[str, Any], str],
        Field(
            description=(
                "Structure to predict band gap for, as a pymatgen Structure dict "
                "(from Structure.as_dict()), or a CIF/POSCAR string. Can be output from any "
                "pymatgen tool or Materials Project API."
            )
        )
    ],
    model: Annotated[
        Literal["MEGNet-MP-2019.4.1-BandGap-mfi"],
        Field(
            default="MEGNet-MP-2019.4.1-BandGap-mfi",
            description=(
                "ML model to use for band gap prediction. Currently only one model is supported:\n"
                "- MEGNet-MP-2019.4.1-BandGap-mfi (MatErials Graph Network trained on MP data)"
            )
        )
    ] = "MEGNet-MP-2019.4.1-BandGap-mfi",
) -> Dict[str, Any]:
    """
    Predict electronic band gap of a crystal structure using ML models.
    
    Predicts the electronic band gap (eV) using a pre-trained graph neural network
    model (MEGNet) trained on Materials Project DFT data. Returns the predicted
    band gap which characterizes the electronic properties of the material.
    
    The band gap is the energy difference between the valence band maximum and
    conduction band minimum, determining whether a material is metallic,
    semiconducting, or insulating. This property is critical for electronic and
    optoelectronic applications.
    
    Common Use Cases:
        1. Electronic screening: Identify metals vs. semiconductors vs. insulators
        2. Optoelectronic discovery: Find materials with desired band gaps for solar cells, LEDs
        3. Semiconductor design: Screen for specific band gap ranges (e.g., 1-2 eV for photovoltaics)
        4. Pre-DFT screening: Identify promising candidates before expensive calculations
    
    Band Gap Interpretation:
        - 0 eV: Metallic (conductor, no band gap)
        - 0-1 eV: Narrow band gap semiconductor (IR-sensitive, good for IR detectors)
        - 1-2 eV: Medium band gap semiconductor (visible light absorption, solar cells)
        - 2-3 eV: Wide band gap semiconductor (UV-sensitive, blue LEDs)
        - >3 eV: Very wide band gap semiconductor/insulator (transparent, dielectrics)
    
    Note:
        DFT typically underestimates band gaps, so ML predictions trained on DFT data
        may also underestimate. For more accurate values, apply correction factors
        (e.g., HSE06 or GW) or use as relative ranking metric only.
    
    Args:
        input_structure: Structure as pymatgen dict, CIF, or POSCAR string
        model: ML model to use for prediction (currently only MEGNet-MP-2019.4.1-BandGap-mfi)
    
    Returns:
        Dictionary containing:
            success                 (bool)      Whether prediction succeeded
            band_gap_eV             (float)     Predicted electronic band gap (eV)
            model_used              (str)       Model name used for prediction
            formula                 (str)       Chemical formula of the structure
            num_sites               (int)       Number of atoms in the structure
            structure_info          (dict)      Basic info about the structure
            material_class          (str)       Classification: metal, narrow gap, semiconductor, etc.
            interpretation          (str)       Human-readable electronic property assessment
            error                   (str)       Error message if prediction failed
    """
    try:
        from pymatgen.core import Structure
        from pymatgen.io.cif import CifParser
        from pymatgen.io.vasp import Poscar
        import matgl
        import torch
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import required libraries: {e}. "
                    f"Install with: pip install matgl pymatgen torch"
        }
    
    # Check if DGL is available (required for band gap models)
    try:
        import dgl
    except Exception as e:
        return {
            "success": False,
            "error": f"DGL backend not available: {e}. "
                    f"Band gap prediction requires DGL. "
                    f"Install with: pip install dgl -f https://data.dgl.ai/wheels/torch-2.0/repo.html"
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
        
        # Get structure info
        formula = structure.composition.reduced_formula
        num_sites = len(structure)
        
        # Set backend for MatGL (required for property prediction models)
        matgl.set_backend('DGL')
        
        # Load the band gap prediction model
        try:
            ml_model = matgl.load_model(model)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to load model '{model}': {e}. "
                        f"Check model name or network connection."
            }
        
        # Predict band gap
        # Band gap models require state_attr parameter
        try:
            state_attr = torch.tensor([0], dtype=torch.long)
            bandgap_tensor = ml_model.predict_structure(structure, state_attr=state_attr)
            bandgap = float(bandgap_tensor.numpy())
        except Exception as e:
            return {
                "success": False,
                "error": f"Prediction failed: {e}. "
                        f"Structure may contain unsupported elements or be malformed."
            }
        
        # Classify material and provide interpretation
        if bandgap < 0.1:
            material_class = "Metal/Conductor"
            interpretation = "Metallic conductor (no band gap, free electron conduction)"
        elif bandgap < 1.0:
            material_class = "Narrow Band Gap Semiconductor"
            interpretation = f"Narrow gap semiconductor (IR-sensitive, suitable for IR detectors, thermoelectrics)"
        elif bandgap < 2.0:
            material_class = "Semiconductor"
            interpretation = f"Semiconductor with visible light absorption (suitable for photovoltaics, photodetectors)"
        elif bandgap < 3.0:
            material_class = "Wide Band Gap Semiconductor"
            interpretation = f"Wide gap semiconductor (UV-sensitive, suitable for blue LEDs, power electronics)"
        else:
            material_class = "Very Wide Band Gap Semiconductor/Insulator"
            interpretation = f"Very wide gap material (transparent in visible, suitable for dielectrics, UV optoelectronics)"
        
        # Build response
        response = {
            "success": True,
            "band_gap_eV": round(bandgap, 6),
            "model_used": model,
            "formula": formula,
            "num_sites": num_sites,
            "material_class": material_class,
            "structure_info": {
                "formula": formula,
                "num_sites": num_sites,
                "volume": round(structure.volume, 4),
                "density_g_per_cm3": round(structure.density, 4),
            },
            "interpretation": interpretation,
            "message": (
                f"Predicted band gap for {formula}: {bandgap:.4f} eV. "
                f"{material_class}. {interpretation}"
            )
        }
        
        return response
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error during prediction: {str(e)}"
        }
