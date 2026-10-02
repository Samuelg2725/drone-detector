#!/usr/bin/env python3
# scripts/generate_mock_data.py
"""Generate synthetic IQ data files for mock playback mode"""

import numpy as np
import sys
from pathlib import Path
sys.path.append('.')

from infrastructure.hardware.mock_hardware import MockSDR

def generate_iq_file(duration_seconds: int = 10, sample_rate: int = 10_000_000):
    """Generate IQ data file for each scenario"""
    
    mock = MockSDR()
    mock.initialize({'sample_rate': sample_rate})
    
    data_dir = Path("data/iq/mock")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    scenarios = [
        ("dji_mavic_2.4g", 2.412e9, "DJI Mavic 3"),
        ("dji_mavic_5.8g", 5.825e9, "DJI Mavic 3"),
        ("fpv_analog_5.8g", 5.800e9, "FPV Analog"),
        ("noise_floor", 2.4e9, None),
        ("interference_wifi", 2.45e9, "Interference"),
    ]
    
    for name, freq, drone_type in scenarios:
        print(f"Generating {name}...")
        
        # Set scenario
        if drone_type:
            scenario_name = f"{name}_active"
        else:
            scenario_name = name
        
        # Generate samples
        num_samples = duration_seconds * sample_rate
        mock.center_freq = freq
        
        # Override scenario temporarily
        if drone_type:
            from infrastructure.hardware.mock_hardware import MockScenario
            mock.current_scenario = MockScenario(
                name=scenario_name,
                drone_type=drone_type or "None",
                center_freq=freq,
                bandwidth=20e6,
                snr_db=15 if drone_type else -20,
                duration=duration_seconds
            )
        else:
            mock.current_scenario.name = scenario_name
        
        # Generate samples
        samples = mock._generate_synthetic_samples(num_samples)
        
        # Save to file
        output_file = data_dir / f"{name}.iq"
        samples.astype(np.complex64).tofile(output_file)
        print(f"  Saved {len(samples)} samples to {output_file}")
    
    print("\nMock data generation complete!")

if __name__ == "__main__":
    generate_iq_file(duration_seconds=30)