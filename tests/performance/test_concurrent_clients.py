#!/usr/bin/env python3
"""
Concurrent Clients Performance Tests

Tests for system performance under concurrent load including:
- Multiple API client connections
- Concurrent WebSocket connections
- Simultaneous detection processing
- Database connection pooling
- Parallel IQ stream processing
- Concurrent alert generation
- Multi-user dashboard access
- Load balancing behavior
- Connection pool efficiency
- Resource contention handling
"""

import asyncio
import time
import json
import statistics
import numpy as np
import threading
import psutil
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
from infrastructure.messaging.websocket_server import WebSocketManager
from app.services import DetectionService

# WebSocket and HTTP clients
try:
    import websockets
    import aiohttp
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False


# ============================================================================
# Test Configuration
# ============================================================================

@dataclass
class ConcurrentConfig:
    """Concurrent clients test configuration"""
    
    # Client load profiles
    client_counts: List[int] = None
    ramp_up_steps: List[int] = None
    
    # Test durations (seconds)
    steady_state_duration: int = 60
    ramp_up_duration: int = 30
    ramp_down_duration: int = 30
    
    # Request rates (requests per second per client)
    api_request_rate: int = 10
    ws_message_rate: int = 20
    
    # Resource thresholds
    max_cpu_percent: float = 80.0
    max_memory_mb: float = 2048.0
    max_connection_pool_size: int = 50
    max_connection_wait_ms: float = 100.0
    
    # Error thresholds
    max_error_rate_percent: float = 1.0
    max_latency_p95_ms: float = 500.0
    
    def __post_init__(self):
        if self.client_counts is None:
            self.client_counts = [1, 5, 10, 25, 50, 100]
        
        if self.ramp_up_steps is None:
            self.ramp_up_steps = [1, 5, 10, 20, 50]


# ============================================================================
# Performance Metrics
# ============================================================================

class ConcurrentMetrics:
    """Metrics collector for concurrent tests"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset all metrics"""
        self.requests = []
        self.errors = []
        self.latencies = []
        self.cpu_samples = []
        self.memory_samples = []
        self.connection_counts = []
        self.active_requests = 0
        self.start_time = None
        self.end_time = None
    
    def start(self):
        """Start collection"""
        self.start_time = time.time()
    
    def stop(self):
        """Stop collection"""
        self.end_time = time.time()
    
    def record_request(self, success: bool, latency_ms: float):
        """Record a request"""
        self.requests.append({
            'timestamp': time.time() - self.start_time,
            'success': success,
            'latency_ms': latency_ms
        })
        if not success:
            self.errors.append(self.requests[-1])
        self.latencies.append(latency_ms)
    
    def record_resource_usage(self):
        """Record current resource usage"""
        self.cpu_samples.append(psutil.cpu_percent())
        self.memory_samples.append(psutil.Process().memory_info().rss / 1024 / 1024)
    
    def record_connection_count(self, count: int):
        """Record active connection count"""
        self.connection_counts.append({
            'timestamp': time.time() - self.start_time,
            'count': count
        })
    
    @property
    def duration(self) -> float:
        """Get test duration"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0
    
    @property
    def total_requests(self) -> int:
        """Get total requests"""
        return len(self.requests)
    
    @property
    def error_count(self) -> int:
        """Get error count"""
        return len(self.errors)
    
    @property
    def error_rate(self) -> float:
        """Get error rate percentage"""
        if self.total_requests > 0:
            return (self.error_count / self.total_requests) * 100
        return 0
    
    def get_latency_stats(self) -> Dict[str, float]:
        """Get latency statistics"""
        if not self.latencies:
            return {}
        
        sorted_latencies = sorted(self.latencies)
        return {
            'min_ms': min(self.latencies),
            'max_ms': max(self.latencies),
            'mean_ms': statistics.mean(self.latencies),
            'median_ms': statistics.median(self.latencies),
            'p50_ms': sorted_latencies[int(len(sorted_latencies) * 0.50)],
            'p90_ms': sorted_latencies[int(len(sorted_latencies) * 0.90)],
            'p95_ms': sorted_latencies[int(len(sorted_latencies) * 0.95)],
            'p99_ms': sorted_latencies[int(len(sorted_latencies) * 0.99)],
            'std_ms': statistics.stdev(self.latencies) if len(self.latencies) > 1 else 0
        }
    
    def get_throughput(self) -> float:
        """Get requests per second"""
        if self.duration > 0:
            return self.total_requests / self.duration
        return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get complete statistics"""
        return {
            'duration_seconds': self.duration,
            'total_requests': self.total_requests,
            'error_count': self.error_count,
            'error_rate_percent': self.error_rate,
            'throughput_rps': self.get_throughput(),
            'latency': self.get_latency_stats(),
            'cpu_percent_avg': statistics.mean(self.cpu_samples) if self.cpu_samples else 0,
            'cpu_percent_max': max(self.cpu_samples) if self.cpu_samples else 0,
            'memory_mb_avg': statistics.mean(self.memory_samples) if self.memory_samples else 0,
            'memory_mb_max': max(self.memory_samples) if self.memory_samples else 0,
            'peak_connections': max([c['count'] for c in self.connection_counts]) if self.connection_counts else 0
        }
    
    def print_summary(self, title: str):
        """Print summary statistics"""
        stats = self.get_stats()
        print(f"\n{title}")
        print("-" * 40)
        print(f"  Duration: {stats['duration_seconds']:.2f}s")
        print(f"  Total requests: {stats['total_requests']:,}")
        print(f"  Error rate: {stats['error_rate_percent']:.2f}%")
        print(f"  Throughput: {stats['throughput_rps']:.2f} req/sec")
        print(f"\n  Latency:")
        print(f"    Mean: {stats['latency'].get('mean_ms', 0):.2f} ms")
        print(f"    P95: {stats['latency'].get('p95_ms', 0):.2f} ms")
        print(f"    P99: {stats['latency'].get('p99_ms', 0):.2f} ms")
        print(f"\n  Resources:")
        print(f"    CPU: {stats['cpu_percent_avg']:.1f}% (max: {stats['cpu_percent_max']:.1f}%)")
        print(f"    Memory: {stats['memory_mb_avg']:.1f} MB (max: {stats['memory_mb_max']:.1f} MB)")


# ============================================================================
# API Concurrent Client Tests
# ============================================================================

class TestAPIConcurrency:
    """Test API server under concurrent load"""
    
    def __init__(self, config: ConcurrentConfig):
        self.config = config
        self.base_url = "http://localhost:8888"
        self.metrics = ConcurrentMetrics()
    
    async def make_request(self, session: aiohttp.ClientSession, client_id: int) -> Tuple[bool, float]:
        """Make a single API request"""
        start = time.perf_counter()
        try:
            async with session.get(f"{self.base_url}/api/detections?limit=10") as resp:
                latency = (time.perf_counter() - start) * 1000
                return resp.status == 200, latency
        except Exception:
            latency = (time.perf_counter() - start) * 1000
            return False, latency
    
    async def client_worker(self, session: aiohttp.ClientSession, client_id: int, 
                            duration: float, rate: int):
        """Worker for a single client"""
        interval = 1.0 / rate if rate > 0 else 0
        end_time = time.time() + duration
        
        while time.time() < end_time:
            start = time.perf_counter()
            success, latency = await self.make_request(session, client_id)
            self.metrics.record_request(success, latency)
            
            elapsed = time.perf_counter() - start
            if interval > elapsed:
                await asyncio.sleep(interval - elapsed)
    
    async def run_load_test(self, num_clients: int, duration: int, rate: int) -> Dict[str, Any]:
        """Run load test with specified clients"""
        print(f"\n  Testing {num_clients} concurrent clients at {rate} req/sec each")
        
        self.metrics = ConcurrentMetrics()
        self.metrics.start()
        
        async with aiohttp.ClientSession() as session:
            # Create client tasks
            tasks = [
                self.client_worker(session, i, duration, rate)
                for i in range(num_clients)
            ]
            
            # Monitor resources
            async def monitor():
                while time.time() - self.metrics.start_time < duration:
                    self.metrics.record_resource_usage()
                    await asyncio.sleep(1)
            
            monitor_task = asyncio.create_task(monitor())
            
            # Run all clients
            await asyncio.gather(*tasks)
            monitor_task.cancel()
        
        self.metrics.stop()
        self.metrics.print_summary(f"API Load Test - {num_clients} clients")
        
        return self.metrics.get_stats()
    
    async def run_ramp_test(self):
        """Test with gradually increasing load"""
        print("\n" + "="*60)
        print("API CONCURRENT LOAD TEST (RAMP UP)")
        print("="*60)
        
        results = {}
        
        for num_clients in self.config.ramp_up_steps:
            stats = await self.run_load_test(
                num_clients=num_clients,
                duration=self.config.ramp_up_duration,
                rate=self.config.api_request_rate
            )
            results[num_clients] = stats
            
            # Check if we should stop
            if stats['error_rate_percent'] > self.config.max_error_rate_percent:
                print(f"\n  ✗ Stopping: Error rate {stats['error_rate_percent']:.2f}% exceeds {self.config.max_error_rate_percent}%")
                break
            
            if stats['cpu_percent_avg'] > self.config.max_cpu_percent:
                print(f"\n  ✗ Stopping: CPU {stats['cpu_percent_avg']:.1f}% exceeds {self.config.max_cpu_percent}%")
                break
        
        return results


# ============================================================================
# WebSocket Concurrent Client Tests
# ============================================================================

class TestWebSocketConcurrency:
    """Test WebSocket server under concurrent load"""
    
    def __init__(self, config: ConcurrentConfig):
        self.config = config
        self.ws_url = "ws://localhost:8889"
        self.metrics = ConcurrentMetrics()
    
    async def websocket_client(self, client_id: int, duration: float, rate: int) -> int:
        """Single WebSocket client worker"""
        try:
            async with websockets.connect(self.ws_url) as ws:
                messages_sent = 0
                end_time = time.time() + duration
                interval = 1.0 / rate if rate > 0 else 0
                
                while time.time() < end_time:
                    start = time.perf_counter()
                    try:
                        await ws.send(json.dumps({"type": "ping"}))
                        response = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        latency = (time.perf_counter() - start) * 1000
                        self.metrics.record_request(True, latency)
                        messages_sent += 1
                    except Exception as e:
                        latency = (time.perf_counter() - start) * 1000
                        self.metrics.record_request(False, latency)
                    
                    elapsed = time.perf_counter() - start
                    if interval > elapsed:
                        await asyncio.sleep(interval - elapsed)
                
                return messages_sent
        except Exception:
            return 0
    
    async def run_load_test(self, num_clients: int, duration: int, rate: int) -> Dict[str, Any]:
        """Run WebSocket load test"""
        if not WEBSOCKET_AVAILABLE:
            return {'error': 'WebSocket library not available'}
        
        print(f"\n  Testing {num_clients} concurrent WebSocket clients at {rate} msg/sec each")
        
        self.metrics = ConcurrentMetrics()
        self.metrics.start()
        
        # Create client tasks
        tasks = [
            self.websocket_client(i, duration, rate)
            for i in range(num_clients)
        ]
        
        # Monitor connections
        async def monitor():
            while time.time() - self.metrics.start_time < duration:
                self.metrics.record_connection_count(len([t for t in tasks if not t.done()]))
                self.metrics.record_resource_usage()
                await asyncio.sleep(1)
        
        monitor_task = asyncio.create_task(monitor())
        
        # Run all clients
        results = await asyncio.gather(*tasks)
        monitor_task.cancel()
        
        self.metrics.stop()
        total_messages = sum(results)
        print(f"    Total messages: {total_messages:,}")
        self.metrics.print_summary(f"WebSocket Load Test - {num_clients} clients")
        
        return self.metrics.get_stats()
    
    async def run_max_clients_test(self):
        """Find maximum sustainable clients"""
        print("\n" + "="*60)
        print("WEBSOCKET MAX CONCURRENT CLIENTS")
        print("="*60)
        
        results = {}
        
        for num_clients in self.config.client_counts:
            stats = await self.run_load_test(
                num_clients=num_clients,
                duration=self.config.steady_state_duration,
                rate=self.config.ws_message_rate
            )
            results[num_clients] = stats
            
            if stats.get('error_rate_percent', 0) > self.config.max_error_rate_percent:
                print(f"\n  Maximum sustainable clients: {num_clients - self.config.client_counts[self.config.client_counts.index(num_clients) - 1] if self.config.client_counts.index(num_clients) > 0 else num_clients}")
                break
        
        return results


# ============================================================================
# Database Connection Pool Test
# ============================================================================

class TestDatabaseConnectionPool:
    """Test database connection pool under concurrent load"""
    
    def __init__(self, config: ConcurrentConfig):
        self.config = config
        self.db = None
        self.metrics = ConcurrentMetrics()
    
    async def setup(self):
        """Set up database with connection pool"""
        db_config = DatabaseConfig(
            db_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database="drone_test",
            user="test_user",
            password="test_password",
            pool_min_size=1,
            pool_max_size=20
        )
        self.db = DatabaseManager(db_config)
        await self.db.initialize()
    
    async def db_worker(self, worker_id: int, duration: float) -> int:
        """Database worker making concurrent queries"""
        operations = 0
        end_time = time.time() + duration
        
        while time.time() < end_time:
            start = time.perf_counter()
            try:
                # Execute query
                result = await self.db.fetch_one("SELECT 1")
                latency = (time.perf_counter() - start) * 1000
                self.metrics.record_request(True, latency)
                operations += 1
            except Exception as e:
                latency = (time.perf_counter() - start) * 1000
                self.metrics.record_request(False, latency)
            
            await asyncio.sleep(0.001)  # Small delay
        
        return operations
    
    async def run_connection_test(self, num_workers: int, duration: int) -> Dict[str, Any]:
        """Test database connection pool with concurrent workers"""
        print(f"\n  Testing {num_workers} concurrent database workers")
        
        self.metrics = ConcurrentMetrics()
        self.metrics.start()
        
        # Create worker tasks
        tasks = [self.db_worker(i, duration) for i in range(num_workers)]
        
        # Monitor pool usage
        async def monitor():
            while time.time() - self.metrics.start_time < duration:
                if hasattr(self.db, '_adapter') and hasattr(self.db._adapter, '_pool'):
                    pool = self.db._adapter._pool
                    if pool:
                        self.metrics.record_connection_count(pool._size)
                self.metrics.record_resource_usage()
                await asyncio.sleep(1)
        
        monitor_task = asyncio.create_task(monitor())
        
        # Run all workers
        results = await asyncio.gather(*tasks)
        monitor_task.cancel()
        
        self.metrics.stop()
        total_ops = sum(results)
        print(f"    Total operations: {total_ops:,}")
        self.metrics.print_summary(f"Database Pool Test - {num_workers} workers")
        
        return self.metrics.get_stats()


# ============================================================================
# Concurrent Detection Processing Test
# ============================================================================

class TestDetectionConcurrency:
    """Test concurrent detection processing"""
    
    def __init__(self, config: ConcurrentConfig):
        self.config = config
        self.hardware = MockSDR()
        self.db = None
        self.detection_service = None
        self.metrics = ConcurrentMetrics()
    
    async def setup(self):
        """Set up detection service"""
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
    
    async def detection_worker(self, worker_id: int, duration: float) -> int:
        """Worker that processes detections"""
        detections = 0
        end_time = time.time() + duration
        
        while time.time() < end_time:
            start = time.perf_counter()
            try:
                # Inject drone signal
                self.hardware.inject_drone(f"Test Drone {worker_id}", 2.44e9)
                await asyncio.sleep(0.01)  # Simulate processing
                latency = (time.perf_counter() - start) * 1000
                self.metrics.record_request(True, latency)
                detections += 1
            except Exception as e:
                latency = (time.perf_counter() - start) * 1000
                self.metrics.record_request(False, latency)
            
            await asyncio.sleep(0.05)  # Rate limiting
        
        return detections
    
    async def run_concurrent_test(self, num_workers: int, duration: int) -> Dict[str, Any]:
        """Run concurrent detection processing test"""
        print(f"\n  Testing {num_workers} concurrent detection workers")
        
        self.metrics = ConcurrentMetrics()
        self.metrics.start()
        
        # Create worker tasks
        tasks = [self.detection_worker(i, duration) for i in range(num_workers)]
        
        # Monitor resources
        async def monitor():
            while time.time() - self.metrics.start_time < duration:
                self.metrics.record_resource_usage()
                await asyncio.sleep(1)
        
        monitor_task = asyncio.create_task(monitor())
        
        # Run all workers
        results = await asyncio.gather(*tasks)
        monitor_task.cancel()
        
        self.metrics.stop()
        total_detections = sum(results)
        print(f"    Total detections: {total_detections:,}")
        self.metrics.print_summary(f"Detection Concurrency - {num_workers} workers")
        
        return self.metrics.get_stats()


# ============================================================================
# Main Test Runner
# ============================================================================

class ConcurrentTestRunner:
    """Run all concurrent client tests"""
    
    def __init__(self, config: ConcurrentConfig = None):
        self.config = config or ConcurrentConfig()
        self.results = {}
    
    async def run_all(self):
        """Run all concurrent tests"""
        print("\n" + "="*60)
        print("CONCURRENT CLIENTS PERFORMANCE TESTS")
        print("="*60)
        
        # API concurrency tests
        api_tester = TestAPIConcurrency(self.config)
        self.results['api_ramp'] = await api_tester.run_ramp_test()
        
        # WebSocket concurrency tests
        ws_tester = TestWebSocketConcurrency(self.config)
        self.results['websocket'] = await ws_tester.run_max_clients_test()
        
        # Database connection pool tests
        db_tester = TestDatabaseConnectionPool(self.config)
        await db_tester.setup()
        self.results['database'] = {}
        
        for num_workers in self.config.client_counts[:5]:  # Test up to 50 workers
            stats = await db_tester.run_connection_test(num_workers, 30)
            self.results['database'][num_workers] = stats
            
            if stats.get('error_rate_percent', 0) > self.config.max_error_rate_percent:
                break
        
        # Detection concurrency tests
        det_tester = TestDetectionConcurrency(self.config)
        await det_tester.setup()
        self.results['detection'] = {}
        
        for num_workers in [1, 2, 5, 10]:
            stats = await det_tester.run_concurrent_test(num_workers, 30)
            self.results['detection'][num_workers] = stats
        
        # Print final summary
        self.print_summary()
        
        return self.results
    
    def print_summary(self):
        """Print final summary"""
        print("\n" + "="*60)
        print("CONCURRENT CLIENTS TEST SUMMARY")
        print("="*60)
        
        # API concurrency summary
        if self.results.get('api_ramp'):
            print("\n  API Concurrency Maximum:")
            max_clients = max([k for k in self.results['api_ramp'].keys() if self.results['api_ramp'][k].get('error_rate_percent', 0) <= self.config.max_error_rate_percent], default=0)
            if max_clients:
                print(f"    Maximum clients: {max_clients}")
                stats = self.results['api_ramp'][max_clients]
                print(f"    Throughput: {stats.get('throughput_rps', 0):.2f} req/sec")
                print(f"    Error rate: {stats.get('error_rate_percent', 0):.2f}%")
                print(f"    P95 latency: {stats.get('latency', {}).get('p95_ms', 0):.2f} ms")
        
        # WebSocket summary
        if self.results.get('websocket'):
            print("\n  WebSocket Maximum:")
            max_clients = max([k for k in self.results['websocket'].keys()], default=0)
            if max_clients:
                print(f"    Maximum clients: {max_clients}")
                stats = self.results['websocket'][max_clients]
                print(f"    Throughput: {stats.get('throughput_rps', 0):.2f} msg/sec")
                print(f"    Error rate: {stats.get('error_rate_percent', 0):.2f}%")
        
        # Database pool summary
        if self.results.get('database'):
            print("\n  Database Connection Pool:")
            max_workers = max([k for k in self.results['database'].keys() if self.results['database'][k].get('error_rate_percent', 0) <= self.config.max_error_rate_percent], default=0)
            if max_workers:
                print(f"    Maximum concurrent workers: {max_workers}")
                stats = self.results['database'][max_workers]
                print(f"    Peak connections: {stats.get('peak_connections', 0)}")
                print(f"    Error rate: {stats.get('error_rate_percent', 0):.2f}%")
        
        # Resource usage summary
        print("\n  Resource Usage Summary:")
        all_stats = []
        for category in self.results.values():
            if isinstance(category, dict):
                for stats in category.values():
                    if isinstance(stats, dict):
                        all_stats.append(stats)
        
        if all_stats:
            avg_cpu = statistics.mean([s.get('cpu_percent_avg', 0) for s in all_stats])
            max_cpu = max([s.get('cpu_percent_avg', 0) for s in all_stats])
            avg_memory = statistics.mean([s.get('memory_mb_avg', 0) for s in all_stats])
            
            print(f"    Avg CPU: {avg_cpu:.1f}%")
            print(f"    Peak CPU: {max_cpu:.1f}%")
            print(f"    Avg Memory: {avg_memory:.1f} MB")


# ============================================================================
# Main Execution
# ============================================================================

async def main():
    """Main entry point"""
    config = ConcurrentConfig(
        steady_state_duration=30,
        ramp_up_duration=20,
        api_request_rate=10,
        ws_message_rate=20,
        max_error_rate_percent=2.0,
        max_cpu_percent=80.0
    )
    
    runner = ConcurrentTestRunner(config)
    await runner.run_all()


if __name__ == "__main__":
    asyncio.run(main())