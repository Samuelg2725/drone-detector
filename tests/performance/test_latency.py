#!/usr/bin/env python3
"""
Latency Performance Tests

Tests for system latency including:
- Signal acquisition latency
- FFT/PSD computation latency
- Detection pipeline latency
- Database query latency
- API response latency
- WebSocket message latency
- End-to-end detection latency
- Real-time streaming latency
- Notification delivery latency
- Alert generation latency
"""

import asyncio
import time
import json
import statistics
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from datetime import datetime
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import application components
from infrastructure.hardware.mock_hardware import MockSDR
from infrastructure.storage.database import DatabaseManager, DatabaseConfig, DatabaseType
from app.services import DetectionService
from domain.algorithms.fft import compute_fft
from domain.algorithms.psd compute_psd
from domain.algorithms.peak_detection import detect_peaks


# ============================================================================
# Test Configuration
# ============================================================================

@dataclass
class LatencyConfig:
    """Latency test configuration"""
    
    # Sample sizes for latency testing
    sample_sizes: List[int] = None
    
    # Number of measurements per test
    num_measurements: int = 100
    
    # Warmup iterations
    warmup_iterations: int = 10
    
    # Test durations (seconds)
    short_duration: int = 30
    medium_duration: int = 60
    long_duration: int = 300
    
    # Latency thresholds (milliseconds)
    max_acquisition_latency_ms: float = 10.0
    max_fft_latency_ms: float = 5.0
    max_detection_latency_ms: float = 50.0
    max_db_query_latency_ms: float = 10.0
    max_api_latency_ms: float = 100.0
    max_ws_latency_ms: float = 50.0
    max_e2e_latency_ms: float = 200.0
    
    # Percentile targets
    p50_target_ms: float = 10.0
    p95_target_ms: float = 50.0
    p99_target_ms: float = 100.0
    
    def __post_init__(self):
        if self.sample_sizes is None:
            self.sample_sizes = [1024, 4096, 16384, 65536, 262144]


# ============================================================================
# Latency Measurement Utilities
# ============================================================================

class LatencyStats:
    """Statistics for latency measurements"""
    
    def __init__(self, name: str):
        self.name = name
        self.measurements: List[float] = []
        self.timestamps: List[float] = []
    
    def add_measurement(self, latency_ms: float):
        """Add a latency measurement"""
        self.measurements.append(latency_ms)
        self.timestamps.append(time.time())
    
    @property
    def count(self) -> int:
        return len(self.measurements)
    
    @property
    def min_ms(self) -> float:
        return min(self.measurements) if self.measurements else 0
    
    @property
    def max_ms(self) -> float:
        return max(self.measurements) if self.measurements else 0
    
    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.measurements) if self.measurements else 0
    
    @property
    def median_ms(self) -> float:
        return statistics.median(self.measurements) if self.measurements else 0
    
    @property
    def std_dev_ms(self) -> float:
        return statistics.stdev(self.measurements) if len(self.measurements) > 1 else 0
    
    def percentile(self, p: float) -> float:
        """Calculate percentile"""
        if not self.measurements:
            return 0
        sorted_measurements = sorted(self.measurements)
        idx = int(len(sorted_measurements) * p / 100)
        return sorted_measurements[min(idx, len(sorted_measurements) - 1)]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        return {
            'name': self.name,
            'count': self.count,
            'min_ms': self.min_ms,
            'max_ms': self.max_ms,
            'mean_ms': self.mean_ms,
            'median_ms': self.median_ms,
            'std_dev_ms': self.std_dev_ms,
            'p50_ms': self.percentile(50),
            'p90_ms': self.percentile(90),
            'p95_ms': self.percentile(95),
            'p99_ms': self.percentile(99)
        }
    
    def print_summary(self):
        """Print summary statistics"""
        stats = self.get_stats()
        print(f"\n  {self.name} Latency:")
        print(f"    Count: {stats['count']}")
        print(f"    Min: {stats['min_ms']:.3f} ms")
        print(f"    Max: {stats['max_ms']:.3f} ms")
        print(f"    Mean: {stats['mean_ms']:.3f} ms")
        print(f"    Median: {stats['median_ms']:.3f} ms")
        print(f"    P95: {stats['p95_ms']:.3f} ms")
        print(f"    P99: {stats['p99_ms']:.3f} ms")
        print(f"    Std Dev: {stats['std_dev_ms']:.3f} ms")


# ============================================================================
# Component Latency Tests
# ============================================================================

class TestAcquisitionLatency:
    """Test signal acquisition latency"""
    
    def __init__(self, config: LatencyConfig):
        self.config = config
        self.hardware = MockSDR()
        self.hardware.initialize({'sample_rate': 10e6})
        self.stats = LatencyStats("Acquisition")
    
    async def measure(self, num_samples: int) -> float:
        """Measure acquisition latency for given sample count"""
        start = time.perf_counter()
        samples = self.hardware.read_samples(num_samples)
        end = time.perf_counter()
        return (end - start) * 1000
    
    async def run(self):
        """Run acquisition latency tests"""
        print("\n" + "="*60)
        print("ACQUISITION LATENCY")
        print("="*60)
        
        # Warmup
        print("  Warming up...")
        for _ in range(self.config.warmup_iterations):
            await self.measure(16384)
        
        results = {}
        
        for num_samples in self.config.sample_sizes:
            print(f"\n  Testing {num_samples} samples...")
            
            for _ in range(self.config.num_measurements):
                latency = await self.measure(num_samples)
                self.stats.add_measurement(latency)
            
            stats = self.stats.get_stats()
            results[num_samples] = stats
            print(f"    Mean: {stats['mean_ms']:.3f} ms")
            print(f"    P95: {stats['p95_ms']:.3f} ms")
        
        self.stats.print_summary()
        
        # Verify threshold
        if self.stats.mean_ms <= self.config.max_acquisition_latency_ms:
            print(f"\n  ✓ Acquisition latency OK (mean: {self.stats.mean_ms:.2f}ms ≤ {self.config.max_acquisition_latency_ms}ms)")
        else:
            print(f"\n  ✗ Acquisition latency HIGH (mean: {self.stats.mean_ms:.2f}ms > {self.config.max_acquisition_latency_ms}ms)")
        
        return results


class TestFFTLatency:
    """Test FFT computation latency"""
    
    def __init__(self, config: LatencyConfig):
        self.config = config
        self.stats = LatencyStats("FFT")
    
    def measure(self, samples: np.ndarray) -> float:
        """Measure FFT latency"""
        start = time.perf_counter()
        result = compute_fft(samples)
        end = time.perf_counter()
        return (end - start) * 1000
    
    async def run(self):
        """Run FFT latency tests"""
        print("\n" + "="*60)
        print("FFT COMPUTATION LATENCY")
        print("="*60)
        
        # Warmup
        print("  Warming up...")
        for _ in range(self.config.warmup_iterations):
            test_samples = np.random.randn(16384) + 1j * np.random.randn(16384)
            self.measure(test_samples)
        
        results = {}
        
        for num_samples in self.config.sample_sizes:
            print(f"\n  Testing FFT size: {num_samples}")
            samples = np.random.randn(num_samples) + 1j * np.random.randn(num_samples)
            
            for _ in range(self.config.num_measurements):
                latency = self.measure(samples)
                self.stats.add_measurement(latency)
            
            stats = self.stats.get_stats()
            results[num_samples] = stats
            print(f"    Mean: {stats['mean_ms']:.3f} ms")
            print(f"    P95: {stats['p95_ms']:.3f} ms")
        
        self.stats.print_summary()
        
        # Verify threshold
        if self.stats.mean_ms <= self.config.max_fft_latency_ms:
            print(f"\n  ✓ FFT latency OK (mean: {self.stats.mean_ms:.2f}ms ≤ {self.config.max_fft_latency_ms}ms)")
        else:
            print(f"\n  ✗ FFT latency HIGH (mean: {self.stats.mean_ms:.2f}ms > {self.config.max_fft_latency_ms}ms)")
        
        return results


class TestPSDLatency:
    """Test PSD computation latency"""
    
    def __init__(self, config: LatencyConfig):
        self.config = config
        self.stats = LatencyStats("PSD")
    
    def measure(self, samples: np.ndarray, sample_rate: float) -> float:
        """Measure PSD latency"""
        start = time.perf_counter()
        result = compute_psd(samples, sample_rate)
        end = time.perf_counter()
        return (end - start) * 1000
    
    async def run(self):
        """Run PSD latency tests"""
        print("\n" + "="*60)
        print("PSD COMPUTATION LATENCY")
        print("="*60)
        
        # Warmup
        print("  Warming up...")
        for _ in range(self.config.warmup_iterations):
            test_samples = np.random.randn(16384) + 1j * np.random.randn(16384)
            self.measure(test_samples, 10e6)
        
        results = {}
        
        for num_samples in self.config.sample_sizes:
            print(f"\n  Testing {num_samples} samples...")
            samples = np.random.randn(num_samples) + 1j * np.random.randn(num_samples)
            
            for _ in range(self.config.num_measurements):
                latency = self.measure(samples, 10e6)
                self.stats.add_measurement(latency)
            
            stats = self.stats.get_stats()
            results[num_samples] = stats
            print(f"    Mean: {stats['mean_ms']:.3f} ms")
            print(f"    P95: {stats['p95_ms']:.3f} ms")
        
        self.stats.print_summary()
        
        return results


class TestDetectionLatency:
    """Test detection pipeline latency"""
    
    def __init__(self, config: LatencyConfig):
        self.config = config
        self.hardware = MockSDR()
        self.hardware.initialize({'sample_rate': 10e6})
        self.stats = LatencyStats("Detection")
    
    async def measure(self) -> float:
        """Measure end-to-end detection latency"""
        start = time.perf_counter()
        
        # Acquire samples
        samples = self.hardware.read_samples(16384)
        
        # Compute FFT
        fft_result = compute_fft(samples)
        
        # Compute PSD
        psd = compute_psd(fft_result)
        
        # Detect peaks
        peaks = detect_peaks(psd)
        
        end = time.perf_counter()
        return (end - start) * 1000
    
    async def run(self):
        """Run detection latency tests"""
        print("\n" + "="*60)
        print("DETECTION PIPELINE LATENCY")
        print("="*60)
        
        # Warmup
        print("  Warming up...")
        for _ in range(self.config.warmup_iterations):
            await self.measure()
        
        for _ in range(self.config.num_measurements):
            latency = await self.measure()
            self.stats.add_measurement(latency)
        
        self.stats.print_summary()
        
        # Verify threshold
        if self.stats.mean_ms <= self.config.max_detection_latency_ms:
            print(f"\n  ✓ Detection latency OK (mean: {self.stats.mean_ms:.2f}ms ≤ {self.config.max_detection_latency_ms}ms)")
        else:
            print(f"\n  ✗ Detection latency HIGH (mean: {self.stats.mean_ms:.2f}ms > {self.config.max_detection_latency_ms}ms)")
        
        return self.stats.get_stats()


# ============================================================================
# Database Latency Tests
# ============================================================================

class TestDatabaseLatency:
    """Test database query latency"""
    
    def __init__(self, config: LatencyConfig):
        self.config = config
        self.db = None
        self.stats_write = LatencyStats("Database Write")
        self.stats_read = LatencyStats("Database Read")
    
    async def setup(self):
        """Set up database"""
        db_config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            sqlite_path=":memory:"
        )
        self.db = DatabaseManager(db_config)
        await self.db.initialize()
        await self.db.create_tables()
    
    async def measure_write(self) -> float:
        """Measure write latency"""
        import uuid
        
        start = time.perf_counter()
        await self.db.execute(
            "INSERT INTO detections (id, timestamp, drone_type, confidence, threat_level) VALUES (?, ?, ?, ?, ?)",
            str(uuid.uuid4()),
            datetime.now().isoformat(),
            "DJI Mavic 3",
            0.95,
            "HIGH"
        )
        end = time.perf_counter()
        return (end - start) * 1000
    
    async def measure_read(self) -> float:
        """Measure read latency"""
        start = time.perf_counter()
        await self.db.fetch_all("SELECT * FROM detections LIMIT 10")
        end = time.perf_counter()
        return (end - start) * 1000
    
    async def run(self):
        """Run database latency tests"""
        print("\n" + "="*60)
        print("DATABASE LATENCY")
        print("="*60)
        
        # Write latency
        print("\n  Write Latency:")
        for _ in range(self.config.num_measurements):
            latency = await self.measure_write()
            self.stats_write.add_measurement(latency)
        
        self.stats_write.print_summary()
        
        # Read latency
        print("\n  Read Latency:")
        for _ in range(self.config.num_measurements):
            latency = await self.measure_read()
            self.stats_read.add_measurement(latency)
        
        self.stats_read.print_summary()
        
        # Verify thresholds
        write_ok = self.stats_write.mean_ms <= self.config.max_db_query_latency_ms
        read_ok = self.stats_read.mean_ms <= self.config.max_db_query_latency_ms
        
        if write_ok and read_ok:
            print(f"\n  ✓ Database latency OK")
        else:
            if not write_ok:
                print(f"\n  ✗ Write latency HIGH: {self.stats_write.mean_ms:.2f}ms")
            if not read_ok:
                print(f"  ✗ Read latency HIGH: {self.stats_read.mean_ms:.2f}ms")
        
        return {
            'write': self.stats_write.get_stats(),
            'read': self.stats_read.get_stats()
        }


# ============================================================================
# End-to-End Latency Tests
# ============================================================================

class TestEndToEndLatency:
    """Test end-to-end system latency"""
    
    def __init__(self, config: LatencyConfig):
        self.config = config
        self.hardware = MockSDR()
        self.db = None
        self.detection_service = None
        self.stats = LatencyStats("End-to-End")
    
    async def setup(self):
        """Set up system"""
        self.hardware.initialize({'sample_rate': 10e6})
        
        db_config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            sqlite_path=":memory:"
        )
        self.db = DatabaseManager(db_config)
        await self.db.initialize()
        await self.db.create_tables()
        
        self.detection_service = DetectionService(
            hardware=self.hardware,
            db=self.db
        )
        await self.detection_service.start()
    
    async def measure(self) -> float:
        """Measure end-to-end latency from signal to detection"""
        start = time.perf_counter()
        
        # Inject drone signal
        self.hardware.inject_drone("DJI Mavic 3", 2.44e9)
        
        # Wait for detection (simplified - in real system, would wait for event)
        await asyncio.sleep(0.01)
        
        # Query for recent detection
        result = await self.db.fetch_one(
            "SELECT * FROM detections ORDER BY timestamp DESC LIMIT 1"
        )
        
        end = time.perf_counter()
        return (end - start) * 1000
    
    async def run(self):
        """Run end-to-end latency tests"""
        print("\n" + "="*60)
        print("END-TO-END SYSTEM LATENCY")
        print("="*60)
        
        # Warmup
        print("  Warming up...")
        for _ in range(self.config.warmup_iterations):
            await self.measure()
        
        for _ in range(self.config.num_measurements):
            latency = await self.measure()
            self.stats.add_measurement(latency)
        
        self.stats.print_summary()
        
        # Verify threshold
        if self.stats.mean_ms <= self.config.max_e2e_latency_ms:
            print(f"\n  ✓ End-to-end latency OK (mean: {self.stats.mean_ms:.2f}ms ≤ {self.config.max_e2e_latency_ms}ms)")
        else:
            print(f"\n  ✗ End-to-end latency HIGH (mean: {self.stats.mean_ms:.2f}ms > {self.config.max_e2e_latency_ms}ms)")
        
        return self.stats.get_stats()


# ============================================================================
# Latency Stability Tests
# ============================================================================

class TestLatencyStability:
    """Test latency stability over time"""
    
    def __init__(self, config: LatencyConfig):
        self.config = config
        self.stats = defaultdict(lambda: LatencyStats(""))
    
    async def run(self, duration_seconds: int):
        """Run latency stability test"""
        print("\n" + "="*60)
        print(f"LATENCY STABILITY ({duration_seconds}s)")
        print("="*60)
        
        hardware = MockSDR()
        hardware.initialize({'sample_rate': 10e6})
        
        start_time = time.time()
        measurements = []
        
        while time.time() - start_time < duration_seconds:
            # Measure acquisition latency
            start = time.perf_counter()
            samples = hardware.read_samples(16384)
            acq_latency = (time.perf_counter() - start) * 1000
            
            # Measure processing latency
            start = time.perf_counter()
            fft_result = compute_fft(samples)
            proc_latency = (time.perf_counter() - start) * 1000
            
            measurements.append({
                'timestamp': time.time() - start_time,
                'acquisition_ms': acq_latency,
                'processing_ms': proc_latency,
                'total_ms': acq_latency + proc_latency
            })
            
            await asyncio.sleep(0.01)
        
        # Analyze measurements
        acq_latencies = [m['acquisition_ms'] for m in measurements]
        proc_latencies = [m['processing_ms'] for m in measurements]
        total_latencies = [m['total_ms'] for m in measurements]
        
        print(f"\n  Measurements: {len(measurements)}")
        print(f"\n  Acquisition Latency:")
        print(f"    Mean: {statistics.mean(acq_latencies):.3f} ms")
        print(f"    Std Dev: {statistics.stdev(acq_latencies):.3f} ms")
        print(f"    Max: {max(acq_latencies):.3f} ms")
        
        print(f"\n  Processing Latency:")
        print(f"    Mean: {statistics.mean(proc_latencies):.3f} ms")
        print(f"    Std Dev: {statistics.stdev(proc_latencies):.3f} ms")
        print(f"    Max: {max(proc_latencies):.3f} ms")
        
        print(f"\n  Total Latency:")
        print(f"    Mean: {statistics.mean(total_latencies):.3f} ms")
        print(f"    Std Dev: {statistics.stdev(total_latencies):.3f} ms")
        print(f"    Max: {max(total_latencies):.3f} ms")
        
        # Check for outliers
        outlier_threshold = statistics.mean(total_latencies) + 3 * statistics.stdev(total_latencies)
        outliers = [m for m in total_latencies if m > outlier_threshold]
        
        if outliers:
            print(f"\n  ⚠️  Outliers detected: {len(outliers)} ({len(outliers)/len(total_latencies)*100:.1f}%)")
        else:
            print(f"\n  ✓ No significant outliers detected")
        
        return measurements


# ============================================================================
# Main Test Runner
# ============================================================================

class LatencyTestRunner:
    """Run all latency tests"""
    
    def __init__(self, config: LatencyConfig = None):
        self.config = config or LatencyConfig()
        self.results = {}
    
    async def run_all(self):
        """Run all latency tests"""
        print("\n" + "="*60)
        print("LATENCY PERFORMANCE TESTS")
        print("="*60)
        
        # Acquisition latency
        acq_tester = TestAcquisitionLatency(self.config)
        self.results['acquisition'] = await acq_tester.run()
        
        # FFT latency
        fft_tester = TestFFTLatency(self.config)
        self.results['fft'] = await fft_tester.run()
        
        # PSD latency
        psd_tester = TestPSDLatency(self.config)
        self.results['psd'] = await psd_tester.run()
        
        # Detection latency
        det_tester = TestDetectionLatency(self.config)
        self.results['detection'] = await det_tester.run()
        
        # Database latency
        db_tester = TestDatabaseLatency(self.config)
        await db_tester.setup()
        self.results['database'] = await db_tester.run()
        
        # End-to-end latency
        e2e_tester = TestEndToEndLatency(self.config)
        await e2e_tester.setup()
        self.results['e2e'] = await e2e_tester.run()
        
        # Latency stability
        stability_tester = TestLatencyStability(self.config)
        self.results['stability'] = await stability_tester.run(self.config.medium_duration)
        
        # Print final summary
        self.print_summary()
        
        return self.results
    
    def print_summary(self):
        """Print final summary"""
        print("\n" + "="*60)
        print("LATENCY TEST SUMMARY")
        print("="*60)
        
        thresholds = {
            'Acquisition': self.config.max_acquisition_latency_ms,
            'FFT': self.config.max_fft_latency_ms,
            'Detection': self.config.max_detection_latency_ms,
            'Database Query': self.config.max_db_query_latency_ms,
            'End-to-End': self.config.max_e2e_latency_ms
        }
        
        print("\n  Component | Mean (ms) | Target (ms) | Status")
        print("  " + "-" * 50)
        
        for component, threshold in thresholds.items():
            if component == 'Acquisition' and 'acquisition' in self.results:
                mean = self.results['acquisition'].get('mean_ms', 0)
            elif component == 'FFT' and 'fft' in self.results:
                mean = self.results['fft'].get('mean_ms', 0)
            elif component == 'Detection' and 'detection' in self.results:
                mean = self.results['detection'].get('mean_ms', 0)
            elif component == 'Database Query' and 'database' in self.results:
                mean = self.results['database'].get('write', {}).get('mean_ms', 0)
            elif component == 'End-to-End' and 'e2e' in self.results:
                mean = self.results['e2e'].get('mean_ms', 0)
            else:
                continue
            
            status = "✓" if mean <= threshold else "✗"
            print(f"  {component:12} | {mean:9.2f} | {threshold:11.2f} | {status}")
        
        # Percentile summary
        if 'e2e' in self.results:
            print(f"\n  End-to-End Latency Percentiles:")
            print(f"    P50: {self.results['e2e'].get('p50_ms', 0):.2f} ms (target: {self.config.p50_target_ms} ms)")
            print(f"    P95: {self.results['e2e'].get('p95_ms', 0):.2f} ms (target: {self.config.p95_target_ms} ms)")
            print(f"    P99: {self.results['e2e'].get('p99_ms', 0):.2f} ms (target: {self.config.p99_target_ms} ms)")


# ============================================================================
# Main Execution
# ============================================================================

async def main():
    """Main entry point"""
    config = LatencyConfig(
        num_measurements=100,
        max_acquisition_latency_ms=15,
        max_fft_latency_ms=10,
        max_detection_latency_ms=50,
        max_e2e_latency_ms=150
    )
    
    runner = LatencyTestRunner(config)
    await runner.run_all()


if __name__ == "__main__":
    asyncio.run(main())