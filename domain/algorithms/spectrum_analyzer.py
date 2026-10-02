#!/usr/bin/env python3
# drone-detector/domain/algorithms/spectrum_analyzer.py
"""
Advanced Spectrum Analysis Module

This module provides sophisticated spectrum analysis capabilities for drone detection,
including:
- Multi-resolution spectral analysis
- Cyclostationary feature detection
- Blind source separation
- Modulation recognition
- Spectral correlation density
- Time-frequency analysis (spectrograms)
- Signal parameter estimation
- Interference detection and characterization
- Band occupancy analysis
- Signature matching
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any, Union
from enum import Enum
from collections import deque
from scipy import signal, stats, ndimage
from scipy.fft import fft, ifft, fftshift, fftfreq
from scipy.signal import spectrogram, find_peaks, correlate, hilbert
from scipy.stats import kurtosis, skew, entropy
from sklearn.decomposition import PCA, FastICA
from sklearn.preprocessing import StandardScaler
import warnings


# ============================================================================
# Enums and Data Classes
# ============================================================================

class ModulationType(Enum):
    """Types of modulations that can be detected"""
    UNKNOWN = "unknown"
    BPSK = "bpsk"
    QPSK = "qpsk"
    QAM16 = "qam16"
    QAM64 = "qam64"
    GMSK = "gmsk"
    OFDM = "ofdm"
    FM = "fm"
    AM = "am"
    DSB = "dsb"
    SSB = "ssb"
    CW = "cw"
    LORA = "lora"
    DRONE_DJI = "drone_dji"      # DJI OcuSync
    DRONE_FPV = "drone_fpv"       # Analog FPV
    DRONE_AUTEL = "drone_autel"
    DRONE_SKYDIO = "drone_skydio"
    WIFI_80211 = "wifi_80211"
    BLUETOOTH = "bluetooth"


class SignalType(Enum):
    """Signal type classification"""
    NOISE = "noise"
    TONE = "tone"
    NARROWBAND = "narrowband"
    WIDEBAND = "wideband"
    IMPULSIVE = "impulsive"
    BURST = "burst"
    CONTINUOUS = "continuous"
    SPREAD_SPECTRUM = "spread_spectrum"
    FREQ_HOPPING = "frequency_hopping"
    CHIRP = "chirp"


class InterferenceType(Enum):
    """Types of interference that can be detected"""
    NONE = "none"
    THERMAL_NOISE = "thermal_noise"
    IMPULSE = "impulse"
    NARROWBAND = "narrowband"
    WIDEBAND = "wideband"
    HARMONIC = "harmonic"
    INTERMODULATION = "intermodulation"
    BLOCKING = "blocking"
    TRANSIENT = "transient"


@dataclass
class SpectrumParameters:
    """Extracted spectrum parameters"""
    center_frequency: float = 0.0  # Hz
    bandwidth: float = 0.0  # Hz
    peak_frequency: float = 0.0  # Hz
    peak_power: float = -np.inf  # dBm
    avg_power: float = -np.inf  # dBm
    noise_floor: float = -np.inf  # dBm
    snr_db: float = 0.0  # Signal-to-noise ratio
    signal_power: float = -np.inf  # dBm
    occupied_bandwidth: float = 0.0  # Hz (99% power bandwidth)
    peak_to_average_ratio: float = 0.0  # dB
    kurtosis: float = 0.0
    skewness: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'center_freq_hz': self.center_frequency,
            'bandwidth_hz': self.bandwidth,
            'peak_freq_hz': self.peak_frequency,
            'peak_power_dbm': self.peak_power,
            'avg_power_dbm': self.avg_power,
            'noise_floor_dbm': self.noise_floor,
            'snr_db': self.snr_db,
            'occupied_bw_hz': self.occupied_bandwidth,
            'peak_to_avg_ratio_db': self.peak_to_average_ratio,
            'kurtosis': self.kurtosis,
            'skewness': self.skewness
        }


@dataclass
class ModulationFeatures:
    """Modulation classification features"""
    modulation_type: ModulationType = ModulationType.UNKNOWN
    confidence: float = 0.0
    symbol_rate: float = 0.0  # symbols/second
    carrier_offset: float = 0.0  # Hz
    phase_noise: float = 0.0  # dBc/Hz
    evm: float = 0.0  # Error vector magnitude (RMS)
    constellation_points: Optional[List[Tuple[float, float]]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'modulation': self.modulation_type.value,
            'confidence': self.confidence,
            'symbol_rate': self.symbol_rate,
            'carrier_offset_hz': self.carrier_offset,
            'phase_noise_dbc': self.phase_noise,
            'evm_percent': self.evm * 100
        }


@dataclass
class InterferenceCharacteristic:
    """Interference characterization"""
    type: InterferenceType = InterferenceType.NONE
    severity: float = 0.0  # 0-1 scale
    center_frequency: float = 0.0
    bandwidth: float = 0.0
    power: float = -np.inf
    duration: float = 0.0  # seconds
    duty_cycle: float = 0.0
    is_periodic: bool = False
    period: float = 0.0


@dataclass
class DroneSignature:
    """Drone-specific signal signature"""
    drone_type: str
    frequency_band: Tuple[float, float]  # (min, max) Hz
    typical_bandwidth: float
    modulation: ModulationType
    hopping_pattern: Optional[np.ndarray] = None
    preamble_sequence: Optional[np.ndarray] = None
    cyclostationary_features: Optional[Dict[str, Any]] = None
    
    
# ============================================================================
# Core Spectrum Analyzer
# ============================================================================

class SpectrumAnalyzer:
    """
    Advanced spectrum analysis engine for drone detection
    
    Provides comprehensive signal analysis including:
    - Spectral parameter estimation
    - Modulation recognition
    - Interference detection
    - Drone signature matching
    - Cyclostationary analysis
    """
    
    def __init__(self, sample_rate: float = 10e6, fft_size: int = 2048,
                 window_type: str = 'hann', overlap_factor: float = 0.5):
        """
        Initialize spectrum analyzer
        
        Args:
            sample_rate: Sampling rate in Hz
            fft_size: FFT size for spectral analysis
            window_type: Window function ('hann', 'hamming', 'blackman', etc.)
            overlap_factor: Overlap factor for spectrogram (0-1)
        """
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.overlap_factor = overlap_factor
        self.window = self._create_window(window_type, fft_size)
        
        # Frequency bins
        self.freq_bins = fftfreq(fft_size, 1/sample_rate)
        self.freq_bins_positive = self.freq_bins[self.freq_bins >= 0]
        
        # History buffers
        self.psd_history = deque(maxlen=100)
        self.detections_history = deque(maxlen=50)
        
        # Calibration
        self.noise_floor_calibration = None
        self.gain_calibration = 0.0
        
    def _create_window(self, window_type: str, size: int) -> np.ndarray:
        """Create window function"""
        windows = {
            'hann': signal.windows.hann,
            'hamming': signal.windows.hamming,
            'blackman': signal.windows.blackman,
            'blackmanharris': signal.windows.blackmanharris,
            'bartlett': signal.windows.bartlett,
            'flattop': signal.windows.flattop
        }
        
        if window_type in windows:
            return windows[window_type](size)
        else:
            return signal.windows.hann(size)
    
    def compute_psd(self, iq_samples: np.ndarray, db_scale: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute Power Spectral Density
        
        Args:
            iq_samples: Complex IQ samples
            db_scale: Convert to dB scale if True
            
        Returns:
            (frequencies, psd) tuple
        """
        # Window the data
        if len(iq_samples) >= self.fft_size:
            # Use Welch's method for better estimate
            f, psd = signal.welch(
                iq_samples,
                fs=self.sample_rate,
                window=self.window,
                nperseg=self.fft_size,
                noverlap=int(self.fft_size * self.overlap_factor),
                scaling='density'
            )
        else:
            # Zero-pad and use single FFT
            padded = np.zeros(self.fft_size, dtype=np.complex128)
            padded[:len(iq_samples)] = iq_samples
            fft_data = fftshift(fft(padded * self.window))
            psd = np.abs(fft_data)**2 / (self.sample_rate * self.fft_size)
            # Complex IQ spans the full -fs/2..+fs/2 range, not just
            # positive frequencies, so f must match psd's full length
            # here - self.freq_bins_positive (half-length) was the bug.
            f = fftshift(fftfreq(self.fft_size, d=1.0 / self.sample_rate))
        
        if db_scale:
            psd = 10 * np.log10(psd + 1e-12)
            
        return f, psd
    
    def compute_spectrogram(self, iq_samples: np.ndarray, 
                            nperseg: Optional[int] = None,
                            noverlap: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute spectrogram (time-frequency representation)
        
        Args:
            iq_samples: Complex IQ samples
            nperseg: Length of each segment
            noverlap: Number of points to overlap
            
        Returns:
            (frequencies, times, spectrogram) tuple
        """
        if nperseg is None:
            nperseg = min(1024, len(iq_samples) // 10)
        if noverlap is None:
            noverlap = int(nperseg * self.overlap_factor)
        
        f, t, Sxx = spectrogram(
            iq_samples,
            fs=self.sample_rate,
            window=self.window,
            nperseg=nperseg,
            noverlap=noverlap,
            mode='psd'
        )
        
        # Convert to dB
        Sxx_db = 10 * np.log10(Sxx + 1e-12)
        
        return f, t, Sxx_db
    
    def extract_parameters(self, frequencies: np.ndarray, psd: np.ndarray,
                          signal_mask: Optional[np.ndarray] = None) -> SpectrumParameters:
        """
        Extract spectrum parameters from PSD
        
        Args:
            frequencies: Frequency array in Hz
            psd: Power spectral density in dBm/Hz
            signal_mask: Boolean mask indicating signal regions
            
        Returns:
            SpectrumParameters object
        """
        params = SpectrumParameters()
        
        if len(frequencies) == 0 or len(psd) == 0:
            return params
        
        # Convert to linear if needed
        psd_linear = 10 ** (psd / 10) if np.any(psd < 0) else psd
        
        # Total power (integrate)
        total_power = np.trapz(psd_linear, frequencies)
        params.avg_power = 10 * np.log10(total_power / len(frequencies))
        
        # Peak parameters
        peak_idx = np.argmax(psd)
        params.peak_power = psd[peak_idx]
        params.peak_frequency = frequencies[peak_idx]
        
        # Noise floor estimation (using percentiles)
        lower_percentile = 10 if signal_mask is None else 25
        noise_idx = signal_mask is None or not signal_mask
        if noise_idx:
            noise_psd = psd if signal_mask is None else psd[~signal_mask]
            params.noise_floor = np.percentile(noise_psd, lower_percentile)
        else:
            params.noise_floor = np.percentile(psd, lower_percentile)
        
        # Signal-to-noise ratio
        params.snr_db = params.peak_power - params.noise_floor
        
        # Find signal region (above noise floor + threshold)
        threshold = params.noise_floor + 6  # 6 dB above noise floor
        signal_region = psd > threshold
        
        if np.any(signal_region):
            # Center frequency (power-weighted)
            if np.sum(psd_linear[signal_region]) > 0:
                params.center_frequency = np.average(
                    frequencies[signal_region],
                    weights=psd_linear[signal_region]
                )
            else:
                params.center_frequency = np.mean(frequencies[signal_region])
            
            # Bandwidth (power-weighted spread)
            if params.center_frequency > 0:
                variance = np.average(
                    (frequencies[signal_region] - params.center_frequency)**2,
                    weights=psd_linear[signal_region]
                )
                params.bandwidth = 2 * np.sqrt(variance)
            
            # Occupied bandwidth (99% power)
            cum_power = np.cumsum(psd_linear[signal_region])
            total_signal_power = cum_power[-1]
            lower_idx = np.argmax(cum_power >= 0.005 * total_signal_power)
            upper_idx = np.argmax(cum_power >= 0.995 * total_signal_power)
            
            signal_freqs = frequencies[signal_region]
            params.occupied_bandwidth = signal_freqs[upper_idx] - signal_freqs[lower_idx]
            
            # Signal power
            params.signal_power = 10 * np.log10(total_signal_power)
            
            # Peak-to-average ratio
            params.peak_to_average_ratio = params.peak_power - params.avg_power
        
        # Statistical moments
        params.kurtosis = kurtosis(psd)
        params.skewness = skew(psd)
        
        return params
    
    def detect_interference(self, frequencies: np.ndarray, psd: np.ndarray,
                            historical_psd: Optional[List[np.ndarray]] = None) -> List[InterferenceCharacteristic]:
        """
        Detect and characterize interference in the spectrum
        
        Args:
            frequencies: Frequency array in Hz
            psd: Current PSD in dBm
            historical_psd: Historical PSD measurements for baseline
            
        Returns:
            List of detected interference characteristics
        """
        interferences = []
        
        # Baseline noise floor
        if historical_psd is not None and len(historical_psd) > 0:
            # Use historical median as baseline
            baseline = np.median(historical_psd, axis=0)
            deviation = psd - baseline
        else:
            # Use local median as baseline
            baseline = ndimage.median_filter(psd, size=51)
            deviation = psd - baseline
        
        # Detect peaks in deviation
        threshold = 10  # dB above baseline
        peak_indices, properties = find_peaks(
            deviation,
            height=threshold,
            prominence=5,
            width=1
        )
        
        for idx in peak_indices:
            interference = InterferenceCharacteristic()
            interference.center_frequency = frequencies[idx]
            interference.power = psd[idx]
            
            # Estimate bandwidth
            width_idx = properties['widths'][int(np.where(peak_indices == idx)[0][0])] \
                if len(peak_indices) > 0 else 1
            interference.bandwidth = width_idx * (frequencies[1] - frequencies[0])
            
            # Determine interference type based on characteristics
            interference.type = self._classify_interference_type(
                psd, idx, deviation, properties
            )
            
            # Calculate severity (0-1)
            interference.severity = min(1.0, deviation[idx] / 30.0)
            
            # Check periodicity if historical data available
            if historical_psd is not None:
                interference.is_periodic, interference.period = \
                    self._check_periodicity(historical_psd, idx)
            
            interferences.append(interference)
        
        return interferences
    
    def _classify_interference_type(self, psd: np.ndarray, peak_idx: int,
                                    deviation: np.ndarray, properties: dict) -> InterferenceType:
        """Classify the type of interference based on spectral shape"""
        # Get region around peak
        start = max(0, peak_idx - 10)
        end = min(len(psd), peak_idx + 10)
        region = deviation[start:end]
        
        width_hz = properties['widths'][0] if len(properties['widths']) > 0 else 1
        
        if width_hz < 3:
            return InterferenceType.NARROWBAND
        elif width_hz < 20:
            return InterferenceType.WIDEBAND
        elif np.std(region) > 5:
            return InterferenceType.IMPULSE
        else:
            # Check for harmonic patterns
            if self._detect_harmonics(deviation, peak_idx):
                return InterferenceType.HARMONIC
        
        return InterferenceType.INTERMODULATION
    
    def _detect_harmonics(self, deviation: np.ndarray, peak_idx: int) -> bool:
        """Detect if the peak has harmonic components"""
        # Look for multiples of the fundamental frequency
        # This is a simplified implementation
        return False
    
    def _check_periodicity(self, historical_psd: List[np.ndarray], 
                          freq_idx: int) -> Tuple[bool, float]:
        """Check if interference at given frequency is periodic"""
        # Extract time series at this frequency
        time_series = [psd[freq_idx] for psd in historical_psd]
        
        if len(time_series) < 10:
            return False, 0.0
        
        # Compute autocorrelation
        autocorr = np.correlate(time_series, time_series, mode='full')
        autocorr = autocorr[len(autocorr)//2:]
        
        # Find peaks in autocorrelation
        peaks, _ = find_peaks(autocorr, height=np.max(autocorr) * 0.3)
        
        if len(peaks) > 1:
            period_samples = peaks[1] - peaks[0]
            period_seconds = period_samples * (1.0 / 10.0)  # Assuming 10 Hz update rate
            return True, period_seconds
        
        return False, 0.0
    
    def estimate_modulation(self, iq_samples: np.ndarray,
                           center_freq: Optional[float] = None,
                           bandwidth: Optional[float] = None) -> ModulationFeatures:
        """
        Estimate modulation type and extract features
        
        Args:
            iq_samples: Complex IQ samples
            center_freq: Center frequency (for downconversion)
            bandwidth: Signal bandwidth
            
        Returns:
            ModulationFeatures object
        """
        features = ModulationFeatures()
        
        # Downconvert if center frequency provided
        if center_freq is not None:
            t = np.arange(len(iq_samples)) / self.sample_rate
            iq_samples = iq_samples * np.exp(-2j * np.pi * center_freq * t)
        
        # Decimate to appropriate bandwidth
        if bandwidth is not None and bandwidth < self.sample_rate / 2:
            decimation = int(self.sample_rate / (bandwidth * 2))
            if decimation > 1:
                iq_samples = signal.decimate(iq_samples, decimation)
        
        # Extract features for modulation classification
        features = self._extract_modulation_features(iq_samples, features)
        
        # Classify modulation
        features.modulation_type, features.confidence = self._classify_modulation(
            iq_samples, features
        )
        
        # Estimate symbol rate
        features.symbol_rate = self._estimate_symbol_rate(iq_samples)
        
        # Estimate carrier offset
        features.carrier_offset = self._estimate_carrier_offset(iq_samples)
        
        # Estimate EVM if constellation can be recovered
        if features.modulation_type in [ModulationType.BPSK, ModulationType.QPSK,
                                        ModulationType.QAM16, ModulationType.QAM64]:
            features.evm = self._estimate_evm(iq_samples, features.modulation_type)
        
        return features
    
    def _extract_modulation_features(self, iq_samples: np.ndarray,
                                     features: ModulationFeatures) -> ModulationFeatures:
        """Extract features for modulation classification"""
        # Instantaneous amplitude statistics
        amplitude = np.abs(iq_samples)
        amplitude_norm = amplitude / np.mean(amplitude)
        features.phase_noise = np.std(amplitude_norm)
        
        # Instantaneous phase statistics (unwrapped)
        phase = np.unwrap(np.angle(iq_samples))
        phase_diff = np.diff(phase)
        phase_variance = np.var(phase_diff)
        
        # Quadrature statistics
        real_part = np.real(iq_samples)
        imag_part = np.imag(iq_samples)
        
        # Higher-order cumulants
        features.kurtosis = kurtosis(iq_samples.flatten())
        features.skewness = skew(iq_samples.flatten())
        
        # Spectral symmetry
        fft_data = fft(iq_samples)
        fft_mag = np.abs(fft_data)
        n = len(fft_mag)
        spectral_symmetry = np.corrcoef(fft_mag[:n//2], fft_mag[n//2:][::-1])[0, 1]
        
        # Store additional features
        features.constellation_points = [(float(r), float(i)) 
                                         for r, i in zip(real_part[:100], imag_part[:100])]
        
        return features
    
    def _classify_modulation(self, iq_samples: np.ndarray,
                            features: ModulationFeatures) -> Tuple[ModulationType, float]:
        """
        Classify modulation type using feature-based approach
        
        Returns:
            (modulation_type, confidence)
        """
        # This is a simplified classifier
        # In production, use pre-trained ML model
        amplitude = np.abs(iq_samples)
        phase = np.angle(iq_samples)
        
        # Check for constant envelope (FM, FSK, etc.)
        amplitude_variance = np.var(amplitude) / np.mean(amplitude)**2
        
        if amplitude_variance < 0.1:
            # Constant envelope modulation
            phase_variance = np.var(np.diff(phase))
            
            if phase_variance < 0.1:
                return ModulationType.GMSK, 0.7
            else:
                return ModulationType.FM, 0.6
        
        # Check for QAM-like modulations
        real_part = np.real(iq_samples)
        imag_part = np.imag(iq_samples)
        
        # Number of distinct amplitude levels
        amplitude_levels = len(np.unique(np.round(amplitude, 2)))
        
        if amplitude_levels <= 2:
            return ModulationType.BPSK, 0.8
        elif amplitude_levels <= 4:
            return ModulationType.QPSK, 0.7
        elif amplitude_levels <= 16:
            return ModulationType.QAM16, 0.6
        elif amplitude_levels <= 64:
            return ModulationType.QAM64, 0.5
        
        # Check for OFDM
        cyclic_prefix_len = self._detect_cyclic_prefix(iq_samples)
        if cyclic_prefix_len > 0:
            return ModulationType.OFDM, 0.75
        
        # Check for drone-specific signatures
        drone_type = self._match_drone_signature(iq_samples)
        if drone_type == "DJI":
            return ModulationType.DRONE_DJI, 0.85
        elif drone_type == "FPV":
            return ModulationType.DRONE_FPV, 0.8
        
        return ModulationType.UNKNOWN, 0.3
    
    def _detect_cyclic_prefix(self, iq_samples: np.ndarray) -> int:
        """Detect presence of cyclic prefix (OFDM)"""
        # Simplified detection
        # Correlate signal with delayed version
        delays = [16, 32, 64, 128, 256]
        
        for delay in delays:
            if delay >= len(iq_samples):
                continue
                
            correlation = np.correlate(iq_samples[:-delay], iq_samples[delay:], mode='valid')
            norm_factor = np.sqrt(np.sum(np.abs(iq_samples[:-delay])**2) * 
                                 np.sum(np.abs(iq_samples[delay:])**2))
            
            if norm_factor > 0:
                max_corr = np.max(np.abs(correlation)) / norm_factor
                if max_corr > 0.3:  # Significant correlation
                    return delay
        
        return 0
    
    def _estimate_symbol_rate(self, iq_samples: np.ndarray) -> float:
        """
        Estimate symbol rate using cyclostationary analysis
        
        Returns:
            Estimated symbol rate in symbols/second
        """
        # Compute cyclic autocorrelation
        n = len(iq_samples)
        x = iq_samples * np.hanning(n)
        X = fft(x)
        
        # Search for cyclic frequencies
        symbol_rates = []
        
        # Test potential symbol rates
        test_rates = np.linspace(self.sample_rate / 1000, self.sample_rate / 10, 20)
        
        for rate in test_rates:
            alpha = int(rate * n / self.sample_rate)
            if alpha < 1 or alpha >= n:
                continue
            
            S_alpha = X * np.roll(np.conj(X), alpha)
            alpha_magnitude = np.abs(np.mean(S_alpha))
            
            if alpha_magnitude > 0.1:
                symbol_rates.append(rate)
        
        if symbol_rates:
            return np.median(symbol_rates)
        return 0.0
    
    def _estimate_carrier_offset(self, iq_samples: np.ndarray) -> float:
        """
        Estimate carrier frequency offset
        
        Returns:
            Carrier offset in Hz
        """
        # Use fourth-power method for QPSK/QAM
        x_pow = iq_samples ** 4
        spectrum = fft(x_pow)
        
        # Find peak
        peak_idx = np.argmax(np.abs(spectrum[:len(spectrum)//2]))
        peak_freq = peak_idx * self.sample_rate / len(spectrum)
        
        # Carrier offset is peak_freq / 4
        carrier_offset = peak_freq / 4
        
        return carrier_offset
    
    def _estimate_evm(self, iq_samples: np.ndarray, modulation: ModulationType) -> float:
        """
        Estimate Error Vector Magnitude
        
        Returns:
            RMS EVM as a fraction (0-1)
        """
        # Ideal constellation points (simplified)
        if modulation == ModulationType.BPSK:
            ideal_points = np.array([1 + 0j, -1 + 0j])
        elif modulation == ModulationType.QPSK:
            ideal_points = np.array([1+1j, 1-1j, -1+1j, -1-1j]) / np.sqrt(2)
        elif modulation == ModulationType.QAM16:
            points = [-3, -1, 1, 3]
            ideal_points = np.array([x + 1j*y for x in points for y in points]) / np.sqrt(10)
        else:
            return 0.3  # Unknown
        
        # Normalize received symbols
        received = iq_samples / np.sqrt(np.mean(np.abs(iq_samples)**2))
        
        # Demodulate (simplified - nearest neighbor)
        errors = []
        for symbol in received:
            distances = np.abs(symbol - ideal_points)
            best_idx = np.argmin(distances)
            error = symbol - ideal_points[best_idx]
            errors.append(np.abs(error))
        
        evm = np.sqrt(np.mean(np.array(errors)**2))
        
        return evm
    
    def _match_drone_signature(self, iq_samples: np.ndarray) -> str:
        """
        Match signal against known drone signatures
        
        Returns:
            Drone type if matched, empty string otherwise
        """
        # Compute features for matching
        f, psd = self.compute_psd(iq_samples)
        
        # Check for DJI OcuSync signature (OFDM with specific cyclic prefix)
        if self._detect_cyclic_prefix(iq_samples) == 64:
            # Check bandwidth
            params = self.extract_parameters(f, psd)
            if 10e6 < params.bandwidth < 20e6:
                return "DJI"
        
        # Check for FPV analog signature (FM with specific deviation)
        phase = np.angle(iq_samples)
        phase_diff = np.diff(phase)
        phase_std = np.std(phase_diff)
        
        if 0.5 < phase_std < 2.0:
            return "FPV"
        
        return ""
    
    def compute_cyclostationary_features(self, iq_samples: np.ndarray,
                                         alpha: Optional[np.ndarray] = None,
                                         tau: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Compute Cyclic Autocorrelation Function (CAF) / Spectral Correlation Density (SCD)
        
        Args:
            iq_samples: Complex IQ samples
            alpha: Cycle frequencies (if None, automatically determined)
            tau: Time delays (if None, automatically determined)
            
        Returns:
            SCD matrix (alpha x tau)
        """
        n = len(iq_samples)
        
        if alpha is None:
            # Use OFDM cycle frequencies
            alpha = np.arange(-n//4, n//4, n//100) / n * self.sample_rate
        
        if tau is None:
            tau = np.arange(0, n//10)
        
        # Compute cyclic autocorrelation
        scd = np.zeros((len(alpha), len(tau)), dtype=np.complex128)
        
        x = iq_samples * np.hanning(n)
        
        for i, a in enumerate(alpha):
            a_idx = int(a * n / self.sample_rate)
            if a_idx == 0:
                continue
                
            for j, t in enumerate(tau):
                if t + a_idx < n:
                    scd[i, j] = np.mean(x[:-t-a_idx] * np.conj(x[t:]) * 
                                        np.exp(-2j * np.pi * a * np.arange(n-t-a_idx) / self.sample_rate))
        
        return scd
    
    def blind_source_separation(self, iq_samples: np.ndarray,
                               n_sources: int = 2) -> List[np.ndarray]:
        """
        Perform blind source separation to isolate signals
        
        Args:
            iq_samples: Complex IQ samples
            n_sources: Number of sources to separate
            
        Returns:
            List of separated signals
        """
        # Create observation matrix (time-delayed versions)
        n = len(iq_samples)
        n_delays = min(10, n // 100)
        
        X = np.zeros((n_delays, n - n_delays), dtype=np.complex128)
        for i in range(n_delays):
            X[i] = iq_samples[i:n - n_delays + i]
        
        # Separate real and imaginary parts
        X_real = np.vstack([np.real(X), np.imag(X)])
        
        # Standardize
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_real.T).T
        
        # Apply ICA
        ica = FastICA(n_components=min(2 * n_sources, X_scaled.shape[0]), random_state=42)
        S = ica.fit_transform(X_scaled.T).T
        
        # Combine real and imaginary parts
        separated = []
        for i in range(0, len(S), 2):
            if i+1 < len(S):
                signal_complex = S[i] + 1j * S[i+1]
                separated.append(signal_complex)
        
        return separated[:n_sources]
    
    def detect_bursts(self, iq_samples: np.ndarray,
                     threshold_db: float = 6,
                     min_duration_ms: float = 1) -> List[Tuple[int, int]]:
        """
        Detect burst transmissions in the signal
        
        Args:
            iq_samples: Complex IQ samples
            threshold_db: Energy threshold above noise floor (dB)
            min_duration_ms: Minimum burst duration in milliseconds
            
        Returns:
            List of (start_index, end_index) for each burst
        """
        # Compute energy of signal
        energy = np.abs(iq_samples) ** 2
        
        # Estimate noise floor
        noise_floor = np.percentile(energy, 25)
        threshold = noise_floor * (10 ** (threshold_db / 10))
        
        # Find bursts
        above_threshold = energy > threshold
        burst_start = []
        burst_end = []
        
        in_burst = False
        start_idx = 0
        
        for i, is_above in enumerate(above_threshold):
            if is_above and not in_burst:
                in_burst = True
                start_idx = i
            elif not is_above and in_burst:
                in_burst = False
                # Check duration
                duration_samples = i - start_idx
                duration_ms = duration_samples / self.sample_rate * 1000
                if duration_ms >= min_duration_ms:
                    burst_start.append(start_idx)
                    burst_end.append(i)
        
        return list(zip(burst_start, burst_end))
    
    def compute_band_occupancy(self, frequencies: np.ndarray, psd: np.ndarray,
                              threshold_db: float = 6) -> Dict[str, float]:
        """
        Compute band occupancy statistics
        
        Args:
            frequencies: Frequency array
            psd: Power spectral density
            threshold_db: Threshold above noise floor
            
        Returns:
            Dictionary with occupancy metrics
        """
        # Estimate noise floor
        noise_floor = np.percentile(psd, 10)
        threshold = noise_floor + threshold_db
        
        # Find occupied frequencies
        occupied = psd > threshold
        
        # Calculate metrics
        total_bandwidth = frequencies[-1] - frequencies[0]
        occupied_bandwidth = np.sum(np.diff(frequencies)[0] * occupied)
        
        # Find spectral holes
        spectral_holes = []
        in_hole = False
        start_hole = 0
        
        for i, is_occupied in enumerate(occupied):
            if not is_occupied and not in_hole:
                in_hole = True
                start_hole = frequencies[i]
            elif is_occupied and in_hole:
                in_hole = False
                spectral_holes.append((start_hole, frequencies[i]))
        
        # Calculate duty cycle per frequency (simplified)
        # This requires time-series data
        
        return {
            'total_bandwidth_hz': total_bandwidth,
            'occupied_bandwidth_hz': occupied_bandwidth,
            'occupancy_percent': (occupied_bandwidth / total_bandwidth) * 100,
            'num_spectral_holes': len(spectral_holes),
            'largest_hole_hz': max([h[1] - h[0] for h in spectral_holes]) if spectral_holes else 0
        }
    
    def calibrate_noise_floor(self, iq_samples: np.ndarray, percentile: int = 10) -> float:
        """
        Calibrate noise floor from known noise-only samples
        
        Args:
            iq_samples: IQ samples (should contain only noise)
            percentile: Percentile to use for noise floor
            
        Returns:
            Calibrated noise floor in dB
        """
        _, psd = self.compute_psd(iq_samples)
        self.noise_floor_calibration = np.percentile(psd, percentile)
        return self.noise_floor_calibration


# ============================================================================
# Advanced Analysis Utilities
# ============================================================================

class SignalParameterEstimator:
    """Advanced signal parameter estimation"""
    
    @staticmethod
    def estimate_doppler_shift(iq_samples: np.ndarray, 
                               sample_rate: float,
                               reference_freq: float) -> float:
        """
        Estimate Doppler shift in signal
        
        Args:
            iq_samples: Complex IQ samples
            sample_rate: Sampling rate
            reference_freq: Reference frequency
            
        Returns:
            Doppler shift in Hz
        """
        # Compute instantaneous frequency
        phase = np.unwrap(np.angle(iq_samples))
        inst_freq = np.diff(phase) * sample_rate / (2 * np.pi)
        
        # Average frequency offset
        doppler = np.mean(inst_freq) - reference_freq
        
        return doppler
    
    @staticmethod
    def estimate_multipath_delay(iq_samples: np.ndarray,
                                 sample_rate: float) -> float:
        """
        Estimate multipath delay spread
        
        Returns:
            Delay spread in seconds
        """
        # Compute channel impulse response
        autocorr = np.correlate(iq_samples, iq_samples, mode='full')
        autocorr = autocorr[len(autocorr)//2:]
        
        # Normalize
        autocorr = autocorr / autocorr[0]
        
        # Find delays where correlation drops below threshold
        threshold = 0.1
        indices = np.where(autocorr < threshold)[0]
        
        if len(indices) > 0:
            delay_samples = indices[0]
            delay_seconds = delay_samples / sample_rate
            return delay_seconds
        
        return 0.0
    
    @staticmethod
    def estimate_rf_fingerprint(iq_samples: np.ndarray) -> Dict[str, float]:
        """
        Extract RF fingerprint for device identification
        
        Returns:
            Dictionary of fingerprint features
        """
        # Phase noise characteristics
        phase = np.unwrap(np.angle(iq_samples))
        phase_noise = np.diff(phase)
        
        # I/Q imbalance
        i_component = np.real(iq_samples)
        q_component = np.imag(iq_samples)
        
        iq_imbalance = np.mean(i_component) / (np.mean(q_component) + 1e-12)
        
        # Amplitude variations
        amplitude = np.abs(iq_samples)
        amplitude_std = np.std(amplitude) / np.mean(amplitude)
        
        # Non-linearities (3rd order intermodulation)
        cubic = iq_samples**3
        cubic_power = np.mean(np.abs(cubic)**2)
        
        return {
            'phase_noise_std': np.std(phase_noise),
            'phase_noise_max': np.max(np.abs(phase_noise)),
            'iq_imbalance_db': 20 * np.log10(np.abs(iq_imbalance)),
            'amplitude_variation': amplitude_std,
            'cubic_power_ratio': 10 * np.log10(cubic_power / (np.mean(np.abs(iq_samples)**2) + 1e-12)),
            'amplitude_kurtosis': kurtosis(amplitude),
            'phase_kurtosis': kurtosis(phase_noise)
        }


# ============================================================================
# Factory Functions
# ============================================================================

def create_spectrum_analyzer(sample_rate: float = 10e6,
                            fft_size: int = 2048,
                            window_type: str = 'hann') -> SpectrumAnalyzer:
    """Create a configured spectrum analyzer"""
    return SpectrumAnalyzer(
        sample_rate=sample_rate,
        fft_size=fft_size,
        window_type=window_type
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Test spectrum analyzer
    import matplotlib.pyplot as plt
    
    print("Advanced Spectrum Analyzer Test")
    print("=" * 50)
    
    # Create analyzer
    samplerate = 10e6
    analyzer = SpectrumAnalyzer(sample_rate=samplerate, fft_size=2048)
    
    # Generate test signal (simulated drone signal)
    t = np.arange(0, 0.1, 1/samplerate)
    
    # Carrier frequency
    fc = 2.4e9
    f_base = 1e6  # Baseband frequency
    
    # QPSK-modulated signal
    symbols = np.random.choice([1+1j, 1-1j, -1+1j, -1-1j], len(t) // 100)
    qpsk_signal = np.repeat(symbols, 100)
    qpsk_signal = qpsk_signal[:len(t)]
    
    # Add some Doppler
    doppler = np.sin(2 * np.pi * 10 * t) * 100
    signal = qpsk_signal * np.exp(2j * np.pi * (f_base + doppler) * t)
    
    # Add noise
    noise_power = 0.1
    signal += np.sqrt(noise_power/2) * (np.random.randn(len(signal)) + 1j * np.random.randn(len(signal)))
    
    print(f"Generated test signal: {len(signal)} samples at {samplerate/1e6:.1f} MHz")
    
    # Compute PSD
    f, psd = analyzer.compute_psd(signal)
    
    # Extract parameters
    params = analyzer.extract_parameters(f, psd)
    print(f"\nSpectrum Parameters:")
    print(f"  Center frequency: {params.center_frequency/1e6:.2f} MHz")
    print(f"  Bandwidth: {params.bandwidth/1e6:.2f} MHz")
    print(f"  Peak power: {params.peak_power:.1f} dBm")
    print(f"  SNR: {params.snr_db:.1f} dB")
    
    # Estimate modulation
    modulation = analyzer.estimate_modulation(signal)
    print(f"\nModulation Analysis:")
    print(f"  Type: {modulation.modulation_type.value}")
    print(f"  Confidence: {modulation.confidence:.2f}")
    print(f"  Symbol rate: {modulation.symbol_rate/1000:.1f} kSymbols/s")
    
    # Detect bursts
    bursts = analyzer.detect_bursts(signal)
    print(f"\nBurst Detection:")
    print(f"  Number of bursts: {len(bursts)}")
    
    # Perform blind source separation
    try:
        sources = analyzer.blind_source_separation(signal, n_sources=1)
        print(f"\nBlind Source Separation:")
        print(f"  Separated {len(sources)} signals")
    except:
        print("\nBlind Source Separation: Not enough samples")
    
    # Plot results
    plt.figure(figsize=(12, 8))
    
    # Spectrum plot
    plt.subplot(2, 2, 1)
    plt.plot(f / 1e6, psd)
    plt.xlabel('Frequency (MHz)')
    plt.ylabel('PSD (dB)')
    plt.title('Power Spectral Density')
    plt.grid(True, alpha=0.3)
    
    # Constellation
    plt.subplot(2, 2, 2)
    plt.scatter(np.real(signal[::100]), np.imag(signal[::100]), s=1, alpha=0.5)
    plt.xlabel('In-phase')
    plt.ylabel('Quadrature')
    plt.title('Constellation Diagram')
    plt.grid(True, alpha=0.3)
    plt.axis('equal')
    
    # Spectrogram
    plt.subplot(2, 2, (3, 4))
    f_spec, t_spec, Sxx = analyzer.compute_spectrogram(signal[:min(len(signal), 100000)], 
                                                        nperseg=512)
    plt.imshow(Sxx, aspect='auto', origin='lower',
               extent=[t_spec[0], t_spec[-1], f_spec[0]/1e6, f_spec[-1]/1e6])
    plt.xlabel('Time (s)')
    plt.ylabel('Frequency (MHz)')
    plt.title('Spectrogram')
    plt.colorbar(label='Power (dB)')
    
    plt.tight_layout()
    plt.show()
    
    print("\n" + "=" * 50)
    print("Spectrum analyzer test complete")