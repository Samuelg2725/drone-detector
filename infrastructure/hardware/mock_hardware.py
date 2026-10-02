# infrastructure/hardware/mock_hardware.py
"""Mock SDR hardware for testing and development without physical devices"""

import numpy as np
import random
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from .sdr_base import SDRBase

@dataclass
class MockScenario:
    """Defines a simulation scenario"""
    name: str
    drone_type: str
    center_freq: float
    bandwidth: float
    snr_db: float
    duration: float  # seconds
    file_path: Optional[str] = None

class MockSDR(SDRBase):
    """
    Mock implementation of SDR hardware for development.
    Simulates real IQ data using pre-recorded files or synthetic generation.
    """
    
    def __init__(self):
        self.sdr = None
        self.is_streaming = False
        self.sample_rate = 10e6
        self.center_freq = 2.4e9
        self.lna_gain = 16
        self.vga_gain = 20
        self.amp_enable = False
        
        # Mock-specific attributes
        self.current_scenario: Optional[MockScenario] = None
        self.scenarios: List[MockScenario] = []
        self.scenario_index = 0
        self.playback_offset = 0
        self.synthetic_mode = True
        self.loaded_samples = None
        self.mock_data_path = Path("data/iq/mock/")
        
        # Simulation parameters
        self.noise_floor_db = -100
        self.simulate_latency_ms = 5
        self.simulate_errors = False
        self.error_rate = 0.01  # 1% error rate when enabled
        
        # Current frequency band info
        self.band_info = {
            "2.4g": {"freq": 2.4e9, "width": 80e6, "drones": ["DJI Mavic", "DJI Mini", "Custom"]},
            "5.2g": {"freq": 5.2e9, "width": 200e6, "drones": ["DJI Mavic"]},
            "5.8g": {"freq": 5.8e9, "width": 200e6, "drones": ["FPV", "DJI Avata", "Autel"]},
        }
        
        # Load predefined scenarios
        self._load_scenarios()
    
    def _load_scenarios(self):
        """Load predefined mock scenarios"""
        self.scenarios = [
            MockScenario(
                name="dji_mavic_2.4g_active",
                drone_type="DJI Mavic 3",
                center_freq=2.412e9,
                bandwidth=20e6,
                snr_db=15,
                duration=30.0,
                file_path=self.mock_data_path / "dji_mavic_2.4g.iq" if (self.mock_data_path / "dji_mavic_2.4g.iq").exists() else None
            ),
            MockScenario(
                name="dji_mavic_5.8g_active",
                drone_type="DJI Mavic 3",
                center_freq=5.825e9,
                bandwidth=20e6,
                snr_db=18,
                duration=30.0
            ),
            MockScenario(
                name="fpv_analog_5.8g",
                drone_type="FPV Analog",
                center_freq=5.800e9,
                bandwidth=10e6,
                snr_db=12,
                duration=30.0
            ),
            MockScenario(
                name="noise_only",
                drone_type=None,
                center_freq=2.4e9,
                bandwidth=20e6,
                snr_db=-20,
                duration=float('inf')
            ),
            MockScenario(
                name="interference_wifi",
                drone_type="Interference",
                center_freq=2.45e9,
                bandwidth=40e6,
                snr_db=5,
                duration=float('inf')
            )
        ]
        self.current_scenario = self.scenarios[3]  # Start with noise only
    
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize mock hardware"""
        print(f"[MOCK] Initializing mock SDR with config: {config}")
        
        # Apply config
        if config:
            self.sample_rate = config.get('sample_rate', 10e6)
            self.center_freq = config.get('center_freq', 2.4e9)
            self.lna_gain = config.get('gains', {}).get('lna_gain', 16)
            self.vga_gain = config.get('gains', {}).get('vga_gain', 20)
            self.amp_enable = config.get('gains', {}).get('amp_enable', False)
            self.synthetic_mode = config.get('mock', {}).get('synthetic_mode', True)
            self.simulate_latency_ms = config.get('mock', {}).get('simulate_latency_ms', 5)
            self.simulate_errors = config.get('mock', {}).get('simulate_errors', False)
        
        print(f"[MOCK] Mock SDR ready - Mode: {'Synthetic' if self.synthetic_mode else 'Playback'}")
        return True
    
    def tune(self, frequency: float):
        """Tune to specified frequency"""
        self.center_freq = frequency
        # Auto-select scenario based on frequency
        self._auto_select_scenario(frequency)
        print(f"[MOCK] Tuned to {frequency/1e9:.3f} GHz - Scenario: {self.current_scenario.name}")
    
    def _auto_select_scenario(self, frequency: float):
        """Automatically select appropriate scenario based on frequency"""
        if 2.4e9 <= frequency <= 2.5e9:
            # 2.4 GHz band - check if we should simulate drone
            if random.random() < 0.3:  # 30% chance of drone in band
                self.current_scenario = self.scenarios[0]  # DJI Mavic 2.4G
            else:
                self.current_scenario = self.scenarios[3]  # Noise only
        elif 5.7e9 <= frequency <= 5.9e9:
            # 5.8 GHz band
            if random.random() < 0.4:  # 40% chance of drone
                self.current_scenario = random.choice([self.scenarios[1], self.scenarios[2]])
            else:
                self.current_scenario = self.scenarios[3]
        else:
            self.current_scenario = self.scenarios[3]
    
    def set_gain(self, gain_type: str, value: float):
        """Set gain values (mock does nothing but logs)"""
        if gain_type == 'lna':
            self.lna_gain = value
        elif gain_type == 'vga':
            self.vga_gain = value
        elif gain_type == 'amp':
            self.amp_enable = bool(value)
        print(f"[MOCK] Set {gain_type} gain to {value}")
    
    def read_samples(self, num_samples: int) -> np.ndarray:
        """Read IQ samples - mock implementation"""
        # Simulate hardware latency
        if self.simulate_latency_ms > 0:
            time.sleep(self.simulate_latency_ms / 1000.0)
        
        # Simulate occasional errors
        if self.simulate_errors and random.random() < self.error_rate:
            raise RuntimeError("[MOCK] Simulated hardware error")
        
        # Generate or load samples
        if self.synthetic_mode or not self.current_scenario.file_path:
            samples = self._generate_synthetic_samples(num_samples)
        else:
            samples = self._playback_samples(num_samples)
        
        return samples
    
    def _generate_synthetic_samples(self, num_samples: int) -> np.ndarray:
        """Generate synthetic IQ samples based on current scenario"""
        
        if self.current_scenario.name == "noise_only":
            # Pure Gaussian noise
            noise_power = 10 ** ((self.noise_floor_db - 30) / 10)  # Convert dB to linear
            samples = np.sqrt(noise_power/2) * (np.random.randn(num_samples) + 1j * np.random.randn(num_samples))
            
        elif self.current_scenario.name == "interference_wifi":
            # OFDM-like interference + noise
            signal_power = 0.1
            noise_power = 0.01
            samples = np.zeros(num_samples, dtype=np.complex128)
            
            # Add OFDM-like bursts
            burst_duration = 2048
            for start in range(0, num_samples, burst_duration * 3):
                end = min(start + burst_duration, num_samples)
                # OFDM symbol simulation
                subcarriers = np.random.randn(burst_duration) + 1j * np.random.randn(burst_duration)
                ofdm_signal = np.fft.ifft(subcarriers) * np.sqrt(signal_power)
                samples[start:end] += ofdm_signal[:end-start]
            
            # Add noise
            samples += np.sqrt(noise_power/2) * (np.random.randn(num_samples) + 1j * np.random.randn(num_samples))
            
        else:
            # Simulate drone signal (OFDM/FM + doppler shift)
            samples = self._simulate_drone_signal(num_samples)
        
        # Scale to match real SDR output (-1 to 1 range)
        max_val = np.max(np.abs(samples))
        if max_val > 0:
            samples = samples / max_val
        
        return samples.astype(np.complex64)
    
    def _simulate_drone_signal(self, num_samples: int) -> np.ndarray:
        """Simulate a specific drone signal"""
        
        # Time vector
        t = np.arange(num_samples) / self.sample_rate
        
        # Add doppler shift (simulates moving drone)
        doppler_rate = 100 * np.sin(2 * np.pi * 0.5 * t)  # 100 Hz peak variation
        doppler_phase = 2 * np.pi * np.cumsum(doppler_rate) / self.sample_rate
        
        if "DJI" in self.current_scenario.drone_type:
            # DJI uses OFDM-like modulation
            symbol_rate = 10000
            symbols = np.random.choice([-1-1j, -1+1j, 1-1j, 1+1j], int(num_samples / self.sample_rate * symbol_rate))
            upsampled = np.zeros(num_samples, dtype=np.complex128)
            upsampled[::int(self.sample_rate/symbol_rate)] = symbols
            # Pulse shaping
            pulse = np.hanning(16)[:, None]
            signal = np.convolve(upsampled, pulse.flatten(), mode='same')
            
        elif "FPV" in self.current_scenario.drone_type:
            # Analog FM signal for FPV goggles
            message = np.sin(2 * np.pi * 100 * t) * 0.5
            freq_deviation = 5000
            phase = 2 * np.pi * freq_deviation * np.cumsum(message) / self.sample_rate
            signal = np.exp(1j * phase)
            
        else:
            # Default: simple frequency modulated carrier
            signal = np.exp(1j * 2 * np.pi * 1000 * t)
        
        # Calculate signal power based on SNR
        snr_linear = 10 ** (self.current_scenario.snr_db / 10)
        signal_power = np.mean(np.abs(signal)**2)
        noise_power = signal_power / snr_linear
        noise = np.sqrt(noise_power/2) * (np.random.randn(num_samples) + 1j * np.random.randn(num_samples))
        
        # Apply doppler shift
        samples = signal * np.exp(1j * doppler_phase) + noise
        
        return samples
    
    def _playback_samples(self, num_samples: int) -> np.ndarray:
        """Playback pre-recorded IQ samples"""
        
        if self.loaded_samples is None:
            # Load IQ file
            try:
                self.loaded_samples = np.fromfile(self.current_scenario.file_path, dtype=np.complex64)
                print(f"[MOCK] Loaded {len(self.loaded_samples)} samples from {self.current_scenario.file_path}")
            except Exception as e:
                print(f"[MOCK] Failed to load file: {e}, falling back to synthetic")
                return self._generate_synthetic_samples(num_samples)
        
        # Playback with wrap-around
        samples = self.loaded_samples[self.playback_offset:self.playback_offset + num_samples]
        self.playback_offset = (self.playback_offset + num_samples) % len(self.loaded_samples)
        
        # Add some noise for realism
        noise_power = 0.01
        noise = np.sqrt(noise_power/2) * (np.random.randn(len(samples)) + 1j * np.random.randn(len(samples)))
        samples = samples + noise
        
        return samples.astype(np.complex64)
    
    def start_streaming(self):
        """Start continuous streaming mode"""
        self.is_streaming = True
        print("[MOCK] Started streaming mode")
    
    def stop_streaming(self):
        """Stop continuous streaming"""
        self.is_streaming = False
        print("[MOCK] Stopped streaming mode")
    
    def get_stream_samples(self, num_samples: int = None) -> np.ndarray:
        """Get samples from streaming buffer"""
        if not self.is_streaming:
            return np.array([], dtype=np.complex64)
        
        # Simulate streaming by generating on-the-fly
        if num_samples is None:
            num_samples = int(self.sample_rate)  # 1 second by default
        
        return self.read_samples(num_samples)
    
    def set_scenario(self, scenario_name: str):
        """Manually set active scenario for testing"""
        for scenario in self.scenarios:
            if scenario.name == scenario_name:
                self.current_scenario = scenario
                print(f"[MOCK] Scenario set to: {scenario_name}")
                return True
        print(f"[MOCK] Scenario not found: {scenario_name}")
        return False
    
    def list_scenarios(self) -> List[str]:
        """List all available scenarios"""
        return [s.name for s in self.scenarios]
    
    def inject_drone(self, drone_type: str, frequency: float):
        """Inject a drone signal at specified frequency"""
        self.set_scenario(f"{drone_type.lower().replace(' ', '_')}_{frequency//1e9:.1f}g_active")
        self.center_freq = frequency
        print(f"[MOCK] Injected {drone_type} drone at {frequency/1e9:.3f} GHz")
    
    def close(self):
        """Close mock device"""
        self.is_streaming = False
        self.loaded_samples = None
        print("[MOCK] Mock SDR closed")