#!/bin/bash
# Post-attach script for dev container

echo "🚀 Attached to development container"

# Display helpful information
echo ""
echo "📡 Drone Detector Development Environment"
echo "========================================="
echo "API Server:      http://localhost:8888"
echo "API Docs:        http://localhost:8888/docs"
echo "WebSocket:       ws://localhost:8889"
echo "Jupyter:         http://localhost:8888/lab"
echo ""
echo "Database:        postgresql://drone_user:drone_password@localhost:5432/drone_detector"
echo "Redis:           redis://localhost:6379"
echo ""
echo "Mock Hardware:   Enabled (USE_MOCK_HARDWARE=true)"
echo "Log Level:       DEBUG"
echo ""
echo "Useful commands:"
echo "  pytest tests/ -v                    # Run tests"
echo "  python run.py --mock                # Run application"
echo "  jupyter lab                         # Start Jupyter"
echo "  python scripts/train_model.py       # Train ML model"