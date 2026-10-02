#!/usr/bin/env python3
"""
Throughput Performance Tests

Tests for system throughput including:
- Sample processing rate
- Detection throughput
- API request handling
- Database write/read performance
- WebSocket message throughput
- Real-time data streaming capacity
- Concurrent connection handling
- Batch processing performance
- Memory usage under load
- CPU utilization during high throughput
"""

import asyncio
import time
import json
import psutil
import os
import threading
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from datetime import datetime
import numpy as np
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import application components
from infrastructure.hardware.mock_hardware import MockSDR
from infrastructure.storage.database import DatabaseManager, DatabaseConfig, DatabaseType
from infrastructure.messaging.websocket_server import WebSocketManager
from app.services import DetectionService
from domain.algorithms.fft import compute_fft
from domain.algorithms.psd import compute_psd


# ============================================================================
# Test Configuration
# ============================================================================

@dataclass
class ThroughputConfig:
    """Throughput test configuration"""
    
    # Sample processing
    sample_rate: float = 10e6
    chunk_sizes: List[int] = None
    
    # Detection throughput
    detections_per_second_target: int = 100
    test_duration_seconds: int = 30
    
    # API throughput
    api_concurrent_requests: List[int] = None
    api_request_duration: int = 60
    
    # Database throughput
    batch_sizes: List[int] = None
    db_test_duration: int = 30
    
    # WebSocket throughput
    ws_concurrent_clients: List[int] = None
    ws_message_rate: int = 100
    
    # Resource thresholds
    max_cpu_percent: float = 80.0
    max_memory_mb: float = 1024.0
    
    def __post_init__(self):
        if self.chunk_sizes is None:
            self.chunk_sizes = [1024, 4096, 16384, 65536]
        
        if self.api_concurrent_requests is None:
            self.api_concurrent_requests = [1, 10, 50, 100]
        
        if self.batch_sizes is None:
            self.batch_sizes = [10, 100, 1000, 5000]
        
        if self.ws_concurrent_clients is None:
            self.ws_concurrent_clients = [1, 10, 50, 100]


# ============================================================================
# Performance Metrics
# ============================================================================

class ThroughputMetrics:
    """Collect and analyze throughput metrics"""
    
    def __init__(self):
        self.samples = []
        self.start_time = None
        self.end_time = None
        self.cpu_samples = []
        self.memory_samples = []
    
    def start(self):
        """Start metric collection"""
        self.start_time = time.time()
        self.samples = []
        self.cpu_samples = []
        self.memory_samples = []
    
    def stop(self):
        """Stop metric collection"""
        self.end_time = time.time()
    
    def record_sample(self, value: float, unit: str = "ops"):
        """Record a sample"""
        self.samples.append({
            'timestamp': time.time() - self.start_time,
            'value': value,
            'unit': unit
        })
    
    def record_resource_usage(self):
        """Record current resource usage"""
        self.cpu_samples.append(psutil.cpu_percent())
        self.memory_samples.append(psutil.Process().memory_info().rss / 1024 / 1024)
    
    @property
    def duration(self) -> float:
        """Get test duration"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0
    
    @property
    def total_operations(self) -> int:
        """Get total operations"""
        return len(self.samples)
    
    @property
    def throughput(self) -> float:
        """Calculate throughput (ops/second)"""
        if self.duration > 0:
            return self.total_operations / self.duration
        return 0
    
    @property
    def avg_cpu(self) -> float:
        """Get average CPU usage"""
        return np.mean(self.cpu_samples) if self.cpu_samples else 0
    
    @property
    def avg_memory_mb(self) -> float:
        """Get average memory usage"""
        return np.mean(self.memory_samples) if self.memory_samples else 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        if not self.samples:
            return {}
        
        values = [s['value'] for s in self.samples]
        
        return {
            'duration_seconds': self.duration,
            'total_operations': self.total_operations,
            'throughput_ops_per_sec': self.throughput,
            'mean_ops_per_sec': np.mean(values),
            'median_ops_per_sec': np.median(values),
            'min_ops_per_sec': np.min(values),
            'max_ops_per_sec': np.max(values),
            'std_ops_per_sec': np.std(values),
            'p95_ops_per_sec': np.percentile(values, 95),
            'p99_ops_per_sec': np.percentile(values, 99),
            'avg_cpu_percent': self.avg_cpu,
            'avg_memory_mb': self.avg_memory_mb,
            'samples': len(self.samples)
        }
    
    def print_summary(self, title: str):
        """Print summary statistics"""
        print(f"\n{title}")
        print("-" * 40)
        stats = self.get_stats()
        print(f"  Duration: {stats.get('duration_seconds', 0):.2f}s")
        print(f"  Total operations: {stats.get('total_operations', 0):,}")
        print(f"  Throughput: {stats.get('throughput_ops_per_sec', 0):.2f} ops/sec")
        print(f"  Mean: {stats.get('mean_ops_per_sec', 0):.2f} ops/sec")
        print(f"  P95: {stats.get('p95_ops_per_sec', 0):.2f} ops/sec")
        print(f"  P99: {stats.get('p99_ops_per_sec', 0):.2f} ops/sec")
        print(f"  CPU: {stats.get('avg_cpu_percent', 0):.1f}%")
        print(f"  Memory: {stats.get('avg_memory_mb', 0):.1f} MB")


# ============================================================================
# Sample Processing Throughput Tests
# ============================================================================

class TestSampleProcessingThroughput:
    """Test sample processing throughput"""
    
    def __init__(self, config: ThroughputConfig):
        self.config = config
        self.metrics = ThroughputMetrics()
        self.hardware = MockSDR()
        self.hardware.initialize({'sample_rate': config.sample_rate})
    
    async def test_chunk_processing(self):
        """Test throughput for different chunk sizes"""
        print("\n" + "="*60)
        print("SAMPLE PROCESSING THROUGHPUT")
        print("="*60)
        
        results = {}
        
        for chunk_size in self.config.chunk_sizes:
            print(f"\n  Testing chunk size: {chunk_size} samples")
            
            metrics = ThroughputMetrics()
            metrics.start()
            
            total_samples = 0
            start_time = time.time()
            
            while time.time() - start_time < 10:
                # Read chunk
                samples = self.hardware.read_samples(chunk_size)
                
                # Process chunk (FFT + PSD)
                fft_result = compute_fft(samples)
                psd = compute_psd(fft_result)
                
                total_samples += len(samples)
                metrics.record_sample(len(samples) / metrics.duration if metrics.duration > 0 else 0)
                metrics.record_resource_usage()
            
            metrics.stop()
            
            throughput_msps = total_samples / metrics.duration / 1e6
            results[chunk_size] = {
                'throughput_msps': throughput_msps,
                'samples_per_second': total_samples / metrics.duration,
                'cpu_percent': metrics.avg_cpu,
                'memory_mb': metrics.avg_memory_mb
            }
            
            print(f"    Throughput: {throughput_msps:.2f} MS/s")
            print(f"    CPU: {metrics.avg_cpu:.1f}%")
            print(f"    Memory: {metrics.avg_memory_mb:.1f} MB")
        
        # Find optimal chunk size
        optimal = max(results.items(), key=lambda x: x[1]['throughput_msps'])
        print(f"\n  Optimal chunk size: {optimal[0]} samples ({optimal[1]['throughput_msps']:.2f} MS/s)")
        
        return results
    
    async def test_continuous_processing(self):
        """Test continuous processing throughput over time"""
        print("\n" + "="*60)
        print("CONTINUOUS PROCESSING THROUGHPUT")
        print("="*60)
        
        optimal_chunk = 16384  # Typical optimal size
        self.metrics.start()
        
        start_time = time.time()
        samples_processed = 0
        
        while time.time() - start_time < self.config.test_duration_seconds:
            samples = self.hardware.read_samples(optimal_chunk)
            
            # Simulate processing pipeline
            fft_result = compute_fft(samples)
            psd = compute_psd(fft_result)
            
            samples_processed += len(samples)
            self.metrics.record_sample(len(samples) / self.metrics.duration if self.metrics.duration > 0 else 0)
            self.metrics.record_resource_usage()
        
        self.metrics.stop()
        
        throughput_msps = samples_processed / self.metrics.duration / 1e6
        print(f"\n  Duration: {self.metrics.duration:.2f}s")
        print(f"  Samples processed: {samples_processed:,}")
        print(f"  Throughput: {throughput_msps:.2f} MS/s")
        print(f"  CPU: {self.metrics.avg_cpu:.1f}%")
        print(f"  Memory: {self.metrics.avg_memory_mb:.1f} MB")
        
        return {
            'throughput_msps': throughput_msps,
            'duration': self.metrics.duration,
            'samples_processed': samples_processed
        }


# ============================================================================
# Detection Throughput Tests
# ============================================================================

class TestDetectionThroughput:
    """Test detection throughput"""
    
    def __init__(self, config: ThroughputConfig):
        self.config = config
        self.metrics = ThroughputMetrics()
        self.hardware = MockSDR()
        self.detection_service = None
    
    async def setup(self):
        """Set up detection service"""
        db_config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            sqlite_path=":memory:"
        )
        db = DatabaseManager(db_config)
        await db.initialize()
        
        self.detection_service = DetectionService(
            hardware=self.hardware,
            db=db
        )
        await self.detection_service.start()
    
    async def test_detection_rate(self):
        """Test maximum detection rate"""
        print("\n" + "="*60)
        print("DETECTION THROUGHPUT")
        print("="*60)
        
        self.metrics.start()
        
        start_time = time.time()
        detections = 0
        
        # Generate continuous drone signals
        async def generate_signals():
            nonlocal detections
            while time.time() - start_time < self.config.test_duration_seconds:
                self.hardware.inject_drone("DJI Mavic 3", 2.44e9)
                await asyncio.sleep(0.01)
                detections += 1
        
        # Process detections
        async def process_detections():
            while time.time() - start_time < self.config.test_duration_seconds:
                await asyncio.sleep(0.001)
                self.metrics.record_sample(detections / self.metrics.duration if self.metrics.duration > 0 else 0)
                self.metrics.record_resource_usage()
        
        await asyncio.gather(generate_signals(), process_detections())
        
        self.metrics.stop()
        
        detection_rate = detections / self.metrics.duration
        print(f"\n  Duration: {self.metrics.duration:.2f}s")
        print(f"  Total detections: {detections:,}")
        print(f"  Detection rate: {detection_rate:.2f} detections/sec")
        print(f"  CPU: {self.metrics.avg_cpu:.1f}%")
        print(f"  Memory: {self.metrics.avg_memory_mb:.1f} MB")
        
        # Compare to target
        target = self.config.detections_per_second_target
        if detection_rate >= target:
            print(f"  ✓ Target met: {detection_rate:.0f} >= {target} detections/sec")
        else:
            print(f"  ✗ Target not met: {detection_rate:.0f} < {target} detections/sec")
        
        return {
            'detection_rate': detection_rate,
            'total_detections': detections,
            'target': target,
            'met_target': detection_rate >= target
        }


# ============================================================================
# Database Throughput Tests
# ============================================================================

class TestDatabaseThroughput:
    """Test database read/write throughput"""
    
    def __init__(self, config: ThroughputConfig):
        self.config = config
        self.db = None
    
    async def setup(self):
        """Set up database"""
        db_config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            sqlite_path=":memory:"
        )
        self.db = DatabaseManager(db_config)
        await self.db.initialize()
        await self.db.create_tables()
    
    async def test_write_throughput(self):
        """Test database write throughput"""
        print("\n" + "="*60)
        print("DATABASE WRITE THROUGHPUT")
        print("="*60)
        
        results = {}
        
        for batch_size in self.config.batch_sizes:
            print(f"\n  Testing batch size: {batch_size}")
            
            metrics = ThroughputMetrics()
            metrics.start()
            
            total_writes = 0
            start_time = time.time()
            
            while time.time() - start_time < 10:
                # Prepare batch
                batch = []
                for i in range(batch_size):
                    batch.append((
                        f"det_{int(time.time())}_{i}",
                        datetime.now().isoformat(),
                        "DJI Mavic 3",
                        0.95,
                        "HIGH"
                    ))
                
                # Execute batch insert
                await self.db.execute_many(
                    "INSERT INTO detections (id, timestamp, drone_type, confidence, threat_level) VALUES (?, ?, ?, ?, ?)",
                    batch
                )
                
                total_writes += len(batch)
                metrics.record_sample(total_writes / metrics.duration if metrics.duration > 0 else 0)
                metrics.record_resource_usage()
            
            metrics.stop()
            
            write_rate = total_writes / metrics.duration
            results[batch_size] = {
                'writes_per_second': write_rate,
                'total_writes': total_writes,
                'cpu_percent': metrics.avg_cpu,
                'memory_mb': metrics.avg_memory_mb
            }
            
            print(f"    Write rate: {write_rate:.0f} writes/sec")
            print(f"    CPU: {metrics.avg_cpu:.1f}%")
            print(f"    Memory: {metrics.avg_memory_mb:.1f} MB")
        
        # Find optimal batch size
        optimal = max(results.items(), key=lambda x: x[1]['writes_per_second'])
        print(f"\n  Optimal batch size: {optimal[0]} ({optimal[1]['writes_per_second']:.0f} writes/sec)")
        
        return results
    
    async def test_read_throughput(self):
        """Test database read throughput"""
        print("\n" + "="*60)
        print("DATABASE READ THROUGHPUT")
        print("="*60)
        
        # Insert test data
        print("  Inserting test data...")
        await self.test_write_throughput()
        
        metrics = ThroughputMetrics()
        metrics.start()
        
        total_reads = 0
        start_time = time.time()
        
        while time.time() - start_time < 10:
            # Query detections
            results = await self.db.fetch_all(
                "SELECT * FROM detections ORDER BY timestamp DESC LIMIT 100"
            )
            total_reads += len(results)
            metrics.record_sample(total_reads / metrics.duration if metrics.duration > 0 else 0)
            metrics.record_resource_usage()
        
        metrics.stop()
        
        read_rate = total_reads / metrics.duration
        print(f"\n  Read rate: {read_rate:.0f} records/sec")
        print(f"  Total reads: {total_reads:,}")
        print(f"  CPU: {metrics.avg_cpu:.1f}%")
        print(f"  Memory: {metrics.avg_memory_mb:.1f} MB")
        
        return {
            'read_rate': read_rate,
            'total_reads': total_reads
        }


# ============================================================================
# API Throughput Tests
# ============================================================================

class TestAPIThroughput:
    """Test API request throughput"""
    
    def __init__(self, config: ThroughputConfig):
        self.config = config
        self.base_url = f"http://localhost:8888"
    
    async def test_concurrent_requests(self):
        """Test concurrent request handling"""
        print("\n" + "="*60)
        print("API THROUGHPUT")
        print("="*60)
        
        import aiohttp
        
        results = {}
        
        for concurrency in self.config.api_concurrent_requests:
            print(f"\n  Testing concurrency: {concurrency}")
            
            metrics = ThroughputMetrics()
            metrics.start()
            
            async def make_request(session, i):
                try:
                    async with session.get(f"{self.base_url}/api/detections?limit=10") as resp:
                        return resp.status == 200
                except:
                    return False
            
            async with aiohttp.ClientSession() as session:
                start_time = time.time()
                request_count = 0
                
                while time.time() - start_time < 10:
                    # Create batch of concurrent requests
                    tasks = [make_request(session, i) for i in range(concurrency)]
                    results_batch = await asyncio.gather(*tasks)
                    request_count += sum(results_batch)
                    
                    metrics.record_sample(request_count / metrics.duration if metrics.duration > 0 else 0)
                    metrics.record_resource_usage()
            
            metrics.stop()
            
            request_rate = request_count / metrics.duration
            results[concurrency] = {
                'requests_per_second': request_rate,
                'total_requests': request_count,
                'cpu_percent': metrics.avg_cpu,
                'memory_mb': metrics.avg_memory_mb
            }
            
            print(f"    Request rate: {request_rate:.0f} req/sec")
            print(f"    CPU: {metrics.avg_cpu:.1f}%")
            print(f"    Memory: {metrics.avg_memory_mb:.1f} MB")
        
        return results


# ============================================================================
# WebSocket Throughput Tests
# ============================================================================

class TestWebSocketThroughput:
    """Test WebSocket message throughput"""
    
    def __init__(self, config: ThroughputConfig):
        self.config = config
        self.ws_url = f"ws://localhost:8889"
    
    async def test_message_throughput(self):
        """Test WebSocket message throughput"""
        print("\n" + "="*60)
        print("WEBSOCKET THROUGHPUT")
        print("="*60)
        
        import websockets
        
        results = {}
        
        for num_clients in self.config.ws_concurrent_clients:
            print(f"\n  Testing clients: {num_clients}")
            
            metrics = ThroughputMetrics()
            metrics.start()
            
            async def client_handler(client_id):
                try:
                    async with websockets.connect(self.ws_url) as ws:
                        messages_received = 0
                        while time.time() - metrics.start_time < 10:
                            await ws.send(json.dumps({"type": "ping"}))
                            response = await asyncio.wait_for(ws.recv(), timeout=1.0)
                            messages_received += 1
                        return messages_received
                except:
                    return 0
            
            # Create client tasks
            tasks = [client_handler(i) for i in range(num_clients)]
            results_batch = await asyncio.gather(*tasks)
            
            total_messages = sum(results_batch)
            metrics.stop()
            
            message_rate = total_messages / metrics.duration
            results[num_clients] = {
                'messages_per_second': message_rate,
                'total_messages': total_messages,
                'messages_per_client': total_messages / num_clients if num_clients > 0 else 0
            }
            
            print(f"    Message rate: {message_rate:.0f} msg/sec")
            print(f"    Messages per client: {results[num_clients]['messages_per_client']:.0f}")
        
        return results


# ============================================================================
# Main Test Runner
# ============================================================================

class ThroughputTestRunner:
    """Run all throughput tests"""
    
    def __init__(self, config: ThroughputConfig = None):
        self.config = config or ThroughputConfig()
        self.results = {}
    
    async def run_all(self):
        """Run all throughput tests"""
        print("\n" + "="*60)
        print("THROUGHPUT PERFORMANCE TESTS")
        print("="*60)
        
        # Sample processing tests
        processor = TestSampleProcessingThroughput(self.config)
        self.results['sample_processing'] = await processor.test_chunk_processing()
        self.results['continuous_processing'] = await processor.test_continuous_processing()
        
        # Detection throughput tests
        detector = TestDetectionThroughput(self.config)
        await detector.setup()
        self.results['detection'] = await detector.test_detection_rate()
        
        # Database throughput tests
        db_tester = TestDatabaseThroughput(self.config)
        await db_tester.setup()
        self.results['database_write'] = await db_tester.test_write_throughput()
        self.results['database_read'] = await db_tester.test_read_throughput()
        
        # Print final summary
        self.print_summary()
        
        return self.results
    
    def print_summary(self):
        """Print final summary"""
        print("\n" + "="*60)
        print("THROUGHPUT TEST SUMMARY")
        print("="*60)
        
        # Sample processing
        if 'sample_processing' in self.results:
            optimal = max(self.results['sample_processing'].items(), 
                         key=lambda x: x[1]['throughput_msps'])
            print(f"\n  Sample Processing:")
            print(f"    Optimal chunk: {optimal[0]} samples")
            print(f"    Max throughput: {optimal[1]['throughput_msps']:.2f} MS/s")
        
        # Detection
        if 'detection' in self.results:
            det = self.results['detection']
            print(f"\n  Detection:")
            print(f"    Rate: {det.get('detection_rate', 0):.2f} detections/sec")
            print(f"    Target met: {'✓' if det.get('met_target', False) else '✗'}")
        
        # Database
        if 'database_write' in self.results:
            optimal = max(self.results['database_write'].items(),
                         key=lambda x: x[1]['writes_per_second'])
            print(f"\n  Database Write:")
            print(f"    Optimal batch: {optimal[0]}")
            print(f"    Max write rate: {optimal[1]['writes_per_second']:.0f} writes/sec")
        
        if 'database_read' in self.results:
            read = self.results['database_read']
            print(f"\n  Database Read:")
            print(f"    Read rate: {read.get('read_rate', 0):.0f} records/sec")


# ============================================================================
# Main Execution
# ============================================================================

async def main():
    """Main entry point"""
    config = ThroughputConfig(
        test_duration_seconds=30,
        detections_per_second_target=50
    )
    
    runner = ThroughputTestRunner(config)
    await runner.run_all()


if __name__ == "__main__":
    asyncio.run(main())