# Signal Processing Chain Documentation

## Overview

The Drone Detector's signal processing chain transforms raw IQ samples from Software Defined Radios (SDRs) into actionable drone detection events. This document details each stage of the pipeline, from antenna through to final classification.

## Signal Processing Pipeline
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ Complete Signal Processing Chain │
│ │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│ │ Antenna │─▶│ LNA │─▶│ Mixer │─▶│ ADC │─▶│ DDC │─▶│ IQ │ │
│ │ │ │ │ │ │ │ │ │ │ │ Stream │ │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └───┬────┘ │
│ (Hardware) │ │
│ ▼ │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│ │ Detection│◀─│ ML │◀─│ Feature │◀─│ PSD │◀─│ FFT │◀─│ IQ │ │
│ │ Event │ │Classify │ │ Extract │ │ Compute │ │ Compute │ │ Buffer │ │
│ └────┬─────┘ └──────────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┘ │
│ │ │ │ │ │
│ ▼ ▼ ▼ ▼ │
│ ┌──────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│ │ Alert │ │ Signature │ │ Peak Map │ │ Spectrum │ │
│ │ Dispatch │ │ Matching │ │ (Waterfall)│ │ Display │ │
│ └──────────┘ └──────────────┘ └──────────────┘ └──────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────┘

text

## Stage 1: RF Front-End (Hardware)

### Antenna System

```yaml
Antenna Specifications:
  Frequency Range: 70 MHz - 6 GHz
  Gain: 5-15 dBi (depending on band)
  Polarization: Vertical (omnidirectional) or Circular (directional)
  Impedance: 50Ω
  VSWR: < 2:1

Recommended Antennas:
  - Omnidirectional: Discone (100 MHz - 3 GHz)
  - Directional: Log-periodic (400 MHz - 6 GHz)
  - Wideband: Biconical (70 MHz - 6 GHz)
Low Noise Amplifier (LNA)
yaml
LNA Characteristics:
  Gain: 20-30 dB
  Noise Figure: < 1 dB
  P1dB: > 10 dBm
  OIP3: > 30 dBm
  Current Consumption: < 100 mA @ 5V
SDR Hardware Chain
python
class SDRHardwareChain:
    """
    Hardware signal chain configuration
    """
    
    def __init__(self):
        self.stages = [
            {
                "name": "Antenna",
                "gain": 10,  # dBi
                "noise_figure": 0.5  # dB
            },
            {
                "name": "LNA",
                "gain": 25,  # dB
                "noise_figure": 0.8,  # dB
                "p1db": 5  # dBm
            },
            {
                "name": "Bandpass Filter",
                "insertion_loss": 1,  # dB
                "bandwidth": "2.4-2.5 GHz"
            },
            {
                "name": "Mixer",
                "conversion_loss": 7,  # dB
                "ip3": 15  # dBm
            },
            {
                "name": "ADC",
                "resolution": 12,  # bits
                "sample_rate": 20e6,  # Hz
                "sfdr": 70  # dBc
            }
        ]
    
    def calculate_total_gain(self) -> float:
        """Calculate total system gain"""
        total_gain = 0
        for stage in self.stages:
            if "gain" in stage:
                total_gain += stage["gain"]
            elif "insertion_loss" in stage:
                total_gain -= stage["insertion_loss"]
            elif "conversion_loss" in stage:
                total_gain -= stage["conversion_loss"]
        return total_gain
    
    def calculate_noise_figure(self) -> float:
        """Calculate cascaded noise figure using Friis formula"""
        noise_factors = []
        gains_linear = []
        
        for stage in self.stages:
            nf = stage.get("noise_figure", stage.get("insertion_loss", 3))
            gain = stage.get("gain", -stage.get("insertion_loss", 0))
            
            noise_factors.append(10 ** (nf / 10))
            gains_linear.append(10 ** (gain / 10))
        
        # Friis formula
        total_nf = noise_factors[0]
        cumulative_gain = gains_linear[0]
        
        for i in range(1, len(noise_factors)):
            total_nf += (noise_factors[i] - 1) / cumulative_gain
            cumulative_gain *= gains_linear[i]
        
        return 10 * math.log10(total_nf)
Stage 2: IQ Data Acquisition
Sampling Parameters
python
class IQAcquisitionConfig:
    """Configuration for IQ sample acquisition"""
    
    SAMPLE_RATES = {
        "narrow": 2e6,    # 2 MHz - for focused scanning
        "medium": 10e6,   # 10 MHz - standard operation
        "wide": 20e6,     # 20 MHz - wideband scanning
        "ultra": 56e6     # 56 MHz - max for high-end SDRs
    }
    
    GAIN_SETTINGS = {
        "minimum": 0,      # dB
        "low": 10,         # dB
        "medium": 20,      # dB
        "high": 30,        # dB
        "maximum": 40      # dB (if hardware supports)
    }
    
    CENTER_FREQUENCIES = {
        "2.4GHz": 2.45e9,
        "5.8GHz": 5.8e9,
        "900MHz": 915e6,
        "1.2GHz": 1.25e9,
        "custom": None
    }
    
    def __init__(self):
        self.sample_rate = self.SAMPLE_RATES["medium"]
        self.center_frequency = self.CENTER_FREQUENCIES["2.4GHz"]
        self.gain = self.GAIN_SETTINGS["medium"]
        self.samples_per_buffer = 131072  # 2^17
        self.buffer_count = 4
        self.format = "complex_float32"  # or "complex_int16"
IQ Data Structure
python
import numpy as np
from dataclasses import dataclass
from datetime import datetime

@dataclass
class IQData:
    """
    IQ sample container
    """
    samples: np.ndarray  # complex64 array
    sample_rate: float    # Hz
    center_frequency: float  # Hz
    timestamp: datetime
    gain: float  # dB
    metadata: dict
    
    @property
    def duration(self) -> float:
        """Calculate signal duration in seconds"""
        return len(self.samples) / self.sample_rate
    
    @property
    def bandwidth(self) -> float:
        """Calculate effective bandwidth (sampling rate)"""
        return self.sample_rate
    
    @property
    def nyquist_frequency(self) -> float:
        """Calculate Nyquist frequency"""
        return self.sample_rate / 2
    
    def get_power(self) -> float:
        """Calculate average power in dBm"""
        power_watts = np.mean(np.abs(self.samples) ** 2)
        power_dbm = 10 * np.log10(power_watts * 1000)
        return power_dbm
Stage 3: IQ Preprocessing
DC Offset Removal
python
class DCBlocker:
    """
    Remove DC offset from IQ samples
    """
    
    def __init__(self, alpha: float = 0.999):
        """
        Args:
            alpha: Filter coefficient (0.95-0.999 typical)
        """
        self.alpha = alpha
        self.dc_estimate = 0.0 + 0.0j
    
    def process(self, samples: np.ndarray) -> np.ndarray:
        """Apply DC blocking filter"""
        output = np.zeros_like(samples, dtype=np.complex64)
        
        for i, sample in enumerate(samples):
            self.dc_estimate = self.alpha * self.dc_estimate + (1 - self.alpha) * sample
            output[i] = sample - self.dc_estimate
        
        return output
    
    def process_vectorized(self, samples: np.ndarray) -> np.ndarray:
        """Vectorized version for better performance"""
        # Use cumulative moving average
        dc = np.cumsum(samples) / np.arange(1, len(samples) + 1)
        return samples - dc
IQ Imbalance Correction
python
class IQImbalanceCorrector:
    """
    Correct IQ gain and phase imbalance
    """
    
    def __init__(self):
        self.gain_correction = 1.0
        self.phase_correction = 0.0
        self.trained = False
    
    def train(self, samples: np.ndarray):
        """
        Estimate imbalance parameters from pure tone
        Assumes at least one strong tone in signal
        """
        # Extract I and Q components
        I = np.real(samples)
        Q = np.imag(samples)
        
        # Calculate gain imbalance
        power_I = np.mean(I ** 2)
        power_Q = np.mean(Q ** 2)
        self.gain_correction = np.sqrt(power_Q / power_I)
        
        # Calculate phase imbalance
        correlation = np.mean(I * Q)
        self.phase_correction = np.arcsin(correlation / np.sqrt(power_I * power_Q))
        
        self.trained = True
    
    def correct(self, samples: np.ndarray) -> np.ndarray:
        """Apply IQ imbalance correction"""
        if not self.trained:
            return samples
        
        I = np.real(samples)
        Q = np.imag(samples)
        
        # Apply gain correction
        I_corrected = I * self.gain_correction
        
        # Apply phase correction
        Q_corrected = Q - I_corrected * self.phase_correction
        
        return I_corrected + 1j * Q_corrected
Frequency Correction (Doppler/PLL)
python
class FrequencyCorrector:
    """
    Correct for frequency offsets using PLL or FFT-based estimation
    """
    
    def __init__(self, sample_rate: float):
        self.sample_rate = sample_rate
        self.frequency_offset = 0.0
        
    def estimate_offset_fft(self, samples: np.ndarray) -> float:
        """
        Estimate frequency offset using FFT
        """
        # Compute FFT
        spectrum = np.fft.fftshift(np.fft.fft(samples))
        frequencies = np.fft.fftshift(np.fft.fftfreq(len(samples), 1/self.sample_rate))
        
        # Find peak
        peak_idx = np.argmax(np.abs(spectrum))
        self.frequency_offset = frequencies[peak_idx]
        
        return self.frequency_offset
    
    def correct(self, samples: np.ndarray) -> np.ndarray:
        """Apply frequency correction"""
        if self.frequency_offset == 0:
            return samples
        
        t = np.arange(len(samples)) / self.sample_rate
        correction = np.exp(-2j * np.pi * self.frequency_offset * t)
        return samples * correction
Stage 4: Fast Fourier Transform (FFT)
Windowing Functions
python
class WindowFunctions:
    """
    Available windows for FFT preprocessing
    """
    
    @staticmethod
    def hamming(n: int) -> np.ndarray:
        """Hamming window - good for frequency resolution"""
        return 0.54 - 0.46 * np.cos(2 * np.pi * np.arange(n) / (n - 1))
    
    @staticmethod
    def hann(n: int) -> np.ndarray:
        """Hann window - good for amplitude accuracy"""
        return 0.5 * (1 - np.cos(2 * np.pi * np.arange(n) / (n - 1)))
    
    @staticmethod
    def blackman(n: int) -> np.ndarray:
        """Blackman window - excellent side lobe suppression"""
        a0, a1, a2 = 0.42, 0.5, 0.08
        return a0 - a1 * np.cos(2 * np.pi * np.arange(n) / (n - 1)) + \
               a2 * np.cos(4 * np.pi * np.arange(n) / (n - 1))
    
    @staticmethod
    def kaiser(n: int, beta: float = 14) -> np.ndarray:
        """Kaiser window - adjustable side lobe suppression"""
        from scipy.signal import kaiser
        return kaiser(n, beta)
    
    @staticmethod
    def flat_top(n: int) -> np.ndarray:
        """Flat-top window - best for amplitude accuracy"""
        a0, a1, a2, a3, a4 = 0.21557895, 0.41663158, 0.277263158, 0.083578947, 0.006947368
        k = np.arange(n)
        return a0 - a1 * np.cos(2 * np.pi * k / (n - 1)) + \
               a2 * np.cos(4 * np.pi * k / (n - 1)) - \
               a3 * np.cos(6 * np.pi * k / (n - 1)) + \
               a4 * np.cos(8 * np.pi * k / (n - 1))
FFT Implementation
python
class FFTProcessor:
    """
    Fast Fourier Transform processor with configurable parameters
    """
    
    def __init__(self, nfft: int = 1024, window: str = "hann", overlap: float = 0.5):
        """
        Args:
            nfft: Number of FFT points
            window: Window type (hann, hamming, blackman, kaiser, flat_top)
            overlap: Overlap ratio for successive FFTs (0-1)
        """
        self.nfft = nfft
        self.window_name = window
        self.overlap = overlap
        self.window = self._get_window(nfft, window)
        self.hop = int(nfft * (1 - overlap))
        
    def _get_window(self, nfft: int, window_type: str) -> np.ndarray:
        """Select and generate window function"""
        windows = {
            "hamming": WindowFunctions.hamming,
            "hann": WindowFunctions.hann,
            "blackman": WindowFunctions.blackman,
            "kaiser": lambda n: WindowFunctions.kaiser(n, 14),
            "flat_top": WindowFunctions.flat_top
        }
        
        if window_type in windows:
            window = windows[window_type](nfft)
        else:
            window = np.ones(nfft)
        
        # Normalize for power conservation
        window /= np.sqrt(np.mean(window ** 2))
        
        return window
    
    def compute_spectrum(self, samples: np.ndarray) -> np.ndarray:
        """
        Compute power spectrum using Welch's method
        """
        # Pad samples if needed
        if len(samples) < self.nfft:
            samples = np.pad(samples, (0, self.nfft - len(samples)))
        
        # Number of FFT frames
        n_frames = 1 + (len(samples) - self.nfft) // self.hop
        
        # Initialize spectrogram
        spectrum = np.zeros((n_frames, self.nfft // 2 + 1), dtype=np.float32)
        
        for i in range(n_frames):
            start = i * self.hop
            end = start + self.nfft
            frame = samples[start:end]
            
            # Apply window and compute FFT
            windowed = frame * self.window
            fft = np.fft.rfft(windowed)
            
            # Compute power (magnitude squared)
            spectrum[i] = np.abs(fft) ** 2
        
        # Average across frames
        avg_spectrum = np.mean(spectrum, axis=0)
        
        return avg_spectrum
    
    def compute_spectrogram(self, samples: np.ndarray) -> tuple:
        """
        Compute full spectrogram (waterfall)
        
        Returns:
            spectrogram: 2D array of powers (frames x frequencies)
            frequencies: Frequency axis values
            times: Time axis values
        """
        n_frames = 1 + (len(samples) - self.nfft) // self.hop
        spectrogram = np.zeros((n_frames, self.nfft // 2 + 1), dtype=np.float32)
        
        for i in range(n_frames):
            start = i * self.hop
            end = start + self.nfft
            frame = samples[start:end]
            
            windowed = frame * self.window
            fft = np.fft.rfft(windowed)
            spectrogram[i] = 10 * np.log10(np.abs(fft) ** 2 + 1e-12)
        
        frequencies = np.fft.rfftfreq(self.nfft, 1/self.sample_rate)
        times = np.arange(n_frames) * self.hop / self.sample_rate
        
        return spectrogram, frequencies, times
Stage 5: Power Spectral Density (PSD)
PSD Calculation
python
class PSDCalculator:
    """
    Power Spectral Density estimation using multiple methods
    """
    
    def __init__(self, sample_rate: float, method: str = "welch"):
        self.sample_rate = sample_rate
        self.method = method  # welch, periodogram, multitaper, burg
        
    def welch_method(self, samples: np.ndarray, 
                     segment_length: int = 256,
                     overlap: float = 0.5) -> tuple:
        """
        Welch's averaged periodogram method
        """
        from scipy import signal
        
        frequencies, psd = signal.welch(
            samples,
            fs=self.sample_rate,
            nperseg=segment_length,
            noverlap=int(segment_length * overlap),
            window='hann',
            scaling='density',
            return_onesided=True
        )
        
        # Convert to dBm/Hz
        psd_dbm = 10 * np.log10(psd * 1000)
        
        return frequencies, psd_dbm
    
    def periodogram_method(self, samples: np.ndarray) -> tuple:
        """
        Simple periodogram (single FFT)
        """
        n = len(samples)
        fft = np.fft.rfft(samples)
        psd = np.abs(fft) ** 2 / (n * self.sample_rate)
        
        frequencies = np.fft.rfftfreq(n, 1/self.sample_rate)
        psd_dbm = 10 * np.log10(psd * 1000)
        
        return frequencies, psd_dbm
    
    def multitaper_method(self, samples: np.ndarray, 
                          time_bandwidth: float = 4,
                          n_tapers: int = 7) -> tuple:
        """
        Multitaper spectral estimation (better variance)
        """
        from scipy import signal
        
        # Compute DPSS tapers
        tapers, _ = signal.dpss(len(samples), time_bandwidth, n_tapers)
        
        # Compute spectrums for each taper
        psd_sum = np.zeros(len(samples) // 2 + 1)
        
        for taper in tapers:
            windowed = samples * taper
            fft = np.fft.rfft(windowed)
            psd_sum += np.abs(fft) ** 2
        
        psd = psd_sum / (len(tapers) * len(samples) * self.sample_rate)
        
        frequencies = np.fft.rfftfreq(len(samples), 1/self.sample_rate)
        psd_dbm = 10 * np.log10(psd * 1000 + 1e-12)
        
        return frequencies, psd_dbm
    
    def compute_psd(self, samples: np.ndarray) -> tuple:
        """Compute PSD using selected method"""
        methods = {
            "welch": self.welch_method,
            "periodogram": self.periodogram_method,
            "multitaper": self.multitaper_method
        }
        
        method_func = methods.get(self.method, self.welch_method)
        return method_func(samples)
Noise Floor Estimation
python
class NoiseFloorEstimator:
    """
    Estimate noise floor from PSD
    """
    
    def __init__(self, method: str = "median"):
        self.method = method  # median, mode, percentile, iterative
        
    def estimate_median(self, psd: np.ndarray) -> float:
        """Median-based noise floor"""
        return np.median(psd)
    
    def estimate_mode(self, psd: np.ndarray) -> float:
        """Mode-based estimation (most common value)"""
        hist, bins = np.histogram(psd, bins=100)
        mode_idx = np.argmax(hist)
        return bins[mode_idx]
    
    def estimate_percentile(self, psd: np.ndarray, percentile: float = 10) -> float:
        """Percentile-based estimation"""
        return np.percentile(psd, percentile)
    
    def estimate_iterative(self, psd: np.ndarray, sigma_threshold: float = 2.5) -> float:
        """
        Iterative clipping algorithm
        """
        psd_clipped = psd.copy()
        
        for _ in range(5):
            mean = np.mean(psd_clipped)
            std = np.std(psd_clipped)
            threshold = mean + sigma_threshold * std
            
            psd_clipped = psd_clipped[psd_clipped < threshold]
            
            if len(psd_clipped) < len(psd) * 0.1:
                break
        
        return np.mean(psd_clipped)
    
    def estimate_noise_floor(self, psd: np.ndarray) -> tuple:
        """
        Estimate noise floor and signal-to-noise ratio
        """
        if self.method == "median":
            noise_floor = self.estimate_median(psd)
        elif self.method == "mode":
            noise_floor = self.estimate_mode(psd)
        elif self.method == "percentile":
            noise_floor = self.estimate_percentile(psd)
        elif self.method == "iterative":
            noise_floor = self.estimate_iterative(psd)
        else:
            noise_floor = self.estimate_median(psd)
        
        return noise_floor
Stage 6: Peak Detection
Peak Detection Algorithms
python
class PeakDetector:
    """
    Detect signal peaks in PSD
    """
    
    def __init__(self, 
                 threshold_db: float = 10,
                 min_distance: int = 10,
                 prominence: float = 3):
        """
        Args:
            threshold_db: Minimum peak height above noise floor
            min_distance: Minimum distance between peaks (bins)
            prominence: Minimum peak prominence (dB)
        """
        self.threshold_db = threshold_db
        self.min_distance = min_distance
        self.prominence = prominence
        
    def detect_simple(self, psd: np.ndarray, 
                      noise_floor: float) -> list:
        """
        Simple threshold-based peak detection
        """
        threshold = noise_floor + self.threshold_db
        peaks = []
        
        for i in range(1, len(psd) - 1):
            if psd[i] > threshold and \
               psd[i] > psd[i-1] and \
               psd[i] > psd[i+1]:
                peaks.append(i)
        
        # Merge close peaks
        merged_peaks = self._merge_close_peaks(peaks, self.min_distance)
        
        return merged_peaks
    
    def detect_scipy(self, psd: np.ndarray) -> list:
        """
        Use scipy's peak detection
        """
        from scipy import signal
        
        peaks, properties = signal.find_peaks(
            psd,
            height=self.threshold_db,
            distance=self.min_distance,
            prominence=self.prominence,
            width=2
        )
        
        return peaks.tolist()
    
    def detect_adaptive(self, psd: np.ndarray, 
                        noise_floor: np.ndarray) -> list:
        """
        Adaptive threshold using background estimate
        """
        # Calculate adaptive threshold
        window_size = 21
        threshold = np.zeros_like(psd)
        
        for i in range(len(psd)):
            start = max(0, i - window_size // 2)
            end = min(len(psd), i + window_size // 2)
            threshold[i] = np.mean(noise_floor[start:end]) + self.threshold_db
        
        peaks = []
        for i in range(1, len(psd) - 1):
            if psd[i] > threshold[i] and \
               psd[i] > psd[i-1] and \
               psd[i] > psd[i+1]:
                peaks.append(i)
        
        return peaks
    
    def _merge_close_peaks(self, peaks: list, min_distance: int) -> list:
        """Merge peaks that are too close"""
        if not peaks:
            return []
        
        merged = [peaks[0]]
        for peak in peaks[1:]:
            if peak - merged[-1] >= min_distance:
                merged.append(peak)
        
        return merged
    
    def characterize_peak(self, psd: np.ndarray, 
                          peak_idx: int, 
                          frequencies: np.ndarray) -> dict:
        """
        Extract peak characteristics
        """
        # Peak parameters
        peak_freq = frequencies[peak_idx]
        peak_power = psd[peak_idx]
        
        # Find 3dB bandwidth
        half_power = peak_power - 3
        left_idx = peak_idx
        right_idx = peak_idx
        
        while left_idx > 0 and psd[left_idx] > half_power:
            left_idx -= 1
        
        while right_idx < len(psd) - 1 and psd[right_idx] > half_power:
            right_idx += 1
        
        bandwidth_3db = frequencies[right_idx] - frequencies[left_idx]
        
        # Calculate occupied bandwidth (99% power)
        total_power = np.sum(psd)
        cumulative = 0
        left_idx_99 = 0
        right_idx_99 = len(psd) - 1
        
        for i in range(peak_idx, -1, -1):
            cumulative += psd[i]
            if cumulative / total_power > 0.005:  # 0.5% from peak
                left_idx_99 = i
                break
        
        cumulative = 0
        for i in range(peak_idx, len(psd)):
            cumulative += psd[i]
            if cumulative / total_power > 0.005:
                right_idx_99 = i
                break
        
        occupied_bw = frequencies[right_idx_99] - frequencies[left_idx_99]
        
        return {
            "frequency": peak_freq,
            "power": peak_power,
            "bandwidth_3db": bandwidth_3db,
            "occupied_bandwidth": occupied_bw,
            "peak_width_bins": right_idx - left_idx,
            "peak_prominence": peak_power - np.mean(
                [psd[peak_idx - 5], psd[peak_idx + 5]]
            )
        }
Stage 7: Feature Extraction
Feature Vector Generation
python
class FeatureExtractor:
    """
    Extract discriminative features for ML classification
    """
    
    def __init__(self, sample_rate: float):
        self.sample_rate = sample_rate
        
    def extract_features(self, samples: np.ndarray, 
                         psd: np.ndarray,
                         frequencies: np.ndarray,
                         peaks: list) -> dict:
        """
        Comprehensive feature extraction
        """
        features = {}
        
        # Time domain features
        features.update(self._time_domain_features(samples))
        
        # Frequency domain features
        features.update(self._frequency_domain_features(psd, frequencies))
        
        # Statistical features
        features.update(self._statistical_features(psd))
        
        # Peak features
        features.update(self._peak_features(psd, frequencies, peaks))
        
        # Cyclostationary features
        features.update(self._cyclostationary_features(samples))
        
        return features
    
    def _time_domain_features(self, samples: np.ndarray) -> dict:
        """Extract time-domain features"""
        amplitude = np.abs(samples)
        phase = np.angle(samples)
        
        features = {
            "rms_power_db": 10 * np.log10(np.mean(amplitude ** 2) + 1e-12),
            "peak_to_average_ratio": np.max(amplitude) / (np.mean(amplitude) + 1e-12),
            "crest_factor": np.max(amplitude) / (np.sqrt(np.mean(amplitude ** 2)) + 1e-12),
            "kurtosis": self._kurtosis(amplitude),
            "skewness": self._skewness(amplitude),
            "zero_crossing_rate": self._zero_crossing_rate(phase),
            "phase_variance": np.var(phase),
            "phase_range": np.max(phase) - np.min(phase)
        }
        
        return features
    
    def _frequency_domain_features(self, psd: np.ndarray, 
                                    frequencies: np.ndarray) -> dict:
        """Extract frequency-domain features"""
        # Spectral centroid
        spectral_centroid = np.sum(frequencies * psd) / (np.sum(psd) + 1e-12)
        
        # Spectral spread
        spectral_spread = np.sqrt(
            np.sum(((frequencies - spectral_centroid) ** 2) * psd) / (np.sum(psd) + 1e-12)
        )
        
        # Spectral flatness (Wiener entropy)
        geometric_mean = np.exp(np.mean(np.log(psd + 1e-12)))
        arithmetic_mean = np.mean(psd)
        spectral_flatness = geometric_mean / (arithmetic_mean + 1e-12)
        
        # Spectral rolloff (95% energy)
        cumulative_energy = np.cumsum(psd)
        total_energy = cumulative_energy[-1]
        rolloff_idx = np.where(cumulative_energy >= 0.95 * total_energy)[0]
        spectral_rolloff = frequencies[rolloff_idx[0]] if len(rolloff_idx) > 0 else 0
        
        # Spectral bandwidth
        spectral_bandwidth = np.sqrt(
            np.sum(((frequencies - spectral_centroid) ** 2) * psd) / (np.sum(psd) + 1e-12)
        )
        
        # Spectral contrast
        energy_peaks = []
        energy_valleys = []
        
        n_bands = 8
        band_size = len(psd) // n_bands
        
        for i in range(n_bands):
            start = i * band_size
            end = (i + 1) * band_size
            band_psd = psd[start:end]
            
            if len(band_psd) > 10:
                sorted_psd = np.sort(band_psd)
                energy_peaks.append(np.mean(sorted_psd[-5:]))
                energy_valleys.append(np.mean(sorted_psd[:5]))
        
        spectral_contrast = np.mean(energy_peaks) / (np.mean(energy_valleys) + 1e-12)
        
        return {
            "spectral_centroid": spectral_centroid,
            "spectral_spread": spectral_spread,
            "spectral_flatness": spectral_flatness,
            "spectral_rolloff": spectral_rolloff,
            "spectral_bandwidth": spectral_bandwidth,
            "spectral_contrast": spectral_contrast
        }
    
    def _statistical_features(self, psd: np.ndarray) -> dict:
        """Extract statistical features"""
        from scipy import stats
        
        return {
            "psd_mean": np.mean(psd),
            "psd_median": np.median(psd),
            "psd_std": np.std(psd),
            "psd_variance": np.var(psd),
            "psd_skewness": self._skewness(psd),
            "psd_kurtosis": self._kurtosis(psd),
            "psd_entropy": stats.entropy(psd + 1e-12)
        }
    
    def _peak_features(self, psd: np.ndarray, 
                       frequencies: np.ndarray, 
                       peaks: list) -> dict:
        """Extract features from detected peaks"""
        if not peaks:
            return {
                "num_peaks": 0,
                "max_peak_power": 0,
                "total_peak_power": 0,
                "peak_frequency_spread": 0,
                "strongest_peak_bw": 0
            }
        
        peak_powers = [psd[p] for p in peaks]
        peak_frequencies = [frequencies[p] for p in peaks]
        
        features = {
            "num_peaks": len(peaks),
            "max_peak_power": np.max(peak_powers),
            "total_peak_power": np.sum(peak_powers),
            "peak_frequency_spread": np.max(peak_frequencies) - np.min(peak_frequencies),
            "peak_power_variance": np.var(peak_powers),
            "peak_power_skewness": self._skewness(peak_powers),
            "strongest_peak_idx": peaks[np.argmax(peak_powers)]
        }
        
        # Add bandwidth of strongest peak
        strongest_idx = peaks[np.argmax(peak_powers)]
        half_power = max(peak_powers) - 3
        left = strongest_idx
        right = strongest_idx
        
        while left > 0 and psd[left] > half_power:
            left -= 1
        while right < len(psd) - 1 and psd[right] > half_power:
            right += 1
        
        features["strongest_peak_bw"] = frequencies[right] - frequencies[left]
        
        return features
    
    def _cyclostationary_features(self, samples: np.ndarray) -> dict:
        """
        Extract cyclostationary features for modulation classification
        """
        # Calculate cyclic autocorrelation
        alpha = 0.001  # Cycle frequency
        n = len(samples)
        
        # Simple cyclostationary detection
        cyclic_autocorr = np.correlate(
            samples * np.exp(-1j * 2 * np.pi * alpha * np.arange(n)),
            samples,
            mode='full'
        )
        
        # Normalized cyclic autocorrelation
        cyclic_autocorr_norm = np.abs(cyclic_autocorr) / (np.abs(np.corrcoef(samples, samples)[0, 1]) + 1e-12)
        
        features = {
            "cyclic_autocorr_max": np.max(cyclic_autocorr_norm),
            "cyclic_autocorr_std": np.std(cyclic_autocorr_norm),
            "modulation_index": np.max(cyclic_autocorr_norm[int(n/2):])  # Simplified
        }
        
        return features
    
    def _kurtosis(self, data: np.ndarray) -> float:
        """Calculate kurtosis (fourth moment)"""
        mean = np.mean(data)
        std = np.std(data) + 1e-12
        return np.mean(((data - mean) / std) ** 4) - 3
    
    def _skewness(self, data: np.ndarray) -> float:
        """Calculate skewness (third moment)"""
        mean = np.mean(data)
        std = np.std(data) + 1e-12
        return np.mean(((data - mean) / std) ** 3)
    
    def _zero_crossing_rate(self, phase: np.ndarray) -> float:
        """Calculate zero crossing rate of phase signal"""
        phase_diff = np.diff(np.unwrap(phase))
        zero_crossings = np.where(np.diff(np.sign(phase_diff)))[0]
        return len(zero_crossings) / len(phase_diff)
Stage 8: Signal Classification
ML Classifier Integration
python
class SignalClassifier:
    """
    ML-based signal classification
    """
    
    def __init__(self, model_path: str):
        self.model = self._load_model(model_path)
        self.classes = [
            "DJI OcuSync",
            "DJI O4",
            "FPV Analog",
            "FPV Digital (HDZero)",
            "FPV Digital (DJI)",
            "WiFi Drone",
            "Custom OFDM",
            "LoRa Telemetry",
            "Interference",
            "Noise"
        ]
        
    def _load_model(self, model_path: str):
        """Load trained ML model"""
        import joblib
        return joblib.load(model_path)
    
    def predict(self, features: dict) -> tuple:
        """
        Classify signal from features
        """
        # Convert features to vector
        feature_vector = self._features_to_vector(features)
        
        # Predict class and probabilities
        predicted_class_idx = self.model.predict([feature_vector])[0]
        probabilities = self.model.predict_proba([feature_vector])[0]
        
        predicted_class = self.classes[predicted_class_idx]
        confidence = probabilities[predicted_class_idx]
        
        return predicted_class, confidence, probabilities
    
    def _features_to_vector(self, features: dict) -> np.ndarray:
        """Convert feature dict to fixed-length vector"""
        # Define expected feature order
        feature_order = [
            "rms_power_db", "peak_to_average_ratio", "crest_factor",
            "kurtosis", "skewness", "zero_crossing_rate",
            "spectral_centroid", "spectral_spread", "spectral_flatness",
            "spectral_rolloff", "num_peaks", "max_peak_power",
            "total_peak_power", "strongest_peak_bw", "cyclic_autocorr_max"
        ]
        
        vector = []
        for feature_name in feature_order:
            vector.append(features.get(feature_name, 0))
        
        return np.array(vector)
Stage 9: Drone Identification
Signature Matching
python
class DroneSignatureMatcher:
    """
    Match detected signals against known drone signatures
    """
    
    def __init__(self, signatures_db_path: str):
        self.signatures = self._load_signatures(signatures_db_path)
        
    def _load_signatures(self, path: str) -> dict:
        """Load drone signature database"""
        import json
        with open(path, 'r') as f:
            return json.load(f)
    
    def match_signature(self, features: dict, 
                        psd: np.ndarray,
                        frequencies: np.ndarray) -> dict:
        """
        Match detected signal against known signatures
        """
        matches = []
        
        for drone_type, signature in self.signatures.items():
            score = self._calculate_similarity(features, psd, frequencies, signature)
            matches.append({
                "drone_type": drone_type,
                "similarity_score": score,
                "confidence": self._score_to_confidence(score)
            })
        
        # Sort by similarity score
        matches.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        best_match = matches[0]
        
        return {
            "drone_type": best_match["drone_type"],
            "confidence": best_match["confidence"],
            "all_matches": matches[:3],
            "is_known_drone": best_match["similarity_score"] > 0.7
        }
    
    def _calculate_similarity(self, features: dict, psd: np.ndarray,
                              frequencies: np.ndarray, signature: dict) -> float:
        """
        Calculate similarity between detected signal and signature
        """
        scores = []
        
        # Frequency band match
        if "frequency_bands" in signature:
            detected_freq = features.get("spectral_centroid", 0)
            for band in signature["frequency_bands"]:
                if band["start"] <= detected_freq <= band["end"]:
                    scores.append(1.0)
                else:
                    scores.append(0.0)
        
        # Spectral shape correlation
        if "spectral_template" in signature:
            # Resample PSD to match template length
            template = np.array(signature["spectral_template"])
            if len(psd) > len(template):
                psd_resampled = np.interp(
                    np.linspace(0, len(psd)-1, len(template)),
                    np.arange(len(psd)),
                    psd
                )
            else:
                psd_resampled = psd
            
            correlation = np.corrcoef(psd_resampled, template)[0, 1]
            scores.append(max(0, correlation))
        
        # Feature matching
        if "expected_features" in signature:
            for feat_name, expected_value in signature["expected_features"].items():
                if feat_name in features:
                    actual = features[feat_name]
                    tolerance = signature.get("tolerances", {}).get(feat_name, 0.1)
                    error = abs(actual - expected_value) / (expected_value + 1e-12)
                    feature_score = max(0, 1 - error / tolerance)
                    scores.append(feature_score)
        
        # Average all scores
        overall_score = np.mean(scores) if scores else 0.5
        
        return overall_score
    
    def _score_to_confidence(self, score: float) -> float:
        """Convert similarity score to confidence percentage"""
        if score >= 0.9:
            return 0.95 + (score - 0.9) * 0.5
        elif score >= 0.7:
            return 0.7 + (score - 0.7) * 1.25
        elif score >= 0.5:
            return 0.5 + (score - 0.5) * 1.0
        else:
            return score * 1.0
Stage 10: Detection Event Generation
Final Detection Pipeline
python
class DetectionPipeline:
    """
    Complete signal processing pipeline
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.fft_processor = FFTProcessor(
            nfft=config.get("nfft", 1024),
            window=config.get("window", "hann")
        )
        self.psd_calculator = PSDCalculator(
            sample_rate=config.get("sample_rate", 2e6),
            method=config.get("psd_method", "welch")
        )
        self.peak_detector = PeakDetector(
            threshold_db=config.get("peak_threshold", 10),
            min_distance=config.get("min_peak_distance", 10)
        )
        self.feature_extractor = FeatureExtractor(
            sample_rate=config.get("sample_rate", 2e6)
        )
        self.classifier = SignalClassifier(
            model_path=config.get("model_path", "models/classifier.pkl")
        )
        self.signature_matcher = DroneSignatureMatcher(
            signatures_db_path=config.get("signatures_path", "config/drone_signatures.json")
        )
        self.noise_estimator = NoiseFloorEstimator(method="median")
    
    async def process_iq_stream(self, iq_samples: np.ndarray) -> dict:
        """
        Process streaming IQ data through complete pipeline
        """
        # Stage 3: IQ Preprocessing
        iq_corrected = self._preprocess_iq(iq_samples)
        
        # Stage 4 & 5: Compute PSD
        frequencies, psd = self.psd_calculator.compute_psd(iq_corrected)
        
        # Stage 5b: Estimate noise floor
        noise_floor = self.noise_estimator.estimate_noise_floor(psd)
        
        # Stage 6: Detect peaks
        peaks = self.peak_detector.detect_scipy(psd - noise_floor)
        
        if not peaks:
            return {"detection": None, "reason": "No peaks detected"}
        
        # Stage 7: Extract features
        features = self.feature_extractor.extract_features(
            iq_corrected, psd, frequencies, peaks
        )
        
        # Stage 8: ML Classification
        drone_type, ml_confidence, probabilities = self.classifier.predict(features)
        
        # Stage 9: Signature matching
        signature_match = self.signature_matcher.match_signature(
            features, psd, frequencies
        )
        
        # Combine results
        final_confidence = (ml_confidence + signature_match["confidence"]) / 2
        
        # Stage 10: Generate detection event
        detection_event = {
            "timestamp": datetime.now().isoformat(),
            "frequency_hz": frequencies[peaks[0]] + self.config.get("center_frequency", 0),
            "power_dbm": float(psd[peaks[0]]),
            "snr_db": float(psd[peaks[0]] - noise_floor),
            "bandwidth_hz": features.get("strongest_peak_bw", 0),
            "drone_type": signature_match["drone_type"],
            "ml_classification": drone_type,
            "confidence": final_confidence,
            "features": features,
            "threat_level": self._assess_threat(
                drone_type, final_confidence, features
            ),
            "spectrum": {
                "frequencies": frequencies.tolist(),
                "psd": psd.tolist(),
                "peaks": peaks
            }
        }
        
        return {"detection": detection_event, "reason": "Detection successful"}
    
    def _preprocess_iq(self, samples: np.ndarray) -> np.ndarray:
        """Apply preprocessing steps"""
        # Remove DC offset
        samples = samples - np.mean(samples)
        
        # Apply gain normalization
        samples = samples / (np.std(samples) + 1e-12)
        
        return samples
    
    def _assess_threat(self, drone_type: str, 
                       confidence: float, 
                       features: dict) -> dict:
        """Assess threat level based on detection"""
        # Threat levels: NONE, LOW, MEDIUM, HIGH, CRITICAL
        
        threat_score = 0
        
        # Based on drone type
        high_threat_drones = ["Custom OFDM", "LoRa Telemetry"]
        medium_threat_drones = ["DJI OcuSync", "DJI O4"]
        
        if drone_type in high_threat_drones:
            threat_score += 40
        elif drone_type in medium_threat_drones:
            threat_score += 20
        
        # Based on confidence
        threat_score += int(confidence * 30)
        
        # Based on signal power
        power = features.get("rms_power_db", -100)
        if power > -30:
            threat_score += 20
        elif power > -50:
            threat_score += 10
        
        # Determine threat level
        if threat_score >= 80:
            level = "CRITICAL"
        elif threat_score >= 60:
            level = "HIGH"
        elif threat_score >= 40:
            level = "MEDIUM"
        elif threat_score >= 20:
            level = "LOW"
        else:
            level = "NONE"
        
        return {
            "level": level,
            "score": threat_score,
            "factors": {
                "drone_type": drone_type,
                "confidence": confidence,
                "signal_power": power
            }
        }
Performance Optimization
Accelerated Processing
python
class OptimizedSignalProcessor:
    """
    GPU-accelerated signal processing using CuPy
    """
    
    def __init__(self):
        self.use_gpu = self._check_gpu_availability()
        if self.use_gpu:
            import cupy as cp
            self.xp = cp
        else:
            import numpy as np
            self.xp = np
    
    def _check_gpu_availability(self) -> bool:
        """Check if GPU/CUDA is available"""
        try:
            import cupy as cp
            cp.cuda.runtime.getDeviceCount()
            return True
        except:
            return False
    
    def process_batch(self, iq_batch: np.ndarray) -> np.ndarray:
        """Process batch of IQ data on GPU if available"""
        if self.use_gpu:
            # Transfer to GPU
            iq_gpu = self.xp.asarray(iq_batch)
            
            # FFT on GPU
            spectrum = self.xp.fft.rfft(iq_gpu)
            psd = self.xp.abs(spectrum) ** 2
            
            # Transfer back to CPU
            return self.xp.asnumpy(psd)
        else:
            # CPU processing
            spectrum = np.fft.rfft(iq_batch)
            return np.abs(spectrum) ** 2
Real-Time Processing Requirements
python
class RealTimeProcessor:
    """
    Real-time signal processing with latency guarantees
    """
    
    def __init__(self, target_latency_ms: float = 100):
        self.target_latency = target_latency_ms / 1000
        self.processing_times = []
        
    async def process_stream(self, stream_generator):
        """Process stream with latency monitoring"""
        async for iq_frame in stream_generator:
            start_time = time.time()
            
            # Process frame
            detection = await self._process_frame(iq_frame)
            
            processing_time = time.time() - start_time
            
            # Monitor latency
            self.processing_times.append(processing_time)
            
            if processing_time > self.target_latency:
                logger.warning(f"Processing latency exceeded: {processing_time*1000:.2f}ms")
            
            yield detection
    
    async def _process_frame(self, iq_frame):
        """Single frame processing"""
        # Simplified for example
        return {
            "timestamp": datetime.now(),
            "processing_time_ms": (time.time() - start_time) * 1000
        }
This comprehensive signal chain documentation covers the entire processing pipeline from RF front-end through final drone detection, providing implementable algorithms and performance considerations for production deployment.
