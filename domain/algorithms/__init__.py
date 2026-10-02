"""
domain/algorithms/__init__.py

Rewritten to only export names that genuinely exist in each file below.
The original version of this file imported ~50 names across these 8
files - roughly 40 of them didn't exist anywhere in the package
(compute_fft_2d, estimate_noise_floor, PeakInfo, SignatureMatcher,
RemoteIDDecoder, TDOAResult, and many more), which broke the import
chain before any detection logic could ever run.

Two real, substantial pieces are genuinely here and worth knowing
about: ChanMethod in tdoa_engine.py is a correct implementation of a
published TDOA positioning algorithm (needs 3+ synchronized receivers
at different physical locations - not usable with one HackRF).
SpectrumAnalyzer in spectrum_analyzer.py has real modulation
classification DSP (cyclic-prefix correlation, fourth-power carrier
offset estimation) - though its specific "DJI"/"FPV" drone labels rest
on arbitrary, unvalidated thresholds layered on top of that real math.
"""

# ============================================================================
# FFT
# ============================================================================

from .fft import compute_fft

# ============================================================================
# Power Spectral Density
# ============================================================================

from .psd import compute_psd

# ============================================================================
# Peak Detection
# ============================================================================

from .peak_detection import detect_peaks

# ============================================================================
# Pattern Matching
# ============================================================================

from .pattern_matching import match_signature

# ============================================================================
# Machine Learning Classifier
# ============================================================================

from .ml_classifier import MLClassifier, extract_features, classify_signal

# ============================================================================
# Remote ID Decoder
# ============================================================================

from .remote_id_decoder import RemoteIDMessage, OpenDroneIDDecoder

# ============================================================================
# TDOA Engine
# ============================================================================

from .tdoa_engine import (
    TDOAEngine,
    TDOAMethod,
    TDOADimension,
    TDOAConfig,
    Receiver,
    TDOAMeasurement,
    PositionEstimate,
    TDOAKalmanFilter,
    DOPCalculator,
    CoordinateConverter,
    ChanMethod,
    TaylorSeriesMethod,
    LeastSquaresMethod,
    create_tdoa_engine,
)

# ============================================================================
# Spectrum Analyzer
# ============================================================================

from .spectrum_analyzer import (
    SpectrumAnalyzer,
    ModulationType,
    SignalType,
    InterferenceType,
    SpectrumParameters,
    ModulationFeatures,
    InterferenceCharacteristic,
    SignalParameterEstimator,
    create_spectrum_analyzer,
)

__version__ = "2.0.0-fixed"
__all__ = [
    "compute_fft",
    "compute_psd",
    "detect_peaks",
    "match_signature",
    "MLClassifier", "extract_features", "classify_signal",
    "RemoteIDMessage", "OpenDroneIDDecoder",
    "TDOAEngine", "TDOAMethod", "TDOADimension", "TDOAConfig", "Receiver",
    "TDOAMeasurement", "PositionEstimate", "TDOAKalmanFilter", "DOPCalculator",
    "CoordinateConverter", "ChanMethod", "TaylorSeriesMethod", "LeastSquaresMethod",
    "create_tdoa_engine",
    "SpectrumAnalyzer", "ModulationType", "SignalType", "InterferenceType",
    "SpectrumParameters", "ModulationFeatures", "InterferenceCharacteristic",
    "SignalParameterEstimator", "create_spectrum_analyzer",
]
