# app/startup.py (updated with mock support)

import yaml
from infrastructure.hardware.hardware_factory import HardwareFactory, HardwareType
from infrastructure.hardware.mock_hardware import MockSDR

async def startup_app():
    """Initialize application with mock support"""
    
    # Load config
    with open('config/system.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Determine hardware mode
    mock_enabled = config.get('hardware', {}).get('mock', {}).get('enabled', False)
    hardware_type = config.get('hardware', {}).get('type', 'auto')
    
    if mock_enabled:
        print("=" * 50)
        print("⚠️  MOCK HARDWARE MODE ACTIVE ⚠️")
        print("Running with simulated SDR - No physical hardware needed")
        print("Use 'mock_config.yaml' to adjust simulation parameters")
        print("=" * 50)
    
    # Create hardware
    hardware = HardwareFactory.create_hardware(
        hardware_type=hardware_type,
        config=config,
        force_mock=mock_enabled
    )
    
    # If using mock, set up auto-injection
    if isinstance(hardware, MockSDR):
        auto_inject = config.get('hardware', {}).get('mock', {}).get('auto_inject', {})
        if auto_inject.get('enabled', False):
            asyncio.create_task(auto_inject_drones(hardware, auto_inject))
    
    return hardware

async def auto_inject_drones(mock_hw: MockSDR, config: dict):
    """Periodically inject drone signals into mock hardware"""
    probability = config.get('inject_probability', 0.3)
    duration_min = config.get('duration_min', 5)
    duration_max = config.get('duration_max', 30)
    
    while True:
        await asyncio.sleep(5)  # Check every 5 seconds
        
        if random.random() < probability:
            # Inject drone for random duration
            duration = random.uniform(duration_min, duration_max)
            drone_type = random.choice(["DJI Mavic", "FPV", "DJI Mini"])
            freq = random.choice([2.4e9, 5.8e9])
            
            print(f"[MOCK] Auto-injecting {drone_type} drone at {freq/1e9:.1f}GHz for {duration:.1f}s")
            
            # This would need to set scenario and timer
            # Implementation depends on your event system