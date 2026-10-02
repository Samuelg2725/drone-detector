# infrastructure/hardware/hackrf.py
import numpy as np
import time
from typing import Optional
from python_hackrf import pyhackrf
from .sdr_base import SDRBase

class HackRFDevice(SDRBase):
    """HackRF One hardware implementation"""
    
    def __init__(self):
        self.sdr = None
        self.is_streaming = False
        self.sample_rate = 10e6
        self.center_freq = 2.4e9
        self.lna_gain = 16
        self.vga_gain = 20
        self.amp_enable = False
        self.rx_callback = None
        self.samples_buffer = []
        
    def initialize(self, config: dict):
        """Initialize HackRF device"""
        # Initialize HackRF library
        pyhackrf.pyhackrf_init()
        
        # Open device
        self.sdr = pyhackrf.pyhackrf_open()
        
        # Configure from config
        if config:
            self.sample_rate = config.get('sample_rate', 10e6)
            self.center_freq = config.get('center_freq', 2.4e9)
            self.lna_gain = config.get('gains', {}).get('lna_gain', 16)
            self.vga_gain = config.get('gains', {}).get('vga_gain', 20)
            self.amp_enable = config.get('gains', {}).get('amp_enable', False)
        
        # Apply settings
        self.sdr.pyhackrf_set_sample_rate(self.sample_rate)
        self.sdr.pyhackrf_set_freq(self.center_freq)
        self.sdr.pyhackrf_set_lna_gain(self.lna_gain)
        self.sdr.pyhackrf_set_vga_gain(self.vga_gain)
        self.sdr.pyhackrf_set_amp_enable(self.amp_enable)
        self.sdr.pyhackrf_set_antenna_enable(False)
        
        # Compute baseband filter bandwidth
        baseband_filter = min(self.sample_rate * 0.8, 10e6)
        allowed_filter = pyhackrf.pyhackrf_compute_baseband_filter_bw_round_down_lt(baseband_filter)
        self.sdr.pyhackrf_set_baseband_filter_bandwidth(allowed_filter)
        
        return True
    
    def tune(self, frequency: float):
        """Tune to frequency"""
        self.center_freq = frequency
        if self.sdr:
            self.sdr.pyhackrf_set_freq(frequency)
    
    def set_gain(self, gain_type: str, value: float):
        """Set gain value"""
        if gain_type == 'lna':
            self.lna_gain = value
            if self.sdr:
                self.sdr.pyhackrf_set_lna_gain(value)
        elif gain_type == 'vga':
            self.vga_gain = value
            if self.sdr:
                self.sdr.pyhackrf_set_vga_gain(value)
        elif gain_type == 'amp':
            self.amp_enable = bool(value)
            if self.sdr:
                self.sdr.pyhackrf_set_amp_enable(self.amp_enable)
    
    def read_samples(self, num_samples: int) -> np.ndarray:
        """Read IQ samples synchronously"""
        samples = np.zeros(num_samples, dtype=np.complex64)
        
        def callback(device, buffer, buffer_length, valid_length):
            nonlocal samples, sample_idx
            accepted = valid_length // 2
            accepted_samples = buffer[:valid_length].astype(np.int8)
            iq_samples = accepted_samples[0::2] + 1j * accepted_samples[1::2]
            iq_samples = iq_samples / 128.0  # Scale to -1 to 1
            
            remaining = num_samples - sample_idx
            to_copy = min(accepted, remaining)
            samples[sample_idx:sample_idx + to_copy] = iq_samples[:to_copy]
            sample_idx += to_copy
            return 0
        
        sample_idx = 0
        self.sdr.set_rx_callback(callback)
        self.sdr.pyhackrf_start_rx()
        
        # Wait for samples
        timeout = num_samples / self.sample_rate + 0.5
        start = time.time()
        while sample_idx < num_samples and (time.time() - start) < timeout:
            time.sleep(0.01)
        
        self.sdr.pyhackrf_stop_rx()
        
        return samples
    
    def start_streaming(self):
        """Start asynchronous streaming with callback"""
        if self.is_streaming:
            return
        
        self.samples_buffer = []
        
        def stream_callback(device, buffer, buffer_length, valid_length):
            accepted = valid_length // 2
            accepted_samples = buffer[:valid_length].astype(np.int8)
            iq_samples = accepted_samples[0::2] + 1j * accepted_samples[1::2]
            iq_samples = iq_samples / 128.0
            
            # Add to buffer
            self.samples_buffer.extend(iq_samples)
            
            # Trim buffer if too large
            max_buffer = int(self.sample_rate * 10)  # 10 seconds max
            if len(self.samples_buffer) > max_buffer:
                self.samples_buffer = self.samples_buffer[-max_buffer:]
            
            return 0
        
        self.sdr.set_rx_callback(stream_callback)
        self.sdr.pyhackrf_start_rx()
        self.is_streaming = True
    
    def stop_streaming(self):
        """Stop streaming"""
        if self.is_streaming:
            self.sdr.pyhackrf_stop_rx()
            self.is_streaming = False
    
    def get_stream_samples(self, num_samples: int = None) -> np.ndarray:
        """Get accumulated samples from streaming buffer"""
        if not self.samples_buffer:
            return np.array([], dtype=np.complex64)
        
        if num_samples:
            samples = np.array(self.samples_buffer[:num_samples])
            self.samples_buffer = self.samples_buffer[num_samples:]
        else:
            samples = np.array(self.samples_buffer)
            self.samples_buffer = []
        
        return samples
    
    def close(self):
        """Close device"""
        if self.is_streaming:
            self.stop_streaming()
        
        if self.sdr:
            self.sdr.pyhackrf_close()
        
        pyhackrf.pyhackrf_exit()