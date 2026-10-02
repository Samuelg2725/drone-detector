drone-detector/tests/hardware/README.md - Hardware Tests Documentation

markdown
# Hardware Tests Directory

This directory contains hardware test suites for the Drone Detection System, including tests for SDR devices (HackRF, RTL-SDR, Pluto), antenna controllers, signal generators, and other hardware components. These tests verify that hardware devices are functioning correctly and meeting performance requirements.

## Directory Structure
tests/hardware/
├── README.md # This file
├── init.py # Package initialization and utilities
├── hackrf/ # HackRF One tests
│ ├── test_hackrf_basic.py # Basic device functionality
│ ├── test_hackrf_gain.py # Gain control tests
│ └── test_hackrf_stability.py # Long-term stability tests
├── rtl_sdr/ # RTL-SDR tests
│ ├── test_rtl_basic.py # Basic RTL-SDR functionality
│ └── test_rtl_tuning.py # Frequency tuning tests
├── pluto/ # ADALM-PLUTO tests
│ ├── test_pluto_basic.py # Basic Pluto functionality
│ └── test_pluto_network.py # Network operation tests
├── mock/ # Mock hardware tests
│ ├── test_mock_hardware.py # Mock SDR tests
│ └── test_mock_scenarios.py # Scenario management tests
└── utils/ # Testing utilities
└── rf_sanity_check.py # RF sanity check utilities

text

## Hardware Test Categories

### HackRF One Tests (`hackrf/`)

| Test File | Description | Key Test Areas |
|-----------|-------------|----------------|
| `test_hackrf_basic.py` | Basic device functionality | Detection, initialization, tuning, sample reading |
| `test_hackrf_gain.py` | Gain control testing | LNA/VGA ranges, linearity, AMP control |
| `test_hackrf_stability.py` | Long-term stability | Temperature effects, drift, continuous operation |

### RTL-SDR Tests (`rtl_sdr/`)

| Test File | Description | Key Test Areas |
|-----------|-------------|----------------|
| `test_rtl_basic.py` | Basic RTL-SDR functionality | Device detection, tuning, sample capture |
| `test_rtl_tuning.py` | Frequency tuning tests | Range accuracy, settling time, drift |

### ADALM-PLUTO Tests (`pluto/`)

| Test File | Description | Key Test Areas |
|-----------|-------------|----------------|
| `test_pluto_basic.py` | Basic Pluto functionality | Device init, RX/TX, gain control |
| `test_pluto_network.py` | Network operation | Remote access, streaming, latency |

### Mock Hardware Tests (`mock/`)

| Test File | Description | Key Test Areas |
|-----------|-------------|----------------|
| `test_mock_hardware.py` | Mock SDR tests | Signal generation, streaming, error simulation |
| `test_mock_scenarios.py` | Scenario management | Scenario switching, signal characteristics |

### Utilities (`utils/`)

| File | Description | Key Features |
|------|-------------|--------------|
| `rf_sanity_check.py` | RF hardware validation | Signal detection, frequency accuracy, noise floor |

## Prerequisites

### Hardware Requirements

| Device | Minimum Requirements | Recommended |
|--------|---------------------|-------------|
| HackRF One | USB 3.0 port, antenna | 10 MHz reference, LNA |
| RTL-SDR | USB 2.0 port, antenna | TCXO version |
| ADALM-PLUTO | USB port or network | External antenna |

### Software Requirements

```bash
# Install SDR libraries
sudo apt-get install libhackrf-dev librtlsdr-dev libiio-dev

# Install Python dependencies
pip install pyhackrf pyrtlsdr pyadi-iio
pip install numpy scipy matplotlib

# Install test dependencies
pip install pytest pytest-cov pytest-asyncio pytest-timeout
Running Hardware Tests
Basic Test Execution
bash
# Run all hardware tests
python -m pytest tests/hardware/ -v

# Run HackRF tests only
python -m pytest tests/hardware/hackrf/ -v

# Run specific test file
python -m pytest tests/hardware/hackrf/test_hackrf_basic.py -v

# Run specific test class
python -m pytest tests/hackrf/test_hackrf_gain.py::TestHackRFLNAGain -v
With Hardware Detection
bash
# Tests automatically skip if hardware not present
python -m pytest tests/hardware/hackrf/ -v

# Force hardware tests (fail if not present)
python -m pytest tests/hardware/hackrf/ -v --require-hardware

# Run mock tests only (no hardware needed)
python -m pytest tests/hardware/mock/ -v
Performance Testing
bash
# Run stability tests (long duration)
python -m pytest tests/hardware/hackrf/test_hackrf_stability.py -v

# Run gain sweep tests
python -m pytest tests/hardware/hackrf/test_hackrf_gain.py::TestHackRFLNAGain -v

# Run with performance profiling
python -m pytest tests/hardware/hackrf/test_hackrf_basic.py --durations=10
With Coverage
bash
# Run with coverage report
python -m pytest tests/hardware/hackrf/ --cov=. --cov-report=html

# Generate XML coverage for CI
python -m pytest tests/hardware/hackrf/ --cov=. --cov-report=xml
Test Configuration
Environment Variables
Variable	Description	Default
HACKRF_SERIAL	Specific HackRF serial number	None (auto-detect)
RTL_SDR_INDEX	RTL-SDR device index	0
PLUTO_URI	Pluto network URI	usb:0
HARDWARE_TIMEOUT	Test timeout (seconds)	30
RF_SOURCE_FREQ	Known signal frequency for testing	100e6
Test Configuration File
yaml
# hardware_test_config.yaml
hardware:
  hackrf:
    enabled: true
    serial: null
    sample_rate: 10e6
    timeout: 30
  
  rtl_sdr:
    enabled: true
    index: 0
    sample_rate: 2.4e6
  
  pluto:
    enabled: false
    uri: "usb:0"
    network: "192.168.2.1"

test:
  frequencies:
    vhf: [88e6, 100e6, 108e6, 144e6, 440e6]
    "2.4g": [2.400e9, 2.412e9, 2.442e9, 2.472e9]
    "5.8g": [5.150e9, 5.180e9, 5.320e9, 5.725e9, 5.825e9]
  
  sample_rates: [1e6, 2.4e6, 5e6, 8e6, 10e6, 20e6]
  
  thresholds:
    min_sample_rate_msps: 8.0
    max_tuning_time_ms: 100.0
    min_detection_snr_db: 10.0
    max_noise_floor_dbm: -85.0
Writing Hardware Tests
Test Structure Template
python
import unittest
from tests.hardware import require_hardware, HardwareTestCase

class TestDeviceFeature(HardwareTestCase):
    """Test device specific feature"""
    
    @classmethod
    def setUpClass(cls):
        """Initialize device once for all tests"""
        cls.device = DeviceClass()
        cls.device.initialize({'sample_rate': 10e6})
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after tests"""
        cls.device.close()
    
    @require_hardware('hackrf')
    def test_feature(self):
        """Test specific device feature"""
        # Configure device
        self.device.tune(2.44e9)
        self.device.set_gain(20)
        
        # Perform test
        samples = self.device.read_samples(16384)
        
        # Verify results
        self.assertGreater(len(samples), 0)
        self.record_measurement("sample_count", len(samples))
        
        # Assert with context
        self.assertTestPass(
            self.device.is_ready(),
            "Device not ready"
        )
Using Test Helpers
python
from tests.hardware import HardwareTestHelper

class TestWithHelpers(HardwareTestCase):
    
    def test_frequency_scan(self):
        # Get test frequencies
        freqs = self.helper.get_test_frequencies('2g')
        
        # Measure tuning time
        tuning_time = self.helper.measure_tuning_time(self.device, freqs)
        
        # Generate test signal
        signal = self.helper.generate_test_signal(100e6, snr_db=20)
        
        # Create test directory for logs
        log_dir = self.helper.create_test_directory('hackrf')
Test Data
Test Signal Files
text
tests/hardware/data/
├── test_signals/
│   ├── tone_100MHz.iq          # 100 MHz test tone
│   ├── chirp_2.4GHz.iq         # Chirp signal
│   └── modulated_5.8GHz.iq     # Modulated test signal
├── expected/
│   ├── spectrum_expected.npy   # Expected spectrum data
│   └── constellation.npy       # Expected constellation
└── calibration/
    ├── noise_floor.json        # Calibrated noise floor
    └── gain_calibration.npy    # Gain calibration data
RF Sanity Check
Quick Hardware Validation
python
from tests.hardware.utils.rf_sanity_check import RFSanityChecker, quick_connectivity_test

# Quick connectivity test
if quick_connectivity_test(hackrf):
    print("HackRF connected")

# Full sanity check
checker = RFSanityChecker(hackrf)
results = checker.run_all_tests()
checker.generate_report(results, "rf_report.html")
Continuous Integration
GitHub Actions Workflow
yaml
name: Hardware Tests

on:
  push:
    branches: [ main ]
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  hackrf-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install HackRF drivers
        run: sudo apt-get install -y libhackrf-dev
      - name: Run HackRF tests
        run: pytest tests/hardware/hackrf/ -v --cov=. --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
Test Coverage Goals
Component	Target Coverage	Current
HackRF Basic	90%	-
HackRF Gain	85%	-
HackRF Stability	80%	-
RTL-SDR Basic	85%	-
Pluto Basic	80%	-
Mock Hardware	95%	-
Utilities	70%	-
Troubleshooting
Common Issues
Issue	Cause	Solution
Device not found	USB connection issue	Check cable, replug device
Permission denied	udev rules not set	Run sudo ./setup_udev.sh
Tests timeout	Device not responding	Check power, reset device
High noise floor	Antenna not connected	Connect antenna
Frequency drift	PLL not locked	Increase settle time
Debugging Hardware Tests
bash
# Run with hardware debug output
HACKRF_DEBUG=1 pytest tests/hardware/hackrf/ -v

# Capture USB traffic (requires wireshark)
sudo usbmon -i 2 -o capture.pcap

# Monitor device temperature
while true; do hackrf_info | grep temp; sleep 1; done

# Check USB bandwidth
lsusb -t | grep -A 5 HackRF
Best Practices
Hardware Protection: Never exceed maximum input levels

Test Isolation: Each test should leave device in known state

Timeout Management: Set appropriate timeouts for hardware operations

Resource Cleanup: Always close device handles after tests

Signal Levels: Use attenuators for high-power testing

Temperature Awareness: Allow warm-up time before tests

USB Bandwidth: Don't exceed USB bandwidth limits

Ground Loops: Use proper grounding to avoid noise

Safety Guidelines
Hazard	Precaution
RF Radiation	Use dummy load when transmitting
ESD	Use grounded wrist strap
Overheating	Ensure adequate ventilation
Power surges	Use USB isolator
Antenna contact	Keep antennas clear of people
