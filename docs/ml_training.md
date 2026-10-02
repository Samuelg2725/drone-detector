# Drone Detector System - Machine Learning Training Guide

## Overview

The Drone Detector system uses machine learning for signal classification, drone identification, and threat assessment. This guide covers the complete ML pipeline from data collection to model deployment.

## ML Architecture
┌─────────────────────────────────────────────────────────────────────────────┐
│ Machine Learning Pipeline │
│ │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ Data Collection │ │
│ │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │ │
│ │ │ Live SDR │ │ Replay │ │ Synthetic│ │ External│ │ │
│ │ │ Capture │ │ Dataset │ │ Generator│ │ Datasets│ │ │
│ │ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │ │
│ │ └─────────────┼─────────────┼─────────────┘ │ │
│ │ ▼ ▼ │ │
│ │ ┌─────────────┐ ┌─────────────┐ │ │
│ │ │ Raw IQ Data │ │ Metadata │ │ │
│ │ └──────┬──────┘ └──────┬──────┘ │ │
│ └─────────────────────┼────────────────┼─────────────────────────────┘ │
│ │ │ │
│ ▼ ▼ │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ Feature Engineering │ │
│ │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │ │
│ │ │ FFT │ │ PSD │ │ Cyclo- │ │ Time │ │ │
│ │ │ │ │ │ │ stationary│ │ Domain │ │ │
│ │ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │ │
│ │ └─────────────┼─────────────┼─────────────┘ │ │
│ │ ▼ ▼ │ │
│ │ ┌─────────────┐ ┌─────────────┐ │ │
│ │ │ Feature │ │ Labels │ │ │
│ │ │ Vectors │ │ │ │ │
│ │ └──────┬──────┘ └──────┬──────┘ │ │
│ └─────────────────────┼────────────────┼─────────────────────────────┘ │
│ │ │ │
│ ▼ ▼ │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ Model Training │ │
│ │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │ │
│ │ │ CNN │ │ RNN/LSTM│ │ Random │ │ XGBoost│ │ │
│ │ │ │ │ │ │ Forest │ │ │ │ │
│ │ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │ │
│ │ └─────────────┼─────────────┼─────────────┘ │ │
│ │ ▼ ▼ │ │
│ │ ┌─────────────┐ ┌─────────────┐ │ │
│ │ │ Trained │ │ Evaluation │ │ │
│ │ │ Model │ │ Metrics │ │ │
│ │ └──────┬──────┘ └──────┬──────┘ │ │
│ └─────────────────────┼────────────────┼─────────────────────────────┘ │
│ │ │ │
│ ▼ ▼ │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ Model Deployment │ │
│ │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │ │
│ │ │ Export │ │ Version │ │ A/B Test │ │ Monitor │ │ │
│ │ │ Model │ │ Control │ │ │ │ │ │ │
│ │ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │ │
│ └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘

text

## Quick Start

### One-Command Training

```bash
# Train default classifier
python scripts/train_model.py

# Train with GPU acceleration
python scripts/train_model.py --gpu --batch-size 128

# Train specific model type
python scripts/train_model.py --model-type cnn --epochs 100

# Train with custom dataset
python scripts/train_model.py --dataset /path/to/dataset --output /path/to/model

# Resume training from checkpoint
python scripts/train_model.py --resume checkpoints/model_epoch_50.pt
Training Pipeline Example
python
# examples/train_drone_classifier.py
"""Complete training pipeline example"""

from drone_detector.ml import (
    DataLoader,
    FeatureExtractor,
    DroneClassifier,
    Trainer,
    Evaluator
)

# 1. Load and prepare data
data_loader = DataLoader(
    dataset_path="/data/drone_dataset",
    validation_split=0.2,
    test_split=0.1
)

train_data, val_data, test_data = data_loader.load()

# 2. Extract features
feature_extractor = FeatureExtractor(
    features=[
        "spectral_centroid",
        "peak_bandwidth",
        "cyclic_autocorr",
        "time_domain_stats"
    ]
)

X_train = feature_extractor.extract(train_data)
X_val = feature_extractor.extract(val_data)

# 3. Create model
model = DroneClassifier(
    input_size=X_train.shape[1],
    num_classes=10,  # 10 drone types
    model_type="xgboost"  # or "cnn", "random_forest"
)

# 4. Train
trainer = Trainer(
    model=model,
    learning_rate=0.001,
    batch_size=64,
    epochs=50
)

history = trainer.train(
    X_train, train_data.labels,
    X_val, val_data.labels
)

# 5. Evaluate
evaluator = Evaluator(model)
metrics = evaluator.evaluate(test_data)

print(f"Accuracy: {metrics['accuracy']:.2%}")
print(f"F1 Score: {metrics['f1_score']:.2%}")

# 6. Save model
model.save("/models/drone_classifier_v1.pkl")
Dataset Preparation
Dataset Structure
text
drone_dataset/
├── raw/
│   ├── dji_mavic_24g/
│   │   ├── session_001.iq
│   │   ├── session_001.json
│   │   ├── session_002.iq
│   │   └── session_002.json
│   ├── fpv_analog_58g/
│   ├── dji_ocu_24g/
│   ├── noise_samples/
│   └── interference/
├── processed/
│   ├── features/
│   │   ├── X_train.npy
│   │   ├── X_val.npy
│   │   ├── X_test.npy
│   │   ├── y_train.npy
│   │   ├── y_val.npy
│   │   └── y_test.npy
│   ├── metadata.json
│   └── feature_names.json
├── augmented/
│   └── (augmented samples)
├── labels.json
└── dataset_info.yaml
Dataset Collection Script
python
# scripts/collect_dataset.py
"""Collect training dataset from live SDR"""

import asyncio
from pathlib import Path
from datetime import datetime

class DatasetCollector:
    """Collect IQ samples for training dataset"""
    
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    async def collect_samples(self, drone_type: str, duration: int = 60):
        """Collect samples for specific drone type"""
        
        # Create session directory
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = self.output_dir / "raw" / drone_type / session_id
        session_dir.mkdir(parents=True)
        
        # Configure SDR
        sdr = await self.setup_sdr(drone_type)
        
        # Collect in segments
        segment_duration = 5  # seconds
        num_segments = duration // segment_duration
        
        for i in range(num_segments):
            iq_data = await sdr.read_samples(
                duration=segment_duration,
                sample_rate=2e6
            )
            
            # Save IQ data
            iq_file = session_dir / f"segment_{i:04d}.iq"
            iq_data.tofile(iq_file)
            
            # Save metadata
            metadata = {
                'drone_type': drone_type,
                'sample_rate': 2e6,
                'center_frequency': await self.get_frequency(drone_type),
                'gain': 20,
                'timestamp': datetime.now().isoformat(),
                'segment': i,
                'snr': await self.estimate_snr(iq_data)
            }
            
            with open(session_dir / f"segment_{i:04d}.json", 'w') as f:
                json.dump(metadata, f)
                
            print(f"Collected segment {i+1}/{num_segments}")
            
        await sdr.close()
        print(f"Collection complete for {drone_type}")
Synthetic Data Generation
python
# scripts/generate_synthetic_data.py
"""Generate synthetic training data"""

import numpy as np
from scipy import signal

class SyntheticDataGenerator:
    """Generate synthetic drone signals"""
    
    def __init__(self, sample_rate=2e6):
        self.sample_rate = sample_rate
        
    def generate_dji_signal(self, duration=1.0, snr=20):
        """Generate DJI OcuSync-like OFDM signal"""
        n_samples = int(duration * self.sample_rate)
        
        # OFDM parameters
        fft_size = 1024
        cp_len = 128
        num_symbols = n_samples // (fft_size + cp_len)
        
        # Generate QAM symbols
        qam_symbols = (2 * np.random.randint(0, 2, fft_size) - 1) + \
                      1j * (2 * np.random.randint(0, 2, fft_size) - 1)
        
        # OFDM modulation
        ofdm_signal = []
        for _ in range(num_symbols):
            # IFFT
            symbol = np.fft.ifft(qam_symbols)
            # Add cyclic prefix
            symbol_with_cp = np.concatenate([symbol[-cp_len:], symbol])
            ofdm_signal.extend(symbol_with_cp)
            
        # Add frequency offset (typical for DJI)
        t = np.arange(len(ofdm_signal)) / self.sample_rate
        freq_offset = 50e3  # 50 kHz offset
        ofdm_signal = ofdm_signal * np.exp(1j * 2 * np.pi * freq_offset * t)
        
        # Add noise
        noise = self._add_noise(ofdm_signal, snr)
        
        return np.array(ofdm_signal[:n_samples])
    
    def generate_fpv_signal(self, duration=1.0, snr=20):
        """Generate analog FPV signal (FM modulated)"""
        n_samples = int(duration * self.sample_rate)
        t = np.arange(n_samples) / self.sample_rate
        
        # Baseband video signal (composite)
        video = np.sin(2 * np.pi * 15734 * t)  # Horizontal sync
        video += 0.3 * np.sin(2 * np.pi * 60 * t)  # Vertical sync
        video += 0.5 * np.random.randn(n_samples)  # Video noise
        
        # FM modulation
        deviation = 5e6  # 5 MHz deviation
        fm_signal = np.exp(1j * 2 * np.pi * deviation * 
                          np.cumsum(video) / self.sample_rate)
        
        # Add noise
        fm_signal = self._add_noise(fm_signal, snr)
        
        return fm_signal
    
    def generate_telemetry_signal(self, duration=1.0, snr=20):
        """Generate LoRa-like telemetry signal"""
        n_samples = int(duration * self.sample_rate)
        
        # Chirp spread spectrum
        t = np.arange(n_samples) / self.sample_rate
        bandwidth = 500e3
        chirp_rate = bandwidth / duration
        
        up_chirp = np.exp(1j * 2 * np.pi * (bandwidth * t + 
                         0.5 * chirp_rate * t**2))
        
        # Add data modulation (simple BPSK on chirp)
        data_rate = 1000  # symbols per second
        symbols_per_chirp = int(duration * data_rate)
        data = 2 * np.random.randint(0, 2, symbols_per_chirp) - 1
        
        # Modulate chirp with data
        modulated = up_chirp * np.repeat(data, n_samples // symbols_per_chirp)
        
        return self._add_noise(modulated, snr)
    
    def _add_noise(self, signal, snr_db):
        """Add AWGN noise at specified SNR"""
        signal_power = np.mean(np.abs(signal)**2)
        noise_power = signal_power / (10 ** (snr_db / 10))
        noise = np.sqrt(noise_power/2) * (np.random.randn(len(signal)) + 
                                         1j * np.random.randn(len(signal)))
        return signal + noise
Data Augmentation
python
# scripts/augment_data.py
"""Data augmentation for training"""

class DataAugmenter:
    """Augment IQ data for better generalization"""
    
    def __init__(self):
        self.augmentations = [
            self.add_noise,
            self.add_frequency_offset,
            self.add_phase_noise,
            self.time_shift,
            self.amplitude_scale,
            self.sample_rate_conversion
        ]
        
    def augment(self, iq_samples, num_augmentations=5):
        """Generate augmented versions of IQ samples"""
        augmented = []
        
        for _ in range(num_augmentations):
            aug_samples = iq_samples.copy()
            
            # Randomly select 2-3 augmentations
            selected = np.random.choice(
                self.augmentations,
                size=np.random.randint(2, 4),
                replace=False
            )
            
            for aug_func in selected:
                aug_samples = aug_func(aug_samples)
                
            augmented.append(aug_samples)
            
        return augmented
    
    def add_noise(self, samples):
        """Add AWGN noise with random SNR"""
        snr_db = np.random.uniform(5, 30)
        signal_power = np.mean(np.abs(samples)**2)
        noise_power = signal_power / (10 ** (snr_db / 10))
        noise = np.sqrt(noise_power/2) * (np.random.randn(len(samples)) + 
                                         1j * np.random.randn(len(samples)))
        return samples + noise
    
    def add_frequency_offset(self, samples):
        """Add random frequency offset"""
        max_offset = 100e3  # 100 kHz max
        offset = np.random.uniform(-max_offset, max_offset)
        t = np.arange(len(samples)) / 2e6  # Assume 2 MHz sample rate
        return samples * np.exp(1j * 2 * np.pi * offset * t)
    
    def add_phase_noise(self, samples):
        """Add phase noise"""
        phase_noise_std = np.random.uniform(0.01, 0.1)
        phase_noise = np.random.normal(0, phase_noise_std, len(samples))
        return samples * np.exp(1j * phase_noise)
    
    def time_shift(self, samples):
        """Random time shift"""
        shift = np.random.randint(-100, 100)
        return np.roll(samples, shift)
    
    def amplitude_scale(self, samples):
        """Random amplitude scaling"""
        scale = np.random.uniform(0.5, 1.5)
        return samples * scale
    
    def sample_rate_conversion(self, samples):
        """Resample to simulate different sample rates"""
        from scipy import signal
        rates = [1e6, 2e6, 5e6, 10e6]
        target_rate = np.random.choice(rates)
        current_rate = 2e6
        num_samples = int(len(samples) * target_rate / current_rate)
        return signal.resample(samples, num_samples)
Feature Engineering
Feature Extraction Pipeline
python
# models/training/features/feature_extractor.py
"""Comprehensive feature extraction for drone signals"""

import numpy as np
from scipy import signal, stats
from scipy.fft import fft, fftfreq
from scipy.signal import spectrogram, welch

class FeatureExtractor:
    """Extract features from IQ samples for ML"""
    
    def __init__(self, config):
        self.config = config
        self.feature_names = []
        
    def extract_all_features(self, iq_samples):
        """Extract complete feature set"""
        features = {}
        
        # Time domain features
        features.update(self._time_domain_features(iq_samples))
        
        # Frequency domain features
        features.update(self._frequency_domain_features(iq_samples))
        
        # Cyclostationary features
        features.update(self._cyclostationary_features(iq_samples))
        
        # Statistical features
        features.update(self._statistical_features(iq_samples))
        
        # Modulation-specific features
        features.update(self._modulation_features(iq_samples))
        
        return features
    
    def _time_domain_features(self, samples):
        """Extract time domain features"""
        amplitude = np.abs(samples)
        phase = np.angle(samples)
        I = np.real(samples)
        Q = np.imag(samples)
        
        features = {
            'rms_power': 10 * np.log10(np.mean(amplitude**2)),
            'peak_power': 10 * np.log10(np.max(amplitude**2)),
            'peak_to_average_ratio': np.max(amplitude) / (np.mean(amplitude) + 1e-12),
            'crest_factor': np.max(amplitude) / (np.sqrt(np.mean(amplitude**2)) + 1e-12),
            
            'kurtosis': stats.kurtosis(amplitude),
            'skewness': stats.skew(amplitude),
            'variance': np.var(amplitude),
            'std_dev': np.std(amplitude),
            
            'zero_crossing_rate': self._zero_crossing_rate(phase),
            'phase_variance': np.var(phase),
            'phase_range': np.max(phase) - np.min(phase),
            
            'iq_correlation': np.corrcoef(I, Q)[0, 1],
            'iq_power_ratio': np.mean(I**2) / (np.mean(Q**2) + 1e-12),
        }
        
        self.feature_names.extend(features.keys())
        return features
    
    def _frequency_domain_features(self, samples):
        """Extract frequency domain features"""
        # Compute PSD using Welch's method
        f, psd = welch(samples, fs=2e6, nperseg=256)
        
        # Normalize PSD
        psd_norm = psd / (np.sum(psd) + 1e-12)
        
        # Spectral centroid
        centroid = np.sum(f * psd_norm)
        
        # Spectral spread
        spread = np.sqrt(np.sum(((f - centroid) ** 2) * psd_norm))
        
        # Spectral flatness (Wiener entropy)
        geometric_mean = np.exp(np.mean(np.log(psd + 1e-12)))
        arithmetic_mean = np.mean(psd)
        flatness = geometric_mean / (arithmetic_mean + 1e-12)
        
        # Spectral rolloff (95% energy)
        cumsum = np.cumsum(psd)
        rolloff_idx = np.where(cumsum >= 0.95 * cumsum[-1])[0]
        rolloff = f[rolloff_idx[0]] if len(rolloff_idx) > 0 else f[-1]
        
        # Peak detection
        peaks, peak_props = signal.find_peaks(psd, height=np.max(psd)*0.5)
        
        features = {
            'spectral_centroid': centroid,
            'spectral_spread': spread,
            'spectral_flatness': flatness,
            'spectral_rolloff': rolloff,
            'spectral_entropy': stats.entropy(psd + 1e-12),
            'num_spectral_peaks': len(peaks),
            'max_peak_height': np.max(psd[peaks]) if len(peaks) > 0 else 0,
            'peak_frequency_spacing': np.mean(np.diff(f[peaks])) if len(peaks) > 1 else 0,
            'occupied_bandwidth': self._occupied_bandwidth(f, psd),
            'power_ratio_25_75': self._band_power_ratio(psd, [0.25, 0.75]),
        }
        
        self.feature_names.extend(features.keys())
        return features
    
    def _cyclostationary_features(self, samples):
        """Extract cyclostationary features"""
        # Compute cyclic autocorrelation
        alpha = 0.001  # Cycle frequency
        n = len(samples)
        
        cyclic_autocorr = np.correlate(
            samples * np.exp(-1j * 2 * np.pi * alpha * np.arange(n)),
            samples,
            mode='full'
        )
        
        # Normalize
        cyclic_autocorr_norm = np.abs(cyclic_autocorr) / (np.max(np.abs(cyclic_autocorr)) + 1e-12)
        
        # Spectral coherence
        f, Pxx = welch(samples, fs=2e6)
        f, Pyy = welch(samples, fs=2e6)
        f, Pxy = welch(samples, samples, fs=2e6)
        
        coherence = np.abs(Pxy) ** 2 / (Pxx * Pyy + 1e-12)
        
        features = {
            'cyclic_autocorr_max': np.max(cyclic_autocorr_norm),
            'cyclic_autocorr_std': np.std(cyclic_autocorr_norm),
            'cyclic_autocorr_peak_to_avg': np.max(cyclic_autocorr_norm) / (np.mean(cyclic_autocorr_norm) + 1e-12),
            'max_coherence': np.max(coherence),
            'mean_coherence': np.mean(coherence),
            'coherence_entropy': stats.entropy(coherence + 1e-12),
        }
        
        self.feature_names.extend(features.keys())
        return features
    
    def _statistical_features(self, samples):
        """Extract higher-order statistical features"""
        I = np.real(samples)
        Q = np.imag(samples)
        
        features = {
            'I_mean': np.mean(I),
            'I_std': np.std(I),
            'I_var': np.var(I),
            'I_kurtosis': stats.kurtosis(I),
            'I_skewness': stats.skew(I),
            
            'Q_mean': np.mean(Q),
            'Q_std': np.std(Q),
            'Q_var': np.var(Q),
            'Q_kurtosis': stats.kurtosis(Q),
            'Q_skewness': stats.skew(Q),
            
            'constellation_dispersion': np.std(np.abs(samples - np.mean(samples))),
            'constellation_radius_std': np.std(np.abs(samples)),
        }
        
        # Higher-order cumulants (for modulation classification)
        m20 = np.mean(samples ** 2)
        m21 = np.mean(np.abs(samples) ** 2)
        m40 = np.mean(samples ** 4)
        m41 = np.mean(samples ** 2 * np.conj(samples))
        m42 = np.mean(np.abs(samples) ** 4)
        
        features.update({
            'c20': m20,
            'c21': m21,
            'c40': m40 - 3 * m20 ** 2,
            'c41': m41 - 3 * m20 * m21,
            'c42': m42 - abs(m20) ** 2 - 2 * m21 ** 2,
        })
        
        self.feature_names.extend(features.keys())
        return features
    
    def _modulation_features(self, samples):
        """Extract modulation-specific features"""
        # Instantaneous features
        amplitude = np.abs(samples)
        phase = np.angle(samples)
        inst_freq = np.diff(np.unwrap(phase)) * 2e6 / (2 * np.pi)
        
        features = {
            'gamma_max': np.max(np.abs(np.diff(amplitude))) / np.mean(amplitude),
            'sigma_ap': np.std(phase),
            'sigma_aa': np.std(amplitude) / np.mean(amplitude),
            'sigma_af': np.std(inst_freq),
            'freq_centroid': np.mean(inst_freq),
            'freq_spread': np.std(inst_freq),
        }
        
        self.feature_names.extend(features.keys())
        return features
    
    def _zero_crossing_rate(self, phase):
        """Calculate zero crossing rate"""
        phase_diff = np.diff(np.unwrap(phase))
        zero_crossings = np.where(np.diff(np.sign(phase_diff)))[0]
        return len(zero_crossings) / len(phase_diff)
    
    def _occupied_bandwidth(self, frequencies, psd, power_percent=0.99):
        """Calculate occupied bandwidth containing specified power percentage"""
        cumsum = np.cumsum(psd)
        total_power = cumsum[-1]
        
        # Find indices where cumulative power crosses (1-power_percent)/2 and (1+power_percent)/2
        lower_idx = np.where(cumsum >= total_power * (1 - power_percent) / 2)[0]
        upper_idx = np.where(cumsum >= total_power * (1 + power_percent) / 2)[0]
        
        if len(lower_idx) > 0 and len(upper_idx) > 0:
            return frequencies[upper_idx[0]] - frequencies[lower_idx[0]]
        return 0
    
    def _band_power_ratio(self, psd, percentiles):
        """Calculate ratio of power in different frequency bands"""
        cumsum = np.cumsum(psd)
        total_power = cumsum[-1]
        
        lower_idx = np.where(cumsum >= total_power * percentiles[0])[0]
        upper_idx = np.where(cumsum >= total_power * percentiles[1])[0]
        
        if len(lower_idx) > 0 and len(upper_idx) > 0:
            power_in_band = cumsum[upper_idx[0]] - cumsum[lower_idx[0]]
            return power_in_band / total_power
        return 0
    
    def get_feature_names(self):
        """Get list of all feature names"""
        return self.feature_names
Model Architectures
CNN for IQ Classification
python
# models/training/models/cnn_model.py
"""Convolutional Neural Network for IQ classification"""

import tensorflow as tf
from tensorflow.keras import layers, models

class CNNClassifier(tf.keras.Model):
    """CNN for raw IQ classification"""
    
    def __init__(self, num_classes=10, input_shape=(1024, 2)):
        super().__init__()
        
        # Input shape: (batch, samples, 2) where 2 = [I, Q]
        self.conv1 = layers.Conv1D(64, 3, activation='relu', padding='same')
        self.bn1 = layers.BatchNormalization()
        self.pool1 = layers.MaxPooling1D(2)
        
        self.conv2 = layers.Conv1D(128, 3, activation='relu', padding='same')
        self.bn2 = layers.BatchNormalization()
        self.pool2 = layers.MaxPooling1D(2)
        
        self.conv3 = layers.Conv1D(256, 3, activation='relu', padding='same')
        self.bn3 = layers.BatchNormalization()
        self.pool3 = layers.GlobalAveragePooling1D()
        
        self.dropout = layers.Dropout(0.5)
        self.dense1 = layers.Dense(256, activation='relu')
        self.dense2 = layers.Dense(128, activation='relu')
        self.output_layer = layers.Dense(num_classes, activation='softmax')
        
    def call(self, inputs, training=False):
        x = self.conv1(inputs)
        x = self.bn1(x, training=training)
        x = self.pool1(x)
        
        x = self.conv2(x)
        x = self.bn2(x, training=training)
        x = self.pool2(x)
        
        x = self.conv3(x)
        x = self.bn3(x, training=training)
        x = self.pool3(x)
        
        x = self.dropout(x, training=training)
        x = self.dense1(x)
        x = self.dense2(x)
        
        return self.output_layer(x)
    
    def build_model(self, input_shape):
        """Build model with input shape"""
        inputs = tf.keras.Input(shape=input_shape)
        outputs = self.call(inputs)
        return tf.keras.Model(inputs, outputs)
LSTM for Temporal Patterns
python
# models/training/models/lstm_model.py
"""LSTM model for temporal signal patterns"""

class LSTMClassifier(tf.keras.Model):
    """LSTM for sequential IQ data"""
    
    def __init__(self, num_classes=10, lstm_units=128):
        super().__init__()
        
        self.lstm1 = layers.LSTM(lstm_units, return_sequences=True)
        self.lstm2 = layers.LSTM(lstm_units // 2, return_sequences=False)
        self.dropout = layers.Dropout(0.3)
        self.dense1 = layers.Dense(64, activation='relu')
        self.output_layer = layers.Dense(num_classes, activation='softmax')
        
    def call(self, inputs, training=False):
        x = self.lstm1(inputs)
        x = self.dropout(x, training=training)
        x = self.lstm2(x)
        x = self.dense1(x)
        return self.output_layer(x)
Random Forest (Traditional ML)
python
# models/training/models/rf_model.py
"""Random Forest classifier for feature-based classification"""

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV

class RandomForestDroneClassifier:
    """Random Forest classifier with hyperparameter tuning"""
    
    def __init__(self):
        self.model = None
        self.param_grid = {
            'n_estimators': [100, 200, 300],
            'max_depth': [10, 20, 30, None],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4],
            'max_features': ['sqrt', 'log2']
        }
        
    def train(self, X_train, y_train, optimize=False):
        """Train Random Forest model"""
        
        if optimize:
            # Hyperparameter optimization
            rf = RandomForestClassifier(random_state=42, n_jobs=-1)
            grid_search = GridSearchCV(
                rf, self.param_grid,
                cv=5, scoring='f1_macro',
                n_jobs=-1, verbose=1
            )
            grid_search.fit(X_train, y_train)
            self.model = grid_search.best_estimator_
            print(f"Best parameters: {grid_search.best_params_}")
        else:
            # Default parameters
            self.model = RandomForestClassifier(
                n_estimators=200,
                max_depth=20,
                min_samples_split=5,
                random_state=42,
                n_jobs=-1
            )
            self.model.fit(X_train, y_train)
            
        return self.model
    
    def predict(self, X):
        """Predict drone types"""
        return self.model.predict(X)
    
    def predict_proba(self, X):
        """Get prediction probabilities"""
        return self.model.predict_proba(X)
    
    def get_feature_importance(self, feature_names):
        """Get feature importance scores"""
        importance = dict(zip(feature_names, self.model.feature_importances_))
        return sorted(importance.items(), key=lambda x: x[1], reverse=True)
XGBoost (Gradient Boosting)
python
# models/training/models/xgboost_model.py
"""XGBoost classifier for high performance"""

import xgboost as xgb

class XGBoostDroneClassifier:
    """XGBoost classifier with GPU support"""
    
    def __init__(self, use_gpu=True):
        self.use_gpu = use_gpu
        self.model = None
        
    def train(self, X_train, y_train, X_val, y_val):
        """Train XGBoost model"""
        
        params = {
            'objective': 'multi:softprob',
            'num_class': len(np.unique(y_train)),
            'eval_metric': 'mlogloss',
            'max_depth': 8,
            'learning_rate': 0.05,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'n_estimators': 500,
            'early_stopping_rounds': 20,
            'random_state': 42
        }
        
        if self.use_gpu:
            params['tree_method'] = 'gpu_hist'
            params['predictor'] = 'gpu_predictor'
            
        # Create DMatrix
        dtrain = xgb.DMatrix(X_train, label=y_train)
        dval = xgb.DMatrix(X_val, label=y_val)
        
        # Train with early stopping
        self.model = xgb.train(
            params,
            dtrain,
            evals=[(dtrain, 'train'), (dval, 'val')],
            verbose_eval=50
        )
        
        return self.model
    
    def predict(self, X):
        """Predict drone types"""
        dtest = xgb.DMatrix(X)
        predictions = self.model.predict(dtest)
        return np.argmax(predictions, axis=1)
Training Pipeline
Complete Training Script
python
# scripts/train_model.py
"""Complete ML training pipeline"""

import argparse
import yaml
import numpy as np
from pathlib import Path
import joblib
from datetime import datetime

from models.training.features.feature_extractor import FeatureExtractor
from models.training.models.xgboost_model import XGBoostDroneClassifier
from models.training.models.rf_model import RandomForestDroneClassifier
from models.training.models.cnn_model import CNNClassifier

class ModelTrainer:
    """Complete model training pipeline"""
    
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        self.output_dir = Path(self.config['output_dir'])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.feature_extractor = FeatureExtractor(self.config['features'])
        
    def load_data(self):
        """Load and prepare dataset"""
        print("Loading dataset...")
        
        # Load preprocessed features if available
        if Path(self.config['data']['processed_dir']).exists():
            X_train = np.load(f"{self.config['data']['processed_dir']}/X_train.npy")
            X_val = np.load(f"{self.config['data']['processed_dir']}/X_val.npy")
            X_test = np.load(f"{self.config['data']['processed_dir']}/X_test.npy")
            y_train = np.load(f"{self.config['data']['processed_dir']}/y_train.npy")
            y_val = np.load(f"{self.config['data']['processed_dir']}/y_val.npy")
            y_test = np.load(f"{self.config['data']['processed_dir']}/y_test.npy")
        else:
            # Process raw data
            X_train, y_train, X_val, y_val, X_test, y_test = self._process_raw_data()
            
        print(f"Training samples: {len(X_train)}")
        print(f"Validation samples: {len(X_val)}")
        print(f"Test samples: {len(X_test)}")
        print(f"Number of features: {X_train.shape[1]}")
        
        return {
            'X_train': X_train,
            'y_train': y_train,
            'X_val': X_val,
            'y_val': y_val,
            'X_test': X_test,
            'y_test': y_test
        }
    
    def create_model(self, model_type, num_features, num_classes):
        """Create model based on configuration"""
        
        if model_type == 'xgboost':
            model = XGBoostDroneClassifier(use_gpu=self.config['gpu'])
        elif model_type == 'random_forest':
            model = RandomForestDroneClassifier()
        elif model_type == 'cnn':
            model = CNNClassifier(num_classes=num_classes)
        else:
            raise ValueError(f"Unknown model type: {model_type}")
            
        return model
    
    def train(self, data, model):
        """Train the model"""
        print(f"\nTraining {self.config['model']['type']} model...")
        
        X_train, y_train = data['X_train'], data['y_train']
        X_val, y_val = data['X_val'], data['y_val']
        
        # Train model
        if isinstance(model, XGBoostDroneClassifier):
            model.train(X_train, y_train, X_val, y_val)
        elif isinstance(model, RandomForestDroneClassifier):
            model.train(X_train, y_train, optimize=self.config['model']['optimize'])
        elif isinstance(model, CNNClassifier):
            self._train_cnn(model, X_train, y_train, X_val, y_val)
            
        return model
    
    def evaluate(self, model, X_test, y_test):
        """Evaluate model performance"""
        print("\nEvaluating model...")
        
        from sklearn.metrics import (
            accuracy_score, precision_score, recall_score,
            f1_score, confusion_matrix, classification_report
        )
        
        # Make predictions
        y_pred = model.predict(X_test)
        
        # Calculate metrics
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, average='weighted'),
            'recall': recall_score(y_test, y_pred, average='weighted'),
            'f1_score': f1_score(y_test, y_pred, average='weighted'),
            'confusion_matrix': confusion_matrix(y_test, y_pred).tolist()
        }
        
        print(f"Accuracy: {metrics['accuracy']:.4f}")
        print(f"Precision: {metrics['precision']:.4f}")
        print(f"Recall: {metrics['recall']:.4f}")
        print(f"F1 Score: {metrics['f1_score']:.4f}")
        
        # Full classification report
        report = classification_report(y_test, y_pred, output_dict=True)
        metrics['classification_report'] = report
        
        # Save metrics
        with open(self.output_dir / 'metrics.json', 'w') as f:
            json.dump(metrics, f, indent=2)
            
        return metrics
    
    def save_model(self, model):
        """Save trained model and artifacts"""
        print(f"\nSaving model to {self.output_dir}...")
        
        # Save model
        model_path = self.output_dir / 'classifier.pkl'
        joblib.dump(model, model_path)
        
        # Save feature names
        feature_names = self.feature_extractor.get_feature_names()
        with open(self.output_dir / 'feature_names.json', 'w') as f:
            json.dump(feature_names, f, indent=2)
        
        # Save configuration
        with open(self.output_dir / 'training_config.yaml', 'w') as f:
            yaml.dump(self.config, f)
            
        # Save scaler (if fitted)
        if hasattr(self, 'scaler'):
            joblib.dump(self.scaler, self.output_dir / 'scaler.pkl')
            
        print("Model saved successfully!")
        
    def run(self):
        """Run complete training pipeline"""
        print("="*60)
        print("DRONE DETECTOR - ML MODEL TRAINING")
        print("="*60)
        
        # Load data
        data = self.load_data()
        
        # Create model
        num_classes = len(np.unique(data['y_train']))
        model = self.create_model(
            self.config['model']['type'],
            data['X_train'].shape[1],
            num_classes
        )
        
        # Train
        start_time = datetime.now()
        model = self.train(data, model)
        training_time = (datetime.now() - start_time).total_seconds()
        print(f"Training completed in {training_time:.2f} seconds")
        
        # Evaluate
        metrics = self.evaluate(model, data['X_test'], data['y_test'])
        
        # Save model
        self.save_model(model)
        
        # Save training metadata
        metadata = {
            'training_time_seconds': training_time,
            'model_type': self.config['model']['type'],
            'num_features': data['X_train'].shape[1],
            'num_classes': num_classes,
            'train_samples': len(data['X_train']),
            'val_samples': len(data['X_val']),
            'test_samples': len(data['X_test']),
            'metrics': metrics,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(self.output_dir / 'training_metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
            
        print("\n✅ Training pipeline completed successfully!")
        return model, metrics
    
    def _train_cnn(self, model, X_train, y_train, X_val, y_val):
        """Train CNN model"""
        import tensorflow as tf
        
        # Reshape for CNN (samples, features, channels)
        X_train_cnn = X_train.reshape(X_train.shape[0], X_train.shape[1], 1)
        X_val_cnn = X_val.reshape(X_val.shape[0], X_val.shape[1], 1)
        
        # Convert labels to categorical
        y_train_cat = tf.keras.utils.to_categorical(y_train)
        y_val_cat = tf.keras.utils.to_categorical(y_val)
        
        # Compile model
        model.compile(
            optimizer=tf.keras.optimizers.Adam(self.config['model']['learning_rate']),
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        # Train
        model.fit(
            X_train_cnn, y_train_cat,
            validation_data=(X_val_cnn, y_val_cat),
            epochs=self.config['model']['epochs'],
            batch_size=self.config['model']['batch_size'],
            verbose=1
        )

def main():
    parser = argparse.ArgumentParser(description='Train drone detection ML model')
    parser.add_argument('--config', type=str, default='config/training_config.yaml',
                       help='Training configuration file')
    parser.add_argument('--gpu', action='store_true', help='Enable GPU training')
    parser.add_argument('--model-type', choices=['xgboost', 'random_forest', 'cnn'],
                       help='Override model type')
    parser.add_argument('--epochs', type=int, help='Number of training epochs')
    
    args = parser.parse_args()
    
    # Load and update config
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)
        
    if args.gpu:
        config['gpu'] = True
    if args.model_type:
        config['model']['type'] = args.model_type
    if args.epochs:
        config['model']['epochs'] = args.epochs
        
    # Run training
    trainer = ModelTrainer(args.config)
    trainer.run()

if __name__ == "__main__":
    main()
Model Evaluation
Evaluation Metrics
python
# scripts/evaluate_model.py
"""Comprehensive model evaluation"""

import numpy as np
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report,
    precision_recall_curve, roc_curve
)
import matplotlib.pyplot as plt
import seaborn as sns

class ModelEvaluator:
    """Evaluate trained model performance"""
    
    def __init__(self, model, test_data, class_names):
        self.model = model
        self.X_test, self.y_test = test_data
        self.class_names = class_names
        
    def evaluate_all(self):
        """Run all evaluation metrics"""
        
        # Get predictions
        y_pred = self.model.predict(self.X_test)
        y_pred_proba = self.model.predict_proba(self.X_test)
        
        # Basic metrics
        metrics = {
            'accuracy': accuracy_score(self.y_test, y_pred),
            'precision_macro': precision_score(self.y_test, y_pred, average='macro'),
            'precision_weighted': precision_score(self.y_test, y_pred, average='weighted'),
            'recall_macro': recall_score(self.y_test, y_pred, average='macro'),
            'recall_weighted': recall_score(self.y_test, y_pred, average='weighted'),
            'f1_macro': f1_score(self.y_test, y_pred, average='macro'),
            'f1_weighted': f1_score(self.y_test, y_pred, average='weighted'),
        }
        
        # Per-class metrics
        per_class = {}
        for i, class_name in enumerate(self.class_names):
            y_true_binary = (self.y_test == i).astype(int)
            y_pred_binary = (y_pred == i).astype(int)
            
            per_class[class_name] = {
                'precision': precision_score(y_true_binary, y_pred_binary, zero_division=0),
                'recall': recall_score(y_true_binary, y_pred_binary, zero_division=0),
                'f1': f1_score(y_true_binary, y_pred_binary, zero_division=0),
                'support': np.sum(y_true_binary),
                'roc_auc': roc_auc_score(y_true_binary, y_pred_proba[:, i])
            }
            
        metrics['per_class'] = per_class
        
        # Log loss (cross-entropy)
        from sklearn.metrics import log_loss
        metrics['log_loss'] = log_loss(self.y_test, y_pred_proba)
        
        # Confusion matrix
        metrics['confusion_matrix'] = confusion_matrix(self.y_test, y_pred).tolist()
        
        # Detailed classification report
        metrics['classification_report'] = classification_report(
            self.y_test, y_pred,
            target_names=self.class_names,
            output_dict=True
        )
        
        return metrics
    
    def plot_confusion_matrix(self, save_path=None):
        """Plot confusion matrix"""
        cm = confusion_matrix(self.y_test, self.model.predict(self.X_test))
        
        plt.figure(figsize=(10, 8))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                   xticklabels=self.class_names,
                   yticklabels=self.class_names)
        plt.title('Confusion Matrix')
        plt.ylabel('True Label')
        plt.xlabel('Predicted Label')
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.show()
        
    def plot_roc_curves(self, save_path=None):
        """Plot ROC curves for each class"""
        y_pred_proba = self.model.predict_proba(self.X_test)
        
        plt.figure(figsize=(10, 8))
        
        for i, class_name in enumerate(self.class_names):
            y_true_binary = (self.y_test == i).astype(int)
            fpr, tpr, _ = roc_curve(y_true_binary, y_pred_proba[:, i])
            auc = roc_auc_score(y_true_binary, y_pred_proba[:, i])
            plt.plot(fpr, tpr, label=f'{class_name} (AUC = {auc:.3f})')
            
        plt.plot([0, 1], [0, 1], 'k--', label='Random')
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('ROC Curves by Drone Type')
        plt.legend()
        plt.grid(True)
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.show()
        
    def plot_precision_recall_curves(self, save_path=None):
        """Plot precision-recall curves"""
        y_pred_proba = self.model.predict_proba(self.X_test)
        
        plt.figure(figsize=(10, 8))
        
        for i, class_name in enumerate(self.class_names):
            y_true_binary = (self.y_test == i).astype(int)
            precision, recall, _ = precision_recall_curve(
                y_true_binary, y_pred_proba[:, i]
            )
            plt.plot(recall, precision, label=class_name)
            
        plt.xlabel('Recall')
        plt.ylabel('Precision')
        plt.title('Precision-Recall Curves by Drone Type')
        plt.legend()
        plt.grid(True)
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.show()
        
    def generate_report(self, output_dir):
        """Generate HTML evaluation report"""
        metrics = self.evaluate_all()
        
        # Create HTML report
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Model Evaluation Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                .metric {{ font-size: 24px; font-weight: bold; margin: 10px 0; }}
                .good {{ color: green; }}
                .bad {{ color: red; }}
            </style>
        </head>
        <body>
            <h1>Drone Detector - Model Evaluation Report</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <h2>Overall Metrics</h2>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Accuracy</td><td>{metrics['accuracy']:.4f}</td></tr>
                <tr><td>Macro F1 Score</td><td>{metrics['f1_macro']:.4f}</td></tr>
                <tr><td>Weighted F1 Score</td><td>{metrics['f1_weighted']:.4f}</td></tr>
                <tr><td>Log Loss</td><td>{metrics['log_loss']:.4f}</td></tr>
            </table>
            
            <h2>Per-Class Performance</h2>
            <table>
                <tr><th>Drone Type</th><th>Precision</th><th>Recall</th><th>F1 Score</th><th>Support</th><th>ROC AUC</th></tr>
        """
        
        for class_name, class_metrics in metrics['per_class'].items():
            html += f"""
                <tr>
                    <td>{class_name}</td>
                    <td>{class_metrics['precision']:.4f}</td>
                    <td>{class_metrics['recall']:.4f}</td>
                    <td>{class_metrics['f1']:.4f}</td>
                    <td>{class_metrics['support']}</td>
                    <td>{class_metrics['roc_auc']:.4f}</td>
                </tr>
            """
            
        html += """
            </table>
            
            <h2>Confusion Matrix</h2>
            <!-- Include image reference -->
            <img src="confusion_matrix.png" alt="Confusion Matrix" style="max-width: 100%;">
            
            <h2>ROC Curves</h2>
            <img src="roc_curves.png" alt="ROC Curves" style="max-width: 100%;">
            
            <h2>Precision-Recall Curves</h2>
            <img src="pr_curves.png" alt="Precision-Recall Curves" style="max-width: 100%;">
        </body>
        </html>
        """
        
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        with open(output_dir / 'evaluation_report.html', 'w') as f:
            f.write(html)
            
        # Save plots
        self.plot_confusion_matrix(output_dir / 'confusion_matrix.png')
        self.plot_roc_curves(output_dir / 'roc_curves.png')
        self.plot_precision_recall_curves(output_dir / 'pr_curves.png')
        
        # Save metrics as JSON
        with open(output_dir / 'evaluation_metrics.json', 'w') as f:
            json.dump(metrics, f, indent=2)
            
        print(f"Evaluation report saved to {output_dir}")
Model Optimization
Hyperparameter Tuning
python
# scripts/hyperparam_tuning.py
"""Hyperparameter optimization using Optuna"""

import optuna
from optuna.samplers import TPESampler
from optuna.pruners import MedianPruner
from sklearn.model_selection import cross_val_score

class HyperparameterOptimizer:
    """Optimize model hyperparameters"""
    
    def __init__(self, X_train, y_train, n_trials=100):
        self.X_train = X_train
        self.y_train = y_train
        self.n_trials = n_trials
        
    def optimize_xgboost(self):
        """Optimize XGBoost parameters"""
        
        def objective(trial):
            params = {
                'max_depth': trial.suggest_int('max_depth', 3, 12),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'n_estimators': trial.suggest_int('n_estimators', 100, 1000),
                'subsample': trial.suggest_float('subsample', 0.5, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                'gamma': trial.suggest_float('gamma', 0, 5),
                'reg_alpha': trial.suggest_float('reg_alpha', 0, 2),
                'reg_lambda': trial.suggest_float('reg_lambda', 0, 2),
            }
            
            import xgboost as xgb
            model = xgb.XGBClassifier(**params, random_state=42)
            
            # Cross-validation score
            scores = cross_val_score(model, self.X_train, self.y_train, 
                                    cv=5, scoring='f1_macro')
            return scores.mean()
        
        study = optuna.create_study(
            direction='maximize',
            sampler=TPESampler(),
            pruner=MedianPruner()
        )
        
        study.optimize(objective, n_trials=self.n_trials)
        
        print("Best parameters:", study.best_params)
        print("Best score:", study.best_value)
        
        return study.best_params
    
    def optimize_random_forest(self):
        """Optimize Random Forest parameters"""
        
        def objective(trial):
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 100, 500),
                'max_depth': trial.suggest_int('max_depth', 5, 50),
                'min_samples_split': trial.suggest_int('min_samples_split', 2, 20),
                'min_samples_leaf': trial.suggest_int('min_samples_leaf', 1, 10),
                'max_features': trial.suggest_categorical('max_features', 
                                                          ['sqrt', 'log2', None])
            }
            
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(**params, n_jobs=-1, random_state=42)
            
            scores = cross_val_score(model, self.X_train, self.y_train,
                                    cv=5, scoring='f1_macro')
            return scores.mean()
        
        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=self.n_trials)
        
        return study.best_params
Model Deployment
Export for Production
python
# scripts/export_model.py
"""Export trained model for production"""

import joblib
import json
import onnx
import tf2onnx
from pathlib import Path

class ModelExporter:
    """Export model to production formats"""
    
    def __init__(self, model, output_dir):
        self.model = model
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def export_pickle(self):
        """Export as pickle file"""
        output_path = self.output_dir / 'model.pkl'
        joblib.dump(self.model, output_path)
        print(f"Pickle model saved to {output_path}")
        
    def export_onnx(self, input_shape):
        """Export to ONNX format"""
        import torch
        
        if isinstance(self.model, torch.nn.Module):
            dummy_input = torch.randn(input_shape)
            torch.onnx.export(
                self.model, dummy_input,
                self.output_dir / 'model.onnx',
                input_names=['input'],
                output_names=['output'],
                dynamic_axes={'input': {0: 'batch_size'},
                             'output': {0: 'batch_size'}}
            )
            print(f"ONNX model saved to {self.output_dir / 'model.onnx'}")
            
    def export_tensorflow(self):
        """Export to TensorFlow SavedModel format"""
        import tensorflow as tf
        
        if isinstance(self.model, tf.keras.Model):
            tf.saved_model.save(self.model, self.output_dir / 'saved_model')
            print(f"TensorFlow model saved to {self.output_dir / 'saved_model'}")
            
    def export_metadata(self, metadata):
        """Export model metadata"""
        with open(self.output_dir / 'model_metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
            
    def create_version_file(self, version):
        """Create version information file"""
        version_info = {
            'version': version,
            'export_date': datetime.now().isoformat(),
            'model_type': type(self.model).__name__,
            'framework': self._detect_framework()
        }
        
        with open(self.output_dir / 'version.json', 'w') as f:
            json.dump(version_info, f, indent=2)
Continuous Training Pipeline
Automated Retraining
yaml
# .github/workflows/ml_retrain.yml
name: ML Model Retraining

on:
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday at 2 AM
  workflow_dispatch:  # Manual trigger

jobs:
  retrain:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
          
      - name: Download latest dataset
        run: |
          aws s3 sync s3://drone-datasets/latest/ data/raw/
          
      - name: Train model
        run: |
          python scripts/train_model.py \
            --config config/training_config.yaml \
            --gpu
          
      - name: Evaluate model
        run: |
          python scripts/evaluate_model.py \
            --model models/classifier.pkl \
            --output evaluation/
          
      - name: Compare with production model
        run: |
          python scripts/compare_models.py \
            --new models/classifier.pkl \
            --prod models/production/classifier.pkl \
            --threshold 0.05
          
      - name: Deploy if improved
        if: success()
        run: |
          aws s3 sync models/ s3://drone-models/latest/
          aws lambda update-function-code --function-name drone-classifier \
            --s3-bucket drone-models --s3-key latest/classifier.pkl
Troubleshooting
Common Training Issues
python
# scripts/training_diagnostics.py
"""Diagnose training issues"""

class TrainingDiagnostics:
    """Check for common training problems"""
    
    def check_class_imbalance(self, y_train):
        """Check for class imbalance"""
        from collections import Counter
        
        counts = Counter(y_train)
        min_count = min(counts.values())
        max_count = max(counts.values())
        
        imbalance_ratio = max_count / min_count
        
        if imbalance_ratio > 10:
            print(f"⚠️ Severe class imbalance detected: {imbalance_ratio:.1f}:1")
            print("Consider using class weights or oversampling")
        elif imbalance_ratio > 3:
            print(f"⚠️ Moderate class imbalance: {imbalance_ratio:.1f}:1")
        else:
            print("✓ Classes are balanced")
            
        return counts
    
    def check_feature_scale(self, X_train):
        """Check feature scaling"""
        means = np.mean(X_train, axis=0)
        stds = np.std(X_train, axis=0)
        
        if np.max(stds) / np.min(stds + 1e-12) > 100:
            print("⚠️ Features have vastly different scales")
            print("Consider applying StandardScaler")
        else:
            print("✓ Feature scales are reasonable")
            
    def check_missing_values(self, X_train):
        """Check for missing values"""
        missing = np.isnan(X_train).sum()
        
        if missing > 0:
            print(f"⚠️ {missing} missing values detected")
        else:
            print("✓ No missing values")
            
    def check_memory_usage(self, X_train):
        """Check memory usage"""
        memory_mb = X_train.nbytes / 1024 / 1024
        
        if memory_mb > 1000:
            print(f"⚠️ High memory usage: {memory_mb:.1f} MB")
            print("Consider using batch processing or dimensionality reduction")
        else:
            print(f"✓ Memory usage: {memory_mb:.1f} MB")
This comprehensive ML training guide covers the entire machine learning pipeline from data collection and feature engineering through model training, evaluation, optimization, and deployment for the Drone Detector system.
