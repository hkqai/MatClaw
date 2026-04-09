"""
Tool for extracting structure-based features from materials for ML prediction.

Computes comprehensive structural descriptors including:
- Site statistics (coordination numbers, local environments)
- Packing efficiency and density metrics
- Bond lengths, bond angles, and bond type distributions
- Voronoi polyhedra analysis
- Radial distribution functions
- Symmetry features
- Structural complexity metrics

Uses Matminer's structure featurizers to generate ML-ready structural features.
These features complement composition features for property prediction models.
"""

from typing import Dict, Any, Optional, Union, Annotated, List
from pydantic import Field


def structure_analyzer(
    input_structure: Annotated[
        Union[Dict[str, Any], str],
        Field(
            description=(
                "Structure to analyze. Can be:\n"
                "- Pymatgen Structure dict (from Structure.as_dict())\n"
                "- CIF string\n"
                "- POSCAR string\n"
                "Can be output from pymatgen tools or Materials Project API."
            )
        )
    ],
    feature_set: Annotated[
        str,
        Field(
            default="standard",
            description=(
                "Set of features to compute:\n"
                "- 'basic': Essential features only (density, volume, basic coordination)\n"
                "- 'standard': Balanced set for most ML tasks (recommended)\n"
                "- 'extensive': All available structure descriptors (may be very slow)\n"
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
                "Examples: 'DensityFeatures', 'GlobalSymmetryFeatures', 'SiteStatsFingerprint'\n"
                "See matminer documentation for available structure featurizers."
            )
        )
    ] = None,
    compute_site_stats: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True, computes site-level statistics (coordination numbers, bond lengths, etc.).\n"
                "Uses CrystalNN for local environment analysis. May be slow for large structures.\n"
                "Default: True"
            )
        )
    ] = True,
    compute_rdf: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True, computes radial distribution function features.\n"
                "Captures information about atomic spacing and local structure.\n"
                "Default: True"
            )
        )
    ] = True,
    compute_bonding: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True, computes bond-based features (bond fractions, bond types).\n"
                "Analyzes bonding characteristics of the structure.\n"
                "Default: True"
            )
        )
    ] = True,
    site_stats_preset: Annotated[
        str,
        Field(
            default="CrystalNNFingerprint_ops",
            description=(
                "Preset for SiteStatsFingerprint featurizer.\n"
                "Options: 'CrystalNNFingerprint_ops', 'JmolNNFingerprint_ops', 'VoronoiFingerprint'\n"
                "Default: 'CrystalNNFingerprint_ops' (recommended for most materials)"
            )
        )
    ] = "CrystalNNFingerprint_ops",
    primitive: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, converts structure to primitive cell before analysis.\n"
                "Can reduce computation time for large supercells.\n"
                "Default: False"
            )
        )
    ] = False,
) -> Dict[str, Any]:
    """
    Extract structure-based features for ML prediction models.
    
    Analyzes the crystal structure of a material and computes comprehensive
    structural descriptors using matminer featurizers. These features capture
    geometric, topological, and bonding characteristics essential for
    property prediction tasks.
    
    Returns
    -------
    dict:
        success             (bool)  Whether feature extraction succeeded.
        formula             (str)   Chemical formula.
        n_sites             (int)   Number of sites in structure.
        volume              (float) Unit cell volume (Ų).
        density             (float) Density (g/cm³).
        features            (dict)  Computed structure features:
            basic_info          (dict)  Basic structural information.
            density_features    (dict)  Packing efficiency, volume/atom, etc.
            symmetry_features   (dict)  Space group, crystal system, etc.
            site_statistics     (dict)  Coordination numbers, bond stats (if computed).
            rdf_features        (dict)  Radial distribution function (if computed).
            bond_features       (dict)  Bond fractions and types (if computed).
            complexity          (dict)  Structural complexity metrics (if computed).
            other_features      (dict)  Additional featurizer outputs.
        feature_vector      (list)  Flattened numeric feature vector for ML.
        feature_names       (list)  Names corresponding to feature_vector values.
        metadata            (dict)  Metadata about feature extraction:
            feature_set         (str)   Feature set used.
            featurizers_used    (list)  Names of matminer featurizers applied.
            n_features          (int)   Total number of features extracted.
            primitive_used      (bool)  Whether primitive cell was used.
        message             (str)   Human-readable summary.
        warnings            (list)  Non-critical warnings (if any).
        error               (str)   Error message (if failed).
    """
    import numpy as np
    
    # Imports
    try:
        from pymatgen.core import Structure
        from pymatgen.io.cif import CifParser
        from pymatgen.io.vasp import Poscar
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import pymatgen: {e}. Install with: pip install pymatgen"
        }
    
    try:
        from matminer.featurizers.structure import (
            DensityFeatures,
            GlobalSymmetryFeatures,
            StructuralComplexity,
            SiteStatsFingerprint,
            RadialDistributionFunction,
            BondFractions,
        )
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import matminer: {e}. Install with: pip install matminer"
        }
    
    # # Fix pymatgen/matminer compatibility issue for cn_opt_params.yaml
    # Newer pymatgen moved the file from analysis/ to core/, but matminer still expects old location
    try:
        import os
        import shutil
        import pymatgen.core  # Use submodule to get __file__
        pymatgen_path = os.path.dirname(os.path.dirname(pymatgen.core.__file__))
        source_file = os.path.join(pymatgen_path, "core", "cn_opt_params.yaml")
        target_file = os.path.join(pymatgen_path, "analysis", "cn_opt_params.yaml")
        
        # Only copy if source exists and target doesn't
        if os.path.exists(source_file) and not os.path.exists(target_file):
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            shutil.copy2(source_file, target_file)
    except Exception:
        pass
    
    # Parse input structure
    try:
        if isinstance(input_structure, dict):
            structure = Structure.from_dict(input_structure)
        elif isinstance(input_structure, str):
            from io import StringIO
            if "data_" in input_structure or "_cell_length" in input_structure:
                parser = CifParser(StringIO(input_structure))
                structure = parser.get_structures()[0]
            else:
                poscar = Poscar.from_str(input_structure)
                structure = poscar.structure
        else:
            return {
                "success": False,
                "error": "input_structure must be a Structure dict, CIF string, or POSCAR string."
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse input structure: {e}"
        }
    
    # Convert to primitive if requested
    if primitive:
        try:
            sga = SpacegroupAnalyzer(structure)
            structure = sga.get_primitive_standard_structure()
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to convert to primitive structure: {e}"
            }
    
    # Basic structure info
    formula = structure.composition.reduced_formula
    n_sites = len(structure)
    volume = structure.volume
    density = structure.density
    
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
                if feat_name == "DensityFeatures":
                    featurizer_configs.append(("DensityFeatures", DensityFeatures()))
                elif feat_name == "GlobalSymmetryFeatures":
                    featurizer_configs.append(("GlobalSymmetryFeatures", GlobalSymmetryFeatures()))
                elif feat_name == "StructuralComplexity":
                    featurizer_configs.append(("StructuralComplexity", StructuralComplexity()))
                elif feat_name == "SiteStatsFingerprint":
                    if compute_site_stats:
                        featurizer_configs.append(("SiteStatsFingerprint", 
                                                   SiteStatsFingerprint.from_preset(site_stats_preset)))
                elif feat_name == "RadialDistributionFunction":
                    if compute_rdf:
                        featurizer_configs.append(("RadialDistributionFunction", 
                                                   RadialDistributionFunction()))
                elif feat_name == "BondFractions":
                    if compute_bonding:
                        featurizer_configs.append(("BondFractions", BondFractions()))
            except Exception as e:
                warnings.append(f"Could not initialize featurizer {feat_name}: {e}")
    
    elif feature_set == "basic":
        # Basic features only - fast computation
        featurizer_configs = [
            ("DensityFeatures", DensityFeatures()),
            ("GlobalSymmetryFeatures", GlobalSymmetryFeatures()),
        ]
    
    elif feature_set == "extensive":
        # All available features - comprehensive but slow
        featurizer_configs = [
            ("DensityFeatures", DensityFeatures()),
            ("GlobalSymmetryFeatures", GlobalSymmetryFeatures()),
            ("StructuralComplexity", StructuralComplexity()),
        ]
        if compute_site_stats:
            featurizer_configs.append(("SiteStatsFingerprint", 
                                      SiteStatsFingerprint.from_preset(site_stats_preset)))
        if compute_rdf:
            featurizer_configs.append(("RadialDistributionFunction", 
                                      RadialDistributionFunction()))
        if compute_bonding:
            featurizer_configs.append(("BondFractions", BondFractions()))
    
    else:  # "standard" (default)
        # Balanced feature set for most ML tasks
        featurizer_configs = [
            ("DensityFeatures", DensityFeatures()),
            ("GlobalSymmetryFeatures", GlobalSymmetryFeatures()),
        ]
        if compute_site_stats:
            featurizer_configs.append(("SiteStatsFingerprint", 
                                      SiteStatsFingerprint.from_preset(site_stats_preset)))
        if compute_rdf:
            featurizer_configs.append(("RadialDistributionFunction", 
                                      RadialDistributionFunction()))
    
    # Apply featurizers
    for feat_name, featurizer in featurizer_configs:
        try:
            # Featurize
            feat_values = featurizer.featurize(structure)
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
            "formula": formula,
            "n_sites": n_sites,
            "volume": volume,
            "density": density,
        },
        "density_features": features.get("densityfeatures", {}),
        "symmetry_features": features.get("globalsymmetryfeatures", {}),
        "site_statistics": features.get("sitestatsfingerprint", {}),
        "rdf_features": features.get("radialdistributionfunction", {}),
        "bond_features": features.get("bondfractions", {}),
        "complexity": features.get("structuralcomplexity", {}),
        "other_features": {k: v for k, v in features.items() 
                          if k not in ["densityfeatures", "globalsymmetryfeatures", 
                                      "sitestatsfingerprint", "radialdistributionfunction",
                                      "bondfractions", "structuralcomplexity"]},
    }
    
    # Remove empty categories
    organized_features = {k: v for k, v in organized_features.items() if v}
    
    # Metadata
    metadata = {
        "feature_set": feature_set,
        "featurizers_used": featurizers_used,
        "n_features": len(feature_vector),
        "primitive_used": primitive,
        "compute_site_stats": compute_site_stats,
        "compute_rdf": compute_rdf,
        "compute_bonding": compute_bonding,
    }
    
    # Build result
    result = {
        "success": True,
        "formula": formula,
        "n_sites": n_sites,
        "volume": round(volume, 4),
        "density": round(density, 4),
        "features": organized_features,
        "feature_vector": feature_vector,
        "feature_names": feature_names,
        "metadata": metadata,
        "message": f"Successfully extracted {len(feature_vector)} structure features from {formula}",
    }
    
    if warnings:
        result["warnings"] = warnings
    
    return result
