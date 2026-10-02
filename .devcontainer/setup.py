#!/usr/bin/env python3
"""
Setup script for Drone Detector System

This script installs the drone detector package and its dependencies.
"""

import os
import sys
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
from pathlib import Path

# ============================================================================
# Version Management
# ============================================================================

def get_version():
    """Get version from version file or git tag"""
    version_file = Path(__file__).parent / "VERSION"
    
    if version_file.exists():
        # Read from VERSION file
        with open(version_file, 'r') as f:
            version = f.read().strip()
            return version
    
    # Try to get from git tag
    try:
        import subprocess
        git_tag = subprocess.check_output(
            ['git', 'describe', '--tags', '--abbrev=0'],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        
        if git_tag.startswith('v'):
            git_tag = git_tag[1:]
        return git_tag
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Default version
    return "1.0.0"

# ============================================================================
# Read Requirements
# ============================================================================

def read_requirements(filename):
    """Read requirements from requirements.txt"""
    requirements = []
    req_file = Path(__file__).parent / filename
    
    if req_file.exists():
        with open(req_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith('#'):
                    # Handle git+https requirements
                    if line.startswith('git+'):
                        # Extract package name from git URL
                        if '#egg=' in line:
                            egg = line.split('#egg=')[1]
                            requirements.append(egg)
                    else:
                        requirements.append(line)
    
    return requirements

def read_long_description():
    """Read long description from README.md"""
    readme = Path(__file__).parent / "README.md"
    if readme.exists():
        with open(readme, 'r', encoding='utf-8') as f:
            return f.read()
    return "Drone Detection System using Software Defined Radio"

# ============================================================================
# Custom Test Command
# ============================================================================

class PyTest(TestCommand):
    """Custom test command to run pytest"""
    
    user_options = [('pytest-args=', 'a', "Arguments to pass to pytest")]
    
    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = []
    
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True
    
    def run_tests(self):
        import pytest
        errno = pytest.main(self.pytest_args)
        sys.exit(errno)

# ============================================================================
# Package Data
# ============================================================================

def get_package_data():
    """Get package data files to include"""
    package_data = {
        'drone_detector': [
            'py.typed',
            'version.py',
        ],
        'drone_detector.config': [
            '*.yaml',
            '*.json',
            '*.yml',
        ],
        'drone_detector.models': [
            '*.pkl',
            '*.joblib',
        ],
        'drone_detector.ui': [
            '*.html',
            '*.css',
            '*.js',
            '*.svg',
            '*.png',
            '*.ico',
            '*.woff2',
            '*.mp3',
            '*.wav',
        ],
        'drone_detector.docs': [
            '*.md',
            '*.rst',
            '*.txt',
        ],
    }
    
    return package_data

# ============================================================================
# Extension Modules (Cython/C extensions)
# ============================================================================

ext_modules = []

try:
    from Cython.Build import cythonize
    from Cython.Distutils import build_ext
    
    # Check if we should build C extensions
    if os.environ.get('BUILD_EXTENSIONS', 'true').lower() == 'true':
        # Signal processing optimizations
        extensions = [
            # FFT optimizations
            Extension(
                'drone_detector.core.fft_optimized',
                ['drone_detector/core/fft_optimized.pyx'],
                extra_compile_args=['-O3', '-march=native', '-ffast-math'],
                libraries=['fftw3', 'fftw3f'],
            ),
            # Peak detection
            Extension(
                'drone_detector.core.peak_detection',
                ['drone_detector/core/peak_detection.pyx'],
                extra_compile_args=['-O3', '-march=native'],
            ),
            # IQ processing
            Extension(
                'drone_detector.core.iq_processing',
                ['drone_detector/core/iq_processing.pyx'],
                extra_compile_args=['-O3', '-march=native', '-ffast-math'],
            ),
        ]
        
        ext_modules = cythonize(
            extensions,
            compiler_directives={
                'language_level': 3,
                'boundscheck': False,
                'wraparound': False,
                'initializedcheck': False,
                'nonecheck': False,
            }
        )
except ImportError:
    # Cython not available, skip building extensions
    pass

# ============================================================================
# Setup Configuration
# ============================================================================

setup(
    # Basic information
    name="drone-detector",
    version=get_version(),
    author="Drone Detector Team",
    author_email="dev@drone-detector.com",
    description="Advanced Drone Detection System using Software Defined Radio",
    long_description=read_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/drone-detector/drone-detector",
    
    # License
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Telecommunications Industry",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering",
        "Topic :: Communications :: Ham Radio",
        "Topic :: Security",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS :: MacOS X",
    ],
    
    # Package discovery
    packages=find_packages(
        exclude=[
            "tests",
            "tests.*",
            "examples",
            "examples.*",
            "docs",
            "docs.*",
            "scripts",
            "scripts.*",
            "notebooks",
            "notebooks.*",
        ]
    ),
    
    # Package data
    package_data=get_package_data(),
    include_package_data=True,
    
    # Dependencies
    python_requires=">=3.11",
    install_requires=read_requirements("requirements.txt"),
    extras_require={
        'dev': read_requirements("requirements-dev.txt"),
        'gpu': [
            'tensorflow>=2.13.0',
            'torch>=2.0.0',
            'cupy-cuda12x>=12.0.0',
        ],
        'sdr': [
            'pyhackrf>=0.1.0',
            'pyrtlsdr>=0.3.0',
            'pyadi-iio>=0.0.12',
        ],
        'ml': [
            'scikit-learn>=1.3.0',
            'xgboost>=1.7.0',
            'lightgbm>=4.0.0',
        ],
        'signal': [
            'scipy>=1.11.0',
            'numpy>=1.24.0',
            'pyfftw>=0.13.0',
        ],
        'api': [
            'fastapi>=0.100.0',
            'uvicorn[standard]>=0.23.0',
            'websockets>=11.0.0',
        ],
        'database': [
            'asyncpg>=0.29.0',
            'psycopg2-binary>=2.9.0',
            'sqlalchemy>=2.0.0',
            'alembic>=1.12.0',
            'redis>=5.0.0',
        ],
        'monitoring': [
            'prometheus-client>=0.17.0',
            'grafana-api>=1.0.0',
        ],
        'cloud': [
            'boto3>=1.28.0',
            'google-cloud-storage>=2.10.0',
            'azure-storage-blob>=12.18.0',
        ],
        'all': [
            # This will be populated by combining all extras
        ],
    },
    
    # Entry points
    entry_points={
        'console_scripts': [
            'drone-detector=drone_detector.cli:main',
            'drone-api=drone_detector.api.cli:main',
            'drone-worker=drone_detector.workers.cli:main',
            'drone-train=drone_detector.ml.cli:train',
            'drone-test=drone_detector.testing.cli:main',
        ],
        'drone_detector.plugins': [
            'hackrf = drone_detector.hardware.hackrf:HackRFPlugin',
            'rtl_sdr = drone_detector.hardware.rtl_sdr:RTL_SDRPlugin',
            'pluto = drone_detector.hardware.pluto:PlutoPlugin',
        ],
        'pytest11': [
            'drone_detector = drone_detector.testing.pytest_plugin',
        ],
    },
    
    # Extension modules
    ext_modules=ext_modules,
    cmdclass={
        'build_ext': build_ext if ext_modules else None,
        'test': PyTest,
    },
    
    # Options
    zip_safe=False,
    test_suite="tests",
    tests_require=[
        "pytest>=7.4.0",
        "pytest-cov>=4.1.0",
        "pytest-asyncio>=0.21.0",
        "pytest-mock>=3.11.0",
        "pytest-timeout>=2.1.0",
    ],
    
    # Project URLs
    project_urls={
        "Documentation": "https://docs.drone-detector.com",
        "Source": "https://github.com/drone-detector/drone-detector",
        "Tracker": "https://github.com/drone-detector/drone-detector/issues",
        "Changelog": "https://github.com/drone-detector/drone-detector/releases",
        "Discord": "https://discord.gg/drone-detector",
    },
)

# ============================================================================
# Post-installation hook (optional)
# ============================================================================

if __name__ == "__main__":
    # This code runs after successful installation
    print("\n" + "="*60)
    print("Drone Detector System installed successfully!")
    print("="*60)
    print("\nNext steps:")
    print("  1. Copy .env.example to .env and configure")
    print("  2. Run database migrations: python scripts/migrate.py upgrade head")
    print("  3. Start the API: drone-api")
    print("  4. Or run with docker: docker-compose up -d")
    print("\nFor development:")
    print("  pip install -e .[dev]")
    print("  pytest tests/")
    print("\nDocumentation: https://docs.drone-detector.com")
    print("Report issues: https://github.com/drone-detector/drone-detector/issues")
    print("="*60)