#!/bin/bash

# Fix OpenAI library compatibility issue
# This script upgrades/downgrades OpenAI to a compatible version

echo "🔧 Fixing OpenAI library compatibility issue..."
echo ""

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Virtual environment not active"
    echo "   Activating virtual environment..."
    if [ -d "venv" ]; then
        source venv/bin/activate
        echo "✅ Virtual environment activated"
    else
        echo "❌ Virtual environment not found!"
        echo "   Please run: python3 -m venv venv && source venv/bin/activate"
        exit 1
    fi
fi

echo "📦 Current OpenAI version:"
pip show openai | grep Version || echo "   OpenAI not installed"

echo ""
echo "🔄 Installing compatible OpenAI version..."

# Try installing a stable version that works with Python 3.9
pip install --upgrade 'openai>=1.12.0,<2.0' --quiet

if [ $? -eq 0 ]; then
    echo "✅ OpenAI library updated successfully"
    echo ""
    echo "📦 New OpenAI version:"
    pip show openai | grep Version
    echo ""
    echo "✅ Fix complete! Try running the script again."
else
    echo "⚠️  Failed to update OpenAI"
    echo "   Trying alternative version..."
    pip install --upgrade 'openai==1.12.0' --quiet
    if [ $? -eq 0 ]; then
        echo "✅ Installed OpenAI 1.12.0 (stable version)"
    else
        echo "❌ Failed to install compatible version"
        echo "   Please try manually: pip install --upgrade openai"
    fi
fi

