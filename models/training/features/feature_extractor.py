"""
Feature Extraction Module
Extracts 46 features from IQ samples for drone classification
"""

import numpy as np
from scipy import signal, stats
from scipy.fft import fft, fftshift, fftfreq


class FeatureExtractor:
    """Extract features from IQ samples for drone classification"""
    
    def __init__(self, sample_rate=10e6):
        self.sample_rate = sample_rate
        self.fft_size = 2048
    
    def extract_all_features(self, iq_samples):
        """Extract all 46 features from IQ samples"""
        features = {}
        
        # Extract spectral features
        spectral_features = self._extract_spectral_features(iq_samples)
        features.update(spectral_features)
        
        # Extract cyclostationary features
        cyclic_features = self._extract_cyclic_features(iq_samples)
        features.update(cyclic_features)
        
        # Extract statistical features
        statistical_features = self._extract_statistical_features(iq_samples)
        features.update(statistical_features)
        
        # Extract modulation features
        modulation_features = self._extract_modulation_features(iq_samples)
        features.update(modulation_features)
        
        return features
    
    def _extract_spectral_features(self, iq_samples):
        """Extract 20 spectral features"""
        # Compute PSD
        f, psd = signal.welch(iq_samples, fs=self.sample_rate, nperseg=self.fft_size)
        psd_db = 10 * np.log10(psd + 1e-12)
        
        # Find peaks
        peaks, properties = signal.find_peaks(psd_db, prominence=5, width=1)
        
        features = {}
        
        if len(peaks) > 0:
            # Peak features
            main_peak = peaks[np.argmax(psd_db[peaks])]
            features['peak_freq'] = f[main_peak]
            features['peak_magnitude'] = psd_db[main_peak]
            features['peak_width'] = properties['widths'][0] if 'widths' in properties else 0
            features['peak_prominence'] = properties['peak_heights'][0] if 'peak_heights' in properties else 0
        else:
            features['peak_freq'] = 0
            features['peak_magnitude'] = np.max(psd_db)
            features['peak_width'] = 0
            features['peak_prominence'] = 0
        
        # PSD statistics
        features['power_spectral_density_mean'] = np.mean(psd_db)
        features['power_spectral_density_std'] = np.std(psd_db)
        features['power_spectral_density_skew'] = stats.skew(psd_db)
        features['power_spectral_density_kurtosis'] = stats.kurtosis(psd_db)
        
        # Bandwidth measurements
        peak_power = np.max(psd_db)
        threshold_3db = peak_power - 3
        threshold_6db = peak_power - 6
        threshold_20db = peak_power - 20
        
        above_3db = psd_db > threshold_3db
        above_6db = psd_db > threshold_6db
        above_20db = psd_db > threshold_20db
        
        features['bandwidth_3db'] = np.sum(above_3db) * (f[1] - f[0]) if np.any(above_3db) else 0
        features['bandwidth_6db'] = np.sum(above_6db) * (f[1] - f[0]) if np.any(above_6db) else 0
        features['bandwidth_20db'] = np.sum(above_20db) * (f[1] - f[0]) if np.any(above_20db) else 0
        
        # Roll-off factor
        cumulative_power = np.cumsum(psd)
        total_power = cumulative_power[-1]
        rolloff_idx = np.where(cumulative_power >= 0.95 * total_power)[0]
        features['roll_off_factor'] = f[rolloff_idx[0]] / f[-1] if len(rolloff_idx) > 0 else 1
        
        # Spectral flatness
        geometric_mean = np.exp(np.mean(np.log(psd + 1e-12)))
        arithmetic_mean = np.mean(psd)
        features['spectral_flatness'] = geometric_mean / arithmetic_mean if arithmetic_mean > 0 else 0
        
        # Spectral centroid
        features['spectral_centroid'] = np.sum(f * psd) / np.sum(psd) if np.sum(psd) > 0 else 0
        
        # Spectral spread
        centroid = features['spectral_centroid']
        features['spectral_spread'] = np.sqrt(np.sum(((f - centroid) ** 2) * psd) / np.sum(psd)) if np.sum(psd) > 0 else 0
        
        # Spectral rolloff
        cumulative = np.cumsum(psd)
        rolloff_idx = np.where(cumulative >= 0.85 * total_power)[0]
        features['spectral_rolloff'] = f[rolloff_idx[0]] if len(rolloff_idx) > 0 else f[-1]
        
        # Noise floor and SNR
        noise_indices = psd_db < np.percentile(psd_db, 25)
        features['noise_floor'] = np.mean(psd_db[noise_indices]) if np.any(noise_indices) else np.min(psd_db)
        features['signal_to_noise_ratio'] = features['peak_magnitude'] - features['noise_floor']
        
        # Peak-to-average power ratio
        features['peak_to_average_power_ratio'] = features['peak_magnitude'] - features['power_spectral_density_mean']
        
        # Total harmonic distortion (simplified)
        harmonics = [2, 3, 4, 5]
        harmonic_power = 0
        for h in harmonics:
            harmonic_freq = features['peak_freq'] * h
            if harmonic_freq < f[-1]:
                idx = np.argmin(np.abs(f - harmonic_freq))
                harmonic_power += 10 ** (psd_db[idx] / 10)
        fundamental_power = 10 ** (features['peak_magnitude'] / 10)
        features['total_harmonic_distortion'] = np.sqrt(harmonic_power / fundamental_power) if fundamental_power > 0 else 0
        
        return features
    
    def _extract_cyclic_features(self, iq_samples):
        """Extract 8 cyclostationary features"""
        n = len(iq_samples)
        x = iq_samples * np.hanning(n)
        X = fft(x)
        
        features = {}
        
        # Find cyclic frequencies (simplified)
        alpha_candidates = np.linspace(0, self.sample_rate / 2, 20)
        cyclic_amplitudes = []
        
        for alpha in alpha_candidates:
            alpha_idx = int(alpha * n / self.sample_rate)
            if alpha_idx < 1 or alpha_idx >= n:
                continue
            S_alpha = X * np.roll(np.conj(X), alpha_idx)
            cyclic_amp = np.abs(np.mean(S_alpha))
            cyclic_amplitudes.append(cyclic_amp)
        
        # Top 3 cyclic frequencies
        top_indices = np.argsort(cyclic_amplitudes)[-3:]
        
        for i, idx in enumerate(top_indices, 1):
            features[f'cyclic_frequency_{i}'] = alpha_candidates[idx] if idx < len(alpha_candidates) else 0
            features[f'cyclic_amplitude_{i}'] = cyclic_amplitudes[idx] if idx < len(cyclic_amplitudes) else 0
        
        # Cyclic coherence
        features['cyclic_coherence'] = np.max(cyclic_amplitudes) if cyclic_amplitudes else 0
        
        # Cycle frequency spacing
        if len(alpha_candidates) > 1:
            features['cycle_frequency_spacing'] = alpha_candidates[1] - alpha_candidates[0]
        else:
            features['cycle_frequency_spacing'] = 0
        
        return features
    
    def _extract_statistical_features(self, iq_samples):
        """Extract 10 statistical features"""
        real_part = np.real(iq_samples)
        imag_part = np.imag(iq_samples)
        amplitude = np.abs(iq_samples)
        phase = np.angle(iq_samples)
        
        features = {
            'iq_mean_real': np.mean(real_part),
            'iq_mean_imag': np.mean(imag_part),
            'iq_std_real': np.std(real_part),
            'iq_std_imag': np.std(imag_part),
            'iq_variance': np.var(iq_samples),
            'iq_skewness': stats.skew(real_part),
            'iq_kurtosis': stats.kurtosis(real_part),
            'amplitude_variance': np.var(amplitude),
            'phase_variance': np.var(phase),
            'instantaneous_frequency_std': np.std(np.diff(phase))
        }
        
        return features
    
    def _extract_modulation_features(self, iq_samples):
        """Extract 8 modulation features"""
        # Hilbert transform
        analytic = signal.hilbert(iq_samples)
        instantaneous_amplitude = np.abs(analytic)
        instantaneous_phase = np.unwrap(np.angle(analytic))
        instantaneous_frequency = np.diff(instantaneous_phase) * self.sample_rate / (2 * np.pi)
        
        features = {
            'modulation_index': np.std(instantaneous_phase),
            'frequency_deviation': np.std(instantaneous_frequency),
            'symbol_rate': self._estimate_symbol_rate(iq_samples)
        }
        
        # Carrier offset
        f, psd = signal.welch(iq_samples, fs=self.sample_rate, nperseg=1024)
        features['carrier_offset'] = f[np.argmax(psd)]
        
        # EVM (Error Vector Magnitude)
        constellation = self._recover_constellation(iq_samples)
        ideal_points = self._get_ideal_constellation(len(constellation))
        errors = np.abs(constellation - ideal_points[:len(constellation)])
        features['evm_rms'] = np.sqrt(np.mean(errors**2))
        features['evm_peak'] = np.max(errors)
        
        # Phase and magnitude errors
        features['phase_error_rms'] = np.std(np.angle(constellation))
        features['magnitude_error_rms'] = np.std(np.abs(constellation) - 1)
        
        return features
    
    def _estimate_symbol_rate(self, iq_samples):
        """Estimate symbol rate using cyclostationary analysis"""
        # Simplified estimation
        return self.sample_rate / 100  # Placeholder
    
    def _recover_constellation(self, iq_samples):
        """Recover constellation points from IQ samples"""
        # Normalize
        samples = iq_samples / np.sqrt(np.mean(np.abs(iq_samples)**2))
        return samples[:100]  # Return first 100 points
    
    def _get_ideal_constellation(self, n_points):
        """Get ideal constellation points for QPSK"""
        ideal = np.array([1+1j, 1-1j, -1+1j, -1-1j]) / np.sqrt(2)
        return np.tile(ideal, int(np.ceil(n_points / 4)))[:n_points]