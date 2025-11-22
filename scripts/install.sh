#!/bin/bash
# Amazon Fresh Fetch - macOS/Linux Installer

echo "=========================================="
echo "  Amazon Fresh Fetch - Installation"
echo "=========================================="
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed!"
    echo "Please install Python 3.8 or higher from https://www.python.org/downloads/"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✅ Found Python $PYTHON_VERSION"

# Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
echo ""
echo "⬆️  Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo ""
echo "📥 Installing dependencies (this may take a few minutes)..."
pip install -r requirements.txt --quiet

# Install Playwright browsers
echo ""
echo "🌐 Installing browser automation (Playwright)..."
playwright install chromium

# Setup .env file
echo ""
if [ ! -f ".env" ]; then
    echo "🔑 Setting up API key..."
    echo ""
    echo "Please enter your Google API Key"
    echo "(Get it from: https://makersuite.google.com/app/apikey)"
    read -p "API Key: " api_key
    echo "GOOGLE_API_KEY=$api_key" > .env
    echo "✅ API key saved to .env"
else
    echo "ℹ️  .env file already exists, skipping API key setup"
fi

# Make launch script executable
chmod +x launch.sh

echo ""
echo "=========================================="
echo "  ✅ Installation Complete!"
echo "=========================================="
echo ""
echo "To launch the app, run: ./launch.sh"
echo "Or double-click the launch.sh file"
echo ""
