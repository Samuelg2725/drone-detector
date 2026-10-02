drone-detector/data/iq/synthetic/README.md - Synthetic IQ Data Documentation

markdown
# Synthetic IQ Data Directory

This directory contains synthetically generated IQ data for testing, algorithm development, and system validation. Synthetic data enables controlled experiments with known parameters, edge cases, and scenarios that are difficult to capture in real-world recordings.

## Directory Structure
data/iq/synthetic/
├── README.md # This file
├── noise/ # Synthetic noise signals
│ ├── white_gaussian.iq
│ ├── white_gaussian.json
│ ├── pink_noise.iq
│ ├── pink_noise.json
│ ├── brown_noise.iq
│ ├── brown_noise.json
│ ├── impulsive_noise.iq
│ ├── impulsive_noise.json
│ └── dataset_info.json
├── ofdm/ # OFDM-modulated signals
│ ├── ofdm_20mhz.iq
│ ├── ofdm_20mhz.json
│ ├── ofdm_40mhz.iq
│ ├── ofdm_40mhz.json
│ ├── ofdm_80mhz.iq
│ ├── ofdm_80mhz.json
│ ├── ofdm_with_cp.iq
│ ├── ofdm_with_cp.json
│ └── dataset_info.json
├── lora/ # LoRa-modulated signals
│ ├── lora_sf7.iq
│ ├── lora_sf7.json
│ ├── lora_sf8.iq
│ ├── lora_sf8.json
│ ├── lora_sf9.iq
│ ├── lora_sf9.json
│ ├── lora_sf10.iq
│ ├── lora_sf10.json
│ ├── lora_sf11.iq
│ ├── lora_sf11.json
│ ├── lora_sf12.iq
│ ├── lora_sf12.json
│ └── dataset_info.json
├── fm/ # Frequency Modulation signals
│ ├── fm_analog.iq
│ ├── fm_analog.json
│ ├── fm_digital.iq
│ ├── fm_digital.json
│ ├── fm_broadcast.iq
│ ├── fm_broadcast.json
│ └── dataset_info.json
├── test_tones/ # Calibration tones
│ ├── single_tone.iq
│ ├── single_tone.json
│ ├── multi_tone.iq
│ ├── multi_tone.json
│ ├── chirp.iq
│ ├── chirp.json
│ ├── swept_sine.iq
│ ├── swept_sine.json
│ └── dataset_info.json
└── index.json # Global synthetic index

text

## Synthetic Signal Types

### 1. Noise Signals (`noise/`)

| File | Type | Characteristics | Use Case |
|------|------|-----------------|----------|
| `white_gaussian.iq` | White Gaussian | Flat PSD, Gaussian distribution | Baseline noise testing |
| `pink_noise.iq` | Pink Noise | 1/f spectrum, natural variation | Environmental simulation |
| `brown_noise.iq` | Brown Noise | 1/f² spectrum, random walk | Drift simulation |
| `impulsive_noise.iq` | Impulsive | Burst interference | RFI simulation |

**Generation Parameters:**
```python
# White Gaussian Noise
duration = 30  # seconds
sample_rate = 10e6
noise_power_dbm = -100
mean = 0
variance = 10 ** (noise_power_dbm / 10)
noise = np.sqrt(variance/2) * (np.random.randn(n) + 1j * np.random.randn(n))
2. OFDM Signals (ofdm/)
File	Bandwidth	Subcarriers	CP Length	Use Case
ofdm_20mhz.iq	20 MHz	64	16	WiFi/802.11 simulation
ofdm_40mhz.iq	40 MHz	128	32	802.11n simulation
ofdm_80mhz.iq	80 MHz	256	64	802.11ac simulation
ofdm_with_cp.iq	20 MHz	64	16	DJI OcuSync simulation
OFDM Parameters:

python
config = {
    'fft_size': 64,      # or 128, 256
    'cp_len': 16,        # Cyclic prefix length
    'num_symbols': 1000,
    'modulation': 'QPSK',  # BPSK, QPSK, 16-QAM, 64-QAM
    'null_subcarriers': [0, 32],  # DC and guard bands
    'pilot_subcarriers': [11, 25, 39, 53]
}
3. LoRa Signals (lora/)
File	Spreading Factor	Bandwidth	Coding Rate	Data Rate
lora_sf7.iq	7	125 kHz	4/5	5.47 kbps
lora_sf8.iq	8	125 kHz	4/5	3.13 kbps
lora_sf9.iq	9	125 kHz	4/5	1.76 kbps
lora_sf10.iq	10	125 kHz	4/5	0.98 kbps
lora_sf11.iq	11	125 kHz	4/5	0.54 kbps
lora_sf12.iq	12	125 kHz	4/5	0.29 kbps
LoRa Generation:

python
def generate_lora_symbol(sf, bandwidth, num_samples):
    """Generate LoRa chirp symbol"""
    t = np.arange(num_samples) / sample_rate
    f_start = -bandwidth/2
    f_end = bandwidth/2
    chirp_rate = (f_end - f_start) / (num_samples / sample_rate)
    frequency = f_start + chirp_rate * t
    return np.exp(1j * 2 * np.pi * np.cumsum(frequency) / sample_rate)
4. FM Signals (fm/)
File	Type	Deviation	Bandwidth	Use Case
fm_analog.iq	Analog FM	75 kHz	200 kHz	Broadcast FM
fm_digital.iq	Digital FM	25 kHz	100 kHz	FPV Analog video
fm_broadcast.iq	Broadcast	75 kHz	200 kHz	Radio station simulation
FM Generation:

python
def generate_fm_signal(message, fc, deviation, sample_rate):
    """Generate FM modulated signal"""
    t = np.arange(len(message)) / sample_rate
    phase = 2 * np.pi * fc * t + 2 * np.pi * deviation * np.cumsum(message) / sample_rate
    return np.exp(1j * phase)
5. Test Tones (test_tones/)
File	Type	Frequencies	Duration	Use Case
single_tone.iq	Single Frequency	1 MHz	10s	Calibration
multi_tone.iq	Multiple Frequencies	0.1, 0.5, 1, 2, 5 MHz	10s	IMD testing
chirp.iq	Linear Chirp	0-10 MHz	10s	Sweep testing
swept_sine.iq	Swept Sine	0.1-10 MHz	10s	Frequency response
Generation Scripts
Basic Noise Generation
python
#!/usr/bin/env python3
"""
Generate synthetic noise signals
"""

import numpy as np
import json
from pathlib import Path

def generate_white_gaussian_noise(duration=30, sample_rate=10e6, noise_power_dbm=-100):
    """Generate white Gaussian noise"""
    n = int(sample_rate * duration)
    power_linear = 10 ** (noise_power_dbm / 10)
    noise = np.sqrt(power_linear/2) * (np.random.randn(n) + 1j * np.random.randn(n))
    return noise.astype(np.complex64)

def generate_pink_noise(duration=30, sample_rate=10e6):
    """Generate pink noise (1/f spectrum)"""
    n = int(sample_rate * duration)
    # Generate white noise
    white = np.random.randn(n) + 1j * np.random.randn(n)
    
    # Apply pink filter
    # Simplified: use FFT and 1/f scaling
    fft_data = np.fft.fft(white)
    freqs = np.fft.fftfreq(n, 1/sample_rate)
    freqs[0] = 1  # Avoid division by zero
    pink_filter = 1 / np.sqrt(np.abs(freqs))
    fft_pink = fft_data * pink_filter
    pink = np.fft.ifft(fft_pink)
    
    # Normalize power
    pink = pink / np.sqrt(np.mean(np.abs(pink)**2)) * 0.1
    return pink.astype(np.complex64)

def generate_impulsive_noise(duration=30, sample_rate=10e6, impulse_rate=0.01):
    """Generate impulsive noise with random bursts"""
    n = int(sample_rate * duration)
    noise = np.zeros(n, dtype=np.complex128)
    
    num_impulses = int(n * impulse_rate)
    impulse_indices = np.random.choice(n, num_impulses, replace=False)
    
    for idx in impulse_indices:
        amplitude = np.random.exponential(5)
        duration_samples = np.random.randint(1, 10)
        end = min(idx + duration_samples, n)
        noise[idx:end] += amplitude * np.exp(1j * 2 * np.pi * np.random.rand())
    
    return noise.astype(np.complex64)

# Generate all noise variants
output_dir = Path("data/iq/synthetic/noise")
output_dir.mkdir(parents=True, exist_ok=True)

signals = {
    "white_gaussian": generate_white_gaussian_noise(30),
    "pink_noise": generate_pink_noise(30),
    "impulsive_noise": generate_impulsive_noise(30)
}

for name, signal in signals.items():
    # Save IQ data
    output_file = output_dir / f"{name}.iq"
    signal.tofile(output_file)
    
    # Save metadata
    metadata = {
        "signal_type": name.replace('_', ' ').title(),
        "sample_rate": 10e6,
        "duration": 30,
        "num_samples": len(signal),
        "generation_date": datetime.now().isoformat()
    }
    
    with open(output_dir / f"{name}.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Generated {name}: {len(signal)} samples")
OFDM Signal Generation
python
#!/usr/bin/env python3
"""
Generate synthetic OFDM signals
"""

import numpy as np

class OFDMGenerator:
    """OFDM signal generator"""
    
    def __init__(self, fft_size=64, cp_len=16, modulation='QPSK'):
        self.fft_size = fft_size
        self.cp_len = cp_len
        self.modulation = modulation
        self.symbol_len = fft_size + cp_len
        
        # Subcarrier mapping
        self.data_subcarriers = self._get_data_subcarriers()
        self.pilot_subcarriers = [11, 25, 39, 53]  # Standard 802.11 pilots
        self.null_subcarriers = [0, 32]  # DC and guard bands
    
    def _get_data_subcarriers(self):
        """Get data subcarrier indices"""
        all_sc = list(range(-self.fft_size//2, self.fft_size//2))
        data_sc = [sc for sc in all_sc 
                  if sc not in self.pilot_subcarriers 
                  and sc not in self.null_subcarriers]
        return data_sc
    
    def _modulate_qpsk(self, bits):
        """QPSK modulation"""
        bits = bits.reshape(-1, 2)
        symbols = np.zeros(len(bits), dtype=np.complex128)
        for i, (b0, b1) in enumerate(bits):
            if b0 == 0 and b1 == 0:
                symbols[i] = (1 + 1j) / np.sqrt(2)
            elif b0 == 0 and b1 == 1:
                symbols[i] = (1 - 1j) / np.sqrt(2)
            elif b0 == 1 and b1 == 0:
                symbols[i] = (-1 + 1j) / np.sqrt(2)
            else:
                symbols[i] = (-1 - 1j) / np.sqrt(2)
        return symbols
    
    def generate_ofdm_symbol(self):
        """Generate single OFDM symbol"""
        # Generate random bits for data subcarriers
        num_data_bits = len(self.data_subcarriers) * 2  # 2 bits per symbol for QPSK
        data_bits = np.random.randint(0, 2, num_data_bits)
        data_symbols = self._modulate_qpsk(data_bits)
        
        # Generate pilot symbols (BPSK)
        pilot_symbols = [1, -1, 1, -1]
        
        # Create frequency domain signal
        freq_domain = np.zeros(self.fft_size, dtype=np.complex128)
        freq_domain[self.fft_size//2:] = data_symbols[:len(self.data_subcarriers)//2]
        freq_domain[:self.fft_size//2] = data_symbols[len(self.data_subcarriers)//2:]
        
        for i, sc in enumerate(self.pilot_subcarriers):
            idx = self.fft_size//2 + sc
            freq_domain[idx] = pilot_symbols[i]
        
        # Null subcarriers
        for sc in self.null_subcarriers:
            idx = self.fft_size//2 + sc
            freq_domain[idx] = 0
        
        # IFFT
        time_domain = np.fft.ifft(freq_domain)
        
        # Add cyclic prefix
        cp = time_domain[-self.cp_len:]
        return np.concatenate([cp, time_domain])
    
    def generate_signal(self, num_symbols=1000):
        """Generate complete OFDM signal"""
        signal = []
        for _ in range(num_symbols):
            symbol = self.generate_ofdm_symbol()
            signal.append(symbol)
        
        return np.concatenate(signal).astype(np.complex64)

# Generate OFDM variants
generator_20mhz = OFDMGenerator(fft_size=64, cp_len=16)
generator_40mhz = OFDMGenerator(fft_size=128, cp_len=32)
generator_80mhz = OFDMGenerator(fft_size=256, cp_len=64)

signals = {
    "ofdm_20mhz": generator_20mhz.generate_signal(5000),
    "ofdm_40mhz": generator_40mhz.generate_signal(5000),
    "ofdm_80mhz": generator_80mhz.generate_signal(5000)
}

for name, signal in signals.items():
    output_file = Path(f"data/iq/synthetic/ofdm/{name}.iq")
    signal.tofile(output_file)
Usage Examples
Loading Synthetic Data
python
import numpy as np
import json
from pathlib import Path

def load_synthetic_data(signal_type, category):
    """Load synthetic IQ data"""
    file_path = Path(f"data/iq/synthetic/{category}/{signal_type}.iq")
    meta_path = file_path.with_suffix('.json')
    
    # Load IQ data
    iq_data = np.fromfile(file_path, dtype=np.complex64)
    
    # Load metadata
    with open(meta_path, 'r') as f:
        metadata = json.load(f)
    
    return iq_data, metadata

# Examples
white_noise, meta = load_synthetic_data("white_gaussian", "noise")
ofdm_signal, meta = load_synthetic_data("ofdm_20mhz", "ofdm")
lora_signal, meta = load_synthetic_data("lora_sf7", "lora")
Parameter Sweep Testing
python
def test_snr_sweep():
    """Test detection performance across SNR range"""
    
    # Load clean signal
    signal, meta = load_synthetic_data("ofdm_20mhz", "ofdm")
    
    snr_values = [-10, -5, 0, 5, 10, 15, 20, 25, 30]
    results = {}
    
    for snr_db in snr_values:
        # Add noise
        signal_power = np.mean(np.abs(signal)**2)
        noise_power = signal_power / (10 ** (snr_db / 10))
        noise = np.sqrt(noise_power/2) * (np.random.randn(len(signal)) + 1j * np.random.randn(len(signal)))
        noisy = signal + noise
        
        # Process
        detections = detection_pipeline.process(noisy, meta['sample_rate'])
        results[snr_db] = len(detections) > 0
    
    return results
Modulation Recognition Testing
python
def test_modulation_recognition():
    """Test modulation classification accuracy"""
    
    modulations = {
        "ofdm_20mhz": "OFDM",
        "lora_sf7": "LoRa",
        "fm_analog": "FM"
    }
    
    results = {}
    
    for signal_name, expected_mod in modulations.items():
        signal, meta = load_synthetic_data(signal_name, 
                                          "ofdm" if "ofdm" in signal_name else 
                                          "lora" if "lora" in signal_name else 
                                          "fm")
        
        # Classify modulation
        detected_mod = modulation_classifier.classify(signal, meta['sample_rate'])
        
        results[signal_name] = {
            "expected": expected_mod,
            "detected": detected_mod,
            "correct": expected_mod == detected_mod
        }
    
    return results
Quality Metrics
Signal-to-Noise Ratio (SNR)
python
def calculate_snr(signal, noise_floor_db=-100):
    """Calculate SNR of synthetic signal"""
    signal_power = np.mean(np.abs(signal)**2)
    noise_power = 10 ** (noise_floor_db / 10)
    snr_db = 10 * np.log10(signal_power / noise_power)
    return snr_db
Peak-to-Average Power Ratio (PAPR)
python
def calculate_papr(signal):
    """Calculate PAPR in dB"""
    peak_power = np.max(np.abs(signal)**2)
    avg_power = np.mean(np.abs(signal)**2)
    papr_db = 10 * np.log10(peak_power / avg_power)
    return papr_db
Error Vector Magnitude (EVM)
python
def calculate_evm(signal, reference):
    """Calculate EVM percentage"""
    error = signal - reference
    evm_rms = np.sqrt(np.mean(np.abs(error)**2) / np.mean(np.abs(reference)**2))
    return evm_rms * 100
Validation Tools
Spectrum Validation
python
def validate_spectrum(signal, sample_rate, expected_bandwidth):
    """Validate signal spectrum characteristics"""
    from scipy import signal
    
    f, psd = signal.welch(signal, fs=sample_rate, nperseg=4096)
    psd_db = 10 * np.log10(psd + 1e-12)
    
    # Find occupied bandwidth
    threshold = np.max(psd_db) - 20  # 20 dB below peak
    occupied = np.where(psd_db > threshold)[0]
    occupied_bw = (f[occupied[-1]] - f[occupied[0]]) / 1e6
    
    is_valid = abs(occupied_bw - expected_bandwidth) < expected_bandwidth * 0.1
    
    return {
        "valid": is_valid,
        "measured_bw_mhz": occupied_bw,
        "expected_bw_mhz": expected_bandwidth,
        "error_pct": abs(occupied_bw - expected_bandwidth) / expected_bandwidth * 100
    }
Statistical Validation
python
def validate_statistics(signal):
    """Validate signal statistics"""
    from scipy import stats
    
    real = np.real(signal)
    imag = np.imag(signal)
    
    # Test for Gaussianity (if applicable)
    _, p_value = stats.normaltest(real[:10000])
    
    # Calculate moments
    skewness = stats.skew(real)
    kurtosis = stats.kurtosis(real)
    
    return {
        "is_gaussian": p_value > 0.05,
        "skewness": skewness,
        "kurtosis": kurtosis,
        "mean": np.mean(real),
        "std": np.std(real)
    }
Performance Benchmarks
Generation Speed
Signal Type	Duration	Generation Time	Memory Usage
White Noise	30s	0.5s	240 MB
Pink Noise	30s	2.0s	240 MB
OFDM (20MHz)	30s	1.5s	240 MB
OFDM (80MHz)	30s	3.0s	480 MB
LoRa SF7	30s	1.0s	240 MB
FM Analog	30s	0.8s	240 MB
Command Line Interface
bash
# Generate all synthetic data
python scripts/generate_synthetic_data.py --all

# Generate specific signal type
python scripts/generate_synthetic_data.py --type ofdm --bandwidth 20

# Generate with custom parameters
python scripts/generate_synthetic_data.py --type noise --duration 60 --snr 20

# Validate synthetic data
python scripts/generate_synthetic_data.py --validate

# Run benchmarks
python scripts/generate_synthetic_data.py --benchmark
Adding New Synthetic Signals
Signal Template
python
class CustomSignalGenerator:
    """Template for new synthetic signals"""
    
    def __init__(self, sample_rate=10e6, duration=30):
        self.sample_rate = sample_rate
        self.duration = duration
        self.num_samples = int(sample_rate * duration)
    
    def generate(self):
        """Generate the signal"""
        t = np.arange(self.num_samples) / self.sample_rate
        # Implement signal generation here
        signal = np.zeros(self.num_samples, dtype=np.complex128)
        return signal.astype(np.complex64)
    
    def save(self, output_path):
        """Save generated signal"""
        signal = self.generate()
        signal.tofile(output_path)
        
        # Save metadata
        metadata = {
            "signal_type": self.__class__.__name__,
            "sample_rate": self.sample_rate,
            "duration": self.duration,
            "num_samples": self.num_samples,
            "generation_date": datetime.now().isoformat()
        }
        
        with open(output_path.with_suffix('.json'), 'w') as f:
            json.dump(metadata, f, indent=2)
Troubleshooting
Issue	Solution
Signal clipping	Reduce amplitude or normalize
Unexpected spectrum	Verify generation parameters
Memory errors	Reduce duration or use chunking
Slow generation	Optimize FFT operations
