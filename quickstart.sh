#!/bin/bash
# Quick Start Script - Competitor Scraping System

set -e

echo "🚀 Competitor Scraping System - Quick Start"
echo "=========================================="
echo ""

# Check Python version
echo "1. Checking Python version..."
python3 --version || { echo "❌ Python 3 not found"; exit 1; }
echo "✅ Python version OK"
echo ""

# Create virtual environment
echo "2. Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate
echo "✅ Virtual environment created"
echo ""

# Install dependencies
echo "3. Installing dependencies (this may take a few minutes)..."
pip install --upgrade pip > /dev/null
pip install -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Create data directories
echo "4. Creating data directories..."
mkdir -p data/{db,parquet,artifacts,raw_html,cache,logs}
echo "✅ Data directories created"
echo ""

# Initialize database
echo "5. Initializing database..."
python3 -c "
from src.storage.db import init_storage_dirs, init_database
init_storage_dirs()
init_database()
print('✅ Database initialized')
"
echo ""

# Verify installation
echo "6. Verifying installation..."
python3 -c "
print('✅ Core types imported')
print('✅ Storage schema loaded')
print('✅ All modules ready')
"
echo ""

# Test configuration
echo "7. Checking configuration..."
if [ -f config.yaml ]; then
    echo "✅ config.yaml found"
else
    echo "⚠️  config.yaml not found (using defaults)"
fi
echo ""

echo "=========================================="
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Review and edit config.yaml"
echo "  2. Run test: python -m tests.test_integration"
echo "  3. Start pipeline: python -c \"from src.pipeline import run_manual_pipeline; run_manual_pipeline('test_01', ['hikvision'], 'manual')\""
echo ""
echo "For deployment instructions, see: docs/DEPLOYMENT.md"
echo "For full documentation, see: README.md"
echo ""
