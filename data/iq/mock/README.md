drone-detector/data/iq/mock/README.md - Mock IQ Data Documentation

markdown
# Mock IQ Data Directory

This directory contains synthetic IQ data files for testing and development of the Drone Detection System. These files simulate various drone signals, interference sources, and noise floors to enable comprehensive testing without requiring actual hardware or live drone flights.

## Directory Structure
data/iq/mock/
├── README.md # This file
├── dji_mavic_2.4g.iq # DJI Mavic 2.4 GHz signal
├── dji_mavic_2.4g.json # Metadata for DJI 2.4 GHz
├── dji_mavic_5.8g.iq # DJI Mavic 5.8 GHz signal
├── dji_mavic_5.8g.json # Metadata for DJI 5.8 GHz
├── fpv_analog_5.8g.iq # FPV Analog 5.8 GHz video
├── fpv_analog_5.8g.json # Metadata for FPV Analog
├── noise_floor.iq # General noise floor
├── noise_floor.json # Noise floor metadata
├── interference_wifi.iq # WiFi interference
├── interference_wifi.json # WiFi metadata
├── calibration_signal.iq # Calibration tones
└── generation_scripts/ # Scripts to regenerate data
├── generate_dji_mavic.py
├── generate_fpv_analog.py
├── generate_noise_floor.py
└── generate_wifi_interference.py

text

## File Formats

### IQ Data Files (.iq)

- **Format**: Raw binary, interleaved 32-bit floats (I, Q)
- **Data Type**: `np.complex64` (8 bytes per sample)
- **Endianness**: Little-endian (native system format)
- **No header**: Direct sample data only

### Metadata Files (.json)

Each `.iq` file has a corresponding `.json` metadata file containing:

```json
{
  "signal_type": "DJI Mavic 3",
  "center_frequency": 2412000000,
  "sample_rate": 10000000,
  "duration_seconds": 30,
  "num_samples": 300000000,
  "modulation": "OFDM",
  "bandwidth": 20000000,
  "snr_db": 15,
  "statistics": {
    "mean": 0.001234,
    "std": 0.123456,
    "mean_power_dbm": -45.2,
    "peak_power_dbm": -30.1
  },
  "generation_date": "2024-01-15T10:30:00Z"
}
Available Mock Data
1. DJI Mavic Signals
2.4 GHz Version (dji_mavic_2.4g.iq)
Parameter	Value
Frequency	2.412 GHz (Channel 1)
Sample Rate	10 MHz
Bandwidth	20 MHz
Modulation	OFDM (256 subcarriers)
Cyclic Prefix	64 samples
SNR	15 dB
Doppler Shift	50 Hz
Duration	30 seconds
Use Case: Testing detection of DJI OcuSync 2.4 GHz transmissions.

5.8 GHz Version (dji_mavic_5.8g.iq)
Parameter	Value
Frequency	5.825 GHz
Sample Rate	20 MHz
Bandwidth	40 MHz
Modulation	OFDM (512 subcarriers)
Cyclic Prefix	128 samples
SNR	18 dB
Frequency Hopping	Enabled (8 channels)
Duration	30 seconds
Use Case: Testing detection of DJI OcuSync 5.8 GHz transmissions with frequency hopping.

2. FPV Analog Signal (fpv_analog_5.8g.iq)
Parameter	Value
Frequency	5.800 GHz (Raceband 8)
Sample Rate	10 MHz
Bandwidth	8 MHz
Modulation	FM
Video Standard	NTSC
Video Deviation	4.5 MHz
Audio Subcarrier	4.5 MHz
SNR	12 dB
Multipath	Enabled
Duration	30 seconds
Use Case: Testing detection of analog FPV video transmissions.

3. Noise Floor Signals
General Noise Floor (noise_floor.iq)
Parameter	Value
Type	Thermal + Atmospheric
Sample Rate	10 MHz
Noise Floor	-100 dBm
Temperature	290 K
Duration	30 seconds
Environment Variants:

File	Environment	Noise Floor	Characteristics
noise_floor_urban.iq	Urban	-85 dBm	High interference, impulse noise
noise_floor_suburban.iq	Suburban	-95 dBm	Moderate interference
noise_floor_rural.iq	Rural	-105 dBm	Low interference, atmospheric
noise_floor_industrial.iq	Industrial	-80 dBm	High impulse noise
noise_floor_office.iq	Office	-90 dBm	WiFi/BT interference
4. WiFi Interference (interference_wifi.iq)
Parameter	Value
Standard	802.11n
Band	2.4 GHz
Channel	7
Frequency	2.442 GHz
Channel Width	20/40 MHz
Traffic Type	Continuous
SNR	20 dB
Duration	30 seconds
Standard Variants:

File	Standard	Max Rate	Band
interference_wifi_802.11b.iq	802.11b	11 Mbps	2.4 GHz
interference_wifi_802.11g.iq	802.11g	54 Mbps	2.4 GHz
interference_wifi_802.11n.iq	802.11n	600 Mbps	2.4/5 GHz
interference_wifi_802.11ac.iq	802.11ac	3.5 Gbps	5 GHz
5. Calibration Signal (calibration_signal.iq)
Parameter	Value
Tones	±2 MHz, ±1 MHz, ±500 kHz, ±100 kHz, 0
Duration	10 seconds
SNR	20 dB
Use Case: System calibration and frequency response testing.

Loading IQ Data
Python Example
python
import numpy as np
import json

def load_iq_data(filepath):
    """Load IQ data and metadata from file"""
    filepath = Path(filepath)
    
    # Load metadata
    with open(filepath.with_suffix('.json'), 'r') as f:
        metadata = json.load(f)
    
    # Load IQ data
    iq_data = np.fromfile(filepath, dtype=np.complex64)
    
    return iq_data, metadata

# Example usage
iq_data, meta = load_iq_data('data/iq/mock/dji_mavic_2.4g.iq')

print(f"Signal: {meta['signal_type']}")
print(f"Samples: {len(iq_data):,}")
print(f"Duration: {len(iq_data) / meta['sample_rate']:.2f}s")
print(f"Sample Rate: {meta['sample_rate']/1e6:.1f} MHz")

# Process the IQ data
# ... your detection logic here ...
MATLAB/Octave Example
matlab
% Load IQ data
filename = 'data/iq/mock/dji_mavic_2.4g.iq';
fid = fopen(filename, 'rb');
iq_data = fread(fid, Inf, 'single');
fclose(fid);

% Reshape to complex (interleaved I/Q)
iq_data = iq_data(1:2:end) + 1j * iq_data(2:2:end);

% Load metadata
fid = fopen(strrep(filename, '.iq', '.json'), 'r');
metadata = jsondecode(fread(fid, '*char')');
fclose(fid);

fprintf('Signal: %s\n', metadata.signal_type);
fprintf('Samples: %d\n', length(iq_data));
fprintf('Duration: %.2f s\n', length(iq_data) / metadata.sample_rate);
GNU Radio Example
python
# In GNU Radio Companion, use the File Source block:
# File: data/iq/mock/dji_mavic_2.4g.iq
# Type: complex
# Repeat: No
Visualization Examples
Plot Spectrum
python
import matplotlib.pyplot as plt
from scipy import signal

def plot_spectrum(iq_data, sample_rate, title="Spectrum"):
    """Plot power spectral density"""
    f, psd = signal.welch(iq_data, fs=sample_rate, nperseg=4096)
    psd_db = 10 * np.log10(psd + 1e-12)
    
    plt.figure(figsize=(12, 6))
    plt.plot(f / 1e6, psd_db)
    plt.xlabel('Frequency (MHz)')
    plt.ylabel('PSD (dBm/Hz)')
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.xlim([-10, 10])  # Show ±10 MHz around center
    plt.show()

# Usage
iq_data, meta = load_iq_data('data/iq/mock/dji_mavic_2.4g.iq')
plot_spectrum(iq_data, meta['sample_rate'], meta['signal_type'])
Plot Constellation
python
def plot_constellation(iq_data, num_points=1000):
    """Plot IQ constellation diagram"""
    plt.figure(figsize=(8, 8))
    plt.scatter(np.real(iq_data[:num_points]), 
                np.imag(iq_data[:num_points]), 
                s=1, alpha=0.5)
    plt.xlabel('In-phase')
    plt.ylabel('Quadrature')
    plt.title('Constellation Diagram')
    plt.grid(True, alpha=0.3)
    plt.axis('equal')
    plt.show()
Performance Characteristics
File Sizes
Duration	Samples	File Size (complex64)
1 second	10e6	80 MB
10 seconds	100e6	800 MB
30 seconds	300e6	2.4 GB
60 seconds	600e6	4.8 GB
Processing Time Estimates
Operation	Duration (30 sec file)
File Load	~2-5 seconds
FFT (2048 pts)	~0.5 seconds
PSD Computation	~1 second
Peak Detection	~0.2 seconds
ML Classification	~0.1 seconds
Regenerating Mock Data
All mock data files can be regenerated using the provided generation scripts:

bash
# Regenerate DJI Mavic signals
python generation_scripts/generate_dji_mavic.py --duration 30

# Regenerate FPV Analog signal
python generation_scripts/generate_fpv_analog.py --duration 30

# Regenerate noise floor
python generation_scripts/generate_noise_floor.py --duration 30

# Regenerate WiFi interference
python generation_scripts/generate_wifi_interference.py --duration 30
Custom Generation Parameters
bash
# Generate custom DJI signal
python generation_scripts/generate_dji_mavic.py \
    --duration 60 \
    --snr 20 \
    --frequency 2.44e9 \
    --sample-rate 20e6

# Generate custom noise floor
python generation_scripts/generate_noise_floor.py \
    --duration 60 \
    --environment industrial \
    --noise-floor -80

# Generate multi-channel WiFi
python generation_scripts/generate_wifi_interference.py \
    --multi-channel \
    --duration 10
Testing Scenarios
Scenario 1: Basic Detection
python
# Test detection on DJI Mavic signal
iq_data, meta = load_iq_data('data/iq/mock/dji_mavic_2.4g.iq')
detections = detector.process(iq_data, meta['sample_rate'])
assert len(detections) > 0
assert detections[0]['drone_type'] == 'DJI Mavic'
Scenario 2: Interference Rejection
python
# Mix drone signal with interference
drone, drone_meta = load_iq_data('data/iq/mock/dji_mavic_2.4g.iq')
wifi, wifi_meta = load_iq_data('data/iq/mock/interference_wifi.iq')

# Mix signals
mixed = drone + 0.5 * wifi[:len(drone)]

# Test detection still works
detections = detector.process(mixed, drone_meta['sample_rate'])
Scenario 3: Low SNR Performance
python
import numpy as np

# Load clean signal
iq_data, meta = load_iq_data('data/iq/mock/dji_mavic_2.4g.iq')

# Add noise to reduce SNR
noise_power = 10 ** (meta['statistics']['mean_power_dbm'] / 10) / (10 ** (5 / 10))
noise = np.sqrt(noise_power/2) * (np.random.randn(len(iq_data)) + 1j * np.random.randn(len(iq_data)))
noisy_signal = iq_data + noise

# Test detection at 5 dB SNR
detections = detector.process(noisy_signal, meta['sample_rate'])
Troubleshooting
Common Issues
Issue	Solution
File not found	Verify file path and generation
Memory error	Use chunked processing for large files
Wrong sample rate	Check metadata for correct sample rate
No detections	Verify signal is within frequency range
File Integrity Check
python
def verify_iq_file(filepath):
    """Verify IQ file integrity"""
    # Check file exists
    if not Path(filepath).exists():
        return False, "File not found"
    
    # Check metadata exists
    if not Path(filepath).with_suffix('.json').exists():
        return False, "Metadata not found"
    
    # Check file size
    file_size = Path(filepath).stat().st_size
    if file_size % 8 != 0:
        return False, f"Invalid file size: {file_size} bytes"
    
    # Check data integrity
    try:
        data = np.fromfile(filepath, dtype=np.complex64)
        if len(data) == 0:
            return False, "Empty file"
        if np.any(np.isnan(data)):
            return False, "NaN values detected"
        if np.any(np.isinf(data)):
            return False, "Infinite values detected"
    except Exception as e:
        return False, str(e)
    
    return True, "OK"
License
All mock data files and generation scripts are part of the Drone Detection System and are subject to the same license terms.

Version History
Version	Date	Changes
2.0.0	2024-01-15	Added 5.8 GHz variants, multi-environment noise
1.0.0	2023-12-01	Initial release with basic mock data
