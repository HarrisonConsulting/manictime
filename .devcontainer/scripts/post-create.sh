#!/bin/bash
set -e

# Install the package in development mode
pip install -e .

# Install additional development dependencies
pip install -r requirements-dev.txt 2>/dev/null || echo "No requirements-dev.txt found, skipping"

# Wait for ManicTime server to be ready
echo "Waiting for ManicTime server..."
timeout 60 bash -c 'until curl -s http://manictime-server:8080/api/server/info; do sleep 1; done'

# Create test data if needed
python ./.devcontainer/scripts/create_test_data.py 2>/dev/null || echo "No create_test_data.py script found, skipping"

echo "Development environment setup complete!"