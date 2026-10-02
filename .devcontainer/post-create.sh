#!/bin/bash
# Post-create script for dev container

echo "🚀 Running post-create setup..."

# Install project dependencies
pip install -e .

# Setup pre-commit hooks
pre-commit install

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file from example"
fi

# Setup database if needed
if [ -f "scripts/setup_db.py" ]; then
    python scripts/setup_db.py --dev
fi

echo "✅ Post-create setup complete!"