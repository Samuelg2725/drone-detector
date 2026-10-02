# app/services.py
import asyncio
import numpy as np
from typing import Optional, Dict, Any
from infrastructure.hardware import HardwareFactory
from domain.algorithms.fft import compute_fft
from domain.algorithms.psd import compute_psd
from domain.algorithms.peak_detection import detect_peaks

class HardwareService:
    """Orchestrates hardware operations"""
    
    def __init__(self, config: dict):
        self.config = config
        self.hardware = None
        self.is_running = False
        self.current_freq = None
        self.scan_index = 0
        
    async def initialize(self):
        """Initialize hardware"""
        hw_config = self.config.get('hardware', {})
        hw_type = hw_config.get('type', 'hackrf')
        
        self.hardware = HardwareFactory.create_hardware(hw_type, self.config.get('rf_settings', {}))
        print(f"Initialized {hw_type} hardware")
        
    async def start_scanning(self):
        """Start frequency scanning"""
        self.is_running = True
        frequencies = self.config.get('rf_settings', {}).get('frequencies', [2.4e9, 5.2e9, 5.8e9])
        scan_interval = self.config.get('rf_settings', {}).get('scan_interval', 0.5)
        
        while self.is_running:
            freq = frequencies[self.scan_index % len(frequencies)]
            await self.scan_frequency(freq)
            self.scan_index += 1
            await asyncio.sleep(scan_interval)
    
    async def scan_frequency(self, frequency: float):
        """Scan a specific frequency"""
        try:
            # Tune to frequency
            self.hardware.tune(frequency)
            self.current_freq = frequency
            
            # Read samples
            num_samples = int(self.config.get('rf_settings', {}).get('sample_rate', 10e6))
            samples = self.hardware.read_samples(num_samples)
            
            # Process samples
            fft_result = compute_fft(samples, fft_size=2048)
            psd = compute_psd(fft_result)
            peaks = detect_peaks(psd, threshold_factor=3.0)
            
            # Return processed data
            return {
                'frequency': frequency,
                'psd': psd,
                'peaks': peaks,
                'timestamp': time.time()
            }
            
        except Exception as e:
            print(f"Error scanning {frequency}: {e}")
            return None
    
    async def stop(self):
        """Stop scanning"""
        self.is_running = False
        if self.hardware:
            self.hardware.close()