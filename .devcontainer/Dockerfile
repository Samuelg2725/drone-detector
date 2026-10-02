# Development Container for Drone Detector System
# Uses Python 3.11 with SDR support and development tools

FROM mcr.microsoft.com/devcontainers/python:3.11-bookworm

# ============================================================================
# Container Metadata
# ============================================================================
LABEL maintainer="Drone Detector Team <dev@drone-detector.com>"
LABEL description="Development container for Drone Detector System"
LABEL version="1.0.0"

# ============================================================================
# Environment Variables
# ============================================================================
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.7.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    NVM_DIR="/home/vscode/.nvm" \
    NODE_VERSION="20"

# ============================================================================
# System Dependencies
# ============================================================================
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install -y --no-install-recommends \
    # Build essentials
    build-essential \
    gcc \
    g++ \
    make \
    cmake \
    pkg-config \
    libssl-dev \
    libffi-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libncurses5-dev \
    libgdbm-dev \
    zlib1g-dev \
    uuid-dev \
    # SDR Libraries
    libhackrf-dev \
    librtlsdr-dev \
    libairspy-dev \
    libsoapysdr-dev \
    libbladerf-dev \
    liblimesuite-dev \
    libuhd-dev \
    libad9361-dev \
    # Signal Processing
    libfftw3-dev \
    libliquid-dev \
    libvolk2-dev \
    libgsl-dev \
    # Database Libraries
    libpq-dev \
    libmysqlclient-dev \
    libsqlite3-dev \
    # Graphics & Visualization
    libfreetype6-dev \
    libpng-dev \
    libjpeg-dev \
    libtiff-dev \
    libharfbuzz-dev \
    libfontconfig1-dev \
    libxcb-shape0-dev \
    libxcb-xfixes0-dev \
    libxcb1-dev \
    libx11-dev \
    libgl1-mesa-dev \
    # USB & Hardware Access
    libusb-1.0-0-dev \
    libusb-dev \
    libudev-dev \
    # Network & Communication
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    # Testing Tools
    chromium \
    firefox-esr \
    # System Utilities
    htop \
    tmux \
    vim \
    nano \
    git \
    curl \
    wget \
    unzip \
    zip \
    tree \
    jq \
    less \
    net-tools \
    iputils-ping \
    dnsutils \
    strace \
    gdb \
    valgrind \
    lsof \
    # Documentation
    pandoc \
    graphviz \
    doxygen \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ============================================================================
# Python Development Tools
# ============================================================================
RUN pip install --no-cache-dir --upgrade \
    pip \
    wheel \
    setuptools \
    poetry \
    pipenv \
    virtualenv \
    tox \
    pre-commit \
    black \
    isort \
    flake8 \
    pylint \
    mypy \
    bandit \
    safety \
    pydocstyle \
    pytest \
    pytest-cov \
    pytest-xdist \
    pytest-asyncio \
    pytest-timeout \
    pytest-benchmark \
    pytest-mock \
    pytest-env \
    pytest-html \
    pytest-xdist \
    ipython \
    ipdb \
    pudb \
    watchdog \
    httpie \
    jupyter \
    jupyterlab \
    nbconvert \
    voila \
    # Data Science
    numpy \
    scipy \
    pandas \
    matplotlib \
    seaborn \
    scikit-learn \
    scikit-image \
    sympy \
    statsmodels \
    # ML/DL Frameworks
    torch \
    torchvision \
    tensorflow \
    keras \
    xgboost \
    lightgbm \
    catboost \
    # Signal Processing
    pyfftw \
    pywt \
    spiceypy \
    # SDR Python Bindings
    pyhackrf \
    pyrtlsdr \
    pyadi-iio \
    soapysdr \
    # Web Frameworks
    fastapi \
    uvicorn \
    gunicorn \
    httpx \
    aiohttp \
    websockets \
    # Database
    asyncpg \
    psycopg2-binary \
    redis \
    sqlalchemy \
    alembic \
    # Utilities
    python-dotenv \
    pyyaml \
    click \
    rich \
    tqdm \
    joblib \
    schedule \
    celery \
    flower

# ============================================================================
# Node.js Setup (for frontend development)
# ============================================================================
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash \
    && . "$NVM_DIR/nvm.sh" \
    && nvm install ${NODE_VERSION} \
    && nvm use ${NODE_VERSION} \
    && nvm alias default ${NODE_VERSION} \
    && npm install -g npm@latest \
    && npm install -g \
    yarn \
    pm2 \
    nodemon \
    typescript \
    ts-node \
    webpack \
    webpack-cli \
    eslint \
    prettier

# ============================================================================
# SDR Device Rules
# ============================================================================
COPY .devcontainer/99-sdr.rules /etc/udev/rules.d/99-sdr.rules
RUN udevadm control --reload-rules && udevadm trigger

# ============================================================================
# Create Non-Root User
# ============================================================================
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# ============================================================================
# Git Configuration
# ============================================================================
RUN git config --system init.defaultBranch main \
    && git config --system core.autocrlf input

# ============================================================================
# Create Working Directory
# ============================================================================
WORKDIR /workspace
RUN chown -R $USERNAME:$USERNAME /workspace

# ============================================================================
# Create Data Directories
# ============================================================================
RUN mkdir -p /workspace/data \
    /workspace/data/iq/live \
    /workspace/data/iq/replay \
    /workspace/data/iq/synthetic \
    /workspace/data/iq/mock \
    /workspace/data/logs \
    /workspace/data/exports \
    /workspace/data/recordings \
    /workspace/logs \
    /workspace/models \
    /workspace/notebooks \
    && chown -R $USERNAME:$USERNAME /workspace

# ============================================================================
# Shell Configuration
# ============================================================================
COPY .devcontainer/.bashrc /home/$USERNAME/.bashrc
COPY .devcontainer/.bash_aliases /home/$USERNAME/.bash_aliases
COPY .devcontainer/.gitconfig /home/$USERNAME/.gitconfig

# ============================================================================
# Python Startup Script
# ============================================================================
RUN mkdir -p /home/$USERNAME/.ipython/profile_default/startup \
    && echo 'print("\n🐍 Drone Detector Development Environment Ready!")' > /home/$USERNAME/.ipython/profile_default/startup/00-welcome.py \
    && echo 'import numpy as np' >> /home/$USERNAME/.ipython/profile_default/startup/01-imports.py \
    && echo 'import pandas as pd' >> /home/$USERNAME/.ipython/profile_default/startup/01-imports.py \
    && echo 'import matplotlib.pyplot as plt' >> /home/$USERNAME/.ipython/profile_default/startup/01-imports.py \
    && chown -R $USERNAME:$USERNAME /home/$USERNAME/.ipython

# ============================================================================
# Pre-commit Hooks
# ============================================================================
RUN pip install pre-commit \
    && pre-commit install

# ============================================================================
# Port Exposures
# ============================================================================
# API Server
EXPOSE 8888
# WebSocket Server
EXPOSE 8889
# Metrics Endpoint
EXPOSE 9090
# Debugger
EXPOSE 5678
# Jupyter
EXPOSE 8888
# PostgreSQL
EXPOSE 5432
# Redis
EXPOSE 6379
# Grafana
EXPOSE 3000
# Prometheus
EXPOSE 9090
# MinIO API
EXPOSE 9000
# MinIO Console
EXPOSE 9001
# pgAdmin
EXPOSE 5050
# Redis Commander
EXPOSE 8081

# ============================================================================
# Health Check
# ============================================================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8888/health || exit 1

# ============================================================================
# Entrypoint
# ============================================================================
COPY .devcontainer/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# ============================================================================
# Switch to non-root user
# ============================================================================
USER $USERNAME

# ============================================================================
# Default Command
# ============================================================================
CMD ["bash"]