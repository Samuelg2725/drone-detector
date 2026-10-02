#!/usr/bin/env python3
"""
Data Preprocessing Module for Drone Detection

This module handles all preprocessing operations for IQ data before feature extraction:
- IQ data normalization and scaling
- Noise reduction and filtering
- Signal detection and segmentation
- Artifact removal
- Data augmentation
- Batch processing utilities
"""

import numpy as np
from scipy import signal
from scipy.signal import butter, filtfilt, medfilt, savgol_filter
from scipy.stats import zscore
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from typing import Tuple, Optional, List, Dict, Any, Union
from dataclasses import dataclass
from enum import Enum
import warnings

warnings.filterwarnings('ignore')


# ============================================================================
# Enums and Data Classes
# ============================================================================

class NormalizationMethod(Enum):
    """Normalization methods for IQ data"""
    NONE = "none"
    Z_SCORE = "z_score"
    MIN_MAX = "min_max"
    ROBUST = "robust"
    UNIT_NORM = "unit_norm"
    POWER_NORM = "power_norm"


class FilterType(Enum):
    """Filter types for signal preprocessing"""
    LOWPASS = "lowpass"
    HIGHPASS = "highpass"
    BANDPASS = "bandpass"
    NOTCH = "notch"
    MEDIAN = "median"
    SAVGOL = "savgol"


@dataclass
class PreprocessingConfig:
    """Configuration for preprocessing pipeline"""
    # Normalization
    normalize: bool = True
    normalization_method: NormalizationMethod = NormalizationMethod.Z_SCORE
    
    # Filtering
    apply_filter: bool = True
    filter_type: FilterType = FilterType.BANDPASS
    lowcut_hz: float = 1000.0
    highcut_hz: float = 5e6
    order: int = 4
    notch_freq_hz: float = 60.0
    
    # Noise reduction
    remove_dc_offset: bool = True
    apply_median_filter: bool = False
    median_filter_size: int = 5
    apply_savgol: bool = False
    savgol_window: int = 11
    savgol_order: int = 3
    
    # Signal detection
    detect_signal: bool = False
    signal_threshold_sigma: float = 3.0
    min_signal_duration_ms: float = 1.0
    
    # Resampling
    target_sample_rate: Optional[float] = None
    resample_method: str = "polyphase"  # polyphase, fft, linear
    
    # Data augmentation (for training)
    augment: bool = False
    noise_augment: bool = True
    noise_snr_db: List[float] = None  # e.g., [10, 20, 30]
    freq_shift_augment: bool = True
    freq_shift_max_hz: float = 100e3
    time_shift_augment: bool = True
    time_shift_max_ms: float = 10.0
    amplitude_augment: bool = True
    amplitude_scale_range: Tuple[float, float] = (0.8, 1.2)
    phase_augment: bool = True
    phase_shift_max_deg: float = 45.0
    
    def __post_init__(self):
        if self.noise_snr_db is None:
            self.noise_snr_db = [10, 20, 30]


# ============================================================================
# IQ Preprocessor Class
# ============================================================================

class IQPreprocessor:
    """
    Comprehensive IQ data preprocessing pipeline
    
    Features:
    - Normalization and scaling
    - Filtering (lowpass, highpass, bandpass, notch)
    - Noise reduction
    - DC offset removal
    - Signal detection
    - Resampling
    - Data augmentation
    """
    
    def __init__(self, config: Optional[PreprocessingConfig] = None):
        """
        Initialize preprocessor with configuration
        
        Args:
            config: Preprocessing configuration (uses defaults if None)
        """
        self.config = config or PreprocessingConfig()
        self.sample_rate = None
        self._filters = {}
        self._scaler = None
    
    def preprocess(self, iq_samples: np.ndarray, 
                   sample_rate: float,
                   return_metadata: bool = False) -> Union[np.ndarray, Tuple[np.ndarray, Dict]]:
        """
        Main preprocessing pipeline
        
        Args:
            iq_samples: Input IQ samples (complex)
            sample_rate: Sample rate in Hz
            return_metadata: Return preprocessing metadata
            
        Returns:
            Preprocessed IQ samples (and metadata if requested)
        """
        metadata = {
            'original_shape': iq_samples.shape,
            'original_dtype': str(iq_samples.dtype),
            'operations': []
        }
        
        x = iq_samples.copy()
        
        # Convert to complex64 for consistency
        if x.dtype != np.complex64:
            x = x.astype(np.complex64)
            metadata['operations'].append('converted_to_complex64')
        
        # Remove DC offset
        if self.config.remove_dc_offset:
            x = self.remove_dc_offset(x)
            metadata['operations'].append('removed_dc_offset')
        
        # Apply filter
        if self.config.apply_filter:
            x = self.apply_filter(x, sample_rate)
            metadata['operations'].append(f'applied_{self.config.filter_type.value}_filter')
        
        # Apply median filter
        if self.config.apply_median_filter:
            x = self.median_filter(x)
            metadata['operations'].append(f'median_filter_size_{self.config.median_filter_size}')
        
        # Apply Savitzky-Golay filter
        if self.config.apply_savgol:
            x = self.savgol_filter(x)
            metadata['operations'].append(f'savgol_filter_window_{self.config.savgol_window}')
        
        # Normalize
        if self.config.normalize:
            x = self.normalize(x)
            metadata['operations'].append(f'normalized_{self.config.normalization_method.value}')
        
        # Resample if needed
        if self.config.target_sample_rate and self.config.target_sample_rate != sample_rate:
            x = self.resample(x, sample_rate, self.config.target_sample_rate)
            sample_rate = self.config.target_sample_rate
            metadata['operations'].append(f'resampled_to_{sample_rate/1e6:.1f}MHz')
        
        # Detect signal (optional)
        if self.config.detect_signal:
            signal_present, segments = self.detect_signal_regions(x, sample_rate)
            metadata['signal_detected'] = signal_present
            metadata['signal_segments'] = segments
            metadata['operations'].append('signal_detection_performed')
        
        metadata['output_shape'] = x.shape
        metadata['output_dtype'] = str(x.dtype)
        
        self.sample_rate = sample_rate
        
        if return_metadata:
            return x, metadata
        return x
    
    # ========================================================================
    # Normalization Methods
    # ========================================================================
    
    def normalize(self, x: np.ndarray) -> np.ndarray:
        """
        Normalize IQ samples using specified method
        
        Args:
            x: IQ samples
            
        Returns:
            Normalized samples
        """
        if self.config.normalization_method == NormalizationMethod.Z_SCORE:
            # Z-score normalization
            real = np.real(x)
            imag = np.imag(x)
            real_norm = (real - np.mean(real)) / (np.std(real) + 1e-12)
            imag_norm = (imag - np.mean(imag)) / (np.std(imag) + 1e-12)
            return real_norm + 1j * imag_norm
        
        elif self.config.normalization_method == NormalizationMethod.MIN_MAX:
            # Min-max scaling to [-1, 1]
            max_abs = np.max(np.abs(x))
            if max_abs > 0:
                return x / max_abs
            return x
        
        elif self.config.normalization_method == NormalizationMethod.ROBUST:
            # Robust scaling using median and IQR
            real = np.real(x)
            imag = np.imag(x)
            real_median = np.median(real)
            real_iqr = np.percentile(real, 75) - np.percentile(real, 25)
            imag_median = np.median(imag)
            imag_iqr = np.percentile(imag, 75) - np.percentile(imag, 25)
            real_norm = (real - real_median) / (real_iqr + 1e-12)
            imag_norm = (imag - imag_median) / (imag_iqr + 1e-12)
            return real_norm + 1j * imag_norm
        
        elif self.config.normalization_method == NormalizationMethod.UNIT_NORM:
            # Unit norm (magnitude = 1)
            magnitude = np.abs(x)
            magnitude[magnitude == 0] = 1
            return x / magnitude
        
        elif self.config.normalization_method == NormalizationMethod.POWER_NORM:
            # Power normalization (average power = 1)
            power = np.mean(np.abs(x)**2)
            if power > 0:
                return x / np.sqrt(power)
            return x
        
        else:  # NONE
            return x
    
    # ========================================================================
    # Filtering Methods
    # ========================================================================
    
    def apply_filter(self, x: np.ndarray, sample_rate: float) -> np.ndarray:
        """
        Apply specified filter to IQ samples
        
        Args:
            x: IQ samples
            sample_rate: Sample rate in Hz
            
        Returns:
            Filtered samples
        """
        nyquist = sample_rate / 2
        
        if self.config.filter_type == FilterType.LOWPASS:
            b, a = self._butter_lowpass(self.config.highcut_hz, sample_rate)
            return filtfilt(b, a, x, axis=0)
        
        elif self.config.filter_type == FilterType.HIGHPASS:
            b, a = self._butter_highpass(self.config.lowcut_hz, sample_rate)
            return filtfilt(b, a, x, axis=0)
        
        elif self.config.filter_type == FilterType.BANDPASS:
            b, a = self._butter_bandpass(
                self.config.lowcut_hz, self.config.highcut_hz, sample_rate
            )
            return filtfilt(b, a, x, axis=0)
        
        elif self.config.filter_type == FilterType.NOTCH:
            b, a = self._butter_notch(self.config.notch_freq_hz, sample_rate)
            return filtfilt(b, a, x, axis=0)
        
        else:
            return x
    
    def _butter_lowpass(self, cutoff_hz: float, fs: float, order: int = None) -> Tuple:
        """Design lowpass Butterworth filter"""
        if order is None:
            order = self.config.order
        nyquist = fs / 2
        normal_cutoff = cutoff_hz / nyquist
        b, a = butter(order, normal_cutoff, btype='low', analog=False)
        return b, a
    
    def _butter_highpass(self, cutoff_hz: float, fs: float, order: int = None) -> Tuple:
        """Design highpass Butterworth filter"""
        if order is None:
            order = self.config.order
        nyquist = fs / 2
        normal_cutoff = cutoff_hz / nyquist
        b, a = butter(order, normal_cutoff, btype='high', analog=False)
        return b, a
    
    def _butter_bandpass(self, lowcut_hz: float, highcut_hz: float, 
                          fs: float, order: int = None) -> Tuple:
        """Design bandpass Butterworth filter"""
        if order is None:
            order = self.config.order
        nyquist = fs / 2
        low = lowcut_hz / nyquist
        high = highcut_hz / nyquist
        b, a = butter(order, [low, high], btype='band', analog=False)
        return b, a
    
    def _butter_notch(self, notch_freq_hz: float, fs: float, 
                      quality_factor: float = 30.0) -> Tuple:
        """Design notch filter"""
        nyquist = fs / 2
        w0 = notch_freq_hz / nyquist
        b, a = butter(2, [w0 - 0.01, w0 + 0.01], btype='bandstop')
        return b, a
    
    def median_filter(self, x: np.ndarray) -> np.ndarray:
        """
        Apply median filter to reduce impulse noise
        
        Args:
            x: IQ samples
            
        Returns:
            Median filtered samples
        """
        real = medfilt(np.real(x), kernel_size=self.config.median_filter_size)
        imag = medfilt(np.imag(x), kernel_size=self.config.median_filter_size)
        return real + 1j * imag
    
    def savgol_filter(self, x: np.ndarray) -> np.ndarray:
        """
        Apply Savitzky-Golay filter for smoothing
        
        Args:
            x: IQ samples
            
        Returns:
            Smoothed samples
        """
        real = savgol_filter(np.real(x), self.config.savgol_window, self.config.savgol_order)
        imag = savgol_filter(np.imag(x), self.config.savgol_window, self.config.savgol_order)
        return real + 1j * imag
    
    # ========================================================================
    # Noise Reduction Methods
    # ========================================================================
    
    def remove_dc_offset(self, x: np.ndarray) -> np.ndarray:
        """
        Remove DC offset from IQ samples
        
        Args:
            x: IQ samples
            
        Returns:
            Samples with DC offset removed
        """
        return x - np.mean(x)
    
    def remove_outliers(self, x: np.ndarray, sigma_threshold: float = 5.0) -> np.ndarray:
        """
        Remove outlier samples based on magnitude
        
        Args:
            x: IQ samples
            sigma_threshold: Number of standard deviations for outlier detection
            
        Returns:
            Samples with outliers removed (clipped)
        """
        magnitude = np.abs(x)
        mean_mag = np.mean(magnitude)
        std_mag = np.std(magnitude)
        threshold = mean_mag + sigma_threshold * std_mag
        
        # Clip outliers
        magnitude_clipped = np.clip(magnitude, 0, threshold)
        x_clipped = x * (magnitude_clipped / (magnitude + 1e-12))
        
        return x_clipped
    
    # ========================================================================
    # Signal Detection Methods
    # ========================================================================
    
    def detect_signal_regions(self, x: np.ndarray, sample_rate: float) -> Tuple[bool, List[Tuple[int, int]]]:
        """
        Detect regions containing signal
        
        Args:
            x: IQ samples
            sample_rate: Sample rate in Hz
            
        Returns:
            (signal_present, list of (start_idx, end_idx) segments)
        """
        # Compute energy
        energy = np.abs(x)**2
        
        # Smooth energy
        window_size = int(sample_rate * 0.001)  # 1 ms window
        if window_size > 1:
            kernel = np.ones(window_size) / window_size
            energy = np.convolve(energy, kernel, mode='same')
        
        # Compute threshold
        noise_floor = np.percentile(energy, 25)
        threshold = noise_floor * (10 ** (self.config.signal_threshold_sigma / 10))
        
        # Find regions above threshold
        above_threshold = energy > threshold
        
        # Find contiguous regions
        segments = []
        in_signal = False
        start_idx = 0
        
        for i, is_above in enumerate(above_threshold):
            if is_above and not in_signal:
                in_signal = True
                start_idx = i
            elif not is_above and in_signal:
                in_signal = False
                duration_ms = (i - start_idx) / sample_rate * 1000
                if duration_ms >= self.config.min_signal_duration_ms:
                    segments.append((start_idx, i))
        
        return len(segments) > 0, segments
    
    def extract_signal_regions(self, x: np.ndarray, sample_rate: float) -> List[np.ndarray]:
        """
        Extract only the signal-containing regions
        
        Args:
            x: IQ samples
            sample_rate: Sample rate in Hz
            
        Returns:
            List of signal segments
        """
        _, segments = self.detect_signal_regions(x, sample_rate)
        return [x[start:end] for start, end in segments]
    
    # ========================================================================
    # Resampling Methods
    # ========================================================================
    
    def resample(self, x: np.ndarray, original_rate: float, target_rate: float) -> np.ndarray:
        """
        Resample IQ data to target sample rate
        
        Args:
            x: IQ samples
            original_rate: Original sample rate
            target_rate: Target sample rate
            
        Returns:
            Resampled samples
        """
        if original_rate == target_rate:
            return x
        
        num_samples = int(len(x) * target_rate / original_rate)
        
        if self.config.resample_method == "polyphase":
            # Use polyphase resampling for efficient resampling
            from scipy.signal import resample_poly
            gcd = np.gcd(int(original_rate), int(target_rate))
            up = int(target_rate // gcd)
            down = int(original_rate // gcd)
            return resample_poly(x, up, down, axis=0)
        
        elif self.config.resample_method == "fft":
            # FFT-based resampling (good for small changes)
            from scipy.signal import resample
            return resample(x, num_samples, axis=0)
        
        else:
            # Linear interpolation
            from scipy import interpolate
            old_indices = np.arange(len(x))
            new_indices = np.linspace(0, len(x) - 1, num_samples)
            interp_real = interpolate.interp1d(old_indices, np.real(x), kind='linear')
            interp_imag = interpolate.interp1d(old_indices, np.imag(x), kind='linear')
            return interp_real(new_indices) + 1j * interp_imag(new_indices)
    
    # ========================================================================
    # Data Augmentation Methods (for training)
    # ========================================================================
    
    def augment(self, x: np.ndarray, sample_rate: float) -> np.ndarray:
        """
        Apply data augmentation techniques
        
        Args:
            x: IQ samples
            sample_rate: Sample rate in Hz
            
        Returns:
            Augmented samples
        """
        if not self.config.augment:
            return x
        
        x_aug = x.copy()
        
        # Add noise
        if self.config.noise_augment:
            snr_db = np.random.choice(self.config.noise_snr_db)
            x_aug = self.add_noise(x_aug, snr_db)
        
        # Frequency shift
        if self.config.freq_shift_augment:
            shift_hz = np.random.uniform(-self.config.freq_shift_max_hz, 
                                          self.config.freq_shift_max_hz)
            x_aug = self.frequency_shift(x_aug, shift_hz, sample_rate)
        
        # Time shift
        if self.config.time_shift_augment:
            shift_ms = np.random.uniform(-self.config.time_shift_max_ms,
                                          self.config.time_shift_max_ms)
            x_aug = self.time_shift(x_aug, shift_ms, sample_rate)
        
        # Amplitude scaling
        if self.config.amplitude_augment:
            scale = np.random.uniform(*self.config.amplitude_scale_range)
            x_aug = x_aug * scale
        
        # Phase shift
        if self.config.phase_augment:
            phase_deg = np.random.uniform(-self.config.phase_shift_max_deg,
                                           self.config.phase_shift_max_deg)
            x_aug = self.phase_shift(x_aug, np.radians(phase_deg))
        
        return x_aug
    
    def add_noise(self, x: np.ndarray, snr_db: float) -> np.ndarray:
        """
        Add Gaussian noise to achieve target SNR
        
        Args:
            x: IQ samples
            snr_db: Target SNR in dB
            
        Returns:
            Noisy samples
        """
        signal_power = np.mean(np.abs(x)**2)
        noise_power = signal_power / (10 ** (snr_db / 10))
        noise = np.sqrt(noise_power / 2) * (np.random.randn(len(x)) + 1j * np.random.randn(len(x)))
        return x + noise
    
    def frequency_shift(self, x: np.ndarray, shift_hz: float, sample_rate: float) -> np.ndarray:
        """
        Apply frequency shift to signal
        
        Args:
            x: IQ samples
            shift_hz: Frequency shift in Hz
            sample_rate: Sample rate in Hz
            
        Returns:
            Frequency-shifted samples
        """
        t = np.arange(len(x)) / sample_rate
        return x * np.exp(1j * 2 * np.pi * shift_hz * t)
    
    def time_shift(self, x: np.ndarray, shift_ms: float, sample_rate: float) -> np.ndarray:
        """
        Apply time shift (circular) to signal
        
        Args:
            x: IQ samples
            shift_ms: Time shift in milliseconds
            sample_rate: Sample rate in Hz
            
        Returns:
            Time-shifted samples
        """
        shift_samples = int(shift_ms * sample_rate / 1000)
        return np.roll(x, shift_samples)
    
    def phase_shift(self, x: np.ndarray, phase_rad: float) -> np.ndarray:
        """
        Apply constant phase shift
        
        Args:
            x: IQ samples
            phase_rad: Phase shift in radians
            
        Returns:
            Phase-shifted samples
        """
        return x * np.exp(1j * phase_rad)
    
    # ========================================================================
    # Batch Processing
    # ========================================================================
    
    def preprocess_batch(self, samples: List[np.ndarray], 
                         sample_rates: List[float]) -> List[np.ndarray]:
        """
        Preprocess a batch of IQ samples
        
        Args:
            samples: List of IQ sample arrays
            sample_rates: List of sample rates
            
        Returns:
            List of preprocessed samples
        """
        processed = []
        for x, fs in zip(samples, sample_rates):
            processed.append(self.preprocess(x, fs))
        return processed
    
    def fit_scaler(self, samples: List[np.ndarray]):
        """
        Fit scaler for normalization (for use with StandardScaler)
        
        Args:
            samples: List of IQ sample arrays for fitting
        """
        all_real = []
        all_imag = []
        
        for x in samples:
            all_real.extend(np.real(x))
            all_imag.extend(np.imag(x))
        
        all_real = np.array(all_real).reshape(-1, 1)
        all_imag = np.array(all_imag).reshape(-1, 1)
        
        self._scaler = StandardScaler()
        self._scaler.fit(np.concatenate([all_real, all_imag], axis=1))
    
    def apply_scaler(self, x: np.ndarray) -> np.ndarray:
        """
        Apply fitted scaler to IQ samples
        
        Args:
            x: IQ samples
            
        Returns:
            Scaled samples
        """
        if self._scaler is None:
            return x
        
        real = np.real(x).reshape(-1, 1)
        imag = np.imag(x).reshape(-1, 1)
        scaled = self._scaler.transform(np.concatenate([real, imag], axis=1))
        return scaled[:, 0] + 1j * scaled[:, 1]


# ============================================================================
# Feature Extractor Wrapper
# ============================================================================

class PreprocessingPipeline:
    """
    Complete preprocessing pipeline that integrates with feature extraction
    """
    
    def __init__(self, config: Optional[PreprocessingConfig] = None):
        self.preprocessor = IQPreprocessor(config)
        self.config = config or PreprocessingConfig()
    
    def process_for_training(self, iq_samples: np.ndarray, 
                             sample_rate: float) -> np.ndarray:
        """
        Process IQ data for training (with augmentation)
        
        Args:
            iq_samples: IQ samples
            sample_rate: Sample rate
            
        Returns:
            Processed samples ready for feature extraction
        """
        # Preprocess
        processed = self.preprocessor.preprocess(iq_samples, sample_rate)
        
        # Augment if enabled
        if self.config.augment:
            processed = self.preprocessor.augment(processed, sample_rate)
        
        return processed
    
    def process_for_inference(self, iq_samples: np.ndarray,
                               sample_rate: float) -> np.ndarray:
        """
        Process IQ data for inference (real-time detection)
        
        Args:
            iq_samples: IQ samples
            sample_rate: Sample rate
            
        Returns:
            Processed samples ready for feature extraction
        """
        return self.preprocessor.preprocess(iq_samples, sample_rate)


# ============================================================================
# Utility Functions
# ============================================================================

def compute_snr(signal_power: float, noise_power: float) -> float:
    """Compute SNR in dB"""
    return 10 * np.log10(signal_power / (noise_power + 1e-12))


def compute_papr(x: np.ndarray) -> float:
    """Compute Peak-to-Average Power Ratio"""
    peak_power = np.max(np.abs(x)**2)
    avg_power = np.mean(np.abs(x)**2)
    return 10 * np.log10(peak_power / (avg_power + 1e-12))


def compute_crest_factor(x: np.ndarray) -> float:
    """Compute Crest Factor (peak amplitude / RMS)"""
    peak_amp = np.max(np.abs(x))
    rms_amp = np.sqrt(np.mean(np.abs(x)**2))
    return peak_amp / (rms_amp + 1e-12)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Create sample IQ data
    sample_rate = 10e6
    t = np.arange(0, 0.1, 1/sample_rate)
    
    # Generate a test signal (simulated drone)
    signal = np.exp(1j * 2 * np.pi * 1e6 * t)  # 1 MHz tone
    noise = 0.1 * (np.random.randn(len(t)) + 1j * np.random.randn(len(t)))
    iq_data = signal + noise
    
    print("=" * 60)
    print("IQ Preprocessor Test")
    print("=" * 60)
    
    # Create preprocessor with custom config
    config = PreprocessingConfig(
        normalize=True,
        normalization_method=NormalizationMethod.Z_SCORE,
        apply_filter=True,
        filter_type=FilterType.BANDPASS,
        lowcut_hz=500e3,
        highcut_hz=2e6,
        remove_dc_offset=True
    )
    
    preprocessor = IQPreprocessor(config)
    
    # Process the data
    print(f"\nOriginal shape: {iq_data.shape}")
    print(f"Original mean: {np.mean(iq_data):.4f}")
    print(f"Original std: {np.std(iq_data):.4f}")
    
    processed, metadata = preprocessor.preprocess(iq_data, sample_rate, return_metadata=True)
    
    print(f"\nProcessed shape: {processed.shape}")
    print(f"Processed mean: {np.mean(processed):.4f}")
    print(f"Processed std: {np.std(processed):.4f}")
    
    print(f"\nOperations performed:")
    for op in metadata['operations']:
        print(f"  - {op}")
    
    # Test augmentation
    print("\n" + "=" * 60)
    print("Data Augmentation Test")
    print("=" * 60)
    
    aug_config = PreprocessingConfig(
        augment=True,
        noise_augment=True,
        noise_snr_db=[15, 20, 25],
        freq_shift_augment=True,
        freq_shift_max_hz=10e3,
        amplitude_augment=True
    )
    
    preprocessor_aug = IQPreprocessor(aug_config)
    processed_aug = preprocessor_aug.process_for_training(iq_data, sample_rate)
    
    print(f"Original: mean={np.mean(np.abs(iq_data)):.4f}, std={np.std(np.abs(iq_data)):.4f}")
    print(f"Augmented: mean={np.mean(np.abs(processed_aug)):.4f}, std={np.std(np.abs(processed_aug)):.4f}")
    
    print("\n" + "=" * 60)
    print("Preprocessing test complete!")