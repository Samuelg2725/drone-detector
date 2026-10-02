---
name: 🔧 Hardware Issue
about: Report hardware-related issues (SDR, antennas, USB, etc.)
title: '[HARDWARE] '
labels: hardware, bug, needs-triage
assignees: ''
---

## 🔧 Hardware Issue Description

<!-- A clear and concise description of the hardware issue. -->

**Hardware Component:**
- [ ] SDR Device (HackRF, RTL-SDR, Pluto, etc.)
- [ ] Antenna
- [ ] LNA (Low Noise Amplifier)
- [ ] USB Connection/Cable
- [ ] Power Supply
- [ ] GPS/Clock Synchronization
- [ ] Other: ___________

**Issue Type:**
- [ ] Device not detected
- [ ] Poor signal quality
- [ ] Overheating
- [ ] USB disconnection
- [ ] Performance degradation
- [ ] Physical damage
- [ ] Driver/firmware issue
- [ ] Other: ___________

## 📊 Hardware Configuration

**SDR Device Details:**
<!-- Run detection commands and paste output -->

<details>
<summary>SDR Detection Output</summary>

```bash
# HackRF
hackrf_info

# RTL-SDR
rtl_test -t
rtl_eeprom -d 0

# ADALM-PLUTO
iio_info -s

# General USB
lsusb
lsusb -t
dmesg | tail -50
</details>
Antenna Setup:

Antenna Type: <!-- e.g., Discone, Log-periodic, Patch, Yagi -->

Frequency Range: <!-- e.g., 2.4-2.5 GHz -->

Antenna Gain: <!-- e.g., 5 dBi -->

Cable Type: <!-- e.g., LMR-400, RG-58 -->

Cable Length: <!-- e.g., 10 meters -->

Mounting Location: <!-- e.g., Rooftop, Window, Indoor -->

Height above ground: <!-- e.g., 15 meters -->

Accessories:

LNA (Gain: ___ dB)

Bandpass Filter (Frequency: ___)

USB Isolator

Bias-Tee

GPSDO (GPS Disciplined Oscillator)

Cooling Fan/Heatsink

Other: ___________

Environmental Factors:

Temperature: ___ °C / ___ °F

Weather: ☀️ Clear / ☁️ Cloudy / 🌧️ Rain / ❄️ Snow

Interference sources nearby: <!-- e.g., WiFi routers, cell towers, microwave ovens -->

🔄 Steps to Reproduce
<!-- Steps to reproduce the hardware issue: -->
Connect hardware as described

Run command: __________

Observe behavior

📊 Observed Behavior
Symptoms:

<!-- Describe what you're experiencing -->
Error Messages:

text
<!-- Paste any error messages here -->
LED Status:

Power LED: [ ] On / [ ] Off / [ ] Blinking

Activity LED: [ ] On / [ ] Off / [ ] Blinking

Other LEDs: ___________

Signal Quality Metrics:

bash
# Run these commands and paste output (if possible)

# Signal strength
hackrf_sweep -f 2400:2500 -n 10

# Noise floor
rtl_power -f 2400M:2500M:1M -g 20 -i 1 -1 noise_measurement.csv

# Sample drops
# For HackRF:
hackrf_transfer -r /dev/null -s 20000000 -n 100000000 2>&1 | grep -i "drop"

# For RTL-SDR:
rtl_test -t 2>&1 | grep -i "lost"
📈 Expected Behavior
<!-- What should happen instead? -->
Expected Signal Characteristics:

Expected SNR: ___ dB

Expected noise floor: ___ dBm

Expected temperature: ___ °C

🏗️ System Environment
Operating System:

bash
uname -a
cat /etc/os-release
Drivers and Firmware:

bash
# Driver versions
modinfo hackrf
modinfo rtl2832

# Firmware versions
hackrf_info | grep "Firmware"
rtl_eeprom -d 0 | grep "Firmware"
USB Configuration:

bash
# USB bus information
lsusb -t
cat /sys/kernel/debug/usb/devices | grep -A 10 "HackRF"
🩺 Diagnostic Tests Performed
<!-- Check all that apply and provide results -->
Basic connectivity test

bash
# Results:
Signal test with known source

bash
# Results:
Temperature monitoring

bash
# Results (temperature over time):
USB bandwidth test

bash
# Results:
Different USB port/cable test

<!-- What happened? -->
Different antenna test

<!-- What happened? -->
LNA bypass test (if applicable)

<!-- What happened? -->
Mock mode test (software-only)

bash
export USE_MOCK_HARDWARE=true
# Results:
🔧 Troubleshooting Attempted
<!-- What have you tried to fix the issue? -->
Restarted SDR device

Reconnected USB cable

Changed USB port

Restarted computer

Updated drivers

Updated firmware

Changed antenna

Added/removed LNA

Changed gain settings

Changed frequency

Reduced sample rate

Added USB isolator

Added cooling

Other: ___________

Results of troubleshooting:

<!-- What happened after each attempt? -->
📸 Photos/Videos
<!-- If applicable, add photos of your hardware setup, LED status, or screenshots -->
📋 Configuration
<details> <summary>Hardware Configuration (config/hardware.yaml)</summary>
yaml
# Paste your hardware configuration here (redact sensitive info)
</details>
📎 Additional Context
<!-- Any other relevant information -->
When did the issue start? <!-- e.g., After update, after hardware change, always -->

Does it happen consistently? <!-- Always / Sometimes / Rarely -->

Does it happen with different software? <!-- e.g., SDR#, GQRX, other tools -->

Any recent changes to the environment? <!-- e.g., New equipment, moved antenna -->

✅ Checklist
I have searched for existing hardware issues (including closed)

I have checked the hardware setup guide

I have tested with mock mode (software-only)

I have tried basic troubleshooting steps

I have included diagnostic output

I have described my hardware configuration

I have provided steps to reproduce

I have attached photos if relevant

🚦 Severity Assessment
Critical: Hardware non-functional, system cannot operate

High: Major performance degradation, frequent issues

Medium: Intermittent issues, reduced performance

Low: Minor inconvenience, rare occurren ced

📞 Contact for Follow-up
Can we contact you for more information?

Discord: @username

GitHub: @username

Email: (only if comfortable)

<!-- Hardware issues often require detailed information. Please provide as much detail as possible to help us diagnose and fix the issue. -->
text

Here's also a `config.yml` for issue templates (if not already created):

```yaml
# .github/ISSUE_TEMPLATE/config.yml
blank_issues_enabled: false
contact_links:
  - name: 📚 Hardware Setup Guide
    url: https://docs.drone-detector.com/hardware_setup
    about: Check the hardware setup guide first
  - name: 🔧 Troubleshooting Guide
    url: https://docs.drone-detector.com/troubleshooting#hardware
    about: Common hardware issues and solutions
  - name: 💬 Discord Community
    url: https://discord.gg/drone-detector
    about: Get help from the community
  - name: 📖 SDR Documentation
    url: https://docs.drone-detector.com/sdr
    about: SDR-specific documentation
  - name: 🛒 Hardware Recommendations
    url: https://docs.drone-detector.com/hardware#recommendations
    about: Recommended hardware and vendors
This hardware issue template provides:

Hardware-Specific Sections:

Component identification (SDR, antenna, LNA, etc.)

Issue type classification

Detailed configuration collection

Diagnostic Commands:

SDR detection commands for all devices

USB diagnostics

Signal quality metrics

Temperature monitoring

Environmental Factors:

Temperature and weather conditions

Interference sources

Mounting location details

Antenna Configuration:

Type, gain, cable specs

Mounting height and location

Accessories used

Troubleshooting Steps:

Comprehensive checklist of attempted fixes

Results tracking

Systematic approach

Performance Metrics:

SNR measurements

Noise floor readings

Sample drop analysis

Temperature data

USB Configuration:

Bus information

Bandwidth testing

Cable/port testing

Software Comparison:

Test with other SDR software

Mock mode validation

Driver version verification

Visual Documentation:

Photos of hardware setup

LED status indicators

Screenshots of issues

This template helps hardware issues get properly diagnosed by collecting all the necessary information about the physical setup, environmental factors, and diagnostic test results.
