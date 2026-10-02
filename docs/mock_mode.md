# Drone Detector - Mock Mode Usage Guide

## Overview

Mock Mode simulates drone detection system behavior without physical SDR hardware. This is ideal for:
- Development and testing without radio equipment
- CI/CD pipeline integration
- Training and demonstrations
- Capacity planning and load testing
- Algorithm development and validation

## Quick Start

### Enable Mock Mode

```bash
# Method 1: Environment variable
export USE_MOCK_HARDWARE=true
export HARDWARE_TYPE=mock
python run.py

# Method 2: Command line argument
python run.py --mock

# Method 3: Configuration file
# Edit config/system.yaml
system:
  mode: development
  mock_mode: true

hardware:
  type: mock
  mock_scenario: "default"
Verify Mock Mode is Active
bash
# Check status
curl http://localhost:8888/api/v1/system/info

# Response should show:
{
  "hardware": {
    "type": "mock",
    "connected": true,
    "mock_active": true
  }
}

# Check logs
docker-compose logs api | grep -i mock
# Should see: "Initializing Mock Hardware...", "Mock mode active"
Mock Mode Architecture
text
┌─────────────────────────────────────────────────────────────────────┐
│                        Mock Mode Architecture                       │
│                                                                      │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐     │
│  │   Mock SDR   │─────▶│ Mock Signal  │─────▶│   Detector   │     │
│  │   Hardware   │      │  Generator   │      │   Pipeline   │     │
│  └──────────────┘      └──────────────┘      └──────┬───────┘     │
│                                                      │              │
│  ┌──────────────┐      ┌──────────────┐             │              │
│  │   Mock IQ    │─────▶│   Mock       │             │              │
│  │   Files      │      │   Drone      │◀────────────┘              │
│  └──────────────┘      │   Events     │                            │
│                        └──────────────┘                            │
│                                                                      │
│  Mock Data Sources:                                                 │
│  • Synthetic signal generation                                      │
│  • Pre-recorded IQ files                                           │
│  • Programmatic scenarios                                          │
│  • Random event injection                                          │
└─────────────────────────────────────────────────────────────────────┘
Configuration
Mock Mode Configuration File
yaml
# config/mock_config.yaml
mock:
  # General settings
  enabled: true
  hardware_type: "mock_hackrf"  # mock_hackrf, mock_rtl, mock_pluto
  
  # Signal generation
  signal_generator:
    enabled: true
    sample_rate: 2000000  # Hz
    center_frequency: 2450000000  # Hz
    noise_floor: -100  # dBm
    snr_range: [10, 30]  # dB
    fading_enabled: true
    
  # Drone simulation
  drone_simulation:
    enabled: true
    min_drones: 1
    max_drones: 5
    spawn_rate: 0.1  # drones per second
    movement_enabled: true
    
  # Data sources
  data_sources:
    - type: "synthetic"  # Generate synthetic IQ data
      weight: 0.7
    - type: "replay"     # Replay pre-recorded IQ
      weight: 0.3
      source_dir: "/app/data/iq/mock"
      
  # Performance simulation
  performance:
    simulate_latency_ms: [10, 50]  # Random latency
    simulate_cpu_load: true
    max_cpu_percent: 30
    simulate_dropped_samples: false
    drop_rate: 0.001  # 0.1% drops
    
  # Error simulation
  error_simulation:
    simulate_hardware_errors: false
    error_rate: 0.01  # 1% error rate
    error_types: ["timeout", "disconnect", "overflow"]
    
  # Scenarios
  scenarios:
    default: "urban_low_density"
    available:
      - "urban_low_density"
      - "urban_high_density"
      - "rural_scattered"
      - "multi_band"
      - "interference_heavy"
      - "tdoa_localization"
Environment Variables
bash
# Basic mock configuration
export USE_MOCK_HARDWARE=true
export MOCK_SCENARIO="urban_high_density"
export MOCK_DRONE_COUNT=10

# Signal parameters
export MOCK_NOISE_FLOOR=-100
export MOCK_SNR_MIN=10
export MOCK_SNR_MAX=30

# Performance simulation
export MOCK_LATENCY_MS=25
export MOCK_CPU_LOAD=20

# Data source
export MOCK_DATA_SOURCE="synthetic"
export MOCK_DATA_DIR="/app/data/iq/mock"

# Error simulation
export MOCK_ERROR_RATE=0.001
export MOCK_SIMULATE_HARDWARE_ERRORS=false
Mock Hardware Components
MockSDR Class
python
# Infrastructure/hardware/mock_hardware.py
from infrastructure.hardware.mock_hardware import MockSDR

# Initialize mock SDR
mock_sdr = MockSDR()
mock_sdr.initialize({
    'sample_rate': 2e6,
    'center_frequency': 2.45e9,
    'gain': 20,
    'mock_scenario': 'urban_low_density'
})

# Start streaming
async for iq_samples in mock_sdr.start_stream():
    # iq_samples contains simulated IQ data
    process_samples(iq_samples)

# Inject custom drone
mock_sdr.inject_drone(
    drone_type="DJI Mavic 3",
    frequency=2.45e9,
    signal_power=-50,
    duration_seconds=10
)

# Simulate hardware error
mock_sdr.simulate_error("disconnect")

# Get mock status
status = mock_sdr.get_status()
print(status['mock_mode'], status['simulated_drones'])
Mock Hardware Factory
python
# Using hardware factory with mock
from infrastructure.hardware.hardware_factory import HardwareFactory

factory = HardwareFactory()
config = {
    'type': 'mock',
    'mock_config': {
        'scenario': 'urban_high_density',
        'sample_rate': 5e6
    }
}

sdr = factory.create_hardware(config)
Mock Signal Generation
Synthetic IQ Generation
python
# scripts/generate_mock_data.py - Create synthetic IQ data

from mock_signal_generator import MockSignalGenerator

# Initialize generator
generator = MockSignalGenerator(
    sample_rate=20e6,
    duration_seconds=60,
    noise_floor=-100
)

# Add drone signals
generator.add_drone_signal(
    drone_type="DJI",
    frequency_offset=10e6,
    power=-50,
    bandwidth=20e6
)

generator.add_drone_signal(
    drone_type="FPV",
    frequency_offset=-15e6,
    power=-45,
    bandwidth=5e6
)

# Generate IQ data
iq_samples = generator.generate()

# Save to file
generator.save_to_file("generated_iq.bin")
Scenario Templates
yaml
# config/mock_scenarios/urban_low_density.yaml
name: "Urban Low Density"
description: "Low drone traffic in urban environment"

environment:
  noise_floor: -95
  interference_sources:
    - type: "wifi"
      channels: [1, 6, 11]
      power: -70
    - type: "bluetooth"
      channels: [78]
      power: -80

drones:
  - type: "DJI Mavic 3"
    frequency: 2.45e9
    power: -50
    duration: 30
    movement:
      type: "hover"
      radius: 50
      
  - type: "FPV Analog"
    frequency: 5.8e9
    power: -45
    duration: 45
    movement:
      type: "flyby"
      speed: 10  # m/s

schedule:
  - time: 0-300
    drones: [1]
  - time: 300-600
    drones: [2]
  - time: 600-900
    drones: [1, 2]
Programmatic Signal Generation
python
# Custom signal generation

import numpy as np
from scipy import signal

class CustomMockGenerator:
    """Generate custom mock signals"""
    
    def generate_ofdm_signal(self, duration, bandwidth, subcarriers=1024):
        """Generate OFDM signal (DJI-like)"""
        sample_rate = bandwidth * 2
        n_samples = int(duration * sample_rate)
        
        # Generate random QAM symbols
        symbols = (2 * np.random.randint(0, 2, n_samples) - 1) + \
                  1j * (2 * np.random.randint(0, 2, n_samples) - 1)
        
        # OFDM modulation
        ofdm_signal = self._ofdm_modulate(symbols, subcarriers)
        
        return ofdm_signal
    
    def generate_fm_signal(self, duration, bandwidth, modulation_index=1.5):
        """Generate analog FM signal (FPV-like)"""
        sample_rate = bandwidth * 5
        t = np.arange(0, duration, 1/sample_rate)
        
        # Baseband message
        message = np.sin(2 * np.pi * 100 * t) + \
                  0.5 * np.sin(2 * np.pi * 300 * t)
        
        # FM modulation
        fm_signal = np.exp(1j * 2 * np.pi * modulation_index * 
                          np.cumsum(message) / sample_rate)
        
        return fm_signal
Mock Data Replay
Recording Real Signals for Replay
bash
# Record real IQ data for later replay
python scripts/record_live_for_mock.py \
    --duration 300 \
    --frequency 2.45e9 \
    --sample-rate 20e6 \
    --output /app/data/iq/mock/live_session_001.iq

# Convert to mock format
python scripts/convert_to_mock.py \
    --input live_session_001.iq \
    --add-metadata \
    --include-detections
Replay Configuration
yaml
# config/replay_config.yaml
replay:
  enabled: true
  source_type: "directory"
  source_path: "/app/data/iq/mock"
  
  repeat: true
  loop_count: 10
  
  randomize_order: true
  
  metadata:
    include_spectrum: true
    include_detections: true
    
  performance:
    speed_factor: 1.0  # Replay speed multiplier
    drop_frames: false
Replay API
bash
# List available replay files
curl http://localhost:8888/api/v1/mock/replay/files

# Start replay of specific file
curl -X POST http://localhost:8888/api/v1/mock/replay/start \
  -H "Content-Type: application/json" \
  -d '{"file": "dji_mavic_2.4g.iq", "loop": true}'

# Stop replay
curl -X POST http://localhost:8888/api/v1/mock/replay/stop

# Get replay status
curl http://localhost:8888/api/v1/mock/replay/status
Testing with Mock Mode
Unit Tests
python
# tests/unit/test_detection_with_mock.py
import pytest
from infrastructure.hardware.mock_hardware import MockSDR
from domain.services.detection_service import DetectionService

@pytest.mark.asyncio
async def test_detection_pipeline():
    """Test detection pipeline with mock hardware"""
    
    # Setup mock hardware
    mock_sdr = MockSDR()
    mock_sdr.initialize({
        'mock_scenario': 'single_drone',
        'drone_type': 'DJI Mavic 3'
    })
    
    # Create detection service
    detector = DetectionService(hardware=mock_sdr)
    
    # Process one frame
    async for iq_samples in mock_sdr.start_stream():
        detection = await detector.process_frame(iq_samples)
        
        # Assert detection was found
        assert detection is not None
        assert detection.drone_type == "DJI Mavic 3"
        assert detection.confidence > 0.8
        break

@pytest.mark.parametrize("scenario", [
    "urban_low_density",
    "urban_high_density", 
    "multi_band",
    "interference_heavy"
])
def test_scenarios(scenario):
    """Test various mock scenarios"""
    mock_sdr = MockSDR()
    mock_sdr.initialize({'mock_scenario': scenario})
    
    # Run test suite
    results = run_detection_tests(mock_sdr)
    
    assert results['detection_rate'] > 0.8
    assert results['false_positive_rate'] < 0.1
Integration Tests
python
# tests/integration/test_mock_pipeline.py
async def test_full_pipeline_mock():
    """Test complete pipeline with mock data"""
    
    # Setup
    config = MockConfig.from_yaml("config/mock_config.yaml")
    hardware = MockSDR(config.hardware)
    api_client = TestClient(app)
    
    # Inject custom drone
    hardware.inject_drone(
        drone_type="Custom Drone",
        frequency=2.45e9,
        duration=30
    )
    
    # Start detection
    async with hardware.start_stream():
        await asyncio.sleep(2)
        
        # Check API endpoint
        response = await api_client.get("/api/v1/detections")
        assert response.status_code == 200
        
        detections = response.json()['data']
        assert len(detections) > 0
        assert detections[0]['drone_type'] == "Custom Drone"
Load Testing
python
# tests/performance/test_mock_load.py
async def test_high_throughput_mock():
    """Test system with high event rate using mock"""
    
    config = MockConfig(
        drone_spawn_rate=10,  # 10 drones per second
        max_drones=100,
        event_rate=1000  # 1000 events/sec
    )
    
    stats = await run_load_test(config, duration=60)
    
    assert stats['throughput'] > 900  # events/sec
    assert stats['max_latency'] < 100  # ms
    assert stats['error_rate'] < 0.01
Mock Mode Scenarios
Predefined Scenarios
python
# Access via API
scenarios = {
    "empty": {
        "description": "No signals, clean spectrum",
        "drones": [],
        "noise_floor": -110
    },
    
    "single_drone_2.4ghz": {
        "description": "Single DJI drone at 2.4GHz",
        "drones": [{
            "type": "DJI Mavic 3",
            "frequency": 2.45e9,
            "power": -50,
            "duration": 60
        }]
    },
    
    "single_drone_5.8ghz": {
        "description": "Single FPV drone at 5.8GHz",
        "drones": [{
            "type": "FPV Digital",
            "frequency": 5.8e9,
            "power": -45,
            "duration": 60
        }]
    },
    
    "multi_drone_mixed": {
        "description": "Multiple drones on different bands",
        "drones": [
            {"type": "DJI Mavic 3", "frequency": 2.45e9, "power": -50},
            {"type": "FPV Analog", "frequency": 5.8e9, "power": -45},
            {"type": "Custom Building", "frequency": 2.45e9, "power": -55}
        ]
    },
    
    "interference": {
        "description": "Drone with interference",
        "interference_sources": [
            {"type": "wifi", "power": -65, "bandwidth": 20e6},
            {"type": "bluetooth", "power": -70, "bandwidth": 1e6},
            {"type": "microwave", "power": -60, "bandwidth": 10e6}
        ],
        "drones": [{"type": "DJI Mini", "frequency": 2.45e9, "power": -60}]
    },
    
    "tdoa_localization": {
        "description": "Multi-receiver TDOA simulation",
        "receivers": 3,
        "drone_movement": {
            "trajectory": "circle",
            "radius": 500,
            "speed": 10
        }
    }
}
Custom Scenario Creation
python
# Creating custom scenario programmatically
from mock_scenario import MockScenarioBuilder

builder = MockScenarioBuilder()
builder.set_noise_floor(-100)
builder.add_drone(
    drone_type="Custom OFDM",
    start_time=0,
    duration=30,
    frequency=2.45e9,
    power=-50,
    bandwidth=20e6,
    movement={
        "type": "linear",
        "start": [37.7749, -122.4194, 100],
        "end": [37.7755, -122.4185, 150],
        "speed": 15
    }
)
builder.add_interference(
    type="wifi",
    strength=-70,
    channels=[1, 6, 11]
)
builder.set_schedule([
    {"time": 0, "action": "start_drone", "drone_index": 0},
    {"time": 15, "action": "increase_power", "drone_index": 0, "delta": 10},
    {"time": 30, "action": "stop_drone", "drone_index": 0}
])

scenario = builder.build()
scenario.save_to_file("custom_scenario.yaml")
API Endpoints for Mock Control
Mock Management API
bash
# Get mock status
curl http://localhost:8888/api/v1/mock/status

# Response
{
  "enabled": true,
  "active": true,
  "current_scenario": "urban_low_density",
  "active_drones": 3,
  "total_detections_simulated": 1245,
  "uptime_seconds": 3600
}

# Change scenario on-the-fly
curl -X POST http://localhost:8888/api/v1/mock/scenario \
  -H "Content-Type: application/json" \
  -d '{"scenario": "urban_high_density"}'

# Inject custom drone
curl -X POST http://localhost:8888/api/v1/mock/inject \
  -H "Content-Type: application/json" \
  -d '{
    "drone_type": "Test Drone",
    "frequency": 2450000000,
    "power": -45,
    "duration": 30,
    "trajectory": {
      "type": "line",
      "start": [37.7749, -122.4194],
      "end": [37.7755, -122.4185]
    }
  }'

# Simulate hardware error
curl -X POST http://localhost:8888/api/v1/mock/error \
  -H "Content-Type: application/json" \
  -d '{"error_type": "disconnect", "duration": 5}'

# Reset mock state
curl -X POST http://localhost:8888/api/v1/mock/reset

# Get available scenarios
curl http://localhost:8888/api/v1/mock/scenarios
WebSocket Control
javascript
// Control mock mode via WebSocket
const ws = new WebSocket('ws://localhost:8888/api/v1/ws');

ws.onopen = () => {
  // Enable mock mode
  ws.send(JSON.stringify({
    type: "mock_command",
    command: "enable",
    config: {
      scenario: "urban_high_density",
      drone_count: 10
    }
  }));
  
  // Inject drone event
  ws.send(JSON.stringify({
    type: "mock_command",
    command: "inject_drone",
    data: {
      drone_type: "Custom Drone",
      confidence: 0.95
    }
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === "mock_event") {
    console.log("Mock event:", data.event);
  }
};
Debugging & Visualization
Mock Mode Dashboard
python
# Access mock debug dashboard
# http://localhost:8888/mock/debug

# Features:
# - Real-time spectrum visualization
# - Drone positions on map
# - Event timeline
# - Hardware status simulation
# - Scenario controls

# API endpoints for debug data
curl http://localhost:8888/api/v1/mock/debug/spectrum
curl http://localhost:8888/api/v1/mock/debug/positions
curl http://localhost:8888/api/v1/mock/debug/events?limit=100
Logging Mock Operations
yaml
# config/logging.yaml - Mock-specific logging
loggers:
  mock_hardware:
    level: DEBUG
    handlers: [console, file]
    propagate: false
    
  mock_generator:
    level: INFO
    handlers: [file]
    
handlers:
  file:
    class: logging.handlers.RotatingFileHandler
    filename: /var/log/drone-detector/mock.log
    maxBytes: 10485760  # 10MB
    backupCount: 10
bash
# View mock logs
tail -f /var/log/drone-detector/mock.log

# Example log entry
2024-01-01 12:00:00 - mock_hardware - INFO - Mock SDR initialized
2024-01-01 12:00:01 - mock_generator - DEBUG - Generating IQ data
2024-01-01 12:00:02 - mock_hardware - INFO - Injected drone: DJI Mavic 3
2024-01-01 12:00:03 - mock_hardware - DEBUG - Detection event triggered
Performance Considerations
Resource Usage
yaml
# Resource consumption in mock mode
mock_resources:
  cpu:
    synthetic_generation: 5-15%
    replay_mode: 2-5%
    idle: <1%
    
  memory:
    synthetic_generation: 100-500MB
    replay_mode: 50-200MB
    idle: 50MB
    
  disk:
    replay_files: ~1GB per hour (compressed)
    logs: ~10MB per hour
Optimization Tips
python
# Optimize mock generation for high throughput

# Use numpy vectorization
def generate_fast(samples, snr):
    # Vectorized operations are much faster
    noise = np.random.normal(0, 1, samples) + 1j * np.random.normal(0, 1, samples)
    signal = generate_signal_vectorized(samples)
    return signal + noise * (10 ** (-snr/20))

# Reduce sample rate when not needed
config = {
    'sample_rate': 1e6,  # Lower than real-time
    'simulate_only_at_detection_rate': True
}

# Use pre-generated data when possible
mock_sdr = MockSDR()
mock_sdr.set_generation_mode("replay")  # Faster than synthetic
CI/CD Integration
GitHub Actions Example
yaml
# .github/workflows/test.yml
name: Tests with Mock Mode

on: [push, pull_request]

jobs:
  test:
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
          
      - name: Run unit tests (mock mode)
        run: |
          export USE_MOCK_HARDWARE=true
          pytest tests/unit/ -v --cov=app
          
      - name: Run integration tests (mock mode)
        run: |
          export USE_MOCK_HARDWARE=true
          pytest tests/integration/ -v
          
      - name: Run performance tests (mock mode)
        run: |
          export USE_MOCK_HARDWARE=true
          pytest tests/performance/ -v --benchmark-only
Docker Compose for CI
yaml
# docker-compose.ci.yml
version: '3.8'
services:
  api:
    build: .
    environment:
      USE_MOCK_HARDWARE: "true"
      MOCK_SCENARIO: "test_suite"
    ports:
      - "8888:8888"
    command: >
      sh -c "pytest tests/ -v --cov=app --cov-report=xml"
Troubleshooting Mock Mode
Common Issues
bash
# Issue: Mock mode not activating
# Check configuration precedence:
echo $USE_MOCK_HARDWARE  # Should be 'true'
grep mock_mode config/system.yaml  # Should be 'true'

# Issue: No detections in mock mode
# Verify mock generator is producing signals
curl http://localhost:8888/api/v1/mock/debug/spectrum | jq '.signal_present'

# Issue: Performance issues in mock mode
# Check for resource limits
docker stats
# Reduce drone count or sample rate
export MOCK_MAX_DRONES=5
export MOCK_SAMPLE_RATE=1000000

# Issue: Replay files not found
ls -la /app/data/iq/mock/
# Check path in config
grep source_dir config/mock_config.yaml
Validation Tests
python
# scripts/validate_mock.py
def validate_mock_setup():
    """Validate mock mode configuration"""
    
    checks = [
        ("Environment variable", os.getenv("USE_MOCK_HARDWARE") == "true"),
        ("Config file", check_config_has_mock_mode()),
        ("Mock SDR import", import_mock_sdr_success()),
        ("Signal generation", test_signal_generation()),
        ("Detection pipeline", test_detection_with_mock())
    ]
    
    for check_name, passed in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {check_name}")
    
    return all(passed for _, passed in checks)
Best Practices
Development Workflow
Start Development in Mock Mode

bash
export USE_MOCK_HARDWARE=true
python run.py --mock
Test Changes Locally

bash
pytest tests/ --mock
Validate with Recorded Data

bash
python scripts/record_live_for_mock.py
python scripts/validate_mock_vs_live.py
Gradually Add Hardware

bash
# Start with mock, transition to real hardware
export USE_MOCK_HARDWARE=true
export HARDWARE_TYPE=auto  # Will auto-detect if available
Mock vs Real Hardware
Aspect	Mock Mode	Real Hardware
Development	Fast iteration	Hardware required
Testing	Deterministic	Variable conditions
CI/CD	Easy to automate	Difficult
Performance	Predictable	Hardware-dependent
Realism	Simulated	Actual RF environment
Cost	Free	Hardware cost
Debugging	Good visibility	Limited visibility
Production Considerations
yaml
# Don't use mock mode in production unless:
production_mock_use_cases:
  - "Fallback when hardware fails"
  - "Demo/display mode"
  - "Load testing without RF"
  - "Training environments"
  
  # Don't use for:
  - "Actual drone detection"
  - "Security-critical monitoring"
  - "Legal/compliance recording"
Example Scenarios
Complete Mock Setup Example
python
# examples/mock_demo.py
"""Complete mock mode demonstration"""

import asyncio
from drone_detector import DroneDetectorClient
from infrastructure.hardware.mock_hardware import MockSDR

async def mock_demo():
    # Initialize mock hardware
    mock_sdr = MockSDR()
    mock_sdr.initialize({
        'scenario': 'urban_high_density',
        'drone_count': 5,
        'duration': 60
    })
    
    # Configure client
    client = DroneDetectorClient(
        base_url="http://localhost:8888",
        mock_mode=True
    )
    
    # Start detection
    async for detection in client.stream_detections():
        print(f"Detection: {detection.drone_type} at {detection.frequency}")
        
        # Inject new drone periodically
        if detection.confidence > 0.9:
            mock_sdr.inject_drone(
                drone_type="High Confidence Drone",
                duration=10
            )
        
    # Get statistics
    stats = await client.get_mock_stats()
    print(f"Total detections: {stats['total_detections']}")
    print(f"Detection rate: {stats['detections_per_second']}/sec")

if __name__ == "__main__":
    asyncio.run(mock_demo())
This mock mode guide provides comprehensive documentation for using simulated hardware in the Drone Detector system, enabling development, testing, and validation without physical SDR equipment.
