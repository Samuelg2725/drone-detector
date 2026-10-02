#!/usr/bin/env python3
"""
Performance Tests Package

This package contains performance and load testing modules for the drone detector system.

Test Categories:
- test_throughput: Data processing throughput tests
- test_latency: End-to-end latency measurements
- test_concurrent_clients: Concurrent client load testing

Performance Metrics:
- Requests per second (RPS)
- Latency percentiles (p50, p90, p95, p99)
- Resource utilization (CPU, memory)
- Connection pool efficiency
- Error rates under load
"""

from .test_concurrent_clients import (
    ConcurrentConfig,
    ConcurrentMetrics,
    ConcurrentTestRunner,
    TestAPIConcurrency,
    TestWebSocketConcurrency,
    TestDatabaseConnectionPool,
    TestDetectionConcurrency
)

__all__ = [
    # Main runner
    'ConcurrentTestRunner',
    
    # Configuration and metrics
    'ConcurrentConfig',
    'ConcurrentMetrics',
    
    # Individual test classes
    'TestAPIConcurrency',
    'TestWebSocketConcurrency',
    'TestDatabaseConnectionPool',
    'TestDetectionConcurrency',
]

# Package version
__version__ = '1.0.0'

# Test configuration defaults
DEFAULT_TEST_DURATION = 30  # seconds
DEFAULT_MAX_ERROR_RATE = 2.0  # percent
DEFAULT_MAX_CPU_PERCENT = 80.0