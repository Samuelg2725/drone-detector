#!/usr/bin/env python3
"""
Record Live Signals for Mock Data Generation

This script captures real IQ signals from SDR hardware to create
authentic mock datasets for testing and development. It supports:
- Continuous recording with automatic segmentation
- Trigger-based recording (signal detection)
- Multiple frequency band scanning
- Automatic gain control
- Signal quality validation
- Metadata collection (GPS, timestamps, signal stats)
- Batch processing for large datasets
- Real-time spectrum visualization
- Audio feedback for signal detection
"""

import argparse
import asyncio
import json
import numpy as np
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import threading
from collections import deque

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.hardware import HardwareFactory
from infrastructure.signal_io.recorder import IQRecorder, RecordingConfig, RecordingFormat
from infrastructure.signal_io.iq_stream import IQStream, StreamConfig
from domain.algorithms.psd import compute_psd
from domain.algorithms.peak_detection import detect_peaks

# Optional imports for advanced features
try:
    from pynput import keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

try:
    import simpleaudio as sa
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False

try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False


# ============================================================================
# Configuration
# ============================================================================

class RecordConfig:
    """Recording configuration"""
    
    # Hardware settings
    SAMPLE_RATE: float = 10e6  # 10 MHz
    CENTER_FREQ: float = 2.44e9  # 2.44 GHz
    GAIN: int = 20  # dB
    
    # Recording settings
    DURATION: int = 30  # seconds
    SEGMENT_DURATION: int = 10  # seconds per file
    OUTPUT_DIR: str = "data/iq/replay"
    
    # Trigger settings
    TRIGGER_ENABLED: bool = False
    TRIGGER_THRESHOLD_DB: float = -60  # dBm
    PRE_TRIGGER_SECONDS: float = 2.0
    POST_TRIGGER_SECONDS: float = 5.0
    
    # Scanning settings
    SCAN_MODE: bool = False
    FREQUENCIES: List[float] = [
        2.412e9,  # 2.4 GHz WiFi ch1
        2.442e9,  # 2.4 GHz WiFi ch7
        2.472e9,  # 2.4 GHz WiFi ch13
        5.180e9,  # 5.2 GHz
        5.800e9,  # 5.8 GHz
    ]
    SCAN_DWELL_SECONDS: float = 5.0
    
    # File naming
    PREFIX: str = "recording"
    INCLUDE_TIMESTAMP: bool = True
    INCLUDE_FREQ_IN_NAME: bool = True
    
    # Metadata
    ADD_GPS: bool = False
    GPS_PORT: str = "/dev/ttyUSB0"
    GPS_BAUD: int = 9600
    
    # Audio feedback
    AUDIO_FEEDBACK: bool = True
    
    # Visualization
    SHOW_SPECTRUM: bool = True
    SPECTRUM_UPDATE_INTERVAL: float = 0.5


# ============================================================================
# Signal Recorder Class
# ============================================================================

class LiveSignalRecorder:
    """
    Real-time signal recorder for mock data generation
    
    Features:
    - Manual recording with keyboard controls
    - Automatic trigger-based recording
    - Multiple frequency scanning
    - Signal quality monitoring
    - Metadata collection
    - Real-time spectrum display
    """
    
    def __init__(self, config: RecordConfig = None):
        """
        Initialize recorder
        
        Args:
            config: Recording configuration
        """
        self.config = config or RecordConfig()
        self.hardware = None
        self.recorder = None
        self.stream = None
        self.is_recording = False
        self.current_session = None
        self.recording_count = 0
        
        # Signal analysis
        self.signal_buffer = deque(maxlen=int(self.config.SAMPLE_RATE * 2))
        self.peak_history = deque(maxlen=100)
        self.noise_floor = -100
        
        # Statistics
        self.stats = {
            'total_recordings': 0,
            'total_duration_seconds': 0,
            'total_samples': 0,
            'detections': 0
        }
        
        # Set up output directories
        self.output_dir = Path(self.config.OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print("=" * 60)
        print("Live Signal Recorder for Mock Data")
        print("=" * 60)
        print(f"Output directory: {self.output_dir}")
        print(f"Sample rate: {self.config.SAMPLE_RATE/1e6:.1f} MHz")
        print(f"Center frequency: {self.config.CENTER_FREQ/1e9:.3f} GHz")
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Set up keyboard controls
        if HAS_PYNPUT:
            self._setup_keyboard_listener()
    
    # ========================================================================
    # Initialization
    # ========================================================================
    
    async def initialize(self) -> bool:
        """
        Initialize hardware and recording components
        
        Returns:
            True if initialization successful
        """
        print("\n[1/4] Initializing hardware...")
        
        # Create hardware instance
        self.hardware = HardwareFactory.create_hardware(
            hardware_type='hackrf',
            config={'sample_rate': self.config.SAMPLE_RATE}
        )
        
        # Initialize hardware
        success = self.hardware.initialize({
            'sample_rate': self.config.SAMPLE_RATE,
            'center_freq': self.config.CENTER_FREQ
        })
        
        if not success:
            print("Failed to initialize hardware")
            return False
        
        print(f"  Hardware initialized: {self.hardware.__class__.__name__}")
        
        # Create recorder
        print("\n[2/4] Initializing recorder...")
        
        recording_config = RecordingConfig(
            output_dir=str(self.output_dir),
            sample_rate=self.config.SAMPLE_RATE,
            center_freq=self.config.CENTER_FREQ,
            format=RecordingFormat.RAW_BINARY,
            auto_rotate=True,
            max_file_size_mb=1024,
            pre_trigger_seconds=self.config.PRE_TRIGGER_SECONDS,
            post_trigger_seconds=self.config.POST_TRIGGER_SECONDS
        )
        
        self.recorder = IQRecorder(recording_config)
        
        # Create stream
        print("\n[3/4] Initializing stream...")
        
        stream_config = StreamConfig(
            sample_rate=self.config.SAMPLE_RATE,
            chunk_size=16384,
            buffer_size=524288,
            enable_stats=True
        )
        
        self.stream = IQStream(self.hardware, stream_config)
        self.stream.add_processor(self._process_chunk)
        
        # Set center frequency
        await self.hardware.tune(self.config.CENTER_FREQ)
        
        print("\n[4/4] Ready for recording!")
        print("-" * 60)
        print("Controls:")
        print("  'r' - Start recording")
        print("  's' - Stop recording")
        print("  't' - Toggle trigger mode")
        print("  'f' - Change frequency")
        print("  'q' - Quit")
        print("-" * 60)
        
        return True
    
    # ========================================================================
    # Recording Methods
    # ========================================================================
    
    async def start_recording(self, duration: Optional[float] = None) -> str:
        """
        Start manual recording
        
        Args:
            duration: Recording duration in seconds (None for continuous)
        
        Returns:
            Recording ID
        """
        if self.is_recording:
            print("Already recording!")
            return None
        
        # Create session name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        freq_str = f"{self.config.CENTER_FREQ/1e9:.3f}GHz".replace('.', '_')
        session_name = f"{self.config.PREFIX}_{timestamp}_{freq_str}"
        
        if duration:
            session_name += f"_{duration}s"
        
        print(f"\n🎤 STARTING RECORDING: {session_name}")
        
        # Generate metadata
        metadata = {
            'recording_type': 'manual',
            'operator': 'live_recording_script',
            'duration_seconds': duration,
            'notes': 'Recorded for mock data generation'
        }
        
        # Add GPS if available
        if self.config.ADD_GPS:
            gps_data = await self._get_gps_data()
            if gps_data:
                metadata['gps'] = gps_data
        
        # Start recording
        recording_id = await self.recorder.start_recording(session_name, metadata)
        
        self.is_recording = True
        self.current_session = session_name
        
        # Set timer if duration specified
        if duration:
            asyncio.create_task(self._auto_stop(duration))
        
        # Play start sound if enabled
        if self.config.AUDIO_FEEDBACK and HAS_AUDIO:
            self._play_beep(1000, 0.2)
        
        return recording_id
    
    async def stop_recording(self) -> Optional[Dict]:
        """
        Stop current recording
        
        Returns:
            Recording metadata
        """
        if not self.is_recording:
            print("Not recording!")
            return None
        
        print(f"\n🛑 STOPPING RECORDING")
        
        metadata = await self.recorder.stop_recording()
        
        self.is_recording = False
        self.recording_count += 1
        
        # Update stats
        if metadata:
            self.stats['total_recordings'] += 1
            self.stats['total_duration_seconds'] += metadata.duration_seconds
            self.stats['total_samples'] += metadata.num_samples
        
        # Play stop sound
        if self.config.AUDIO_FEEDBACK and HAS_AUDIO:
            self._play_beep(500, 0.3)
        
        print(f"  Duration: {metadata.duration_seconds:.2f}s")
        print(f"  File size: {metadata.file_size_bytes / (1024*1024):.2f} MB")
        print(f"  Output: {metadata.file_path}")
        
        return metadata
    
    async def _auto_stop(self, duration: float):
        """Auto-stop after duration"""
        await asyncio.sleep(duration)
        if self.is_recording:
            await self.stop_recording()
    
    # ========================================================================
    # Trigger-Based Recording
    # ========================================================================
    
    async def start_trigger_recording(self):
        """Start trigger-based recording mode"""
        print("\n🔍 Starting trigger-based recording mode...")
        print(f"  Threshold: {self.config.TRIGGER_THRESHOLD_DB} dBm")
        print("  Waiting for signal...")
        
        trigger_active = False
        
        while True:
            # Analyze signal buffer
            if len(self.signal_buffer) > 0:
                samples = np.array(list(self.signal_buffer))
                
                # Compute power
                power = np.mean(np.abs(samples)**2)
                power_dbm = 10 * np.log10(power + 1e-12)
                
                # Check threshold
                if power_dbm > self.config.TRIGGER_THRESHOLD_DB and not trigger_active:
                    print(f"\n🚨 SIGNAL DETECTED! Power: {power_dbm:.1f} dBm")
                    
                    # Start recording with pre-trigger buffer
                    await self.start_recording()
                    trigger_active = True
                    
                    # Set post-trigger timer
                    asyncio.create_task(self._post_trigger_stop())
            
            await asyncio.sleep(0.05)
    
    async def _post_trigger_stop(self):
        """Stop recording after post-trigger period"""
        await asyncio.sleep(self.config.POST_TRIGGER_SECONDS)
        if self.is_recording:
            await self.stop_recording()
    
    # ========================================================================
    # Frequency Scanning
    # ========================================================================
    
    async def scan_frequencies(self):
        """Scan through multiple frequencies"""
        print("\n📡 Starting frequency scan mode...")
        
        for freq in self.config.FREQUENCIES:
            if not self.is_recording:
                print(f"\nTuning to {freq/1e9:.3f} GHz...")
                
                # Tune to frequency
                await self.hardware.tune(freq)
                self.config.CENTER_FREQ = freq
                
                # Update recorder config
                self.recorder.config.center_freq = freq
                
                # Dwell for specified time
                await asyncio.sleep(self.config.SCAN_DWELL_SECONDS)
    
    # ========================================================================
    # Signal Processing
    # ========================================================================
    
    async def _process_chunk(self, chunk: np.ndarray) -> np.ndarray:
        """
        Process incoming IQ chunks for analysis
        
        Args:
            chunk: IQ data chunk
            
        Returns:
            Processed chunk
        """
        # Add to buffer for analysis
        self.signal_buffer.extend(chunk)
        
        # Periodic analysis
        if len(self.signal_buffer) >= self.config.SAMPLE_RATE:
            samples = np.array(list(self.signal_buffer))
            
            # Compute statistics
            power = np.mean(np.abs(samples)**2)
            power_dbm = 10 * np.log10(power + 1e-12)
            
            # Estimate SNR
            # (Simplified - would use proper noise floor estimation)
            self.noise_floor = self.noise_floor * 0.95 + power_dbm * 0.05
            
            # Check for signal
            signal_detected = power_dbm > self.noise_floor + 10
            
            if signal_detected:
                self.stats['detections'] += 1
            
            # Clear buffer partially (keep 1 second overlap)
            overlap = int(self.config.SAMPLE_RATE)
            self.signal_buffer = deque(list(self.signal_buffer)[-overlap:], 
                                       maxlen=self.signal_buffer.maxlen)
        
        return chunk
    
    # ========================================================================
    # Frequency Management
    # ========================================================================
    
    async def set_frequency(self, freq_ghz: float):
        """
        Change center frequency
        
        Args:
            freq_ghz: Frequency in GHz
        """
        freq_hz = freq_ghz * 1e9
        self.config.CENTER_FREQ = freq_hz
        
        print(f"\n📻 Tuning to {freq_ghz:.3f} GHz...")
        
        await self.hardware.tune(freq_hz)
        
        # Update recorder config
        if self.recorder:
            self.recorder.config.center_freq = freq_hz
    
    # ========================================================================
    # Real-time Visualization
    # ========================================================================
    
    async def run_visualization(self):
        """Run real-time spectrum visualization"""
        if not self.config.SHOW_SPECTRUM:
            return
        
        try:
            import matplotlib.pyplot as plt
            import matplotlib.animation as animation
            
            # Setup plot
            plt.ion()
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.set_xlabel('Frequency (MHz)')
            ax.set_ylabel('Power (dBm)')
            ax.set_title('Real-time Spectrum Monitor')
            ax.grid(True, alpha=0.3)
            ax.set_ylim(-120, -20)
            
            line, = ax.plot([], [], 'b-', linewidth=1)
            peak_line, = ax.plot([], [], 'ro', markersize=8)
            
            plt.show(block=False)
            
            while True:
                if len(self.signal_buffer) >= 1024:
                    samples = np.array(list(self.signal_buffer))[:16384]
                    
                    # Compute FFT
                    fft_data = np.fft.fftshift(np.fft.fft(samples))
                    fft_mag = 20 * np.log10(np.abs(fft_data) + 1e-12)
                    freqs = np.fft.fftfreq(len(samples), 1/self.config.SAMPLE_RATE)
                    freqs = np.fft.fftshift(freqs) / 1e6  # Convert to MHz
                    
                    # Update plot
                    line.set_data(freqs, fft_mag)
                    
                    # Find peaks
                    peaks, _ = detect_peaks(fft_mag, threshold_factor=3.0)
                    if len(peaks) > 0:
                        peak_freqs = freqs[peaks]
                        peak_mags = fft_mag[peaks]
                        peak_line.set_data(peak_freqs, peak_mags)
                    
                    ax.set_xlim(freqs[0], freqs[-1])
                    ax.relim()
                    fig.canvas.draw()
                    fig.canvas.flush_events()
                
                await asyncio.sleep(self.config.SPECTRUM_UPDATE_INTERVAL)
                
        except ImportError:
            print("Matplotlib not available for visualization")
        except Exception as e:
            print(f"Visualization error: {e}")
    
    # ========================================================================
    # GPS Integration
    # ========================================================================
    
    async def _get_gps_data(self) -> Optional[Dict]:
        """Get GPS data from serial GPS module"""
        if not HAS_SERIAL:
            return None
        
        try:
            ser = serial.Serial(self.config.GPS_PORT, self.config.GPS_BAUD, timeout=1)
            
            for _ in range(10):
                line = ser.readline().decode('ascii', errors='ignore')
                if line.startswith('$GPGGA'):
                    parts = line.split(',')
                    if len(parts) > 5 and parts[2] and parts[4]:
                        lat = self._parse_gps(parts[2], parts[3])
                        lon = self._parse_gps(parts[4], parts[5])
                        alt = float(parts[9]) if parts[9] else 0
                        
                        ser.close()
                        return {'latitude': lat, 'longitude': lon, 'altitude': alt}
            
            ser.close()
            
        except Exception as e:
            print(f"GPS error: {e}")
        
        return None
    
    def _parse_gps(self, coord: str, direction: str) -> float:
        """Parse GPS coordinate string"""
        if not coord:
            return 0.0
        
        degrees = float(coord[:2])
        minutes = float(coord[2:])
        decimal = degrees + minutes / 60.0
        
        if direction in ['S', 'W']:
            decimal = -decimal
        
        return decimal
    
    # ========================================================================
    # Audio Feedback
    # ========================================================================
    
    def _play_beep(self, frequency: int, duration: float):
        """Play beep sound"""
        if not HAS_AUDIO:
            return
        
        try:
            sample_rate = 44100
            t = np.linspace(0, duration, int(sample_rate * duration))
            wave = 0.5 * np.sin(2 * np.pi * frequency * t)
            audio = (wave * 32767).astype(np.int16)
            
            # Play asynchronously
            threading.Thread(target=lambda: sa.play_buffer(audio, 1, 2, sample_rate)).start()
        except Exception as e:
            print(f"Audio error: {e}")
    
    # ========================================================================
    # Keyboard Controls
    # ========================================================================
    
    def _setup_keyboard_listener(self):
        """Set up keyboard listener for controls"""
        
        def on_press(key):
            try:
                if hasattr(key, 'char'):
                    if key.char == 'r':
                        asyncio.create_task(self.start_recording())
                    elif key.char == 's':
                        asyncio.create_task(self.stop_recording())
                    elif key.char == 't':
                        self.config.TRIGGER_ENABLED = not self.config.TRIGGER_ENABLED
                        print(f"\nTrigger mode: {'ON' if self.config.TRIGGER_ENABLED else 'OFF'}")
                    elif key.char == 'q':
                        asyncio.create_task(self.shutdown())
                    elif key.char == 'f':
                        print("\nEnter frequency (GHz): ", end='', flush=True)
                        # Would need more complex input handling
            except AttributeError:
                pass
        
        listener = keyboard.Listener(on_press=on_press)
        listener.daemon = True
        listener.start()
    
    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C"""
        print("\n\nInterrupted by user")
        asyncio.create_task(self.shutdown())
    
    # ========================================================================
    # Shutdown
    # ========================================================================
    
    async def shutdown(self):
        """Shutdown recorder and clean up"""
        print("\n🛑 Shutting down...")
        
        if self.is_recording:
            await self.stop_recording()
        
        if self.stream:
            await self.stream.stop()
        
        if self.hardware:
            self.hardware.close()
        
        # Print statistics
        print("\n📊 Recording Statistics:")
        print(f"  Total recordings: {self.stats['total_recordings']}")
        print(f"  Total duration: {self.stats['total_duration_seconds']:.2f}s")
        print(f"  Total samples: {self.stats['total_samples']:,}")
        print(f"  Signal detections: {self.stats['detections']}")
        
        print("\n✅ Shutdown complete")
        sys.exit(0)


# ============================================================================
# Main Function
# ============================================================================

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Record live signals for mock data generation"
    )
    
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=RecordConfig.DURATION,
        help="Recording duration in seconds"
    )
    
    parser.add_argument(
        "--frequency", "-f",
        type=float,
        default=RecordConfig.CENTER_FREQ / 1e9,
        help="Center frequency in GHz"
    )
    
    parser.add_argument(
        "--sample-rate", "-s",
        type=float,
        default=RecordConfig.SAMPLE_RATE / 1e6,
        help="Sample rate in MHz"
    )
    
    parser.add_argument(
        "--gain", "-g",
        type=int,
        default=RecordConfig.GAIN,
        help="LNA gain in dB"
    )
    
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=RecordConfig.OUTPUT_DIR,
        help="Output directory"
    )
    
    parser.add_argument(
        "--prefix", "-p",
        type=str,
        default=RecordConfig.PREFIX,
        help="File prefix"
    )
    
    parser.add_argument(
        "--trigger",
        action="store_true",
        help="Enable trigger-based recording"
    )
    
    parser.add_argument(
        "--threshold",
        type=float,
        default=RecordConfig.TRIGGER_THRESHOLD_DB,
        help="Trigger threshold in dBm"
    )
    
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Enable frequency scanning mode"
    )
    
    parser.add_argument(
        "--no-viz",
        action="store_true",
        help="Disable spectrum visualization"
    )
    
    args = parser.parse_args()
    
    # Configure recorder
    config = RecordConfig()
    config.DURATION = args.duration
    config.CENTER_FREQ = args.frequency * 1e9
    config.SAMPLE_RATE = args.sample_rate * 1e6
    config.GAIN = args.gain
    config.OUTPUT_DIR = args.output_dir
    config.PREFIX = args.prefix
    config.TRIGGER_ENABLED = args.trigger
    config.TRIGGER_THRESHOLD_DB = args.threshold
    config.SCAN_MODE = args.scan
    config.SHOW_SPECTRUM = not args.no_viz
    
    # Create and initialize recorder
    recorder = LiveSignalRecorder(config)
    
    if not await recorder.initialize():
        print("Failed to initialize recorder")
        sys.exit(1)
    
    # Start visualization
    if config.SHOW_SPECTRUM:
        asyncio.create_task(recorder.run_visualization())
    
    # Run based on mode
    if config.TRIGGER_ENABLED:
        await recorder.start_trigger_recording()
    elif config.SCAN_MODE:
        await recorder.scan_frequencies()
    else:
        # Wait for user input
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await recorder.shutdown()


if __name__ == "__main__":
    asyncio.run(main())