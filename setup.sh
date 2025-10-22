#!/bin/bash
# QR Live Protocol - Quick Setup Script
# Modern setup using uv for optimal performance

set -e

echo "🔲 QR Live Protocol (QRLP) - Modern Setup"
echo "=============================================="

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Installing uv..."
    echo ""
    echo "Install uv by running:"
    echo "curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "or"
    echo "pip install uv"
    echo ""
    exit 1
fi

echo "✅ uv is available"

# Create virtual environment
echo "🏗️  Creating virtual environment..."
uv venv

# Activate and install
echo "📦 Installing QRLP with development dependencies..."
source .venv/bin/activate
uv pip install -e .[dev]

# Verify installation
echo "🔍 Verifying installation..."
if qrlp --help &> /dev/null; then
    echo "✅ QRLP CLI is working!"
else
    echo "❌ QRLP CLI failed. Check installation."
    exit 1
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Available commands:"
echo "  qrlp live              # Start live QR generation"
echo "  qrlp generate           # Generate single QR code"
echo "  qrlp verify <data>      # Verify QR data"
echo "  python main.py          # Run comprehensive demo"
echo ""
echo "For OBS Studio integration:"
echo "  1. Add Browser Source"
echo "  2. URL: http://localhost:8080/viewer"
echo "  3. Width: 800, Height: 600"
echo ""
echo "Start with: qrlp live"
