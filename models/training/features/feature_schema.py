#!/usr/bin/env python3
"""
Feature Schema Definition for Drone Detection

This module defines the complete feature schema for drone classification,
including feature names, types, descriptions, validation rules, and
preprocessing requirements.

Features are organized into categories:
1. Spectral Features (20) - Frequency domain characteristics
2. Cyclostationary Features (8) - Periodic patterns in signals
3. Statistical Features (10) - Statistical properties of IQ samples
4. Modulation Features (8) - Modulation-specific parameters
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import numpy as np


# ============================================================================
# Enums
# ============================================================================

class FeatureType(Enum):
    """Feature data types"""
    CONTINUOUS = "continuous"
    DISCRETE = "discrete"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"


class FeatureCategory(Enum):
    """Feature categories"""
    SPECTRAL = "spectral"
    CYCLOSTATIONARY = "cyclostationary"
    STATISTICAL = "statistical"
    MODULATION = "modulation"


class NormalizationMethod(Enum):
    """Feature normalization methods"""
    MIN_MAX = "min_max"
    Z_SCORE = "z_score"
    ROBUST = "robust"
    LOG = "log"
    NONE = "none"


# ============================================================================
# Feature Definition Classes
# ============================================================================

@dataclass
class FeatureDefinition:
    """Definition of a single feature"""
    name: str
    display_name: str
    description: str
    category: FeatureCategory
    feature_type: FeatureType
    unit: str
    data_range: Tuple[float, float]
    typical_range: Tuple[float, float]
    normalization: NormalizationMethod
    importance: float = 0.0
    required: bool = True
    example_value: Any = None
    validation_fn: Optional[str] = None
    
    def validate(self, value: float) -> bool:
        """Validate feature value against range"""
        if value < self.data_range[0] or value > self.data_range[1]:
            return False
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'category': self.category.value,
            'type': self.feature_type.value,
            'unit': self.unit,
            'min_value': self.data_range[0],
            'max_value': self.data_range[1],
            'typical_min': self.typical_range[0],
            'typical_max': self.typical_range[1],
            'normalization': self.normalization.value,
            'importance': self.importance,
            'required': self.required,
            'example': self.example_value
        }


@dataclass
class FeatureGroup:
    """Group of related features"""
    name: str
    display_name: str
    description: str
    category: FeatureCategory
    features: List[FeatureDefinition]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'category': self.category.value,
            'feature_count': len(self.features),
            'features': [f.to_dict() for f in self.features]
        }


# ============================================================================
# Feature Definitions
# ============================================================================

# ============================================================================
# Spectral Features (20 features)
# ============================================================================

SPECTRAL_FEATURES = [
    FeatureDefinition(
        name="peak_freq",
        display_name="Peak Frequency",
        description="Frequency of the maximum power peak in the spectrum",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="Hz",
        data_range=(0, 6e9),
        typical_range=(2.4e9, 5.8e9),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0987,
        example_value=2.44e9
    ),
    FeatureDefinition(
        name="peak_magnitude",
        display_name="Peak Magnitude",
        description="Power level at the peak frequency in dBm",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="dBm",
        data_range=(-120, 0),
        typical_range=(-80, -30),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.1245,
        example_value=-45.5
    ),
    FeatureDefinition(
        name="peak_width",
        display_name="Peak Width",
        description="Width of the spectral peak at half maximum",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="Hz",
        data_range=(0, 50e6),
        typical_range=(100e3, 20e6),
        normalization=NormalizationMethod.LOG,
        importance=0.0189,
        example_value=1.2e6
    ),
    FeatureDefinition(
        name="peak_prominence",
        display_name="Peak Prominence",
        description="How much the peak stands out from the surrounding baseline",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="dB",
        data_range=(0, 80),
        typical_range=(3, 30),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0354,
        example_value=15.2
    ),
    FeatureDefinition(
        name="power_spectral_density_mean",
        display_name="PSD Mean",
        description="Mean of the power spectral density",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="dBm/Hz",
        data_range=(-150, -50),
        typical_range=(-120, -70),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0321,
        example_value=-85.3
    ),
    FeatureDefinition(
        name="power_spectral_density_std",
        display_name="PSD Standard Deviation",
        description="Standard deviation of the power spectral density",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="dB",
        data_range=(0, 50),
        typical_range=(5, 25),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0654,
        example_value=12.7
    ),
    FeatureDefinition(
        name="power_spectral_density_skew",
        display_name="PSD Skewness",
        description="Skewness of the power spectral density distribution",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="unitless",
        data_range=(-5, 5),
        typical_range=(-1, 1),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0077,
        example_value=0.25
    ),
    FeatureDefinition(
        name="power_spectral_density_kurtosis",
        display_name="PSD Kurtosis",
        description="Kurtosis of the power spectral density distribution",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="unitless",
        data_range=(-2, 10),
        typical_range=(0, 5),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0022,
        example_value=3.2
    ),
    FeatureDefinition(
        name="bandwidth_3db",
        display_name="3 dB Bandwidth",
        description="Bandwidth at 3 dB below peak",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="Hz",
        data_range=(0, 50e6),
        typical_range=(100e3, 15e6),
        normalization=NormalizationMethod.LOG,
        importance=0.0254,
        example_value=2.5e6
    ),
    FeatureDefinition(
        name="bandwidth_6db",
        display_name="6 dB Bandwidth",
        description="Bandwidth at 6 dB below peak",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="Hz",
        data_range=(0, 50e6),
        typical_range=(200e3, 20e6),
        normalization=NormalizationMethod.LOG,
        importance=0.0876,
        example_value=4.2e6
    ),
    FeatureDefinition(
        name="bandwidth_20db",
        display_name="20 dB Bandwidth",
        description="Bandwidth at 20 dB below peak",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="Hz",
        data_range=(0, 100e6),
        typical_range=(500e3, 30e6),
        normalization=NormalizationMethod.LOG,
        importance=0.0123,
        example_value=8.5e6
    ),
    FeatureDefinition(
        name="roll_off_factor",
        display_name="Roll-off Factor",
        description="Spectral roll-off factor indicating filter sharpness",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="unitless",
        data_range=(0, 1),
        typical_range=(0.2, 0.8),
        normalization=NormalizationMethod.NONE,
        importance=0.0019,
        example_value=0.45
    ),
    FeatureDefinition(
        name="spectral_flatness",
        display_name="Spectral Flatness",
        description="Wiener entropy - ratio of geometric to arithmetic mean",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="unitless",
        data_range=(0, 1),
        typical_range=(0.1, 0.9),
        normalization=NormalizationMethod.NONE,
        importance=0.0765,
        example_value=0.35
    ),
    FeatureDefinition(
        name="spectral_centroid",
        display_name="Spectral Centroid",
        description="Center of mass of the spectrum",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="Hz",
        data_range=(0, 6e9),
        typical_range=(2.4e9, 5.8e9),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0210,
        example_value=2.45e9
    ),
    FeatureDefinition(
        name="spectral_spread",
        display_name="Spectral Spread",
        description="Spread of spectrum around centroid",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="Hz",
        data_range=(0, 500e6),
        typical_range=(1e6, 50e6),
        normalization=NormalizationMethod.LOG,
        importance=0.0145,
        example_value=8.2e6
    ),
    FeatureDefinition(
        name="spectral_rolloff",
        display_name="Spectral Rolloff",
        description="Frequency below which 85% of power is contained",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="Hz",
        data_range=(0, 6e9),
        typical_range=(2.42e9, 5.82e9),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0101,
        example_value=2.465e9
    ),
    FeatureDefinition(
        name="noise_floor",
        display_name="Noise Floor",
        description="Estimated noise floor level",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="dBm",
        data_range=(-120, -50),
        typical_range=(-100, -70),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0276,
        example_value=-85.0
    ),
    FeatureDefinition(
        name="signal_to_noise_ratio",
        display_name="Signal-to-Noise Ratio",
        description="Ratio of peak power to noise floor",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="dB",
        data_range=(0, 60),
        typical_range=(6, 30),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.1123,
        example_value=18.5
    ),
    FeatureDefinition(
        name="peak_to_average_power_ratio",
        display_name="Peak-to-Average Power Ratio",
        description="Ratio of peak power to average power",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="dB",
        data_range=(0, 20),
        typical_range=(3, 12),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0065,
        example_value=7.8
    ),
    FeatureDefinition(
        name="total_harmonic_distortion",
        display_name="Total Harmonic Distortion",
        description="Ratio of harmonic power to fundamental power",
        category=FeatureCategory.SPECTRAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="unitless",
        data_range=(0, 0.5),
        typical_range=(0.01, 0.2),
        normalization=NormalizationMethod.LOG,
        importance=0.0071,
        example_value=0.05
    )
]


# ============================================================================
# Cyclostationary Features (8 features)
# ============================================================================

CYCLOSTATIONARY_FEATURES = [
    FeatureDefinition(
        name="cyclic_frequency_1",
        display_name="Cyclic Frequency 1",
        description="Primary cyclic frequency detected",
        category=FeatureCategory.CYCLOSTATIONARY,
        feature_type=FeatureType.CONTINUOUS,
        unit="Hz",
        data_range=(0, 10e6),
        typical_range=(100e3, 5e6),
        normalization=NormalizationMethod.LOG,
        importance=0.0112,
        example_value=1.2e6
    ),
    FeatureDefinition(
        name="cyclic_frequency_2",
        display_name="Cyclic Frequency 2",
        description="Secondary cyclic frequency detected",
        category=FeatureCategory.CYCLOSTATIONARY,
        feature_type=FeatureType.CONTINUOUS,
        unit="Hz",
        data_range=(0, 10e6),
        typical_range=(50e3, 2e6),
        normalization=NormalizationMethod.LOG,
        importance=0.0025,
        example_value=600e3
    ),
    FeatureDefinition(
        name="cyclic_frequency_3",
        display_name="Cyclic Frequency 3",
        description="Tertiary cyclic frequency detected",
        category=FeatureCategory.CYCLOSTATIONARY,
        feature_type=FeatureType.CONTINUOUS,
        unit="Hz",
        data_range=(0, 10e6),
        typical_range=(20e3, 1e6),
        normalization=NormalizationMethod.LOG,
        importance=0.0007,
        example_value=250e3
    ),
    FeatureDefinition(
        name="cyclic_amplitude_1",
        display_name="Cyclic Amplitude 1",
        description="Amplitude of primary cyclic frequency",
        category=FeatureCategory.CYCLOSTATIONARY,
        feature_type=FeatureType.CONTINUOUS,
        unit="linear",
        data_range=(0, 1),
        typical_range=(0.1, 0.8),
        normalization=NormalizationMethod.NONE,
        importance=0.0298,
        example_value=0.45
    ),
    FeatureDefinition(
        name="cyclic_amplitude_2",
        display_name="Cyclic Amplitude 2",
        description="Amplitude of secondary cyclic frequency",
        category=FeatureCategory.CYCLOSTATIONARY,
        feature_type=FeatureType.CONTINUOUS,
        unit="linear",
        data_range=(0, 1),
        typical_range=(0.05, 0.6),
        normalization=NormalizationMethod.NONE,
        importance=0.0016,
        example_value=0.28
    ),
    FeatureDefinition(
        name="cyclic_amplitude_3",
        display_name="Cyclic Amplitude 3",
        description="Amplitude of tertiary cyclic frequency",
        category=FeatureCategory.CYCLOSTATIONARY,
        feature_type=FeatureType.CONTINUOUS,
        unit="linear",
        data_range=(0, 1),
        typical_range=(0.02, 0.4),
        normalization=NormalizationMethod.NONE,
        importance=0.0009,
        example_value=0.15
    ),
    FeatureDefinition(
        name="cyclic_coherence",
        display_name="Cyclic Coherence",
        description="Maximum cyclic coherence value",
        category=FeatureCategory.CYCLOSTATIONARY,
        feature_type=FeatureType.CONTINUOUS,
        unit="unitless",
        data_range=(0, 1),
        typical_range=(0.2, 0.9),
        normalization=NormalizationMethod.NONE,
        importance=0.0543,
        example_value=0.62
    ),
    FeatureDefinition(
        name="cycle_frequency_spacing",
        display_name="Cycle Frequency Spacing",
        description="Spacing between detected cycle frequencies",
        category=FeatureCategory.CYCLOSTATIONARY,
        feature_type=FeatureType.CONTINUOUS,
        unit="Hz",
        data_range=(0, 5e6),
        typical_range=(50e3, 2e6),
        normalization=NormalizationMethod.LOG,
        importance=0.0011,
        example_value=350e3
    )
]


# ============================================================================
# Statistical Features (10 features)
# ============================================================================

STATISTICAL_FEATURES = [
    FeatureDefinition(
        name="iq_mean_real",
        display_name="IQ Mean (Real)",
        description="Mean of the in-phase (real) component",
        category=FeatureCategory.STATISTICAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="unitless",
        data_range=(-1, 1),
        typical_range=(-0.1, 0.1),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0089,
        example_value=0.02
    ),
    FeatureDefinition(
        name="iq_mean_imag",
        display_name="IQ Mean (Imaginary)",
        description="Mean of the quadrature (imaginary) component",
        category=FeatureCategory.STATISTICAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="unitless",
        data_range=(-1, 1),
        typical_range=(-0.1, 0.1),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0036,
        example_value=-0.01
    ),
    FeatureDefinition(
        name="iq_std_real",
        display_name="IQ Std Dev (Real)",
        description="Standard deviation of in-phase component",
        category=FeatureCategory.STATISTICAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="unitless",
        data_range=(0, 1),
        typical_range=(0.1, 0.7),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0134,
        example_value=0.35
    ),
    FeatureDefinition(
        name="iq_std_imag",
        display_name="IQ Std Dev (Imaginary)",
        description="Standard deviation of quadrature component",
        category=FeatureCategory.STATISTICAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="unitless",
        data_range=(0, 1),
        typical_range=(0.1, 0.7),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0013,
        example_value=0.33
    ),
    FeatureDefinition(
        name="iq_variance",
        display_name="IQ Variance",
        description="Total variance of IQ samples",
        category=FeatureCategory.STATISTICAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="unitless",
        data_range=(0, 1),
        typical_range=(0.02, 0.5),
        normalization=NormalizationMethod.LOG,
        importance=0.0387,
        example_value=0.12
    ),
    FeatureDefinition(
        name="iq_skewness",
        display_name="IQ Skewness",
        description="Skewness of IQ sample distribution",
        category=FeatureCategory.STATISTICAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="unitless",
        data_range=(-3, 3),
        typical_range=(-0.5, 0.5),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0048,
        example_value=0.08
    ),
    FeatureDefinition(
        name="iq_kurtosis",
        display_name="IQ Kurtosis",
        description="Kurtosis of IQ sample distribution",
        category=FeatureCategory.STATISTICAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="unitless",
        data_range=(-2, 10),
        typical_range=(0, 5),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0059,
        example_value=2.5
    ),
    FeatureDefinition(
        name="amplitude_variance",
        display_name="Amplitude Variance",
        description="Variance of signal amplitude",
        category=FeatureCategory.STATISTICAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="unitless",
        data_range=(0, 1),
        typical_range=(0.01, 0.4),
        normalization=NormalizationMethod.LOG,
        importance=0.0042,
        example_value=0.08
    ),
    FeatureDefinition(
        name="phase_variance",
        display_name="Phase Variance",
        description="Variance of signal phase",
        category=FeatureCategory.STATISTICAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="rad²",
        data_range=(0, 10),
        typical_range=(0.1, 2),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0028,
        example_value=0.45
    ),
    FeatureDefinition(
        name="instantaneous_frequency_std",
        display_name="Instantaneous Frequency Std Dev",
        description="Standard deviation of instantaneous frequency",
        category=FeatureCategory.STATISTICAL,
        feature_type=FeatureType.CONTINUOUS,
        unit="Hz",
        data_range=(0, 1e6),
        typical_range=(1e3, 100e3),
        normalization=NormalizationMethod.LOG,
        importance=0.0095,
        example_value=15.2e3
    )
]


# ============================================================================
# Modulation Features (8 features)
# ============================================================================

MODULATION_FEATURES = [
    FeatureDefinition(
        name="modulation_index",
        display_name="Modulation Index",
        description="Depth of modulation",
        category=FeatureCategory.MODULATION,
        feature_type=FeatureType.CONTINUOUS,
        unit="unitless",
        data_range=(0, 5),
        typical_range=(0.5, 2),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0421,
        example_value=1.2
    ),
    FeatureDefinition(
        name="frequency_deviation",
        display_name="Frequency Deviation",
        description="Peak frequency deviation for FM signals",
        category=FeatureCategory.MODULATION,
        feature_type=FeatureType.CONTINUOUS,
        unit="Hz",
        data_range=(0, 500e3),
        typical_range=(10e3, 200e3),
        normalization=NormalizationMethod.LOG,
        importance=0.0031,
        example_value=75e3
    ),
    FeatureDefinition(
        name="symbol_rate",
        display_name="Symbol Rate",
        description="Symbol rate of digital modulation",
        category=FeatureCategory.MODULATION,
        feature_type=FeatureType.CONTINUOUS,
        unit="symbols/s",
        data_range=(0, 10e6),
        typical_range=(100e3, 5e6),
        normalization=NormalizationMethod.LOG,
        importance=0.0053,
        example_value=1.2e6
    ),
    FeatureDefinition(
        name="carrier_offset",
        display_name="Carrier Offset",
        description="Offset of carrier frequency",
        category=FeatureCategory.MODULATION,
        feature_type=FeatureType.CONTINUOUS,
        unit="Hz",
        data_range=(-1e6, 1e6),
        typical_range=(-100e3, 100e3),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0232,
        example_value=25.3e3
    ),
    FeatureDefinition(
        name="evm_rms",
        display_name="EVM (RMS)",
        description="Root mean square error vector magnitude",
        category=FeatureCategory.MODULATION,
        feature_type=FeatureType.CONTINUOUS,
        unit="unitless",
        data_range=(0, 1),
        typical_range=(0.05, 0.3),
        normalization=NormalizationMethod.NONE,
        importance=0.0432,
        example_value=0.12
    ),
    FeatureDefinition(
        name="evm_peak",
        display_name="EVM (Peak)",
        description="Peak error vector magnitude",
        category=FeatureCategory.MODULATION,
        feature_type=FeatureType.CONTINUOUS,
        unit="unitless",
        data_range=(0, 1),
        typical_range=(0.1, 0.5),
        normalization=NormalizationMethod.NONE,
        importance=0.0083,
        example_value=0.25
    ),
    FeatureDefinition(
        name="phase_error_rms",
        display_name="Phase Error (RMS)",
        description="Root mean square phase error",
        category=FeatureCategory.MODULATION,
        feature_type=FeatureType.CONTINUOUS,
        unit="degrees",
        data_range=(0, 90),
        typical_range=(2, 20),
        normalization=NormalizationMethod.Z_SCORE,
        importance=0.0167,
        example_value=8.5
    ),
    FeatureDefinition(
        name="magnitude_error_rms",
        display_name="Magnitude Error (RMS)",
        description="Root mean square magnitude error",
        category=FeatureCategory.MODULATION,
        feature_type=FeatureType.CONTINUOUS,
        unit="unitless",
        data_range=(0, 0.5),
        typical_range=(0.02, 0.15),
        normalization=NormalizationMethod.LOG,
        importance=0.0005,
        example_value=0.06
    )
]


# ============================================================================
# Feature Groups
# ============================================================================

FEATURE_GROUPS = [
    FeatureGroup(
        name="spectral_features",
        display_name="Spectral Features",
        description="Frequency domain characteristics of the signal",
        category=FeatureCategory.SPECTRAL,
        features=SPECTRAL_FEATURES
    ),
    FeatureGroup(
        name="cyclostationary_features",
        display_name="Cyclostationary Features",
        description="Periodic patterns and cyclic statistics",
        category=FeatureCategory.CYCLOSTATIONARY,
        features=CYCLOSTATIONARY_FEATURES
    ),
    FeatureGroup(
        name="statistical_features",
        display_name="Statistical Features",
        description="Statistical properties of IQ samples",
        category=FeatureCategory.STATISTICAL,
        features=STATISTICAL_FEATURES
    ),
    FeatureGroup(
        name="modulation_features",
        display_name="Modulation Features",
        description="Modulation-specific parameters",
        category=FeatureCategory.MODULATION,
        features=MODULATION_FEATURES
    )
]


# ============================================================================
# Complete Feature List
# ============================================================================

ALL_FEATURES: List[FeatureDefinition] = (
    SPECTRAL_FEATURES + 
    CYCLOSTATIONARY_FEATURES + 
    STATISTICAL_FEATURES + 
    MODULATION_FEATURES
)


# ============================================================================
# Feature Schema Class
# ============================================================================

class FeatureSchema:
    """Complete feature schema for drone classification"""
    
    def __init__(self):
        self.features = ALL_FEATURES
        self.feature_groups = FEATURE_GROUPS
        self._feature_map = {f.name: f for f in self.features}
    
    def get_feature(self, name: str) -> Optional[FeatureDefinition]:
        """Get feature definition by name"""
        return self._feature_map.get(name)
    
    def get_feature_names(self) -> List[str]:
        """Get list of all feature names"""
        return [f.name for f in self.features]
    
    def get_features_by_category(self, category: FeatureCategory) -> List[FeatureDefinition]:
        """Get features by category"""
        return [f for f in self.features if f.category == category]
    
    def get_feature_importance(self, top_n: int = None) -> List[Tuple[str, float]]:
        """Get feature importance sorted descending"""
        importance = [(f.name, f.importance) for f in self.features]
        importance.sort(key=lambda x: x[1], reverse=True)
        if top_n:
            return importance[:top_n]
        return importance
    
    def get_required_features(self) -> List[str]:
        """Get list of required feature names"""
        return [f.name for f in self.features if f.required]
    
    def normalize_feature_vector(self, features: Dict[str, float]) -> np.ndarray:
        """Normalize feature vector based on schema definitions"""
        normalized = []
        for feature in self.features:
            value = features.get(feature.name, 0)
            
            if feature.normalization == NormalizationMethod.Z_SCORE:
                # Apply Z-score normalization
                mean = (feature.typical_range[0] + feature.typical_range[1]) / 2
                std = (feature.typical_range[1] - feature.typical_range[0]) / 4
                normalized_value = (value - mean) / std if std > 0 else 0
            
            elif feature.normalization == NormalizationMethod.MIN_MAX:
                # Apply min-max normalization
                min_val, max_val = feature.data_range
                normalized_value = (value - min_val) / (max_val - min_val) if max_val > min_val else 0
            
            elif feature.normalization == NormalizationMethod.LOG:
                # Apply log normalization
                normalized_value = np.log1p(value)
            
            else:
                normalized_value = value
            
            normalized.append(normalized_value)
        
        return np.array(normalized)
    
    def validate_features(self, features: Dict[str, float]) -> Tuple[bool, List[str]]:
        """Validate feature values against schema"""
        errors = []
        for feature in self.features:
            value = features.get(feature.name)
            if value is None:
                errors.append(f"Missing feature: {feature.name}")
            elif not feature.validate(value):
                errors.append(
                    f"Feature {feature.name} value {value} outside range "
                    f"[{feature.data_range[0]}, {feature.data_range[1]}]"
                )
        return len(errors) == 0, errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entire schema to dictionary"""
        return {
            'version': '2.0.0',
            'total_features': len(self.features),
            'feature_count_by_category': {
                category.value: len(self.get_features_by_category(category))
                for category in FeatureCategory
            },
            'feature_groups': [g.to_dict() for g in self.feature_groups],
            'feature_importance': self.get_feature_importance(),
            'normalization_methods': {
                f.name: f.normalization.value for f in self.features
            }
        }


# ============================================================================
# Singleton Instance
# ============================================================================

_feature_schema: Optional[FeatureSchema] = None


def get_feature_schema() -> FeatureSchema:
    """Get singleton feature schema instance"""
    global _feature_schema
    if _feature_schema is None:
        _feature_schema = FeatureSchema()
    return _feature_schema


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Get feature schema
    schema = get_feature_schema()
    
    print("=" * 60)
    print("Feature Schema for Drone Detection")
    print("=" * 60)
    
    print(f"\nTotal Features: {len(schema.features)}")
    
    print("\nFeatures by Category:")
    for category in FeatureCategory:
        count = len(schema.get_features_by_category(category))
        print(f"  {category.value}: {count} features")
    
    print("\nTop 10 Most Important Features:")
    importance = schema.get_feature_importance(10)
    for i, (name, imp) in enumerate(importance, 1):
        print(f"  {i}. {name}: {imp:.2%}")
    
    print("\nFeature Groups:")
    for group in schema.feature_groups:
        print(f"  {group.display_name}: {len(group.features)} features")
        print(f"    {group.description}")
    
    # Example validation
    sample_features = {
        'peak_freq': 2.44e9,
        'peak_magnitude': -45.5,
        'bandwidth_6db': 4.2e6,
        'signal_to_noise_ratio': 18.5
    }
    
    is_valid, errors = schema.validate_features(sample_features)
    print(f"\nValidation Result: {'Valid' if is_valid else 'Invalid'}")
    if errors:
        print(f"  Errors: {errors}")