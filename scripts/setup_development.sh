#!/bin/bash
# ============================================================================
# Drone Detection System - Development Environment Setup Script
# Version: 2.0.0
# Description: Complete setup script for development environment
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo -e "${BLUE}"
    echo "═══════════════════════════════════════════════════════════════════════════════"
    echo "  $1"
    echo "═══════════════════════════════════════════════════════════════════════════════"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

print_step() {
    echo -e "${CYAN}📌 $1${NC}"
}

check_command() {
    if command -v $1 &> /dev/null; then
        print_success "$1 found: $(which $1)"
        return 0
    else
        print_warning "$1 not found"
        return 1
    fi
}

get_os() {
    case "$(uname -s)" in
        Darwin*)    echo "macos";;
        Linux*)     echo "linux";;
        *)          echo "unknown";;
    esac
}

# ============================================================================
# Main Setup Functions
# ============================================================================

setup_system_dependencies() {
    print_header "Installing System Dependencies"
    
    OS=$(get_os)
    
    if [ "$OS" == "linux" ]; then
        print_info "Detected Linux system"
        
        # Update package list
        sudo apt-get update
        
        # Install basic build tools
        sudo apt-get install -y \
            build-essential \
            cmake \
            git \
            wget \
            curl \
            vim \
            htop \
            net-tools
            
        # Install Python dependencies
        sudo apt-get install -y \
            python3 \
            python3-pip \
            python3-dev \
            python3-venv \
            python3-setuptools
            
        # Install SDR dependencies
        sudo apt-get install -y \
            libusb-1.0-0-dev \
            libfftw3-dev \
            libhackrf-dev \
            librtlsdr-dev \
            libvolk2-dev
            
        # Install database dependencies
        sudo apt-get install -y \
            sqlite3 \
            libsqlite3-dev
            
        # Install visualization dependencies
        sudo apt-get install -y \
            libfreetype6-dev \
            libpng-dev \
            libxft-dev
            
        print_success "Linux dependencies installed"
        
    elif [ "$OS" == "macos" ]; then
        print_info "Detected macOS system"
        
        # Check if Homebrew is installed
        if ! command -v brew &> /dev/null; then
            print_info "Installing Homebrew..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        
        # Install packages
        brew update
        brew install \
            python@3.9 \
            cmake \
            git \
            wget \
            hackrf \
            rtl-sdr \
            fftw \
            sqlite3
            
        print_success "macOS dependencies installed"
    else
        print_error "Unsupported operating system"
        exit 1
    fi
}

setup_python_environment() {
    print_header "Setting Up Python Environment"
    
    # Create virtual environment
    if [ ! -d "venv" ]; then
        print_info "Creating virtual environment..."
        python3 -m venv venv
        print_success "Virtual environment created"
    else
        print_info "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    print_info "Upgrading pip..."
    pip install --upgrade pip setuptools wheel
    
    # Install requirements
    print_info "Installing Python packages..."
    
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        print_success "Requirements installed"
    else
        print_warning "requirements.txt not found"
    fi
    
    if [ -f "requirements-dev.txt" ]; then
        pip install -r requirements-dev.txt
        print_success "Development requirements installed"
    fi
    
    # Install package in development mode
    if [ -f "setup.py" ]; then
        pip install -e .
        print_success "Package installed in development mode"
    fi
    
    print_success "Python environment ready"
}

setup_database() {
    print_header "Setting Up Database"
    
    # Create data directory
    mkdir -p data
    mkdir -p data/iq/live
    mkdir -p data/iq/replay
    mkdir -p data/iq/synthetic
    mkdir -p data/logs
    mkdir -p data/exports
    mkdir -p data/backups
    
    # Initialize database
    if [ ! -f "data/detections.db" ]; then
        print_info "Initializing database..."
        python -c "
import sqlite3
from pathlib import Path

# Create database directory
Path('data').mkdir(exist_ok=True)

# Connect to database (creates file)
conn = sqlite3.connect('data/detections.db')
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('PRAGMA synchronous=NORMAL')

# Create initial tables
conn.execute('''
    CREATE TABLE IF NOT EXISTS detections (
        id TEXT PRIMARY KEY,
        timestamp TIMESTAMP NOT NULL,
        drone_type TEXT,
        confidence REAL,
        threat_level TEXT,
        frequency REAL,
        latitude REAL,
        longitude REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

conn.execute('''
    CREATE TABLE IF NOT EXISTS alerts (
        id TEXT PRIMARY KEY,
        detection_id TEXT,
        severity TEXT NOT NULL,
        message TEXT,
        acknowledged BOOLEAN DEFAULT 0,
        timestamp TIMESTAMP NOT NULL
    )
''')

conn.commit()
conn.close()
print('Database initialized successfully')
"
        print_success "Database initialized"
    else
        print_info "Database already exists"
    fi
}

setup_configuration() {
    print_header "Setting Up Configuration"
    
    # Create config directory
    mkdir -p config
    
    # Copy example config files if they don't exist
    if [ ! -f "config/system.yaml" ] && [ -f "config/system.yaml.example" ]; then
        cp config/system.yaml.example config/system.yaml
        print_success "Created config/system.yaml"
    fi
    
    if [ ! -f "config/hardware.yaml" ] && [ -f "config/hardware.yaml.example" ]; then
        cp config/hardware.yaml.example config/hardware.yaml
        print_success "Created config/hardware.yaml"
    fi
    
    if [ ! -f "config/logging.yaml" ] && [ -f "config/logging.yaml.example" ]; then
        cp config/logging.yaml.example config/logging.yaml
        print_success "Created config/logging.yaml"
    fi
    
    # Create .env file if it doesn't exist
    if [ ! -f ".env" ] && [ -f ".env.example" ]; then
        cp .env.example .env
        print_success "Created .env file"
        print_warning "Please update .env with your configuration"
    fi
    
    print_success "Configuration files ready"
}

setup_git_hooks() {
    print_header "Setting Up Git Hooks"
    
    # Setup pre-commit hooks
    if command -v pre-commit &> /dev/null; then
        print_info "Installing pre-commit hooks..."
        pre-commit install
        print_success "Pre-commit hooks installed"
    else
        print_warning "pre-commit not installed. Skipping hooks setup."
    fi
}

setup_mock_data() {
    print_header "Setting Up Mock Test Data"
    
    read -p "Generate mock test data? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Generating mock IQ data..."
        
        # Create mock data directory
        mkdir -p data/iq/mock
        
        # Generate mock data using Python
        python -c "
import numpy as np
from pathlib import Path
import json
from datetime import datetime

def generate_mock_iq(duration=10, sample_rate=10e6):
    samples = int(sample_rate * duration)
    # Generate synthetic IQ data
    t = np.arange(samples) / sample_rate
    # Simulate a signal
    signal = np.exp(1j * 2 * np.pi * 1e6 * t)
    noise = 0.1 * (np.random.randn(samples) + 1j * np.random.randn(samples))
    iq_data = signal + noise
    return iq_data.astype(np.complex64)

# Generate test files
output_dir = Path('data/iq/mock')
output_dir.mkdir(parents=True, exist_ok=True)

# DJI Mavic 2.4 GHz mock data
iq_data = generate_mock_iq(10)
iq_data.tofile(output_dir / 'dji_mavic_2.4g.iq')
metadata = {
    'drone_type': 'DJI Mavic 3',
    'frequency': 2.44e9,
    'sample_rate': 10e6,
    'duration': 10,
    'description': 'Mock DJI Mavic signal for testing'
}
with open(output_dir / 'dji_mavic_2.4g.json', 'w') as f:
    json.dump(metadata, f, indent=2)

# FPV Analog mock data
iq_data = generate_mock_iq(10)
iq_data.tofile(output_dir / 'fpv_analog_5.8g.iq')
metadata['drone_type'] = 'FPV Analog'
metadata['frequency'] = 5.8e9
with open(output_dir / 'fpv_analog_5.8g.json', 'w') as f:
    json.dump(metadata, f, indent=2)

# Noise floor mock data
iq_data = 0.05 * (np.random.randn(10*10**6) + 1j * np.random.randn(10*10**6))
iq_data = iq_data.astype(np.complex64)
iq_data.tofile(output_dir / 'noise_floor.iq')
metadata = {
    'type': 'noise',
    'sample_rate': 10e6,
    'duration': 10,
    'description': 'Background noise for testing'
}
with open(output_dir / 'noise_floor.json', 'w') as f:
    json.dump(metadata, f, indent=2)

print('Mock data generated successfully')
"
        print_success "Mock data generated"
    else
        print_info "Skipping mock data generation"
    fi
}

setup_udev_rules() {
    print_header "Setting Up udev Rules (Linux Only)"
    
    OS=$(get_os)
    
    if [ "$OS" == "linux" ]; then
        read -p "Setup udev rules for SDR devices? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Creating udev rules..."
            
            sudo tee /etc/udev/rules.d/99-sdr.rules > /dev/null <<EOF
# HackRF One
SUBSYSTEM=="usb", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6089", GROUP="plugdev", MODE="0666"

# RTL-SDR
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", GROUP="plugdev", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2832", GROUP="plugdev", MODE="0666"

# ADALM-PLUTO
SUBSYSTEM=="usb", ATTRS{idVendor}=="0456", ATTRS{idProduct}=="b673", GROUP="plugdev", MODE="0666"
EOF
            
            sudo udevadm control --reload-rules
            sudo udevadm trigger
            
            print_success "udev rules created"
            print_info "You may need to reconnect your SDR devices"
        else
            print_info "Skipping udev rules setup"
        fi
    fi
}

setup_docker() {
    print_header "Setting Up Docker (Optional)"
    
    read -p "Setup Docker environment? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if command -v docker &> /dev/null; then
            print_info "Docker already installed"
            
            # Build Docker image
            if [ -f "docker/Dockerfile" ]; then
                print_info "Building Docker image..."
                docker build -t drone-detector:dev -f docker/Dockerfile .
                print_success "Docker image built"
            fi
        else
            print_warning "Docker not installed"
            print_info "Install Docker from: https://docs.docker.com/get-docker/"
        fi
    else
        print_info "Skipping Docker setup"
    fi
}

setup_development_tools() {
    print_header "Setting Up Development Tools"
    
    # Install useful Python development tools
    print_info "Installing development tools..."
    
    source venv/bin/activate
    
    # Jupyter for notebooks
    pip install jupyter ipykernel
    python -m ipykernel install --user --name=drone-detector
    
    # Testing tools
    pip install pytest pytest-cov pytest-asyncio pytest-mock
    
    # Code quality tools
    pip install black isort flake8 mypy pylint
    
    # Debugging tools
    pip install ipdb pudb
    
    print_success "Development tools installed"
}

setup_precommit() {
    print_header "Setting Up Pre-commit Hooks"
    
    if command -v pre-commit &> /dev/null; then
        # Create .pre-commit-config.yaml if it doesn't exist
        if [ ! -f ".pre-commit-config.yaml" ]; then
            cat > .pre-commit-config.yaml <<EOF
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
  
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  
  - repo: https://github.com/PyCQA/isort
    rev: 5.12.0
    hooks:
      - id: isort
  
  - repo: https://github.com/PyCQA/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=100]
EOF
            print_success "Created .pre-commit-config.yaml"
        fi
        
        pre-commit install
        print_success "Pre-commit hooks configured"
    else
        print_warning "pre-commit not installed"
    fi
}

print_summary() {
    print_header "Setup Complete!"
    
    echo -e "${GREEN}"
    echo "╔════════════════════════════════════════════════════════════════════╗"
    echo "║                    Development Environment Ready                    ║"
    echo "╠════════════════════════════════════════════════════════════════════╣"
    echo "║                                                                    ║"
    echo "║  📁 Project Directory: $(pwd)                                      "
    echo "║  🐍 Python: $(source venv/bin/activate && python --version)        "
    echo "║  📦 Virtual Environment: venv/                                     "
    echo "║                                                                    ║"
    echo "║  🚀 Next Steps:                                                    ║"
    echo "║    1. Activate environment: source venv/bin/activate               ║"
    echo "║    2. Configure settings: edit config/*.yaml                       ║"
    echo "║    3. Update .env file with your credentials                       ║"
    echo "║    4. Run the system: python run.py                                ║"
    echo "║    5. Run tests: pytest                                            ║"
    echo "║                                                                    ║"
    echo "║  📚 Useful Commands:                                               ║"
    echo "║    - Start API: python -m api.main                                 ║"
    echo "║    - Run tests: pytest -v                                          ║"
    echo "║    - Format code: black .                                          ║"
    echo "║    - Check linting: flake8                                         ║"
    echo "║                                                                    ║"
    echo "╚════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "${YELLOW}"
    echo "⚠️  Important Notes:"
    echo "   - Activate virtual environment before running the system"
    echo "   - Update configuration files with your settings"
    echo "   - For production, use production configuration"
    echo -e "${NC}"
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
    print_header "Drone Detection System - Development Environment Setup"
    
    echo -e "${CYAN}This script will set up the complete development environment for the Drone Detection System.${NC}"
    echo ""
    
    # Check for root/sudo
    if [ "$EUID" -eq 0 ]; then
        print_warning "Running as root. It's recommended to run as a regular user."
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Run setup steps
    setup_system_dependencies
    setup_python_environment
    setup_database
    setup_configuration
    setup_mock_data
    setup_udev_rules
    setup_development_tools
    setup_precommit
    setup_docker
    setup_git_hooks
    
    print_summary
}

# Run main function
main "$@"