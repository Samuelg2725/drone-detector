#!/usr/bin/env python3
"""
Drone Detector Test Suite

This package contains comprehensive tests for the drone detection system.

Test Structure:
- unit/           : Unit tests for individual components (fast, isolated)
- integration/    : Integration tests for component interactions
- hardware/       : Hardware-specific tests (requires SDR hardware)
- performance/    : Performance and load testing
- e2e/            : End-to-end system tests

Test Categories:
- Domain Logic   : Signal processing, detection algorithms, threat assessment
- Infrastructure : Database, messaging, hardware abstraction
- Application    : Services, pipelines, workers
- API Layer      : REST endpoints, WebSocket connections
- UI Layer       : Dashboard functionality (when applicable)

Usage:
    # Run all tests
    pytest
    
    # Run specific test category
    pytest tests/unit/
    pytest tests/integration/
    
    # Run with custom markers
    pytest -m "not slow"
    pytest -m "integration"
    
    # Run with coverage
    pytest --cov=app --cov=domain --cov=infrastructure
    
    # Run in parallel
    pytest -n auto
"""

# Test package version
__version__ = '1.0.0'

# Package metadata
__all__ = [
    # No exports - test packages should be imported directly
]

# Test configuration constants
TEST_DATA_DIR = "test_data"
FIXTURES_DIR = "fixtures"
MOCK_DATA_DIR = "mock_data"

# Test timeouts (seconds)
UNIT_TEST_TIMEOUT = 5
INTEGRATION_TEST_TIMEOUT = 30
HARDWARE_TEST_TIMEOUT = 60
PERFORMANCE_TEST_TIMEOUT = 300
E2E_TEST_TIMEOUT = 120

# Test coverage thresholds
MIN_COVERAGE = 80  # percent
MIN_BRANCH_COVERAGE = 70  # percent

# Skip conditions
SKIP_HARDWARE_TESTS = False  # Set to True to skip hardware tests
SKIP_SLOW_TESTS = False  # Set to True to skip slow tests
SKIP_PERFORMANCE_TESTS = False  # Set to True to skip performance tests