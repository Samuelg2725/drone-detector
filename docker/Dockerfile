# Multi-stage Dockerfile for Drone Detector System
# Stages: base, builder, production, development

# ============================================================================
# Stage 1: Base
# ============================================================================
FROM python:3.11-slim-bookworm AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.7.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build dependencies
    gcc \
    g++ \
    make \
    cmake \
    pkg-config \
    # SDR libraries
    libhackrf-dev \
    librtlsdr-dev \
    libairspy-dev \
    libsoapysdr-dev \
    # Signal processing
    libfftw3-dev \
    libliquid-dev \
    # Utilities
    curl \
    git \
    ca-certificates \
    # PostgreSQL client for database
    libpq-dev \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ============================================================================
# Stage 2: Builder
# ============================================================================
FROM base AS builder

# Install Python build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev \
    python3-wheel \
    python3-setuptools \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY requirements.txt requirements-dev.txt pyproject.toml setup.py ./

# Install Python dependencies
RUN pip install --no-cache-dir \
    -r requirements.txt \
    gunicorn \
    uvicorn[standard]

# Copy application code
COPY . .

# Build any C extensions if needed
RUN python setup.py build_ext --inplace || true

# Run tests (optional - comment out for faster builds)
# RUN pytest tests/unit/ -v --tb=short

# ============================================================================
# Stage 3: Production
# ============================================================================
FROM base AS production

# Create non-root user
RUN useradd --create-home --shell /bin/bash drone \
    && chown -R drone:drone /app

# Copy installed packages from builder
COPY --from=builder --chown=drone:drone /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder --chown=drone:drone /usr/local/bin /usr/local/bin
COPY --from=builder --chown=drone:drone /app /app

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/models /app/config \
    && chown -R drone:drone /app/data /app/logs /app/models

# Copy configuration files
COPY config/*.yaml config/*.json /app/config/

# Copy model files (if any)
COPY models/*.pkl /app/models/ 2>/dev/null || true

# Copy scripts
COPY scripts/*.py /app/scripts/

# Create entrypoint script (will be added below)
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh

# Switch to non-root user
USER drone

# Expose ports
# API server
EXPOSE 8888
# WebSocket server
EXPOSE 8889
# Metrics endpoint
EXPOSE 9090
# Prometheus metrics
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8888/health || exit 1

# Entry point
ENTRYPOINT ["/app/docker/entrypoint.sh"]

# Default command
CMD ["api"]

# ============================================================================
# Stage 4: Development
# ============================================================================
FROM base AS development

# Install development dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    vim \
    nano \
    htop \
    tmux \
    iputils-ping \
    net-tools \
    strace \
    gdb \
    valgrind \
    # Development tools
    build-essential \
    python3-pip \
    python3-venv \
    # Testing tools
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install dev Python packages
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy application code
COPY --chown=drone:drone . /app

# Install pre-commit hooks
RUN pre-commit install

# Set environment for development
ENV ENVIRONMENT=development \
    DEBUG=True \
    LOG_LEVEL=DEBUG

# Create non-root user if not exists
RUN if ! id -u drone >/dev/null 2>&1; then \
    useradd --create-home --shell /bin/bash drone; \
    fi \
    && chown -R drone:drone /app

USER drone

# Expose additional ports for debugging
EXPOSE 5678  # Debugger port

# Override entrypoint for development
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["dev"]

# ============================================================================
# Stage 5: GPU (for ML inference)
# ============================================================================
FROM nvidia/cuda:12.1-runtime-ubuntu22.04 AS gpu

# Install Python and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3-pip \
    python3-dev \
    libhackrf-dev \
    librtlsdr-dev \
    libfftw3-dev \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.11 /usr/bin/python

WORKDIR /app

# Copy requirements with GPU support
COPY requirements.txt .
RUN pip install --no-cache-dir \
    -r requirements.txt \
    torch torchvision --index-url https://download.pytorch.org/whl/cu118

# Copy application
COPY . .

ENV CUDA_VISIBLE_DEVICES=0 \
    TF_CPP_MIN_LOG_LEVEL=2

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["api"]

# ============================================================================
# Stage 6: Raspberry Pi / ARM (for edge deployment)
# ============================================================================
FROM arm32v7/python:3.11-slim-bookworm AS arm

# Install ARM-specific dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    cmake \
    libhackrf-dev \
    librtlsdr-dev \
    libfftw3-dev \
    libatomic1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Optimize for ARM
ENV OPENBLAS_CORETYPE=ARMV8 \
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2

EXPOSE 8888 8889

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["api"]