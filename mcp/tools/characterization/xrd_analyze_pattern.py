"""
XRD pattern analysis tool using autoXRD (XRD-AutoAnalyzer).

Automated phase identification from powder X-ray diffraction patterns using a
probabilistic deep learning model trained with physics-informed data augmentation.

Given an experimental XRD pattern (.xy format), this tool:
1. Loads a pre-trained CNN model for the relevant chemical space
2. Identifies phases present in the pattern with confidence scores
3. Optionally performs automated Rietveld refinement for weight fractions
4. Returns results in ARROWS-compatible format (formula_spacegroup notation)

This tool is designed to close the experimental characterization loop in active
learning workflows, particularly with ARROWS (arrows_record_result expects the
exact output format produced here).

Based on: https://github.com/njszym/XRD-AutoAnalyzer
Publications:
  - Chem. Mater. 2021: https://doi.org/10.1021/acs.chemmater.1c01071
  - npj Comput. Mater. 2024: https://doi.org/10.1038/s41524-024-01230-9
"""

from typing import Dict, Any, List, Optional, Annotated
from pydantic import Field
import os


def xrd_analyze_pattern(
    spectrum_path: Annotated[
        str,
        Field(
            description=(
                "Path to the XRD pattern file in .xy format (two-column ASCII data: "
                "2θ angle in degrees, intensity). Can be absolute or relative to the "
                "current working directory. Example: './Spectra/sample_001.xy'"
            )
        )
    ],
    model_path: Annotated[
        str,
        Field(
            description=(
                "Path to the trained model file or directory. Can be:\n"
                "  - Single model: 'Model.h5' (XRD-only analysis)\n"
                "  - Dual models: 'Models/' directory containing 'XRD_Model.h5' and "
                "'PDF_Model.h5' (combined XRD+PDF analysis, more accurate)\n"
                "  - Custom path to any .h5 model file\n"
                "Models are trained for specific chemical spaces using construct_xrd_model.py."
            )
        )
    ],
    min_confidence: Annotated[
        float,
        Field(
            default=40.0,
            ge=0.0,
            le=100.0,
            description=(
                "Minimum confidence threshold (0-100%) for reporting a phase. "
                "Phases with confidence below this value are excluded from results. "
                "Lower values may include spurious phases; higher values may miss "
                "minor phases. Default: 40.0 (calibrated from published benchmarks)."
            )
        )
    ] = 40.0,
    calculate_weights: Annotated[
        bool,
        Field(
            description=(
                "If True, perform automated Rietveld refinement to determine weight "
                "fractions of identified phases. Refinement uses CIF reference files "
                "from the model's References/ directory. Adds ~5-10 seconds per pattern. "
                "Default: True (required for ARROWS integration)."
            )
        )
    ] = True,
    wavelength: Annotated[
        float,
        Field(
            default=1.5406,
            gt=0.0,
            le=3.0,
            description=(
                "X-ray wavelength in ångströms. Default: 1.5406 (Cu Kα). "
                "Patterns collected with other radiation sources will be converted "
                "to Cu Kα equivalent before analysis. Common values:\n"
                "  - Cu Kα: 1.5406 Å (most common)\n"
                "  - Mo Kα: 0.7107 Å\n"
                "  - Co Kα: 1.7889 Å"
            )
        )
    ] = 1.5406,
    min_angle: Annotated[
        float,
        Field(
            default=10.0,
            ge=5.0,
            le=80.0,
            description=(
                "Minimum 2θ angle (degrees, Cu Kα equivalent) of the scan range. "
                "Must match the range used during model training. Default: 10.0°"
            )
        )
    ] = 10.0,
    max_angle: Annotated[
        float,
        Field(
            default=80.0,
            ge=20.0,
            le=150.0,
            description=(
                "Maximum 2θ angle (degrees, Cu Kα equivalent) of the scan range. "
                "Must match the range used during model training. Default: 80.0°"
            )
        )
    ] = 80.0,
    max_phases: Annotated[
        int,
        Field(
            default=3,
            ge=1,
            le=10,
            description=(
                "Maximum number of phases to identify in multi-phase patterns. "
                "Algorithm stops when either this limit is reached or all peaks above "
                "cutoff_intensity are assigned. Default: 3."
            )
        )
    ] = 3,
    cutoff_intensity: Annotated[
        float,
        Field(
            default=5.0,
            ge=0.0,
            le=50.0,
            description=(
                "Minimum peak intensity (% of maximum) to consider during phase "
                "identification. Peaks below this threshold are ignored. Lower values "
                "increase sensitivity to minor phases but may add noise. Default: 5.0%"
            )
        )
    ] = 5.0,
    use_pdf: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True and dual models are available (XRD_Model.h5 + PDF_Model.h5 in "
                "Models/ directory), combine predictions from both XRD and virtual PDF "
                "analysis for improved accuracy. Requires PDF model to be pre-trained. "
                "Default: False (XRD-only)."
            )
        )
    ] = False,
    unknown_threshold: Annotated[
        float,
        Field(
            default=25.0,
            ge=0.0,
            le=100.0,
            description=(
                "Threshold (% of initial maximum intensity) for warning about unidentified "
                "peaks. If residual peaks exceed this value after all phases are assigned, "
                "a warning is issued. Default: 25.0%"
            )
        )
    ] = 25.0,
    references_dir: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "Optional path to the References/ directory containing CIF files for "
                "all phases in the model's training set. If None, assumes References/ "
                "exists in the same directory as the model. Required for weight fraction "
                "calculation."
            )
        )
    ] = None,
) -> Dict[str, Any]:
    """
    Analyze XRD pattern to identify phases and quantify weight fractions.

    Returns results in ARROWS-compatible format for seamless integration with
    active learning workflows (arrows_record_result).

    Returns
    -------
    dict:
        success             (bool)   Whether analysis succeeded.
        spectrum_file       (str)    Input filename (basename only).
        num_phases          (int)    Number of phases identified.
        phases              (list)   Phase labels in formula_spacegroup format
                                     (e.g., ['BaTiO3_99', 'BaO_225']).
        confidence          (list)   Confidence scores (%) for each phase.
        weight_fractions    (list)   Weight fractions (0-1, sums to ~1.0) from
                                     Rietveld refinement. Only present if
                                     calculate_weights=True and refinement succeeds.
        arrows_ready        (bool)   True if output can be passed directly to
                                     arrows_record_result (requires phases and
                                     weight_fractions to be valid).
        unknown_peaks       (dict)   Info about unidentified peaks, if any:
            present             (bool)   Whether unknown peaks were detected.
            max_intensity_pct   (float)  Maximum intensity (%) of unknown peaks.
            warning             (str)    Warning message if above threshold.
        metadata            (dict)   Analysis parameters and diagnostics.
        message             (str)    Human-readable summary.
        warnings            (list)   Non-fatal issues encountered.
        error               (str)    Error message (only if success=False).
    """

    warnings: List[str] = []

    # ------------------------------------------------------------------
    # 1. Validate inputs
    # ------------------------------------------------------------------
    if min_angle >= max_angle:
        return {
            "success": False,
            "error": f"min_angle ({min_angle}) must be less than max_angle ({max_angle})."
        }

    spectrum_abs = os.path.abspath(spectrum_path)
    if not os.path.isfile(spectrum_abs):
        return {
            "success": False,
            "spectrum_file": os.path.basename(spectrum_path),
            "error": f"Spectrum file not found: {spectrum_abs}"
        }

    model_abs = os.path.abspath(model_path)
    if not (os.path.isfile(model_abs) or os.path.isdir(model_abs)):
        return {
            "success": False,
            "error": f"Model path not found: {model_abs}"
        }

    # Determine model type (single or dual)
    is_dual_model = False
    xrd_model_file = None
    pdf_model_file = None

    if os.path.isdir(model_abs):
        # Check for dual model directory
        xrd_model_candidate = os.path.join(model_abs, "XRD_Model.h5")
        pdf_model_candidate = os.path.join(model_abs, "PDF_Model.h5")
        if os.path.isfile(xrd_model_candidate):
            is_dual_model = True
            xrd_model_file = xrd_model_candidate
            if os.path.isfile(pdf_model_candidate):
                pdf_model_file = pdf_model_candidate
            else:
                if use_pdf:
                    warnings.append(
                        "PDF model requested but PDF_Model.h5 not found in Models/. "
                        "Falling back to XRD-only analysis."
                    )
                    use_pdf = False
        else:
            # Try single Model.h5 in directory
            single_model_candidate = os.path.join(model_abs, "Model.h5")
            if os.path.isfile(single_model_candidate):
                xrd_model_file = single_model_candidate
            else:
                return {
                    "success": False,
                    "error": f"No valid model files found in directory: {model_abs}"
                }
    else:
        # Single model file
        if not model_abs.endswith(".h5"):
            warnings.append(
                f"Model file {os.path.basename(model_abs)} does not have .h5 extension. "
                "Proceeding anyway..."
            )
        xrd_model_file = model_abs

    # Determine References directory
    if references_dir is not None:
        refs_abs = os.path.abspath(references_dir)
    elif os.path.isdir(model_abs):
        refs_abs = os.path.join(model_abs, "References")
    else:
        refs_abs = os.path.join(os.path.dirname(model_abs), "References")

    if calculate_weights and not os.path.isdir(refs_abs):
        warnings.append(
            f"References directory not found at {refs_abs}. Weight fraction "
            "calculation will be skipped."
        )
        calculate_weights = False

    # ------------------------------------------------------------------
    # 2. Load spectrum
    # ------------------------------------------------------------------
    try:
        import numpy as np

        spectrum_data = np.loadtxt(spectrum_abs)
        if spectrum_data.ndim != 2 or spectrum_data.shape[1] != 2:
            return {
                "success": False,
                "spectrum_file": os.path.basename(spectrum_path),
                "error": (
                    "Spectrum file must be two-column ASCII (2θ, intensity). "
                    f"Got shape: {spectrum_data.shape}"
                )
            }
        angles = spectrum_data[:, 0]
        intensities = spectrum_data[:, 1]

        if len(angles) < 10:
            return {
                "success": False,
                "spectrum_file": os.path.basename(spectrum_path),
                "error": f"Spectrum has too few data points ({len(angles)}). Need at least 10."
            }

    except ImportError:
        return {
            "success": False,
            "error": "numpy is required for XRD analysis. Install with: pip install numpy"
        }
    except Exception as e:
        return {
            "success": False,
            "spectrum_file": os.path.basename(spectrum_path),
            "error": f"Failed to load spectrum: {e}"
        }

    # ------------------------------------------------------------------
    # 3. Import and configure autoXRD
    # ------------------------------------------------------------------
    try:
        # autoXRD uses TensorFlow/Keras backend
        # Suppress TF warnings for cleaner output
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
        
        from autoXRD.spectrum_analysis import SpectrumAnalyzer
        from autoXRD.quantifier import main as quantifier_main
        import tensorflow as tf
        
        autoXRD_available = True

    except ImportError as e:
        # Package not available - return error
        return {
            "success": False,
            "error": (
                f"autoXRD package is not installed. Error: {e}\n"
                "Install with: pip install autoXRD"
            )
        }

    # ------------------------------------------------------------------
    # 4. Run phase identification
    # ------------------------------------------------------------------
    try:
        # Convert wavelength to autoXRD format
        if wavelength == 1.5406:
            wavelen = 'CuKa'
        else:
            wavelen = float(wavelength)
        
        # Get spectrum directory and filename
        spectra_dir = os.path.dirname(spectrum_abs)
        spectrum_fname = os.path.basename(spectrum_abs)
        
        # Initialize analyzer
        analyzer = SpectrumAnalyzer(
            spectra_dir=spectra_dir,
            spectrum_fname=spectrum_fname,
            max_phases=max_phases,
            cutoff_intensity=cutoff_intensity,
            min_conf=min_confidence,
            wavelen=wavelen,
            reference_dir=refs_abs if os.path.isdir(refs_abs) else os.path.dirname(refs_abs),
            min_angle=min_angle,
            max_angle=max_angle,
            model_path=xrd_model_file,
            is_pdf=use_pdf and pdf_model_file is not None
        )
        
        # Run phase identification
        prediction_list, confidence_list, backup_list, scale_list, spec_list = analyzer.suspected_mixtures
        
        # Check if any phases were identified
        if len(prediction_list) == 0 or (len(prediction_list) > 0 and len(prediction_list[0]) == 0):
            return {
                "success": True,
                "spectrum_file": spectrum_fname,
                "num_phases": 0,
                "phases": [],
                "confidence": [],
                "arrows_ready": False,
                "unknown_peaks": {
                    "present": True,
                    "max_intensity_pct": 100.0,
                    "warning": "No phases identified above confidence threshold."
                },
                "metadata": {
                    "model_used": xrd_model_file,
                    "min_confidence": min_confidence,
                    "cutoff_intensity": cutoff_intensity,
                    "wavelength": wavelength,
                    "angle_range": [min_angle, max_angle]
                },
                "message": f"No phases identified in {spectrum_fname} above {min_confidence}% confidence.",
                "warnings": warnings
            }
        
        # Take the first (most confident) mixture
        predicted_phases_raw = prediction_list[0]  # List of CIF filenames
        confidences = confidence_list[0]  # List of confidence scores
        scale_factors = scale_list[0] if len(scale_list) > 0 else None
        
    except Exception as e:
        return {
            "success": False,
            "spectrum_file": os.path.basename(spectrum_path),
            "error": f"Phase identification failed: {e}",
            "warnings": warnings
        }

    # ------------------------------------------------------------------
    # 5. Perform weight fraction calculation (if requested)
    # ------------------------------------------------------------------
    weight_fractions = None
    refinement_quality = None
    
    if calculate_weights and len(predicted_phases_raw) > 0:
        try:
            # Call quantifier to get weight fractions
            weight_fractions = quantifier_main(
                spectra_directory=spectra_dir,
                spectrum_fname=spectrum_fname,
                predicted_phases=predicted_phases_raw,
                scale_factors=scale_factors,
                min_angle=min_angle,
                max_angle=max_angle,
                wavelength=wavelen,
                rietveld=True  # Use Rietveld refinement for better accuracy
            )
            
        except Exception as e:
            warnings.append(
                f"Weight fraction calculation failed: {e}. "
                "Results will not include weight_fractions."
            )
            weight_fractions = None

    # ------------------------------------------------------------------
    # 6. Format phases for ARROWS compatibility
    # ------------------------------------------------------------------
    # autoXRD returns phases as CIF filenames (e.g., "BaTiO3_99.cif")
    # ARROWS expects formula_spacegroup format (e.g., "BaTiO3_99")
    phases_formatted = []
    for phase in predicted_phases_raw:
        # Remove .cif extension if present
        if phase.endswith('.cif'):
            phase_name = phase[:-4]
        else:
            phase_name = phase
        phases_formatted.append(phase_name)

    # ------------------------------------------------------------------
    # 7. Check for unknown peaks
    # ------------------------------------------------------------------
    # Analyze residual spectrum to detect unidentified peaks
    unknown_info = {
        "present": False,
        "max_intensity_pct": 0.0
    }
    
    # If we have residual spectra from the analysis
    if len(spec_list) > 0 and len(spec_list[0]) > 0:
        try:
            # Get the final residual spectrum after all phases subtracted
            final_residual = spec_list[0][-1]
            max_residual = float(np.max(final_residual))
            
            unknown_info["max_intensity_pct"] = max_residual
            
            if max_residual > unknown_threshold:
                unknown_info["present"] = True
                unknown_info["warning"] = (
                    f"Unidentified peaks with max intensity {max_residual:.1f}% detected. "
                    "Consider: (1) adding more phases to model training set, "
                    "(2) lowering min_confidence threshold, or "
                    "(3) increasing max_phases limit."
                )
                warnings.append(unknown_info["warning"])
            
        except Exception:
            # If residual analysis fails, skip it
            pass

    # ------------------------------------------------------------------
    # 8. Format final output
    # ------------------------------------------------------------------
    # Determine if output is ready for ARROWS
    arrows_ready = (
        len(phases_formatted) > 0 and 
        weight_fractions is not None and 
        len(weight_fractions) == len(phases_formatted)
    )
    
    result = {
        "success": True,
        "spectrum_file": spectrum_fname,
        "num_phases": len(phases_formatted),
        "phases": phases_formatted,
        "confidence": [float(c) for c in confidences],
        "arrows_ready": arrows_ready,
        "unknown_peaks": unknown_info,
        "metadata": {
            "model_used": xrd_model_file,
            "pdf_model_used": pdf_model_file if use_pdf else None,
            "min_confidence": min_confidence,
            "cutoff_intensity": cutoff_intensity,
            "wavelength": wavelength,
            "angle_range": [min_angle, max_angle],
            "calculate_weights": calculate_weights,
            "use_pdf": use_pdf
        },
        "message": f"Identified {len(phases_formatted)} phase(s) in {spectrum_fname}"
    }
    
    # Add weight fractions if calculated
    if weight_fractions is not None:
        result["weight_fractions"] = [float(w) for w in weight_fractions]
        result["message"] += f" with weight fractions: {[f'{w:.3f}' for w in weight_fractions]}"
    
    # Add warnings if any
    if warnings:
        result["warnings"] = warnings
    
    return result
