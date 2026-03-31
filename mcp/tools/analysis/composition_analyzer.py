"""
Tool for extracting composition-based features from materials for ML prediction.

Computes comprehensive composition descriptors including:
- Elemental fractions and stoichiometry
- Average/weighted elemental properties (mass, radius, electronegativity, etc.)
- Statistical aggregations (mean, std, min, max, range)
- Oxidation state analysis
- Chemical family and group distributions

Uses Matminer's composition featurizers to generate ML-ready features.
These features are essential inputs for property prediction models.
"""

from typing import Dict, Any, Optional, Union, Annotated, List
from pydantic import Field


def composition_analyzer(
    input_structure: Annotated[
        Union[Dict[str, Any], str],
        Field(
            description=(
                "Structure or composition to analyze. Can be:\n"
                "- Pymatgen Structure dict (from Structure.as_dict())\n"
                "- Pymatgen Composition dict (from Composition.as_dict())\n"
                "- Composition string (e.g., 'Fe2O3', 'LiCoO2')\n"
                "- CIF/POSCAR string (composition will be extracted)"
            )
        )
    ],
    feature_set: Annotated[
        str,
        Field(
            default="standard",
            description=(
                "Set of features to compute:\n"
                "- 'basic': Essential features only (elemental fractions, avg properties)\n"
                "- 'standard': Balanced set for most ML tasks (recommended)\n"
                "- 'extensive': All available composition descriptors (may be slow)\n"
                "- 'custom': Use custom_features parameter to specify individual featurizers\n"
                "Default: 'standard'"
            )
        )
    ] = "standard",
    custom_features: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description=(
                "List of specific matminer featurizer names to use (only if feature_set='custom').\n"
                "Examples: 'ElementProperty', 'Stoichiometry', 'ValenceOrbital', 'IonProperty'\n"
                "See matminer documentation for available featurizers."
            )
        )
    ] = None,
    include_oxidation_features: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True, attempts to assign oxidation states and compute oxidation-based features.\n"
                "Includes ionic character, oxidation state statistics, etc.\n"
                "Default: True"
            )
        )
    ] = True,
    element_properties: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description=(
                "Specific elemental properties to compute statistics for.\n"
                "If None, uses a standard set: ['Number', 'AtomicWeight', 'MeltingT', 'Column', \n"
                "'Row', 'Electronegativity', 'CovalentRadius', 'AtomicRadius', 'FirstIonizationEnergy'].\n"
                "Available properties depend on matminer's ElementProperty featurizer."
            )
        )
    ] = None,
    stats: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description=(
                "Statistical aggregations to compute for elemental properties.\n"
                "If None, uses: ['mean', 'std_dev', 'range', 'minimum', 'maximum'].\n"
                "Options: 'mean', 'avg_dev', 'std_dev', 'minimum', 'maximum', 'range', 'mode'"
            )
        )
    ] = None,
) -> Dict[str, Any]:
    """
    Extract composition-based features for ML prediction models.
    
    Analyzes the chemical composition of a material and computes comprehensive
    descriptors using matminer featurizers. These features capture elemental
    properties, stoichiometry, and chemical characteristics essential for
    property prediction tasks.
    
    Returns
    -------
    dict:
        success             (bool)  Whether feature extraction succeeded.
        composition         (str)   Reduced composition formula.
        n_elements          (int)   Number of distinct elements.
        element_list        (list)  Elements present in composition.
        elemental_fractions (dict)  Fractional amounts of each element.
        features            (dict)  Computed composition features:
            basic_info          (dict)  Basic composition statistics.
            element_stats       (dict)  Statistical aggregations of elemental properties.
            stoichiometry       (dict)  Stoichiometry-based features (if computed).
            oxidation_states    (dict)  Oxidation state features (if computed).
            band_center         (dict)  Electronic structure features (if computed).
            other_features      (dict)  Additional featurizer outputs.
        feature_vector      (list)  Flattened numeric feature vector for ML.
        feature_names       (list)  Names corresponding to feature_vector values.
        metadata            (dict)  Metadata about feature extraction:
            feature_set         (str)   Feature set used.
            featurizers_used    (list)  Names of matminer featurizers applied.
            n_features          (int)   Total number of features extracted.
        message             (str)   Human-readable summary.
        warnings            (list)  Non-critical warnings (if any).
        error               (str)   Error message (if failed).
    """
    try:
        from pymatgen.core import Composition, Structure
        from pymatgen.io.cif import CifParser
        from pymatgen.io.vasp import Poscar
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import pymatgen: {e}. Install with: pip install pymatgen"
        }
    
    try:
        from matminer.featurizers.composition import (
            ElementProperty,
            Stoichiometry,
            ValenceOrbital,
            IonProperty,
            OxidationStates,
            BandCenter,
            ElectronAffinity,
            ElectronegativityDiff,
            AtomicOrbitals,
        )
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import matminer: {e}. Install with: pip install matminer"
        }
    
    # Parse input to get Composition
    try:
        composition = None
        
        if isinstance(input_structure, dict):
            # Check if it's a Structure dict or Composition dict
            if "@module" in input_structure:
                module = input_structure.get("@module", "")
                if "Structure" in module:
                    structure = Structure.from_dict(input_structure)
                    composition = structure.composition
                elif "Composition" in module:
                    composition = Composition.from_dict(input_structure)
                else:
                    # Try both
                    try:
                        structure = Structure.from_dict(input_structure)
                        composition = structure.composition
                    except:
                        composition = Composition.from_dict(input_structure)
            else:
                # Assume it's a Structure dict
                structure = Structure.from_dict(input_structure)
                composition = structure.composition
                
        elif isinstance(input_structure, str):
            # Try to parse as formula first
            try:
                composition = Composition(input_structure)
            except:
                # Try CIF or POSCAR
                from io import StringIO
                if "data_" in input_structure or "_cell_length" in input_structure:
                    parser = CifParser(StringIO(input_structure))
                    structure = parser.get_structures()[0]
                    composition = structure.composition
                else:
                    poscar = Poscar.from_str(input_structure)
                    composition = poscar.structure.composition
        else:
            return {
                "success": False,
                "error": "input_structure must be a Structure dict, Composition dict, composition string, CIF, or POSCAR."
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse input: {e}"
        }
    
    if composition is None:
        return {
            "success": False,
            "error": "Could not extract composition from input"
        }
    
    # Basic composition info
    reduced_formula = composition.reduced_formula
    element_list = [str(el) for el in composition.elements]
    n_elements = len(element_list)
    elemental_fractions = {str(el): composition.get_atomic_fraction(el) for el in composition.elements}
    
    # Initialize results
    warnings = []
    features = {}
    feature_vector = []
    feature_names = []
    featurizers_used = []
    
    # Determine which featurizers to use
    featurizer_configs = []
    
    if feature_set == "custom" and custom_features:
        # Use custom featurizers
        for feat_name in custom_features:
            try:
                if feat_name == "ElementProperty":
                    props = element_properties or [
                        'Number', 'AtomicWeight', 'MeltingT', 'Column', 'Row',
                        'Electronegativity', 'CovalentRadius', 'AtomicRadius',
                        'FirstIonizationEnergy'
                    ]
                    stat_list = stats or ['mean', 'std_dev', 'range', 'minimum', 'maximum']
                    featurizer_configs.append(("ElementProperty", ElementProperty.from_preset("magpie")))
                elif feat_name == "Stoichiometry":
                    featurizer_configs.append(("Stoichiometry", Stoichiometry()))
                elif feat_name == "ValenceOrbital":
                    featurizer_configs.append(("ValenceOrbital", ValenceOrbital()))
                elif feat_name == "IonProperty":
                    featurizer_configs.append(("IonProperty", IonProperty()))
                elif feat_name == "OxidationStates":
                    featurizer_configs.append(("OxidationStates", OxidationStates()))
                elif feat_name == "BandCenter":
                    featurizer_configs.append(("BandCenter", BandCenter()))
                elif feat_name == "ElectronAffinity":
                    featurizer_configs.append(("ElectronAffinity", ElectronAffinity()))
                elif feat_name == "ElectronegativityDiff":
                    featurizer_configs.append(("ElectronegativityDiff", ElectronegativityDiff()))
                elif feat_name == "AtomicOrbitals":
                    featurizer_configs.append(("AtomicOrbitals", AtomicOrbitals()))
            except Exception as e:
                warnings.append(f"Could not initialize featurizer {feat_name}: {e}")
    
    elif feature_set == "basic":
        # Basic features only
        featurizer_configs = [
            ("ElementProperty", ElementProperty.from_preset("magpie")),
            ("Stoichiometry", Stoichiometry()),
        ]
    
    elif feature_set == "extensive":
        # All available features
        featurizer_configs = [
            ("ElementProperty", ElementProperty.from_preset("magpie")),
            ("Stoichiometry", Stoichiometry()),
            ("ValenceOrbital", ValenceOrbital()),
            ("BandCenter", BandCenter()),
            ("ElectronAffinity", ElectronAffinity()),
            ("ElectronegativityDiff", ElectronegativityDiff()),
            ("AtomicOrbitals", AtomicOrbitals()),
        ]
        if include_oxidation_features:
            featurizer_configs.extend([
                ("IonProperty", IonProperty()),
                ("OxidationStates", OxidationStates()),
            ])
    
    else:  # "standard" (default)
        # Balanced feature set for most ML tasks
        featurizer_configs = [
            ("ElementProperty", ElementProperty.from_preset("magpie")),
            ("Stoichiometry", Stoichiometry()),
            ("ValenceOrbital", ValenceOrbital()),
            ("BandCenter", BandCenter()),
        ]
        if include_oxidation_features:
            featurizer_configs.append(("OxidationStates", OxidationStates()))
    
    # Apply featurizers
    for feat_name, featurizer in featurizer_configs:
        try:
            # Handle oxidation state requirements
            comp_to_use = composition
            if feat_name in ["IonProperty", "OxidationStates"] and include_oxidation_features:
                # Try to add oxidation states
                try:
                    comp_to_use = composition.add_charges_from_oxi_state_guesses()
                except Exception as e:
                    warnings.append(f"Could not assign oxidation states for {feat_name}: {e}")
                    continue
            
            # Featurize
            feat_values = featurizer.featurize(comp_to_use)
            feat_labels = featurizer.feature_labels()
            
            # Store in features dict
            features[feat_name.lower()] = dict(zip(feat_labels, feat_values))
            
            # Add to feature vector
            feature_vector.extend(feat_values)
            feature_names.extend(feat_labels)
            featurizers_used.append(feat_name)
            
        except Exception as e:
            warnings.append(f"Featurizer {feat_name} failed: {e}")
    
    # Organize features into categories
    organized_features = {
        "basic_info": {
            "n_elements": n_elements,
            "element_list": element_list,
            "elemental_fractions": elemental_fractions,
            "reduced_formula": reduced_formula,
        },
        "element_stats": features.get("elementproperty", {}),
        "stoichiometry": features.get("stoichiometry", {}),
        "oxidation_states": features.get("oxidationstates", {}),
        "band_center": features.get("bandcenter", {}),
        "valence_orbital": features.get("valenceorbital", {}),
        "other_features": {k: v for k, v in features.items() 
                          if k not in ["elementproperty", "stoichiometry", "oxidationstates", 
                                      "bandcenter", "valenceorbital"]},
    }
    
    # Remove empty categories
    organized_features = {k: v for k, v in organized_features.items() if v}
    
    # Metadata
    metadata = {
        "feature_set": feature_set,
        "featurizers_used": featurizers_used,
        "n_features": len(feature_vector),
        "include_oxidation_features": include_oxidation_features,
    }
    
    # Build result
    result = {
        "success": True,
        "composition": reduced_formula,
        "n_elements": n_elements,
        "element_list": element_list,
        "elemental_fractions": elemental_fractions,
        "features": organized_features,
        "feature_vector": feature_vector,
        "feature_names": feature_names,
        "metadata": metadata,
        "message": f"Successfully extracted {len(feature_vector)} composition features from {reduced_formula}",
    }
    
    if warnings:
        result["warnings"] = warnings
    
    return result
