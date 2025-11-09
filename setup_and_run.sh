#!/bin/bash

# Simple setup and run script for macOS
# This script automatically installs everything needed and runs the app

echo "🚀 WhatsApp Bot Setup"
echo "===================="
echo ""

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "📦 Homebrew not found. Installing Homebrew..."
    echo "   (This may take a few minutes)"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon Macs
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo "✅ Homebrew is already installed"
fi

# Install Python if not installed
if ! command -v python3 &> /dev/null; then
    echo "📦 Python not found. Installing Python..."
    brew install python3
else
    echo "✅ Python is already installed: $(python3 --version)"
fi

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "✅ Virtual environment created and activated"
else
    echo "✅ Virtual environment already active"
fi

# Install dependencies
echo "📦 Installing dependencies..."
echo "   (This may take a few minutes)"
pip install --upgrade pip
pip install -r requirements.txt

# Check if Chrome is installed
if ! command -v google-chrome &> /dev/null && ! command -v chromium &> /dev/null; then
    echo "⚠️  Chrome/Chromium not found. Installing Chrome..."
    brew install --cask google-chrome
else
    echo "✅ Chrome is already installed"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 Starting WhatsApp Bot..."
echo "   The app will open in your browser at http://localhost:8501"
echo "   Press Ctrl+C to stop"
echo ""

# Run the app
streamlit run streamlit_app.py

