"""
Tool for predicting formation energy of crystal structures using machine learning models.

Uses pre-trained M3GNet/MEGNet property prediction models to estimate formation energy
(eV/atom) of crystal structures. Much faster than DFT calculations while providing
reasonable accuracy for high-throughput screening.

Use this tool to:
- Screen large sets of candidate structures by formation energy
- Estimate thermodynamic stability before expensive DFT calculations
- Rank materials by predicted stability
- Filter out highly unfavorable compositions early in discovery workflows
"""

from typing import Dict, Any, Optional, Union, Annotated, Literal
from pydantic import Field


def ml_predict_eform(
    input_structure: Annotated[
        Union[Dict[str, Any], str],
        Field(
            description=(
                "Structure to predict formation energy for, as a pymatgen Structure dict "
                "(from Structure.as_dict()), or a CIF/POSCAR string. Can be output from any "
                "pymatgen tool or Materials Project API."
            )
        )
    ],
    model: Annotated[
        Literal[
            "M3GNet-MP-2018.6.1-Eform",
            "MEGNet-MP-2018.6.1-Eform"
        ],
        Field(
            default="M3GNet-MP-2018.6.1-Eform",
            description=(
                "ML model to use for formation energy prediction. Options:\n"
                "- M3GNet-MP-2018.6.1-Eform (default, graph neural network, more accurate)\n"
                "- MEGNet-MP-2018.6.1-Eform (earlier model, faster but less accurate)"
            )
        )
    ] = "M3GNet-MP-2018.6.1-Eform",
) -> Dict[str, Any]:
    """
    Predict formation energy of a crystal structure using ML models.
    
    Predicts the formation energy (eV/atom) using pre-trained graph neural network
    models (M3GNet or MEGNet) trained on Materials Project DFT data. Returns the
    predicted formation energy which can be used for thermodynamic stability screening.
    
    Formation energy is the energy released when a compound forms from its constituent
    elements in their standard states. Negative values indicate exothermic formation
    (more stable), while positive values indicate endothermic formation (less stable).
    
    Common Use Cases:
        1. High-throughput screening: Predict formation energies for many candidates
        2. Stability filtering: Filter out candidates with high (unfavorable) Eform
        3. Ranking materials: Sort candidates by predicted thermodynamic stability
        4. Pre-DFT screening: Identify promising candidates before expensive calculations
    
    Model Selection:
        - M3GNet-MP-2018.6.1-Eform: More accurate, recommended for most cases
        - MEGNet-MP-2018.6.1-Eform: Faster predictions, good for very large screenings
    
    Typical Formation Energy Ranges:
        - Highly stable compounds: -3 to -1 eV/atom (e.g., oxides, nitrides)
        - Moderately stable: -1 to 0 eV/atom
        - Metastable/unstable: 0 to +1 eV/atom (may decompose)
        - Highly unstable: > +1 eV/atom (unlikely to exist)
    
    Args:
        input_structure: Structure as pymatgen dict, CIF, or POSCAR string
        model: ML model to use for prediction
    
    Returns:
        Dictionary containing:
            success                     (bool)      Whether prediction succeeded
            formation_energy_eV_per_atom (float)   Predicted formation energy (eV/atom)
            model_used                  (str)       Model name used for prediction
            formula                     (str)       Chemical formula of the structure
            num_sites                   (int)       Number of atoms in the structure
            total_formation_energy_eV   (float)     Total formation energy for the cell (eV)
            structure_info              (dict)      Basic info about the structure
            interpretation              (str)       Human-readable stability assessment
            error                       (str)       Error message if prediction failed
    """
    try:
        from pymatgen.core import Structure
        from pymatgen.io.cif import CifParser
        from pymatgen.io.vasp import Poscar
        import matgl
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import required libraries: {e}. "
                    f"Install with: pip install matgl pymatgen"
        }
    
    # Check if DGL is available (required for formation energy models)
    try:
        import dgl
    except Exception as e:
        return {
            "success": False,
            "error": f"DGL backend not available: {e}. "
                    f"Formation energy prediction requires DGL. "
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
        
        # Load the formation energy prediction model
        try:
            ml_model = matgl.load_model(model)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to load model '{model}': {e}. "
                        f"Check model name or network connection."
            }
        
        # Predict formation energy
        try:
            eform_tensor = ml_model.predict_structure(structure)
            eform_per_atom = float(eform_tensor.numpy())
        except Exception as e:
            return {
                "success": False,
                "error": f"Prediction failed: {e}. "
                        f"Structure may contain unsupported elements or be malformed."
            }
        
        # Calculate total formation energy for the cell
        total_eform = eform_per_atom * num_sites
        
        # Provide interpretation
        if eform_per_atom < -1.0:
            interpretation = "Highly stable (strongly exothermic formation)"
        elif eform_per_atom < -0.5:
            interpretation = "Stable (exothermic formation)"
        elif eform_per_atom < 0:
            interpretation = "Moderately stable (weakly exothermic formation)"
        elif eform_per_atom < 0.5:
            interpretation = "Metastable (weakly endothermic formation, may exist)"
        elif eform_per_atom < 1.0:
            interpretation = "Unstable (endothermic formation, unlikely to synthesize)"
        else:
            interpretation = "Highly unstable (strongly endothermic, very unlikely to exist)"
        
        # Build response
        response = {
            "success": True,
            "formation_energy_eV_per_atom": round(eform_per_atom, 6),
            "total_formation_energy_eV": round(total_eform, 6),
            "model_used": model,
            "formula": formula,
            "num_sites": num_sites,
            "structure_info": {
                "formula": formula,
                "num_sites": num_sites,
                "volume": round(structure.volume, 4),
                "density_g_per_cm3": round(structure.density, 4),
            },
            "interpretation": interpretation,
            "message": (
                f"Predicted formation energy for {formula}: {eform_per_atom:.4f} eV/atom. "
                f"{interpretation}."
            )
        }
        
        return response
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error during prediction: {str(e)}"
        }
