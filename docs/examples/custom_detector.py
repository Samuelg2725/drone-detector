#!/usr/bin/env python3
"""
Custom Detector Example for Drone Detector System

This example demonstrates how to create custom detection algorithms,
signal processing pipelines, and integrate them with the Drone Detector system.

Topics covered:
    - Custom signal processing algorithms
    - Implementing custom detectors
    - Feature extraction for specific drone types
    - Integration with the detection pipeline
    - Real-time custom detection

Prerequisites:
    - Drone Detector system running
    - Understanding of signal processing concepts
    - NumPy/SciPy knowledge

Usage:
    python custom_detector.py
"""

import numpy as np
from scipy import signal
from scipy.fft import fft, ifft
from scipy.signal import spectrogram, welch, find_peaks
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import asyncio
import json
from datetime import datetime

# ============================================================================
# Custom Signal Processing Algorithms
# ============================================================================

class CustomSignalProcessor:
    """Custom signal processing algorithms for drone detection"""
    
    def __init__(self, sample_rate: float = 2e6):
        self.sample_rate = sample_rate
        
    def advanced_fft(self, samples: np.ndarray, window: str = 'blackman') -> Tuple[np.ndarray, np.ndarray]:
        """
        Advanced FFT with multiple windowing options
        
        Args:
            samples: IQ samples
            window: Window type (hann, hamming, blackman, kaiser)
            
        Returns:
            frequencies: Frequency array
            spectrum: Power spectrum
        """
        n = len(samples)
        
        # Select window function
        if window == 'hann':
            win = np.hanning(n)
        elif window == 'hamming':
            win = np.hamming(n)
        elif window == 'blackman':
            win = np.blackman(n)
        elif window == 'kaiser':
            win = np.kaiser(n, beta=14)
        else:
            win = np.ones(n)
            
        # Apply window and compute FFT
        windowed = samples * win
        
        # Compute FFT with zero-padding for better resolution
        nfft = 2 ** int(np.ceil(np.log2(n)))
        spectrum = fft(windowed, n=nfft)
        spectrum = np.fft.fftshift(spectrum)
        
        # Compute frequencies
        frequencies = np.fft.fftshift(np.fft.fftfreq(nfft, 1/self.sample_rate))
        
        # Power spectrum (dB)
        power = 20 * np.log10(np.abs(spectrum) + 1e-12)
        
        return frequencies, power
    
    def adaptive_threshold(self, spectrum: np.ndarray, 
                           sensitivity: float = 2.0) -> np.ndarray:
        """
        Adaptive threshold based on local statistics
        
        Args:
            spectrum: Power spectrum
            sensitivity: Threshold sensitivity (higher = less sensitive)
            
        Returns:
            threshold: Adaptive threshold array
        """
        window_size = 51
        threshold = np.zeros_like(spectrum)
        
        # Calculate moving median and standard deviation
        for i in range(len(spectrum)):
            start = max(0, i - window_size // 2)
            end = min(len(spectrum), i + window_size // 2)
            window = spectrum[start:end]
            
            median = np.median(window)
            std = np.std(window)
            
            threshold[i] = median + sensitivity * std
            
        return threshold
    
    def cepstral_analysis(self, samples: np.ndarray, 
                          n_quefrencies: int = 100) -> np.ndarray:
        """
        Cepstral analysis for modulation detection
        
        Cepstrum is useful for detecting periodic structures in spectrum,
        characteristic of modulated signals.
        
        Args:
            samples: IQ samples
            n_quefrencies: Number of quefrencies to return
            
        Returns:
            cepstrum: Power cepstrum
        """
        # Compute power spectrum
        frequencies, psd = welch(samples, fs=self.sample_rate, nperseg=1024)
        
        # Compute cepstrum (IFFT of log spectrum)
        log_spectrum = 10 * np.log10(psd + 1e-12)
        cepstrum = np.abs(ifft(log_spectrum))[:n_quefrencies]
        
        return cepstrum
    
    def cyclic_autocorrelation(self, samples: np.ndarray, 
                               alpha_range: Tuple[float, float] = (0, 0.5),
                               n_alphas: int = 100) -> Tuple[np.ndarray, np.ndarray]:
        """
        Cyclic autocorrelation for cyclostationary analysis
        
        Many drone signals exhibit cyclostationary properties due to
        modulation and coding.
        
        Args:
            samples: IQ samples
            alpha_range: Range of cycle frequencies (normalized)
            n_alphas: Number of alpha values to test
            
        Returns:
            alphas: Cycle frequencies
            corr: Cyclic autocorrelation
        """
        n = len(samples)
        alphas = np.linspace(alpha_range[0], alpha_range[1], n_alphas)
        corr = np.zeros(n_alphas, dtype=complex)
        
        for i, alpha in enumerate(alphas):
            # Frequency shift
            t = np.arange(n)
            shifted = samples * np.exp(-1j * 2 * np.pi * alpha * t)
            
            # Correlation
            corr[i] = np.sum(shifted * np.conj(samples)) / n
            
        return alphas, np.abs(corr)

# ============================================================================
# Custom Drone Detector Implementation
# ============================================================================

@dataclass
class CustomDetection:
    """Custom detection result"""
    timestamp: datetime
    drone_type: str
    confidence: float
    frequency: float
    bandwidth: float
    features: Dict
    raw_data: Optional[np.ndarray] = None

class CustomDroneDetector:
    """
    Custom drone detector with multiple specialized algorithms
    
    This detector implements several specialized detection methods:
    1. OFDM detector (for DJI and similar drones)
    2. Analog FM detector (for FPV drones)
    3. Chirp detector (for LoRa telemetry)
    4. General signal classifier
    """
    
    def __init__(self, sample_rate: float = 2e6):
        self.sample_rate = sample_rate
        self.signal_processor = CustomSignalProcessor(sample_rate)
        
        # Detection thresholds
        self.ofdm_threshold = 0.7
        self.fm_threshold = 0.6
        self.chirp_threshold = 0.65
        
        # Known drone characteristics
        self.drone_profiles = self._load_drone_profiles()
        
    def _load_drone_profiles(self) -> Dict:
        """Load profiles for known drone types"""
        return {
            "DJI_OcuSync": {
                "modulation": "OFDM",
                "bandwidth": 20e6,
                "frequencies": [2.4e9, 5.8e9],
                "cyclic_prefix": True,
                "pilots": [2405000000, 2410000000]
            },
            "DJI_O4": {
                "modulation": "OFDM",
                "bandwidth": 40e6,
                "frequencies": [2.4e9, 5.8e9],
                "cyclic_prefix": True
            },
            "FPV_Analog": {
                "modulation": "FM",
                "bandwidth": 8e6,
                "frequencies": [5.8e9],
                "deviation": 5e6
            },
            "FPV_Digital_HDZero": {
                "modulation": "OFDM",
                "bandwidth": 20e6,
                "frequencies": [5.8e9],
                "coding_rate": "2/3"
            },
            "LoRa_Telemetry": {
                "modulation": "Chirp",
                "bandwidth": 125e3,
                "frequencies": [868e6, 915e6],
                "spreading_factor": 7
            }
        }
        
    def detect_ofdm(self, samples: np.ndarray) -> Dict:
        """
        Detect OFDM-modulated signals (DJI, modern FPV)
        
        OFDM characteristics:
        - Flat spectrum with sharp edges
        - Cyclic prefix creates spectral notches
        - Pilot tones at specific frequencies
        """
        features = {}
        
        # 1. Compute PSD
        f, psd = welch(samples, fs=self.sample_rate, nperseg=1024)
        
        # 2. Normalize PSD
        psd_norm = psd / (np.max(psd) + 1e-12)
        
        # 3. Check for flat spectrum (low variance)
        spectral_variance = np.var(psd_norm)
        features['spectral_variance'] = spectral_variance
        
        # 4. Check for sharp roll-off (band edges)
        # Calculate 10% and 90% power frequencies
        cumsum = np.cumsum(psd)
        total_power = cumsum[-1]
        
        freq_10 = f[np.where(cumsum >= total_power * 0.1)[0][0]]
        freq_90 = f[np.where(cumsum >= total_power * 0.9)[0][0]]
        
        rolloff_sharpness = (freq_90 - freq_10) / (f[-1] - f[0])
        features['rolloff_sharpness'] = rolloff_sharpness
        
        # 5. Check for cyclic prefix (spectral notches)
        cepstrum = self.signal_processor.cepstral_analysis(samples)
        # Look for peak at cyclic prefix length
        cp_length_candidates = [64, 128, 256, 512]
        cp_peaks = [cepstrum[cp] if cp < len(cepstrum) else 0 for cp in cp_length_candidates]
        features['has_cyclic_prefix'] = max(cp_peaks) > 0.1
        
        # 6. Check for pilot tones
        # Find peaks in spectrum
        peaks, properties = find_peaks(psd, height=np.max(psd)*0.7)
        peak_freqs = f[peaks]
        
        # Score based on number of significant peaks
        features['num_peaks'] = len(peaks)
        features['peak_spacing'] = np.std(np.diff(peak_freqs)) if len(peaks) > 1 else 0
        
        # 7. Cyclostationary analysis
        alphas, cyclic_corr = self.signal_processor.cyclic_autocorrelation(samples)
        features['cyclostationary_strength'] = np.max(cyclic_corr)
        
        # Calculate overall OFDM score (0-1)
        score = 0
        score += (1 - min(spectral_variance, 0.5) / 0.5) * 0.3
        score += (1 - abs(rolloff_sharpness - 0.8)) * 0.2
        score += features['has_cyclic_prefix'] * 0.25
        score += min(len(peaks) / 20, 1.0) * 0.15
        score += min(features['cyclostationary_strength'], 1.0) * 0.1
        
        return {
            'is_ofdm': score > self.ofdm_threshold,
            'confidence': score,
            'features': features,
            'bandwidth': freq_90 - freq_10,
            'center_frequency': np.mean([freq_10, freq_90])
        }
        
    def detect_fm(self, samples: np.ndarray) -> Dict:
        """
        Detect analog FM-modulated signals (FPV analog)
        
        FM characteristics:
        - Constant envelope
        - Wide bandwidth
        - Strong peak at center
        """
        features = {}
        
        # 1. Compute amplitude
        amplitude = np.abs(samples)
        phase = np.angle(samples)
        
        # 2. Check for constant envelope (low amplitude variance)
        amplitude_variance = np.var(amplitude)
        amplitude_mean = np.mean(amplitude)
        features['envelope_constancy'] = amplitude_variance / (amplitude_mean**2 + 1e-12)
        
        # 3. Compute instantaneous frequency
        inst_freq = np.diff(np.unwrap(phase)) * self.sample_rate / (2 * np.pi)
        
        # 4. FM signature: frequency proportional to message
        freq_variance = np.var(inst_freq)
        features['frequency_variance'] = freq_variance
        
        # 5. Check bandwidth
        f, psd = welch(samples, fs=self.sample_rate, nperseg=1024)
        
        # Find 99% occupied bandwidth
        cumsum = np.cumsum(psd)
        total_power = cumsum[-1]
        idx_1 = np.where(cumsum >= total_power * 0.005)[0][0]
        idx_99 = np.where(cumsum >= total_power * 0.995)[0][0]
        bandwidth = f[idx_99] - f[idx_1]
        features['occupied_bandwidth'] = bandwidth
        
        # 6. Check for typical FM deviation
        expected_deviation = 5e6  # 5 MHz typical for FPV
        features['deviation_match'] = 1 - min(abs(bandwidth/2 - expected_deviation) / expected_deviation, 1)
        
        # Calculate FM score
        score = 0
        score += (1 - min(features['envelope_constancy'], 1.0)) * 0.3
        score += min(freq_variance / 1e12, 1.0) * 0.3
        score += features['deviation_match'] * 0.4
        
        return {
            'is_fm': score > self.fm_threshold,
            'confidence': score,
            'features': features,
            'bandwidth': bandwidth,
            'center_frequency': f[np.argmax(psd)]
        }
        
    def detect_chirp(self, samples: np.ndarray) -> Dict:
        """
        Detect chirp spread spectrum (LoRa telemetry)
        
        Chirp characteristics:
        - Linear frequency sweep
        - Strong time-frequency correlation
        """
        features = {}
        
        # 1. Compute spectrogram
        f, t, Sxx = spectrogram(samples, fs=self.sample_rate, nperseg=256, noverlap=128)
        
        # 2. Detect chirps using Hough transform
        chirp_scores = []
        
        for i, time_slice in enumerate(Sxx.T):
            # Find peak in each time slice
            peak_idx = np.argmax(time_slice)
            peak_freq = f[peak_idx]
            
            # Track frequency change over time
            if i > 0:
                freq_change = peak_freq - last_freq
                chirp_scores.append(abs(freq_change))
                
            last_freq = peak_freq
            
        # 3. Look for linear frequency progression
        if len(chirp_scores) > 0:
            features['freq_change_rate'] = np.mean(chirp_scores)
            features['freq_change_consistency'] = np.std(chirp_scores) / (np.mean(chirp_scores) + 1e-12)
        else:
            features['freq_change_rate'] = 0
            features['freq_change_consistency'] = 0
            
        # 4. Check bandwidth of chirp
        f_mean = np.mean(f)
        f_std = np.std(f)
        features['bandwidth'] = f_std * 4
        
        # 5. Check for typical chirp rates
        expected_chirp_rate = 125e3  # 125 kHz for LoRa
        features['chirp_rate_match'] = 1 - min(abs(features['freq_change_rate'] - expected_chirp_rate) / expected_chirp_rate, 1)
        
        # Calculate chirp score
        score = 0
        score += (1 - min(features['freq_change_consistency'], 1.0)) * 0.4
        score += features['chirp_rate_match'] * 0.4
        score += min(features['freq_change_rate'] / 1e6, 1.0) * 0.2
        
        return {
            'is_chirp': score > self.chirp_threshold,
            'confidence': score,
            'features': features,
            'bandwidth': features['bandwidth']
        }
        
    def classify_signal(self, samples: np.ndarray) -> Dict:
        """
        Classify signal using ensemble of detectors
        """
        # Run all detectors
        ofdm_result = self.detect_ofdm(samples)
        fm_result = self.detect_fm(samples)
        chirp_result = self.detect_chirp(samples)
        
        # Determine most likely type
        results = [
            ('OFDM', ofdm_result['confidence'], ofdm_result),
            ('FM', fm_result['confidence'], fm_result),
            ('Chirp', chirp_result['confidence'], chirp_result)
        ]
        
        best = max(results, key=lambda x: x[1])
        
        return {
            'modulation_type': best[0],
            'confidence': best[1],
            'details': best[2],
            'all_scores': {
                'ofdm': ofdm_result['confidence'],
                'fm': fm_result['confidence'],
                'chirp': chirp_result['confidence']
            }
        }
        
    def identify_drone(self, samples: np.ndarray, classification: Dict) -> Dict:
        """
        Identify specific drone type based on signatures
        """
        detection_result = {
            'drone_type': 'Unknown',
            'confidence': 0,
            'matches': []
        }
        
        modulation = classification['modulation_type']
        
        # Extract key parameters
        params = {}
        if modulation == 'OFDM':
            params = classification['details'].get('features', {})
            params['bandwidth'] = classification['details'].get('bandwidth', 0)
        elif modulation == 'FM':
            params = classification['details'].get('features', {})
            params['bandwidth'] = classification['details'].get('bandwidth', 0)
        elif modulation == 'Chirp':
            params = classification['details'].get('features', {})
            params['bandwidth'] = classification['details'].get('bandwidth', 0)
            
        # Match against known drone profiles
        for drone_name, profile in self.drone_profiles.items():
            if profile['modulation'] != modulation:
                continue
                
            match_score = 0
            match_details = {}
            
            # Compare bandwidth
            if 'bandwidth' in params and 'bandwidth' in profile:
                bw_match = 1 - min(abs(params['bandwidth'] - profile['bandwidth']) / profile['bandwidth'], 1)
                match_score += bw_match * 0.4
                match_details['bandwidth_match'] = bw_match
                
            # Modulation-specific comparisons
            if modulation == 'OFDM':
                if params.get('has_cyclic_prefix', False) == profile.get('cyclic_prefix', False):
                    match_score += 0.3
                    match_details['cyclic_prefix_match'] = 1
                    
            elif modulation == 'FM':
                if 'deviation' in profile and 'deviation_match' in params:
                    match_score += params['deviation_match'] * 0.4
                    
            elif modulation == 'Chirp':
                if 'spreading_factor' in profile:
                    # Estimate spreading factor from chirp rate
                    match_score += params.get('chirp_rate_match', 0) * 0.4
                    
            detection_result['matches'].append({
                'drone_type': drone_name,
                'score': match_score,
                'details': match_details
            })
            
        # Get best match
        if detection_result['matches']:
            best_match = max(detection_result['matches'], key=lambda x: x['score'])
            if best_match['score'] > 0.5:
                detection_result['drone_type'] = best_match['drone_type']
                detection_result['confidence'] = best_match['score']
                
        return detection_result

# ============================================================================
# Real-time Detection Pipeline
# ============================================================================

class RealTimeCustomDetector:
    """
    Real-time custom detection pipeline integrating with main system
    """
    
    def __init__(self, sample_rate: float = 2e6):
        self.detector = CustomDroneDetector(sample_rate)
        self.signal_processor = CustomSignalProcessor(sample_rate)
        self.buffer = []
        self.buffer_size = int(sample_rate * 0.5)  # 0.5 second buffer
        
    async def process_chunk(self, samples: np.ndarray) -> Optional[CustomDetection]:
        """
        Process a chunk of IQ samples for detection
        """
        if len(samples) < 1024:
            return None
            
        # 1. Classify modulation type
        classification = self.detector.classify_signal(samples)
        
        if classification['confidence'] < 0.6:
            return None
            
        # 2. Identify specific drone
        identification = self.detector.identify_drone(samples, classification)
        
        # 3. Compute additional features
        f, psd = welch(samples, fs=self.signal_processor.sample_rate, nperseg=1024)
        
        # Find signal peak
        peak_idx = np.argmax(psd)
        peak_freq = f[peak_idx]
        peak_power = 10 * np.log10(psd[peak_idx] + 1e-12)
        
        # Calculate SNR
        noise_floor = np.median(psd)
        snr = 10 * np.log10(peak_power / (noise_floor + 1e-12))
        
        # 4. Create detection event
        detection = CustomDetection(
            timestamp=datetime.utcnow(),
            drone_type=identification['drone_type'],
            confidence=identification['confidence'],
            frequency=peak_freq,
            bandwidth=classification['details'].get('bandwidth', 0),
            features={
                'modulation_type': classification['modulation_type'],
                'modulation_confidence': classification['confidence'],
                'snr': snr,
                'signal_power': peak_power,
                'noise_floor': 10 * np.log10(noise_floor + 1e-12),
                'classification_scores': classification['all_scores']
            }
        )
        
        return detection
        
    async def stream_process(self, stream_generator):
        """
        Process continuous IQ stream
        """
        async for iq_chunk in stream_generator:
            self.buffer.extend(iq_chunk)
            
            while len(self.buffer) >= self.buffer_size:
                # Take chunk for processing
                chunk = np.array(self.buffer[:self.buffer_size])
                self.buffer = self.buffer[self.buffer_size:]
                
                detection = await self.process_chunk(chunk)
                
                if detection:
                    yield detection

# ============================================================================
# Integration with Main System
# ============================================================================

class MainSystemIntegration:
    """
    Integrate custom detector with the main Drone Detector system
    """
    
    def __init__(self, api_base_url: str = "http://localhost:8888/api/v1"):
        self.api_base_url = api_base_url
        self.custom_detector = RealTimeCustomDetector()
        self.active_detections = []
        
    async def start_custom_detection(self):
        """
        Start custom detection and send results to main system
        """
        print("🚀 Starting custom detection pipeline...")
        
        # This would connect to the system's IQ stream
        # For demonstration, we'll use a mock stream
        from infrastructure.hardware.mock_hardware import MockSDR
        
        mock_sdr = MockSDR()
        mock_sdr.initialize({'sample_rate': 2e6})
        
        print("📡 Listening for IQ data...")
        
        async for iq_samples in mock_sdr.start_stream():
            # Convert to numpy array
            samples = np.array(iq_samples)
            
            # Process with custom detector
            detection = await self.custom_detector.process_chunk(samples)
            
            if detection and detection.confidence > 0.7:
                self.active_detections.append(detection)
                self.print_detection(detection)
                
                # Here you could send to main system via API
                # await self.send_to_main_system(detection)
                
    def print_detection(self, detection: CustomDetection):
        """Print detection in formatted way"""
        print("\n" + "="*70)
        print(f"🎯 CUSTOM DETECTION ({detection.timestamp.strftime('%H:%M:%S')})")
        print("="*70)
        print(f"  Drone Type:  {detection.drone_type}")
        print(f"  Confidence:  {detection.confidence*100:.1f}%")
        print(f"  Frequency:   {detection.frequency/1e9:.3f} GHz")
        print(f"  Bandwidth:   {detection.bandwidth/1e6:.1f} MHz")
        print(f"\n  Modulation:  {detection.features['modulation_type']} "
              f"({detection.features['modulation_confidence']*100:.1f}%)")
        print(f"  SNR:         {detection.features['snr']:.1f} dB")
        print(f"  Signal:      {detection.features['signal_power']:.1f} dBm")
        print(f"  Noise:       {detection.features['noise_floor']:.1f} dBm")
        print("="*70)
        
    async def send_to_main_system(self, detection: CustomDetection):
        """
        Send detection to main system API
        """
        import aiohttp
        
        detection_data = {
            "drone_type": detection.drone_type,
            "confidence": detection.confidence,
            "frequency": detection.frequency,
            "bandwidth": detection.bandwidth,
            "timestamp": detection.timestamp.isoformat(),
            "custom_features": detection.features
        }
        
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{self.api_base_url}/custom/detections",
                json=detection_data
            )

# ============================================================================
# Testing and Validation
# ============================================================================

class CustomDetectorTester:
    """
    Test and validate custom detector performance
    """
    
    def __init__(self):
        self.detector = CustomDroneDetector()
        
    def generate_test_signal(self, signal_type: str, duration: float = 1.0, 
                             sample_rate: float = 2e6) -> np.ndarray:
        """
        Generate test signals for validation
        """
        t = np.arange(0, duration, 1/sample_rate)
        
        if signal_type == 'ofdm':
            # Simulate OFDM signal
            n_subcarriers = 64
            symbols_per_carrier = 10
            data = np.random.choice([-1, 1], n_subcarriers * symbols_per_carrier)
            
            ofdm_signal = []
            for i in range(symbols_per_carrier):
                # IFFT of subcarriers
                symbol = data[i*n_subcarriers:(i+1)*n_subcarriers]
                time_signal = np.fft.ifft(symbol)
                # Add cyclic prefix
                cp_len = 16
                time_signal = np.concatenate([time_signal[-cp_len:], time_signal])
                ofdm_signal.extend(time_signal)
                
            # Resample to match sample rate
            ofdm_signal = np.array(ofdm_signal[:len(t)])
            if len(ofdm_signal) < len(t):
                ofdm_signal = np.pad(ofdm_signal, (0, len(t)-len(ofdm_signal)))
                
            return ofdm_signal
            
        elif signal_type == 'fm':
            # Simulate FM signal
            baseband = np.sin(2 * np.pi * 1000 * t) + 0.5 * np.sin(2 * np.pi * 3000 * t)
            deviation = 100e3
            fm_signal = np.exp(1j * 2 * np.pi * deviation * np.cumsum(baseband) / sample_rate)
            return fm_signal
            
        elif signal_type == 'chirp':
            # Simulate chirp signal
            chirp = signal.chirp(t, f0=100e3, f1=500e3, t1=duration, method='linear')
            return chirp.astype(complex)
            
        else:
            # Gaussian noise
            noise = (np.random.randn(len(t)) + 1j * np.random.randn(len(t))) / np.sqrt(2)
            return noise
            
    def test_detector(self):
        """
        Run validation tests
        """
        print("\n" + "="*60)
        print("🔬 CUSTOM DETECTOR VALIDATION")
        print("="*60)
        
        test_cases = [
            ('ofdm', 'DJI_OcuSync', 0.8),
            ('fm', 'FPV_Analog', 0.7),
            ('chirp', 'LoRa_Telemetry', 0.7),
            ('noise', 'None', 0.3)
        ]
        
        results = []
        
        for signal_type, expected_drone, min_confidence in test_cases:
            print(f"\nTesting {signal_type.upper()} signal...")
            
            # Generate test signal
            signal = self.generate_test_signal(signal_type)
            
            # Detect
            classification = self.detector.classify_signal(signal)
            identification = self.detector.identify_drone(signal, classification)
            
            print(f"  Detected modulation: {classification['modulation_type']} "
                  f"(conf: {classification['confidence']:.2f})")
            print(f"  Drone identification: {identification['drone_type']} "
                  f"(conf: {identification['confidence']:.2f})")
            
            passed = (identification['confidence'] >= min_confidence)
            print(f"  {'✓ PASSED' if passed else '✗ FAILED'}")
            
            results.append({
                'signal_type': signal_type,
                'expected': expected_drone,
                'detected': identification['drone_type'],
                'confidence': identification['confidence'],
                'passed': passed
            })
            
        # Summary
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        
        passed_count = sum(1 for r in results if r['passed'])
        print(f"Passed: {passed_count}/{len(results)} ({passed_count/len(results)*100:.0f}%)")
        
        for result in results:
            status = "✓" if result['passed'] else "✗"
            print(f"  {status} {result['signal_type']:10} -> {result['detected']:15} "
                  f"({result['confidence']*100:.0f}%)")
                  
        return results

# ============================================================================
# Main Execution
# ============================================================================

async def main():
    """Main example execution"""
    print("="*70)
    print("🔧 CUSTOM DRONE DETECTOR EXAMPLE")
    print("="*70)
    print("\nThis example demonstrates:")
    print("  1. Custom signal processing algorithms")
    print("  2. Specialized drone detection (OFDM, FM, Chirp)")
    print("  3. Real-time detection pipeline")
    print("  4. Integration with main system")
    
    # 1. Run validation tests
    tester = CustomDetectorTester()
    test_results = tester.test_detector()
    
    # 2. Demonstrate real-time detection
    print("\n" + "="*60)
    print("🎬 REAL-TIME DETECTION DEMO")
    print("="*60)
    print("Starting real-time detection (30 seconds)...")
    
    integration = MainSystemIntegration()
    
    # Run for 30 seconds
    try:
        await asyncio.wait_for(
            integration.start_custom_detection(),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        print("\n\n✅ Demo completed")
        
    # 3. Summary
    print("\n" + "="*60)
    print("📈 CUSTOM DETECTOR SUMMARY")
    print("="*60)
    
    print(f"\nDetection modes implemented:")
    print("  • OFDM detector (DJI OcuSync/O4)")
    print("  • FM detector (FPV Analog)")
    print("  • Chirp detector (LoRa telemetry)")
    print("\nCustom features:")
    print("  • Adaptive thresholding")
    print("  • Cepstral analysis")
    print("  • Cyclostationary detection")
    print("  • Ensemble classification")
    
    print("\nNext steps:")
    print("  1. Train ML models on collected data")
    print("  2. Add more drone types to profiles")
    print("  3. Implement TDOA localization")
    print("  4. Deploy as standalone service")

if __name__ == "__main__":
    asyncio.run(main())