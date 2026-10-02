#!/usr/bin/env python3
# scripts/test_hardware.py

import sys
import time
import numpy as np
sys.path.append('.')

from infrastructure.hardware import HackRFDevice

def test_hackrf_basic():
    """Basic HackRF functionality test"""
    print("Testing HackRF One...")
    
    # Initialize
    config = {
        'sample_rate': 10e6,
        'center_freq': 100e6,  # FM broadcast band
        'gains': {'lna_gain': 16, 'vga_gain': 20, 'amp_enable': False}
    }
    
    hackrf = HackRFDevice()
    
    try:
        # Initialize
        success = hackrf.initialize(config)
        if not success:
            print("Failed to initialize HackRF")
            return False
        
        print("HackRF initialized successfully")
        
        # Test sample reading
        print("Reading 1 million samples...")
        samples = hackrf.read_samples(1000000)
        
        print(f"Read {len(samples)} samples")
        print(f"Sample type: {samples.dtype}")
        print(f"Mean magnitude: {np.mean(np.abs(samples)):.4f}")
        print(f"Max magnitude: {np.max(np.abs(samples)):.4f}")
        
        # Quick FFT test
        fft_result = np.fft.fftshift(np.fft.fft(samples))
        psd = 10 * np.log10(np.abs(fft_result)**2 + 1e-10)
        
        print(f"FFT size: {len(fft_result)}")
        print(f"PSD range: {np.min(psd):.1f} to {np.max(psd):.1f} dB")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        hackrf.close()

if __name__ == "__main__":
    success = test_hackrf_basic()
    sys.exit(0 if success else 1)