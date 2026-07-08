#!/bin/bash
# Setup script for Flight Analytics Assistant

set -e

echo "======================================="
echo "Flight Analytics Assistant Setup"
echo "======================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

echo "✓ Python detected: $(python3 --version)"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel -q

# Install dependencies
echo "Installing Python dependencies..."
echo "This may take 5-10 minutes on first install..."
pip install -r requirements.txt -q

echo ""
echo "✓ Python dependencies installed"
echo ""
echo "======================================="
echo "Setup Complete!"
echo "======================================="
echo ""
echo "To start the backend server, run:"
echo "  source venv/bin/activate"
echo "  python scripts/backend_server.py"
echo ""
echo "In another terminal, to start the frontend, run:"
echo "  pnpm dev"
echo ""
