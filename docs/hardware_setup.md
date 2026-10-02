# Drone Detector System - Hardware Setup Guide

## Overview

This guide covers the installation, configuration, and optimization of SDR (Software Defined Radio) hardware for the Drone Detector system. It includes setup procedures for supported devices, antenna selection, calibration, and performance tuning.

## Supported Hardware

### SDR Devices

| Device | Frequency Range | Bandwidth | Interface | Status | Use Case |
|--------|----------------|-----------|-----------|--------|----------|
| HackRF One | 1 MHz - 6 GHz | 20 MHz | USB 2.0 | ✅ Full Support | Multi-band scanning |
| RTL-SDR v3 | 500 kHz - 1.7 GHz | 2.4 MHz | USB 2.0 | ✅ Full Support | Cost-effective 2.4GHz |
| RTL-SDR v4 | 500 kHz - 1.7 GHz | 3.2 MHz | USB 3.0 | ✅ Full Support | Improved dynamic range |
| ADALM-PLUTO | 325 MHz - 3.8 GHz | 20 MHz | USB 2.0 | ✅ Full Support | Educational/2.4GHz |
| LimeSDR Mini | 10 MHz - 3.5 GHz | 30 MHz | USB 3.0 | ⚠️ Beta | Wideband scanning |
| USRP B200 | 70 MHz - 6 GHz | 56 MHz | USB 3.0 | ⚠️ Beta | High-performance |
| Airspy R2 | 24 MHz - 1.7 GHz | 10 MHz | USB 2.0 | ⚠️ Beta | Low noise floor |

### Antennas

| Antenna Type | Frequency | Gain | Pattern | Best For |
|--------------|-----------|------|---------|----------|
| Discone | 100 MHz - 3 GHz | 2-5 dBi | Omnidirectional | General purpose |
| Log-periodic | 400 MHz - 6 GHz | 6-10 dBi | Directional | Specific bands |
| Patch | 2.4 GHz | 5-8 dBi | Directional | 2.4GHz only |
| Yagi | 2.4/5.8 GHz | 10-15 dBi | Highly directional | Long range |
| Biconical | 70 MHz - 6 GHz | 0-3 dBi | Wide omni | Wideband scanning |
| Spiral | 400 MHz - 6 GHz | 3-5 dBi | Circular | Multi-polarization |

### Accessories

| Accessory | Purpose | Recommended |
|-----------|---------|-------------|
| LNA (Low Noise Amplifier) | Boost weak signals | Required for long range |
| Bandpass Filter | Reduce interference | Recommended for urban areas |
| USB Isolator | Ground loop prevention | Recommended for field use |
| RF Shield | Reduce EMI | Optional |
| GPS Dongle | Time synchronization | Required for TDOA |
| Cooling Fan | Prevent overheating | Required for continuous operation |

---

## Quick Start

### Minimal Hardware Setup

```bash
# 1. Connect SDR to USB port
# 2. Attach antenna to SMA connector
# 3. Install drivers (Ubuntu/Debian)
sudo apt update
sudo apt install -y hackrf rtl-sdr

# 4. Test SDR detection
hackrf_info
# or
rtl_test -t

# 5. Verify with software
sudo rtl_power -f 2400M:2500M:1M -g 20 -i 10 | grep -v "^#"
Hardware Connection Diagram
text
┌─────────────────────────────────────────────────────────────────┐
│                     Drone Detector Hardware Setup               │
│                                                                  │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐             │
│  │ Antenna  │─────▶│   LNA    │─────▶│  Filter  │             │
│  └──────────┘      │  (opt)   │      │  (opt)   │             │
│                    └──────────┘      └────┬─────┘             │
│                                           │                      │
│                                           ▼                      │
│                    ┌──────────┐      ┌──────────┐             │
│                    │   SDR    │◀─────│   USB    │             │
│                    │  Device  │      │ Isolator │             │
│                    └────┬─────┘      └──────────┘             │
│                         │                                        │
│                         ▼                                        │
│                    ┌──────────┐                                 │
│                    │ Computer │                                 │
│                    │   USB    │                                 │
│                    └──────────┘                                 │
│                                                                  │
│  Optional:                                                        │
│  ┌──────────┐      ┌──────────┐                                 │
│  │   GPS    │─────▶│  Time    │                                 │
│  │  Dongle  │      │  Sync    │                                 │
│  └──────────┘      └──────────┘                                 │
└─────────────────────────────────────────────────────────────────┘
Device-Specific Installation
HackRF One Installation
Driver Installation
bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y hackrf libhackrf-dev hackrf-tools

# Install from source (latest version)
git clone https://github.com/greatscottgadgets/hackrf.git
cd hackrf/host
mkdir build && cd build
cmake .. -DCMAKE_INSTALL_PREFIX=/usr/local
make -j4
sudo make install
sudo ldconfig

# Install Python bindings
pip install pyhackrf
Firmware Update
bash
# Check current firmware
hackrf_info | grep "Firmware Version"

# Download latest firmware
wget https://github.com/greatscottgadgets/hackrf/releases/latest/download/hackrf-linux.tar.xz
tar xf hackrf-linux.tar.xz

# Update firmware
cd hackrf-*/firmware/bin
hackrf_spiflash -w hackrf_one_usb.bin

# Verify update
hackrf_info
Calibration
bash
# Frequency calibration (using known reference)
hackrf_cal -c 10000000  # Crystal frequency adjustment
hackrf_cal -f 1000000000 -g 16  # Frequency calibration at 1GHz

# Store calibration values
hackrf_cal -s  # Save to device

# Verify calibration
hackrf_sweep -f 1000:2000 -n 1
Performance Optimization
bash
# Set USB buffer size
echo 0 > /sys/module/usbcore/parameters/usbfs_memory_mb

# Increase USB transfer size for HackRF
hackrf_transfer -t /dev/null -s 20000000 -b 1000000

# Optimize driver parameters
sudo modprobe hackrf
sudo sh -c 'echo -1 > /sys/module/hackrf/parameters/fifo_timeout_us'
RTL-SDR Installation
Driver Installation
bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y rtl-sdr librtlsdr-dev

# Install from source (with better performance)
git clone https://github.com/osmocom/rtl-sdr.git
cd rtl-sdr
mkdir build && cd build
cmake .. -DINSTALL_UDEV_RULES=ON -DDETACH_KERNEL_DRIVER=ON
make -j4
sudo make install
sudo ldconfig

# Install Python bindings
pip install pyrtlsdr

# Blacklist default DVB-T driver
sudo tee /etc/modprobe.d/rtl-sdr-blacklist.conf << EOF
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
EOF

sudo reboot
Device Testing
bash
# Basic test - should see samples
rtl_test -t

# Gain testing
rtl_test -g 0
rtl_test -g 20
rtl_test -g 40

# Frequency stability test
rtl_test -p

# SNR test at different frequencies
rtl_power -f 2400M:2500M:1M -g 20 -i 10 -1 -c 50% spectrum.csv
Frequency Correction (PPM)
bash
# Find PPM offset using known reference (e.g., GSM cell tower)
rtl_test -p

# Apply correction (example: 1.5 PPM)
rtl_sdr -f 100000000 -p 1.5 test.raw

# Permanent correction in config
echo "rtl_sdr_ppm=1.5" >> ~/.config/drone-detector/hardware.yaml
ADALM-PLUTO Installation
Driver Installation
bash
# Install libiio and dependencies
sudo apt update
sudo apt install -y libiio-utils libiio-dev libad9361-dev

# Install Pluto firmware
wget https://github.com/analogdevicesinc/plutosdr-fw/releases/latest/download/plutosdr-fw-latest.zip
unzip plutosdr-fw-latest.zip

# Update firmware
pluto_fw_update.py plutosdr-fw-latest/pluto.frm

# Verify connection
iio_info -s
Network Configuration
bash
# Default Pluto IP: 192.168.2.1
# Configure computer network interface
sudo ip addr add 192.168.2.10/24 dev eth0
sudo ip link set eth0 up

# Or use USB network mode
modprobe g_serial
modprobe g_ether

# Test connection
ping 192.168.2.1
iio_info -u ip:192.168.2.1
Performance Tuning
bash
# Increase buffer size
echo 4096 > /sys/bus/iio/devices/iio:device0/buffer/length

# Set higher sample rate
iio_attr -u ip:192.168.2.1 -c ad9361-phy voltage0 sampling_frequency 20000000

# Enable high-performance mode
iio_attr -u ip:192.168.2.1 -d ad9361-phy tx_path_rates rf_bandwidth 20000000
Antenna Setup
Antenna Selection Guide
yaml
# Recommended antenna configurations by scenario

Scenario: "Urban 2.4GHz monitoring"
  primary: "Patch 2.4GHz"
  secondary: "Discone"
  accessories:
    - "2.4GHz bandpass filter"
    - "LNA 15dB gain"

Scenario: "Suburban multi-band"
  primary: "Log-periodic 400MHz-6GHz"
  secondary: "Biconical"
  accessories:
    - "LNA 20dB gain"
    - "FM broadcast filter"

Scenario: "Rural long range"
  primary: "Yagi 2.4GHz 15dBi"
  secondary: "Yagi 5.8GHz 15dBi"
  accessories:
    - "High-gain LNA 30dB"
    - "Low-loss coax"
    - "Elevation mount"

Scenario: "Mobile/DJI tracking"
  primary: "Biconical wideband"
  accessories:
    - "GPS for position"
    - "Magnetic mount"
    - "12V DC power"
Antenna Placement
text
┌─────────────────────────────────────────────────────────────┐
│                   Antenna Placement Guide                   │
│                                                              │
│  Best:                                                      │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Rooftop mount, clear line of sight                │    │
│  │  Above surrounding structures                       │    │
│  │  Minimum 1m from metal objects                     │    │
│  │  Ground plane (if required by antenna)             │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  Acceptable:                                                │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Window mount, as high as possible                 │    │
│  │  Away from metal window frames                     │    │
│  │  Exterior wall mount                               │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  Avoid:                                                     │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Near electronic devices (computers, routers)      │    │
│  │  Inside metal enclosures/equipment racks           │    │
│  │  Near large metal surfaces                         │    │
│  │  Underground or basement                          │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
Coaxial Cable Selection
Cable Type	Loss at 2.4GHz (per 10m)	Use Case
RG-58	-15 dB	Short runs (<5m)
LMR-240	-8 dB	Medium runs (5-15m)
LMR-400	-4 dB	Long runs (15-30m)
LMR-600	-2.5 dB	Very long (>30m)
bash
# Calculate cable loss at 2.4GHz
# LMR-400: ~0.4dB/m
# 10m cable: -4dB loss
# Required LNA gain = 4dB + (cable loss) + 10dB (margin)

# Example cable calculation function
cable_loss() {
    local freq=$1  # 2.4e9
    local length=$2  # meters
    # LMR-400 loss formula (dB/m)
    loss_db_per_m = 0.25 * sqrt(freq/1e9)
    total_loss = loss_db_per_m * length
}
Multi-SDR Configuration
TDOA (Time Difference of Arrival) Setup
For drone localization using multiple receivers:

bash
# Hardware requirements per node:
# - GPS-disciplined oscillator (GPSDO)
# - High stability reference clock
# - Precision time synchronization

# Synchronize multiple devices
# Method 1: GPS PPS signal
sudo apt install gpsd gpsd-clients
sudo systemctl enable gpsd

# Configure GPS sharing
sudo tee /etc/default/gpsd << EOF
START_DAEMON="true"
USBAUTO="true"
DEVICES="/dev/ttyACM0"
GPSD_OPTIONS="-n"
EOF

# Check synchronization
gpsmon
cgps -s
Clock Distribution
text
┌─────────────────────────────────────────────────────────────────┐
│                  Multi-SDR Clock Distribution                   │
│                                                                  │
│  Option 1: GPS Disciplined Oscillator (GPSDO)                   │
│  ┌──────────┐      ┌──────────┐                               │
│  │   GPS    │─────▶│  GPSDO   │─────▶ 10MHz out to all SDRs  │
│  │ Antenna  │      │          │                               │
│  └──────────┘      └────────────────────────────┬────────────┘│
│                                                   │              │
│                            ┌──────────────────────┼────────────┐│
│                            │                      │            ││
│                            ▼                      ▼            ││
│                    ┌──────────┐            ┌──────────┐       ││
│                    │  SDR #1  │            │  SDR #2  │       ││
│                    │ 10MHz IN │            │ 10MHz IN │       ││
│                    └──────────┘            └──────────┘       ││
│                                                                 │
│  Option 2: Network Time Protocol (NTP)                         │
│  ┌──────────┐                                                    │
│  │   GPS    │─────▶ PTP/NTP Server ─────▶ All computers       │
│  │ Antenna  │                                                    │
│  └──────────┘                                                    │
│                                                                  │
│  Option 3: Shared Reference Clock                              │
│  ┌──────────┐      ┌──────────┐                               │
│  │   OCXO   │─────▶│  Buffer  │─────▶ Distribution amp      │
│  │ Reference│      │   Amp    │       to all SDRs            │
│  └──────────┘      └──────────┘                               │
└─────────────────────────────────────────────────────────────────┘
Multi-SDR Configuration File
yaml
# config/multi_sdr.yaml
hardware:
  devices:
    - id: "hackrf_1"
      type: "hackrf"
      serial: "HACKRF000001"
      frequency: 2.45e9
      sample_rate: 20e6
      gain: 24
      position:
        latitude: 37.7749
        longitude: -122.4194
        altitude: 10.0
      clock_source: "gpsdo"
      time_source: "gps"
      
    - id: "hackrf_2"
      type: "hackrf"
      serial: "HACKRF000002"
      frequency: 2.45e9
      sample_rate: 20e6
      gain: 24
      position:
        latitude: 37.7750
        longitude: -122.4195
        altitude: 10.0
      clock_source: "gpsdo"
      time_source: "gps"
      
    - id: "rtl_1"
      type: "rtl_sdr"
      index: 0
      frequency: 2.45e9
      sample_rate: 2.4e6
      gain: 30
      ppm: 1.5  # Frequency correction
      bias_tee: true  # Enable for active antenna
      
  tdoa:
    enabled: true
    reference_device: "hackrf_1"
    max_distance_m: 1000
    update_rate: 10  # Hz
    algorithm: "gcc_phat"  # Generalized cross-correlation
    
  synchronization:
    method: "gps"
    pps_enabled: true
    max_timestamp_error_us: 100
    calibration_interval: 3600  # seconds
Signal Optimization
Gain Settings Optimization
python
# gain_optimizer.py - Automatic gain optimization

import numpy as np
from rtlsdr import RtlSdr

class GainOptimizer:
    def __init__(self, device):
        self.device = device
        self.gain_range = range(0, 50, 5)  # 0 to 45dB in 5dB steps
        
    def measure_snr(self, frequency, gain):
        """Measure SNR at specific gain setting"""
        self.device.set_center_freq(frequency)
        self.device.set_gain(gain)
        
        # Collect samples
        samples = self.device.read_samples(100000)
        
        # Calculate signal power vs noise
        signal_power = np.mean(np.abs(samples) ** 2)
        
        # Estimate noise floor (median of sorted powers)
        power_sorted = np.sort(np.abs(samples) ** 2)
        noise_power = np.median(power_sorted[:len(power_sorted)//2])
        
        snr = 10 * np.log10(signal_power / noise_power)
        return snr
    
    def optimize_gain(self, frequency):
        """Find optimal gain setting"""
        snr_results = []
        
        for gain in self.gain_range:
            snr = self.measure_snr(frequency, gain)
            snr_results.append((gain, snr))
            print(f"Gain: {gain}dB, SNR: {snr:.1f}dB")
        
        # Find gain with best SNR, avoiding saturation
        optimal_gain = max(snr_results, key=lambda x: x[1])
        return optimal_gain[0]
bash
# Run gain optimization
python scripts/optimize_gain.py --frequency 2.45e9 --device hackrf
# Output: Optimal gain: 24dB, SNR: 28.5dB
Filter Selection Guide
yaml
filters:
  # Band-specific filters
  "2.4GHz bandpass":
    frequency: "2.4-2.5 GHz"
    insertion_loss: "1.5dB"
    rejection:
      - "800-900MHz: >50dB"
      - "1.2-1.3GHz: >40dB"
      - "5.8GHz: >60dB"
    application: "Urban 2.4GHz drone detection"
    
  "FM broadcast bandstop":
    frequency: "88-108 MHz"
    rejection: ">40dB"
    application: "Remove FM broadcast interference"
    
  "LTE bandstop":
    frequency: "700-900 MHz"
    rejection: ">35dB"
    application: "Cellular interference mitigation"
    
  "Low noise amplifier (LNA)":
    gain: "20-30dB"
    noise_figure: "<1dB"
    p1db: ">10dBm"
    application: "Weak signal amplification"
Noise Mitigation
bash
# Identify noise sources
rtl_power -f 0:6e9:1M -g 20 -i 1 -1 noise_scan.csv
python scripts/analyze_noise.py noise_scan.csv

# Common fixes for identified noise
# USB noise
sudo apt install usbguard
# Add ferrite beads to USB cables

# Power supply noise
# Use linear power supply instead of switching
# Add LC filter on DC input

# Computer EMI
# Use shielded case
# Relocate computer away from antenna
# Use fiber optic USB extenders

# Environmental interference
# Identify WiFi routers, move channels
# Identify microwave ovens, time scheduling
# Identify cell towers, add rejection filter
Environmental Considerations
Temperature Management
bash
# Monitor SDR temperature (HackRF)
watch -n 1 hackrf_info | grep "Temperature"

# Cooling solutions
# Option 1: Passive heatsink
sudo apt install lm-sensors
sensors

# Option 2: Active fan control
cat > /etc/udev/rules.d/99-sdr-fan.rules << EOF
SUBSYSTEM=="usb", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6089", RUN+="/usr/local/bin/sdr-cooling.sh"
EOF

# Option 3: Enclosure with air circulation
# Use metal enclosure as heatsink
# Install 12V DC fan with PWM control
Weather Protection (Outdoor Installations)
bash
# Weatherproof enclosure requirements
# - IP65 or higher rating
# - Solar radiation shield
# - Active cooling (for hot climates)
# - Heater (for freezing climates)

# Antenna weatherproofing
# - Use self-amalgamating tape on connectors
# - Apply dielectric grease to connections
# - Install drip loops in cables
# - Use lightning arrestor

# Lightning protection
# - Install lightning rod above antenna
# - Use gas discharge tube protector
# - Ground all equipment
# - Use fiber optic for data (not copper)
Performance Testing
Throughput Testing
bash
# Test maximum sample rate
# HackRF
hackrf_transfer -r /dev/null -s 20000000 -n 100000000

# RTL-SDR
rtl_sdr -f 2450000000 -s 2400000 -n 10000000 /dev/null

# PlutoSDR
iio_readdev -u ip:192.168.2.1 -b 1000000 cf-ad9361-lpc | dd of=/dev/null bs=1M

# Measure performance metrics
time hackrf_transfer -r test.raw -s 20000000 -n 1000000000 2>&1 | grep "throughput"
Range Testing
bash
#!/bin/bash
# range_test.sh - Test detection range

# Place drone at measured distances
distances=(50 100 200 300 500 1000)

for distance in "${distances[@]}"; do
    echo "Testing at ${distance}m..."
    
    # Record 1 minute of IQ data
    hackrf_transfer -r range_test_${distance}m.raw \
        -f 2450000000 -s 20000000 -n 600000000
    
    # Process detection
    python scripts/analyze_range.py range_test_${distance}m.raw
    
    # Upload to server or log
    curl -X POST https://api.drone-detector.com/test/range \
        -d "distance=${distance}&file=range_test_${distance}m.raw"
done
Sensitivity Testing
python
# sensitivity_test.py
import numpy as np
from hackrf import HackRF

def test_sensitivity():
    """Measure receiver sensitivity at various frequencies"""
    frequencies = [900e6, 2.4e9, 5.8e9]
    gains = [0, 10, 20, 30, 40, 50]
    
    results = {}
    
    with HackRF() as hrf:
        for freq in frequencies:
            hrf.set_freq(freq)
            
            for gain in gains:
                hrf.set_gain(gain)
                
                # Measure noise floor
                noise = []
                for _ in range(100):
                    samples = hrf.read_samples(10000)
                    power = 10 * np.log10(np.mean(np.abs(samples)**2))
                    noise.append(power)
                
                results[f"{freq/1e9}GHz_{gain}dB"] = np.mean(noise)
                print(f"Freq: {freq/1e9}GHz, Gain: {gain}dB, Noise: {np.mean(noise):.1f}dBm")
    
    return results

results = test_sensitivity()
Troubleshooting Hardware Issues
Common Problems and Solutions
bash
# Problem: SDR not detected
lsusb | grep -i "hackrf\|rtl"
sudo dmesg | tail -20
sudo modprobe hackrf
sudo systemctl restart udev

# Problem: USB disconnect/reconnect
# Check USB port power
lsusb -v 2>&1 | grep -E "MaxPower|bMaxPower"
# Use powered USB hub
# Use shorter, higher quality USB cable

# Problem: High noise floor
# Identify source
python scripts/identify_noise.py --frequency 2.45e9
# Typical fixes:
# - Use shielded USB cable
# - Add ferrite beads
# - Use linear power supply
# - Move antenna away from computer

# Problem: Poor signal quality
# Check antenna
hackrf_info | grep "Antenna"
# Check LNA power
# Check for damaged cables

# Problem: Overheating
hackrf_info | grep "Temperature"
# Add heatsink
# Reduce gain
# Reduce sample rate
# Add fan

# Problem: Frequency drift
hackrf_cal -f 1000000000 -g 16  # Recalibrate
rtl_test -p  # Check RTL PPM
# Use external reference clock
# Warm up device for 15 minutes
Diagnostic Commands
bash
# Comprehensive hardware diagnostics
# HackRF
hackrf_info
hackrf_clock
hackrf_max283x
hackrf_si5351c
hackrf_rffc5071
hackrf_spiflash -R

# RTL-SDR
rtl_test -t
rtl_test -p
rtl_eeprom -d 0
rtl_biast -d 0

# General USB
lsusb -t
usb-devices
sudo lsusb -v | grep -E "iSerial|bcdDevice"

# System
dmesg | grep -i "usb\|sdr"
lspci | grep -i usb
sysctl -a | grep usb
Hardware Logging
yaml
# config/hardware_monitoring.yaml
monitoring:
  enabled: true
  interval: 60  # seconds
  metrics:
    - temperature
    - gain_setting
    - sample_rate
    - frequency
    - sample_dropped_rate
    - usb_errors
  logging:
    file: /var/log/drone-detector/hardware.log
    retention_days: 30
  alerts:
    temperature:
      warning: 60°C
      critical: 75°C
    sample_drops:
      warning: 1%
      critical: 5%
Hardware Maintenance
Regular Maintenance Schedule
Component	Interval	Action
SDR Device	Daily	Check temperature, sample drops
Antenna	Weekly	Inspect connections, weatherproofing
Cables	Monthly	Check for damage, corrosion
LNA	Monthly	Check gain, noise figure
Power supply	Monthly	Measure voltage, current
GPSDO	Quarterly	Check lock status, phase noise
Full calibration	Annually	Factory calibration
Cleaning Procedure
bash
# Antenna cleaning
# Use isopropyl alcohol (70%) on connectors
# Use compressed air on radiating elements
# Apply new dielectric grease

# SDR device cleaning
# Use compressed air for ventilation ports
# Check for dust accumulation
# Clean USB connector with contact cleaner

# Ground connections
# Check resistance < 5 ohms
# Clean grounding rods
# Check for corrosion
Calibration Checklist
bash
# Frequency calibration
# Use GPS-disciplined oscillator or known broadcast station
# Measure offset at multiple frequencies
# Apply correction

# Gain calibration
# Use calibrated signal generator
# Measure linearity across gain range
# Create correction table

# Time calibration
# For TDOA systems
# Measure timestamp error between devices
# Apply calibration

# Antenna calibration
# Measure SWR
# Measure radiation pattern
# Verify connector loss
Advanced Configurations
Remote SDR Operation
bash
# Setup rtl_tcp server on remote SDR
rtl_tcp -a 0.0.0.0 -p 1234 -f 2450000000 -g 20

# Connect from client
rtl_sdr -d rtl_tcp://remote_host:1234 -f 2450000000 -s 2400000 test.raw

# With HackRF (using hackrf_net)
hackrf_net -a remote_host -p 1234
Multiple Frequency Bands (Frequency Hopping)
yaml
# config/hopping.yaml
frequency_hopping:
  enabled: true
  bands:
    - frequency: 2.45e9
      dwell_ms: 100
      gain: 24
    - frequency: 5.8e9
      dwell_ms: 100
      gain: 24
    - frequency: 915e6
      dwell_ms: 100
      gain: 30
    - frequency: 1.2e9
      dwell_ms: 100
      gain: 30
  transition_ms: 5
  priority_events:
    - type: "detection"
      stay_ms: 1000
Automatic Gain Control (AGC)
python
# agc_controller.py - Adaptive gain control
class AGController:
    def __init__(self, target_snr=25):
        self.target_snr = target_snr
        self.gain_history = []
        
    def adjust_gain(self, current_snr, current_gain):
        # Calculate gain error
        error = self.target_snr - current_snr
        
        # PID-like control
        gain_adjustment = error * 0.5
        
        # Limit adjustments
        new_gain = current_gain + gain_adjustment
        new_gain = max(0, min(40, new_gain))  # Clamp 0-40dB
        
        self.gain_history.append(new_gain)
        
        # Smoothing
        if len(self.gain_history) > 5:
            smoothed_gain = np.mean(self.gain_history[-5:])
            return int(smoothed_gain)
        
        return int(new_gain)
Safety Guidelines
RF Safety
yaml
# RF exposure limits (FCC/ICNIRP)
power_density:
  general_public: "0.1 mW/cm²"
  occupational: "1 mW/cm²"

# Safety distances for transmitter antennas
min_distance:
  "10W transmitter": "0.5m"
  "100W transmitter": "2m"
  "1000W transmitter": "6m"

# Precautionary measures:
# - Always terminate unused SDR ports with 50Ω load
# - Do not touch active antenna elements
# - Verify transmitter power before connection
# - Use RF safety interlock on high power systems
Electrical Safety
bash
# Grounding requirements
# - Resistance to ground: < 5 ohms
# - Ground rod depth: 2.4m (8ft) minimum
# - Bond all equipment to common ground point

# Power protection
# - Use surge protector on AC mains
# - Install UPS with AVR
# - Use isolation transformer for sensitive equipment
# - Implement over-current protection

# Lightning safety
# - Disconnect antennas during storms
# - Install lightning arrestor at building entry
# - Use gas discharge tubes on all coax lines
# - Remove power during storm activity
Procurement Guide
Recommended Hardware Kits
yaml
# Starter Kit (~$200)
- 1x RTL-SDR v3 ($30)
- 1x 2.4GHz patch antenna ($20)
- 1x USB extension cable with ferrite ($10)
- 1x SMA to MCX adapter ($5)
Total: ~$65

# Professional Kit (~$500)
- 1x HackRF One ($300)
- 1x Wideband discone antenna ($80)
- 1x LNA - 20dB gain ($40)
- 1x 2.4GHz bandpass filter ($30)
- 1x USB 3.0 extension cable ($15)
- 1x SMA male to SMA male cable ($10)
Total: ~$475

# Enterprise Kit (~$2000)
- 2x HackRF One with GPSDO ($800)
- 2x Log-periodic antennas ($200)
- 2x High-gain LNA 30dB ($100)
- 2x Band-specific filters ($60)
- 1x GPS disciplined oscillator ($300)
- 1x 8-port power distribution ($80)
- 1x Weatherproof enclosure ($100)
- 1x Active USB 3.0 extender ($50)
Total: ~$1690

# TDOA Localization Kit (~$5000)
- 3x HackRF One with GPSDO ($1200)
- 3x High-precision GPS antennas ($300)
- 3x Directional antennas ($300)
- 3x High-dynamic LNA ($150)
- 1x Precision time server ($2000)
- 3x Weatherproof enclosures ($300)
- 1x Network switch ($150)
- 3x Cat6 shielded cables ($150)
Total: ~$4550
Where to Buy
Component	Suppliers
HackRF	Great Scott Gadgets, Amazon, Mouser
RTL-SDR	Amazon, AliExpress, Nooelec
Antennas	L-Com, Pasternack, Taoglas
LNAs	Mini-Circuits, RF Bay, eBay
Cables	Belden, Times Microwave, Amphenol
Enclosures	Bud Industries, Hammond, Polycase
