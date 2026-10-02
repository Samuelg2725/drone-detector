#!/bin/bash
# Post-start script for dev container

echo "🚀 Starting development services..."

# Start PostgreSQL (if not already running)
sudo service postgresql start || true

# Start Redis (if not already running)
sudo service redis-server start || true

echo "✅ Development services started!"