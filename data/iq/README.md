drone-detector/data/iq/README.md - IQ Data Directory Documentation

markdown
# IQ Data Directory

This directory contains all IQ (In-phase/Quadrature) data for the Drone Detection System. IQ data is the raw complex baseband signal captured by SDR hardware, representing both amplitude and phase information of RF signals.

## Directory Structure
data/iq/
├── README.md # This file
├── index.json # Global IQ data index
├── live/ # Live recordings from SDR
│ ├── README.md
│ ├── session_YYYYMMDD_HHMMSS/
│ │ ├── frame_000000.iq
│ │ ├── frame_000000.json
│ │ ├── ...
│ │ ├── session_metadata.json
│ │ └── detection_events.json
│ └── index.json
├── replay/ # Replay dataset for testing
│ ├── README.md
│ ├── dji_mavic_2.4g/
│ │ ├── recording_001.iq
│ │ ├── recording_001.json
│ │ └── dataset_info.json
│ ├── dji_mavic_5.8g/
│ ├── fpv_analog_5.8g/
│ ├── fpv_digital_5.8g/
│ ├── autel_evo_2.4g/
│ ├── skydio_2_2.4g/
│ ├── noise_only/
│ ├── interference/
│ ├── mixed_scenarios/
│ └── index.json
└── synthetic/ # Synthetically generated data
├── README.md
├── noise/
│ ├── white_gaussian.iq
│ ├── pink_noise.iq
│ └── impulsive_noise.iq
├── ofdm/
│ ├── ofdm_20mhz.iq
│ ├── ofdm_40mhz.iq
│ └── ofdm_80mhz.iq
├── lora/
│ ├── lora_sf7.iq
│ └── lora_sf12.iq
├── fm/
│ ├── fm_analog.iq
│ └── fm_digital.iq
├── test_tones/
│ ├── single_tone.iq
│ ├── multi_tone.iq
│ └── chirp.iq
└── index.json

text

## IQ Data Format

### File Format Specification

| Property | Value |
|----------|-------|
| File Extension | `.iq` |
| Format | Raw binary |
| Data Type | Complex 64-bit floating point (`np.complex64`) |
| Sample Size | 8 bytes (4 bytes real + 4 bytes imaginary) |
| Endianness | Little-endian (native system format) |
| No Header | Direct sample data only |

### Sample Structure

Each sample consists of two interleaved 32-bit floating point numbers:
Byte Offset	Content
0-3	I (Real) component
4-7	Q (Imaginary) component
8-11	I (Real) component (next sample)
12-15	Q (Imaginary) component (next sample)
...	
text

### Memory Layout

```python
import numpy as np

# Loading IQ data
iq_data = np.fromfile('file.iq', dtype=np.complex64)

# Individual sample access
sample = iq_data[0]
real = sample.real  # I component
imag = sample.imag  # Q component
Metadata Format
Each IQ file has a corresponding JSON metadata file with the same base name:

json
{
  "file_id": "frame_000000",
  "timestamp": "2024-01-15T14:30:22.123456Z",
  "sample_rate": 10000000,
  "center_frequency": 2440000000,
  "num_samples": 16384000,
  "duration_seconds": 1.6384,
  "data_source": "live|replay|synthetic",
  "signal_type": "drone|noise|interference",
  "drone_type": "DJI Mavic 3",
  "confidence": 0.95,
  "threat_level": "HIGH",
  "recording_device": {
    "type": "hackrf",
    "serial": "HACKRF001234",
    "sample_rate": 10000000,
    "gain": 20
  },
  "gps_location": {
    "latitude": 37.7749,
    "longitude": -122.4194,
    "altitude": 50.0
  },
  "analysis": {
    "snr_db": 15.2,
    "peak_frequency": 2440000000,
    "bandwidth": 20000000,
    "modulation": "OFDM"
  }
}
Global Index File
The index.json file provides a searchable index of all IQ data:

json
{
  "version": "2.0.0",
  "last_updated": "2024-01-15T14:35:45.678901Z",
  "total_files": 1250,
  "total_size_gb": 245.6,
  "total_duration_hours": 36.5,
  "by_category": {
    "live": {
      "count": 850,
      "size_gb": 180.2,
      "duration_hours": 24.5
    },
    "replay": {
      "count": 350,
      "size_gb": 58.4,
      "duration_hours": 10.5
    },
    "synthetic": {
      "count": 50,
      "size_gb": 7.0,
      "duration_hours": 1.5
    }
  },
  "by_signal_type": {
    "drone": {"count": 520, "size_gb": 98.5},
    "noise": {"count": 180, "size_gb": 32.4},
    "interference": {"count": 100, "size_gb": 18.7},
    "mixed": {"count": 50, "size_gb": 9.8}
  },
  "by_drone_type": {
    "DJI Mavic 3": {"count": 120, "size_gb": 22.5},
    "DJI Mini 3": {"count": 80, "size_gb": 15.2},
    "FPV Analog": {"count": 100, "size_gb": 18.9},
    "FPV Digital": {"count": 80, "size_gb": 15.1},
    "Autel EVO II": {"count": 70, "size_gb": 13.2},
    "Skydio 2": {"count": 70, "size_gb": 13.2}
  },
  "by_frequency_band": {
    "2.4 GHz": {"count": 650, "size_gb": 122.5},
    "5.8 GHz": {"count": 500, "size_gb": 94.3},
    "Other": {"count": 100, "size_gb": 18.8}
  }
}
Subdirectory Documentation
Live Recordings (live/)
Real-time recordings captured during system operation. See live/README.md for details.

Typical Use Cases:

Incident documentation

Forensic analysis

Real-time detection testing

Field validation

Replay Dataset (replay/)
Pre-recorded datasets for testing and validation. See replay/README.md for details.

Typical Use Cases:

Algorithm development

Regression testing

Performance benchmarking

Training data collection

Synthetic Data (synthetic/)
Computer-generated signals for controlled testing. See synthetic/README.md for details.

Typical Use Cases:

Edge case testing

Parameter sweep experiments

Modulation recognition

SNR robustness testing

Loading IQ Data
Python
python
import numpy as np
import json
from pathlib import Path

def load_iq_file(file_path):
    """Load IQ data and metadata"""
    file_path = Path(file_path)
    
    # Load IQ data
    iq_data = np.fromfile(file_path, dtype=np.complex64)
    
    # Load metadata
    meta_path = file_path.with_suffix('.json')
    with open(meta_path, 'r') as f:
        metadata = json.load(f)
    
    return iq_data, metadata

# Usage
iq_data, meta = load_iq_file('data/iq/live/session_20240115_143022/frame_000000.iq')
print(f"Loaded {len(iq_data)} samples at {meta['sample_rate']/1e6:.1f} MHz")
print(f"Duration: {len(iq_data) / meta['sample_rate']:.2f}s")
MATLAB
matlab
function [iq_data, metadata] = load_iq_file(filepath)
    % Load IQ data
    fid = fopen(filepath, 'rb');
    data = fread(fid, Inf, 'single');
    fclose(fid);
    
    % Reshape to complex
    iq_data = data(1:2:end) + 1j * data(2:2:end);
    
    % Load metadata
    [path, name, ~] = fileparts(filepath);
    metafile = fullfile(path, [name '.json']);
    fid = fopen(metafile, 'r');
    metadata = jsondecode(fread(fid, '*char')');
    fclose(fid);
end
GNU Radio
text
# File Source Block Configuration:
File: /path/to/file.iq
Type: complex
Repeat: No
Output Type: Complex Float32
Processing IQ Data
Basic Spectrum Analysis
python
import numpy as np
import matplotlib.pyplot as plt
from scipy import signal

def plot_spectrum(iq_data, sample_rate, title="Power Spectral Density"):
    """Plot power spectral density"""
    f, psd = signal.welch(iq_data, fs=sample_rate, nperseg=4096)
    psd_db = 10 * np.log10(psd + 1e-12)
    
    plt.figure(figsize=(12, 6))
    plt.plot(f / 1e6, psd_db)
    plt.xlabel('Frequency (MHz)')
    plt.ylabel('PSD (dBm/Hz)')
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.xlim([-sample_rate/2e6, sample_rate/2e6])
    plt.show()

# Usage
plot_spectrum(iq_data, meta['sample_rate'], f"Spectrum - {meta['signal_type']}")
Signal Detection
python
def detect_signal(iq_data, threshold_db=6):
    """Simple energy-based signal detection"""
    # Compute power
    power = np.abs(iq_data)**2
    power_db = 10 * np.log10(power + 1e-12)
    
    # Estimate noise floor
    noise_floor = np.percentile(power_db, 25)
    
    # Detect signal
    signal_mask = power_db > (noise_floor + threshold_db)
    
    return signal_mask

# Usage
signal_mask = detect_signal(iq_data)
signal_present = np.any(signal_mask)
print(f"Signal present: {signal_present}")
print(f"Signal duty cycle: {np.mean(signal_mask):.1%}")
Peak Detection
python
from scipy.signal import find_peaks

def find_peaks_in_spectrum(iq_data, sample_rate, height_db=-80):
    """Find peaks in power spectrum"""
    f, psd = signal.welch(iq_data, fs=sample_rate, nperseg=4096)
    psd_db = 10 * np.log10(psd + 1e-12)
    
    peaks, properties = find_peaks(psd_db, height=height_db, prominence=5)
    
    peak_freqs = f[peaks]
    peak_powers = psd_db[peaks]
    
    return peak_freqs, peak_powers, properties

# Usage
freqs, powers, props = find_peaks_in_spectrum(iq_data, meta['sample_rate'])
for freq, power in zip(freqs, powers):
    print(f"Peak at {freq/1e6:.2f} MHz: {power:.1f} dBm")
Storage Management
File Size Calculator
python
def calculate_file_size(sample_rate, duration_seconds):
    """Calculate IQ file size in bytes"""
    samples = sample_rate * duration_seconds
    bytes_per_sample = 8  # complex64
    size_bytes = samples * bytes_per_sample
    size_mb = size_bytes / (1024 ** 2)
    size_gb = size_bytes / (1024 ** 3)
    
    return {
        'samples': int(samples),
        'bytes': int(size_bytes),
        'mb': size_mb,
        'gb': size_gb
    }

# Examples
print("30 seconds at 10 MHz:", calculate_file_size(10e6, 30))
print("60 seconds at 20 MHz:", calculate_file_size(20e6, 60))
Storage Requirements
Duration	Sample Rate	File Size
1 second	2.4 MHz	19.2 MB
1 second	10 MHz	80 MB
1 second	20 MHz	160 MB
10 seconds	10 MHz	800 MB
60 seconds	10 MHz	4.8 GB
10 minutes	10 MHz	48 GB
Data Quality Metrics
SNR Estimation
python
def estimate_snr(iq_data):
    """Estimate SNR from IQ data"""
    # Compute power
    power = np.abs(iq_data)**2
    power_db = 10 * np.log10(power + 1e-12)
    
    # Estimate noise floor (10th percentile)
    noise_floor = np.percentile(power_db, 10)
    
    # Estimate signal power (90th percentile)
    signal_power = np.percentile(power_db, 90)
    
    snr_db = signal_power - noise_floor
    
    return {
        'snr_db': snr_db,
        'noise_floor_dbm': noise_floor,
        'signal_power_dbm': signal_power
    }
DC Offset Removal
python
def remove_dc_offset(iq_data):
    """Remove DC offset from IQ data"""
    return iq_data - np.mean(iq_data)

# Usage
iq_data_clean = remove_dc_offset(iq_data)
print(f"DC offset removed: {np.mean(iq_data):.6f} -> {np.mean(iq_data_clean):.6f}")
IQ Imbalance Correction
python
def correct_iq_imbalance(iq_data):
    """Correct IQ imbalance (phase and amplitude)"""
    # Calculate statistics
    real = np.real(iq_data)
    imag = np.imag(iq_data)
    
    # Amplitude correction
    gain_real = 1 / np.std(real)
    gain_imag = 1 / np.std(imag)
    
    # Phase correction
    phase_error = -np.mean(real * imag) / (np.std(real) * np.std(imag))
    
    # Apply corrections
    real_corrected = real * gain_real
    imag_corrected = (imag - phase_error * real) * gain_imag
    
    return real_corrected + 1j * imag_corrected
Data Validation
Integrity Check
python
def validate_iq_file(file_path):
    """Validate IQ file integrity"""
    file_path = Path(file_path)
    
    issues = []
    
    # Check file exists
    if not file_path.exists():
        issues.append("File not found")
        return False, issues
    
    # Check file size
    file_size = file_path.stat().st_size
    if file_size % 8 != 0:
        issues.append(f"Invalid file size: {file_size} bytes (not multiple of 8)")
    
    # Check metadata exists
    meta_path = file_path.with_suffix('.json')
    if not meta_path.exists():
        issues.append("Metadata file not found")
    
    # Check can load data
    try:
        data = np.fromfile(file_path, dtype=np.complex64)
        if len(data) == 0:
            issues.append("Empty file")
        if np.any(np.isnan(data)):
            issues.append("NaN values detected")
        if np.any(np.isinf(data)):
            issues.append("Infinite values detected")
    except Exception as e:
        issues.append(f"Cannot load: {e}")
    
    return len(issues) == 0, issues
Content Validation
python
def validate_iq_content(iq_data, sample_rate):
    """Validate IQ data content"""
    results = {}
    
    # Check signal power
    power = np.mean(np.abs(iq_data)**2)
    power_dbm = 10 * np.log10(power + 1e-12)
    results['power_dbm'] = power_dbm
    results['power_valid'] = -120 < power_dbm < 0
    
    # Check bandwidth
    f, psd = signal.welch(iq_data, fs=sample_rate, nperseg=4096)
    results['bandwidth_hz'] = f[-1] - f[0]
    results['bandwidth_valid'] = results['bandwidth_hz'] <= sample_rate
    
    # Check for clipping
    clip_threshold = 0.95
    clipping = np.abs(iq_data) > clip_threshold
    results['clipping_ratio'] = np.mean(clipping)
    results['clipping_valid'] = results['clipping_ratio'] < 0.01
    
    return results
Performance Optimization
Chunked Processing
python
def process_iq_chunks(file_path, chunk_size=1024*1024):
    """Process IQ file in chunks to manage memory"""
    file_size = Path(file_path).stat().st_size
    samples_per_chunk = chunk_size // 8  # 8 bytes per sample
    
    with open(file_path, 'rb') as f:
        while True:
            # Read chunk
            chunk_data = f.read(chunk_size)
            if not chunk_data:
                break
            
            # Convert to complex
            chunk = np.frombuffer(chunk_data, dtype=np.complex64)
            
            # Process chunk
            yield chunk

# Usage
for chunk in process_iq_chunks('large_file.iq'):
    process_chunk(chunk)  # Your processing function
Memory Mapping
python
def mmap_iq_file(file_path):
    """Memory-map large IQ file for efficient access"""
    file_path = Path(file_path)
    file_size = file_path.stat().st_size
    num_samples = file_size // 8
    
    # Memory map the file
    iq_data = np.memmap(file_path, dtype=np.complex64, mode='r', shape=(num_samples,))
    
    return iq_data

# Usage
iq_data = mmap_iq_file('large_file.iq')
print(f"Memory-mapped {len(iq_data)} samples")
# Access like normal array without loading into memory
sample = iq_data[1000000]  # Random access
Backup and Archiving
Compression
python
import gzip
import shutil

def compress_iq_file(file_path):
    """Compress IQ file with gzip"""
    compressed_path = file_path.with_suffix('.iq.gz')
    
    with open(file_path, 'rb') as f_in:
        with gzip.open(compressed_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    
    original_size = file_path.stat().st_size
    compressed_size = compressed_path.stat().st_size
    ratio = compressed_size / original_size
    
    print(f"Compressed: {original_size/1e6:.1f}MB -> {compressed_size/1e6:.1f}MB ({ratio:.1%})")
    
    return compressed_path
Archiving
python
import tarfile
from datetime import datetime

def archive_session(session_path):
    """Archive a recording session"""
    archive_name = f"{session_path.name}_{datetime.now().strftime('%Y%m%d')}.tar.gz"
    archive_path = session_path.parent / archive_name
    
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(session_path, arcname=session_path.name)
    
    print(f"Archived to: {archive_path}")
    return archive_path
Troubleshooting
Issue	Cause	Solution
File too large	Long duration/high sample rate	Use chunked processing or reduce duration
Memory error	Loading entire file	Use memory mapping or chunked reading
No signal detected	Low SNR or wrong frequency	Check SNR and center frequency
Clipping	Gain too high	Reduce gain or normalize data
DC offset	Hardware bias	Apply DC removal filter
IQ imbalance	Hardware imperfections	Apply correction algorithm
Best Practices
Always use metadata: Never use IQ files without their corresponding JSON metadata

Document recordings: Include detailed metadata for reproducible analysis

Validate data: Run validation checks before processing

Manage storage: Implement retention policies for old recordings

Use compression: Compress archived recordings to save space

Chunk large files: Process large files in chunks to manage memory

Backup important data: Regular backups of critical recordings
