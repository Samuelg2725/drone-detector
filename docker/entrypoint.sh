#!/bin/bash
# ============================================================================
# Drone Detector System - Docker Entrypoint Script
# ============================================================================
# This script handles container initialization, environment setup,
# service orchestration, and graceful shutdown for all deployment types.
# ============================================================================

set -euo pipefail

# ============================================================================
# Global Configuration
# ============================================================================
readonly SCRIPT_NAME=$(basename "$0")
readonly SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
readonly APP_DIR="/app"
readonly DATA_DIR="/app/data"
readonly LOG_DIR="/app/logs"
readonly CONFIG_DIR="/app/config"
readonly MODELS_DIR="/app/models"

# Default values
: "${ENVIRONMENT:=development}"
: "${LOG_LEVEL:=INFO}"
: "${DEBUG:=false}"
: "${SECRET_KEY:=}"
: "${PORT:=8888}"
: "${WEBSOCKET_PORT:=8889}"
: "${METRICS_PORT:=9090}"
: "${WORKER_CONCURRENCY:=4}"
: "${DATABASE_URL:=}"
: "${REDIS_URL:=}"
: "${HARDWARE_TYPE:=auto}"
: "${USE_MOCK_HARDWARE:=false}"

# Color codes for output (only if terminal supports)
if [ -t 1 ]; then
    readonly RED='\033[0;31m'
    readonly GREEN='\033[0;32m'
    readonly YELLOW='\033[1;33m'
    readonly BLUE='\033[0;34m'
    readonly PURPLE='\033[0;35m'
    readonly CYAN='\033[0;36m'
    readonly WHITE='\033[1;37m'
    readonly NC='\033[0m' # No Color
else
    readonly RED=''
    readonly GREEN=''
    readonly YELLOW=''
    readonly BLUE=''
    readonly PURPLE=''
    readonly CYAN=''
    readonly WHITE=''
    readonly NC=''
fi

# ============================================================================
# Logging Functions
# ============================================================================
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*" | tee -a "${LOG_DIR}/entrypoint.log" 2>/dev/null || true
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*" | tee -a "${LOG_DIR}/entrypoint.log" 2>/dev/null || true
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*" | tee -a "${LOG_DIR}/entrypoint.log" 2>/dev/null || true
}

log_debug() {
    if [ "${DEBUG}" = "true" ] || [ "${LOG_LEVEL}" = "DEBUG" ]; then
        echo -e "${BLUE}[DEBUG]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*" | tee -a "${LOG_DIR}/entrypoint.log" 2>/dev/null || true
    fi
}

print_banner() {
    echo -e "${CYAN}"
    cat << "EOF"
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║     ██████╗ ██████╗  ██████╗ ███╗   ██╗███████╗              ║
    ║     ██╔══██╗██╔══██╗██╔═══██╗████╗  ██║██╔════╝              ║
    ║     ██║  ██║██████╔╝██║   ██║██╔██╗ ██║█████╗                ║
    ║     ██║  ██║██╔══██╗██║   ██║██║╚██╗██║██╔══╝                ║
    ║     ██████╔╝██║  ██║╚██████╔╝██║ ╚████║███████╗              ║
    ║     ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝              ║
    ║                                                               ║
    ║     ██████╗ ███████╗████████╗███████╗██╗   ██╗████████╗      ║
    ║     ██╔══██╗██╔════╝╚══██╔══╝██╔════╝╚██╗ ██╔╝╚══██╔══╝      ║
    ║     ██║  ██║█████╗     ██║   █████╗   ╚████╔╝    ██║         ║
    ║     ██║  ██║██╔══╝     ██║   ██╔══╝    ╚██╔╝     ██║         ║
    ║     ██████╔╝███████╗   ██║   ███████╗   ██║      ██║         ║
    ║     ╚═════╝ ╚══════╝   ╚═╝   ╚══════╝   ╚═╝      ╚═╝         ║
    ║                                                               ║
    ║                   Drone Detection System                      ║
    ║                         v1.0.0                                ║
    ╚═══════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
    log_info "Starting Drone Detector System"
    log_info "Environment: ${ENVIRONMENT}"
    log_info "Log Level: ${LOG_LEVEL}"
    log_info "Hardware Type: ${HARDWARE_TYPE}"
    log_info "Mock Hardware: ${USE_MOCK_HARDWARE}"
}

# ============================================================================
# Environment Validation
# ============================================================================
validate_environment() {
    log_info "Validating environment..."
    
    # Check required directories
    for dir in "${APP_DIR}" "${DATA_DIR}" "${LOG_DIR}" "${CONFIG_DIR}"; do
        if [ ! -d "${dir}" ]; then
            log_warn "Creating directory: ${dir}"
            mkdir -p "${dir}"
        fi
    done
    
    # Check for production secrets
    if [ "${ENVIRONMENT}" = "production" ]; then
        if [ -z "${SECRET_KEY}" ]; then
            log_error "SECRET_KEY environment variable is required in production"
            exit 1
        fi
        
        if [ ${#SECRET_KEY} -lt 32 ]; then
            log_error "SECRET_KEY must be at least 32 characters long in production"
            exit 1
        fi
        
        if [ -z "${DATABASE_URL}" ]; then
            log_error "DATABASE_URL environment variable is required in production"
            exit 1
        fi
        
        if [ -z "${REDIS_URL}" ]; then
            log_error "REDIS_URL environment variable is required in production"
            exit 1
        fi
    fi
    
    # Check hardware availability
    if [ "${USE_MOCK_HARDWARE}" != "true" ] && [ "${HARDWARE_TYPE}" != "mock" ]; then
        check_hardware_availability
    fi
    
    log_info "Environment validation completed successfully"
}

# ============================================================================
# Hardware Availability Check
# ============================================================================
check_hardware_availability() {
    log_info "Checking SDR hardware availability..."
    
    # Check for HackRF
    if command -v hackrf_info &> /dev/null; then
        if hackrf_info &> /dev/null; then
            log_info "HackRF One detected"
            export HARDWARE_AVAILABLE="hackrf"
            return 0
        fi
    fi
    
    # Check for RTL-SDR
    if command -v rtl_test &> /dev/null; then
        if rtl_test -t &> /dev/null; then
            log_info "RTL-SDR dongle detected"
            export HARDWARE_AVAILABLE="rtl_sdr"
            return 0
        fi
    fi
    
    # Check for ADALM-PLUTO
    if [ -e "/dev/pluto" ] || [ -e "/dev/ttyACM0" ]; then
        log_info "ADALM-PLUTO detected"
        export HARDWARE_AVAILABLE="pluto"
        return 0
    fi
    
    log_warn "No SDR hardware detected. Falling back to mock hardware."
    export USE_MOCK_HARDWARE="true"
    export HARDWARE_TYPE="mock"
}

# ============================================================================
# Database Setup
# ============================================================================
setup_database() {
    log_info "Setting up database..."
    
    # Wait for database to be ready if using external DB
    if [[ "${DATABASE_URL}" =~ postgresql:// ]]; then
        log_info "Waiting for PostgreSQL to be ready..."
        
        # Extract host and port from DATABASE_URL
        local db_host=$(echo "${DATABASE_URL}" | sed -n 's/.*@\([^:]*\):.*/\1/p')
        local db_port=$(echo "${DATABASE_URL}" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
        db_host=${db_host:-"postgres"}
        db_port=${db_port:-"5432"}
        
        local max_attempts=30
        local attempt=0
        
        while [ $attempt -lt $max_attempts ]; do
            if nc -z "${db_host}" "${db_port}" 2>/dev/null; then
                log_info "PostgreSQL is ready"
                break
            fi
            attempt=$((attempt + 1))
            log_debug "Waiting for PostgreSQL... (attempt ${attempt}/${max_attempts})"
            sleep 2
        done
        
        if [ $attempt -eq $max_attempts ]; then
            log_error "PostgreSQL not ready after ${max_attempts} attempts"
            if [ "${ENVIRONMENT}" = "production" ]; then
                exit 1
            fi
        fi
    fi
    
    # Run database migrations
    if [ -f "${APP_DIR}/scripts/migrate.py" ]; then
        log_info "Running database migrations..."
        if python "${APP_DIR}/scripts/migrate.py" --upgrade head; then
            log_info "Database migrations completed successfully"
        else
            log_error "Database migrations failed"
            if [ "${ENVIRONMENT}" = "production" ]; then
                exit 1
            fi
        fi
    else
        log_warn "Migration script not found, skipping database setup"
    fi
}

# ============================================================================
# Configuration Validation
# ============================================================================
validate_configuration() {
    log_info "Validating configuration..."
    
    # Check for required config files
    local required_configs=("system.yaml" "hardware.yaml")
    
    for config in "${required_configs[@]}"; do
        if [ ! -f "${CONFIG_DIR}/${config}" ]; then
            log_error "Required configuration file not found: ${CONFIG_DIR}/${config}"
            if [ "${ENVIRONMENT}" = "production" ]; then
                exit 1
            fi
        fi
    done
    
    # Validate YAML syntax
    if command -v python &> /dev/null; then
        for config in "${CONFIG_DIR}"/*.yaml; do
            if [ -f "${config}" ]; then
                if ! python -c "import yaml; yaml.safe_load(open('${config}'))" 2>/dev/null; then
                    log_error "Invalid YAML syntax in ${config}"
                    if [ "${ENVIRONMENT}" = "production" ]; then
                        exit 1
                    fi
                fi
            fi
        done
    fi
    
    log_info "Configuration validation completed"
}

# ============================================================================
# Signal Handlers for Graceful Shutdown
# ============================================================================
setup_signal_handlers() {
    log_info "Setting up signal handlers..."
    
    # Function to handle SIGTERM
    handle_sigterm() {
        log_info "Received SIGTERM signal, shutting down gracefully..."
        SHUTDOWN_REQUESTED=true
        # Forward signal to child processes
        if [ -n "${PID:-}" ] && kill -0 "${PID}" 2>/dev/null; then
            log_debug "Sending SIGTERM to process ${PID}"
            kill -TERM "${PID}" 2>/dev/null || true
        fi
        exit 0
    }
    
    # Function to handle SIGINT
    handle_sigint() {
        log_info "Received SIGINT signal, shutting down gracefully..."
        SHUTDOWN_REQUESTED=true
        if [ -n "${PID:-}" ] && kill -0 "${PID}" 2>/dev/null; then
            log_debug "Sending SIGINT to process ${PID}"
            kill -INT "${PID}" 2>/dev/null || true
        fi
        exit 0
    }
    
    # Register signal handlers
    trap handle_sigterm SIGTERM
    trap handle_sigint SIGINT
    
    log_debug "Signal handlers registered"
}

# ============================================================================
# Start Services
# ============================================================================
start_api() {
    log_info "Starting API server on port ${PORT}..."
    
    if [ "${ENVIRONMENT}" = "development" ]; then
        # Development mode with auto-reload
        exec uvicorn api.main:app \
            --host 0.0.0.0 \
            --port "${PORT}" \
            --reload \
            --reload-dir "${APP_DIR}" \
            --log-level "${LOG_LEVEL,,}" \
            --access-log \
            --use-colors
    else
        # Production mode with Gunicorn
        local workers=${GUNICORN_WORKERS:-$(nproc --all 2>/dev/null || echo 4)}
        local threads=${GUNICORN_THREADS:-2}
        
        log_info "Starting Gunicorn with ${workers} workers and ${threads} threads"
        exec gunicorn api.main:app \
            --worker-class uvicorn.workers.UvicornWorker \
            --workers "${workers}" \
            --threads "${threads}" \
            --bind "0.0.0.0:${PORT}" \
            --timeout "${GUNICORN_TIMEOUT:-120}" \
            --keep-alive "${GUNICORN_KEEP_ALIVE:-5}" \
            --max-requests "${GUNICORN_MAX_REQUESTS:-1000}" \
            --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-50}" \
            --graceful-timeout 30 \
            --log-level "${LOG_LEVEL,,}" \
            --access-logfile - \
            --error-logfile -
    fi
}

start_worker() {
    log_info "Starting background worker with concurrency ${WORKER_CONCURRENCY}..."
    
    if [ -f "${APP_DIR}/app/workers/worker.py" ]; then
        exec python "${APP_DIR}/app/workers/worker.py" \
            --concurrency "${WORKER_CONCURRENCY}" \
            --log-level "${LOG_LEVEL,,}"
    else
        log_error "Worker script not found"
        exit 1
    fi
}

start_beat() {
    log_info "Starting scheduler (beat) service..."
    
    if [ -f "${APP_DIR}/app/workers/beat.py" ]; then
        exec python "${APP_DIR}/app/workers/beat.py" \
            --log-level "${LOG_LEVEL,,}"
    else
        log_error "Beat script not found"
        exit 1
    fi
}

start_websocket() {
    log_info "Starting WebSocket server on port ${WEBSOCKET_PORT}..."
    
    if [ -f "${APP_DIR}/infrastructure/messaging/websocket_server.py" ]; then
        exec python "${APP_DIR}/infrastructure/messaging/websocket_server.py" \
            --port "${WEBSOCKET_PORT}" \
            --log-level "${LOG_LEVEL,,}"
    else
        log_error "WebSocket server script not found"
        exit 1
    fi
}

start_all() {
    log_info "Starting all services in same container..."
    
    # Start API in background
    start_api &
    local api_pid=$!
    
    # Start worker in background
    start_worker &
    local worker_pid=$!
    
    # Start beat in background
    start_beat &
    local beat_pid=$!
    
    # Wait for any service to exit
    wait -n $api_pid $worker_pid $beat_pid
    local exit_code=$?
    
    # Forward exit code
    exit $exit_code
}

start_dev() {
    log_info "Starting development environment..."
    
    # Install development dependencies if not in production
    if [ -f "${APP_DIR}/requirements-dev.txt" ]; then
        log_info "Installing development dependencies..."
        pip install -r "${APP_DIR}/requirements-dev.txt" --quiet || log_warn "Failed to install dev dependencies"
    fi
    
    # Start all services
    start_all
}

# ============================================================================
# Health Check
# ============================================================================
run_health_check() {
    log_debug "Running health check..."
    
    local health_url="http://localhost:${PORT}/health"
    
    if curl -f -s -o /dev/null "${health_url}" 2>/dev/null; then
        log_debug "Health check passed"
        exit 0
    else
        log_warn "Health check failed"
        exit 1
    fi
}

# ============================================================================
# Main Entry Point
# ============================================================================
main() {
    # Print banner
    print_banner
    
    # Create log directory if it doesn't exist
    mkdir -p "${LOG_DIR}" 2>/dev/null || true
    
    # Validate environment
    validate_environment
    
    # Setup database
    setup_database
    
    # Validate configuration
    validate_configuration
    
    # Setup signal handlers
    setup_signal_handlers
    
    # Determine which service to start
    local service="${1:-api}"
    
    log_info "Starting service: ${service}"
    
    case "${service}" in
        api)
            start_api
            ;;
        worker)
            start_worker
            ;;
        beat)
            start_beat
            ;;
        websocket)
            start_websocket
            ;;
        all)
            start_all
            ;;
        dev)
            start_dev
            ;;
        health)
            run_health_check
            ;;
        *)
            log_error "Unknown service: ${service}"
            echo "Usage: $0 {api|worker|beat|websocket|all|dev|health}"
            exit 1
            ;;
    esac
}

# ============================================================================
# Script Execution
# ============================================================================
# Set up trap for cleanup on exit
cleanup() {
    log_debug "Cleaning up temporary files..."
    # Add any cleanup logic here
    exit 0
}
trap cleanup EXIT

# Run main function with all arguments
main "$@"