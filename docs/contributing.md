# Contributing to Drone Detector

Thank you for your interest in contributing to the Drone Detector project! This document provides guidelines and instructions for contributing to this open-source project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation Guidelines](#documentation-guidelines)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)
- [Feature Requests](#feature-requests)
- [Community](#community)

## Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

### Our Pledge

We pledge to make participation in our project a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity and expression, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

## Getting Started

### Prerequisites

```bash
# Required software
- Python 3.11+
- Git 2.40+
- Docker 24.0+ (optional)
- Make 4.0+

# Development tools
- VS Code / PyCharm (recommended)
- pre-commit (for git hooks)
- pytest (for testing)
Initial Setup
bash
# 1. Fork the repository on GitHub
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/drone-detector.git
cd drone-detector

# 3. Add upstream remote
git remote add upstream https://github.com/drone-detector/drone-detector.git

# 4. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 5. Install development dependencies
pip install -r requirements-dev.txt
pip install -e .

# 6. Install pre-commit hooks
pre-commit install

# 7. Run tests to verify setup
pytest tests/ -v
Development Environment Setup
bash
# Option 1: Local development
export USE_MOCK_HARDWARE=true
python run.py --mock

# Option 2: Docker development
docker-compose -f docker-compose.dev.yml up

# Option 3: VS Code Dev Container
# Open in VS Code and click "Reopen in Container"
Development Workflow
Branch Naming Convention
text
feature/    - New features (feature/drone-tracking)
bugfix/     - Bug fixes (bugfix/fft-crash)
docs/       - Documentation (docs/api-update)
test/       - Testing (test/unit-coverage)
refactor/   - Code refactoring (refactor/signal-chain)
perf/       - Performance improvements (perf/fft-optimization)
hotfix/     - Critical fixes (hotfix/security-patch)
Commit Message Format
We follow Conventional Commits:

text
<type>(<scope>): <subject>

<body>

<footer>
Types:

feat: New feature

fix: Bug fix

docs: Documentation

style: Code style (formatting, missing semicolons)

refactor: Code refactoring

perf: Performance improvement

test: Adding/updating tests

chore: Maintenance tasks

ci: CI/CD changes

Examples:

text
feat(detection): add peak detection algorithm

Implement new peak detection using adaptive thresholding.
Includes unit tests and performance benchmarks.

Closes #123
text
fix(hardware): resolve HackRF buffer overflow

Increase buffer size and add overflow handling.
Fixes intermittent data loss in high bandwidth mode.
Development Steps
bash
# 1. Create feature branch
git checkout -b feature/your-feature-name

# 2. Make changes and commit
git add .
git commit -m "feat(scope): description"

# 3. Keep branch updated
git fetch upstream
git rebase upstream/main

# 4. Run tests locally
pytest tests/ -v --cov=app

# 5. Push to your fork
git push origin feature/your-feature-name

# 6. Create Pull Request
Coding Standards
Python Style Guide
We follow PEP 8 with additional guidelines:

python
# Imports
# Standard library imports
import asyncio
from datetime import datetime
from typing import List, Optional, Dict

# Third-party imports
import numpy as np
from fastapi import FastAPI

# Local imports
from domain.entities import DetectionEvent
from infrastructure.hardware import MockSDR

# Class naming: PascalCase
class SignalProcessor:
    """Docstring with description and examples."""
    
    # Constants: UPPER_SNAKE_CASE
    DEFAULT_SAMPLE_RATE = 2_000_000
    
    def __init__(self, sample_rate: float):
        """Initialize with parameters.
        
        Args:
            sample_rate: Sampling rate in Hz
        """
        self.sample_rate = sample_rate
        self._private_attr = None
    
    # Methods: snake_case
    def calculate_psd(self, samples: np.ndarray) -> np.ndarray:
        """Calculate Power Spectral Density.
        
        Args:
            samples: IQ samples array
            
        Returns:
            PSD array in dBm/Hz
            
        Raises:
            ValueError: If samples array is empty
        """
        if len(samples) == 0:
            raise ValueError("Empty samples array")
        
        # Implementation
        return psd

# Function naming: snake_case
def process_detection(event: DetectionEvent) -> None:
    """Process detection event."""
    pass

# Type hints are mandatory
def calculate_snr(signal_power: float, noise_power: float) -> float:
    """Calculate signal-to-noise ratio."""
    return 10 * np.log10(signal_power / noise_power)
Code Formatting
We use automated formatters to ensure consistency:

bash
# Format code
black app/ tests/

# Sort imports
isort app/ tests/

# Check style
flake8 app/ tests/
pylint app/

# Type checking
mypy app/
Pre-commit Hooks
Configured hooks run automatically on commit:

yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
      
  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: ["--profile", "black"]
        
  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: ["--max-line-length=100"]
Documentation Strings
python
def complex_function(param1: int, param2: str) -> bool:
    """One-line summary.
    
    Extended description with multiple lines explaining
    the function's purpose, algorithm, and any important
    implementation details.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When invalid input is provided
        RuntimeError: When processing fails
        
    Example:
        >>> result = complex_function(42, "test")
        >>> print(result)
        True
        
    Note:
        Additional notes about usage or limitations
    """
    pass
Testing Guidelines
Test Structure
text
tests/
├── unit/           # Unit tests (fast, isolated)
│   ├── domain/
│   ├── infrastructure/
│   └── app/
├── integration/    # Integration tests (slow, external deps)
├── performance/    # Performance and load tests
├── hardware/       # Hardware-specific tests
└── e2e/            # End-to-end tests
Writing Tests
python
# tests/unit/test_signal_processing.py
import pytest
import numpy as np
from domain.services.signal_processor import SignalProcessor

class TestSignalProcessor:
    """Test suite for SignalProcessor."""
    
    @pytest.fixture
    def processor(self):
        """Create processor instance for testing."""
        return SignalProcessor(sample_rate=2e6)
    
    @pytest.fixture
    def sample_iq(self):
        """Generate test IQ data."""
        # Generate sine wave
        t = np.arange(1024) / 2e6
        iq = np.exp(1j * 2 * np.pi * 100e3 * t)
        return iq
    
    def test_psd_calculation(self, processor, sample_iq):
        """Test PSD calculation produces expected shape."""
        psd = processor.calculate_psd(sample_iq)
        
        # Assertions
        assert psd is not None
        assert len(psd) == len(sample_iq) // 2 + 1
        assert np.all(np.isfinite(psd))
    
    @pytest.mark.parametrize("sample_rate,expected_length", [
        (1e6, 513),
        (2e6, 1025),
        (5e6, 2561),
    ])
    def test_psd_length(self, processor, sample_rate, expected_length):
        """Test PSD length matches expected."""
        processor.sample_rate = sample_rate
        samples = np.random.randn(1024) + 1j * np.random.randn(1024)
        psd = processor.calculate_psd(samples)
        
        assert len(psd) == expected_length
    
    def test_empty_input(self, processor):
        """Test empty input raises ValueError."""
        with pytest.raises(ValueError, match="Empty samples"):
            processor.calculate_psd(np.array([]))
    
    @pytest.mark.slow
    def test_long_signal_processing(self, processor):
        """Test processing of long signals (performance)."""
        samples = np.random.randn(1_000_000) + 1j * np.random.randn(1_000_000)
        
        import time
        start = time.time()
        psd = processor.calculate_psd(samples)
        duration = time.time() - start
        
        assert duration < 1.0  # Should process in < 1 second
        assert len(psd) > 0
Test Coverage
bash
# Run with coverage
pytest tests/ --cov=app --cov=domain --cov=infrastructure --cov-report=html

# Coverage thresholds
COVERAGE_THRESHOLD = 80  # Minimum 80% coverage

# Check coverage
pytest --cov --cov-fail-under=80
Mocking Hardware
python
# tests/conftest.py
@pytest.fixture
def mock_sdr():
    """Mock SDR hardware for testing."""
    from infrastructure.hardware.mock_hardware import MockSDR
    
    sdr = MockSDR()
    sdr.initialize({
        'sample_rate': 2e6,
        'center_frequency': 2.45e9,
        'gain': 20
    })
    return sdr

# Use in tests
def test_detection_pipeline(mock_sdr):
    """Test detection with mock hardware."""
    # Inject test signal
    mock_sdr.inject_drone("Test Drone", 2.45e9)
    
    # Process
    detection = process_signal(mock_sdr)
    
    assert detection is not None
    assert detection.confidence > 0.5
Documentation Guidelines
Code Documentation
python
# Module docstring
"""Module description.

This module handles signal processing for drone detection,
including FFT, PSD, and peak detection algorithms.

Author: Jane Doe
Date: 2024-01-01
"""

# Class docstring
class SignalProcessor:
    """Signal processing core.
    
    This class provides methods for processing IQ samples
    into detection events.
    
    Attributes:
        sample_rate: Sampling rate in Hz
        fft_size: FFT size for transformations
    """
    
    def method_docstring(self):
        """Method description.
        
        This method does X, Y, and Z using algorithm Q.
        
        Returns:
            Description of return value
            
        Example:
            >>> processor = SignalProcessor()
            >>> result = processor.method()
        """
        pass
README Updates
When adding features, update relevant documentation:

markdown
## New Feature Documentation

For new features, add to appropriate documentation:
- API endpoints → `docs/api_reference.md`
- Configuration → `docs/configuration.md`
- Hardware → `docs/hardware_setup.md`
- Signal processing → `docs/signal_chain.md`
- User guide → `README.md`
Writing Examples
python
# examples/new_feature_example.py
"""Example: Using the new detection feature.

This example demonstrates how to use the new peak detection
algorithm for improved drone detection.

Prerequisites:
    - Drone Detector installed
    - Python 3.11+
    - SDR hardware (or mock mode)
"""

import asyncio
from drone_detector import DroneDetector

async def main():
    # Initialize detector
    detector = DroneDetector(mode="mock")
    
    # Configure detection
    detector.configure({
        "peak_threshold": 15,
        "min_confidence": 0.8
    })
    
    # Start detection
    async for detection in detector.stream_detections():
        print(f"Detected: {detection}")

if __name__ == "__main__":
    asyncio.run(main())
Pull Request Process
PR Checklist
Before submitting a Pull Request:

Fork the repository and create feature branch

Write/update tests for new functionality

Ensure all tests pass (pytest tests/)

Update documentation for new features

Run code formatters (black . && isort .)

Run linters (flake8 && pylint)

Run type checker (mypy app/)

Add examples for new features

Update CHANGELOG.md

PR Template
markdown
## Description

Please include a summary of the change and which issue is fixed.
Include relevant motivation and context.

Fixes # (issue)

## Type of change

- [ ] Bug fix (non-breaking change)
- [ ] New feature (non-breaking change)
- [ ] Breaking change (fix or feature that breaks existing API)
- [ ] Documentation update

## How Has This Been Tested?

- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Checklist:

- [ ] My code follows the style guidelines of this project
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective
- [ ] New and existing unit tests pass locally
- [ ] Any dependent changes have been merged

## Additional context

Add any other context about the pull request here.
PR Review Process
CI Checks: All automated checks must pass

Code Review: At least one maintainer approval required

Testing: Reviewer should verify functionality

Documentation: Ensure docs are updated

Merge: Maintainer merges after approval

Issue Reporting
Bug Report Template
markdown
**Describe the bug**
A clear description of the bug.

**To Reproduce**
Steps to reproduce the behavior:
1. Run command '...'
2. See error

**Expected behavior**
What you expected to happen.

**Screenshots/Logs**
If applicable, add screenshots or logs.

**Environment:**
 - OS: [e.g., Ubuntu 22.04]
 - Python version: [e.g., 3.11.5]
 - SDR hardware: [e.g., HackRF One]
 - Version: [e.g., 1.0.0]

**Additional context**
Add any other context about the problem.
Bug Triage
Maintainers will classify bugs by:

Priority:

Critical: System crash, data loss

High: Major feature broken

Medium: Feature partially broken

Low: Minor issue, documentation

Labels:

bug, enhancement, documentation

hardware-* (hardware-specific)

good-first-issue (for new contributors)

Feature Requests
Feature Request Template
markdown
**Is your feature request related to a problem?**
Clear description of the problem.

**Describe the solution you'd like**
What you want to happen.

**Describe alternatives you've considered**
Any alternative solutions.

**Additional context**
Screenshots, diagrams, or references.

**Implementation ideas**
(Optional) How you might implement this.
Feature Development Process
Discussion: Open issue for discussion

Design: Document design and get feedback

Implementation: Write code with tests

Review: PR review process

Release: Merge and release

Community
Communication Channels
GitHub Issues: Bug reports and feature requests

GitHub Discussions: Q&A and general discussion

Discord: Real-time chat

Mailing List: Announcements

Recognition
Contributors will be recognized in:

CONTRIBUTORS.md: List of all contributors

Release Notes: Named in release announcements

Hall of Fame: Top contributors

First-time Contributors
Look for issues labeled good-first-issue or help-wanted.

Recommended first contributions:

Fix documentation typos

Add unit tests

Improve error messages

Add examples

Bug fixes (small scope)

Code Review Guidelines
For reviewers:

Be respectful and constructive

Focus on code, not the person

Explain reasoning behind suggestions

Approve when ready, don't nitpick

For contributors:

Respond to comments promptly

Ask for clarification if needed

Don't take criticism personally

Iterate and improve

Release Process
Version Numbering
We follow Semantic Versioning:

MAJOR: Incompatible API changes

MINOR: Backwards-compatible new features

PATCH: Backwards-compatible bug fixes

Release Schedule
Patch releases: As needed (bug fixes)

Minor releases: Monthly (features)

Major releases: Annually (breaking changes)

Release Checklist
markdown
- [ ] Update CHANGELOG.md
- [ ] Update version in pyproject.toml
- [ ] Run full test suite
- [ ] Update documentation
- [ ] Create release branch
- [ ] Create GitHub release
- [ ] Build and publish to PyPI
- [ ] Update Docker images
- [ ] Announce release
Additional Resources
Project Documentation

API Reference

Developer Guide

Code of Conduct

Security Policy
