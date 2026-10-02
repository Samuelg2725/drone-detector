#!/bin/bash
# Entrypoint script for dev container

set -e

echo "🐍 Drone Detector Development Container"

# Check if we should run the application
if [ "${RUN_DRONE_DETECTOR}" = "true" ]; then
    echo "Starting Drone Detector API..."
    exec python run.py --mock --debug
else
    # Just run the command (usually bash)
    exec "$@"
fi